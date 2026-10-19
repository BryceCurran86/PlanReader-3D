"""Client-supplied procurement demand, supplier bids and purchase-order drafts.

No purchase is transmitted. Material demand is NOT inferred from signed areas.
Never mint physical takeoff quantities or benchmark matches.
"""
from __future__ import annotations

import argparse
import csv
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import hashlib
import io
import json
from pathlib import Path
from typing import Any, Mapping

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from pb_customer_output_verification import _customer_quantity_id, verify_sealed_customer_output
from tools.gpt3_verified_customer_quote import (
    _currency, _csv_text, _decimal, _money, _number, _write_new,
    build_verified_customer_quote,
)
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def _hash(data: Mapping[str, Any], name: str) -> str:
    copy = dict(data)
    copy.pop(name, None)
    return hashlib.sha256(json.dumps(
        copy, sort_keys=True, ensure_ascii=True, separators=(",", ":"),
        allow_nan=False).encode("utf-8")).hexdigest()


def _date(value: Any, field: str) -> date:
    if type(value) is not str:
        raise ValueError(f"{field} must be a calendar date")
    try:
        d = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} is not a calendar date") from exc
    if d.isoformat() != value:
        raise ValueError(f"{field} requires canonical ISO date")
    return d


def _id(value: Any, field: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError(f"{field} requires a canonical nonempty identifier")
    return value


def _amount(value: Any, label: str) -> Decimal:
    result = _decimal(value, label)
    if result != result.quantize(CENT, rounding=ROUND_HALF_UP):
        raise ValueError(f"{label} must be exact currency cents")
    return result


def _positive(value: Any, label: str) -> Decimal:
    num = _decimal(value, label)
    if num <= 0:
        raise ValueError(f"{label} must be positive")
    return num


def _quote_source_lines(sealed_run: dict, customers: list[dict], quote: dict) -> dict:
    """Recheck quote issuer/customer identity before accepting client procurement."""
    if (type(quote) is not dict or quote.get("schema_version") != "gpt3-client-verified-quote-v1"
        or quote.get("quote_fingerprint") != _hash(quote, "quote_fingerprint")):
        raise ValueError("procurement quote was modified or is not canonical")
    sealed = sealed_source_closed_run_from_dict(sealed_run)
    verified = verify_sealed_customer_output(sealed, customers)
    if (
        quote.get("project_id") != sealed.project_id
        or quote.get("signed_run_id") != sealed.run_id
        or quote.get("signed_run_fingerprint") != sealed.fingerprint
        or quote.get("publication_status") != "CLIENT_PRICED_QUOTE"
        or quote.get("unpriced_quantity_count") != 0
    ):
        raise ValueError("procurement requires completely priced original signed quote")
    rows = quote.get("items")
    if type(rows) is not list or len(rows) != verified.valid_quantity_count:
        raise ValueError("procurement original signed quantity universe incomplete")
    by_signed = {q.quantity_id: q for q in sealed.quantities if not q.abstained}
    by_quote = {}
    by_customer = {_customer_quantity_id(row) for row in customers
                   if _customer_quantity_id(row)}
    if by_customer != set(by_signed) or len(by_customer) != verified.valid_quantity_count:
        raise ValueError("procurement customer source identity does not match sealed run")
    for row in rows:
        if type(row) is not dict:
            raise ValueError("malformed source-priced quote row")
        qid = _id(row.get("quantity_id"), "quote source ID")
        if qid in by_quote or qid not in by_signed:
            raise ValueError("duplicate or alien quote source identity")
        original = by_signed[qid]
        if (
            row.get("quantity_fingerprint") != original.fingerprint
            or row.get("physical_quantity") != _number(Decimal(str(original.value)))
            or row.get("unit") != original.unit
            or row.get("source_sha256") != original.source_sha256
            or row.get("revision_id") != original.revision_id
            or row.get("document_id") != original.document_id
            or row.get("source_page") != original.source_page
        ):
            raise ValueError("procurement source row differs from original signed source")
        if row.get("pricing_status") != "PRICED_FROM_CLIENT_RATE":
            raise ValueError("procurement requires explicit client quote pricing")
        if type(row.get("cost_components")) is not dict:
            raise ValueError("procurement requires priced original cost components")
        _amount(row["cost_components"].get("material"), "client material budget")
        by_quote[qid] = row
    if set(by_quote) != set(by_signed):
        raise ValueError("procurement missing signed source-linked quote item")
    return by_quote


def _suppliers(raw: Any, currency: str) -> dict[str, dict]:
    if type(raw) is not list:
        raise ValueError("supplier directory must be an array")
    suppliers = {}
    for row in raw:
        if type(row) is not dict:
            raise ValueError("supplier directory rows must be objects")
        sid = _id(row.get("supplier_id"), "supplier ID")
        if sid in suppliers:
            raise ValueError("duplicate supplier identity")
        name = _id(row.get("supplier_name"), "supplier name")
        if row.get("currency") != currency:
            raise ValueError("cannot compare supplier offers across currencies without FX authority")
        approved = row.get("eligible_for_award")
        if type(approved) is not bool:
            raise ValueError("supplier eligibility must be client confirmed")
        suppliers[sid] = {
            "supplier_id": sid, "supplier_name": name, "currency": currency,
            "eligible_for_award": approved,
            "payment_terms_days": row.get("payment_terms_days"),
        }
        terms = suppliers[sid]["payment_terms_days"]
        if type(terms) is not int or terms < 0 or terms > 365:
            raise ValueError("supplier payment terms must be an integer number of days")
    return suppliers


def build_procurement_plan(
    quote: dict, sealed_run: dict, customers: list[dict], book: dict,
    *, client_rate_book: dict | None = None,
    scope_preview: dict | None = None,
) -> dict:
    """Generate auditable RFQs, comparable supplier bids and approved PO drafts."""
    if scope_preview is not None and client_rate_book is None:
        raise ValueError("scope preview pricing requires original client rate book")
    if client_rate_book is not None:
        repriced = build_verified_customer_quote(
            sealed_run, customers, client_rate_book, scope_preview=scope_preview,
        )
        if quote != repriced:
            raise ValueError(
                "procurement source quote does not reproduce from original client rates"
            )
    qlines = _quote_source_lines(sealed_run, customers, quote)
    if type(book) is not dict or book.get("schema_version") != "gpt3-client-procurement-v1":
        raise ValueError("procurement book schema invalid")
    if book.get("quote_fingerprint") != quote["quote_fingerprint"] or (
        book.get("project_id") != quote["project_id"]
    ):
        raise ValueError("procurement input does not bind the exact priced source quote")
    currency = _currency(book.get("currency"))
    if currency != quote["currency"]:
        raise ValueError("procurement currency must match explicit client quote")
    as_of = _date(book.get("as_of"), "procurement offer evaluation date")
    issued_on = _date(quote.get("issued_on"), "source client quote issued_on")
    expires_on = quote.get("expires_on")
    if as_of < issued_on:
        raise ValueError("client quote is not yet issued at procurement approval date")
    if expires_on is not None and as_of > _date(
        expires_on, "source client quote expires_on"
    ):
        raise ValueError("client quote expired before procurement approval date")
    suppliers = _suppliers(book.get("suppliers"), currency)
    raw_demand = book.get("requisitions")
    if type(raw_demand) is not list:
        raise ValueError("procurement requisitions must be supplied by client")
    demand = {}
    for row in raw_demand:
        if type(row) is not dict:
            raise ValueError("procurement requisition must be an object")
        req = _id(row.get("requisition_id"), "requisition ID")
        if req in demand:
            raise ValueError("duplicate client requisition ID")
        description = _id(row.get("description"), "purchased item description")
        unit = _id(row.get("purchase_unit"), "procurement purchase unit")
        required = _positive(row.get("requested_purchase_quantity"), "client purchase quantity")
        _date(row.get("needed_by"), "procurement need-by date")
        source_ids = row.get("related_signed_quantity_ids")
        if (type(source_ids) is not list or not source_ids
            or any(type(qid) is not str or qid not in qlines for qid in source_ids)
            or len(source_ids) != len(set(source_ids))):
            raise ValueError("purchase requisition must reference unique existing signed quantity IDs")
        cap = row.get("maximum_approved_gross")
        demand[req] = {
            "requisition_id": req, "description": description,
            "purchase_unit": unit, "requested_purchase_quantity": _number(required),
            "related_signed_quantity_ids": sorted(source_ids),
            "needed_by": row["needed_by"],
            "delivery_location": _id(row.get("delivery_location"), "delivery location"),
            "maximum_approved_gross": _money(_amount(cap, "requisition gross cap"))
            if cap is not None else None,
            "authority": "CLIENT_PLANNED_MATERIAL_DEMAND_NOT_SOURCE_MEASUREMENT",
        }
    raw_offers = book.get("supplier_offers")
    if type(raw_offers) is not list:
        raise ValueError("supplier offers must be an explicit list")
    offers = {}
    per_req = {key: [] for key in demand}
    for bid in raw_offers:
        if type(bid) is not dict:
            raise ValueError("supplier offer must be an object")
        oid = _id(bid.get("offer_id"), "supplier offer ID")
        sid = bid.get("supplier_id")
        req = bid.get("requisition_id")
        if oid in offers or sid not in suppliers or req not in demand:
            raise ValueError("duplicate or unrelated supplier offer")
        if bid.get("purchase_unit") != demand[req]["purchase_unit"]:
            raise ValueError("supplier offer unit differs from client requested purchase unit")
        unit_cost = _amount(bid.get("unit_price_ex_tax"), "supplier unit price")
        freight = _amount(bid.get("freight_ex_tax"), "supplier freight")
        min_order = _decimal(bid.get("minimum_order_quantity", "0"), "supplier minimum order")
        pack = _positive(bid.get("pack_multiple"), "supplier pack multiple")
        days = bid.get("lead_days")
        if type(days) is not int or not 0 <= days <= 365:
            raise ValueError("supplier lead time must be integer days")
        tax = _decimal(bid.get("tax_pct"), "supplier offered tax percent", cap=HUNDRED)
        valid = _date(bid.get("valid_through"), "supplier offer expiry date")
        requested = Decimal(demand[req]["requested_purchase_quantity"])
        purchased = (max(requested, min_order) / pack).to_integral_value(
            rounding=ROUND_CEILING) * pack
        goods = (purchased * unit_cost).quantize(CENT, rounding=ROUND_HALF_UP)
        pre_tax = goods + freight
        tax_value = (pre_tax * tax / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
        gross = pre_tax + tax_value
        estimated_arrival = as_of + timedelta(days=days)
        eligible = (
            suppliers[sid]["eligible_for_award"] and valid >= as_of
            and estimated_arrival <= _date(demand[req]["needed_by"], "need-by date")
        )
        cap = demand[req]["maximum_approved_gross"]
        within_cap = cap is None or gross <= Decimal(cap)
        record = {
            "offer_id": oid, "requisition_id": req, "supplier_id": sid,
            "unit_price_ex_tax": _money(unit_cost), "freight_ex_tax": _money(freight),
            "purchase_quantity": _number(purchased),
            "pack_multiple": _number(pack),
            "minimum_order_quantity": _number(min_order),
            "requested_purchase_quantity": demand[req]["requested_purchase_quantity"],
            "overbuy_quantity": _number(purchased - requested),
            "tax_pct": _number(tax), "goods_ex_tax": _money(goods),
            "tax_amount": _money(tax_value), "gross_cost": _money(gross),
            "lead_days": days, "estimated_arrival": estimated_arrival.isoformat(),
            "valid_through": valid.isoformat(),
            "eligible_before_budget": eligible, "within_client_cap": within_cap,
            "awardable": eligible and within_cap,
            "bid_status": (
                "ELIGIBLE" if eligible and within_cap
                else "INELIGIBLE_SUPPLIER_OR_EXPIRED_OR_LATE"
                if not eligible else "EXCEEDS_CLIENT_BUDGET"
            ),
        }
        offers[oid] = record
        per_req[req].append(oid)
    rankings = []
    for req in sorted(demand):
        ids = sorted(per_req[req], key=lambda key: (
            not offers[key]["awardable"], Decimal(offers[key]["gross_cost"]),
            offers[key]["lead_days"], key))
        rankings.append({
            "requisition_id": req, "ranked_offer_ids": ids,
            "lowest_eligible_offer_id": next(
                (oid for oid in ids if offers[oid]["awardable"]), None),
            "comparison_does_not_create_approval": True,
        })
    raw_awards = book.get("client_awards")
    if type(raw_awards) is not list:
        raise ValueError("client awards must be an explicit list, even if empty")
    awards = {}
    for row in raw_awards:
        if type(row) is not dict:
            raise ValueError("client award must be an object")
        rid = _id(row.get("requisition_id"), "award requisition")
        bid = _id(row.get("offer_id"), "selected supplier bid")
        if rid in awards or rid not in demand or bid not in offers or (
            offers[bid]["requisition_id"] != rid
        ):
            raise ValueError("client award does not match one source requisition and offer")
        if not offers[bid]["awardable"]:
            raise ValueError("client award cannot override invalid supplier offer without new explicit quote")
        actor = _id(row.get("approved_by"), "client procurement approver")
        ref = _id(row.get("approval_reference"), "client approval reference")
        approved_on = _date(row.get("approved_on"), "client award date")
        if approved_on != as_of:
            raise ValueError("supplier bid must be reevaluated at exact approval date")
        awards[rid] = {
            **offers[bid], "approval_reference": ref, "approved_by": actor,
            "approved_on": approved_on.isoformat(),
            "purchase_order_status": "DRAFT_NOT_TRANSMITTED",
        }
    orders: dict[str, dict] = {}
    for rid in sorted(awards):
        row = awards[rid]
        sid = row["supplier_id"]
        target = orders.setdefault(sid, {
            "supplier_id": sid, "supplier_name": suppliers[sid]["supplier_name"],
            "currency": currency, "lines": [], "gross_total": Decimal("0"),
            "status": "DRAFT_NOT_TRANSMITTED",
        })
        target["lines"].append({
            **row, "description": demand[rid]["description"],
            "purchase_unit": demand[rid]["purchase_unit"],
            "delivery_location": demand[rid]["delivery_location"],
            "related_signed_quantity_ids": demand[rid]["related_signed_quantity_ids"],
            "purchase_order_measurement_authority": "CLIENT_PLANNED_PURCHASE_NOT_SIGNED_AREA",
        })
        target["gross_total"] += Decimal(row["gross_cost"])
    purchase_orders = []
    for sid, data in sorted(orders.items()):
        data["gross_total"] = _money(data["gross_total"])
        data["po_draft_id"] = "draft-po-" + hashlib.sha256(
            (quote["quote_fingerprint"] + ":" + sid + ":" +
             ":".join(row["offer_id"] for row in data["lines"])).encode("utf-8")
        ).hexdigest()[:20]
        purchase_orders.append(data)
    all_caps = sum((Decimal(row["maximum_approved_gross"]) for row in demand.values()
                    if row["maximum_approved_gross"] is not None), Decimal("0"))
    total_commit = sum((Decimal(po["gross_total"]) for po in purchase_orders), Decimal("0"))
    source_material_cost = sum(
        (Decimal(row["cost_components"]["material"]) for row in qlines.values()),
        Decimal("0"))
    result = {
        "schema_version": "gpt3-client-procurement-awards-v1",
        "project_id": quote["project_id"],
        "currency": currency, "as_of": as_of.isoformat(),
        "quote_fingerprint": quote["quote_fingerprint"],
        "signed_run_fingerprint": quote["signed_run_fingerprint"],
        "supplier_directory": [suppliers[key] for key in sorted(suppliers)],
        "requisitions": [demand[key] for key in sorted(demand)],
        "offers": [offers[key] for key in sorted(offers)],
        "supplier_bid_comparison": rankings,
        "purchase_order_drafts": purchase_orders,
        "unawarded_requisition_ids": sorted(set(demand) - set(awards)),
        "commercial_summary": {
            "approved_purchase_order_draft_gross": _money(total_commit),
            "client_requisition_cap_total_for_capped_lines_only": _money(all_caps),
            "original_quote_client_material_cost_excluding_quote_tax": _money(source_material_cost),
            "material_quote_to_supplier_commitments_not_like_for_like": True,
        },
        "order_transmitted": False,
        "goods_received": False,
        "material_requirement_authenticated_from_drawings": False,
        "official_four_project_accuracy": None,
    }
    if client_rate_book is not None:
        result["client_rate_source_replay_status"] = (
            "EXACT_V1_CUSTOMER_RATE_REPLAY_NOT_SOURCE_PDF_AUTHORITY"
        )
        result["original_source_pdf_reverified"] = False
    result["procurement_fingerprint"] = _hash(result, "procurement_fingerprint")
    return result


def rfq_csv(plan: Mapping[str, Any]) -> str:
    """Private supplier RFQ demand list: no original drawing or gold benchmark."""
    keys = ("requisition_id", "description", "purchase_unit",
            "requested_purchase_quantity", "needed_by", "delivery_location",
            "related_signed_quantity_ids", "currency", "authority")
    result = io.StringIO(newline="")
    writer = csv.DictWriter(result, fieldnames=keys)
    writer.writeheader()
    for row in plan["requisitions"]:
        values = {**row, "currency": plan["currency"],
                  "related_signed_quantity_ids": ";".join(row["related_signed_quantity_ids"])}
        writer.writerow({key: _csv_text(values.get(key))
                         if key not in ("requested_purchase_quantity",)
                         else values.get(key) for key in keys})
    return result.getvalue()


def draft_po_csv(plan: Mapping[str, Any]) -> str:
    """Unsent supplier-order draft with explicit client approval references."""
    keys = ("po_draft_id", "supplier_id", "requisition_id", "offer_id",
            "description", "purchase_unit", "purchase_quantity",
            "unit_price_ex_tax", "freight_ex_tax", "tax_amount", "gross_cost",
            "estimated_arrival", "delivery_location", "approval_reference",
            "purchase_order_status", "currency")
    result = io.StringIO(newline="")
    writer = csv.DictWriter(result, fieldnames=keys)
    writer.writeheader()
    for order in plan["purchase_order_drafts"]:
        for line in order["lines"]:
            values = {**line, "po_draft_id": order["po_draft_id"],
                      "currency": plan["currency"]}
            writer.writerow({key: _csv_text(values.get(key))
                             if key not in ("purchase_quantity", "unit_price_ex_tax",
                                            "freight_ex_tax", "tax_amount", "gross_cost")
                             else values.get(key) for key in keys})
    return result.getvalue()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("quote", "sealed_run", "customers", "procurement_book"):
        p.add_argument("--" + name.replace("_", "-"), type=Path, required=True)
    p.add_argument("--client-rates", type=Path)
    p.add_argument("--scope-preview", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--format", choices=("json", "rfq-csv", "po-csv"), default="json")
    args = p.parse_args(argv)
    if args.scope_preview is not None and args.client_rates is None:
        p.error("--scope-preview requires --client-rates")
    paths = tuple(getattr(args, name) for name in (
        "quote", "sealed_run", "customers", "procurement_book"))
    if args.client_rates is not None:
        paths += (args.client_rates,)
    if args.scope_preview is not None:
        paths += (args.scope_preview,)
    quote, sealed, customers, book = (
        _read_json_without_duplicate_keys(path) for path in paths[:4]
    )
    rates = (
        _read_json_without_duplicate_keys(args.client_rates)
        if args.client_rates is not None else None
    )
    scope = (
        _read_json_without_duplicate_keys(args.scope_preview)
        if args.scope_preview is not None else None
    )
    plan = build_procurement_plan(
        quote, sealed, customers, book, client_rate_book=rates,
        scope_preview=scope,
    )
    data = (rfq_csv(plan) if args.format == "rfq-csv"
            else draft_po_csv(plan) if args.format == "po-csv"
            else json.dumps(plan, sort_keys=True, indent=2, allow_nan=False) + "\n")
    _write_new(args.output, data, paths)
    print(json.dumps({"draft_order_count": len(plan["purchase_order_drafts"]),
                      "unawarded_requisition_count": len(plan["unawarded_requisition_ids"]),
                      "official_four_project_accuracy": None}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
