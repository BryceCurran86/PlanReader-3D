"""Diagnostic-only Lot16 room-face source geometry trace (no authority changes).

Run: PYTHONPATH=. python tools/diag_lot16_room_face_scope.py --pdf "documents/sources/3. Architectural - Lot 16 Power.pdf" --page-index 2 --output lot16-room-face-scope.json
The PDF path must be an actual source file; no benchmark gold is loaded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import pb_source_room_face_authority as face_authority
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim


def inspect_source(pdf: Path, page_index: int) -> dict:
    payload = pdf.read_bytes()
    observations = []
    original_derive = face_authority._derive_scope_outcome
    original_extract = face_authority.extract_planar_faces

    def traced_extract(segments, *args, **kwargs):
        faces = original_extract(segments, *args, **kwargs)
        areas = sorted(
            (round(face_authority._polygon_area(face_authority._canonical_polygon(face)), 6)
             for face in faces if face_authority._canonical_polygon(face))
        )
        observations[-1]["planar_faces"] = {
            "count": len(faces),
            "canonical_count": len(areas),
            "areas_pt2_sorted": areas[:1000],
            "areas_truncated": len(areas) > 1000,
            "under_absolute_threshold": sum(
                area < face_authority._ABSOLUTE_DEGENERATE_AREA_PT2 for area in areas
            ),
            "under_relative_threshold": sum(
                area < (areas[-1] * face_authority._TINY_RELATIVE_THRESHOLD)
                for area in areas
            ) if areas else 0,
        }
        return faces

    def traced_derive(scope):
        records = tuple(getattr(scope, "records", ()) or ())
        edges_by_wall = {}
        for record in records:
            wall_id = str(getattr(record, "wall_candidate_id", "") or "")
            if wall_id:
                edges_by_wall[wall_id] = face_authority._wall_edges(record)
        observation = {
            "page_id": str(getattr(scope, "page_id", "") or ""),
            "decision_scope_id": str(getattr(scope, "decision_scope_id", "") or ""),
            "scope_status": str(getattr(getattr(scope, "status", None), "value", getattr(scope, "status", None))),
            "scope_complete": bool(getattr(scope, "scope_complete", False)),
            "source_wall_record_count": len(records),
            "source_wall_identity_count": len(edges_by_wall),
            "source_wall_edge_count": sum(map(len, edges_by_wall.values())),
            "source_wall_zero_edge_count": sum(not edges for edges in edges_by_wall.values()),
        }
        observations.append(observation)
        outcome = original_derive(scope)
        observation["outcome_status"] = str(getattr(getattr(outcome, "status", None), "value", getattr(outcome, "status", None)))
        observation["outcome_reasons"] = list(getattr(outcome, "reason_codes", ()) or ())
        observation["published_face_count"] = len(getattr(outcome, "records", ()) or ())
        return outcome

    try:
        face_authority._derive_scope_outcome = traced_derive
        face_authority.extract_planar_faces = traced_extract
        claim = collect_live_physical_net_wall_claim(
            pdf, pages=(page_index,), topology_pages=(page_index,),
            room_area_support_pages=None,
        )
        return {
            "diagnostic_only": True, "pdf_sha256": hashlib.sha256(payload).hexdigest(),
            "source_page_index_zero_based": page_index,
            "scope_outcomes": observations,
            "claim_type": type(claim).__name__,
            "same_view_prerequisite_breakdown": {
                "room_count": len(claim.canonical_rooms),
                "geometry_incomplete": sum(not room.geometry_complete for room in claim.canonical_rooms),
                "physical_room_id_missing": sum(not str(room.physical_room_id or "").strip() for room in claim.canonical_rooms),
                "source_face_id_missing": sum(not str(room.source_room_face_record_id or "").strip() for room in claim.canonical_rooms),
                "room_label_missing": sum(not str(room.room_label or "").strip() for room in claim.canonical_rooms),
                "room_label_binding_missing": sum(not str(room.room_label_binding_record_id or "").strip() for room in claim.canonical_rooms),
                "room_label_evidence_missing": sum(not bool(room.room_label_evidence_ids) for room in claim.canonical_rooms),
            },
            "downstream": {
                "canonical_room_count": len(claim.canonical_rooms),
                "canonical_room_status": str(getattr(claim.canonical_room_status, "value", claim.canonical_room_status)),
                "canonical_room_reasons": list(claim.canonical_room_reason_codes),
                "canonical_floor_count": len(claim.canonical_floors),
                "canonical_floor_status": str(getattr(claim.canonical_floor_status, "value", claim.canonical_floor_status)),
                "canonical_floor_reasons": list(claim.canonical_floor_reason_codes),
                "metric_floor_count": sum(bool(getattr(floor, "metric_area_complete", False)) for floor in claim.canonical_floors),
                "room_area_quantity_count": len(claim.room_area_quantity_evidence),
                "floor_finish_quantity_count": len(claim.floor_finish_quantity_evidence),
                "same_view_first_failures": list(claim.same_view_room_area_first_failure_codes),
                "cross_view_first_failures": list(claim.cross_view_room_area_first_failure_codes),
                "physical_scale_first_failures": list(claim.physical_scale_first_failure_codes),
            },
            "scope_reason_frequency": dict(Counter(
                reason for item in observations for reason in item["outcome_reasons"]
            )),
        }
    finally:
        face_authority._derive_scope_outcome = original_derive
        face_authority.extract_planar_faces = original_extract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-index", type=int, default=2)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.page_index < 0:
        parser.error("--page-index must be >= 0")
    if not args.pdf.is_file():
        parser.error(f"source PDF unavailable: {args.pdf}")
    report = inspect_source(args.pdf, args.page_index)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "pdf_sha256": report["pdf_sha256"],
        "scope_count": len(report["scope_outcomes"]),
        "scope_reason_frequency": report["scope_reason_frequency"],
        "output": str(args.output),
    }, sort_keys=True))


if __name__ == "__main__":
    main()
