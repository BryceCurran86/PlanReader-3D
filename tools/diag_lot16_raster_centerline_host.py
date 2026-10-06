from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
import pb_opening_host_binding_authority as host
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, RASTER_FRAMED_WALL_BAND_INTERRUPTION
from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SOURCE_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def main() -> None:
    payload = PDF.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != EXPECTED_SOURCE_SHA:
        raise SystemExit(f"source sha mismatch: {sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_raster_centerline_host",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-raster-centerline-host",
        source_bytes=payload,
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

    semantic = composition.semantic_enumeration_result.record
    assert semantic is not None
    physical = composition.physical_opening_authority

    summary = Counter()
    rows = []
    seen = set()
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
        opening = result.existence_record
        if (
            result.proposition != PHYSICAL_OPENING_EXISTS
            or opening is None
            or opening.record_id in seen
            or opening.structural_pattern != RASTER_FRAMED_WALL_BAND_INTERRUPTION
        ):
            continue
        seen.add(opening.record_id)
        geometry = host._opening_geometry(physical, opening)
        assert geometry is not None
        edge_tol = max(0.5, min(2.0, geometry.length * 0.02))
        thickness_tol = max(0.75, geometry.thickness * 0.15)
        center_tol = max(host.DEFAULT_GAP_SNAP_TOLERANCE_PT, thickness_tol)

        raw = []
        for record in walls.records:
            data = host._candidate_axis_data(record, geometry)
            if data is None:
                continue
            u0, u1, offset = data
            if not (u0 < -edge_tol and u1 > geometry.length + edge_tol):
                continue
            identity = record.physical_identity
            if not identity.usable or not identity.candidate_identity_id:
                continue
            raw.append((record, float(u0), float(u1), float(offset)))

        by_group = {}
        for record, u0, u1, offset in raw:
            group = tuple(group_lookup.get(record.wall_candidate_id, (record.wall_candidate_id,)))
            by_group.setdefault(group, []).append((record, u0, u1, offset))

        normalized = []
        for group, members in sorted(by_group.items()):
            selected = sorted(
                members,
                key=lambda item: (abs(item[3]), item[0].wall_candidate_id),
            )[0]
            normalized.append((group, *selected))

        centered = [
            (group, record, u0, u1, offset)
            for group, record, u0, u1, offset in normalized
            if abs(offset) <= center_tol
        ]
        if len(centered) == 1:
            category = "unique_centerline_host_candidate"
        elif len(centered) > 1:
            category = "multiple_centerline_host_candidates"
        else:
            category = "no_centerline_host_candidate"
        summary[category] += 1

        rows.append({
            "opening_id": opening.record_id,
            "bbox": opening.aperture_bbox_pt,
            "length": geometry.length,
            "thickness": geometry.thickness,
            "center_tol": center_tol,
            "normalized_spanning_count": len(normalized),
            "centered_count": len(centered),
            "centered": [
                {
                    "id": record.wall_candidate_id,
                    "offset": offset,
                    "u0": u0,
                    "u1": u1,
                    "group": list(group),
                    "representation": record.wall_candidate.representation,
                    "reason_codes": list(record.wall_candidate.reason_codes),
                    "source_primitive_ids": list(record.physical_identity.source_primitive_ids),
                }
                for group, record, u0, u1, offset in centered
            ],
            "category": category,
        })

    print(json.dumps({
        "source_sha256": sha,
        "wall_candidate_count": len(walls.records),
        "raster_opening_count": len(rows),
        "summary": dict(sorted(summary.items())),
        "rows": rows,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
