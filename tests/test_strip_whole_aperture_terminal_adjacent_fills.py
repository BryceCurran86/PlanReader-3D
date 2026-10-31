"""The coverage rule that decides which fill edges in a terminal set are only pooled by the authority's snap distance."""
from __future__ import annotations

import copy
import random
from dataclasses import replace

import pytest

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow
from strip_whole_aperture_fixture import record

EQ = 0.06
FILL_BOX = (100.96, 196.0, 112.0, 199.0)


def ink(box, sequence, stroked=True):
    return shadow.InkItem(tuple(box), sequence, stroked)


def scenario():
    """One reading whose low terminal set holds a jamb stroke and one edge of a late white rectangle."""
    reading = record((100.0, 304.0), lo=("jamb-lo", "fill-edge"), hi=("jamb-hi",), host=("wall-a",), glazing=("glass-1",))
    ink_by_id = {
        "jamb-lo": ink((100.0, 195.0, 100.0, 205.0), 20), "jamb-hi": ink((304.0, 195.0, 304.0, 205.0), 21),
        "wall-a": ink((20.0, 195.0, 100.0, 195.0), 22), "glass-1": ink((100.0, 200.0, 160.0, 200.0), 23),
        "fill-edge": ink((100.96, 196.0, 100.96, 199.0), 90, stroked=False),
    }
    return [reading], ink_by_id, {"fill-edge": 7}, {7: shadow.FillPath(7, 90, FILL_BOX)}


def adjacent(readings, ink_by_id, fill_path_by_id, fills_by_path, eq=EQ):
    return shadow.terminal_adjacent_fill_paths(readings, ink_by_id, fill_path_by_id, fills_by_path, eq)


def test_a_fill_that_covers_nothing_the_reading_rests_on_is_terminal_adjacent():
    assert adjacent(*scenario()) == {7}


@pytest.mark.parametrize("box", [
    (100.0, 195.0, 100.96, 205.0),          # the fill reaches the jamb
    (95.0, 190.0, 101.0, 199.0),            # the fill reaches a host face painted before it
    (100.5, 196.0, 112.0, 201.0),           # the fill reaches the glazing
])
def test_a_fill_that_overlaps_a_stroke_painted_before_it_is_kept_as_a_possible_mask(box):
    readings, ink_by_id, paths, fills = scenario()
    fills[7] = shadow.FillPath(7, 90, box)
    assert adjacent(readings, ink_by_id, paths, fills) == frozenset()


def test_an_overlapped_stroke_painted_after_the_fill_is_on_top_of_it_and_does_not_count():
    readings, ink_by_id, paths, fills = scenario()
    fills[7] = shadow.FillPath(7, 90, (100.0, 195.0, 100.96, 205.0))
    ink_by_id["jamb-lo"] = ink((100.0, 195.0, 100.0, 205.0), 91)
    ink_by_id["wall-a"] = ink((20.0, 195.0, 100.0, 195.0), 92)
    ink_by_id["glass-1"] = ink((100.0, 200.0, 160.0, 200.0), 93)
    assert adjacent(readings, ink_by_id, paths, fills) == {7}


@pytest.mark.parametrize("gap, kept", [(0.0, True), (0.05, True), (0.07, False), (0.96, False)])
def test_the_touching_distance_is_the_equality_tolerance(gap, kept):
    readings, ink_by_id, paths, fills = scenario()
    # the jamb stroke sits at x = 100.0; the fill's left edge moves away from it by `gap`
    fills[7] = shadow.FillPath(7, 90, (100.0 + gap, 196.0, 112.0, 199.0))
    ink_by_id["glass-1"] = ink((105.0, 200.0, 160.0, 200.0), 23)        # keep the glazing out of reach in this check
    ink_by_id["wall-a"] = ink((20.0, 190.0, 90.0, 190.0), 22)
    assert (adjacent(readings, ink_by_id, paths, fills) == frozenset()) is kept


@pytest.mark.parametrize("change", ["fill_position", "member_position", "no_fill_path", "unknown_member"])
def test_anything_unreadable_or_unproven_keeps_the_fill(change):
    readings, ink_by_id, paths, fills = scenario()
    if change == "fill_position":
        fills[7] = shadow.FillPath(7, None, FILL_BOX)
    elif change == "member_position":
        ink_by_id["jamb-hi"] = ink((100.5, 190.0, 101.5, 210.0), None)       # touches the fill and cannot be placed
    elif change == "no_fill_path":
        fills.clear()                                                         # the producer proved no extent for the path
    else:
        readings = [replace(readings[0], host_face_ids=("wall-a", "never-seen"))]
    assert adjacent(readings, ink_by_id, paths, fills) == frozenset()


def test_a_fill_shared_by_two_readings_is_kept_when_it_could_cover_either_one():
    readings, ink_by_id, paths, fills = scenario()
    second = record((100.0, 200.0), rid="other", lo=("fill-edge",), hi=("jamb-other",), host=(), glazing=())
    ink_by_id["jamb-other"] = ink((100.9, 197.0, 101.5, 198.0), 10)           # painted before the fill, under it
    assert adjacent(readings + [second], ink_by_id, paths, fills) == frozenset()
    ink_by_id["jamb-other"] = ink((300.0, 197.0, 301.0, 198.0), 10)
    assert adjacent(readings + [second], ink_by_id, paths, fills) == {7}


def test_a_fill_that_is_in_no_terminal_set_is_never_returned():
    readings, ink_by_id, paths, fills = scenario()
    ink_by_id["stray"] = ink((500.0, 500.0, 500.0, 510.0), 90, stroked=False)
    paths["stray"] = 8
    fills[8] = shadow.FillPath(8, 90, (500.0, 500.0, 510.0, 510.0))
    assert adjacent(readings, ink_by_id, paths, fills) == {7}


def test_no_readings_means_no_fill_is_terminal_adjacent():
    _, ink_by_id, paths, fills = scenario()
    assert adjacent([], ink_by_id, paths, fills) == frozenset()


def _move(box, scale, dx, dy, swap):
    x0, y0, x1, y1 = box
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    return (x0 * scale + dx, y0 * scale + dy, x1 * scale + dx, y1 * scale + dy)


@pytest.mark.parametrize("scale, dx, dy, swap", [(1.0, 1000.0, 0.0, False), (1.0, -37.5, 250.0, False), (2.0, 0.0, 0.0, False),
                                                  (0.5, 8.0, -4.0, False), (1.0, 0.0, 0.0, True), (2.0, 12.5, 3.0, True)])
def test_translation_quarter_turn_and_uniform_scale_do_not_change_the_result(scale, dx, dy, swap):
    readings, ink_by_id, paths, fills = scenario()
    moved_ink = {k: replace(v, box=_move(v.box, scale, dx, dy, swap)) for k, v in ink_by_id.items()}
    moved_fills = {k: replace(v, box=_move(v.box, scale, dx, dy, swap)) for k, v in fills.items()}
    assert adjacent(readings, moved_ink, paths, moved_fills, EQ * scale) == {7}


def test_input_order_unrelated_content_replay_and_no_mutation():
    readings, ink_by_id, paths, fills = scenario()
    before = copy.deepcopy((readings, ink_by_id, paths, fills))
    expected = adjacent(readings, ink_by_id, paths, fills)
    rng = random.Random(5)
    for _ in range(6):
        order = rng.sample(sorted(ink_by_id), len(ink_by_id))
        shuffled = {k: ink_by_id[k] for k in order}
        assert adjacent(readings, shuffled, paths, fills) == expected
    noise = dict(ink_by_id)
    noise.update({f"n{k}": ink((5000.0 + k, 5000.0, 5001.0 + k, 5000.0), 1 + k) for k in range(40)})
    far = record((5000.0, 5100.0), rid="far", lo=("n1",), hi=("n2",), host=(), glazing=())
    assert adjacent(readings + [far], noise, paths, fills) == expected
    assert adjacent(readings, ink_by_id, paths, fills) == expected
    assert (readings, ink_by_id, paths, fills) == before
    assert type(expected) is frozenset


# ---- the check applied to the readings of the second run ----------------------------------------------------------------
def may_cover(readings, paths, ink_by_id, fills_by_path, eq=EQ):
    return shadow.withheld_fills_may_cover(readings, paths, ink_by_id, fills_by_path, eq)


def test_a_second_run_reading_that_rests_only_on_untouched_ink_is_not_covered():
    readings, ink_by_id, _, fills = scenario()
    assert may_cover(readings, {7}, ink_by_id, fills) is False


@pytest.mark.parametrize("member_box", [(100.0, 195.0, 101.0, 205.0), (105.0, 190.0, 106.0, 198.0)])
def test_a_second_run_reading_resting_on_ink_painted_before_the_fill_and_touched_by_it_is_covered(member_box):
    readings, ink_by_id, _, fills = scenario()
    ink_by_id["jamb-lo"] = ink(member_box, 20)
    assert may_cover(readings, {7}, ink_by_id, fills) is True


def test_ink_painted_after_the_fill_cannot_be_covered_by_it():
    readings, ink_by_id, _, fills = scenario()
    ink_by_id["jamb-lo"] = ink((100.0, 195.0, 101.0, 205.0), 91)
    assert may_cover(readings, {7}, ink_by_id, fills) is False


@pytest.mark.parametrize("change", ["unknown_member", "unreadable_member", "unreadable_fill", "missing_fill"])
def test_anything_unknown_or_unreadable_is_treated_as_possibly_covered(change):
    readings, ink_by_id, _, fills = scenario()
    if change == "unknown_member":
        readings = [replace(readings[0], host_face_ids=("never-seen",))]
    elif change == "unreadable_member":
        ink_by_id["jamb-lo"] = ink((100.0, 195.0, 101.0, 205.0), None)
    elif change == "unreadable_fill":
        fills[7] = shadow.FillPath(7, None, FILL_BOX)
    else:
        fills.clear()
    assert may_cover(readings, {7}, ink_by_id, fills) is True


def test_without_readings_or_withheld_paths_nothing_can_be_covered():
    readings, ink_by_id, _, fills = scenario()
    assert may_cover([], {7}, ink_by_id, fills) is False
    assert may_cover(readings, set(), ink_by_id, fills) is False
