"""Verified ORIGINAL Lot16 sealed rows -> strictly UNMAPPED production inventory.

No benchmark truth, expected quantities, names or inferred identity matches.
The output is diagnostic source ancestry for independent physical binding only.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import re

from pb_combine_source_closed_runs import load_verified_sealed_run
from pb_customer_output_verification import verify_sealed_customer_output
from tools.run_gpt3_lot16_original_sealed_score_input import _publish_new

PROJECT = "au_qld_lot16_power"
ID = re.compile(r"physical_opening_existence_[0-9a-f]{32}\Z")
SHA = re.compile(r"[0-9a-f]{64}\Z")


def build_unmapped_inventory(sealed, rows, verified, receipt: dict) -> dict:
    """Never promote a signed source quantity into a frozen benchmark object."""
    source_sha = receipt.get("source_sha256")
    if (
        sealed.project_id != PROJECT
        or not isinstance(source_sha, str)
        or not SHA.fullmatch(source_sha)
        or tuple(sealed.source_sha256s) != (source_sha,)
        or sealed.fingerprint != receipt.get("sealed_run_fingerprint")
        or sealed.run_id != receipt.get("sealed_run_id")
        or receipt.get("benchmark_score_granted") is not False
        or receipt.get("benchmark_accuracy") is not None
        or receipt.get("frozen_v2_reconciliation_complete") is not False
        or receipt.get("identity_map_status")
        != "INDEPENDENT_ORIGINAL_SOURCE_BINDINGS_REQUIRED"
    ):
        raise ValueError("original source seal/benchmark readiness conflict")
    quantities = tuple(sealed.quantities)
    if not quantities:
        raise ValueError("empty original source quantity inventory")
    quantity_ids = [q.quantity_id for q in quantities]
    if not isinstance(rows, (tuple, list)) or any(
        not isinstance(row, dict) for row in rows
    ):
        raise ValueError("original customer row inventory malformed")
    row_ids = [row.get("quantity_id") for row in rows]
    if (
        any(not isinstance(x, str) or not x or x != x.strip()
            for x in (*quantity_ids, *row_ids))
        or len(set(quantity_ids)) != len(quantity_ids)
        or len(set(row_ids)) != len(row_ids)
        or set(row_ids) != set(quantity_ids)
        or set(verified.verified_quantity_ids) != set(quantity_ids)
        or verified.valid_quantity_count != len(quantity_ids)
        or len(verified.verified_quantity_ids) != len(quantity_ids)
        or receipt.get("quantity_count") != len(quantity_ids)
        or sorted(receipt.get("sealed_quantity_ids", [])) != sorted(quantity_ids)
        or sorted(receipt.get("customer_verified_quantity_ids", []))
        != sorted(quantity_ids)
    ):
        raise ValueError("signed original quantities/customer row parity invalid")
    by_id = {row["quantity_id"]: row for row in rows}
    produced = []
    used_physical_ids = set()
    for q in sorted(quantities, key=lambda item: item.quantity_id):
        object_refs = getattr(q, "object_identity_refs", None)
        evidence_ids = getattr(q, "evidence_ids", ())
        physical = (
            object_refs[0]
            if isinstance(object_refs, (tuple, list)) and len(object_refs) == 1
            else None
        )
        status = getattr(q.status, "value", q.status)
        if (
            q.project_id != PROJECT or q.source_sha256 != source_sha
            or q.family != "opening_area" or q.source_page != "3"
            or q.unit not in ("m2", "m²")
            or type(q.value) not in (int, float) or not math.isfinite(q.value)
            or q.value <= 0 or q.abstained is not False
            or q.lineage_ok is not True or str(status).lower() != "corroborated"
            or not isinstance(physical, str) or not ID.fullmatch(physical)
            or physical in used_physical_ids
            or not isinstance(evidence_ids, (tuple, list))
            or not evidence_ids
            or any(not isinstance(e, str) or not e for e in evidence_ids)
            or not isinstance(q.fingerprint, str) or not SHA.fullmatch(q.fingerprint)
        ):
            raise ValueError("source physical opening/area identity unverified")
        customer = by_id[q.quantity_id]
        if (
            customer.get("source_sha256") != source_sha
            or customer.get("project_id") != PROJECT
            or tuple(customer.get("canonical_entity_ids", ())) != (physical,)
            or customer.get("quantity_family") != "opening_area"
            or customer.get("quantity_id") != q.quantity_id
        ):
            raise ValueError("source customer row identity does not match seal")
        used_physical_ids.add(physical)
        produced.append({
            "quantity_id": q.quantity_id,
            "original_physical_object_id": physical,
            "source_sha256": source_sha,
            "source_page": q.source_page,
            "quantity_family": q.family,
            "value": q.value,
            "unit": q.unit,
            "source_authority": q.authority,
            "source_evidence_ids": list(evidence_ids),
            "source_quantity_fingerprint": q.fingerprint,
            "source_lineage_verified": True,
            "customer_quantity_id_verified": True,
            "frozen_benchmark_object_ref": None,
            "frozen_object_identity_status": "UNRESOLVED_ORIGINAL_SOURCE_BINDING_REQUIRED",
            "frozen_match_status": "UNRESOLVED",
        })
    return {
        "project_id": PROJECT,
        "source_sha256": source_sha,
        "sealed_run_id": sealed.run_id,
        "sealed_run_fingerprint": sealed.fingerprint,
        "verified_quantity_count": len(produced),
        "unmapped_produced_items": produced,
        "object_identity_map_supplied": False,
        "frozen_v2_reconciliation_complete": False,
        "benchmark_accuracy": None,
        "benchmark_score_granted": False,
        "diagnostic_only": True,
    }


def generate_unmapped_inventory(production_dir: Path) -> dict:
    """Independently reverify original signed files; never re-extract source."""
    sealed = load_verified_sealed_run(production_dir / "source_sealed_run.json")
    rows = json.loads((production_dir / "verified_customer_rows.json").read_text())
    receipt = json.loads(
        (production_dir / "source_score_readiness_UNPUBLISHED.json").read_text()
    )
    verified = verify_sealed_customer_output(sealed, rows)
    result = build_unmapped_inventory(sealed, rows, verified, receipt)
    _publish_new(production_dir / "produced_items_UNMAPPED.json", result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = generate_unmapped_inventory(args.production_dir)
    print(json.dumps({
        "status": "SOURCE_VERIFIED_UNMAPPED_BENCHMARK_UNPUBLISHED",
        "quantity_count": result["verified_quantity_count"],
        "benchmark_accuracy": None,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
