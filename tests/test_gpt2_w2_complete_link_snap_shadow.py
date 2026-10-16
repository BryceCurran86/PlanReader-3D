"""Genuine W2 source geometry must not be changed without explicit shadow opt-in."""
import copy
import math

import pytest

from pb_wall_room_topology_stage_a import (
    _snap_geometry_indexed,
    build_wall_graph_for_viewport,
)


def seg(identity, a, b):
    return {
        "id": identity, "x1": float(a[0]), "y1": float(a[1]),
        "x2": float(b[0]), "y2": float(b[1]),
        "kind": "line", "width": .48, "stroke": (0.,0.,0.),
        "layer": "", "dashes": "",
    }


def test_original_running_centroid_admits_2p8_wide_endpoint_cluster():
    endpoints = [
        seg("a", (0, 0), (20, 0)),
        seg("b", (1.4, 0), (20, 1)),
        seg("c", (2.8, 0), (20, 2)),
    ]
    baseline = _snap_geometry_indexed(endpoints, tolerance_pt=2.5)
    assert baseline["edges"][0]["a"] == baseline["edges"][1]["a"]
    assert baseline["edges"][1]["a"] == baseline["edges"][2]["a"]
    shadow = _snap_geometry_indexed(
        endpoints, tolerance_pt=2.5,
        complete_link_snap_shadow=True, include_endpoint_assignments=True,
    )
    assert shadow["edges"][0]["a"] == shadow["edges"][1]["a"]
    assert shadow["edges"][2]["a"] != shadow["edges"][0]["a"]
    assert shadow["complete_link_snap_shadow"]["running_centroid_eligible_joins_rejected"] > 0
    assert shadow["complete_link_snap_shadow"]["retained_original_endpoint_sample_count"] == 6
    assert not shadow["complete_link_snap_shadow"]["source_wall_role_authenticated"]


def test_genuine_exact_shared_junction_preserves_original_graph_under_shadow():
    data = [
        seg("one", (0,0), (20,0)),
        seg("two", (0,0), (0,20)),
        seg("three", (0,0), (-20,0)),
    ]
    before = copy.deepcopy(data)
    base = _snap_geometry_indexed(data, tolerance_pt=2.5)
    protected = _snap_geometry_indexed(data, tolerance_pt=2.5,
                                        complete_link_snap_shadow=True)
    assert base["nodes"] == protected["nodes"]
    assert base["edges"] == protected["edges"]
    assert base["adjacency"] == protected["adjacency"]
    assert protected["complete_link_snap_shadow"]["running_centroid_eligible_joins_rejected"] == 0
    assert before == data


def test_real_w2_pipeline_remains_default_and_complete_link_is_explicit():
    data = [
        seg("horizontal", (0,0), (15,0)),
        seg("vertical", (0,0), (0,15)),
    ]
    baseline = build_wall_graph_for_viewport(data)
    optional = build_wall_graph_for_viewport(data, complete_link_snap_shadow=False)
    assert baseline == optional
    changed = build_wall_graph_for_viewport(data, complete_link_snap_shadow=True)
    assert changed["complete_link_snap_shadow"]["diagnostic_only"]
    assert not changed["complete_link_snap_shadow"]["source_wall_role_authenticated"]
    assert "complete_link_snap_shadow" not in baseline


def test_same_running_centroid_can_reject_distant_reversed_native_endpoint():
    original = [
        seg("a", (0,0), (30,0)),
        seg("b", (1.4,0), (30,3)),
        seg("c", (30,6), (2.8,0)),
    ]
    protected = _snap_geometry_indexed(original, tolerance_pt=2.5,
                                        complete_link_snap_shadow=True)
    ids = {e["id"]: e for e in protected["edges"]}
    assert ids["a"]["a"] == ids["b"]["a"]
    assert ids["c"]["b"] != ids["a"]["a"]


def test_bad_shadow_mode_and_zero_tolerance_refused():
    data = [seg("one", (0,0), (1,0))]
    for invalid in (1, "true", None):
        with pytest.raises(ValueError, match="explicit boolean"):
            _snap_geometry_indexed(data, complete_link_snap_shadow=invalid)
        with pytest.raises(ValueError, match="explicit boolean"):
            build_wall_graph_for_viewport(data,complete_link_snap_shadow=invalid)
    with pytest.raises(ValueError, match="requires positive tolerance"):
        _snap_geometry_indexed(data,tolerance_pt=0,complete_link_snap_shadow=True)
    with pytest.raises(ValueError, match="requires positive tolerance"):
        _snap_geometry_indexed(data,tolerance_pt=2.5,complete_link_snap_shadow=True,
                               exact_endpoint_index_shadow=True)
