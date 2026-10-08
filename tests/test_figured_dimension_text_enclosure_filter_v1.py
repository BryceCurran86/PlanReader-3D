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
    _tight_text_enclosure_path_indices,
    _without_dimension_text_enclosure_paths,
    bind_observation_to_vector_geometry,
    extract_dimension_evidence_bundle,
)


def _seg(
    segment_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    path: int,
) -> ObservedGeometrySegment:
    return ObservedGeometrySegment(
        segment_id=segment_id,
        source_page=1,
        start=start,
        end=end,
        view_id="V",
        source_path_index=path,
    )


def _observation() -> DimensionObservation:
    return DimensionObservation(
        dimension_id="dim",
        source_page=1,
        view_id="V",
        view_type=DrawingViewType.FLOOR_PLAN.value,
        bbox=(100.0, 90.0, 120.0, 110.0),
        raw_text="3400",
        value=3400.0,
        unit="mm",
        orientation=DimensionOrientation.UNKNOWN.value,
    )


def _calibration() -> DimensionLayoutCalibration:
    return DimensionLayoutCalibration(
        median_word_height_pt=20.0,
        line_search_distance_pt=40.0,
        witness_endpoint_distance_pt=12.0,
        chain_axis_tolerance_pt=5.0,
    )


def _tight_text_frame() -> tuple[ObservedGeometrySegment, ...]:
    return (
        _seg("frame-top", (100.0, 90.0), (120.0, 90.0), path=10),
        _seg("frame-right", (120.0, 90.0), (120.0, 110.0), path=10),
        _seg("frame-bottom", (120.0, 110.0), (100.0, 110.0), path=10),
        _seg("frame-left", (100.0, 110.0), (100.0, 90.0), path=10),
    )


def test_tight_text_frame_is_identified_from_one_native_path() -> None:
    excluded = _tight_text_enclosure_path_indices(
        _observation().bbox,
        _tight_text_frame(),
        _calibration(),
    )

    assert excluded == frozenset({10})


def test_tight_text_frame_cannot_mint_dimension_without_real_linework() -> None:
    result = bind_observation_to_vector_geometry(
        _observation(),
        _tight_text_frame(),
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.UNSUPPORTED.value
    assert result.dimension_line_id is None
    assert result.endpoints is None


def test_real_split_dimension_line_resolves_after_text_frame_is_removed() -> None:
    segments = (
        *_tight_text_frame(),
        _seg("dimension-left", (60.0, 100.0), (95.0, 100.0), path=20),
        _seg("dimension-right", (125.0, 100.0), (160.0, 100.0), path=21),
        _seg("left-witness", (60.0, 80.0), (60.0, 120.0), path=22),
        _seg("right-witness", (160.0, 80.0), (160.0, 120.0), path=23),
    )

    result = bind_observation_to_vector_geometry(
        _observation(),
        segments,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )

    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.dimension_line_id is not None
    assert "dimension-left" in result.dimension_line_id
    assert "dimension-right" in result.dimension_line_id
    assert result.witness_line_ids == ("left-witness", "right-witness")
    assert result.endpoints == ((60.0, 100.0), (160.0, 100.0))


def test_neighbor_dimension_text_frame_is_removed_from_binding_universe() -> None:
    own_frame = _tight_text_frame()
    neighbor_frame = (
        _seg("neighbor-top", (78.0, 90.0), (96.0, 90.0), path=50),
        _seg("neighbor-right", (96.0, 90.0), (96.0, 110.0), path=50),
        _seg("neighbor-bottom", (96.0, 110.0), (78.0, 110.0), path=50),
        _seg("neighbor-left", (78.0, 110.0), (78.0, 90.0), path=50),
    )
    real_geometry = (
        _seg("dimension-left", (60.0, 100.0), (95.0, 100.0), path=60),
        _seg("dimension-right", (125.0, 100.0), (160.0, 100.0), path=61),
        _seg("left-witness", (60.0, 80.0), (60.0, 120.0), path=62),
        _seg("right-witness", (160.0, 80.0), (160.0, 120.0), path=63),
    )
    segments = (*own_frame, *neighbor_frame, *real_geometry)

    filtered = _without_dimension_text_enclosure_paths(
        segments,
        (
            (100.0, 90.0, 120.0, 110.0),
            (78.0, 90.0, 96.0, 110.0),
        ),
        _calibration(),
    )

    remaining_ids = {segment.segment_id for segment in filtered}
    assert not any(segment_id.startswith("frame-") for segment_id in remaining_ids)
    assert not any(segment_id.startswith("neighbor-") for segment_id in remaining_ids)
    assert {segment.segment_id for segment in real_geometry} <= remaining_ids

    result = bind_observation_to_vector_geometry(
        _observation(),
        filtered,
        _calibration(),
        text_orientation_hint=DimensionOrientation.HORIZONTAL.value,
    )
    assert result.status == BindingStatus.WITNESS_BOUND.value
    assert result.witness_line_ids == ("left-witness", "right-witness")


def test_larger_rectangle_is_not_filtered_as_text_enclosure() -> None:
    large_box = (
        _seg("large-top", (70.0, 60.0), (150.0, 60.0), path=30),
        _seg("large-right", (150.0, 60.0), (150.0, 140.0), path=30),
        _seg("large-bottom", (150.0, 140.0), (70.0, 140.0), path=30),
        _seg("large-left", (70.0, 140.0), (70.0, 60.0), path=30),
    )

    excluded = _tight_text_enclosure_path_indices(
        _observation().bbox,
        large_box,
        _calibration(),
    )

    assert excluded == frozenset()


def test_distinct_paths_are_never_collapsed_into_one_text_frame() -> None:
    split_paths = (
        _seg("top", (100.0, 90.0), (120.0, 90.0), path=40),
        _seg("right", (120.0, 90.0), (120.0, 110.0), path=41),
        _seg("bottom", (120.0, 110.0), (100.0, 110.0), path=42),
        _seg("left", (100.0, 110.0), (100.0, 90.0), path=43),
    )

    excluded = _tight_text_enclosure_path_indices(
        _observation().bbox,
        split_paths,
        _calibration(),
    )

    assert excluded == frozenset()



def test_yearlike_number_requires_explicit_geometric_view_before_promotion() -> None:
    doc = fitz.open()
    try:
        page = doc.new_page(width=300.0, height=220.0)
        page.draw_line((60.0, 100.0), (180.0, 100.0), width=1.0)
        page.draw_line((60.0, 80.0), (60.0, 120.0), width=1.0)
        page.draw_line((180.0, 80.0), (180.0, 120.0), width=1.0)
        page.insert_text((110.0, 97.0), "2000", fontsize=10.0)
        payload = doc.tobytes()
    finally:
        doc.close()

    unknown_doc = fitz.open(stream=payload, filetype="pdf")
    try:
        unknown = extract_dimension_evidence_bundle(
            unknown_doc[0],
            page_num=1,
        )
    finally:
        unknown_doc.close()

    floor_doc = fitz.open(stream=payload, filetype="pdf")
    try:
        floor = extract_dimension_evidence_bundle(
            floor_doc[0],
            page_num=1,
            view_type=DrawingViewType.FLOOR_PLAN.value,
        )
    finally:
        floor_doc.close()

    assert not any(
        observation.raw_text == "2000"
        and observation.extraction_method == "native_text_witness_promoted"
        for observation in unknown.observations
    )
    promoted = [
        observation
        for observation in floor.observations
        if observation.raw_text == "2000"
        and observation.extraction_method == "native_text_witness_promoted"
    ]
    assert len(promoted) == 1
    binding = next(
        item
        for item in floor.bindings
        if item.observation_id == promoted[0].dimension_id
    )
    assert binding.status == BindingStatus.WITNESS_BOUND.value
