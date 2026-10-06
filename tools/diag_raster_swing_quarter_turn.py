from __future__ import annotations

from collections import Counter
import json

import cv2
import fitz
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def sheet() -> np.ndarray:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    radius = 160
    cv2.line(gray, (240, 164), (240, 324), 0, 1)
    cv2.ellipse(gray, (240, 164), (radius, radius), 0, 0, 90, 0, 1)
    return gray


def pdf(gray: np.ndarray) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(page.rect, stream=png(gray), keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def inspect(gray: np.ndarray, label: str) -> None:
    source = SourceVisibilityProducer(
        producer_method=f"diag-quarter-turn-{label}",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-quarter-turn-{label}",
        source_bytes=pdf(gray),
        source_locator=f"memory://{label}.pdf",
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
    kinds = Counter()
    authority = source.physical_opening_authority()
    statuses = Counter()
    reasons = Counter()
    records = {}
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
        statuses[str(getattr(result.status, "value", result.status))] += 1
        reasons.update(result.reason_codes)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            records[result.existence_record.record_id] = {
                "pattern": result.existence_record.structural_pattern,
                "bbox": result.existence_record.aperture_bbox_pt,
            }
    print(json.dumps({
        "label": label,
        "shape": list(gray.shape),
        "placements": [
            {
                "bbox_pt": list(p.bbox_pt),
                "pixel_width": p.pixel_width,
                "pixel_height": p.pixel_height,
            }
            for p in placements
        ],
        "page_registration_scale": scale,
        "primitive_count": len(published.raster_opening_primitive_observation_ids),
        "kinds": dict(kinds),
        "statuses": dict(statuses),
        "reasons": dict(reasons),
        "records": records,
    }, indent=2, sort_keys=True))


def main() -> None:
    original = sheet()
    inspect(original, "original")
    inspect(np.ascontiguousarray(np.rot90(original)), "rotated")


if __name__ == "__main__":
    main()
