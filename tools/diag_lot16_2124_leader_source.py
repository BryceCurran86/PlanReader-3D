from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _inside(point, bbox, tol=1e-6):
    x, y = point
    x0, y0, x1, y1 = bbox
    return x0 - tol <= x <= x1 + tol and y0 - tol <= y <= y1 + tol


def _point_bbox_distance(point, bbox):
    x, y = point
    x0, y0, x1, y1 = bbox
    dx = max(x0 - x, 0.0, x - x1)
    dy = max(y0 - y, 0.0, y - y1)
    return math.hypot(dx, dy)


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual_sha}")

    source = SourceVisibilityProducer(
        producer_method="diag_lot16_2124_leader_source",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="diag-lot16-2124-leader-source",
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

    semantic = composition.semantic_enumeration_result.record
    if semantic is None:
        raise SystemExit("semantic opening record unavailable")

    physical = composition.physical_opening_authority
    selectors = []
    openings = {}
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
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and record is not None
        ):
            selectors.append(selector)
            openings[record.record_id] = record

    if not openings:
        raise SystemExit("no physical openings")

    label_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    seed = next(iter(openings.values()))
    trusted_lines = label_producer._trusted_text_lines_for_opening(seed)
    target_lines = [
        line for line in trusted_lines
        if "2124" in line.text.replace(",", "")
    ]
    if not target_lines:
        raise SystemExit("2124 trusted source label unavailable")

    visibility = source.authority()
    segments = []
    for observation_id in published.visible_observation_ids:
        resolved = visibility.resolve_visible(ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        obs = resolved.observation
        if (
            resolved.status is not EvidenceResolutionStatus.CORROBORATED
            or obs is None
            or str(obs.page_id) != PAGE_ID
            or obs.observation_kind not in {
                NATIVE_PDF_VISIBLE_SEGMENT,
                RASTER_PDF_VISIBLE_SEGMENT,
            }
            or len(obs.geometry) != 4
        ):
            continue
        line = tuple(float(v) for v in obs.geometry)
        segments.append({
            "observation_id": obs.observation_id,
            "kind": obs.observation_kind,
            "primitive_ref": obs.source_primitive_ref,
            "line": line,
        })

    rows = []
    for label in target_lines:
        lb = tuple(float(v) for v in label.bbox)
        for segment in segments:
            x0, y0, x1, y1 = segment["line"]
            endpoints = ((x0, y0), (x1, y1))
            label_dist = min(_point_bbox_distance(point, lb) for point in endpoints)
            for opening in openings.values():
                bbox = opening.aperture_bbox_pt
                if bbox is None:
                    continue
                ob = tuple(float(v) for v in bbox)
                opening_dist = min(_point_bbox_distance(point, ob) for point in endpoints)
                direct = (
                    any(_inside(point, lb) for point in endpoints)
                    and any(_inside(point, ob) for point in endpoints)
                )
                rows.append({
                    "label_text": label.text,
                    "label_bbox": lb,
                    "opening_id": opening.record_id,
                    "opening_pattern": opening.structural_pattern,
                    "opening_bbox": ob,
                    "segment_observation_id": segment["observation_id"],
                    "segment_kind": segment["kind"],
                    "segment_primitive_ref": segment["primitive_ref"],
                    "segment_line": segment["line"],
                    "label_endpoint_distance_pt": label_dist,
                    "opening_endpoint_distance_pt": opening_dist,
                    "direct_endpoint_bridge": direct,
                })

    direct = [row for row in rows if row["direct_endpoint_bridge"]]
    closest = sorted(
        rows,
        key=lambda row: (
            row["label_endpoint_distance_pt"] + row["opening_endpoint_distance_pt"],
            row["label_endpoint_distance_pt"],
            row["opening_endpoint_distance_pt"],
            row["segment_observation_id"],
            row["opening_id"],
        ),
    )[:80]

    print(json.dumps({
        "source_sha256": actual_sha,
        "trusted_2124_label_count": len(target_lines),
        "trusted_2124_labels": [
            {"text": line.text, "bbox": list(line.bbox), "observation_ids": list(line.observation_ids)}
            for line in target_lines
        ],
        "physical_opening_count": len(openings),
        "visible_segment_count": len(segments),
        "direct_endpoint_bridge_count": len(direct),
        "direct_endpoint_bridges": direct,
        "closest_segment_opening_pairs": closest,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
