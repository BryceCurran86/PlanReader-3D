"""Client-authored variation register for an existing source-linked contract.

A manual change order is not a drawing-derived quantity, original signed V1
takeoff, an authenticated client signature, or frozen V2 benchmark evidence.
"""
from __future__ import annotations

import argparse
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import csv
import io
import json
from pathlib import Path
from typing import Any, Mapping

from tools.gpt3_verified_contract_delivery import (
    HUNDRED, _date, _identifier, digest, verify_contract,
)
from tools.gpt3_verified_customer_quote import _csv_text, _decimal, _money, _write_new
from tools.report_gpt3_four_project_evidence import _read_json_without_duplicate_keys

CENT = Decimal("0.01")
_ALLOWED = frozenset(("ADDED_SCOPE", "REMOVED_SCOPE", "CLIENT_OPTION"))
_STATUSES = frozenset(("PROPOSED", "APPROVED", "REJECTED", "WITHDRAWN"))
_MAX = Decimal("1000000000000")


def _amount(value: Any, name: str) -> Decimal:
    if type(value) not in (str, int) or (type(value) is str and not value.strip()):
        raise ValueError(f"{name} requires exact signed decimal text or integer")
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError(f"{name} is not decimal") from exc
    if not amount.is_finite() or abs(amount) > _MAX:
        raise ValueError(f"{name} is outside safe exact-money range")
    return amount


def build_change_register(
    contract: Mapping[str, Any], quote: Mapping[str, Any],
    register: Mapping[str, Any],
) -> dict:
    """Replay immutable client-entered proposals and recorded decisions."""
    verify_contract(contract, quote)
    if type(register) is not dict or register.get("schema_version") != "gpt3-client-variations-v1":
        raise ValueError("variation event book schema invalid")
    if (register.get("contract_id") != contract.get("contract_id")
        or register.get("contract_fingerprint") != contract.get("contract_fingerprint")
        or register.get("currency") != contract.get("currency")):
        raise ValueError("variation book must name exact contract issuer and currency")
    raw = register.get("events")
    if type(raw) is not list:
        raise ValueError("variation events must be an explicit list")
    quoted_ids = set()
    for package in contract["packages"]:
        quoted_ids.update(package["source_quantity_ids"])
    states: dict[str, dict] = {}
    receipts = []
    previous_hash = contract["contract_fingerprint"]
    last_date = None
    for index, entry in enumerate(raw):
        if type(entry) is not dict:
            raise ValueError("variation event must be an object")
        event_type = entry.get("event")
        event_id = _identifier(entry.get("variation_id"), "variation ID")
        when = _date(entry.get("recorded_on"), "variation event date")
        if last_date is not None and when < last_date:
            raise ValueError("variation event history cannot move backwards")
        last_date = when
        if event_type == "PROPOSE":
            if event_id in states:
                raise ValueError("duplicate variation ID or proposal reissue")
            scope = entry.get("scope_type")
            if scope not in _ALLOWED:
                raise ValueError("variation requires explicit scope class")
            description = _identifier(entry.get("description"), "variation description")
            raw_refs = entry.get("related_signed_quantity_ids", [])
            if (type(raw_refs) is not list
                or any(type(ref) is not str or not ref or ref != ref.strip()
                       for ref in raw_refs)
                or len(set(raw_refs)) != len(raw_refs)
                or not set(raw_refs).issubset(quoted_ids)):
                raise ValueError("variation must reference only real signed physical IDs")
            amount = _amount(entry.get("net_ex_tax"), "variation net cost")
            if amount == 0 or (scope == "REMOVED_SCOPE" and amount > 0) or (
                scope in ("ADDED_SCOPE", "CLIENT_OPTION") and amount < 0
            ):
                raise ValueError("variation sign must agree with its manual scope class")
            rate = _decimal(entry.get("tax_pct"), "variation tax percentage", cap=HUNDRED)
            pre_tax = amount.quantize(CENT, rounding=ROUND_HALF_UP)
            if pre_tax != amount:
                raise ValueError("variation net value must be exact currency cents")
            tax = (pre_tax * rate / HUNDRED).quantize(CENT, rounding=ROUND_HALF_UP)
            states[event_id] = {
                "variation_id": event_id,
                "description": description,
                "scope_type": scope,
                "related_signed_quantity_ids": sorted(raw_refs),
                "original_proposal_on": when.isoformat(),
                "net_ex_tax": _money(pre_tax),
                "tax_pct": str(rate.normalize()),
                "tax": _money(tax),
                "gross_delta": _money(pre_tax + tax),
                "status": "PROPOSED",
                "decision_actor": None, "decision_reference": None,
                "decision_on": None,
                "authority": "CLIENT_MANUAL_SCOPE_NOT_PHYSICAL_QUANTITY",
            }
        elif event_type in ("APPROVE", "REJECT", "WITHDRAW"):
            if event_id not in states or states[event_id]["status"] != "PROPOSED":
                raise ValueError("variation must be proposed and undecided before decision")
            state = states[event_id]
            actor = _identifier(entry.get("actor"), "variation decision actor")
            reference = _identifier(entry.get("reference"), "variation decision reference")
            if event_type == "APPROVE" and contract["acceptance"]["status"] != "ACCEPTED":
                raise ValueError("variation cannot be approved on unsigned client contract")
            state["status"] = {"APPROVE": "APPROVED", "REJECT": "REJECTED",
                               "WITHDRAW": "WITHDRAWN"}[event_type]
            state["decision_actor"] = actor
            state["decision_reference"] = reference
            state["decision_on"] = when.isoformat()
        else:
            raise ValueError("unknown variation event transition")
        receipt = {
            "index": index, "variation_id": event_id, "event": event_type,
            "recorded_on": when.isoformat(), "previous_hash": previous_hash,
            "payload": entry,
        }
        receipt["event_hash"] = digest(receipt, "event_hash")
        previous_hash = receipt["event_hash"]
        receipts.append(receipt)
    approved = sum((Decimal(item["gross_delta"]) for item in states.values()
                    if item["status"] == "APPROVED"), Decimal("0"))
    pending = sum((Decimal(item["gross_delta"]) for item in states.values()
                   if item["status"] == "PROPOSED"), Decimal("0"))
    base = _decimal(contract["contract_value_including_quote_tax"], "contract price")
    if base + approved < 0:
        raise ValueError("approved removals cannot turn contract price negative")
    result = {
        "schema_version": "gpt3-client-variation-register-v1",
        "contract_id": contract["contract_id"],
        "contract_fingerprint": contract["contract_fingerprint"],
        "signed_run_fingerprint": contract["signed_run_fingerprint"],
        "quote_fingerprint": contract["quote_fingerprint"],
        "currency": contract["currency"],
        "variations": [states[key] for key in sorted(states)],
        "event_chain": receipts,
        "approved_variation_delta": _money(approved),
        "pending_variation_delta_not_committed": _money(pending),
        "base_quote_gross": _money(base),
        "committed_client_contract_gross": _money(base + approved),
        "client_approval_is_external_attestation_not_cryptographic_signature": True,
        "physical_quantity_created": False,
        "certified_progress": False,
        "official_four_project_accuracy": None,
    }
    result["variation_register_fingerprint"] = digest(
        result, "variation_register_fingerprint")
    return result


def verify_variations(register: Mapping[str, Any], contract: Mapping[str, Any]) -> None:
    if (type(register) is not dict
        or register.get("schema_version") != "gpt3-client-variation-register-v1"
        or register.get("variation_register_fingerprint") != digest(
            register, "variation_register_fingerprint"
        )
        or register.get("contract_fingerprint") != contract.get("contract_fingerprint")
        or register.get("signed_run_fingerprint") != contract.get("signed_run_fingerprint")
        or register.get("quote_fingerprint") != contract.get("quote_fingerprint")):
        raise ValueError("variation register fingerprint or contract identity mismatch")


def change_order_csv(report: Mapping[str, Any]) -> str:
    """Human-importable manual change register, never certified source areas."""
    names = ("variation_id", "description", "scope_type", "status",
             "net_ex_tax", "tax_pct", "tax", "gross_delta",
             "decision_actor", "decision_reference", "decision_on",
             "related_signed_quantity_ids", "authority")
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=names)
    writer.writeheader()
    for item in report["variations"]:
        writer.writerow({key: (
            ";".join(item["related_signed_quantity_ids"])
            if key == "related_signed_quantity_ids" else
            _csv_text(item.get(key)) if key not in (
                "net_ex_tax", "tax_pct", "tax", "gross_delta"
            ) else item.get(key)
        ) for key in names})
    return buf.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--quote", required=True, type=Path)
    parser.add_argument("--events", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    args = parser.parse_args(argv)
    contract = _read_json_without_duplicate_keys(args.contract)
    quote = _read_json_without_duplicate_keys(args.quote)
    events = _read_json_without_duplicate_keys(args.events)
    report = build_change_register(contract, quote, events)
    body = (change_order_csv(report) if args.format == "csv" else
            json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n")
    _write_new(args.output, body, (args.contract, args.quote, args.events))
    print(json.dumps({
        "contract_id": report["contract_id"],
        "approved_variation_delta": report["approved_variation_delta"],
        "committed_client_contract_gross": report["committed_client_contract_gross"],
        "official_four_project_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
