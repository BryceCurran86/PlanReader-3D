from __future__ import annotations

from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport


def _seg(
    source_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    additive: bool = False,
):
    return {
        "id": source_id,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "kind": "line",
        "kind_present": True,
        "width": 0.0,
        "width_present": False,
        "stroke": None,
        "stroke_present": False,
        "fill": None,
        "fill_present": False,
        "layer": "",
        "layer_present": False,
        "dashes": "",
        "dashes_present": False,
        "clip": None,
        "clip_present": False,
        "clip_known": True,
        "document_id": "doc",
        "page_id": "1",
        "viewport_id": "vp",
        "additive_split_identity_namespace": additive,
    }


def _leaf_rows(graph):
    return [
        edge
        for edge in graph["edges"]
        if not edge.get("collinear_merge_leaf_edge_ids")
    ]


def _by_source(graph, source_id: str):
    return [
        edge
        for edge in _leaf_rows(graph)
        if source_id in tuple(
            (edge.get(LINEAGE_KEY) or {}).get("source_primitive_ids") or ()
        )
    ]


def test_additive_intersection_does_not_rename_unaffected_later_fragment():
    ordinary = [
        _seg("ordinary:a", 0.0, 0.0, 10.0, 0.0),
        _seg("ordinary:b", 20.0, 0.0, 30.0, 0.0),
    ]
    baseline = build_wall_graph_for_viewport(
        ordinary,
        gap_snap_tolerance_pt=0.0,
    )
    baseline_b = _by_source(baseline, "ordinary:b")
    assert len(baseline_b) == 1
    assert baseline_b[0]["id"] == "split_1"

    candidate = build_wall_graph_for_viewport(
        [
            *ordinary,
            _seg("supplemental:x", 5.0, -5.0, 5.0, 5.0, additive=True),
        ],
        gap_snap_tolerance_pt=0.0,
    )
    candidate_b = _by_source(candidate, "ordinary:b")
    assert len(candidate_b) == 1
    assert candidate_b[0]["id"] == "split_1"

    ids = [str(edge["id"]) for edge in candidate["edges"]]
    assert len(ids) == len(set(ids))


def test_fragment_changed_by_additive_intersection_does_not_keep_old_id():
    ordinary = [_seg("ordinary:a", 0.0, 0.0, 10.0, 0.0)]
    baseline = build_wall_graph_for_viewport(
        ordinary,
        gap_snap_tolerance_pt=0.0,
    )
    old = _by_source(baseline, "ordinary:a")
    assert len(old) == 1
    assert old[0]["id"] == "split_0"

    candidate = build_wall_graph_for_viewport(
        [
            *ordinary,
            _seg("supplemental:x", 5.0, -5.0, 5.0, 5.0, additive=True),
        ],
        gap_snap_tolerance_pt=0.0,
    )
    changed = _by_source(candidate, "ordinary:a")
    assert len(changed) == 2
    assert "split_0" not in {row["id"] for row in changed}
    assert all(int(str(row["id"]).split("_")[-1]) >= 1 for row in changed)


def test_without_additive_namespace_historical_enumeration_is_unchanged():
    graph = build_wall_graph_for_viewport(
        [
            _seg("a", 0.0, 0.0, 10.0, 0.0),
            _seg("b", 20.0, 0.0, 30.0, 0.0),
        ],
        gap_snap_tolerance_pt=0.0,
    )
    assert [row["id"] for row in _leaf_rows(graph)] == ["split_0", "split_1"]
