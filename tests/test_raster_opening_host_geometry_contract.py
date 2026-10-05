from __future__ import annotations

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import _opening_geometry
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _source_pdf() -> bytes:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    cv2.line(gray, (240, 154), (400, 154), 0, 1)
    cv2.line(gray, (240, 160), (400, 160), 0, 1)

    doc = fitz.open()
    page = doc.new_page(width=320.0, height=180.0)
    page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _opening():
    producer = SourceVisibilityProducer(
        producer_method="raster-host-geometry-contract",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="raster-host-geometry-contract",
        source_bytes=_source_pdf(),
        source_locator="memory://raster-host-geometry-contract.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    authority = producer.physical_opening_authority()

    proven = {}
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
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            proven[result.existence_record.record_id] = result.existence_record

    assert len(proven) == 1
    return authority, next(iter(proven.values()))


def test_raster_host_geometry_uses_g17_proven_aperture_bbox() -> None:
    """EXPECTED RED until host geometry explicitly supports the raster pattern."""

    authority, opening = _opening()
    assert opening.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    assert opening.aperture_bbox_pt is not None

    geometry = _opening_geometry(authority, opening)
    assert geometry is not None
    assert geometry.axis == pytest.approx((1.0, 0.0), abs=1e-9)
    assert geometry.normal == pytest.approx((0.0, 1.0), abs=1e-9)
    assert geometry.length == pytest.approx(80.0, abs=1.0)
    assert geometry.thickness == pytest.approx(7.5, abs=1.0)
