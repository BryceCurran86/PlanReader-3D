from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pb_opening_host_binding_authority as host
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _wall_geometry_rows(walls, equivalence, geometry):
    group_lookup = host._equivalence_group_lookup(equivalence)
    edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
    thickness_tol = max(0.75, geometry.thickness * 0.15)
    center_tol = max(host.DEFAULT_GAP_SNAP_TOLERANCE_PT, thickness_tol)

    candidates = []
    for record in walls:
        data = host._candidate_axis_data(record, geometry)
        if data is None:
            continue
        u0, u1, offset = data
        identity = record.physical_identity
        group = tuple(group_lookup.get(record.wall_candidate_id, (record.wall_candidate_id,)))
        candidates.append({
            "id": record.wall_candidate_id,
            "u0": float(u0),
            "u1": float(u1),
            "offset": float(offset),
            "group": list(group),
            "identity_usable": bool(identity.usable),
            "candidate_identity_id": identity.candidate_identity_id,
            "representation": record.wall_candidate.representation,
            "reason_codes": list(record.wall_candidate.reason_codes),
            "source_primitive_ids": list(identity.source_primitive_ids),
        })

    spanning = [
        row for row in candidates
        if row["u0"] < -edge_tol and row["u1"] > geometry.length + edge_tol
    ]
    centered = [
        row for row in spanning
        if abs(row["offset"]) <= center_tol
    ]
    left = [
        row for row in candidates
        if row["u0"] < -edge_tol and abs(row["u1"]) <= edge_tol
    ]
    right = [
        row for row in candidates
        if row["u1"] > geometry.length + edge_tol
        and abs(row["u0"] - geometry.length) <= edge_tol
    ]
    pair_lookup = host._pair_lookup(equivalence)
    raw_by_id = {record.wall_candidate_id: record for record in walls}
    left_raw = [
        (row["offset"], raw_by_id[row["id"]])
        for row in left
    ]
    right_raw = [
        (row["offset"], raw_by_id[row["id"]])
        for row in right
    ]
    axis_tol = max(0.5, geometry.thickness * 0.05)
    left_status, left_normalized, left_reasons = host._normalize_role_candidates(
        left_raw,
        equivalence,
        axis_tol,
        pair_lookup=pair_lookup,
        group_lookup=group_lookup,
    )
    right_status, right_normalized, right_reasons = host._normalize_role_candidates(
        right_raw,
        equivalence,
        axis_tol,
        pair_lookup=pair_lookup,
        group_lookup=group_lookup,
    )

    face_breaks = []
    if (
        left_status.value == "corroborated"
        and right_status.value == "corroborated"
    ):
        for left_role in left_normalized:
            for right_role in right_normalized:
                delta = abs(right_role.offset - left_role.offset)
                if delta <= axis_tol:
                    face_breaks.append({
                        "left_id": left_role.record.wall_candidate_id,
                        "right_id": right_role.record.wall_candidate_id,
                        "left_offset": left_role.offset,
                        "right_offset": right_role.offset,
                        "axis_delta": delta,
                        "left_group": list(left_role.candidate_group),
                        "right_group": list(right_role.candidate_group),
                    })

    thickness_tol = max(0.75, geometry.thickness * 0.15)
    band_pairs = []
    for index, first in enumerate(face_breaks):
        for second in face_breaks[index + 1:]:
            separation = abs(second["left_offset"] - first["left_offset"])
            center_offset = (
                first["left_offset"] + second["left_offset"]
            ) / 2.0
            band_pairs.append({
                "first": [first["left_id"], first["right_id"]],
                "second": [second["left_id"], second["right_id"]],
                "separation": separation,
                "thickness_error": abs(separation - geometry.thickness),
                "within_thickness_tolerance": (
                    abs(separation - geometry.thickness) <= thickness_tol
                ),
                "center_offset": center_offset,
            })

    return {
        "axis_candidate_count": len(candidates),
        "left_termination_count": len(left),
        "right_termination_count": len(right),
        "spanning_count": len(spanning),
        "centered_spanning_count": len(centered),
        "center_tol": center_tol,
        "axis_tol": axis_tol,
        "thickness_tol": thickness_tol,
        "left_normalization_status": left_status.value,
        "left_normalization_reasons": list(left_reasons),
        "right_normalization_status": right_status.value,
        "right_normalization_reasons": list(right_reasons),
        "left_normalized": [
            {
                "id": item.record.wall_candidate_id,
                "offset": item.offset,
                "group": list(item.candidate_group),
            }
            for item in left_normalized
        ],
        "right_normalized": [
            {
                "id": item.record.wall_candidate_id,
                "offset": item.offset,
                "group": list(item.candidate_group),
            }
            for item in right_normalized
        ],
        "face_break_count": len(face_breaks),
        "face_breaks": face_breaks,
        "band_pair_count": len(band_pairs),
        "band_pairs": band_pairs,
        "centered_spanning": sorted(
            centered, key=lambda row: (abs(row["offset"]), row["id"])
        )[:20],
        "nearest_offsets": sorted(
            candidates, key=lambda row: (abs(row["offset"]), row["id"])
        )[:30],
    }


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_missing_host_area_doors",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-missing-host-area-doors",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    opening_composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    assert published is not None

    targets = [
        opening
        for opening in opening_composition.canonical_openings
        if opening.opening_kind == "door"
        and opening.area_m2 is not None
        and opening.host_wall_id is None
    ]
    if not targets:
        print(json.dumps({
            "source_sha256": source_sha,
            "target_count": 0,
            "targets": [],
        }, indent=2, sort_keys=True))
        return

    physical = wall_opening.physical_opening_authority
    semantic = wall_opening.semantic_enumeration_result.record
    assert semantic is not None
    records = {}
    for observation_id in semantic.representative_observation_ids:
        result = physical.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if result.existence_record is not None:
            records[result.existence_record.record_id] = result.existence_record

    walls = wall_opening.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=f"wall-source:page-{PAGE_ID}",
        )
    )
    assert walls.scope_complete and walls.equivalence is not None

    binding_by_id = {
        item.opening_identity_id: item
        for item in wall_opening.opening_bindings
        if item.opening_identity_id
    }

    rows = []
    for target in sorted(targets, key=lambda item: item.canonical_opening_id):
        opening = records.get(target.canonical_opening_id)
        if opening is None:
            rows.append({
                "opening_id": target.canonical_opening_id,
                "area_m2": target.area_m2,
                "area_basis": target.area_basis,
                "error": "physical_opening_record_not_found",
            })
            continue
        geometry = host._opening_geometry(physical, opening)
        trace = binding_by_id.get(opening.record_id)
        row = {
            "opening_id": opening.record_id,
            "structural_pattern": opening.structural_pattern,
            "area_m2": target.area_m2,
            "area_basis": target.area_basis,
            "figured_area_record_id": target.figured_area_record_id,
            "aperture_bbox_pt": opening.aperture_bbox_pt,
            "binding_trace": None if trace is None else {
                "status": trace.status.value,
                "reason_codes": list(trace.reason_codes),
                "record_id": trace.record_id,
                "host_wall_id": trace.host_wall_id,
                "member_wall_candidate_ids": list(trace.member_wall_candidate_ids),
            },
        }
        if geometry is not None:
            row["geometry"] = {
                "origin": list(geometry.origin),
                "axis": list(geometry.axis),
                "normal": list(geometry.normal),
                "length": geometry.length,
                "thickness": geometry.thickness,
            }
            row.update(_wall_geometry_rows(walls.records, walls.equivalence, geometry))
        rows.append(row)

    print(json.dumps({
        "source_sha256": source_sha,
        "target_count": len(rows),
        "wall_candidate_count": len(walls.records),
        "targets": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
