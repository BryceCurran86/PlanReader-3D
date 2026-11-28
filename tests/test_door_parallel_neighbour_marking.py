"""The door detector's neighbour search marks exactly the segments that testing every pair would mark."""

import math
import random

import pytest

import pb_plan_opening_detection_indexed_v172 as indexed
import pb_plan_opening_detection_v171 as legacy


def _every_pair(segments, local, marked, *, max_distance):
    for position, left_index in enumerate(local):
        left = segments[left_index]
        for right_index in local[position + 1:]:
            right = segments[right_index]
            if legacy._segments_parallel(left, right) and legacy._segment_distance(left, right) <= max_distance:
                marked.add(id(left))
                marked.add(id(right))


def _short(rng, cx, cy, angle):
    half = rng.uniform(12.5, 70.0)
    ux, uy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
    return legacy.Segment(cx - half * ux, cy - half * uy, cx + half * ux, cy + half * uy)


def test_marked_set_matches_every_pair_on_random_clusters():
    rng = random.Random(20261126)
    marked_total = unmarked_total = 0
    for _ in range(400):
        count = rng.randrange(1, 60)
        spread = rng.choice((40.0, 300.0, 3000.0))
        segments = [
            _short(rng, rng.uniform(0, spread), rng.uniform(0, spread * rng.choice((0.05, 1.0))),
                   rng.choice((0.0, 3.0, 45.0, 90.0, 94.9, 95.2, 178.0)))
            for _ in range(count)
        ]
        if rng.random() < 0.3:
            segments.append(segments[0])  # the same object twice
        local = tuple(rng.sample(range(len(segments)), len(segments)))
        max_distance = rng.choice((0.0, 25.0, 100.0, 400.0))
        expected, actual = set(), set()
        _every_pair(segments, local, expected, max_distance=max_distance)
        indexed._mark_parallel_neighbours(segments, local, actual, max_distance=max_distance)
        assert actual == expected
        marked_total += len(expected)
        unmarked_total += len({id(s) for s in segments} - expected)
    assert marked_total > 2000 and unmarked_total > 2000


def test_partner_exactly_at_the_reach_is_kept():
    a = legacy.Segment(0.0, 0.0, 0.0, 40.0)
    b = legacy.Segment(100.0, 0.0, 100.0, 40.0)
    marked = set()
    indexed._mark_parallel_neighbours([a, b], (1, 0), marked, max_distance=100.0)
    assert marked == {id(a), id(b)}


def test_marks_from_an_earlier_wall_stay():
    segments = [legacy.Segment(0.0, 0.0, 0.0, 40.0), legacy.Segment(5000.0, 0.0, 5000.0, 40.0)]
    marked = {id(segments[0])}
    indexed._mark_parallel_neighbours(segments, (0, 1), marked, max_distance=100.0)
    assert marked == {id(segments[0])}


@pytest.mark.parametrize("scale", [None, {"px_per_m": 56.0, "render_zoom": 1.0}])
def test_dense_sheet_matches_legacy_detector(scale):
    rng = random.Random(7)
    segments = []
    for row in range(6):  # long walls with clusters and lone short leaves beside them
        y = 300.0 * row
        segments.append(legacy.Segment(0.0, y, 1500.0, y))
        for _ in range(60):
            x = rng.choice((rng.uniform(0, 300), rng.uniform(0, 1500)))
            segments.append(_short(rng, x, y + rng.uniform(-25, 25), rng.choice((90.0, 90.0, 85.0, 100.0))))
    walls = legacy.detect_wall_lines(segments)
    words = (legacy.TextWord("D01", 95.0, 95.0, 115.0, 105.0),)
    expected = legacy.detect_door_candidates(segments, walls, words, scale_info=scale, page_no=3)
    assert indexed.detect_door_candidates_indexed(segments, walls, words, scale_info=scale, page_no=3) == expected
    assert expected  # lone leaves survive
    assert len(expected) < 360  # and clustered ones are removed
