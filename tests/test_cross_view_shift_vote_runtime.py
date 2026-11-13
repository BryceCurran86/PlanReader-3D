"""Registration contract/performance checks; no quantity authority is granted."""
from __future__ import annotations

import copy

import pytest

from pb_source_cross_view_floor_correspondence_shadow import LineIndex, _shift_votes


def _lines():
    return (
        {"H": {0.0: [(0.0, 3.0), (4.0, 8.0)], 10.0: [(1.0, 3.0)]},
         "V": {20.0: [(0.0, 4.0)]}},
        {"H": {5.0: [(0.0, 2.0), (3.0, 4.0)], 15.0: [(0.0, 1.0)]},
         "V": {22.0: [(0.0, 2.0)], 26.0: [(0.0, 1.0)]}},
    )


def test_weighted_registration_votes_keep_full_order_without_input_mutation():
    src, dst = _lines()
    before = copy.deepcopy((src, dst))
    assert _shift_votes(src, LineIndex(dst), 30) == ([2.0, 6.0], [5.0, -5.0, 15.0])
    assert (src, dst) == before


@pytest.mark.parametrize("shift", [-10000.0, -2.25, 0.0, 2030.5])
def test_common_translation_keeps_votes_and_ties(shift):
    src, dst = _lines()
    def moved(lines):
        return {axis: {key + shift: [(lo + shift, hi + shift) for lo, hi in intervals]
                       for key, intervals in rows.items()} for axis, rows in lines.items()}
    assert _shift_votes(moved(src), LineIndex(moved(dst)), 30) == ([2.0, 6.0], [5.0, -5.0, 15.0])


def test_vote_limit_topn_and_zero_content_keep_original_contract():
    src, dst = _lines()
    assert _shift_votes(src, LineIndex(dst), 1) == ([2.0], [5.0])
    assert _shift_votes(src, LineIndex(dst), 30, limit=4.0) == ([2.0], [])
    assert _shift_votes(src, LineIndex(dst), 0) == ([], [])
    assert _shift_votes({"H": {}, "V": {}}, LineIndex(dst), 30) == ([], [])


def test_equal_vote_weights_keep_numeric_translation_tie_break():
    src = {"H": {0.0: [(0.0, 4.0)]}, "V": {0.0: [(0.0, 4.0)]}}
    dst = {"H": {5.0: [(0.0, 1.0)], -5.0: [(0.0, 1.0)]},
           "V": {5.0: [(0.0, 1.0)], -5.0: [(0.0, 1.0)]}}
    assert _shift_votes(src, LineIndex(dst), 30) == ([-5.0, 5.0], [-5.0, 5.0])


def test_reused_index_observes_destination_changes_between_calls():
    src, dst = _lines()
    index = LineIndex(dst)
    assert _shift_votes(src, index, 30)[0] == [2.0, 6.0]
    dst["V"][26.0] = [(0.0, 20.0)]
    assert _shift_votes(src, index, 30)[0] == [6.0, 2.0]


def test_destination_interval_work_does_not_multiply_with_source_coordinate_count():
    class CountedIntervals(list):
        visits = 0
        def __iter__(self):
            self.visits += 1
            return super().__iter__()

    intervals = CountedIntervals([(float(i), float(i + 0.5)) for i in range(100)])
    src = {"H": {float(i): [(0.0, 10.0)] for i in range(200)}, "V": {}}
    dst = {"H": {10.0: intervals}, "V": {}}
    assert _shift_votes(src, LineIndex(dst), 1)[1]
    assert intervals.visits == 1
