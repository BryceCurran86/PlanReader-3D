"""Benchmark-neutral handoff from verified production seals to V2-shaped items.

No benchmark manifest, object universe, reference quantities or evaluator is
read here. Trade classification MUST come from a separate source-authenticated
production receipt; family/finish strings are never guessed into trades.
"""
from __future__ import annotations

import argparse
import json
import math
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    sealed_source_closed_run_from_dict,
)

_TRADE = re.compile(r"^[a-z][a-z0-9_]*$")


class ProducedItemsHandoffError(ValueError):
    """Unproven source authority or ambiguous physical claim."""


def _refs(values: Any) -> tuple[str, ...]:
    if not isinstance(values, (list, tuple)) or any(
        not isinstance(v, str) or not v.strip() for v in values
    ):
        raise ProducedItemsHandoffError("identity/evidence refs must be nonempty strings")
    if len(values) != len(set(values)):
        raise ProducedItemsHandoffError("duplicate identity/evidence refs")
    return tuple(sorted(values))


def build_produced_items(
    sealed_run: SealedSourceClosedRun,
    customer_rows: Sequence[Mapping[str, Any]],
    trade_receipts: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Preserve exact production object IDs, units and quantities without remapping."""
    sealed = sealed_source_closed_run_from_dict(sealed_run.to_dict())
    verify_sealed_customer_output(sealed, customer_rows)
    firm = {row.quantity_id: row for row in sealed.quantities if not row.abstained}
    if not firm:
        raise ProducedItemsHandoffError("no firm sealed production quantities")

    receipts: dict[str, Mapping[str, Any]] = {}
    for receipt in trade_receipts:
        if not isinstance(receipt, Mapping):
            raise ProducedItemsHandoffError("trade receipt must be an object")
        quantity_id = receipt.get("quantity_id")
        if not isinstance(quantity_id, str) or quantity_id not in firm:
            raise ProducedItemsHandoffError("trade receipt references unknown/abstained quantity")
        if quantity_id in receipts:
            raise ProducedItemsHandoffError("duplicate trade receipt")
        receipts[quantity_id] = receipt
    if set(receipts) != set(firm):
        raise ProducedItemsHandoffError("missing authenticated trade receipts")

    produced: list[dict[str, Any]] = []
    seen_claims: set[tuple[str, str, tuple[str, ...]]] = set()
    for quantity_id, row in sorted(firm.items()):
        receipt = receipts[quantity_id]
        if not row.lineage_ok or row.blocking_reasons or row.lineage_reason_codes:
            raise ProducedItemsHandoffError("unverified or blocked sealed quantity")
        if any(
            token in str(field).lower()
            for token in ("conflict", "supersed", "abstain")
            for field in (row.status, *row.reason_codes)
        ):
            raise ProducedItemsHandoffError("conflicted, abstained or superseded quantity")
        if row.value is None or not math.isfinite(row.value) or row.value < 0:
            raise ProducedItemsHandoffError("invalid firm quantity")
        if not row.object_identity_refs or not row.evidence_ids:
            raise ProducedItemsHandoffError("missing source-owned identity/evidence")
        trade = receipt.get("trade_category")
        if not isinstance(trade, str) or not _TRADE.fullmatch(trade):
            raise ProducedItemsHandoffError("missing or invalid authenticated trade")
        if receipt.get("authority") != "authenticated_source":
            raise ProducedItemsHandoffError("trade classification is not source authenticated")
        if not isinstance(receipt.get("authority_id"), str) or not receipt["authority_id"].strip():
            raise ProducedItemsHandoffError("trade authority identity missing")
        if (
            receipt.get("quantity_fingerprint") != row.fingerprint
            or receipt.get("source_sha256") != row.source_sha256
            or receipt.get("family") != row.family
            or _refs(receipt.get("object_identity_refs")) != tuple(row.object_identity_refs)
        ):
            raise ProducedItemsHandoffError("trade receipt does not bind sealed quantity")
        evidence = _refs(receipt.get("source_evidence_ids"))
        if not evidence or not set(evidence).issubset(set(row.trace_evidence_ids)):
            raise ProducedItemsHandoffError("trade evidence is not in authenticated source trace")
        claim = (trade, row.unit.lower(), tuple(row.object_identity_refs))
        if claim in seen_claims:
            raise ProducedItemsHandoffError("duplicate trade/unit/physical object claim")
        seen_claims.add(claim)
        produced.append({
            "quantity_id": row.quantity_id,
            "trade_category": trade,
            "value": row.value,
            "unit": row.unit,
            "object_refs": list(row.object_identity_refs),
            "lineage_ok": True,
            "abstained": False,
        })
    return produced


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sealed-run", required=True, type=Path)
    parser.add_argument("--customer-rows", required=True, type=Path)
    parser.add_argument("--trade-receipts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = json.loads(args.sealed_run.read_text(encoding="utf-8"))
    sealed = sealed_source_closed_run_from_dict(payload)
    customer = json.loads(args.customer_rows.read_text(encoding="utf-8"))
    receipts = json.loads(args.trade_receipts.read_text(encoding="utf-8"))
    if not isinstance(customer, list) or not isinstance(receipts, list):
        raise ProducedItemsHandoffError("customer rows and trade receipts must be lists")
    produced = build_produced_items(sealed, customer, receipts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(produced, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
