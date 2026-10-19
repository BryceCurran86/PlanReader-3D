"""Verified V1 customer takeoff -> client-priced, source-linked estimate.

Never infers a physical quantity, authenticates missing original PDF bytes,
alters a signed V1 issuer, or publishes a frozen Full Plan V2 score.
All money is supplied by an explicit client rate book, not benchmark gold.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_HALF_UP
import hashlib
import io
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from pb_customer_output_verification import (
    _customer_quantity_id,
    verify_sealed_customer_output,
)
from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys
from tools.run_gpt3_original_byte_gated_exact_project import FROZEN_ROOT


_CENT = Decimal("0.01")
_HUNDRED = Decimal("100")
_SCOPES = ("quantity", "semantic", "family")
_COMPONENTS = ("material", "labour", "plant", "subcontract")
_MAX_MONEY = Decimal("1000000000000")


def _decimal(value: Any, name: str, *, cap: Decimal = _MAX_MONEY) -> Decimal:
    if type(value) not in (str, int) or type(value) is str and not value.strip():
        raise ValueError(f"{name} requires exact decimal string or integer")
    try:
        result = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} is not a decimal") from exc
    if not result.is_finite() or result < 0 or result > cap:
        raise ValueError(f"{name} must be finite nonnegative and within the safe bound")
    return result


def _currency(value: Any) -> str:
    if type(value) is not str or re.fullmatch("[A-Z]{3}", value) is None:
        raise ValueError("client rate book needs explicit ISO-style currency")
    return value


def _money(value: Decimal) -> str:
    return str(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def _number(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _percentage(book: Mapping[str, Any], name: str) -> Decimal:
    if name not in book:
        raise ValueError(f"client rates require explicit {name}")
    return _decimal(book[name], name, cap=_HUNDRED)


def _equivalent_pricing_unit(unit: str) -> str:
    """Normalize exact notation equivalence, never transform a measured value.

    Rate cards may use m² where the source-owned sealed unit is m2, or 'each'
    where the signed physical count is ea. These are notation aliases only:
    area, volume, linear distance and object counts never cross dimensions.
    """
    aliases = {
        "m²": "m2", "sqm": "m2", "m2": "m2",
        "m³": "m3", "m3": "m3",
        "lm": "m", "m": "m",
        "ea": "ea", "each": "ea", "nr": "ea",
        "no": "ea", "no.": "ea", "number": "ea",
    }
    return aliases.get(unit.lower(), unit)


def _rates(rate_book: Mapping[str, Any]) -> dict[tuple[str, str, str], dict]:
    raw = rate_book.get("rates")
    if type(raw) is not list:
        raise ValueError("client rate book must contain rates array")
    cards: dict[tuple[str, str, str], dict] = {}
    for card in raw:
        if type(card) is not dict:
            raise ValueError("rate card must be an object")
        scope, key, unit = card.get("scope"), card.get("key"), card.get("unit")
        if (scope not in _SCOPES or type(key) is not str or not key
            or key != key.strip() or type(unit) is not str or not unit
            or unit != unit.strip()):
            raise ValueError("rate card requires exact scope, source key and unit")
        identity = (scope, key, _equivalent_pricing_unit(unit))
        if identity in cards:
            raise ValueError("duplicate client rate card")
        values = {name: _decimal(card[name], name)
                  for name in _COMPONENTS if name in card}
        if len(values) != len(_COMPONENTS):
            raise ValueError("rate card must supply material, labour, plant and subcontract")
        values["labour_hours_per_unit"] = _decimal(
            card.get("labour_hours_per_unit", "0"), "labour_hours_per_unit")
        values["markup_pct"] = _decimal(
            card.get("markup_pct", "0"), "markup_pct", cap=_HUNDRED)
        values["waste_pct"] = _decimal(
            card.get("waste_pct", "0"), "waste_pct", cap=_HUNDRED)
        cards[identity] = values
    return cards


def _choose_rate(quantity: Any, cards: dict) -> tuple[tuple[str, str, str] | None, dict | None]:
    for scope, key in (
        ("quantity", quantity.quantity_id),
        ("semantic", quantity.semantic_key),
        ("family", quantity.family),
    ):
        card_id = (scope, key, _equivalent_pricing_unit(quantity.unit))
        if card_id in cards:
            return card_id, cards[card_id]
    return None, None


def _date_fields(book: Mapping[str, Any]) -> dict[str, str | None]:
    issued = book.get("issued_on")
    expires = book.get("expires_on")
    if type(issued) is not str:
        raise ValueError("client must specify issued_on ISO date")
    try:
        start = date.fromisoformat(issued)
        end = date.fromisoformat(expires) if type(expires) is str else None
    except ValueError as exc:
        raise ValueError("invalid client quote calendar dates") from exc
    if expires is not None and end is None:
        raise ValueError("expires_on must be an ISO date or null")
    if end is not None and end < start:
        raise ValueError("quote expiry precedes issue date")
    return {"issued_on": issued, "expires_on": expires}


def _manual_allowances(book: Mapping[str, Any]) -> list[dict]:
    raw = book.get("manual_allowances", [])
    if type(raw) is not list:
        raise ValueError("manual allowances must be an array")
    allowances = []
    ids = set()
    for item in raw:
        if type(item) is not dict:
            raise ValueError("manual allowance must be a typed object")
        ident, label = item.get("id"), item.get("description")
        if (type(ident) is not str or not ident or ident != ident.strip()
            or type(label) is not str or not label.strip() or ident in ids):
            raise ValueError("manual allowances require unique canonical IDs and labels")
        ids.add(ident)
        allowances.append({
            "id": ident, "description": label.strip(),
            "amount": _money(_decimal(item.get("amount"), "manual allowance")),
            "authority": "CLIENT_MANUAL_NOT_SOURCE_VERIFIED",
        })
    return sorted(allowances, key=lambda row: row["id"])


def _cent_exact_cost_components(
    billable: Decimal, card: Mapping[str, Decimal],
) -> tuple[dict[str, str], Decimal]:
    """Allocate final cents once, keeping component totals equal to exact unit cost.

    Independently rounding four 0.5-cent subcomponents creates a 2-cent
    overstatement. Largest residual allocation gives each component no more
    than a cent above its truncated amount, with stable source-independent ties.
    Client rates, source quantity and physical units are never changed.
    """
    if not billable.is_finite() or billable < 0:
        raise ValueError("billable physical quantity must be finite and nonnegative")
    exact = {key: billable * card[key] for key in _COMPONENTS}
    total = sum(exact.values(), Decimal("0"))
    if not total.is_finite() or total < 0 or total > _MAX_MONEY:
        raise ValueError("client physical line cost exceeds safe financial bound")
    rounded_total = total.quantize(_CENT, rounding=ROUND_HALF_UP)
    allocated = {
        key: amount.quantize(_CENT, rounding=ROUND_DOWN)
        for key, amount in exact.items()
    }
    pennies = (rounded_total - sum(allocated.values(), Decimal("0"))) / _CENT
    if pennies != pennies.to_integral_value() or not 0 <= pennies <= len(_COMPONENTS):
        raise ValueError("cost component cent reconciliation is invalid")
    # Never produce a negative component to counteract half-up rounding.
    priority = sorted(_COMPONENTS, key=lambda key: (
        -(exact[key] - allocated[key]), _COMPONENTS.index(key),
    ))
    for key in priority[:int(pennies)]:
        allocated[key] += _CENT
    if sum(allocated.values(), Decimal("0")) != rounded_total:
        raise ValueError("source-linked customer costs fail cent reconciliation")
    return {key: _money(allocated[key]) for key in _COMPONENTS}, rounded_total


def build_verified_customer_quote(
    sealed_run: Mapping[str, Any], customer_rows: list[dict],
    rate_book: Mapping[str, Any],
) -> dict[str, Any]:
    """Price only independently verified, exactly signed quantities."""
    if type(sealed_run) is not dict or type(customer_rows) is not list or type(rate_book) is not dict:
        raise ValueError("signed run, customer rows and client rate book are required")
    sealed = sealed_source_closed_run_from_dict(sealed_run)
    verified = verify_sealed_customer_output(sealed, customer_rows)
    if (rate_book.get("schema_version") != "gpt3-client-rates-v1"
        or rate_book.get("project_id") != sealed.project_id):
        raise ValueError("client rate book project/schema does not match signed issuer")
    currency = _currency(rate_book.get("currency"))
    dates = _date_fields(rate_book)
    cards = _rates(rate_book)
    adjustments = rate_book.get("adjustments")
    if type(adjustments) is not dict:
        raise ValueError("explicit client project adjustments are required")
    percentages = {
        key: _percentage(adjustments, key)
        for key in ("overhead_pct", "contingency_pct", "discount_pct", "tax_pct")
    }
    if type(rate_book.get("include_manual_allowances")) is not bool:
        raise ValueError("client must explicitly choose manual allowance inclusion")
    include_manual = rate_book["include_manual_allowances"]
    allowances = _manual_allowances(rate_book)
    customer_ids: dict[str, dict] = {}
    manual_projection_count = 0
    for row in customer_rows:
        if type(row) is not dict:
            raise ValueError("customer projection must have object rows")
        ident = _customer_quantity_id(row)
        if not ident:
            manual_projection_count += 1
            continue
        if ident in customer_ids:
            raise ValueError("duplicate automated customer quantity")
        customer_ids[ident] = row

    signed = [q for q in sealed.quantities if not q.abstained]
    if (set(customer_ids) != set(verified.verified_quantity_ids)
        or len(signed) != verified.valid_quantity_count
        or set(customer_ids) != {q.quantity_id for q in signed}):
        raise ValueError("signed V1 commercial customer bijection is incomplete")

    items: list[dict[str, Any]] = []
    by_family: dict[tuple[str, str], dict] = {}
    by_page: dict[tuple[str, str], dict] = {}
    priced_subtotal = Decimal("0")
    cost_total = Decimal("0")
    hours_total = Decimal("0")
    unpriced: list[str] = []
    for q in sorted(signed, key=lambda row: row.quantity_id):
        if (type(q.value) not in (int, float) or
            not isinstance(q.quantity_id, str) or not q.quantity_id):
            raise ValueError("signed non-abstained quantity has malformed physical value")
        quantity = Decimal(str(q.value))
        if not quantity.is_finite() or quantity < 0:
            raise ValueError("signed quantity has invalid physical measurement")
        source = customer_ids[q.quantity_id]
        rate_id, card = _choose_rate(q, cards)
        line = {
            "quantity_id": q.quantity_id,
            "quantity_fingerprint": q.fingerprint,
            "family": q.family, "semantic_key": q.semantic_key,
            "physical_quantity": _number(quantity),
            "unit": q.unit,
            "element": source.get("element", ""),
            "location": source.get("location", ""),
            "source_sha256": q.source_sha256,
            "document_id": q.document_id,
            "source_page": q.source_page,
            "revision_id": q.revision_id,
            "object_identity_refs": list(q.object_identity_refs),
            "source_verification": "SIGNED_V1_CUSTOMER_BIJECTION_ONLY",
            "rate_scope": rate_id[0] if rate_id else None,
            "rate_key": rate_id[1] if rate_id else None,
        }
        if card is None:
            line.update({"pricing_status": "UNPRICED_CLIENT_RATE_MISSING",
                         "sell_amount": None, "cost_amount": None,
                         "labour_hours": None})
            unpriced.append(q.quantity_id)
        else:
            billable = quantity * (Decimal("1") + card["waste_pct"] / _HUNDRED)
            unit_cost = sum((card[component] for component in _COMPONENTS), Decimal("0"))
            components, cost = _cent_exact_cost_components(billable, card)
            sell = (cost * (Decimal("1") + card["markup_pct"] / _HUNDRED)).quantize(
                _CENT, rounding=ROUND_HALF_UP)
            hours = billable * card["labour_hours_per_unit"]
            line.update({
                "pricing_status": "PRICED_FROM_CLIENT_RATE",
                "billable_quantity_after_pricing_waste": _number(billable),
                "waste_pct": _number(card["waste_pct"]),
                "markup_pct": _number(card["markup_pct"]),
                "unit_cost": _money(unit_cost),
                "cost_components": components,
                "cost_amount": _money(cost), "sell_amount": _money(sell),
                "labour_hours": _number(hours),
            })
            priced_subtotal += sell
            cost_total += cost
            hours_total += hours
            for destination, key in ((by_family, (q.family, q.unit)),
                                     (by_page, (q.document_id, q.source_page))):
                bucket = destination.setdefault(key, {
                    "priced_line_count": 0, "cost": Decimal("0"),
                    "sell": Decimal("0"), "labour_hours": Decimal("0"),
                })
                bucket["priced_line_count"] += 1
                bucket["cost"] += cost
                bucket["sell"] += sell
                bucket["labour_hours"] += hours
        items.append(line)

    def rollup(data: dict, labels: tuple[str, str]) -> list[dict]:
        return [
            {
                labels[0]: key[0], labels[1]: key[1],
                "priced_line_count": row["priced_line_count"],
                "cost": _money(row["cost"]), "sell": _money(row["sell"]),
                "labour_hours": _number(row["labour_hours"]),
            }
            for key, row in sorted(data.items())
        ]

    manual_total = sum((Decimal(item["amount"]) for item in allowances), Decimal("0"))
    included_manual = manual_total if include_manual else Decimal("0")
    overhead = (priced_subtotal * percentages["overhead_pct"] / _HUNDRED).quantize(_CENT, rounding=ROUND_HALF_UP)
    contingency = (priced_subtotal * percentages["contingency_pct"] / _HUNDRED).quantize(_CENT, rounding=ROUND_HALF_UP)
    before_discount = priced_subtotal + overhead + contingency + included_manual
    discount = (before_discount * percentages["discount_pct"] / _HUNDRED).quantize(_CENT, rounding=ROUND_HALF_UP)
    before_tax = before_discount - discount
    tax = (before_tax * percentages["tax_pct"] / _HUNDRED).quantize(_CENT, rounding=ROUND_HALF_UP)
    total = before_tax + tax
    complete = not unpriced
    report: dict[str, Any] = {
        "schema_version": "gpt3-client-verified-quote-v1",
        "project_id": sealed.project_id,
        "signed_run_id": sealed.run_id,
        "signed_run_fingerprint": sealed.fingerprint,
        "currency": currency, **dates,
        "evidence_scope": "SIGNED_V1_CUSTOMER_ONLY_NOT_FROZEN_V2_SCORE",
        "publication_status": "CLIENT_PRICED_QUOTE" if complete else "INCOMPLETE_UNPRICED_QUANTITIES",
        "signed_quantity_count": len(signed),
        "unpriced_quantity_ids": unpriced,
        "unpriced_quantity_count": len(unpriced),
        "manual_projection_rows_outside_signed_bijection": manual_projection_count,
        "manual_allowances": allowances,
        "manual_allowances_included": include_manual,
        "items": items,
        "family_unit_rollup": rollup(by_family, ("family", "unit")),
        "source_page_rollup": rollup(by_page, ("document_id", "source_page")),
        "summary": {
            "priced_automated_subtotal": _money(priced_subtotal),
            "priced_automated_cost": _money(cost_total),
            "priced_labour_hours": _number(hours_total),
            "project_overhead": _money(overhead),
            "contingency": _money(contingency),
            "manual_allowance_total": _money(manual_total),
            "manual_allowance_included_amount": _money(included_manual),
            "discount": _money(discount),
            "tax": _money(tax),
            "tax_pct": _number(percentages["tax_pct"]),
            "overhead_pct": _number(percentages["overhead_pct"]),
            "contingency_pct": _number(percentages["contingency_pct"]),
            "discount_pct": _number(percentages["discount_pct"]),
            "grand_total": _money(total) if complete else None,
        },
        "official_four_project_accuracy": None,
    }
    digest = hashlib.sha256(json.dumps(
        report, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()
    report["quote_fingerprint"] = digest
    return report


def _csv_text(value: Any) -> Any:
    """Prevent signed labels/client names being evaluated as formulas by spreadsheets."""
    if type(value) is str and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def quote_csv(report: Mapping[str, Any]) -> str:
    """Import-ready customer CSV with signed lines, separate manual and totals."""
    columns = (
        "row_type", "project_id", "quantity_id", "family", "semantic_key",
        "physical_quantity", "unit", "element", "location",
        "document_id", "source_page", "source_sha256", "revision_id",
        "pricing_status", "rate_scope", "rate_key", "cost_amount",
        "sell_amount", "labour_hours", "currency", "quote_fingerprint",
    )
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()

    def emit(row: dict) -> None:
        safety = ("row_type", "project_id", "quantity_id", "family",
                  "semantic_key", "unit", "element", "location",
                  "document_id", "source_page", "source_sha256", "revision_id",
                  "pricing_status", "rate_scope", "rate_key", "currency",
                  "quote_fingerprint")
        writer.writerow({
            key: (_csv_text(row.get(key)) if key in safety else row.get(key))
            for key in columns
        })

    fixed = {
        "project_id": report["project_id"],
        "currency": report["currency"],
        "quote_fingerprint": report["quote_fingerprint"],
    }
    for line in report["items"]:
        emit({**fixed, **line, "row_type": "SIGNED_AUTOMATED_ITEM"})
    for item in report["manual_allowances"]:
        emit({
            **fixed, "row_type": "MANUAL_UNVERIFIED_ALLOWANCE",
            "quantity_id": item["id"], "element": item["description"],
            "pricing_status": item["authority"],
            "sell_amount": (
                item["amount"] if report["manual_allowances_included"] else None
            ),
        })
    fields = (
        ("PRICED_AUTOMATED_SUBTOTAL", "priced_automated_subtotal"),
        ("PROJECT_OVERHEAD", "project_overhead"),
        ("CONTINGENCY", "contingency"),
        ("INCLUDED_MANUAL_ALLOWANCES", "manual_allowance_included_amount"),
        ("DISCOUNT_DEDUCTION", "discount"),
        ("TAX", "tax"),
        ("GRAND_TOTAL_ONLY_IF_FULLY_PRICED", "grand_total"),
    )
    for label, field in fields:
        amount = report["summary"][field]
        if field == "discount" and amount is not None:
            amount = _money(-Decimal(amount))
        emit({**fixed, "row_type": "SUMMARY", "element": label,
              "sell_amount": amount, "pricing_status": report["publication_status"]})
    return handle.getvalue()

def compare_verified_quotes(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict:
    """Reveal price changes without presenting rate-only changes as measured gains."""
    for quote in (before, after):
        if quote.get("schema_version") != "gpt3-client-verified-quote-v1":
            raise ValueError("only canonical-format GPT3 quote reports can be compared")
        copy = dict(quote)
        claimed = copy.pop("quote_fingerprint", None)
        actual = hashlib.sha256(json.dumps(
            copy, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")).hexdigest()
        if type(claimed) is not str or claimed != actual:
            raise ValueError("quote contents differ from its canonical fingerprint")
    if before.get("project_id") != after.get("project_id"):
        raise ValueError("quote comparison cannot combine projects")
    older = {row["quantity_id"]: row for row in before["items"]}
    newer = {row["quantity_id"]: row for row in after["items"]}
    changed = []
    for qid in sorted(set(older) | set(newer)):
        old, fresh = older.get(qid), newer.get(qid)
        if old is None or fresh is None:
            change = "SIGNED_QUANTITY_ADDED_OR_REMOVED_REQUIRES_RESEAL"
        elif (old["quantity_fingerprint"], old["physical_quantity"], old["unit"]) != (
            fresh["quantity_fingerprint"], fresh["physical_quantity"], fresh["unit"]):
            change = "SOURCE_QUANTITY_CHANGED_REQUIRES_RESEAL"
        elif (old["sell_amount"], old["pricing_status"]) != (
            fresh["sell_amount"], fresh["pricing_status"]):
            change = "CLIENT_RATE_OR_PRICING_CHANGED"
        else:
            change = "UNCHANGED"
        if change != "UNCHANGED":
            changed.append({"quantity_id": qid, "change": change,
                            "old_sell_amount": old.get("sell_amount") if old else None,
                            "new_sell_amount": fresh.get("sell_amount") if fresh else None})
    if before.get("signed_run_fingerprint") != after.get("signed_run_fingerprint"):
        issuer_status = "DIFFERENT_SIGNED_ISSUER_REQUIRES_INDEPENDENT_AUTHORITY"
    else:
        issuer_status = "SAME_SIGNED_ISSUER"
    return {
        "schema_version": "gpt3-client-verified-quote-diff-v1",
        "project_id": before["project_id"],
        "old_quote_fingerprint": before.get("quote_fingerprint"),
        "new_quote_fingerprint": after.get("quote_fingerprint"),
        "issuer_comparison": issuer_status,
        "item_changes": changed,
        "old_grand_total": before["summary"].get("grand_total"),
        "new_grand_total": after["summary"].get("grand_total"),
        "official_four_project_accuracy": None,
    }


def _write_new(path: Path, body: str, inputs: tuple[Path, ...]) -> None:
    if (path.is_symlink() or path.exists()
        or path.resolve().is_relative_to(FROZEN_ROOT.resolve())
        or any(path.resolve() == original.resolve() for original in inputs)):
        raise FileExistsError("quote output must be a new path outside source or frozen files")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", dir=path.parent,
            prefix=".gpt3-quote-", suffix=".tmp", delete=False,
        ) as stream:
            tmp = Path(stream.name)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(tmp, path)
    finally:
        if tmp is not None:
            tmp.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--customers", type=Path, required=True)
    parser.add_argument("--client-rates", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)
    inputs = (args.sealed_run, args.customers, args.client_rates)
    if (args.output.exists() or args.output.is_symlink()
        or args.output.resolve().is_relative_to(FROZEN_ROOT.resolve())
        or any(args.output.resolve() == source.resolve() for source in inputs)):
        raise FileExistsError("quote output cannot overwrite source evidence")
    sealed = _read_json_without_duplicate_keys(args.sealed_run)
    customers = _read_json_without_duplicate_keys(args.customers)
    rates = _read_json_without_duplicate_keys(args.client_rates)
    quote = build_verified_customer_quote(sealed, customers, rates)
    body = (quote_csv(quote) if args.format == "csv"
            else json.dumps(quote, sort_keys=True, indent=2, allow_nan=False) + "\n")
    _write_new(args.output, body, inputs)
    print(json.dumps({
        "project_id": quote["project_id"],
        "quote_fingerprint": quote["quote_fingerprint"],
        "publication_status": quote["publication_status"],
        "signed_quantity_count": quote["signed_quantity_count"],
        "unpriced_quantity_count": quote["unpriced_quantity_count"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0 if quote["publication_status"] == "CLIENT_PRICED_QUOTE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
