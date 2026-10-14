"""Run the real Maryborough surface claim through floor-finish sealing only.

Diagnostic/source handoff for GPT3. This tool does not read frozen benchmark
truth, expected quantities, identity maps, tolerances or evaluator output. It
reuses the production source scope, production claim and production
floor-finish sealer, then records the first commercially useful output state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_finish_area_source_closed_export import seal_live_floor_finish_area_run
from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from tools.run_source_closed_project_handoff import _non_abstained, _source_page_scopes


def _status(value: object) -> str:
    owned = getattr(value, "value", value)
    return str(owned or "")


def inspect(pdf: Path, *, expected_sha256: str) -> dict:
    payload = pdf.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()
    if source_sha256 != expected_sha256.lower():
        raise ValueError("original source PDF SHA mismatch")

    topology_pages, support_pages, page_count = _source_page_scopes(pdf)
    all_pages = tuple(range(page_count))
    restricted = bool(topology_pages) and tuple(topology_pages) != all_pages
    claim_pages = (
        tuple(sorted(set(topology_pages) | set(support_pages)))
        if restricted
        else all_pages
    )
    claim = collect_live_physical_net_wall_claim(
        pdf,
        pages=claim_pages,
        topology_pages=(tuple(topology_pages) if restricted else None),
        room_area_support_pages=(tuple(support_pages) if support_pages else None),
        surface_semantic_pages=all_pages,
    )

    floor_areas = _non_abstained(publish_live_floor_area_quantities(claim))
    floor_finishes = _non_abstained(
        tuple(getattr(claim, "floor_finish_quantity_evidence", ()) or ())
    )

    finish_rows = []
    for quantity in floor_finishes:
        metadata = quantity.metadata if isinstance(quantity.metadata, dict) else dict(quantity.metadata or {})
        finish_rows.append({
            "quantity_id": quantity.quantity_id,
            "family": quantity.family,
            "value": quantity.value,
            "unit": quantity.unit,
            "status": _status(quantity.status),
            "authority": _status(quantity.authority),
            "abstained": bool(quantity.abstained),
            "input_entity_ids": list(quantity.input_entity_ids),
            "evidence_ids": list(quantity.evidence_ids),
            "reason_codes": list(quantity.reason_codes),
            "room_label": metadata.get("room_label"),
            "finish_code": metadata.get("finish_code"),
            "finish_system": metadata.get("finish_system"),
            "finish_binding_mode": metadata.get("finish_binding_mode"),
            "source_sha256": metadata.get("source_sha256"),
            "source_dimension_page_id": metadata.get("source_dimension_page_id"),
            "support_page_id": metadata.get("support_page_id"),
            "support_viewport_id": metadata.get("support_viewport_id"),
            "canonical_floor_id": metadata.get("canonical_floor_id"),
            "source_room_face_record_id": metadata.get("source_room_face_record_id"),
        })

    floor_rows = []
    for floor in tuple(getattr(claim, "canonical_floors", ()) or ()):
        floor_rows.append({
            "canonical_floor_id": getattr(floor, "canonical_floor_id", None),
            "physical_floor_surface_id": getattr(floor, "physical_floor_surface_id", None),
            "source_room_face_record_id": getattr(floor, "source_room_face_record_id", None),
            "metric_area_m2": getattr(floor, "metric_area_m2", None),
            "metric_area_quantity_id": getattr(floor, "metric_area_quantity_id", None),
            "metric_area_authority": getattr(floor, "metric_area_authority", None),
            "finish_descriptor": getattr(floor, "finish_descriptor", None),
            "page_id": getattr(floor, "page_id", None),
            "viewport_id": getattr(floor, "viewport_id", None),
        })

    sealed = None
    customer_rows = ()
    if floor_finishes:
        run = seal_live_floor_finish_area_run(
            claim,
            workspace_id=1,
            project_id="gpt3-maryborough-ft3-source-e2e",
        )
        if set(run.source_sha256s) != {source_sha256}:
            raise RuntimeError("sealed floor-finish source envelope changed")
        expected_ids = {q.quantity_id for q in floor_finishes}
        actual_ids = {q.quantity_id for q in run.quantities}
        if expected_ids != actual_ids or len(actual_ids) != len(run.quantities):
            raise RuntimeError("sealed floor-finish quantity identity mismatch")
        if any(q.abstained or not q.lineage_ok for q in run.quantities):
            raise RuntimeError("sealed floor-finish quantity failed lineage gate")
        sealed = {
            "run_id": run.run_id,
            "source_sha256s": list(run.source_sha256s),
            "quantity_count": len(run.quantities),
            "quantity_ids": sorted(actual_ids),
            "fingerprint": run.fingerprint,
        }
        # This is the existing production customer adapter. It separately
        # requires two figured dimensions for DOCUMENTED_DIMENSION authority
        # and verifies the projected rows against a fresh source-closed seal.
        customer_rows = project_live_floor_finish_customer_rows(
            claim,
            workspace_id=1,
            project_id="gpt3-maryborough-ft3-source-e2e",
        )
        if len(customer_rows) != len(floor_finishes):
            raise RuntimeError("floor-finish sealed/customer cardinality mismatch")

    return {
        "diagnostic_only": True,
        "benchmark_score_granted": False,
        "frozen_benchmark_accuracy": None,
        "source_sha256_verified": True,
        "source_sha256": source_sha256,
        "source_page_count": page_count,
        "topology_pages": [p + 1 for p in topology_pages],
        "room_area_support_pages": [p + 1 for p in support_pages],
        "semantic_pages": [p + 1 for p in all_pages],
        "claim_status": _status(getattr(claim, "status", "")),
        "claim_reason_codes": list(getattr(claim, "reason_codes", ()) or ()),
        "canonical_floor_count": len(floor_rows),
        "firm_floor_area_count": len(floor_areas),
        "firm_floor_finish_area_count": len(floor_finishes),
        "canonical_floors": floor_rows,
        "floor_finish_quantities": finish_rows,
        "same_view_room_area_first_failure_codes": [
            list(row) for row in (
                getattr(claim, "same_view_room_area_first_failure_codes", ()) or ()
            )
        ],
        "cross_view_room_area_first_failure_codes": [
            list(row) for row in (
                getattr(claim, "cross_view_room_area_first_failure_codes", ()) or ()
            )
        ],
        "sealed_floor_finish_run": sealed,
        "verified_customer_row_count": len(customer_rows),
        "customer_rows": list(customer_rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = inspect(args.pdf, expected_sha256=args.expected_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "source_sha256_verified": report["source_sha256_verified"],
        "claim_status": report["claim_status"],
        "canonical_floor_count": report["canonical_floor_count"],
        "firm_floor_area_count": report["firm_floor_area_count"],
        "firm_floor_finish_area_count": report["firm_floor_finish_area_count"],
        "finish_codes": sorted({
            str(row.get("finish_code") or "")
            for row in report["floor_finish_quantities"]
            if row.get("finish_code")
        }),
        "sealed_floor_finish_run": report["sealed_floor_finish_run"],
        "verified_customer_row_count": report["verified_customer_row_count"],
        "benchmark_score_granted": False,
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
