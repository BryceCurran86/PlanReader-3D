from __future__ import annotations

import hashlib
import json
from pathlib import Path

import fitz

import pb_opening_host_binding_authority as host
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_floor_plan_page_scope import source_floor_plan_topology_scope
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"


def _result_dict(result) -> dict:
    return {
        "status": str(getattr(result.status, "value", result.status)),
        "reason_codes": list(result.reason_codes),
        "band_count": len(result.bands),
        "bands": [
            {
                "member_ids": list(band.member_ids),
                "member_candidate_identity_ids": list(
                    band.member_candidate_identity_ids
                ),
                "member_equivalence_groups": [
                    list(group) for group in band.member_equivalence_groups
                ],
                "center_offset": band.center_offset,
            }
            for band in result.bands
        ],
    }


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    with fitz.open(stream=source_bytes, filetype="pdf") as doc:
        all_indices = tuple(range(int(doc.page_count)))
    scope = source_floor_plan_topology_scope(PDF, all_indices)
    topology_indices = (
        tuple(scope.topology_page_indices() or ())
        if scope is not None
        else all_indices
    )
    topology_page_ids = tuple(str(i + 1) for i in topology_indices)
    all_page_ids = tuple(str(i + 1) for i in all_indices)
    evidence_page_ids = tuple(
        page_id for page_id in all_page_ids
        if page_id not in topology_page_ids
    )

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_area_ready_host",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-area-ready-host",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=all_page_ids,
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_page_ids,
        evidence_page_ids=evidence_page_ids,
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    current = source.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert current is not None

    ready = [
        opening
        for opening in voids.canonical_openings
        if str(opening.opening_kind or "").strip().lower() in {"door", "window"}
        and opening.area_m2 is not None
        and not str(opening.host_wall_id or "").strip()
    ]
    if len(ready) != 1:
        raise SystemExit(
            f"expected exactly one area-ready unhosted opening, got {len(ready)}"
        )
    target = ready[0]

    semantic = wall_opening.semantic_enumeration_result.record
    assert semantic is not None
    physical = wall_opening.physical_opening_authority
    existence = None
    for observation_id in semantic.representative_observation_ids:
        result = physical.prove_existence(
            ObservationSelector(
                document_id=current.revision.document_id,
                revision_id=current.revision.revision_id,
                source_sha256=current.revision.source_sha256,
                snapshot_id=current.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.existence_record is not None
            and result.existence_record.record_id
            == target.physical_opening_id
        ):
            existence = result.existence_record
            break
    if existence is None:
        raise SystemExit("physical opening record not found")

    page_id = str(existence.page_id)
    wall_scope = wall_opening.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=current.revision.document_id,
            revision_id=current.revision.revision_id,
            source_sha256=current.revision.source_sha256,
            snapshot_id=current.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=f"wall-source:page-{page_id}",
        )
    )
    if not wall_scope.scope_complete or wall_scope.equivalence is None:
        raise SystemExit("wall scope/equivalence unavailable")

    geometry = host._opening_geometry(physical, existence)
    if geometry is None:
        raise SystemExit("opening geometry unavailable")

    split = host._resolve_host_bands(
        wall_scope.records,
        geometry,
        wall_scope.equivalence,
    )
    whole = host._resolve_raster_whole_wall_host(
        wall_scope.records,
        geometry,
        wall_scope.equivalence,
    )
    centerline = host._resolve_raster_split_centerline_host(
        wall_scope.records,
        geometry,
        wall_scope.equivalence,
    )

    trace = next(
        (
            row for row in wall_opening.opening_bindings
            if row.opening_identity_id == target.physical_opening_id
        ),
        None,
    )

    edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
    axis_rows = []
    for record in wall_scope.records:
        data = host._candidate_axis_data(record, geometry)
        if data is None:
            continue
        u0, u1, offset = data
        axis_rows.append({
            "id": record.wall_candidate_id,
            "u0": float(u0),
            "u1": float(u1),
            "offset": float(offset),
            "usable": bool(record.physical_identity.usable),
            "candidate_identity_id":
                record.physical_identity.candidate_identity_id,
            "source_primitive_ids": list(
                record.physical_identity.source_primitive_ids
            ),
            "representation": record.wall_candidate.representation,
            "reason_codes": list(record.wall_candidate.reason_codes),
        })

    left = [
        row for row in axis_rows
        if row["u0"] < -edge_tol and abs(row["u1"]) <= edge_tol
    ]
    right = [
        row for row in axis_rows
        if row["u1"] > geometry.length + edge_tol
        and abs(row["u0"] - geometry.length) <= edge_tol
    ]
    spanning = [
        row for row in axis_rows
        if row["u0"] < -edge_tol
        and row["u1"] > geometry.length + edge_tol
    ]

    payload = {
        "source_sha256": source_sha,
        "topology_page_ids": list(topology_page_ids),
        "target": {
            "physical_opening_id": target.physical_opening_id,
            "canonical_opening_id": target.canonical_opening_id,
            "page_id": page_id,
            "pattern": target.structural_pattern,
            "opening_kind": target.opening_kind,
            "area_m2": target.area_m2,
            "area_basis": target.area_basis,
            "figured_area_record_id": target.figured_area_record_id,
            "evidence_ids": list(target.evidence_ids),
        },
        "opening_geometry": {
            "origin": list(geometry.origin),
            "direction": list(geometry.direction),
            "length": geometry.length,
            "thickness": geometry.thickness,
            "aperture_bbox_pt": existence.aperture_bbox_pt,
        },
        "current_binding": None if trace is None else {
            "status": str(getattr(trace.status, "value", trace.status)),
            "reason_codes": list(trace.reason_codes),
            "record_id": trace.record_id,
            "host_wall_id": trace.host_wall_id,
            "member_wall_candidate_ids":
                list(trace.member_wall_candidate_ids),
        },
        "split_face_resolution": _result_dict(split),
        "whole_wall_resolution": _result_dict(whole),
        "split_centerline_resolution": _result_dict(centerline),
        "wall_candidate_count": len(wall_scope.records),
        "axis_candidate_count": len(axis_rows),
        "left_termination_count": len(left),
        "right_termination_count": len(right),
        "spanning_count": len(spanning),
        "left_candidates": sorted(
            left, key=lambda row: (abs(row["offset"]), row["id"])
        )[:30],
        "right_candidates": sorted(
            right, key=lambda row: (abs(row["offset"]), row["id"])
        )[:30],
        "spanning_candidates": sorted(
            spanning, key=lambda row: (abs(row["offset"]), row["id"])
        )[:30],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
