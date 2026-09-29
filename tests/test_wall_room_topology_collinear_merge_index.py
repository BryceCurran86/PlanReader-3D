"""Differential gates for indexed Stage-A degree-two collinear merging."""
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


def _assert_exact(graph, tolerance=2.5):
    expected = stage_a.merge_collinear_degree_two_nodes(
        graph, angle_tolerance_deg=tolerance
    )
    actual = stage_a._merge_collinear_degree_two_nodes_indexed(
        graph, angle_tolerance_deg=tolerance
    )
    assert actual == expected


def test_randomized_snapped_graphs_match_legacy_exactly():
    for seed in range(50):
        rng = random.Random(seed)
        segments = []
        for index in range(80):
            if index % 3 == 0:
                # Collinear-ish chains with repeated shared endpoints.
                y = float(rng.randrange(-4, 5) * 20)
                x1 = float(rng.randrange(-20, 20) * 10)
                x2 = x1 + rng.choice((5.0, 10.0, 20.0, 30.0))
                segments.append(_seg(index, x1, y, x2, y + rng.uniform(-0.1, 0.1)))
            else:
                x1 = rng.uniform(-300.0, 300.0)
                y1 = rng.uniform(-300.0, 300.0)
                x2 = x1 + rng.uniform(-80.0, 80.0)
                y2 = y1 + rng.uniform(-80.0, 80.0)
                if x1 == x2 and y1 == y2:
                    x2 += 1.0
                segments.append(_seg(index, x1, y1, x2, y2))
        graph = snap_geometry(segments, tolerance_pt=0.0)
        _assert_exact(graph)


def test_long_collinear_chain_matches_legacy():
    segments = [
        _seg(i, i * 10.0, 0.0, (i + 1) * 10.0, 0.0)
        for i in range(40)
    ]
    _assert_exact(snap_geometry(segments, tolerance_pt=0.0))


def test_bent_chain_matches_legacy():
    segments = [
        _seg(0, 0, 0, 10, 0),
        _seg(1, 10, 0, 20, 0.2),
        _seg(2, 20, 0.2, 30, 5),
        _seg(3, 30, 5, 40, 5),
    ]
    _assert_exact(snap_geometry(segments, tolerance_pt=0.0))


def test_loop_and_branch_graphs_match_legacy():
    segments = [
        _seg(0, 0, 0, 10, 0),
        _seg(1, 10, 0, 10, 10),
        _seg(2, 10, 10, 0, 10),
        _seg(3, 0, 10, 0, 0),
        _seg(4, 10, 0, 20, 0),
        _seg(5, 20, 0, 30, 0),
        _seg(6, 20, 0, 20, 10),
    ]
    _assert_exact(snap_geometry(segments, tolerance_pt=0.0))


def test_reversed_input_order_still_matches_legacy():
    segments = [
        _seg(i, i * 7.0, 0.0, (i + 1) * 7.0, 0.0)
        for i in range(12)
    ]
    for ordered in (
        segments,
        list(reversed(segments)),
        [segments[i] for i in (4, 0, 8, 1, 9, 2, 10, 3, 11, 5, 6, 7)],
    ):
        _assert_exact(snap_geometry(ordered, tolerance_pt=0.0))


def test_indexed_merge_does_not_mutate_input_graph():
    segments = [
        _seg(0, 0, 0, 10, 0),
        _seg(1, 10, 0, 20, 0),
        _seg(2, 20, 0, 30, 0),
    ]
    graph = snap_geometry(segments, tolerance_pt=0.0)
    before = repr(graph)
    stage_a._merge_collinear_degree_two_nodes_indexed(graph)
    assert repr(graph) == before


def test_thousand_edge_chain_has_linear_angle_checks(monkeypatch):
    edge_count = 1000
    segments = [
        _seg(i, i * 5.0, 0.0, (i + 1) * 5.0, 0.0)
        for i in range(edge_count)
    ]
    graph = snap_geometry(segments, tolerance_pt=0.0)
    calls = 0
    original = stage_a._angle_delta

    def counted(*args):
        nonlocal calls
        calls += 1
        return original(*args)

    monkeypatch.setattr(stage_a, "_angle_delta", counted)
    result = stage_a._merge_collinear_degree_two_nodes_indexed(graph)
    assert len(result["edges"]) == 1
    assert calls < edge_count * 3
