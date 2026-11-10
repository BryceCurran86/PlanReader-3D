from __future__ import annotations

import cv2
import fitz
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_schedule_opening_instance_binding_authority import (
    BINDING_NO_CONTAINED_TAG,
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SCOPE = "raster-schedule-binding:page-1"


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _raster_wall() -> np.ndarray:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    cv2.line(gray, (240, 154), (400, 154), 0, 1)
    cv2.line(gray, (240, 160), (400, 160), 0, 1)
    return gray


def _pdf(*, tag_x: float) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=400.0)
        page.insert_image(
            fitz.Rect(0.0, 0.0, 320.0, 180.0),
            stream=_png(_raster_wall()),
            keep_proportion=False,
        )
        # The sealed aperture is approximately x=120..200, y=75..82 pt.
        # Baseline 81 keeps the D1 text centroid inside that wall band.
        page.insert_text(fitz.Point(tag_x, 81.0), "D1", fontsize=7.0)

        # Independent source schedule on the same page. Geometry is far from
        # the opening and can never participate in G17 existence.
        for text, x in zip(("MARK", "WIDTH", "HEIGHT"), (20.0, 100.0, 180.0)):
            page.insert_text(fitz.Point(x, 250.0), text, fontsize=8.0)
        for text, x in zip(("D1", "900", "2100"), (20.0, 100.0, 180.0)):
            page.insert_text(fitz.Point(x, 280.0), text, fontsize=8.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _prepare(*, tag_x: float):
    source = SourceVisibilityProducer(
        producer_method="raster-schedule-binding-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="raster-schedule-binding",
        source_bytes=_pdf(tag_x=tag_x),
        source_locator="memory://raster-schedule-binding.pdf",
        page_ids=("1",),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    physical = source.physical_opening_authority()

    found = {}
    selectors = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = result.existence_record
            selectors.setdefault(result.existence_record.record_id, selector)

    assert len(found) == 1
    opening_id = next(iter(found))
    return source, selectors[opening_id], found[opening_id]


def test_raster_opening_binds_contained_explicit_tag_to_schedule() -> None:
    source, selector, opening = _prepare(tag_x=150.0)
    assert opening.aperture_bbox_pt is not None

    result = (
        ScheduleOpeningInstanceBindingProducer
        .from_source_visibility_producer(source)
        .publish_scope(
            opening_selector=selector,
            decision_scope_id=SCOPE,
        )
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.opening_record_id == opening.record_id
    assert result.record.tag_mark == "D1"
    assert result.record.schedule_row_type_mark == "D1"
    assert result.record.schedule_row_width_mm == 900
    assert result.record.schedule_row_height_mm == 2100


def test_raster_schedule_tag_outside_sealed_aperture_stays_unbound() -> None:
    source, selector, _opening = _prepare(tag_x=225.0)

    result = (
        ScheduleOpeningInstanceBindingProducer
        .from_source_visibility_producer(source)
        .publish_scope(
            opening_selector=selector,
            decision_scope_id=SCOPE,
        )
    )

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert BINDING_NO_CONTAINED_TAG in result.reason_codes
