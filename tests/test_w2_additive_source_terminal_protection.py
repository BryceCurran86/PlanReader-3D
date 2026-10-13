"""Original source terminal protection is *geometry proof*, not a snap relaxation."""
from __future__ import annotations

import pytest

from pb_wall_room_topology_stage_a import (
    _protect_additive_intersection_source_terminals,
    _snap_geometry_indexed,
    build_wall_graph_for_viewport,
)
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY


def _line(source_id, x1, y1, x2, y2, *, additive=False):
    return dict(
        id=source_id, x1=x1, y1=y1, x2=x2, y2=y2,
        kind="line", kind_present=True, width=0.0, width_present=False,
        stroke=None, stroke_present=False, fill=None, fill_present=False,
        layer="", layer_present=False, dashes="", dashes_present=False,
        clip=None, clip_present=False, clip_known=True,
        document_id="original-doc", page_id="3", viewport_id="p3",
        additive_split_identity_namespace=additive,
    )


def _edge_source_ids(edge):
    return tuple((edge.get(LINEAGE_KEY) or {}).get("source_primitive_ids") or ())


def test_true_original_terminal_tail_is_not_destroyed_by_additive_crossing():
    old = _line("original:vertical", 10.0, 0.0, 10.0, 10.0)
    new = _line("authenticated:horizontal", 5.0, 8.5, 15.0, 8.5, additive=True)
    graph = build_wall_graph_for_viewport([old, new], gap_snap_tolerance_pt=2.5)
    tails = [e for e in graph["edges"] if "original:vertical" in _edge_source_ids(e)
             and e.get("_protect_source_terminal_end") is True
             or "original:vertical" in _edge_source_ids(e)
             and e.get("_protect_source_terminal_start") is True]
    assert len(tails) == 1
    tail = tails[0]
    assert tail["a"] != tail["b"]
    assert tail["length_pt"] == pytest.approx(1.5)
    assert graph["nodes"][tail["a"]]["id"] != graph["nodes"][tail["b"]]["id"]
    # One endpoint retains the EXACT original source terminal point.
    endpoints = [graph["nodes"][tail[side]] for side in ("a", "b")]
    assert any(n["x"] == pytest.approx(10.0) and n["y"] == pytest.approx(10.0)
               for n in endpoints)
    assert any(n["x"] == pytest.approx(10.0) and n["y"] == pytest.approx(8.5)
               for n in endpoints)


def test_adjacent_unjoined_additive_ink_does_not_protect_short_source_fragment():
    original = _line("original", 0.0, 0.0, 10.0, 0.0)
    near_nonintersection = _line("supplemental", 10.01, -1.0, 10.01, 1.0, additive=True)
    split = dict(_line("split_0", 8.5, 0.0, 10.0, 0.0),
                 **{LINEAGE_KEY: {"source_primitive_ids": ("original",)}})
    outcome = _protect_additive_intersection_source_terminals(
        [split], [original, near_nonintersection], tolerance_pt=2.5
    )
    assert "_protect_source_terminal_start" not in outcome[0]
    assert "_protect_source_terminal_end" not in outcome[0]


def test_nonterminal_source_piece_does_not_become_a_protected_endpoint():
    original = _line("original", 0.0, 0.0, 10.0, 0.0)
    supplemental = _line("supplemental", 5.0, -1.0, 5.0, 1.0, additive=True)
    interior = dict(_line("split_0", 4.0, 0.0, 5.0, 0.0),
                    **{LINEAGE_KEY: {"source_primitive_ids": ("original",)}})
    assert not any(k.startswith("_protect_source_terminal_") for k in
                   _protect_additive_intersection_source_terminals(
                       [interior], [original, supplemental], tolerance_pt=2.5
                   )[0])


def test_ambiguous_original_parent_and_unbacked_single_small_source_do_not_promote():
    old1 = _line("a", 0.0, 0.0, 10.0, 0.0)
    old2 = _line("b", 0.0, 0.0, 10.0, 0.0)
    supplemental = _line("s", 8.5, -1.0, 8.5, 1.0, additive=True)
    ambiguous = dict(_line("split_0", 8.5, 0.0, 10.0, 0.0),
                     **{LINEAGE_KEY: {"source_primitive_ids": ("a", "b")}})
    result = _protect_additive_intersection_source_terminals(
        [ambiguous], [old1, old2, supplemental], tolerance_pt=2.5)
    assert "_protect_source_terminal_end" not in result[0]
    unsupported = dict(ambiguous, **{LINEAGE_KEY: {"source_primitive_ids": ("unknown",)}})
    assert "_protect_source_terminal_end" not in (
        _protect_additive_intersection_source_terminals(
            [unsupported], [old1, supplemental], tolerance_pt=2.5)[0]
    )


def test_ordinary_pipeline_and_zero_tolerance_remain_unchanged():
    source = [_line("source:wall", 0.0, 0.0, 10.0, 0.0)]
    first = build_wall_graph_for_viewport(source)
    second = build_wall_graph_for_viewport(source)
    assert first == second
    assert all(not node.get("_protected_source_terminal") for node in first["nodes"])
    snapshot = dict(_line("split_0", 8.5, 0.0, 10.0, 0.0),
                    **{LINEAGE_KEY: {"source_primitive_ids": ("source:wall",)}})
    extra = _line("supplemental", 8.5, -5.0, 8.5, 5.0, additive=True)
    assert _protect_additive_intersection_source_terminals(
        [snapshot], [source[0], extra], tolerance_pt=0.0
    ) == [snapshot]


def test_source_terminal_locator_rejects_unproven_snap_collapse():
    # A terminal marker may never be silently turned into an empty edge.
    fragment = dict(_line("split_0", 0.0, 0.0, 0.0, 0.0),
                    _protect_source_terminal_end=True)
    with pytest.raises(RuntimeError, match="source-authenticated terminal"):
        _snap_geometry_indexed([fragment], tolerance_pt=2.5)
