"""W2 opt-in shadows that act on the same source scope stay exclusive, default-off and lossless.

Integration tests for the combined landing of #2770 / #2771 (exact source-incidence policies at zero tolerance) and #2805
(complete-link replay at positive tolerance).  Nothing here grants wall, host, role or quantity authority: every flag is a
diagnostic shadow and the default pipeline must be byte-for-byte what it was without them.
"""
from __future__ import annotations

import copy
import itertools

import pytest

from pb_wall_room_topology_stage_a import _snap_geometry_indexed, build_wall_graph_for_viewport


def seg(identity, a, b):
    return {
        "id": identity, "x1": float(a[0]), "y1": float(a[1]), "x2": float(b[0]), "y2": float(b[1]),
        "kind": "line", "width": 0.48, "stroke": (0.0, 0.0, 0.0), "layer": "", "dashes": "",
    }


def _frame():
    """A closed rectangle with a T-junction: ordinary wall linework with no endpoint cluster."""
    return [
        seg("n", (0, 0), (100, 0)),
        seg("e", (100, 0), (100, 60)),
        seg("s", (100, 60), (0, 60)),
        seg("w", (0, 60), (0, 0)),
        seg("t", (50, 0), (50, 60)),
    ]


def _cluster():
    """Three left endpoints 1.4 pt apart: b is within 2.5 pt of both a and c, but a-c is 2.8 pt apart."""
    return [seg("a", (0, 0), (20, 0)), seg("b", (1.4, 0), (20, 1)), seg("c", (2.8, 0), (20, 2))]


# every other W2 shadow and the keyword set that lets it be called on its own
_EXACT_INCIDENCE_CASES = {
    "exact_endpoint_index_shadow": dict(gap_snap_tolerance_pt=0, exact_endpoint_index_shadow=True),
    "immutable_exact_endpoints_shadow": dict(
        gap_snap_tolerance_pt=0, exact_endpoint_index_shadow=True, immutable_exact_endpoints_shadow=True
    ),
    "preserve_overlapping_spans_shadow": dict(preserve_overlapping_spans_shadow=True),
    "partition_exact_collinear_overlaps_shadow": dict(
        gap_snap_tolerance_pt=0, exact_endpoint_index_shadow=True, exact_split_parent_lineage_shadow=True,
        preserve_overlapping_spans_shadow=True, immutable_exact_endpoints_shadow=True,
        partition_exact_collinear_overlaps_shadow=True,
    ),
}


@pytest.mark.parametrize("name", sorted(_EXACT_INCIDENCE_CASES))
def test_each_exact_incidence_shadow_still_runs_on_its_own(name):
    graph = build_wall_graph_for_viewport(_frame(), **_EXACT_INCIDENCE_CASES[name])
    assert graph["edges"], name
    assert "complete_link_snap_shadow" not in graph


@pytest.mark.parametrize("name", sorted(_EXACT_INCIDENCE_CASES))
def test_complete_link_replay_is_exclusive_with_every_exact_incidence_shadow(name):
    with pytest.raises(ValueError, match="exclusive"):
        build_wall_graph_for_viewport(_frame(), complete_link_snap_shadow=True, **_EXACT_INCIDENCE_CASES[name])


def test_complete_link_replay_alone_still_runs_and_is_diagnostic_only():
    graph = build_wall_graph_for_viewport(_frame(), complete_link_snap_shadow=True)
    receipt = graph["complete_link_snap_shadow"]
    assert receipt["enabled"] and receipt["diagnostic_only"]
    assert receipt["source_wall_role_authenticated"] is False


def test_default_pipeline_is_unchanged_by_the_new_keyword():
    omitted = build_wall_graph_for_viewport(_frame())
    explicit_off = build_wall_graph_for_viewport(_frame(), complete_link_snap_shadow=False)
    assert omitted == explicit_off
    assert "complete_link_snap_shadow" not in omitted
    for flag in _EXACT_INCIDENCE_CASES:
        assert flag not in omitted


@pytest.mark.parametrize("bad", [1, 0, "yes", None, 1.0])
def test_flag_values_must_be_explicit_booleans(bad):
    with pytest.raises(ValueError):
        build_wall_graph_for_viewport(_frame(), complete_link_snap_shadow=bad)


def test_replay_is_deterministic_and_does_not_mutate_the_input():
    segments = _cluster()
    before = copy.deepcopy(segments)
    first = _snap_geometry_indexed(segments, tolerance_pt=2.5, complete_link_snap_shadow=True, include_endpoint_assignments=True)
    second = _snap_geometry_indexed(segments, tolerance_pt=2.5, complete_link_snap_shadow=True, include_endpoint_assignments=True)
    assert first == second
    assert segments == before


def _partition(segments):
    graph = _snap_geometry_indexed(segments, tolerance_pt=2.5, complete_link_snap_shadow=True, include_endpoint_assignments=True)
    by_node = {}
    for edge in graph["edges"]:
        by_node.setdefault(edge["a"], set()).add(edge["id"])
    return graph, frozenset(frozenset(ids) for ids in by_node.values())


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_no_original_endpoint_or_segment_is_lost_in_any_input_order(order):
    base = _cluster()
    segments = [base[i] for i in order]
    graph, _ = _partition(segments)
    assert sorted(edge["id"] for edge in graph["edges"]) == ["a", "b", "c"]  # no segment dropped or duplicated
    assert graph["complete_link_snap_shadow"]["retained_original_endpoint_sample_count"] == 6  # every endpoint kept
    node_ids = range(len(graph["nodes"]))
    assert all(edge["a"] in node_ids and edge["b"] in node_ids for edge in graph["edges"])


def test_complete_link_never_joins_endpoints_farther_apart_than_the_tolerance():
    base = _cluster()
    for order in itertools.permutations(range(3)):
        _, partition = _partition([base[i] for i in order])
        assert frozenset({"a", "c"}) not in partition
        assert all(len(group) <= 2 for group in partition)


def test_known_order_sensitive_residual_of_the_greedy_assignment():
    """b is within tolerance of both a and c, so the greedy assignment pairs it with whichever node exists first.

    Both partitions are valid complete-link clusterings; which one is reported depends on the input order.  This is
    inherited from the legacy first-node tie-break, is replay-deterministic for a given order, and is a typed
    residual of the diagnostic shadow: it must not be read as a physical-wall decision.  Pinned so that a future change
    to the tie-break is a deliberate, reviewed edit rather than a silent one.
    """
    base = _cluster()
    seen = set()
    for order in itertools.permutations(range(3)):
        _, partition = _partition([base[i] for i in order])
        seen.add(partition)
    ab_c = frozenset({frozenset({"a", "b"}), frozenset({"c"})})
    a_bc = frozenset({frozenset({"a"}), frozenset({"b", "c"})})
    assert seen == {ab_c, a_bc}
