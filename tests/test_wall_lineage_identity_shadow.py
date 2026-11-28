"""Source-lineage wall identity (report only): kept across snap moves, vetoed when not provable."""
from __future__ import annotations

import copy
import random
from types import SimpleNamespace

import pytest

from pb_wall_lineage_identity_shadow import (
    MISSING_EDGE,
    MISSING_PIECE,
    MISSING_SOURCE,
    NO_JAMB_PIECE,
    NO_LONG_PIECE,
    SEVERAL_JAMB_PIECES,
    SHARED_PIECE,
    host_jamb_identity,
    wall_lineage_identities,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import assemble_wall_topology


def seg(seg_id, x1, y1, x2, y2):
    return {"id": seg_id, "kind": "line", "x1": float(x1), "y1": float(y1), "x2": float(x2), "y2": float(y2),
            "width": 1.0, "stroke": (0, 0, 0), "fill": None, "layer": "", "dashes": ""}


# A corner whose node the ordinary snap drags sideways with two 2 pt stubs (and does not, order-free).
SCENE = [seg("v", 0, -31.5, 0, 2.5), seg("h1", -45, 0, 0, 0), seg("h2", 0, 0, 38.5, 0), seg("far", 38.5, -24.5, 38.5, 20),
         seg("s1", -2, 2.5, 0, 2.5), seg("s2", 0, 2.5, 2, 2.5)]


def run(segments, **options):
    graph = build_wall_graph_for_viewport(segments, retain_leaf_fragments_shadow=True, **options)
    junctions, relationships = classify_junctions(graph, document_id="d", page_id="p1", viewport_id="vp")
    walls, _junctions = assemble_wall_topology(graph, junctions, relationships, viewport_id="vp")
    return walls, wall_lineage_identities(walls, graph, tolerance_pt=2.5)


def by_length(walls, result, low, high):
    return [result["identities"][w.candidate_id] for w in walls
            if low <= abs(w.centerline_pts[-1][0] - w.centerline_pts[0][0]) <= high]


def test_a_moved_corner_keeps_the_lineage_id_while_the_candidate_id_changes():
    ordinary_walls, ordinary = run(SCENE)
    free_walls, free = run(SCENE, order_free_snap_shadow=True)
    assert {w.candidate_id for w in ordinary_walls} != {w.candidate_id for w in free_walls}
    assert by_length(ordinary_walls, ordinary, 38, 39) == by_length(free_walls, free, 38, 39) != [None]


def test_a_different_membership_gets_a_different_id():
    walls, result = run([seg("a", 0, 0, 100, 0)])
    longer_walls, longer = run([seg("a", 0, 0, 100, 0), seg("b", 100, 0, 200, 0)])
    one, two = result["identities"][walls[0].candidate_id], longer["identities"][longer_walls[0].candidate_id]
    assert one is not None and two is not None and one != two  # a merged edge still names both of its pieces


def test_the_same_pieces_in_another_viewport_are_another_wall():
    wall = fake_wall("w", "e")
    other = SimpleNamespace(candidate_id="w", viewport_id="vp2", face_a_segment_ids=("e",), face_b_segment_ids=None)
    ids = [wall_lineage_identities([w], fake_graph({"e": LONG}), tolerance_pt=2.5)["identities"]["w"]
           for w in (wall, other)]
    assert ids[0] != ids[1]


def test_order_and_direction_do_not_change_the_ids():
    _walls, result = run(SCENE, order_free_snap_shadow=True)
    expected = sorted(str(v) for v in result["identities"].values())
    for seed in range(5):
        shuffled = list(SCENE)
        random.Random(seed).shuffle(shuffled)
        flipped = [seg(s["id"], s["x2"], s["y2"], s["x1"], s["y1"]) if random.Random(seed + len(s["id"])).random() < 0.5
                   else s for s in shuffled]
        assert sorted(str(v) for v in run(flipped, order_free_snap_shadow=True)[1]["identities"].values()) == expected


def test_a_translated_copy_gets_different_ids_because_it_is_different_source_geometry():
    walls, result = run([seg("a", 0, 0, 100, 0)])
    moved_walls, moved = run([seg("a", 5, 0, 105, 0)])
    assert result["identities"][walls[0].candidate_id] != moved["identities"][moved_walls[0].candidate_id]


def test_the_default_graph_is_unchanged_and_retention_only_adds_pieces():
    plain = build_wall_graph_for_viewport(SCENE)
    kept = build_wall_graph_for_viewport(SCENE, retain_leaf_fragments_shadow=True)
    assert "leaf_fragments_shadow" not in plain
    assert {k: v for k, v in kept.items() if k != "leaf_fragments_shadow"} == plain
    assert len(kept["leaf_fragments_shadow"]) >= len(plain["edges"])
    with pytest.raises(ValueError):
        build_wall_graph_for_viewport(SCENE, retain_leaf_fragments_shadow=1)


def fake_wall(wall_id, *edges):
    return SimpleNamespace(candidate_id=wall_id, viewport_id="vp", face_a_segment_ids=edges, face_b_segment_ids=None)


def fake_graph(pieces, edges=()):
    return {"edges": [{"id": e} for e in edges or pieces], "leaf_fragments_shadow": pieces}


LONG = {"points": (0.0, 0.0, 10.0, 0.0), "source_primitive_ids": ("n1",)}
SHORT = {"points": (0.0, 0.0, 2.0, 0.0), "source_primitive_ids": ()}


@pytest.mark.parametrize("walls,pieces,edges,expected", [
    ([fake_wall("w", "gone")], {"e": LONG}, (), {"w": MISSING_EDGE}),
    ([fake_wall("w", "e")], {}, ("e",), {"w": MISSING_PIECE}),
    ([fake_wall("w", "e")], {"e": {"points": (0.0, 0.0, 10.0, 0.0), "source_primitive_ids": ()}}, (),
     {"w": MISSING_SOURCE}),
    ([fake_wall("w", "e")], {"e": SHORT}, (), {"w": NO_LONG_PIECE}),
    ([fake_wall("w1", "e"), fake_wall("w2", "f")], {"e": LONG, "f": dict(LONG)}, (),
     {"w1": SHARED_PIECE, "w2": SHARED_PIECE}),
])
def test_unprovable_identities_are_vetoed_not_chosen(walls, pieces, edges, expected):
    result = wall_lineage_identities(walls, fake_graph(pieces, edges), tolerance_pt=2.5)
    assert result["vetoes"] == expected
    assert all(result["identities"][w] is None for w in expected)
    assert result["replaces_existing_identity"] is False and result["diagnostic_only"] is True


def test_minus_zero_and_zero_are_the_same_point():
    minus = {"points": (-0.0, -31.5, 0.0, -0.0), "source_primitive_ids": ("n1",)}
    plus = {"points": (0.0, -31.5, 0.0, 0.0), "source_primitive_ids": ("n1",)}
    ids = [wall_lineage_identities([fake_wall("w", "e")], fake_graph({"e": piece}), tolerance_pt=2.5)["identities"]["w"]
           for piece in (minus, plus)]
    assert ids[0] == ids[1]


def test_short_pieces_are_ignored_and_inputs_are_not_mutated():
    pieces = {"e": LONG, "s": SHORT}
    graph = fake_graph(pieces)
    before = copy.deepcopy(graph)
    with_short = wall_lineage_identities([fake_wall("w", "e", "s")], graph, tolerance_pt=2.5)
    without = wall_lineage_identities([fake_wall("w", "e")], graph, tolerance_pt=2.5)
    assert with_short["identities"]["w"] == without["identities"]["w"] is not None
    assert graph == before


def test_a_graph_without_retained_pieces_is_refused():
    with pytest.raises(ValueError):
        wall_lineage_identities([], {"edges": []}, tolerance_pt=2.5)
    with pytest.raises(ValueError):
        wall_lineage_identities([], fake_graph({}), tolerance_pt=float("nan"))


# Host identity at the opening: a gap from x=100 to x=130 between two wall pieces, with jamb segments at both sides.
GAP = [(100.0, -3.0, 100.0, 3.0), (130.0, -3.0, 130.0, 3.0)]
LEFT = {"points": (40.0, 0.0, 100.0, 0.0), "source_primitive_ids": ("n1",)}
RIGHT = {"points": (130.0, 0.0, 200.0, 0.0), "source_primitive_ids": ("n2",)}


def host(pieces, left=("l",), right=("r",), segments=GAP):
    members = [fake_wall("left", *left), fake_wall("right", *right)]
    return host_jamb_identity(members, fake_graph(pieces), segments, tolerance_pt=2.5)


def test_the_host_identity_survives_a_chain_that_grows_away_from_the_opening():
    short = host({"l": LEFT, "r": RIGHT})
    grown = host({"l": LEFT, "r": RIGHT, "far": {"points": (200.0, 0.0, 300.0, 0.0), "source_primitive_ids": ("n3",)}},
                 right=("r", "far"))
    assert short["identity"] is not None and short["identity"] == grown["identity"]
    assert short["replaces_existing_identity"] is False and short["vetoes"] == {}


def test_another_piece_at_the_jamb_is_another_host():
    other = {"points": (45.0, 0.0, 100.0, 0.0), "source_primitive_ids": ("n1",)}
    assert host({"l": LEFT, "r": RIGHT})["identity"] != host({"l": other, "r": RIGHT})["identity"]


@pytest.mark.parametrize("pieces,left,expected", [
    ({"l": {"points": (40.0, 0.0, 90.0, 0.0), "source_primitive_ids": ("n1",)}, "r": RIGHT}, ("l",), NO_JAMB_PIECE),
    ({"l": LEFT, "r": RIGHT, "up": {"points": (100.0, 0.0, 100.0, 60.0), "source_primitive_ids": ("n4",)}}, ("l", "up"),
     SEVERAL_JAMB_PIECES),
], ids=["none_at_opening", "two_at_opening"])
def test_an_unclear_member_vetoes_the_whole_host(pieces, left, expected):
    result = host(pieces, left=left)
    assert result["identity"] is None and result["vetoes"] == {"left": expected}


def test_both_members_on_one_piece_is_vetoed():
    shared = {"points": (100.0, 0.0, 130.0, 0.0), "source_primitive_ids": ("n1",)}
    result = host({"l": shared, "r": dict(shared)})
    assert result["identity"] is None and set(result["vetoes"].values()) == {SHARED_PIECE}


def test_no_opening_geometry_gives_no_identity():
    assert host({"l": LEFT, "r": RIGHT}, segments=[])["identity"] is None


def test_members_from_two_viewports_get_no_identity():
    members = [fake_wall("left", "l"),
               SimpleNamespace(candidate_id="right", viewport_id="vp2", face_a_segment_ids=("r",), face_b_segment_ids=None)]
    result = host_jamb_identity(members, fake_graph({"l": LEFT, "r": RIGHT}), GAP, tolerance_pt=2.5)
    assert result["identity"] is None and result["vetoes"] == {}


def test_a_piece_beyond_the_jamb_line_is_not_at_the_opening():
    above = {"points": (40.0, 20.0, 100.0, 20.0), "source_primitive_ids": ("n9",)}
    assert host({"l": above, "r": RIGHT})["vetoes"] == {"left": NO_JAMB_PIECE}
