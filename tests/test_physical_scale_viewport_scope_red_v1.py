"""Independent viewport-scope red team for Physical Scale Authority V1.

TEST-ONLY / EXPECTED-RED / DO NOT MERGE.

This supplements #409.  It locks the missing proposition that a physical scale
must belong to the exact drawing viewport that consumes it; a genuine scale bar
elsewhere on the same PDF page is not page-global physical-scale authority.
"""
from __future__ import annotations

from dataclasses import fields
import importlib
import importlib.util

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    segment_page_viewports,
)

MODULE_NAME = "pb_physical_scale_authority"
HAS_PHYSICAL_SCALE_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_PHYSICAL_SCALE_AUTHORITY,
    strict=True,
    reason="producer-owned viewport-scoped physical scale authority is intentionally absent",
)


def _draw_frame(page, rect: fitz.Rect) -> None:
    shape = page.new_shape()
    shape.draw_rect(rect)
    shape.finish(width=1.0)
    shape.commit()


def _draw_scale_bar(
    page,
    *,
    x0: float,
    y: float,
    span_pt: float,
    end_label: str = "1m",
) -> None:
    x1 = x0 + span_pt
    shape = page.new_shape()
    shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
    shape.draw_line(fitz.Point(x0, y - 7.0), fitz.Point(x0, y + 7.0))
    shape.draw_line(fitz.Point(x1, y - 7.0), fitz.Point(x1, y + 7.0))
    shape.finish(width=1.0)
    shape.commit()
    page.insert_text(fitz.Point(x0 - 2.0, y + 22.0), "0")
    page.insert_text(fitz.Point(x1 - 4.0, y + 22.0), end_label)


def _two_viewport_pdf(*, right_has_bar: bool = True) -> bytes:
    """Two source-native framed viewports with intentionally different scales."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=620.0, height=360.0)
        left = fitz.Rect(25.0, 35.0, 290.0, 315.0)
        right = fitz.Rect(330.0, 35.0, 595.0, 315.0)
        _draw_frame(page, left)
        _draw_frame(page, right)

        # Titles are source-native and deliberately inside their governing frames.
        page.insert_text(fitz.Point(55.0, 65.0), "GROUND FLOOR PLAN")
        page.insert_text(fitz.Point(365.0, 65.0), "DETAIL A")

        # Left viewport: 100 pt represents 1 m => 0.1 pt/mm.
        _draw_scale_bar(page, x0=70.0, y=245.0, span_pt=100.0)
        # Right viewport: 50 pt represents 1 m => 0.05 pt/mm.
        if right_has_bar:
            _draw_scale_bar(page, x0=380.0, y=245.0, span_pt=50.0)

        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _resolved_viewports(payload: bytes):
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        viewports = segment_page_viewports(doc[0], page_number=1)
    finally:
        doc.close()
    resolved = [
        viewport
        for viewport in viewports
        if viewport.status == ViewportSegmentationStatus.RESOLVED.value
        and viewport.bounding_box is not None
    ]
    return sorted(resolved, key=lambda viewport: viewport.bounding_box[0])


def _source_fixture(payload: bytes):
    producer = SourceVisibilityProducer(
        producer_method="physical-scale-viewport-redteam",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="physical-scale-viewport-redteam-doc",
        source_bytes=payload,
        source_locator="memory://physical-scale-viewport-redteam.pdf",
    )
    return producer, published


def _selector(mod, published, viewport_id: str):
    selector_fields = {field.name for field in fields(mod.PhysicalScaleSelector)}
    scope_field = (
        "viewport_id"
        if "viewport_id" in selector_fields
        else "view_id"
        if "view_id" in selector_fields
        else None
    )
    assert scope_field is not None, (
        "PhysicalScaleSelector must carry the exact producer-owned viewport identity; "
        "page_id alone is insufficient on multi-scale sheets"
    )
    values = {
        "document_id": published.revision.document_id,
        "revision_id": published.revision.revision_id,
        "source_sha256": published.revision.source_sha256,
        "snapshot_id": published.snapshot.snapshot_id,
        "page_id": "1",
        scope_field: viewport_id,
    }
    return mod.PhysicalScaleSelector(**values)


def test_two_viewport_fixture_is_independently_resolved() -> None:
    """Keep the adversarial fixture honest even while production is absent."""
    viewports = _resolved_viewports(_two_viewport_pdf())
    assert len(viewports) == 2
    assert viewports[0].view_id != viewports[1].view_id
    assert viewports[0].bounding_box[2] < viewports[1].bounding_box[0]


@EXPECTED_RED
def test_future_physical_scale_selector_is_viewport_scoped_not_page_only() -> None:
    mod = importlib.import_module(MODULE_NAME)
    selector_fields = {field.name for field in fields(mod.PhysicalScaleSelector)}
    assert "page_id" in selector_fields
    assert {"viewport_id", "view_id"} & selector_fields


@EXPECTED_RED
def test_two_same_page_viewports_keep_distinct_physical_scale_mappings() -> None:
    mod = importlib.import_module(MODULE_NAME)
    payload = _two_viewport_pdf()
    viewports = _resolved_viewports(payload)
    assert len(viewports) == 2

    source, published = _source_fixture(payload)
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(source)

    left = producer.publish_scope(_selector(mod, published, viewports[0].view_id))
    right = producer.publish_scope(_selector(mod, published, viewports[1].view_id))

    assert left.status is EvidenceResolutionStatus.CORROBORATED
    assert right.status is EvidenceResolutionStatus.CORROBORATED
    assert left.evidence is not None
    assert right.evidence is not None
    assert abs(left.evidence.source_span_pt - 100.0) <= 1e-6
    assert abs(right.evidence.source_span_pt - 50.0) <= 1e-6
    assert abs(left.evidence.points_per_mm - 0.1) <= 1e-9
    assert abs(right.evidence.points_per_mm - 0.05) <= 1e-9
    assert left.evidence.points_per_mm != right.evidence.points_per_mm


@EXPECTED_RED
def test_scale_bar_in_other_viewport_cannot_be_reused_page_globally() -> None:
    mod = importlib.import_module(MODULE_NAME)
    payload = _two_viewport_pdf(right_has_bar=False)
    viewports = _resolved_viewports(payload)
    assert len(viewports) == 2

    source, published = _source_fixture(payload)
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(source)

    left = producer.publish_scope(_selector(mod, published, viewports[0].view_id))
    right = producer.publish_scope(_selector(mod, published, viewports[1].view_id))

    assert left.status is EvidenceResolutionStatus.CORROBORATED
    assert left.evidence is not None
    assert right.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert right.evidence is None
