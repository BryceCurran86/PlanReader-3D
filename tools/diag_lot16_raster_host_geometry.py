from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_opening_host_binding_authority import _candidate_axis_data, _opening_geometry
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


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"source sha mismatch: {actual_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_host_geometry",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-host-geometry",
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

    wall_result = composition.physical_wall_candidate_authority.resolve_scope(
        PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=PAGE_ID,
            decision_scope_id=f"wall-source:page-{PAGE_ID}",
        )
    )
    assert wall_result.scope_complete is True

    semantic = composition.semantic_enumeration_result.record
    assert semantic is not None
    physical = composition.physical_opening_authority

    binding_by_opening = {
        str(trace.opening_identity_id): trace
        for trace in composition.opening_bindings
        if trace.opening_identity_id
    }

    raster_rows = []
    category_counts = Counter()
    seen = set()
    for observation_id in semantic.representative_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        record = result.existence_record
        if (
            result.proposition != PHYSICAL_OPENING_EXISTS
            or record is None
            or record.record_id in seen
            or record.structural_pattern != RASTER_FRAMED_WALL_BAND_INTERRUPTION
        ):
            continue
        seen.add(record.record_id)
        geometry = _opening_geometry(physical, record)
        if geometry is None:
            category_counts["raster_geometry_unavailable"] += 1
            continue

        axis_rows = []
        for wall_record in wall_result.records:
            data = _candidate_axis_data(wall_record, geometry)
            if data is None:
                continue
            along_min, along_max, offset = data
            axis_rows.append(
                (
                    wall_record.wall_candidate_id,
                    float(along_min),
                    float(along_max),
                    float(offset),
                )
            )

        edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
        left_exact = [
            row for row in axis_rows
            if row[1] < -edge_tol and abs(row[2]) <= edge_tol
        ]
        right_exact = [
            row for row in axis_rows
            if row[2] > geometry.length + edge_tol
            and abs(row[1] - geometry.length) <= edge_tol
        ]
        spanning = [
            row for row in axis_rows
            if row[1] < -edge_tol and row[2] > geometry.length + edge_tol
        ]
        centered_spanning = [
            row for row in spanning
            if abs(row[3]) <= max(2.0, geometry.thickness)
        ]
        left_errors = sorted(
            (
                abs(row[2]),
                abs(row[3]),
                row[0],
                row[1],
                row[2],
            )
            for row in axis_rows
            if row[1] < -edge_tol
        )
        right_errors = sorted(
            (
                abs(row[1] - geometry.length),
                abs(row[3]),
                row[0],
                row[1],
                row[2],
            )
            for row in axis_rows
            if row[2] > geometry.length + edge_tol
        )
        trace = binding_by_opening.get(record.record_id)
        reasons = tuple(trace.reason_codes) if trace is not None else ()
        if trace is not None and trace.host_wall_id:
            category = "host_bound"
        elif centered_spanning:
            category = "centered_whole_wall_spans_aperture"
        elif spanning:
            category = "off_center_whole_wall_spans_aperture"
        elif not axis_rows:
            category = "no_axis_compatible_wall_candidates"
        elif not left_exact and not right_exact:
            category = "wall_edges_do_not_terminate_at_aperture"
        elif not left_exact:
            category = "missing_left_termination"
        elif not right_exact:
            category = "missing_right_termination"
        else:
            category = "edge_candidates_exist_but_binding_failed"
        category_counts[category] += 1

        raster_rows.append(
            {
                "opening_id": record.record_id,
                "bbox": record.aperture_bbox_pt,
                "length": geometry.length,
                "thickness": geometry.thickness,
                "binding_status": None if trace is None else trace.status.value,
                "binding_reasons": list(reasons),
                "host_wall_id": None if trace is None else trace.host_wall_id,
                "category": category,
                "axis_candidate_count": len(axis_rows),
                "left_exact_count": len(left_exact),
                "right_exact_count": len(right_exact),
                "spanning_count": len(spanning),
                "centered_spanning_count": len(centered_spanning),
                "nearest_left": left_errors[:5],
                "nearest_right": right_errors[:5],
                "centered_spanning": centered_spanning[:10],
            }
        )

    print(json.dumps(
        {
            "source_sha256": actual_sha,
            "wall_candidate_count": len(wall_result.records),
            "raster_framed_opening_count": len(raster_rows),
            "category_counts": dict(sorted(category_counts.items())),
            "rows": raster_rows,
        },
        indent=2,
        sort_keys=True,
    ))


if __name__ == "__main__":
    main()
