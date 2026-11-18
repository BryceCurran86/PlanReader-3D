"""#4549-06..10 dual-dwelling shell, party exclusion, opening bridges."""
from __future__ import annotations

from pb_source_dual_dwelling_opening_topology_shadow import (
    TopologyEdge,
    build_dual_dwelling_opening_topology,
)


def _dual_scene(*, with_openings: bool = True, with_post: bool = False):
    if not with_openings:
        edges = [
            TopologyEdge(1, (0, 0), (100, 0), role="external"),
            TopologyEdge(2, (100, 0), (100, 80), role="party"),
            TopologyEdge(3, (100, 80), (0, 80), role="external"),
            TopologyEdge(4, (0, 80), (0, 0), role="external"),
            TopologyEdge(5, (100, 0), (200, 0), role="external"),
            TopologyEdge(6, (200, 0), (200, 80), role="external"),
            TopologyEdge(7, (200, 80), (100, 80), role="external"),
        ]
        a = (1, 2, 3, 4)
        b = (5, 2, 7, 6)
    else:
        # Opening bridges replace removed wall segments so loops stay closed.
        edges = [
            TopologyEdge(11, (0, 0), (40, 0), role="external"),
            TopologyEdge(
                9, (40, 0), (60, 0), role="opening_bridge", kind="sliding",
                retained_object_id=901,
            ),
            TopologyEdge(12, (60, 0), (100, 0), role="external"),
            TopologyEdge(2, (100, 0), (100, 80), role="party"),
            TopologyEdge(31, (100, 80), (140, 80), role="external"),
            TopologyEdge(
                10, (140, 80), (160, 80), role="opening_bridge", kind="swing",
                swing_orientation="cw", retained_object_id=1001,
            ),
            TopologyEdge(32, (160, 80), (0, 80), role="external"),
            TopologyEdge(4, (0, 80), (0, 0), role="external"),
            TopologyEdge(5, (100, 0), (200, 0), role="external"),
            TopologyEdge(61, (200, 0), (200, 30), role="external"),
            TopologyEdge(
                8, (200, 30), (200, 50), role="opening_bridge", kind="window",
            ),
            TopologyEdge(62, (200, 50), (200, 80), role="external"),
            TopologyEdge(7, (200, 80), (100, 80), role="external"),
        ]
        a = (11, 9, 12, 2, 31, 10, 32, 4)
        b = (5, 61, 8, 62, 7, 2)
    if with_post:
        edges = list(edges) + [
            TopologyEdge(99, (50, 40), (54, 44), role="post", kind="post"),
        ]
    return tuple(edges), a, b


def test_06_one_outer_shell_two_independent_dwelling_graphs():
    edges, a, b = _dual_scene(with_openings=False)
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=a, dwelling_b_edge_ids=b,
    )
    assert r.status == "CANDIDATE"
    assert set(r.party_wall_edge_ids) == {2}
    assert set(r.dwelling_a_edge_ids) == set(a)
    assert set(r.dwelling_b_edge_ids) == set(b)
    assert 2 not in r.outer_shell_edge_ids
    assert set(r.outer_shell_edge_ids) == {1, 3, 4, 5, 6, 7}


def test_07_party_length_excluded_from_outer_shell_no_double_count():
    edges, a, b = _dual_scene(with_openings=False)
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=a, dwelling_b_edge_ids=b,
    )
    assert r.party_length_excluded_from_outer_pt == 80.0
    assert 2 not in r.outer_shell_edge_ids
    assert r.outer_shell_length_pt == 100 + 100 + 80 + 100 + 80 + 100


def test_08_window_gap_bridge_keeps_outer_path():
    edges, a, b = _dual_scene(with_openings=True)
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=a, dwelling_b_edge_ids=b,
    )
    assert r.status == "CANDIDATE"
    assert 8 in r.window_bridges
    assert 8 in r.outer_shell_edge_ids


def test_09_sliding_closure_retains_door_object():
    edges, a, b = _dual_scene(with_openings=True)
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=a, dwelling_b_edge_ids=b,
    )
    assert 9 in r.sliding_closures
    sliding = next(e for e in edges if e.edge_id == 9)
    assert sliding.retained_object_id == 901
    assert r.to_dict()["doorway_closure_is_not_physical_wall"] is True


def test_10_swing_closure_retains_orientation():
    edges, a, b = _dual_scene(with_openings=True)
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=a, dwelling_b_edge_ids=b,
    )
    assert len(r.swing_closures) == 1
    assert r.swing_closures[0]["swing_orientation"] == "cw"
    assert r.swing_closures[0]["retained_object_id"] == 1001
    assert r.swing_closures[0]["physical_wall_authenticated"] is False


def test_post_never_enters_shell_or_dwelling_graphs():
    edges, a, b = _dual_scene(with_openings=False, with_post=True)
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=a + (99,), dwelling_b_edge_ids=b,
    )
    assert r.status == "CANDIDATE"
    assert 99 in r.posts_refused_as_walls
    assert 99 not in r.outer_shell_edge_ids
    assert 99 not in r.dwelling_a_edge_ids


def test_missing_party_abstains():
    edges = (
        TopologyEdge(1, (0, 0), (100, 0), role="external"),
        TopologyEdge(2, (100, 0), (100, 80), role="external"),
        TopologyEdge(3, (100, 80), (0, 80), role="external"),
        TopologyEdge(4, (0, 80), (0, 0), role="external"),
    )
    r = build_dual_dwelling_opening_topology(
        edges, dwelling_a_edge_ids=(1, 2, 3, 4), dwelling_b_edge_ids=(1, 2, 3, 4),
    )
    assert r.status == "ABSTAINED"
    assert r.reason == "dual_dwelling_requires_authenticated_party_wall"
