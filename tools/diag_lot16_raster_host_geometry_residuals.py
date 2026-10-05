from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def main() -> None:
    source_bytes = PDF.read_bytes()
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    if source_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"source sha mismatch: {source_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_host_geometry_residuals",
        producer_version="1",
    )
    initial = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-host-geometry-residuals",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=initial.revision.revision_id,
        page_ids=(PAGE_ID,),
    )
    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    assert published is not None

    binding_by_opening = {
        trace.opening_identity_id: trace
        for trace in composition.opening_bindings
        if trace.opening_identity_id
    }

    rows = []
    seen = set()
    wall_scope_cache = {}
    semantic = composition.semantic_enumeration_result.record
    representatives = (
        tuple(semantic.representative_observation_ids)
        if semantic is not None
        else ()
    )
    physical = composition.physical_opening_authority
    wall_authority = composition.physical_wall_candidate_authority

    for observation_id in representatives:
        result = physical.prove_existence(_selector(published, observation_id))
        opening = result.existence_record
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or result.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
            or opening.structural_pattern != RASTER_FRAMED_WALL_BAND_INTERRUPTION
            or opening.record_id in seen
        ):
            continue
        seen.add(opening.record_id)

        binding_selector = composition.binding_selectors.get(opening.record_id)
        trace = binding_by_opening.get(opening.record_id)
        geometry = host._opening_geometry(physical, opening)
        if binding_selector is None or geometry is None:
            rows.append({
                "opening_id": opening.record_id,
                "status": "missing_selector_or_geometry",
                "binding_reasons": [] if trace is None else list(trace.reason_codes),
            })
            continue

        scope_key = (
            binding_selector.document_id,
            binding_selector.revision_id,
            binding_selector.source_sha256,
            binding_selector.snapshot_id,
            binding_selector.page_id,
            binding_selector.decision_scope_id,
        )
        wall_scope = wall_scope_cache.get(scope_key)
        if wall_scope is None:
            wall_scope = wall_authority.resolve_scope(
                PhysicalWallCandidateSelector(
                    document_id=binding_selector.document_id,
                    revision_id=binding_selector.revision_id,
                    source_sha256=binding_selector.source_sha256,
                    snapshot_id=binding_selector.snapshot_id,
                    page_id=binding_selector.page_id,
                    decision_scope_id=binding_selector.decision_scope_id,
                )
            )
            wall_scope_cache[scope_key] = wall_scope
        edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
        parallel = []
        left = []
        right = []
        for record in wall_scope.records:
            data = host._candidate_axis_data(record, geometry)
            if data is None:
                continue
            along_min, along_max, offset = data
            parallel.append((record.wall_candidate_id, along_min, along_max, offset))
            if along_min < 0.0:
                left.append((abs(along_max), record.wall_candidate_id, along_min, along_max, offset))
            if along_max > geometry.length:
                right.append((abs(along_min - geometry.length), record.wall_candidate_id, along_min, along_max, offset))

        left.sort()
        right.sort()
        old_left = [row for row in left if row[0] <= edge_tol]
        old_right = [row for row in right if row[0] <= edge_tol]
        resolution = host._resolve_host_bands(
            wall_scope.records,
            geometry,
            wall_scope.equivalence,
        )

        rows.append({
            "opening_id": opening.record_id,
            "aperture_bbox_pt": list(opening.aperture_bbox_pt or ()),
            "length_pt": geometry.length,
            "thickness_pt": geometry.thickness,
            "edge_tol_pt": edge_tol,
            "wall_scope_status": wall_scope.status.value,
            "wall_scope_complete": bool(wall_scope.scope_complete),
            "wall_candidate_count": len(wall_scope.records),
            "parallel_candidate_count": len(parallel),
            "old_left_role_count": len(old_left),
            "old_right_role_count": len(old_right),
            "closest_left_endpoint_residuals_pt": [
                {
                    "residual": row[0],
                    "wall_id": row[1],
                    "along_min": row[2],
                    "along_max": row[3],
                    "offset": row[4],
                }
                for row in left[:8]
            ],
            "closest_right_endpoint_residuals_pt": [
                {
                    "residual": row[0],
                    "wall_id": row[1],
                    "along_min": row[2],
                    "along_max": row[3],
                    "offset": row[4],
                }
                for row in right[:8]
            ],
            "binding_status": None if trace is None else trace.status.value,
            "binding_reasons": [] if trace is None else list(trace.reason_codes),
            "direct_band_status": resolution.status.value,
            "direct_band_reasons": list(resolution.reason_codes),
            "direct_band_count": len(resolution.bands),
        })

    payload = {
        "source_sha256": source_sha,
        "page_id": PAGE_ID,
        "raster_opening_count": len(rows),
        "rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
