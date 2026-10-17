"""Source-linked contract schedules, customer scope and quote revisions.

Produces client-side documentation from existing, independently verified V1
quantities. It does not authenticate client signatures, create original
measurements, call frozen V2 scoring, or certify progress/completion.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from pb_source_closed_run_export import sealed_source_closed_run_from_dict
from pb_customer_output_verification import verify_sealed_customer_output
from tools.gpt3_verified_customer_quote import (
    _currency, _decimal, _money, _number, _write_new, compare_verified_quotes,
)
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys

CENT = Decimal("0.01")
HUNDRED = Decimal("100")


def digest(value: Mapping[str, Any], field: str) -> str:
    data = dict(value)
    data.pop(field, None)
    return hashlib.sha256(json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _date(value: Any, label: str) -> date:
    if type(value) is not str:
        raise ValueError(f"{label} must be an ISO calendar date")
    try:
        result = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO calendar date") from exc
    if result.isoformat() != value:
        raise ValueError(f"{label} requires canonical YYYY-MM-DD")
    return result


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise ValueError(f"{label} must be a canonical nonempty text identity")
    return value


def _texts(value: Any, label: str) -> list[str]:
    if type(value) is not list:
        raise ValueError(f"{label} must be an explicit array")
    return [_identifier(text, label) for text in value]


def verified_quote(
    quote: Mapping[str, Any],
    sealed_run: Mapping[str, Any],
    customer_rows: list[dict],
) -> tuple[Any, list[dict]]:
    """Rebind every quoted physical row to the actual signed V1 envelope."""
    if type(quote) is not dict or quote.get("schema_version") != "gpt3-client-verified-quote-v1":
        raise ValueError("contract requires the GPT3 source-verified quote format")
    if quote.get("quote_fingerprint") != digest(quote, "quote_fingerprint"):
        raise ValueError("quote body changed after its reported fingerprint")
    signed = sealed_source_closed_run_from_dict(sealed_run)
    verified = verify_sealed_customer_output(signed, customer_rows)
    if (
        quote.get("project_id") != signed.project_id
        or quote.get("signed_run_id") != signed.run_id
        or quote.get("signed_run_fingerprint") != signed.fingerprint
        or quote.get("publication_status") != "CLIENT_PRICED_QUOTE"
        or quote.get("unpriced_quantity_count") != 0
        or quote.get("unpriced_quantity_ids") != []
        or _currency(quote.get("currency")) != quote["currency"]
    ):
        raise ValueError("contract quote project, issuer or rate completeness mismatch")
    items = quote.get("items")
    if type(items) is not list:
        raise ValueError("quote source item list is incomplete")
    if len(items) != len({q.quantity_id for q in signed.quantities if not q.abstained}):
        raise ValueError("quote signed physical quantity count mismatch")
    by_id = {}
    for row in items:
        if type(row) is not dict:
            raise ValueError("quote item must be an object")
        key = _identifier(row.get("quantity_id"), "signed quantity ID")
        if key in by_id:
            raise ValueError("quote reuses a signed physical quantity")
        by_id[key] = row
    issued = _date(quote.get("issued_on"), "quote issue date")
    expiry = quote.get("expires_on")
    if expiry is not None and _date(expiry, "quote expiry") < issued:
        raise ValueError("quote expiry precedes quote issue")
    source_quantities = {
        q.quantity_id: q for q in signed.quantities if not q.abstained
    }
    if (
        set(by_id) != set(source_quantities)
        or set(by_id) != set(verified.verified_quantity_ids)
        or quote.get("signed_quantity_count") != len(by_id)
    ):
        raise ValueError("quote source/customer bijection changed")
    calculated = Decimal("0")
    for qid, row in by_id.items():
        q = source_quantities[qid]
        if (
            row.get("quantity_fingerprint") != q.fingerprint
            or row.get("family") != q.family
            or row.get("semantic_key") != q.semantic_key
            or row.get("unit") != q.unit
            or row.get("source_sha256") != q.source_sha256
            or row.get("document_id") != q.document_id
            or row.get("source_page") != q.source_page
            or row.get("revision_id") != q.revision_id
            or row.get("object_identity_refs") != list(q.object_identity_refs)
            or row.get("pricing_status") != "PRICED_FROM_CLIENT_RATE"
            or row.get("physical_quantity") != _number(Decimal(str(q.value)))
        ):
            raise ValueError("quote physical source identity differs from signed V1")
        amount = _decimal(row.get("sell_amount"), "quote source line price")
        if _money(amount) != row.get("sell_amount"):
            raise ValueError("quoted currency amount is not canonical to cents")
        calculated += amount
    summary = quote.get("summary")
    if type(summary) is not dict or _money(calculated) != summary.get("priced_automated_subtotal"):
        raise ValueError("quote item prices disagree with priced subtotal")
    overhead = _decimal(summary.get("project_overhead"), "overhead")
    contingency = _decimal(summary.get("contingency"), "contingency")
    manual = _decimal(summary.get("manual_allowance_included_amount"), "manual allowance")
    discount = _decimal(summary.get("discount"), "discount")
    tax = _decimal(summary.get("tax"), "tax")
    subtotal = calculated + overhead + contingency + manual
    if discount > subtotal:
        raise ValueError("quote discounts exceed positive subtotal")
    if _money(subtotal - discount + tax) != summary.get("grand_total"):
        raise ValueError("quote grand total differs from priced components")
    return signed, [by_id[qid] for qid in sorted(by_id)]


def _milestones(raw: Any, total: Decimal) -> list[dict]:
    if type(raw) is not list or not raw:
        raise ValueError("contract requires an explicit dated milestone programme")
    result = []
    names = set()
    shares = Decimal("0")
    remaining = total
    for index, row in enumerate(raw):
        if type(row) is not dict:
            raise ValueError("milestone must be an object")
        name = _identifier(row.get("id"), "milestone ID")
        description = _identifier(row.get("description"), "milestone description")
        if name in names:
            raise ValueError("duplicate contract milestone ID")
        names.add(name)
        _date(row.get("due_on"), "milestone date")
        share = _decimal(row.get("share_pct"), "milestone percentage", cap=HUNDRED)
        shares += share
        allocated = (
            remaining if index == len(raw) - 1 else
            (total * share / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
        )
        remaining -= allocated
        result.append({
            "id": name, "description": description,
            "due_on": row["due_on"], "share_pct": _number(share),
            "scheduled_value": _money(allocated),
            "status": "PLANNED_NOT_CERTIFIED",
        })
    if shares != HUNDRED:
        raise ValueError("contract milestone shares must sum to precisely 100 percent")
    return result


def _acceptance(raw: Any, quote: Mapping[str, Any]) -> dict:
    if type(raw) is not dict:
        raise ValueError("contract requires explicit client acceptance state")
    status = raw.get("status")
    if status not in ("DRAFT", "SUBMITTED", "ACCEPTED", "REJECTED"):
        raise ValueError("contract acceptance state is unsupported")
    actor = raw.get("actor")
    reference = raw.get("reference")
    on = raw.get("recorded_on")
    if status in ("ACCEPTED", "REJECTED"):
        _identifier(actor, "client acceptance actor")
        _identifier(reference, "client approval reference")
        recorded = _date(on, "client approval date")
        if recorded < _date(quote["issued_on"], "quote issue date"):
            raise ValueError("quote decision occurred before issue")
        expires = quote.get("expires_on")
        if status == "ACCEPTED" and expires is not None and recorded > _date(expires, "quote expiry"):
            raise ValueError("expired quote requires fresh issue rather than inferred acceptance")
    else:
        if any(raw.get(key) is not None for key in ("actor", "reference", "recorded_on")):
            raise ValueError("pending contract cannot include an asserted approval")
    if raw.get("quote_fingerprint") != quote["quote_fingerprint"]:
        raise ValueError("client decision must name the exact quoted revision")
    return {
        "status": status, "actor": actor, "reference": reference,
        "recorded_on": on, "attestation": "CLIENT_RECORDED_NOT_CRYPTOGRAPHIC_SIGNATURE",
        "quote_fingerprint": quote["quote_fingerprint"],
    }


def build_contract_schedule(
    quote: dict, sealed_run: dict, customers: list[dict], policy: dict,
) -> dict:
    """Generate a contract-ready BoQ; no variation or progress auto-certification."""
    _, source_items = verified_quote(quote, sealed_run, customers)
    if type(policy) is not dict or policy.get("schema_version") != "gpt3-contract-policy-v1":
        raise ValueError("explicit client contract policy is required")
    if policy.get("project_id") != quote["project_id"]:
        raise ValueError("contract project differs from signed source")
    contract_id = _identifier(policy.get("contract_id"), "client contract ID")
    client_ref = _identifier(policy.get("client_reference"), "client reference")
    days = policy.get("payment_terms_days")
    if type(days) is not int or not 0 <= days <= 365:
        raise ValueError("client payment terms must be explicit nonnegative days")
    retention_pct = _decimal(policy.get("retention_pct"), "retention percent", cap=HUNDRED)
    inclusion = _texts(policy.get("inclusions"), "scope inclusions")
    exclusion = _texts(policy.get("exclusions"), "scope exclusions")
    assignments = policy.get("package_assignments")
    descriptions = policy.get("package_descriptions")
    if type(assignments) is not dict or type(descriptions) is not dict:
        raise ValueError("source item packages and descriptions are required")
    ids = {row["quantity_id"] for row in source_items}
    if set(assignments) != ids:
        raise ValueError("every signed physical quantity must have one explicit package")
    if not descriptions or any(
        type(key) is not str or not key or type(val) is not str or not val.strip()
        for key, val in descriptions.items()
    ):
        raise ValueError("each work package must be named and described")
    if set(assignments.values()) != set(descriptions):
        raise ValueError("package descriptions must match assigned source work")
    packages = {
        key: {"package_id": key, "description": descriptions[key],
              "source_quantity_ids": [], "priced_line_total": Decimal("0"),
              "unit_quantities": {}}
        for key in descriptions
    }
    for row in source_items:
        group = packages[assignments[row["quantity_id"]]]
        group["source_quantity_ids"].append(row["quantity_id"])
        group["priced_line_total"] += Decimal(row["sell_amount"])
        unit = row["unit"]
        group["unit_quantities"][unit] = (
            group["unit_quantities"].get(unit, Decimal("0"))
            + Decimal(row["physical_quantity"])
        )
    groups = [
        {"package_id": key, "description": row["description"],
         "source_quantity_ids": sorted(row["source_quantity_ids"]),
         "priced_line_total": _money(row["priced_line_total"]),
         "physical_quantities_by_unit": {
             unit: _number(value) for unit, value in sorted(row["unit_quantities"].items())
         }}
        for key, row in sorted(packages.items())
    ]
    total = _decimal(quote["summary"]["grand_total"], "contract price")
    milestones = _milestones(policy.get("milestones"), total)
    acceptance = _acceptance(policy.get("acceptance"), quote)
    data = {
        "schema_version": "gpt3-source-linked-contract-v1",
        "contract_id": contract_id,
        "client_reference": client_ref,
        "project_id": quote["project_id"],
        "signed_run_id": quote["signed_run_id"],
        "signed_run_fingerprint": quote["signed_run_fingerprint"],
        "quote_fingerprint": quote["quote_fingerprint"],
        "currency": quote["currency"],
        "quote_issued_on": quote["issued_on"],
        "quote_expires_on": quote["expires_on"],
        "contract_value_including_quote_tax": _money(total),
        "accepted_contract_value": _money(total) if acceptance["status"] == "ACCEPTED" else None,
        "retention_pct": _number(retention_pct),
        "payment_terms_days": days,
        "acceptance": acceptance,
        "inclusions": inclusion, "exclusions": exclusion,
        "packages": groups, "milestones": milestones,
        "source_item_count": len(source_items),
        "evidence_scope": "SIGNED_V1_QUANTITIES_CLIENT_PRICING_NOT_V2_SCORE",
        "original_pdf_reverified_in_this_delivery": False,
        "certified_progress": False,
        "official_four_project_accuracy": None,
    }
    data["contract_fingerprint"] = digest(data, "contract_fingerprint")
    return data


def verify_contract(contract: Mapping[str, Any], quote: Mapping[str, Any]) -> None:
    if (
        type(contract) is not dict
        or contract.get("schema_version") != "gpt3-source-linked-contract-v1"
        or contract.get("contract_fingerprint") != digest(contract, "contract_fingerprint")
        or contract.get("quote_fingerprint") != quote.get("quote_fingerprint")
        or contract.get("signed_run_fingerprint") != quote.get("signed_run_fingerprint")
        or contract.get("project_id") != quote.get("project_id")
        or contract.get("currency") != quote.get("currency")
    ):
        raise ValueError("contract hash or signed quote identity mismatch")


def build_quote_revision_history(
    revisions: list[dict], sealed_run: dict, customers: list[dict],
) -> dict:
    if type(revisions) is not list or not revisions:
        raise ValueError("quote revision history needs at least one revision")
    history = []
    seen_versions = set()
    older = None
    last_date = None
    for revision in revisions:
        if type(revision) is not dict or set(revision) != {"version", "effective_on", "quote"}:
            raise ValueError("revision requires version, date and signed quote")
        version = revision["version"]
        if type(version) is not int or version < 1 or version in seen_versions:
            raise ValueError("versions must be positive, unique integers")
        if older is not None and version <= history[-1]["version"]:
            raise ValueError("quote revisions must increase monotonically")
        seen_versions.add(version)
        effective = _date(revision["effective_on"], "quote revision effective date")
        if last_date is not None and effective < last_date:
            raise ValueError("quote revision dates cannot move backwards")
        quote = revision["quote"]
        verified_quote(quote, sealed_run, customers)
        if older is not None:
            change = compare_verified_quotes(older, quote)
            if change["issuer_comparison"] != "SAME_SIGNED_ISSUER":
                raise ValueError("different source issuer requires new physical contract")
        else:
            change = None
        total = quote["summary"]["grand_total"]
        history.append({
            "version": version, "effective_on": effective.isoformat(),
            "quote_fingerprint": quote["quote_fingerprint"],
            "signed_run_fingerprint": quote["signed_run_fingerprint"],
            "priced_total": total,
            "change_since_previous": (
                _money(Decimal(total) - Decimal(older["summary"]["grand_total"]))
                if older is not None else None
            ),
            "changed_line_items": change["item_changes"] if change is not None else [],
            "customer_acceptance_required": True,
        })
        older, last_date = quote, effective
    result = {
        "schema_version": "gpt3-source-linked-quote-revisions-v1",
        "project_id": older["project_id"],
        "signed_run_fingerprint": older["signed_run_fingerprint"],
        "currency": older["currency"], "revisions": history,
        "official_four_project_accuracy": None,
    }
    result["revision_history_fingerprint"] = digest(result, "revision_history_fingerprint")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", required=True, type=Path)
    parser.add_argument("--customers", required=True, type=Path)
    parser.add_argument("--quote", type=Path)
    parser.add_argument("--policy", type=Path)
    parser.add_argument("--revisions", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    if bool(args.revisions) == bool(args.quote and args.policy):
        raise ValueError("choose --revisions or both --quote and --policy")
    sources = [args.sealed_run, args.customers]
    source = _read_json_without_duplicate_keys(args.sealed_run)
    customers = _read_json_without_duplicate_keys(args.customers)
    if args.revisions:
        sources.append(args.revisions)
        result = build_quote_revision_history(
            _read_json_without_duplicate_keys(args.revisions).get("revisions"),
            source, customers,
        )
    else:
        sources.extend([args.quote, args.policy])
        result = build_contract_schedule(
            _read_json_without_duplicate_keys(args.quote), source,
            customers, _read_json_without_duplicate_keys(args.policy),
        )
    _write_new(
        args.output, json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + "\n",
        tuple(sources),
    )
    print(json.dumps({
        "project_id": result["project_id"],
        "schema_version": result["schema_version"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
