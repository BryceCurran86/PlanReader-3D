from __future__ import annotations

from collections import Counter
import json

import cv2
import fitz
import numpy as np

from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _sheet() -> np.ndarray:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    radius = 160
    cv2.line(gray, (240, 164), (240, 324), 0, 1)
    cv2.ellipse(
        gray,
        center=(240, 164),
        axes=(radius, radius),
        angle=0,
        startAngle=0,
        endAngle=90,
        color=0,
        thickness=1,
    )
    return gray


def _pdf(gray: np.ndarray) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _run(name: str, gray: np.ndarray) -> dict:
    source = SourceVisibilityProducer(
        producer_method=f"diag-raster-swing-{name}",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-raster-swing-{name}",
        source_bytes=_pdf(gray),
        source_locator=f"memory://diag-raster-swing-{name}.pdf",
        page_ids=("1",),
    )
    placements = source.raster_opening_image_placements(
        published.revision.revision_id,
        "1",
    )
    scale = source.raster_opening_registration_scale(
        published.revision.revision_id,
        "1",
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )

    visibility = source.authority()
    authority = source.physical_opening_authority()
    kinds = Counter()
    records = []
    failures = []
    first_result = None
    for observation_id in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        resolved = visibility.resolve_raster_opening_primitive(selector)
        if resolved.observation is not None:
            kinds[resolved.observation.observation_kind] += 1
        if first_result is None:
            first_result = resolved

    candidates = ()
    scoped_candidates = ()
    if first_result is not None and first_result.observation is not None:
        records, failures = authority._raster_primitive_snapshot_records(first_result)
        candidates = authority._raster_framed_candidates_for(
            first_result.observation,
            records,
        )
        scoped_candidates = authority._viewport_scoped_raster_candidates_for(
            first_result.observation,
            records,
            candidates,
        )

    result_records = {}
    statuses = Counter()
    reasons = Counter()
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        statuses[result.status.value] += 1
        for reason in result.reason_codes:
            reasons[str(reason)] += 1
        if result.existence_record is not None:
            result_records[result.existence_record.record_id] = {
                "pattern": result.existence_record.structural_pattern,
                "bbox": result.existence_record.aperture_bbox_pt,
            }

    return {
        "name": name,
        "shape": list(gray.shape),
        "placements": [
            {
                "bbox_pt": list(item.bbox_pt),
                "pixel_width": item.pixel_width,
                "pixel_height": item.pixel_height,
            }
            for item in placements
        ],
        "registration_scale": None if scale is None else list(scale),
        "primitive_count": len(published.raster_opening_primitive_observation_ids),
        "primitive_kind_counts": dict(sorted(kinds.items())),
        "resolved_record_count": len(records),
        "primitive_failure_count": len(failures),
        "candidate_count": len(candidates),
        "candidate_patterns": Counter(
            candidate.structural_pattern for candidate in candidates
        ),
        "candidate_rows": [
            {
                "id": candidate.candidate_id,
                "pattern": candidate.structural_pattern,
                "bbox": authority._raster_candidate_gap_box_cache.get(
                    candidate.candidate_id
                ),
                "support_count": len(candidate.source_observation_ids),
            }
            for candidate in candidates
        ],
        "scoped_candidate_count": len(scoped_candidates),
        "existence_records": result_records,
        "status_counts": dict(sorted(statuses.items())),
        "reason_counts": dict(sorted(reasons.items())),
    }


def main() -> None:
    base = _sheet()
    rotated = np.ascontiguousarray(np.rot90(base))
    print(json.dumps({
        "base": _run("base", base),
        "rotated": _run("rotated", rotated),
    }, indent=2, sort_keys=True, default=lambda value: dict(value)))


if __name__ == "__main__":
    main()
