from __future__ import annotations

from dataclasses import replace
import io

import fitz
from PIL import Image, ImageDraw
import pytest

from pb_figured_dimension_evidence import (
    calibrate_dimension_layout_from_word_heights,
)
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
    _text_orientation_candidates,
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
    *,
    width: float | None = None,
    color: tuple[float, float, float] | None = None,
) -> _VisibleSegment:
    return _VisibleSegment(
        obs_id,
        geometry,
        orientation,
        stroke_width_pt=width,
        stroke_color_rgb=color,
    )


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


def test_strict_native_style_breaks_same_orientation_logical_line_tie():
    text = _text(4025, (98.0, 80.0, 102.0, 120.0))
    segments = (
        _seg(
            "background",
            (96.0, 20.0, 96.0, 180.0),
            "vertical",
            width=0.24,
            color=(0.5, 0.5, 0.5),
        ),
        _seg(
            "dimension",
            (100.0, 20.0, 100.0, 180.0),
            "vertical",
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _seg(
            "top",
            (90.0, 20.0, 110.0, 20.0),
            "horizontal",
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _seg(
            "bottom",
            (90.0, 180.0, 110.0, 180.0),
            "horizontal",
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = _bind_text_to_geometry(text, segments)

    assert result is not None
    assert result.value_mm == 4025
    assert result.orientation == "vertical"
    assert result.dimension_line_observation_ids == ("dimension",)
    assert set(result.witness_observation_ids) == {"top", "bottom"}


def test_equal_or_missing_native_style_keeps_logical_line_tie_ambiguous():
    text = _text(4025, (98.0, 80.0, 102.0, 120.0))
    equal = (
        _seg(
            "left",
            (96.0, 20.0, 96.0, 180.0),
            "vertical",
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _seg(
            "right",
            (100.0, 20.0, 100.0, 180.0),
            "vertical",
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )
    assert _bind_text_to_geometry(text, equal) is None

    missing = (
        _seg("left", (96.0, 20.0, 96.0, 180.0), "vertical"),
        _seg(
            "right",
            (100.0, 20.0, 100.0, 180.0),
            "vertical",
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )
    assert _bind_text_to_geometry(text, missing) is None


def test_source_typography_calibration_accepts_normal_dimension_extension_gap():
    text = _text(9385, (84.0, 8.0, 88.0, 12.0))
    segments = (
        # The visible dimension line begins 24 pt inboard of the left witness,
        # matching a normal extension/arrow drafting gap seen on real CAD plans.
        _seg("line", (24.0, 10.0, 100.0, 10.0), "horizontal"),
        _seg("left", (0.0, 0.0, 0.0, 20.0), "vertical"),
        _seg("right", (100.0, 0.0, 100.0, 20.0), "vertical"),
    )
    calibration = calibrate_dimension_layout_from_word_heights((16.913818359375,))

    result = _bind_text_to_geometry(
        text,
        segments,
        calibration=calibration,
    )

    assert result is not None
    assert result.value_mm == 9385
    assert result.endpoints_pt == ((0.0, 10.0), (100.0, 10.0))
    assert set(result.witness_observation_ids) == {"left", "right"}


def test_extension_gap_still_fails_without_source_derived_calibration():
    text = _text(9385, (84.0, 8.0, 88.0, 12.0))
    segments = (
        _seg("line", (24.0, 10.0, 100.0, 10.0), "horizontal"),
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



def test_strong_ocr_bbox_orientation_is_positive_but_square_stays_ambiguous():
    assert _text_orientation_candidates((0.0, 0.0, 30.0, 8.0)) == ("horizontal",)
    assert _text_orientation_candidates((0.0, 0.0, 8.0, 30.0)) == ("vertical",)
    assert _text_orientation_candidates((0.0, 0.0, 12.0, 12.0)) == (
        "horizontal",
        "vertical",
    )


def test_tall_dimension_text_does_not_promote_perpendicular_witness_ticks():
    text = _text(2500, (306.0, 44.0, 314.0, 66.0))
    segments = (
        _seg("dimension", (310.0, 30.0, 310.0, 80.0), "vertical"),
        _seg("top_witness", (304.5, 30.0, 316.5, 30.0), "horizontal"),
        _seg("bottom_witness", (304.5, 80.0, 316.5, 80.0), "horizontal"),
    )

    result = _bind_text_to_geometry(text, segments)

    assert result is not None
    assert result.orientation == "vertical"
    assert result.value_mm == 2500
    assert result.span_pt == 50.0
    assert result.dimension_line_observation_ids == ("dimension",)
    assert set(result.witness_observation_ids) == {"top_witness", "bottom_witness"}


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


def _native_style_tie_pdf(*, equal_style: bool = False) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    weak_color = (0.0, 0.0, 0.0) if equal_style else (0.5, 0.5, 0.5)
    weak_width = 2.0 if equal_style else 1.0

    page.draw_line(
        fitz.Point(96.0, 20.0),
        fitz.Point(96.0, 180.0),
        color=weak_color,
        width=weak_width,
    )
    page.draw_line(
        fitz.Point(100.0, 20.0),
        fitz.Point(100.0, 180.0),
        color=(0.0, 0.0, 0.0),
        width=2.0,
    )
    page.draw_line(
        fitz.Point(90.0, 20.0),
        fitz.Point(110.0, 20.0),
        color=(0.0, 0.0, 0.0),
        width=2.0,
    )
    page.draw_line(
        fitz.Point(90.0, 180.0),
        fitz.Point(110.0, 180.0),
        color=(0.0, 0.0, 0.0),
        width=2.0,
    )
    payload = doc.tobytes()
    doc.close()
    return payload


def _vector_only_dimension_pdf(*, rotation: int = 0) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=360, height=200)

    def h(x0, y, x1):
        page.draw_line(
            fitz.Point(x0, y),
            fitz.Point(x1, y),
            color=(0, 0, 0),
            width=1.0,
        )

    def v(x, y0, y1):
        page.draw_line(
            fitz.Point(x, y0),
            fitz.Point(x, y1),
            color=(0, 0, 0),
            width=1.0,
        )

    # Same orthogonal dimension system as the raster fixture, but every witness
    # and dimension line is native vector source geometry.
    h(40, 30, 240)
    v(40, 24, 36)
    v(240, 24, 36)
    h(40, 60, 140)
    v(40, 54, 66)
    v(140, 54, 66)
    h(140, 80, 240)
    v(140, 74, 86)
    v(240, 74, 86)

    v(280, 30, 130)
    h(274, 30, 286)
    h(274, 130, 286)
    v(310, 30, 80)
    h(304, 30, 316)
    h(304, 80, 316)
    v(330, 80, 130)
    h(324, 80, 336)
    h(324, 130, 336)

    if rotation:
        page.set_rotation(rotation)
    payload = doc.tobytes()
    doc.close()
    return payload


def _display_bbox_90(
    native_bbox: tuple[float, float, float, float],
    *,
    native_height: float = 200.0,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = native_bbox
    return (
        native_height - y1,
        x0,
        native_height - y0,
        x1,
    )


def _ocr(text: str, bbox: tuple[float, float, float, float]) -> OCRLine:
    return OCRLine(text=text, confidence=1.0, bbox_px=bbox, bbox_pt=bbox)


# This exercises style recovery from the producer-owned native page cache,
# not caller-supplied _VisibleSegment metadata.
def test_end_to_end_producer_uses_verified_native_style_to_break_line_tie():
    source = SourceVisibilityProducer(
        producer_method="native-style-dimension-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-native-style-dimension",
        source_bytes=_native_style_tie_pdf(),
        source_locator="memory://synthetic-native-style-dimension.pdf",
    )
    backend = MockOCRBackend(
        (_ocr("4025", (98.0, 80.0, 102.0, 120.0)),)
    )

    result = RasterPlanDimensionProducer.create_for_tests(
        source_visibility=source,
        backend=backend,
    ).publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )

    matches = [
        item for item in result.bound_dimensions if item.value_mm == 4025
    ]
    assert len(matches) == 1
    assert matches[0].orientation == "vertical"
    assert len(matches[0].witness_observation_ids) >= 2


def test_end_to_end_equal_native_style_remains_unbound():
    source = SourceVisibilityProducer(
        producer_method="native-style-equal-dimension-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-native-style-equal-dimension",
        source_bytes=_native_style_tie_pdf(equal_style=True),
        source_locator="memory://synthetic-native-style-equal-dimension.pdf",
    )
    backend = MockOCRBackend(
        (_ocr("4025", (98.0, 80.0, 102.0, 120.0)),)
    )

    result = RasterPlanDimensionProducer.create_for_tests(
        source_visibility=source,
        backend=backend,
    ).publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )

    assert not any(
        item.value_mm == 4025 for item in result.bound_dimensions
    )


def test_end_to_end_producer_can_bind_ocr_to_native_visible_dimension_geometry():
    source = SourceVisibilityProducer(
        producer_method="native-vector-raster-dimension-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-native-vector-dims",
        source_bytes=_vector_only_dimension_pdf(),
        source_locator="memory://synthetic-native-vector-dims.pdf",
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

    result = RasterPlanDimensionProducer.create_for_tests(
        source_visibility=source,
        backend=backend,
    ).publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.length_m == 10.0
    assert result.width_m == 5.0
    assert result.horizontal is not None
    assert result.vertical is not None
    assert result.horizontal.child_values_mm == (5000, 5000)
    assert result.vertical.child_values_mm == (2500, 2500)
    assert result.quantity_m2 is None
    assert result.bound_dimensions
    # The binding evidence comes from producer-owned visible source observations;
    # no caller geometry or scale is introduced by this path.
    assert all(
        dimension.dimension_line_observation_ids
        and dimension.witness_observation_ids
        for dimension in result.bound_dimensions
    )


def test_rotated_page_ocr_bounds_are_derotated_before_native_vector_binding():
    source = SourceVisibilityProducer(
        producer_method="rotated-native-vector-raster-dimension-test",
        producer_version="1.0",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="synthetic-rotated-native-vector-dims",
        source_bytes=_vector_only_dimension_pdf(rotation=90),
        source_locator="memory://synthetic-rotated-native-vector-dims.pdf",
    )

    native_boxes = (
        ("10000", (125.0, 26.0, 155.0, 34.0)),
        ("5000", (75.0, 56.0, 105.0, 64.0)),
        ("5000", (175.0, 76.0, 205.0, 84.0)),
        ("5000", (276.0, 68.0, 284.0, 92.0)),
        ("2500", (306.0, 44.0, 314.0, 66.0)),
        ("2500", (326.0, 94.0, 334.0, 116.0)),
    )
    backend = MockOCRBackend(
        tuple(
            _ocr(text, _display_bbox_90(bbox))
            for text, bbox in native_boxes
        )
    )

    result = RasterPlanDimensionProducer.create_for_tests(
        source_visibility=source,
        backend=backend,
    ).publish(
        revision_id=published.revision.revision_id,
        page_id="1",
    )

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.length_m == 10.0
    assert result.width_m == 5.0
    assert result.horizontal is not None
    assert result.vertical is not None
    assert result.horizontal.child_values_mm == (5000, 5000)
    assert result.vertical.child_values_mm == (2500, 2500)
    assert result.quantity_m2 is None


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
