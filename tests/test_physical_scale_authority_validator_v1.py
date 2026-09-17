"""Physical scale authority V1 validator foundation.

TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / NOT FROZEN / DO NOT MERGE.

Current production-safe text-scale helpers must remain fail-closed.  The future
sealed physical-scale authority may become positive only from authenticated
source-native graphic scale-bar geometry plus explicit physical labels.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect

import fitz
import pytest

from pb_geometry_takeoff_model import AuthorityStatus, ScaleCalibration
from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    ScaleCalibrationStatus,
    ScaleSourceType,
    measurement_authority_for_page_scale,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_scale_binding import bind_viewport_scale
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportBoundarySource,
    ViewportSegmentationStatus,
)

MODULE_NAME = "pb_physical_scale_authority"
HAS_PHYSICAL_SCALE_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_PHYSICAL_SCALE_AUTHORITY,
    strict=True,
    reason="producer-owned source-native FIRM physical scale authority is intentionally absent",
)

_FORBIDDEN_PUBLIC = {
    "px_per_m", "points_per_m", "points_per_mm", "mm_per_point",
    "conversion_factor", "ratio", "scale_ratio", "denominator", "scale_text",
    "calibration", "scale_calibration", "viewport_scale_binding", "is_verified",
    "status", "measurement_authority", "firm", "confidence", "source_type",
    "complete", "claimed_complete", "count", "fingerprint", "nearest", "first",
    "radius", "graphic_scale_bar", "bar_start", "bar_end", "labelled_length",
}


def _graphic_scale_pdf(
    bars: tuple[tuple[float, str], ...] = ((100.0, "1m"),),
    *,
    ratio_text: str | None = None,
) -> bytes:
    """Real native PDF vectors + native text, not mocked scale evidence."""
    doc = fitz.open()
    try:
        page = doc.new_page(width=500.0, height=360.0)
        for index, (span_pt, end_label) in enumerate(bars):
            y = 90.0 + index * 100.0
            x0 = 60.0
            x1 = x0 + float(span_pt)
            shape = page.new_shape()
            shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
            shape.draw_line(fitz.Point(x0, y - 8.0), fitz.Point(x0, y + 8.0))
            shape.draw_line(fitz.Point(x1, y - 8.0), fitz.Point(x1, y + 8.0))
            shape.finish(width=1.0)
            shape.commit()
            page.insert_text(fitz.Point(x0 - 2.0, y + 24.0), "0")
            page.insert_text(fitz.Point(x1 - 4.0, y + 24.0), end_label)
        if ratio_text:
            page.insert_text(fitz.Point(300.0, 40.0), ratio_text)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _source_fixture(payload: bytes):
    producer = SourceVisibilityProducer(
        producer_method="physical-scale-validator",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="physical-scale-validator-doc",
        source_bytes=payload,
        source_locator="memory://physical-scale-validator.pdf",
    )
    return producer, published


def _selector(mod, published):
    return mod.PhysicalScaleSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
    )


def test_title_block_only_scale_remains_provisional_not_firm() -> None:
    calibration = ScaleCalibration(
        page_no=1,
        ratio_str="1:100",
        px_per_m=28.346456692913385,
        method="TITLE_BLOCK",
        is_verified=True,
        confidence=1.0,
        source_type=ScaleSourceType.TITLE_BLOCK.value,
        status=ScaleCalibrationStatus.VALID.value,
        revision_id="rev-1",
    )
    assert measurement_authority_for_page_scale(calibration) == AuthorityStatus.PROVISIONAL.value


def test_viewport_text_scale_is_not_promoted_to_firm() -> None:
    viewport = SegmentedViewport(
        view_id="vp-1",
        page_number=1,
        view_type="floor_plan",
        label="GROUND FLOOR PLAN SCALE 1:100",
        title_bbox=(10.0, 10.0, 150.0, 25.0),
        bounding_box=(0.0, 0.0, 500.0, 500.0),
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source=ViewportBoundarySource.VECTOR_FRAME.value,
        confidence=1.0,
        scale_raw="SCALE 1:100",
        scale_denominator=100.0,
    )
    binding = bind_viewport_scale(
        viewport,
        page_no=1,
        revision_id="rev-1",
        sheet_label="A101",
        source_sha256="sha-1",
    )
    assert binding.measurement_authority != AuthorityStatus.FIRM.value
    assert binding.abstained is True
    assert "scale_not_firm" in binding.blocking_reasons


def test_plain_scale_calibration_is_constructible_and_therefore_not_a_sealed_source_proposition() -> None:
    calibration = ScaleCalibration(
        page_no=99,
        ratio_str="1:1",
        px_per_m=999999.0,
        method="CALLER",
        is_verified=True,
        confidence=1.0,
        source_type=ScaleSourceType.SCALE_BAR.value,
        status=ScaleCalibrationStatus.VALID.value,
    )
    assert calibration.is_usable_for_firm_measurement() is True
    assert is_dataclass(calibration)


@EXPECTED_RED
def test_future_physical_scale_api_is_sealed_and_selector_only() -> None:
    mod = importlib.import_module(MODULE_NAME)
    required = {
        "PhysicalScaleSelector",
        "PhysicalScaleEvidence",
        "PhysicalScaleResult",
        "PhysicalScaleAuthority",
        "PhysicalScaleProducer",
    }
    assert required <= set(dir(mod))
    assert is_dataclass(mod.PhysicalScaleSelector)
    selector_fields = {field.name for field in fields(mod.PhysicalScaleSelector)}
    assert not (selector_fields & _FORBIDDEN_PUBLIC)
    for callable_obj in (
        mod.PhysicalScaleProducer.publish_scope,
        mod.PhysicalScaleAuthority.resolve,
    ):
        assert not (set(inspect.signature(callable_obj).parameters) & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_future_scale_producer_does_not_accept_caller_calibration_or_ratio_truth() -> None:
    mod = importlib.import_module(MODULE_NAME)
    params = set(inspect.signature(mod.PhysicalScaleProducer.publish_scope).parameters)
    assert params <= {"self", "selector"}
    assert not (params & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_native_graphic_scale_bar_with_explicit_1m_label_may_publish_firm_mapping() -> None:
    """A self-contained graphic bar is the narrow positive route; no ratio text is needed."""
    mod = importlib.import_module(MODULE_NAME)
    src, published = _source_fixture(_graphic_scale_pdf())
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(src)
    selector = _selector(mod, published)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.source_kind == "native_graphic_scale_bar"
    assert abs(result.evidence.source_span_pt - 100.0) <= 1e-6
    assert result.evidence.physical_span_mm == 1000.0
    assert abs(result.evidence.points_per_mm - 0.1) <= 1e-9
    assert abs(result.evidence.mm_per_point - 10.0) <= 1e-9
    assert producer.authority().resolve(selector) == result


@EXPECTED_RED
def test_text_ratio_without_native_graphic_bar_cannot_publish_physical_scale() -> None:
    mod = importlib.import_module(MODULE_NAME)
    doc = fitz.open()
    try:
        page = doc.new_page(width=400.0, height=250.0)
        page.insert_text(fitz.Point(60.0, 80.0), "SCALE 1:100")
        payload = bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()
    src, published = _source_fixture(payload)
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(src)
    selector = _selector(mod, published)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


@EXPECTED_RED
def test_conflicting_native_graphic_bars_fail_closed() -> None:
    mod = importlib.import_module(MODULE_NAME)
    src, published = _source_fixture(
        _graphic_scale_pdf(bars=((100.0, "1m"), (100.0, "500mm")))
    )
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(src)
    selector = _selector(mod, published)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None


@EXPECTED_RED
def test_graphic_bar_conflicting_with_same_page_ratio_text_fails_closed() -> None:
    """Adding contradictory explicit scale evidence must never preserve FIRM authority."""
    mod = importlib.import_module(MODULE_NAME)
    src, published = _source_fixture(
        _graphic_scale_pdf(bars=((100.0, "1m"),), ratio_text="SCALE 1:100")
    )
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(src)
    selector = _selector(mod, published)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None


@EXPECTED_RED
def test_graphic_bar_agreeing_with_same_page_ratio_text_preserves_mapping() -> None:
    """Corroborating ratio text may agree with, but cannot replace, source-native bar geometry."""
    mod = importlib.import_module(MODULE_NAME)
    span_pt = POINTS_PER_METRE_AT_1_1 / 100.0
    src, published = _source_fixture(
        _graphic_scale_pdf(bars=((span_pt, "1m"),), ratio_text="SCALE 1:100")
    )
    producer = mod.PhysicalScaleProducer.from_source_visibility_producer(src)
    selector = _selector(mod, published)
    result = producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert abs(result.evidence.source_span_pt - span_pt) <= 1e-6
    assert result.evidence.physical_span_mm == 1000.0
    assert abs(result.evidence.points_per_mm - span_pt / 1000.0) <= 1e-9
    assert abs(result.evidence.mm_per_point - 1000.0 / span_pt) <= 1e-9


@EXPECTED_RED
def test_future_scale_authority_capabilities_are_narrow() -> None:
    mod = importlib.import_module(MODULE_NAME)
    capabilities = mod.PhysicalScaleProducer.capabilities()
    assert capabilities["source_native_graphic_scale_bar"] is True
    assert capabilities["title_block_text_can_mint_firm"] is False
    assert capabilities["caller_calibration_can_mint_firm"] is False
    assert capabilities["inferred_scale_can_mint_firm"] is False
