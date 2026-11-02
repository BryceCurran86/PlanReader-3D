"""The paint-order rule that decides which unstroked fills are a backdrop: pure, order-, scale- and position-free."""
from __future__ import annotations

import copy
import random
from dataclasses import replace

import pytest

import pb_callout_strip_whole_aperture_correspondence_shadow as shadow

EQ = 0.06


def stroke(box, sequence):
    return shadow.InkItem(tuple(box), sequence, True)


def fill(path_index, sequence, box):
    return shadow.FillPath(path_index, sequence, tuple(box))


def backdrop(fills, strokes, eq=EQ):
    return shadow.backdrop_fill_paths(fills, strokes, eq)


BOX = (100.0, 195.0, 304.0, 205.0)


def test_a_fill_painted_before_every_stroke_it_touches_is_a_backdrop():
    assert backdrop([fill(1, 5, BOX)], [stroke((100.0, 200.0, 160.0, 200.0), 10), stroke((100.0, 195.0, 100.0, 205.0), 11)]) == {1}


@pytest.mark.parametrize("sequence", [10, 9, 0, -3])
def test_a_stroke_painted_at_or_before_the_fill_means_it_may_be_covered(sequence):
    strokes = [stroke((100.0, 200.0, 160.0, 200.0), 10), stroke((120.0, 196.0, 140.0, 196.0), sequence)]
    assert backdrop([fill(1, 10, BOX)], strokes) == frozenset()


def test_one_earlier_stroke_among_many_later_ones_is_enough_to_keep_the_fill():
    strokes = [stroke((101.0 + k, 200.0, 102.0 + k, 200.0), 50 + k) for k in range(40)] + [stroke((250.0, 200.0, 260.0, 200.0), 4)]
    assert backdrop([fill(1, 5, BOX)], strokes) == frozenset()


def test_a_stroke_with_an_unreadable_position_counts_as_before():
    assert backdrop([fill(1, 5, BOX)], [stroke((120.0, 200.0, 140.0, 200.0), None), stroke((130.0, 200.0, 150.0, 200.0), 9)]) == frozenset()


def test_a_fill_with_an_unreadable_position_is_never_a_backdrop():
    assert backdrop([fill(1, None, BOX)], [stroke((120.0, 200.0, 140.0, 200.0), 9)]) == frozenset()


def test_a_fill_that_no_stroke_touches_covers_nothing_and_is_left_as_it_is():
    assert backdrop([fill(1, 5, BOX)], [stroke((500.0, 500.0, 600.0, 500.0), 9)]) == frozenset()
    assert backdrop([fill(1, 5, BOX)], []) == frozenset()


def test_unstroked_items_in_the_stroke_list_are_ignored():
    items = [shadow.InkItem((120.0, 200.0, 140.0, 200.0), 1, False), stroke((130.0, 200.0, 150.0, 200.0), 9)]
    assert backdrop([fill(1, 5, BOX)], items) == {1}


@pytest.mark.parametrize("gap, touches", [(0.0, True), (0.05, True), (0.07, False), (3.0, False)])
def test_touching_uses_the_equality_tolerance_on_both_axes(gap, touches):
    near = stroke((304.0 + gap, 200.0, 320.0, 200.0), 9)
    later_only = backdrop([fill(1, 5, BOX)], [near])
    assert (later_only == {1}) is touches


def test_only_the_touching_strokes_decide_each_fill_independently():
    fills = [fill(1, 5, BOX), fill(2, 5, (400.0, 195.0, 500.0, 205.0))]
    strokes = [stroke((120.0, 200.0, 140.0, 200.0), 9), stroke((420.0, 200.0, 440.0, 200.0), 3)]
    assert backdrop(fills, strokes) == {1}


def test_fills_and_strokes_spanning_many_grid_cells_are_handled():
    long_fill = fill(1, 2, (0.0, 0.0, 2000.0, 1500.0))
    late = [stroke((k * 37.0, 17.0 * k % 1400, k * 37.0 + 30.0, 17.0 * k % 1400), 100 + k) for k in range(60)]
    assert backdrop([long_fill], late) == {1}
    assert backdrop([long_fill], late + [stroke((1999.0, 1499.0, 2005.0, 1499.0), 1)]) == frozenset()
    page_wide = stroke((0.0, 700.0, 2000.0, 700.0), 1)
    assert backdrop([long_fill], late + [page_wide]) == frozenset()


def _scenario():
    fills = [fill(1, 5, BOX), fill(2, 7, (130.0, 190.0, 180.0, 210.0)), fill(3, 50, (100.0, 195.0, 304.0, 205.0))]
    strokes = [stroke((100.0, 200.0, 160.0, 200.0), 10), stroke((100.0, 195.0, 100.0, 205.0), 11),
               stroke((150.0, 196.0, 170.0, 196.0), 6), stroke((600.0, 600.0, 700.0, 600.0), 1)]
    return fills, strokes


def test_the_scenario_has_the_mixed_outcome_the_invariance_tests_rely_on():
    fills, strokes = _scenario()
    assert backdrop(fills, strokes) == {1}


def _move(box, scale, dx, dy, swap):
    x0, y0, x1, y1 = box
    if swap:
        x0, y0, x1, y1 = y0, x0, y1, x1
    return (x0 * scale + dx, y0 * scale + dy, x1 * scale + dx, y1 * scale + dy)


@pytest.mark.parametrize("scale, dx, dy, swap", [(1.0, 1000.0, 0.0, False), (1.0, -37.5, 250.0, False), (2.0, 0.0, 0.0, False),
                                                  (0.5, 8.0, -4.0, False), (1.0, 0.0, 0.0, True), (2.0, 12.5, 3.0, True)])
def test_translation_quarter_turn_and_uniform_scale_do_not_change_the_result(scale, dx, dy, swap):
    fills, strokes = _scenario()
    moved_fills = [replace(f, box=_move(f.box, scale, dx, dy, swap)) for f in fills]
    moved_strokes = [replace(s, box=_move(s.box, scale, dx, dy, swap)) for s in strokes]
    assert backdrop(moved_fills, moved_strokes, EQ * scale) == backdrop(*_scenario())


def test_input_order_does_not_change_the_result():
    fills, strokes = _scenario()
    rng = random.Random(11)
    for _ in range(8):
        assert backdrop(rng.sample(fills, len(fills)), rng.sample(strokes, len(strokes))) == {1}


def test_splitting_a_stroke_into_pieces_painted_together_does_not_change_the_result():
    fills, strokes = _scenario()
    pieces = []
    for item in strokes:
        x0, y0, x1, y1 = item.box
        mid = (x0 + x1) / 2.0
        pieces += [replace(item, box=(x0, y0, mid, y1)), replace(item, box=(mid, y0, x1, y1))]
    assert backdrop(fills, pieces) == backdrop(fills, strokes)


def test_unrelated_content_and_a_wider_page_do_not_change_the_result():
    fills, strokes = _scenario()
    noise = [stroke((5000.0 + k, 5000.0, 5001.0 + k, 5000.0), 1 + k) for k in range(50)]
    far_fills = [fill(90 + k, 3, (8000.0 + 10 * k, 8000.0, 8005.0 + 10 * k, 8005.0)) for k in range(10)]
    assert backdrop(fills + far_fills, strokes + noise) == backdrop(fills, strokes)


def test_replay_is_deterministic_and_nothing_is_mutated():
    fills, strokes = _scenario()
    before = copy.deepcopy((fills, strokes))
    first, second = backdrop(fills, strokes), backdrop(fills, strokes)
    assert first == second and (fills, strokes) == before


def test_the_result_is_a_frozenset_of_path_indices():
    fills, strokes = _scenario()
    assert type(backdrop(fills, strokes)) is frozenset
