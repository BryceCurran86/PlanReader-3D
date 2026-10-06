from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import pb_physical_wall_candidate_authority as wallmod
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import (
    KIND_GRID,
    collect_typed_semantic_evidence,
)

SOURCE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_GRID_REASON = "source_lineage_dense_orthogonal_lattice"
TARGETS = (
    "FOOD PREP",
    "COLD ROOM",
    "FREEZER",
    "DRY STORE",
    "SALES",
    "WASH UP",
    "FOOD SERVICE",
    "POS COUNTER",
    "M-AMB",
    "F-AMB",
    "TRUCK DRIVER LOUNGE",
    "PWD",
    "AIRLOCK",
    "LAUNDRY",
    "OFFICE",
)


def _norm(value: object) -> str:
    return " ".join(str(value or "").strip().upper().split())


def main() -> int:
    started = time.perf_counter()
    payload = SOURCE.read_bytes()
    source_sha256 = hashlib.sha256(payload).hexdigest()

    original_filter = wallmod._filter_repeated_non_physical_drafting_primitives
    stats = {
        "filter_call_count": 0,
        "baseline_segment_count": 0,
        "proven_grid_source_primitive_count": 0,
        "matched_source_segment_count": 0,
        "removed_segment_count": 0,
        "proven_grid_source_primitive_ids": [],
        "removed_source_segment_ids": [],
    }

    def shadow_counterfactual_filter(
        segments,
        *,
        page_width: float,
        page_height: float,
    ):
        baseline = tuple(
            original_filter(
                segments,
                page_width=page_width,
                page_height=page_height,
            )
        )
        stats["filter_call_count"] += 1
        stats["baseline_segment_count"] += len(baseline)

        graph = build_wall_graph_for_viewport(baseline)
        atoms = collect_typed_semantic_evidence(
            graph,
            document_id=f"diag-maryborough:{source_sha256[:32]}",
            page_id="7",
            viewport_id="diag-maryborough-floor-plan",
        )

        source_ids: set[str] = set()
        for atom in atoms:
            if atom.kind != KIND_GRID or SOURCE_GRID_REASON not in tuple(atom.reason_codes or ()):
                continue
            basis = dict((atom.metadata or {}).get("feature_basis") or {})
            for source_id in basis.get("source_primitive_ids") or ():
                source_id = str(source_id or "").strip()
                if source_id:
                    source_ids.add(source_id)

        baseline_ids = {
            str(segment.get("id") or "").strip()
            for segment in baseline
            if str(segment.get("id") or "").strip()
        }
        matched = source_ids & baseline_ids
        kept = tuple(
            segment
            for segment in baseline
            if str(segment.get("id") or "").strip() not in matched
        )

        stats["proven_grid_source_primitive_count"] += len(source_ids)
        stats["matched_source_segment_count"] += len(matched)
        stats["removed_segment_count"] += len(baseline) - len(kept)
        stats["proven_grid_source_primitive_ids"] = sorted(
            set(stats["proven_grid_source_primitive_ids"]) | source_ids
        )
        stats["removed_source_segment_ids"] = sorted(
            set(stats["removed_source_segment_ids"]) | matched
        )
        return kept

    wallmod._filter_repeated_non_physical_drafting_primitives = shadow_counterfactual_filter
    try:
        claim = collect_live_physical_net_wall_claim(
            SOURCE,
            pages=(6,),
            topology_pages=(6,),
            room_area_support_pages=(10,),
        )
    finally:
        wallmod._filter_repeated_non_physical_drafting_primitives = original_filter

    labels = sorted(
        {
            _norm(room.room_label)
            for room in claim.canonical_rooms
            if _norm(room.room_label)
        }
    )
    firm = [
        {
            "quantity_id": quantity.quantity_id,
            "room_label": dict(quantity.metadata or {}).get("room_label"),
            "value": quantity.value,
            "unit": quantity.unit,
            "authority": quantity.authority,
            "status": quantity.status,
            "evidence_ids": list(quantity.evidence_ids or ()),
            "figured_dimension_ids": list(
                dict(quantity.metadata or {}).get("figured_dimension_ids") or ()
            ),
            "resolved_scale_id": dict(quantity.metadata or {}).get("resolved_scale_id"),
            "scale_status": dict(quantity.metadata or {}).get("scale_status"),
            "input_entity_ids": list(quantity.input_entity_ids or ()),
        }
        for quantity in claim.room_area_quantity_evidence
        if not quantity.abstained
    ]
    floors = [
        {
            "canonical_floor_id": floor.canonical_floor_id,
            "room_entity_id": floor.room_entity_id,
            "metric_area_m2": floor.metric_area_m2,
            "metric_area_quantity_id": floor.metric_area_quantity_id,
            "metric_area_authority": floor.metric_area_authority,
        }
        for floor in claim.canonical_floors
        if floor.metric_area_m2 is not None
    ]

    target_rows = {}
    for target in TARGETS:
        target_rows[target] = {
            "label_present": target in labels,
            "firm_areas": [
                row
                for row in firm
                if _norm(row.get("room_label")) == target
            ],
        }

    output = {
        "source_sha256": source_sha256,
        "mode": "DIAGNOSTIC_ONLY_U2_SOURCE_GRID_SUPPRESSION",
        "status": getattr(claim.status, "value", str(claim.status)),
        "reason_codes": list(claim.reason_codes),
        "canonical_room_count": len(claim.canonical_rooms),
        "canonical_floor_count": len(claim.canonical_floors),
        "label_count": len(labels),
        "labels": labels,
        "firm_room_area_count": len(firm),
        "firm_room_areas": firm,
        "metric_floor_count": len(floors),
        "metric_floors": floors,
        "targets": target_rows,
        "counterfactual_filter": stats,
        "elapsed_seconds": time.perf_counter() - started,
    }
    print(json.dumps(output, indent=2, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
