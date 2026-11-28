"""W2 order-free endpoint snap (shadow): order, unrelated content, ambiguity and transforms."""
from __future__ import annotations

import copy
import math
import random

import pytest

from pb_wall_room_topology_order_free_snap_shadow import order_free_snap_geometry
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport


def seg(x1, y1, x2, y2):
    return {"x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2)}


# A corner of two long walls, one running 2.5 pt past it, with two 2 pt stubs on that overshoot's end.
WALLS = [seg(0, -31.5, 0, 2.5), seg(-15.25, 0, 0, 0), seg(0, 0, 38.5, 0), seg(38.5, -24.5, 38.5, 3.5)]
STUBS = [seg(-2, 2.5, 0, 2.5), seg(0, 2.5, 2, 2.5)]
SCENE = WALLS + STUBS


def free(segments):
    return build_wall_graph_for_viewport(segments, order_free_snap_shadow=True)


def lines(graph):
    ends = lambda e: [(graph["nodes"][e[k]]["x"], graph["nodes"][e[k]]["y"]) for k in ("a", "b")]
    return sorted(tuple(sorted((round(x, 6), round(y, 6)) for x, y in ends(e))) for e in graph["edges"])


def node_points(graph):
    return sorted((round(n["x"], 6), round(n["y"], 6)) for n in graph["nodes"] if n["degree"])


def assert_same_lines(expected, actual):
    """Each expected edge has a matching actual edge within float noise."""
    assert len(expected) == len(actual)
    left = list(actual)
    for a, b in expected:
        match = next((item for item in left
                      if (math.dist(a, item[0]) < 1e-5 and math.dist(b, item[1]) < 1e-5)
                      or (math.dist(a, item[1]) < 1e-5 and math.dist(b, item[0]) < 1e-5)), None)
        assert match is not None, (a, b)
        left.remove(match)


def orders(segments, count=8):
    for seed in range(count):
        shuffled = list(segments)
        random.Random(seed).shuffle(shuffled)
        rng = random.Random(seed + 100)
        yield [seg(s["x2"], s["y2"], s["x1"], s["y1"]) if rng.random() < 0.5 else s for s in shuffled]


def test_stubs_cannot_drag_a_corner_of_long_walls():
    # The ordinary snap tilts the 38.5 pt wall when the stubs come after the walls and not before.
    tilted = lines(build_wall_graph_for_viewport(WALLS + STUBS))
    straight = lines(build_wall_graph_for_viewport(STUBS + WALLS))
    wall = ((0.0, 0.0), (38.5, 0.0))
    assert wall not in tilted and wall in straight
    assert wall in lines(free(WALLS + STUBS))
    assert wall in lines(free(STUBS + WALLS))


def test_result_is_independent_of_order_and_direction():
    reference = lines(free(SCENE))
    for variant in orders(SCENE):
        assert lines(free(variant)) == reference


def test_unrelated_content_leaves_the_corner_alone():
    corner = lambda graph: [pair for pair in lines(graph) if (0.0, 0.0) in pair]
    reference = corner(free(SCENE))
    far = [seg(500, 500, 560, 500), seg(530, 480, 530, 520), seg(501, 501, 502, 501), seg(20, -80, 20, 80)]
    # The last one crosses the 38.5 pt wall far from the corner and splits it there.
    crossed = corner(free(SCENE + far))
    assert [pair for pair in crossed if pair in reference] == [pair for pair in reference if (38.5, 0.0) not in pair]
    assert ((0.0, 0.0), (20.0, 0.0)) in crossed
    assert corner(free(SCENE + far[:3])) == reference


def test_a_short_stub_beside_the_corner_does_not_move_it():
    ell = [seg(0, -31.5, 0, 0), seg(0, 0, 38.5, 0)]
    stub = [seg(0, 1.5, 1.5, 1.5)]
    assert (0.0, 0.0) not in node_points(build_wall_graph_for_viewport(ell + stub))  # ordinary snap moves it
    assert (0.0, 0.0) in node_points(free(ell)) and (0.0, 0.0) in node_points(free(stub + ell))
    assert lines(free(ell + stub)) == lines(free(ell))


def test_a_drafting_gap_between_long_walls_still_closes():
    gap = [seg(-30, 0, -0.5, 0), seg(0.5, 0, 30, 0)]
    assert lines(free(gap)) == [((-30.0, 0.0), (30.0, 0.0))]
    assert lines(free(gap)) == lines(build_wall_graph_for_viewport(gap))


def test_ends_exactly_the_tolerance_apart_stay_joined_after_rotation():
    pair = [seg(0, 0, -30, 0), seg(2.5, 0, 2.5, 30)]
    c, s = math.cos(math.radians(37)), math.sin(math.radians(37))
    move = lambda x, y: (x * c - y * s + 1000.1, x * s + y * c + 2000.3)
    turned = [seg(*move(q["x1"], q["y1"]), *move(q["x2"], q["y2"])) for q in pair]
    assert math.dist((turned[0]["x1"], turned[0]["y1"]), (turned[1]["x1"], turned[1]["y1"])) > 2.5  # float noise
    assert len(node_points(free(pair))) == 3 and len(node_points(free(turned))) == 3


def test_a_gap_wider_than_the_tolerance_stays_open():
    apart = [seg(-30, 0, -1.6, 0), seg(1.5, 0, 30, 0)]
    assert len(lines(free(apart))) == 2


def test_equally_spaced_chain_is_left_unjoined_rather_than_settled_by_order():
    chain = [seg(0, -30, 0, 0), seg(2, 0, 2, 30), seg(4, 0, 34, 0)]
    results = {str(node_points(build_wall_graph_for_viewport(v))) for v in orders(chain)}
    assert len(results) > 1  # the ordinary snap settles it by order
    expected = [(0.0, -30.0), (0.0, 0.0), (2.0, 0.0), (2.0, 30.0), (4.0, 0.0), (34.0, 0.0)]
    for variant in orders(chain):
        graph = free(variant)
        assert node_points(graph) == expected
        assert graph["order_free_snap_shadow"]["equally_close_groupings_refused"] == 1


def test_unequal_chain_joins_the_closer_pair_only():
    chain = [seg(0, -30, 0, 0), seg(1.5, 0, 30, 30), seg(3.5, 0, 33.5, 0)]
    for variant in orders(chain):
        points = node_points(free(variant))
        assert (0.75, 0.0) in points and (3.5, 0.0) in points


def test_equally_spaced_corner_that_fits_the_tolerance_joins_whole():
    ends = [(0.0, 0.0), (2.0, 0.0), (1.0, math.sqrt(3.0))]
    walls = [seg(*ends[0], -30, -20), seg(*ends[1], 32, -20), seg(*ends[2], 1, 40)]
    for variant in orders(walls):
        graph = free(variant)
        assert (1.0, round(math.sqrt(3.0) / 3, 6)) in node_points(graph)
        assert len(node_points(graph)) == 4


def test_a_short_end_equidistant_from_two_corners_is_not_assigned():
    two = [seg(-32, 0, -2, 0), seg(2, 0, 32, 0), seg(0, 0, 0, 2)]
    results = {str(node_points(build_wall_graph_for_viewport(v))) for v in orders(two)}
    assert len(results) > 1  # the ordinary snap settles it by order
    for variant in orders(two):
        graph = free(variant)
        assert {(-2.0, 0.0), (2.0, 0.0)} <= set(node_points(graph))
        assert graph["order_free_snap_shadow"]["short_endpoint_sites_equidistant"] == 1


@pytest.mark.parametrize("degrees,shift", [(90, (0, 0)), (180, (12.5, -7.25)), (30, (123.45, -67.89)),
                                           (0, (1000.1, 2000.3))])
def test_translation_and_rotation_give_the_transformed_result(degrees, shift):
    c, s = math.cos(math.radians(degrees)), math.sin(math.radians(degrees))
    move = lambda x, y: (x * c - y * s + shift[0], x * s + y * c + shift[1])
    scene = SCENE + [seg(0, 40, 0, 70), seg(1.5, 70, 1.5, 100)]
    moved = [seg(*move(q["x1"], q["y1"]), *move(q["x2"], q["y2"])) for q in scene]
    expected = [tuple(move(*point) for point in pair) for pair in lines(free(scene))]
    assert_same_lines(expected, lines(free(moved)))


def test_splitting_a_wall_in_two_changes_nothing():
    split = WALLS[:2] + [seg(0, 0, 20, 0), seg(20, 0, 38.5, 0), WALLS[3]] + STUBS
    assert lines(free(split)) == lines(free(SCENE))


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    before = copy.deepcopy(SCENE)
    first, second = free(SCENE), free(SCENE)
    assert first == second and SCENE == before
    assert first["order_free_snap_shadow"]["diagnostic_only"] is True
    assert first["order_free_snap_shadow"]["source_wall_role_authenticated"] is False


def test_collapsed_stubs_are_still_reported():
    graph = free(SCENE)
    assert any(row["reason"] for row in graph["snap_collapsed_fragments"])


def test_off_by_default_and_the_ordinary_result_is_unchanged():
    assert build_wall_graph_for_viewport(SCENE) == build_wall_graph_for_viewport(SCENE, order_free_snap_shadow=False)
    assert "order_free_snap_shadow" not in build_wall_graph_for_viewport(SCENE)


@pytest.mark.parametrize("kwargs", [
    {"order_free_snap_shadow": 1},
    {"order_free_snap_shadow": True, "complete_link_snap_shadow": True},
    {"order_free_snap_shadow": True, "gap_snap_tolerance_pt": 0.0},
    {"order_free_snap_shadow": True, "gap_snap_tolerance_pt": 0.0, "exact_endpoint_index_shadow": True},
])
def test_unsupported_combinations_are_refused(kwargs):
    with pytest.raises(ValueError):
        build_wall_graph_for_viewport(SCENE, **kwargs)


@pytest.mark.parametrize("tolerance", [0.0, -1.0, float("nan")])
def test_direct_call_needs_a_positive_tolerance(tolerance):
    with pytest.raises(ValueError):
        order_free_snap_geometry([seg(0, 0, 10, 0)], tolerance)


def test_endpoint_trace_requires_unique_ids():
    with pytest.raises(ValueError):
        order_free_snap_geometry([seg(0, 0, 10, 0)], 2.5, include_endpoint_assignments=True)
    traced = order_free_snap_geometry([dict(seg(0, 0, 10, 0), id="a")], 2.5, include_endpoint_assignments=True)
    assert traced["endpoint_snap_assignments"] == {"a": (0, 1)}
