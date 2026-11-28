"""Report-only finished-face edge classes for a room ring (synthetic wall-map rows)."""
from __future__ import annotations

import copy

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_ring_finish_face_edge_class_shadow import (
    AMBIGUOUS_FACE,
    DOORWAY,
    NO_CANDIDATE,
    PUBLISHED_FACE,
    UNVERIFIED_JOG,
    ring_finish_face_edge_classes,
)
from pb_ring_wall_identity_map_shadow import (
    AMBIGUOUS_ONLY,
    CLOSURE_EDGE,
    NO_WALL,
    PUBLISHED,
)

BOX = [(0, 0), (100, 0), (100, 80), (0, 80)]
# the same room with an 11 x 2 notch standing into it from the left wall (x = 0)
NOTCHED = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 42), (11, 42), (11, 40), (0, 40)]


def row(kinds):
    return {"edges": [{"kind": kind, "wall_ids": [] if kind in (NO_WALL, CLOSURE_EDGE) else ["w"]} for kind in kinds]}


def run(polygon, kinds, holes=0):
    return ring_finish_face_edge_classes(polygon, row(kinds), hole_count=holes)


def test_a_fully_published_room_with_a_doorway_is_a_candidate():
    result = run(BOX, [PUBLISHED, PUBLISHED, CLOSURE_EDGE, PUBLISHED])
    assert result["status"] is Status.CANDIDATE
    assert result["edge_classes"] == (PUBLISHED_FACE, PUBLISHED_FACE, DOORWAY, PUBLISHED_FACE)
    assert result["finished_face_quantity_authority"] is False
    assert result["length_pt_by_class"] == {DOORWAY: 100.0, PUBLISHED_FACE: 260.0}


@pytest.mark.parametrize("kinds,holes", [([PUBLISHED] * 3 + [AMBIGUOUS_ONLY], 0), ([PUBLISHED] * 3 + [NO_WALL], 0),
                                         ([PUBLISHED] * 4, 1)], ids=["ambiguous", "no_wall", "hole"])
def test_anything_unverified_abstains(kinds, holes):
    result = run(BOX, kinds, holes)
    assert result["status"] is Status.ABSTAINED and result["unverified_interior_obstacles"] == holes


def notch_kinds(leave, along, back):
    #        bottom     right      top        left-above   notch edges        left-below
    return [PUBLISHED, PUBLISHED, PUBLISHED, PUBLISHED, leave, along, back, PUBLISHED]


@pytest.mark.parametrize("turn", [0, 1, 4, 5, 6], ids=lambda t: f"start{t}")
def test_a_notch_with_a_bare_edge_is_one_unverified_jog_from_any_start(turn):
    kinds = notch_kinds(NO_WALL, NO_WALL, AMBIGUOUS_ONLY)
    polygon, kinds = NOTCHED[turn:] + NOTCHED[:turn], kinds[turn:] + kinds[:turn]
    result = run(polygon, kinds)
    assert result["edge_classes"].count(UNVERIFIED_JOG) == 3 and result["status"] is Status.ABSTAINED
    assert result["length_pt_by_class"][UNVERIFIED_JOG] == pytest.approx(24.0)


def test_a_drawn_wall_nib_keeps_its_wall_faces():
    result = run(NOTCHED, notch_kinds(PUBLISHED, PUBLISHED, PUBLISHED))
    assert UNVERIFIED_JOG not in result["edge_classes"] and result["status"] is Status.CANDIDATE
    ambiguous = run(NOTCHED, notch_kinds(AMBIGUOUS_ONLY, AMBIGUOUS_ONLY, AMBIGUOUS_ONLY))
    assert ambiguous["edge_classes"][4:7] == (AMBIGUOUS_FACE,) * 3


def test_a_corner_step_that_does_not_return_is_not_a_jog():
    stepped = [(0, 0), (100, 0), (100, 80), (60, 80), (60, 70), (40, 70), (0, 70)]  # steps in and stays
    result = run(stepped, [PUBLISHED, PUBLISHED, PUBLISHED, NO_WALL, NO_WALL, PUBLISHED, PUBLISHED])
    assert UNVERIFIED_JOG not in result["edge_classes"] and result["edge_classes"][3:5] == (NO_CANDIDATE,) * 2


def test_a_straight_wall_split_into_pieces_is_not_a_jog():
    split = [(0, 0), (100, 0), (100, 80), (0, 80), (0, 60), (0, 50), (0, 40), (0, 30)]
    result = run(split, [PUBLISHED] * 4 + [NO_WALL, PUBLISHED, PUBLISHED, PUBLISHED])
    assert UNVERIFIED_JOG not in result["edge_classes"] and result["edge_classes"][4] == NO_CANDIDATE


@pytest.mark.parametrize("polygon,kinds", [
    # returns to the face line and then bends away from it
    ([(3, 0), (100, 0), (100, 80), (0, 80), (0, 42), (11, 42), (11, 40), (0, 40)],
     [PUBLISHED] * 4 + [NO_WALL, NO_WALL, PUBLISHED, PUBLISHED]),
    # comes back to the same line heading the other way
    ([(0, 50), (0, 60), (11, 60), (11, 40), (0, 40), (0, 30), (-50, 30), (-50, 50)],
     [PUBLISHED, NO_WALL, NO_WALL, PUBLISHED, PUBLISHED, PUBLISHED, PUBLISHED, PUBLISHED]),
    # a doorway recessed in the wall: the middle edge is the closure
    (NOTCHED, [PUBLISHED] * 4 + [NO_WALL, CLOSURE_EDGE, NO_WALL, PUBLISHED]),
], ids=["bends_away", "doubles_back", "recessed_doorway"])
def test_look_alikes_of_a_jog_are_not_joined(polygon, kinds):
    assert UNVERIFIED_JOG not in run(polygon, kinds)["edge_classes"]


def test_mirrored_and_shifted_notch_and_inputs_untouched():
    mirrored = [(500 - x, 300 + y) for x, y in NOTCHED]
    wall_row = row(notch_kinds(NO_WALL, PUBLISHED, PUBLISHED))
    before = copy.deepcopy(wall_row)
    result = ring_finish_face_edge_classes(mirrored + mirrored[:1], wall_row, hole_count=0)
    assert result["edge_classes"][4:7] == (UNVERIFIED_JOG,) * 3 and wall_row == before
    with pytest.raises(ValueError):
        ring_finish_face_edge_classes(BOX, row([PUBLISHED] * 3), hole_count=0)
    with pytest.raises(ValueError):
        run(BOX, [PUBLISHED] * 4, holes=-1)
