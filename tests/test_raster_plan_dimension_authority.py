from __future__ import annotations

from dataclasses import replace
import io

import fitz
from PIL import Image, ImageDraw
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine
from pb_raster_plan_dimension_authority import (
    BoundRasterDimension,
    RasterDimensionTextObservation,
    RasterPlanDimensionProducer,
    _RECORD_SEAL,
    _VisibleSegment,
    _bind_text_to_geometry,
    _resolve_overall,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _text(
    value: int,
    bbox: tuple[float, float, float, float],
    *,
    obs_id: str = "txt",
) -> RasterDimensionTextObservation:
    return RasterDimensionTextObservation(
        observation_id=obs_id,
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        page_id="1",
        parent_page_observation_id="page",
        raw_text=str(value),
        value_mm=value,
        bbox_pt=bbox,
        backend_name="mock",
        backend_version="1",
        confidence=1.0,
        _seal=_RECORD_SEAL,
    )


def _seg(
    obs_id: str,
    geometry: tuple[float, float, float, float],
    orientation: str,
) -> _VisibleSegment:
    return _VisibleSegment(obs_id, geometry, orientation)


def _bound(
    dim_id: str,
    value: int,
    orientation: str,
    start: float,
    end: float,
    *,
    axis: float = 10.0,
) -> BoundRasterDimension:
    endpoints = (
        ((start, axis), (end, axis))
        if orientation == "horizontal"
        else ((axis, start), (axis, end))
    )
    return BoundRasterDimension(
        dimension_id=dim_id,
        text_observation_id=f"txt-{dim_id}",
        value_mm=value,
        orientation=orientation,
        endpoints_pt=endpoints,
        span_pt=abs(end - start),
        dimension_line_observation_ids=(f"line-{dim_id}",),
        witness_observation_ids=(f"w0-{dim_id}", f"w1-{dim_id}"),
        _seal=_RECORD_SEAL,
    )


def test_unique_line_and_two_witnesses_bind():
    text = _text(10000, (45.0, 8.0, 55.0, 12.0))
    segments = (
        _seg("line", (0.0, 10.0, 100.0, 10.0), "horizontal"),
        _seg("left", (0.0, 0.0, 0.0, 20.0), "vertical"),
        _seg("right", (100.0, 0.0, 100.0, 20.0), "vertical"),
    )
    result = _bind_text_to_geometry(text, segments)
    assert result is not None
    assert result.value_mm == 10000
    assert result.orientation == "horizontal"
    assert result.span_pt == 100.0
    assert result.dimension_line_observation_ids == ("line",)


def test_text_split_line_fragments_bind_as_one_logical_line():
    text = _text(10000, (45.0, 8.0, 55.0, 12.0))
    segments = (
        _seg("a", (0.0, 10.0, 44.0, 10.0), "horizontal"),
        _seg("b", (56.0, 10.0, 100.0, 10.0), "horizontal"),
        _seg("left", (0.0, 0.0, 0.0, 20.0), "vertical"),
        _seg("right", (100.0, 0.0, 100.0, 20.0), "vertical"),
    )
    result = _bind_text_to_geometry(text, segments)
    assert result is not None
    assert set(result.dimension_line_observation_ids) == {"a", "b"}
    assert result.span_pt == 100.0


def test_third_competing_line_keeps_binding_ambiguous():
    text = _text(10000, (45.0, 8.0, 55.0, 12.0))
    segments = (
        _seg("a", (0.0, 10.0, 44.0, 10.0), "horizontal"),
        _seg("b", (56.0, 10.0, 100.0, 10.0), "horizontal"),
        _seg("competing", (0.0, 11.0, 100.0, 11.0), "horizontal"),
        _seg("left", (0.0, 0.0, 0.0, 20.0), "vertical"),
        _seg("right", (100.0, 0.0, 100.0, 20.0), "vertical"),
    )
    assert _bind_text_to_geometry(text, segments) is None


def test_missing_or_competing_witnesses_fail_closed():
    text = _text(10000, (45.0, 8.0, 55.0, 12.0))
    missing = (
        _seg("line", (0.0, 10.0, 100.0, 10.0), "horizontal"),
        _seg("left", (0.0, 0.0, 0.0, 20.0), "vertical"),
    )
    assert _bind_text_to_geometry(text, missing) is None

    competing = (
        _seg("line", (0.0, 10.0, 100.0, 10.0), "horizontal"),
        _seg("left-a", (-0.9, 0.0, -0.9, 20.0), "vertical"),
        _seg("left-b", (0.9, 0.0, 0.9, 20.0), "vertical"),
        _seg("right", (100.0, 0.0, 100.0, 20.0), "vertical"),
    )
    assert _bind_text_to_geometry(text, competing) is None


def test_overall_requires_exact_contiguous_child_sum():
    overall = _bound("overall", 10000, "horizontal", 0.0, 100.0)
    first = _bound("first", 4000, "horizontal", 0.0, 40.0)
    second = _bound("second", 6000, "horizontal", 40.0, 100.0)
    result = _resolve_overall("horizontal", (second, overall, first))
    assert result is not None
    assert result.value_mm == 10000
    assert result.child_values_mm == (4000, 6000)

    wrong = replace(second, value_mm=5900)
    assert _resolve_overall("horizontal", (overall, first, wrong)) is None


def test_multiple_distinct_child_decompositions_are_ambiguous():
    overall = _bound("overall", 10000, "horizontal", 0.0, 100.0)
    a = _bound("a", 4000, "horizontal", 0.0, 40.0)
    b = _bound("b", 6000, "horizontal", 40.0, 100.0)
    c = _bound("c", 5000, "horizontal", 0.0, 50.0)
    d = _bound("d", 5000, "horizontal", 50.0, 100.0)
    assert _resolve_overall("horizontal", (overall, a, b, c, d)) is None


def test_record_constructors_reject_caller_forgery():
    with pytest.raises(TypeError):
        RasterDimensionTextObservation(
            observation_id="x",
            document_id="doc",
            revision_id="rev",
            source_sha256="a" * 64,
            snapshot_id="snap",
            page_id="1",
            parent_page_observation_id="page",
            raw_text="1000",
            value_mm=1000,
            bbox_pt=(0, 0, 1, 1),
            backend_name="caller",
            backend_version="caller",
            confidence=1.0,
        )


def _image_only_dimension_pdf() -> bytes:
    width_pt, height_pt = 360, 200
    scale = 2
    image = Image.new("RGB", (width_pt * scale, height_pt * scale), "white")
    draw = ImageDraw.Draw(image)
    line_w = 3

    def h(x0, y, x1):
        draw.line(
            (x0 * scale, y * scale, x1 * scale, y * scale),
            fill="black",
            width=line_w,
        )

    def v(x, y0, y1):
        draw.line(
            (x * scale, y0 * scale, x * scale, y1 * scale),
            fill="black",
            width=line_w,
        )

    # Horizontal overall 10m and 5m + 5m child chain.
    h(40, 30, 240)
    v(40, 24, 36)
    v(240, 24, 36)
    h(40, 60, 140)
    v(40, 54, 66)
    v(140, 54, 66)
    h(140, 80, 240)
    v(140, 74, 86)
    v(240, 74, 86)

    # Vertical overall 5m and 2.5m + 2.5m child chain. Adjacent members are
    # deliberately placed on separate drafting tracks so the raster detector
    # does not collapse them into one continuous physical line.
    v(280, 30, 130)
    h(274, 30, 286)
    h(274, 130, 286)
    v(310, 30, 80)
    h(304, 30, 316)
    h(304, 80, 316)
    v(330, 80, 130)
    h(324, 80, 336)
    h(324, 130, 336)

    buf = io.BytesIO()
    image.save(buf, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=width_pt, height=height_pt)
    page.insert_image(page.rect, stream=buf.getvalue(), keep_proportion=False)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ocr(text: str, bbox: tuple[float, float, float, float]) -> OCRLine:
    return OCRLine(text=text, confidence=1.0, bbox_px=bbox, bbox_pt=bbox)


def test_end_to_end_producer_resolves_only_source_owned_orthogonal_chains():
    source = SourceVisibilityProducer(
        producer_method="raster-dimension-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-raster-dims",
        source_bytes=_image_only_dimension_pdf(),
        source_locator="memory://synthetic-raster-dims.pdf",
    )

    backend = MockOCRBackend(
        (
            _ocr("10000", (125.0, 26.0, 155.0, 34.0)),
            _ocr("5000", (75.0, 56.0, 105.0, 64.0)),
            _ocr("5000", (175.0, 76.0, 205.0, 84.0)),
            _ocr("5000", (276.0, 68.0, 284.0, 92.0)),
            _ocr("2500", (306.0, 44.0, 314.0, 66.0)),
            _ocr("2500", (326.0, 94.0, 334.0, 116.0)),
        )
    )
    producer = RasterPlanDimensionProducer.create_for_tests(
        source_visibility=source,
        backend=backend,
    )
    result = producer.publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.length_m == 10.0
    assert result.width_m == 5.0
    assert result.horizontal is not None
    assert result.horizontal.child_values_mm == (5000, 5000)
    assert result.vertical is not None
    assert result.vertical.child_values_mm == (2500, 2500)
    assert result.scale_status == "provisional"
    assert result.quantity_m2 is None

    replay = producer.publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    assert replay == result


def test_producer_scale_conflict_fails_closed():
    source = SourceVisibilityProducer(
        producer_method="raster-dimension-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-raster-dims-conflict",
        source_bytes=_image_only_dimension_pdf(),
        source_locator="memory://synthetic-raster-dims-conflict.pdf",
    )

    # Same source geometry, but the vertical figured chain claims only 4m.
    # Both child values sum correctly; the orthogonal scale reconciliation is
    # what must reject the inconsistent system.
    backend = MockOCRBackend(
        (
            _ocr("10000", (125.0, 26.0, 155.0, 34.0)),
            _ocr("5000", (75.0, 56.0, 105.0, 64.0)),
            _ocr("5000", (175.0, 76.0, 205.0, 84.0)),
            _ocr("4000", (276.0, 68.0, 284.0, 92.0)),
            _ocr("2000", (306.0, 44.0, 314.0, 66.0)),
            _ocr("2000", (326.0, 94.0, 334.0, 116.0)),
        )
    )
    result = RasterPlanDimensionProducer.create_for_tests(
        source_visibility=source,
        backend=backend,
    ).publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.length_m is None
    assert result.width_m is None
    assert result.scale_status == "conflicting"
    assert result.quantity_m2 is None
