"""Source-free parity tests for bounded cross-view translation voting."""
from collections import Counter
import random

import pytest

from pb_source_cross_view_floor_correspondence_shadow import LineIndex, _shift_votes


def exhaustive(src, dst, topn, limit):
    votes = {"H": Counter(), "V": Counter()}
    for axis in "HV":
        for k, intervals in src[axis].items():
            source_total = sum(hi - lo for lo, hi in intervals)
            for target in dst.keys[axis]:
                delta = target - k
                if abs(delta) > limit:
                    continue
                target_total = sum(hi - lo for lo, hi in dst.lines[axis][target])
                votes[axis][round(delta / 0.04) * 0.04] += min(source_total, target_total)
    return tuple(
        [x for x, _ in sorted(votes[axis].items(), key=lambda kv: (-kv[1], kv[0]))[:topn]]
        for axis in "VH"
    )


@pytest.mark.parametrize("limit", [0.0, 0.04, 10.0, 3000.0, 100000.0])
@pytest.mark.parametrize("topn", [1, 30, 1000])
def test_indexed_votes_match_exhaustive_on_sparse_and_dense_coordinates(limit, topn):
    rng = random.Random(3128)
    source = {}
    target = {}
    for axis in "HV":
        source[axis] = {
            round(rng.uniform(-10000, 10000), 2): [(0, rng.uniform(3, 100))]
            for _ in range(45)
        }
        target[axis] = {
            round(rng.uniform(-10000, 10000), 2): [(0, rng.uniform(3, 100))]
            for _ in range(90)
        }
        for x in (0.0, 0.04, 0.08, 3000.0, -3000.0):
            source[axis][x] = [(0, 8), (10, 20)]
            target[axis][x] = [(0, 7)]
    index = LineIndex(target)
    assert _shift_votes(source, index, topn, limit) == exhaustive(source, index, topn, limit)


def test_rounded_inclusive_endpoint_is_not_lost_by_cancellation():
    source = {"H": {3000.0: [(0, 100)]}, "V": {-3000.0: [(0, 100)]}}
    target = {
        "H": {-1e-13: [(0, 100)], -1e-10: [(0, 200)], 6000.0: [(0, 50)]},
        "V": {1e-13: [(0, 100)], 1e-10: [(0, 200)], -6000.0: [(0, 50)]},
    }
    index = LineIndex(target)
    assert _shift_votes(source, index, 30, 3000.0) == exhaustive(source, index, 30, 3000.0)
    assert _shift_votes(source, index, 30, 3000.0) == ([3000.0, -3000.0], [-3000.0, 3000.0])
