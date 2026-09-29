"""Exactness and scaling gates for Stage-A endpoint spatial indexing."""
from __future__ import annotations

import random

import pb_wall_room_topology_stage_a as stage_a
from pb_vector_geometry_v130 import snap_geometry


def _seg(index, x1, y1, x2, y2):
    return {
        "id": f"s{index}",
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "width": 1.0,
        "stroke": None,
        "fill": None,
        "layer": "",
        "dashes": "",
    }


def _assert_exact(segments, tolerance=2.5):
    expected = snap_geometry(segments, tolerance_pt=tolerance)
    actual = stage_a._snap_geometry_indexed(segments, tolerance_pt=tolerance)
    assert actual == expected


def test_randomized_exact_graph_equality():
    for seed in range(40):
        rng = random.Random(seed)
        segments = []
        for index in range(120):
            # Mix isolated endpoints and tight clusters so running centroids move.
            if index % 4 == 0:
                base_x = rng.choice((-100.0, 0.0, 100.0, 500.0))
                base_y = rng.choice((-100.0, 0.0, 100.0, 500.0))
                x1 = base_x + rng.uniform(-2.4, 2.4)
                y1 = base_y + rng.uniform(-2.4, 2.4)
            else:
                x1 = rng.uniform(-1000.0, 1000.0)
                y1 = rng.uniform(-1000.0, 1000.0)
            x2 = x1 + rng.uniform(-120.0, 120.0)
            y2 = y1 + rng.uniform(-120.0, 120.0)
            segments.append(_seg(index, x1, y1, x2, y2))
        _assert_exact(segments)


def test_negative_coordinates_and_cell_boundaries_match_exactly():
    segments = [
        _seg(0, -2.51, -2.51, 100.0, 100.0),
        _seg(1, -0.02, -2.49, 200.0, 200.0),
        _seg(2, -2.49, -0.02, 300.0, 300.0),
        _seg(3, 0.01, 0.01, 400.0, 400.0),
    ]
    _assert_exact(segments, tolerance=2.5)


def test_equal_distance_tie_keeps_earliest_node_like_legacy():
    segments = [
        _seg(0, -1.0, 0.0, -100.0, -100.0),
        _seg(1, 1.0, 0.0, 100.0, 100.0),
        _seg(2, 0.0, 0.0, 200.0, 200.0),
    ]
    _assert_exact(segments, tolerance=1.1)


def test_running_centroid_can_cross_grid_cell_without_semantic_change():
    segments = [
        _seg(0, 2.49, 0.0, 100.0, 0.0),
        _seg(1, 4.70, 0.0, 200.0, 0.0),
        _seg(2, 4.60, 0.0, 300.0, 0.0),
        _seg(3, 4.55, 0.0, 400.0, 0.0),
    ]
    _assert_exact(segments, tolerance=2.5)


def test_zero_tolerance_falls_back_to_legacy_exactly():
    segments = [
        _seg(0, 0.0, 0.0, 10.0, 0.0),
        _seg(1, 0.0, 0.0, 0.0, 10.0),
    ]
    _assert_exact(segments, tolerance=0.0)


def test_input_order_is_preserved_exactly():
    segments = [
        _seg(0, 0.0, 0.0, 10.0, 0.0),
        _seg(1, 10.3, 0.0, 20.0, 0.0),
        _seg(2, 20.2, 0.0, 30.0, 0.0),
        _seg(3, 15.0, -10.0, 15.0, 10.0),
    ]
    for order in (
        segments,
        list(reversed(segments)),
        [segments[2], segments[0], segments[3], segments[1]],
    ):
        _assert_exact(order)


def test_sparse_five_thousand_segments_avoids_quadratic_distance_scans(monkeypatch):
    segments = [
        _seg(i, i * 20.0, 0.0, i * 20.0 + 5.0, 0.0)
        for i in range(5000)
    ]
    calls = 0
    original = stage_a.math.hypot

    def counted(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(stage_a.math, "hypot", counted)
    result = stage_a._snap_geometry_indexed(segments, tolerance_pt=2.5)
    assert len(result["edges"]) == 5000
    assert len(result["nodes"]) == 10000
    # One hypot per emitted edge plus only local candidate checks.
    assert calls < 15000
