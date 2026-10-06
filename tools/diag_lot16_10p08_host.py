from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"
TARGET_OPENING_ID = "physical_opening_existence_6cfacbe0cd24184ea9bf0fc52ab965fe"


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_10p08_host",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-10p08-host",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    assert published is not None

    physical = composition.physical_opening_authority
    semantic = composition.semantic_enumeration_result.record
    assert semantic is not None

    opening = None
    for observation_id in semantic.representative_observation_ids:
        result = physical.prove_existence(
            __import__("pb_source_observation_authority").ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if result.existence_record is not None and result.existence_record.record_id == TARGET_OPENING_ID:
            opening = result.existence_record
            break
    if opening is None:
        raise SystemExit("target opening not found")

    trace = next(
        (
            item for item in composition.opening_bindings
            if item.opening_identity_id == TARGET_OPENING_ID
        ),
        None,
    )
    geometry = host._opening_geometry(physical, opening)
    assert geometry is not None

    walls = composition.physical_wall_candidate_authority.resolve_scope(
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
    group_lookup = host._equivalence_group_lookup(walls.equivalence)

    edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
    thickness_tol = max(0.75, geometry.thickness * 0.15)
    center_tol = max(host.DEFAULT_GAP_SNAP_TOLERANCE_PT, thickness_tol)

    candidates = []
    for record in walls.records:
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

    print(json.dumps({
        "source_sha256": source_sha,
        "opening_id": TARGET_OPENING_ID,
        "structural_pattern": opening.structural_pattern,
        "aperture_bbox_pt": opening.aperture_bbox_pt,
        "geometry": {
            "origin": list(geometry.origin),
            "direction": list(geometry.direction),
            "length": geometry.length,
            "thickness": geometry.thickness,
        },
        "binding_trace": None if trace is None else {
            "status": trace.status.value,
            "reason_codes": list(trace.reason_codes),
            "record_id": trace.record_id,
            "host_wall_id": trace.host_wall_id,
            "member_wall_candidate_ids": list(trace.member_wall_candidate_ids),
        },
        "wall_candidate_count": len(walls.records),
        "axis_candidate_count": len(candidates),
        "left_termination_count": len(left),
        "right_termination_count": len(right),
        "spanning_count": len(spanning),
        "centered_spanning_count": len(centered),
        "center_tol": center_tol,
        "centered_spanning": sorted(centered, key=lambda row: (abs(row["offset"]), row["id"]))[:20],
        "nearest_offsets": sorted(candidates, key=lambda row: (abs(row["offset"]), row["id"]))[:30],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
