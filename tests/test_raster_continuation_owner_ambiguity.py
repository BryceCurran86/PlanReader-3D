from __future__ import annotations

import copy
from itertools import permutations

import numpy as np
import pytest

from pb_physical_opening_authority import _raster_pair_flanks


def _input():
    mass = np.zeros((30, 110), np.uint8)
    mass[10:15, 5:25] = 1
    mass[10:15, 60:95] = 1
    return mass, ((5, 10, 24, 14), (60, 10, 94, 14))


def test_a_unique_source_continuation_owner_keeps_the_existing_positive_pair():
    mass, boxes = _input()
    pairs = _raster_pair_flanks(mass, boxes, dpi=150)
    assert len(pairs) == 1
    assert pairs[0].a == boxes[0] and pairs[0].b == boxes[1]
    assert pairs[0].reasons == ()


def test_multiple_continuation_owners_are_all_retained_without_order_selection():
    mass, boxes = _input()
    competing = (*boxes, (60, 9, 94, 15))
    before = mass.copy()
    expected = None
    for ordering in permutations(competing):
        inputs = copy.deepcopy(ordering)
        pairs = _raster_pair_flanks(mass, ordering, dpi=150)
        assert len(pairs) == 2
        assert {pair.b for pair in pairs} == set(competing[1:])
        assert all("raster_continuation_owner_ambiguous" in pair.reasons for pair in pairs)
        assert pairs == expected if expected is not None else True
        expected = pairs
        assert ordering == inputs
        assert np.array_equal(mass, before)


@pytest.mark.parametrize("padding", [0, 15])
def test_ambiguous_source_owner_is_translation_invariant(padding):
    mass, boxes = _input()
    mass = np.pad(mass, ((padding, padding), (padding, padding)))
    boxes = (*boxes, (60, 9, 94, 15))
    moved = tuple(tuple(value + padding for value in box) for box in boxes)
    pairs = _raster_pair_flanks(mass, moved, dpi=150)
    assert len(pairs) == 2
    assert all("raster_continuation_owner_ambiguous" in pair.reasons for pair in pairs)
