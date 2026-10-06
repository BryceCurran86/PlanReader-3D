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


def state(value) -> str:
    return str(getattr(value, "value", value))


def result_dict(result) -> dict:
    return {
        "status": state(result.status),
        "reason_codes": list(result.reason_codes),
        "bands": [
            {
                "member_ids": list(band.member_ids),
                "member_candidate_identity_ids": list(band.member_candidate_identity_ids),
                "member_equivalence_groups": [list(x) for x in band.member_equivalence_groups],
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
        indices = tuple(range(int(doc.page_count)))
    scope = source_floor_plan_topology_scope(PDF, indices)
    topology_indices = tuple(scope.topology_page_indices() or ()) if scope else indices
    topology_page_ids = tuple(str(i + 1) for i in topology_indices)
    all_page_ids = tuple(str(i + 1) for i in indices)
    evidence_page_ids = tuple(p for p in all_page_ids if p not in topology_page_ids)

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_area_ready_hosts_after_safe_semantics",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-area-ready-hosts-after-safe-semantics",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=all_page_ids,
    )
    wall = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=topology_page_ids,
        evidence_page_ids=evidence_page_ids,
    )
    voids = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall,
    )
    current = source.published_snapshot_for_revision(published.revision.revision_id)
    assert current is not None

    ready = [
        opening
        for opening in voids.canonical_openings
        if str(opening.opening_kind or "").strip().lower() in {"door", "window"}
        and opening.area_m2 is not None
        and not str(opening.host_wall_id or "").strip()
    ]

    semantic = wall.semantic_enumeration_result.record
    assert semantic is not None
    physical = wall.physical_opening_authority
    existence_by_id = {}
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
        if result.existence_record is not None:
            existence_by_id[result.existence_record.record_id] = result.existence_record

    binding_by_id = {
        str(row.opening_identity_id): row
        for row in wall.opening_bindings
        if row.opening_identity_id
    }

    rows = []
    for target in sorted(ready, key=lambda item: item.physical_opening_id):
        existence = existence_by_id.get(target.physical_opening_id)
        if existence is None:
            continue
        page_id = str(existence.page_id)
        wall_scope = wall.physical_wall_candidate_authority.resolve_scope(
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
            rows.append({
                "physical_opening_id": target.physical_opening_id,
                "opening_kind": target.opening_kind,
                "area_m2": target.area_m2,
                "area_basis": target.area_basis,
                "wall_scope_complete": wall_scope.scope_complete,
                "wall_scope_status": state(wall_scope.status),
                "wall_scope_reason_codes": list(wall_scope.reason_codes),
            })
            continue
        geometry = host._opening_geometry(physical, existence)
        if geometry is None:
            continue
        split = host._resolve_host_bands(
            wall_scope.records, geometry, wall_scope.equivalence
        )
        whole = host._resolve_raster_whole_wall_host(
            wall_scope.records, geometry, wall_scope.equivalence
        )
        center = host._resolve_raster_split_centerline_host(
            wall_scope.records, geometry, wall_scope.equivalence
        )
        current_binding = binding_by_id.get(target.physical_opening_id)
        rows.append({
            "physical_opening_id": target.physical_opening_id,
            "page_id": page_id,
            "structural_pattern": target.structural_pattern,
            "opening_kind": target.opening_kind,
            "area_m2": target.area_m2,
            "area_basis": target.area_basis,
            "figured_area_record_id": target.figured_area_record_id,
            "aperture_bbox_pt": existence.aperture_bbox_pt,
            "current_binding": None if current_binding is None else {
                "status": state(current_binding.status),
                "reason_codes": list(current_binding.reason_codes),
                "host_wall_id": current_binding.host_wall_id,
            },
            "split_face": result_dict(split),
            "whole_wall": result_dict(whole),
            "split_centerline": result_dict(center),
        })

    print(json.dumps({
        "source_sha256": source_sha,
        "topology_page_ids": list(topology_page_ids),
        "area_ready_unhosted_count": len(ready),
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
