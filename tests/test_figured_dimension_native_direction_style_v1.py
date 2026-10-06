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
) -> ObservedGeometrySegment:
    return ObservedGeometrySegment(
        segment_id=segment_id,
        source_page=1,
        start=start,
        end=end,
        view_id="V",
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
