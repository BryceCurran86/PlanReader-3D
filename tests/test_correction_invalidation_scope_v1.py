"""What a correction invalidates (C08, #4764 7201721302): current behaviour a cache may rely on.

Synthetic only. The tracer offers its pieces to ``barrier_view`` before forming rooms; these tests pin what a cache of
those pieces may reuse for a later correction packet, and which rooms a mark can change.
"""
from __future__ import annotations

import random

import pytest

from pb_user_assisted_review_topology import BarrierRecorder, plan_review
from tests.test_user_assisted_review_topology_v1 import _bar, _mark, _missing_wall_room, _packet, _trace


def _second_room(dx=500):
    """A closed 200 x 150 room of 6 pt walls, far to the right of the first."""
    return [_bar(100 + dx, 100, 300 + dx, 106), _bar(100 + dx, 106, 106 + dx, 250), _bar(294 + dx, 106, 300 + dx, 250),
            _bar(106 + dx, 244, 294 + dx, 250)]


ROWS = _missing_wall_room() + _second_room()
GAP_WALL = _mark("a", "internal_wall", (160, 247), (190, 247))
REJECT_SECOND = _mark("r", "reject_candidate", (790, 175), (810, 175))  # across the second room's right wall
FINISH = _mark("f", "boundary", (600, 175), (800, 175))
EXCLUSION = _mark("e", "exclusion", (650, 130), (750, 130), (750, 220))
PACKETS = [(GAP_WALL,), (REJECT_SECOND,), (GAP_WALL, REJECT_SECOND), (FINISH, EXCLUSION), (GAP_WALL, FINISH)]


def _canonical(points):
    """The same room however its corner list starts or turns."""
    pts = tuple(points)
    turns = [seq[i:] + seq[:i] for seq in (pts, pts[::-1]) for i in range(len(seq))]
    return min(turns)


def _rooms(result):
    return sorted(_canonical(ring.polygon_pdf_pts) for ring in result.rings)


def _pieces(view):
    return (
        sorted((strip.path_index, strip.polygon.wkt) for strip in view.strips),
        sorted((index, polygon.wkt) for index, polygon in view.other_fills),
        tuple(view.closures),
        sorted((cid, rect.wkt) for cid, rect in view.closure_rects),
        tuple(view.unresolved_gaps),
    )


def _offered(rows, then=None):
    seen = []

    def view(offered):
        seen.append(_pieces(offered))
        return offered if then is None else then(offered)

    result = _trace(rows, barrier_view=view)
    return seen, result


def _recorded(rows):
    recorder = BarrierRecorder()
    automatic = _trace(rows, barrier_view=recorder)
    return recorder, automatic


@pytest.mark.parametrize("marks", PACKETS, ids=lambda marks: "".join(m.correction_id for m in marks))
def test_the_pieces_offered_to_the_marks_do_not_depend_on_them(marks):
    recorder, _automatic = _recorded(ROWS)
    without, _ = _offered(ROWS)
    with_marks, _ = _offered(ROWS, then=plan_review(_packet(*marks), recorder))
    assert with_marks == without


def test_pieces_recorded_once_serve_every_later_packet_including_undo():
    recorder, _automatic = _recorded(ROWS)
    strips_before = dict(recorder.strips)
    for marks in PACKETS + [(GAP_WALL,)]:  # the last one undoes the second mark of an earlier packet
        reused = _trace(ROWS, barrier_view=plan_review(_packet(*marks), recorder))
        fresh_recorder, _ = _recorded(ROWS)
        fresh = _trace(ROWS, barrier_view=plan_review(_packet(*marks), fresh_recorder))
        assert _rooms(reused) == _rooms(fresh), [m.correction_id for m in marks]
    assert recorder.strips == strips_before  # applying plans never changes the recorded pieces


def test_marks_that_are_not_barriers_leave_the_rooms_as_they_were():
    recorder, automatic = _recorded(ROWS)
    marked = _trace(ROWS, barrier_view=plan_review(_packet(FINISH, EXCLUSION), recorder))
    assert _rooms(marked) == _rooms(automatic)


@pytest.mark.parametrize("marks, changed", [((GAP_WALL,), "gained"), ((REJECT_SECOND,), "lost")])
def test_a_mark_changes_only_the_room_it_touches(marks, changed):
    recorder, automatic = _recorded(ROWS)
    assert len(automatic.rings) == 1  # only the closed second room
    marked = _trace(ROWS, barrier_view=plan_review(_packet(*marks), recorder))
    if changed == "gained":
        assert len(marked.rings) == 2
        assert set(_rooms(automatic)) <= set(_rooms(marked))
    else:
        assert marked.rings == ()


@pytest.mark.xfail(strict=True, reason="room record ids hash the corner list as shapely returns it; #4764 report, no fix yet")
def test_an_untouched_room_keeps_its_record_id_after_a_mark_elsewhere():
    recorder, automatic = _recorded(ROWS)
    marked = _trace(ROWS, barrier_view=plan_review(_packet(GAP_WALL), recorder))
    assert {ring.record_id for ring in automatic.rings} <= {ring.record_id for ring in marked.rings}


@pytest.mark.xfail(strict=True, reason="the same corner-order dependence; reordering input lines changes the ids")
def test_room_record_ids_do_not_depend_on_input_order():
    ids = {ring.record_id for ring in _trace(ROWS).rings}
    for seed in range(8):
        rows = list(ROWS)
        random.Random(seed).shuffle(rows)
        assert {ring.record_id for ring in _trace(rows).rings} == ids


def test_the_order_of_marks_does_not_matter():
    recorder, _automatic = _recorded(ROWS)
    forward = plan_review(_packet(GAP_WALL, REJECT_SECOND, FINISH), recorder)
    backward = plan_review(_packet(FINISH, REJECT_SECOND, GAP_WALL), recorder)
    assert forward == backward
