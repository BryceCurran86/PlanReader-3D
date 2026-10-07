from __future__ import annotations

import fitz

from pb_dimension_graph_constraint_engine import (
    DimensionObservation,
    DimensionOrientation,
)
from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionLayoutCalibration,
    ObservedGeometrySegment,
    _dimension_text_box_source_items,
    _native_word_orientations,
    bind_observation_to_vector_geometry,
)


def _segment(
    segment_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    width: float | None,
    color: tuple[float, float, float] | None,
    source_path_index: int | None = None,
    source_item_index: int | None = None,
) -> ObservedGeometrySegment:
    return ObservedGeometrySegment(
        segment_id=segment_id,
        source_page=1,
        start=start,
        end=end,
        view_id="V",
        source_path_index=source_path_index,
        source_item_index=source_item_index,
        stroke_width_pt=width,
        stroke_color_rgb=color,
    )


def _observation(*, orientation: str) -> DimensionObservation:
    return DimensionObservation(
        dimension_id="dim",
        source_page=1,
        view_id="V",
        view_type=DrawingViewType.FLOOR_PLAN.value,
        bbox=(101.0, 90.0, 111.0, 110.0),
        raw_text="2400",
        value=2400.0,
        unit="mm",
        orientation=orientation,
    )


def _calibration() -> DimensionLayoutCalibration:
    return DimensionLayoutCalibration(
        median_word_height_pt=20.0,
        line_search_distance_pt=40.0,
        witness_endpoint_distance_pt=12.0,
        chain_axis_tolerance_pt=5.0,
    )


def test_native_text_line_direction_is_available_as_binder_hint() -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.insert_text((80, 120), "3100", fontsize=10)
    page.insert_text((180, 220), "4200", fontsize=10, rotate=90)
    payload = doc.tobytes()
    doc.close()

    reopened = fitz.open(stream=payload, filetype="pdf")
    try:
        page = reopened[0]
        words = list(page.get_text("words") or ())
        orientations = _native_word_orientations(page)
        by_text = {
            str(word[4]): orientations.get((int(word[5]), int(word[6])))
            for word in words
            if str(word[4]) in {"3100", "4200"}
        }
    finally:
        reopened.close()

    assert by_text["3100"] == DimensionOrientation.HORIZONTAL.value
    assert by_text["4200"] == DimensionOrientation.VERTICAL.value


def test_single_orientation_hint_cannot_hide_perpendicular_competitor() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "horizontal",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "vertical",
            (106.0, 70.0),
            (106.0, 130.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.AMBIGUOUS.value
    assert result.endpoints is None


def test_darker_thicker_source_line_breaks_only_a_near_tie() -> None:
    observation = _observation(orientation=DimensionOrientation.VERTICAL.value)
    segments = (
        _segment(
            "background-grid",
            (102.0, 40.0),
            (102.0, 160.0),
            width=0.24,
            color=(0.5, 0.5, 0.5),
        ),
        _segment(
            "dimension-line",
            (106.0, 60.0),
            (106.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "top-witness",
            (94.0, 60.0),
            (116.0, 60.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "bottom-witness",
            (94.0, 140.0),
            (116.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "dimension-line"
    assert set(result.witness_line_ids) == {"top-witness", "bottom-witness"}


def test_equal_source_style_stays_ambiguous() -> None:
    observation = _observation(orientation=DimensionOrientation.VERTICAL.value)
    segments = (
        _segment(
            "left",
            (102.0, 60.0),
            (102.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "right",
            (106.0, 60.0),
            (106.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "top-witness",
            (94.0, 60.0),
            (116.0, 60.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "bottom-witness",
            (94.0, 140.0),
            (116.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
    )

    assert result.status == BindingStatus.AMBIGUOUS.value
    assert result.endpoints is None


def test_horizontal_text_can_fall_back_when_only_vertical_geometry_exists() -> None:
    observation = _observation(orientation=DimensionOrientation.HORIZONTAL.value)
    segments = (
        _segment(
            "dimension-line",
            (106.0, 60.0),
            (106.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "top-witness",
            (94.0, 60.0),
            (116.0, 60.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "bottom-witness",
            (94.0, 140.0),
            (116.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "dimension-line"


def test_endpoint_witness_selection_prefers_actual_line_end_over_nearby_annotation_edge() -> None:
    observation = _observation(orientation=DimensionOrientation.VERTICAL.value)
    calibration = DimensionLayoutCalibration(
        median_word_height_pt=20.0,
        line_search_distance_pt=40.0,
        witness_endpoint_distance_pt=30.0,
        chain_axis_tolerance_pt=5.0,
    )
    segments = (
        _segment(
            "dimension-line",
            (106.0, 60.0),
            (106.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "nearby-annotation-edge",
            (94.0, 42.0),
            (116.0, 42.0),
            width=None,
            color=None,
        ),
        _segment(
            "top-witness",
            (94.0, 60.0),
            (116.0, 60.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "bottom-witness",
            (94.0, 140.0),
            (116.0, 140.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        calibration,
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.witness_line_ids == ("top-witness", "bottom-witness")
    assert result.endpoints == ((106.0, 60.0), (106.0, 140.0))



def test_unique_native_orientation_with_two_endpoint_witnesses_breaks_perpendicular_tie() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "horizontal-dimension",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "vertical-competitor",
            (106.0, 70.0),
            (106.0, 130.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "left-witness",
            (80.0, 82.0),
            (80.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "right-witness",
            (132.0, 82.0),
            (132.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "horizontal-dimension"
    assert result.witness_line_ids == ("left-witness", "right-witness")
    assert result.endpoints == ((80.0, 100.0), (132.0, 100.0))


def test_native_orientation_with_only_one_endpoint_witness_stays_ambiguous() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "horizontal-dimension",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "vertical-competitor",
            (106.0, 70.0),
            (106.0, 130.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "left-witness",
            (80.0, 82.0),
            (80.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.AMBIGUOUS.value
    assert result.dimension_line_id is None
    assert result.endpoints is None


def test_two_same_orientation_witness_complete_candidates_stay_ambiguous() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "horizontal-a",
            (80.0, 98.0),
            (132.0, 98.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "horizontal-b",
            (80.0, 102.0),
            (132.0, 102.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "left-witness",
            (80.0, 80.0),
            (80.0, 120.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "right-witness",
            (132.0, 80.0),
            (132.0, 120.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.AMBIGUOUS.value
    assert result.dimension_line_id is None
    assert result.endpoints is None


def test_unique_span_bracketing_witness_candidate_breaks_same_orientation_tie() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "full-dimension",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "short-competitor",
            (100.0, 102.0),
            (112.0, 102.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "full-left-witness",
            (80.0, 82.0),
            (80.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "full-right-witness",
            (132.0, 82.0),
            (132.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "short-left-witness",
            (100.0, 88.0),
            (100.0, 116.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "full-dimension"
    assert result.witness_line_ids == (
        "full-left-witness",
        "full-right-witness",
    )
    assert result.endpoints == ((80.0, 100.0), (132.0, 100.0))


def test_existing_strict_style_winner_is_not_vetoed_by_new_orientation_fallback() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "historical-style-winner",
            (106.0, 60.0),
            (106.0, 140.0),
            width=0.60,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "orientation-fallback",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.24,
            color=(0.6, 0.6, 0.6),
        ),
        _segment(
            "vertical-top-witness",
            (94.0, 60.0),
            (116.0, 60.0),
            width=0.60,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "vertical-bottom-witness",
            (94.0, 140.0),
            (116.0, 140.0),
            width=0.60,
            color=(0.0, 0.0, 0.0),
        ),
        _segment(
            "horizontal-left-witness",
            (80.0, 82.0),
            (80.0, 118.0),
            width=0.24,
            color=(0.6, 0.6, 0.6),
        ),
        _segment(
            "horizontal-right-witness",
            (132.0, 82.0),
            (132.0, 118.0),
            width=0.24,
            color=(0.6, 0.6, 0.6),
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "historical-style-winner"
    assert set(result.witness_line_ids) == {
        "vertical-top-witness",
        "vertical-bottom-witness",
    }


def test_fragmented_source_path_competitors_do_not_block_unique_bracketing_dimension() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "dimension-line",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=100,
        ),
        _segment(
            "fragment-a",
            (100.0, 98.0),
            (112.0, 98.0),
            width=None,
            color=None,
            source_path_index=200,
        ),
        _segment(
            "fragment-b",
            (100.0, 102.0),
            (112.0, 102.0),
            width=None,
            color=None,
            source_path_index=200,
        ),
        _segment(
            "left-witness",
            (80.0, 82.0),
            (80.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=101,
        ),
        _segment(
            "right-witness",
            (132.0, 82.0),
            (132.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=102,
        ),
        _segment(
            "fragment-left",
            (100.0, 86.0),
            (100.0, 114.0),
            width=None,
            color=None,
            source_path_index=200,
        ),
        _segment(
            "fragment-right",
            (112.0, 86.0),
            (112.0, 114.0),
            width=None,
            color=None,
            source_path_index=200,
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "dimension-line"


def test_two_distinct_complete_source_paths_remain_ambiguous_even_if_one_brackets_text() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    segments = (
        _segment(
            "bracketing-dimension",
            (80.0, 100.0),
            (132.0, 100.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=300,
        ),
        _segment(
            "other-complete-dimension",
            (100.0, 102.0),
            (118.0, 102.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=400,
        ),
        _segment(
            "a-left",
            (80.0, 82.0),
            (80.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=301,
        ),
        _segment(
            "a-right",
            (132.0, 82.0),
            (132.0, 118.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=302,
        ),
        _segment(
            "b-left",
            (100.0, 88.0),
            (100.0, 116.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=401,
        ),
        _segment(
            "b-right",
            (118.0, 88.0),
            (118.0, 116.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=402,
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.AMBIGUOUS.value
    assert result.dimension_line_id is None


def _text_box_rectangle_segments(
    *,
    path_index: int,
    item_index: int,
    bbox: tuple[float, float, float, float],
) -> tuple[ObservedGeometrySegment, ...]:
    x0, y0, x1, y1 = bbox
    return (
        _segment(
            "box-e0",
            (x0, y0),
            (x1, y0),
            width=None,
            color=None,
            source_path_index=path_index,
            source_item_index=item_index,
        ),
        _segment(
            "box-e1",
            (x1, y0),
            (x1, y1),
            width=None,
            color=None,
            source_path_index=path_index,
            source_item_index=item_index,
        ),
        _segment(
            "box-e2",
            (x1, y1),
            (x0, y1),
            width=None,
            color=None,
            source_path_index=path_index,
            source_item_index=item_index,
        ),
        _segment(
            "box-e3",
            (x0, y1),
            (x0, y0),
            width=None,
            color=None,
            source_path_index=path_index,
            source_item_index=item_index,
        ),
    )


def test_native_rectangle_tightly_boxing_dimension_text_is_not_a_line_candidate() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    self_box = _text_box_rectangle_segments(
        path_index=500,
        item_index=0,
        bbox=observation.bbox,
    )
    segments = (
        *self_box,
        _segment(
            "real-dimension-line",
            (80.0, 120.0),
            (132.0, 120.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=501,
            source_item_index=0,
        ),
        _segment(
            "real-left-witness",
            (80.0, 108.0),
            (80.0, 132.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=502,
            source_item_index=0,
        ),
        _segment(
            "real-right-witness",
            (132.0, 108.0),
            (132.0, 132.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=503,
            source_item_index=0,
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id == "real-dimension-line"
    assert result.witness_line_ids == (
        "real-left-witness",
        "real-right-witness",
    )


def test_larger_native_rectangle_is_not_suppressed_as_dimension_text_box() -> None:
    observation = _observation(orientation=DimensionOrientation.UNKNOWN.value)
    larger_box = _text_box_rectangle_segments(
        path_index=600,
        item_index=0,
        bbox=(80.0, 85.0, 140.0, 115.0),
    )
    segments = (
        *larger_box,
        _segment(
            "real-dimension-line",
            (80.0, 120.0),
            (132.0, 120.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=601,
            source_item_index=0,
        ),
        _segment(
            "real-left-witness",
            (80.0, 108.0),
            (80.0, 132.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=602,
            source_item_index=0,
        ),
        _segment(
            "real-right-witness",
            (132.0, 108.0),
            (132.0, 132.0),
            width=0.48,
            color=(0.0, 0.0, 0.0),
            source_path_index=603,
            source_item_index=0,
        ),
    )

    result = bind_observation_to_vector_geometry(
        observation,
        segments,
        _calibration(),
    )

    assert result.status == BindingStatus.AMBIGUOUS.value
    assert result.dimension_line_id is None


def test_page_scope_suppresses_adjacent_dimension_text_boxes_independently() -> None:
    first = DimensionObservation(
        dimension_id="dim-a",
        source_page=1,
        bbox=(100.0, 90.0, 112.0, 100.0),
        raw_text="4200",
        value=4200.0,
        unit="mm",
    )
    second = DimensionObservation(
        dimension_id="dim-b",
        source_page=1,
        bbox=(100.0, 110.0, 112.0, 120.0),
        raw_text="4200",
        value=4200.0,
        unit="mm",
    )
    first_box = _text_box_rectangle_segments(
        path_index=700,
        item_index=0,
        bbox=first.bbox,
    )
    second_box = tuple(
        _segment(
            f"second-{segment.segment_id}",
            segment.start,
            segment.end,
            width=None,
            color=None,
            source_path_index=701,
            source_item_index=0,
        )
        for segment in _text_box_rectangle_segments(
            path_index=701,
            item_index=0,
            bbox=second.bbox,
        )
    )
    unrelated = _text_box_rectangle_segments(
        path_index=702,
        item_index=0,
        bbox=(60.0, 60.0, 160.0, 150.0),
    )

    ignored = _dimension_text_box_source_items(
        (first, second),
        (*first_box, *second_box, *unrelated),
        _calibration(),
    )

    assert ignored == frozenset({(700, 0), (701, 0)})
