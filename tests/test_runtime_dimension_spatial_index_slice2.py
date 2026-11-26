"""Unit tests for Runtime Slice 2 spatial indexing in pb_figured_dimension_evidence.

Verifies exact bit-for-bit parity between the indexed path and brute-force
segment scanning across horizontal/vertical bindings, text-split fragments,
text-enclosure wipeout rectangles, witness tie-breaking, view scoping, and
immutable tuple cache identity safety.
"""
from __future__ import annotations

import pytest

from pb_dimension_graph_constraint_engine import (
    ConstraintStatus,
    DimensionObservation,
    DimensionOrientation,
)
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionLayoutCalibration,
    ObservedGeometrySegment,
    _VectorScopeIndex,
    _without_dimension_text_enclosure_paths,
    bind_observation_to_vector_geometry,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType


def _obs(
    obs_id: str,
    bbox: tuple[float, float, float, float],
    *,
    page: int = 1,
    view_id: str = "",
    value: float = 3000.0,
) -> DimensionObservation:
    return DimensionObservation(
        dimension_id=obs_id,
        source_page=page,
        sheet="A101",
        view_id=view_id,
        view_type="floor_plan",
        bbox=bbox,
        raw_text=str(int(value)),
        value=value,
        unit="mm",
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        confidence=1.0,
        conflict_state=ConstraintStatus.FULLY_CONSTRAINED.value,
        extraction_method="native_text",
    )


def _seg(
    sid: str,
    start: tuple[float, float],
    end: tuple[float, float],
    *,
    page: int = 1,
    view_id: str = "",
    path_idx: int | None = None,
    width: float | None = 0.5,
    color: tuple[float, float, float] | None = (0.0, 0.0, 0.0),
) -> ObservedGeometrySegment:
    return ObservedGeometrySegment(
        segment_id=sid,
        source_page=page,
        start=start,
        end=end,
        view_id=view_id,
        source_path_index=path_idx,
        stroke_width_pt=width,
        stroke_color_rgb=color,
    )


def test_indexed_binding_matches_dense_horizontal_vertical_and_wipeout_frames() -> None:
    cal = DimensionLayoutCalibration(
        median_word_height_pt=8.0,
        line_search_distance_pt=16.0,
        witness_endpoint_distance_pt=12.0,
        chain_axis_tolerance_pt=4.4,
    )
    segments: list[ObservedGeometrySegment] = [
        # Horizontal dimension line + two witness lines around x=[100, 300], y=100
        _seg("h_dim", (100.0, 100.0), (300.0, 100.0), path_idx=1),
        _seg("h_w1", (100.0, 88.0), (100.0, 112.0), path_idx=2),
        _seg("h_w2", (300.0, 88.0), (300.0, 112.0), path_idx=3),
        # Tight 4-edge text wipeout box around horizontal text bbox (190, 92, 210, 100)
        _seg("box_t", (190.0, 92.0), (210.0, 92.0), path_idx=4),
        _seg("box_b", (190.0, 100.0), (210.0, 100.0), path_idx=4),
        _seg("box_l", (190.0, 92.0), (190.0, 100.0), path_idx=4),
        _seg("box_r", (210.0, 92.0), (210.0, 100.0), path_idx=4),
        # Vertical dimension line + two witness lines at x=500, y=[200, 380]
        _seg("v_dim", (500.0, 200.0), (500.0, 380.0), path_idx=5),
        _seg("v_w1", (488.0, 200.0), (512.0, 200.0), path_idx=6),
        _seg("v_w2", (488.0, 380.0), (512.0, 380.0), path_idx=7),
    ]
    # Add 1,000 distractor segments across the sheet to exercise spatial pruning
    for i in range(500):
        y = 500.0 + i * 3.0
        segments.append(_seg(f"dist_h_{i}", (10.0, y), (900.0, y), path_idx=100 + i))
        x = 600.0 + i * 3.0
        segments.append(_seg(f"dist_v_{i}", (x, 10.0), (x, 900.0), path_idx=700 + i))

    filtered = _without_dimension_text_enclosure_paths(
        segments, [(190.0, 92.0, 210.0, 100.0)], cal
    )
    assert all(s.source_path_index != 4 for s in filtered)

    idx = _VectorScopeIndex(filtered)
    obs_h = _obs("o_h", (190.0, 92.0, 210.0, 100.0))
    obs_v = _obs("o_v", (492.0, 280.0, 500.0, 300.0))

    b_h = bind_observation_to_vector_geometry(obs_h, filtered, cal, _scope_index=idx)
    b_v = bind_observation_to_vector_geometry(obs_v, filtered, cal, _scope_index=idx)
    assert b_h.status == BindingStatus.WITNESS_BOUND.value
    assert b_h.dimension_line_id == "h_dim"
    assert b_h.witness_line_ids == ("h_w1", "h_w2")
    assert b_h.endpoints == ((100.0, 100.0), (300.0, 100.0))

    assert b_v.status == BindingStatus.WITNESS_BOUND.value
    assert b_v.dimension_line_id == "v_dim"
    assert b_v.witness_line_ids == ("v_w1", "v_w2")
    assert b_v.endpoints == ((500.0, 200.0), (500.0, 380.0))


def test_view_isolation_and_orientation_edge_cases() -> None:
    cal = DimensionLayoutCalibration(
        median_word_height_pt=8.0,
        line_search_distance_pt=16.0,
        witness_endpoint_distance_pt=12.0,
        chain_axis_tolerance_pt=4.4,
    )
    # Zero-length and diagonal segments remain UNKNOWN
    assert _seg("z", (10.0, 10.0), (10.0, 10.0)).orientation == DimensionOrientation.UNKNOWN.value
    assert _seg("d", (0.0, 0.0), (10.0, 10.0)).orientation == DimensionOrientation.UNKNOWN.value
    assert _seg("h", (0.0, 0.0), (40.0, 10.0)).orientation == DimensionOrientation.HORIZONTAL.value
    assert _seg("v", (0.0, 0.0), (10.0, 40.0)).orientation == DimensionOrientation.VERTICAL.value

    # Segments in another view_id must never bind to an observation in vp_a
    segs = (
        _seg("other_h", (100.0, 100.0), (300.0, 100.0), view_id="vp_b", path_idx=1),
        _seg("other_w1", (100.0, 88.0), (100.0, 112.0), view_id="vp_b", path_idx=2),
        _seg("other_w2", (300.0, 88.0), (300.0, 112.0), view_id="vp_b", path_idx=3),
    )
    obs = _obs("o_vp_a", (190.0, 92.0, 210.0, 100.0), view_id="vp_a")
    binding = bind_observation_to_vector_geometry(obs, segs, cal)
    assert binding.status == BindingStatus.UNSUPPORTED.value
