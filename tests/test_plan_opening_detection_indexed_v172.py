"""Differential and scaling gates for indexed legacy opening geometry."""
from __future__ import annotations

import random

import pb_plan_opening_detection_v171 as legacy
import pb_plan_opening_detection_indexed_v172 as indexed


def _random_segments(seed: int, count: int = 70):
    rng = random.Random(seed)
    segments = []
    # Keep a mix of long wall-like, short jamb-like, diagonal, and noise lines.
    for index in range(count):
        mode = index % 7
        if mode in (0, 1):
            horizontal = bool((index + seed) % 2)
            length = rng.uniform(210.0, 700.0)
            x = rng.uniform(-200.0, 1400.0)
            y = rng.uniform(-200.0, 1400.0)
            if horizontal:
                segments.append(legacy.Segment(x, y, x + length, y + rng.uniform(-8.0, 8.0)))
            else:
                segments.append(legacy.Segment(x, y, x + rng.uniform(-8.0, 8.0), y + length))
        elif mode in (2, 3, 4):
            length = rng.uniform(20.0, 170.0)
            angle = rng.choice((0.0, 90.0, 45.0, 135.0)) + rng.uniform(-7.0, 7.0)
            radians = __import__("math").radians(angle)
            x = rng.uniform(-200.0, 1400.0)
            y = rng.uniform(-200.0, 1400.0)
            segments.append(
                legacy.Segment(
                    x,
                    y,
                    x + length * __import__("math").cos(radians),
                    y + length * __import__("math").sin(radians),
                )
            )
        else:
            x1 = rng.uniform(-200.0, 1400.0)
            y1 = rng.uniform(-200.0, 1400.0)
            x2 = x1 + rng.uniform(-350.0, 350.0)
            y2 = y1 + rng.uniform(-350.0, 350.0)
            if x1 == x2 and y1 == y2:
                x2 += 1.0
            segments.append(legacy.Segment(x1, y1, x2, y2))
    return segments


def _words():
    return (
        legacy.TextWord("D01", 95.0, 95.0, 115.0, 105.0),
        legacy.TextWord("W02", 495.0, 295.0, 515.0, 305.0),
        legacy.TextWord("NOTE", 795.0, 795.0, 835.0, 805.0),
    )


def _wall_lines(segments):
    return legacy.detect_wall_lines(segments)


def test_indexed_door_detector_matches_legacy_randomized():
    for seed in range(30):
        segments = _random_segments(seed)
        walls = _wall_lines(segments)
        expected = legacy.detect_door_candidates(
            segments, walls, _words(), page_no=seed + 1
        )
        actual = indexed.detect_door_candidates_indexed(
            segments, walls, _words(), page_no=seed + 1
        )
        assert actual == expected, seed


def test_indexed_gap_detector_matches_legacy_randomized():
    for seed in range(30):
        segments = _random_segments(1000 + seed)
        walls = _wall_lines(segments)
        expected = legacy.detect_gap_candidates(
            segments, walls, _words(), page_no=seed + 1
        )
        actual = indexed.detect_gap_candidates_indexed(
            segments, walls, _words(), page_no=seed + 1
        )
        assert actual == expected, seed


def test_indexed_detectors_match_legacy_with_explicit_scale():
    segments = [
        legacy.Segment(0, 100, 250, 100),
        legacy.Segment(300, 100, 650, 100),
        legacy.Segment(250, 70, 250, 130),
        legacy.Segment(300, 70, 300, 130),
        legacy.Segment(120, 85, 120, 115),
    ]
    walls = _wall_lines(segments)
    words = (legacy.TextWord("D01", 110, 60, 130, 70),)
    scale = {"px_per_m": 100.0, "render_zoom": 2.0}
    assert indexed.detect_door_candidates_indexed(
        segments, walls, words, scale_info=scale, page_no=4
    ) == legacy.detect_door_candidates(
        segments, walls, words, scale_info=scale, page_no=4
    )
    assert indexed.detect_gap_candidates_indexed(
        segments, walls, words, scale_info=scale, page_no=4
    ) == legacy.detect_gap_candidates(
        segments, walls, words, scale_info=scale, page_no=4
    )


def test_gap_index_avoids_all_wall_pairs_for_sparse_sheet(monkeypatch):
    segments = []
    for index in range(400):
        x = float(index * 5000)
        segments.append(legacy.Segment(x, 0.0, x + 300.0, 0.0))
    walls = _wall_lines(segments)

    calls = 0
    original = legacy._segments_parallel

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(legacy, "_segments_parallel", counted)
    result = indexed.detect_gap_candidates_indexed(segments, walls, ())
    assert result == []
    # Historical nested wall pairs would evaluate 79,800 pairs before any
    # filled-gap scan. Sparse indexed geometry should be nowhere near that.
    assert calls < 2000


def test_door_index_avoids_wall_times_all_segments_for_sparse_sheet(monkeypatch):
    segments = []
    for index in range(250):
        x = float(index * 4000)
        segments.append(legacy.Segment(x, 0.0, x + 300.0, 0.0))
        segments.append(legacy.Segment(x + 150.0, 1000.0, x + 150.0, 1040.0))
    walls = _wall_lines(segments)

    calls = 0
    original = legacy._point_segment_distance

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(legacy, "_point_segment_distance", counted)
    result = indexed.detect_door_candidates_indexed(segments, walls, ())
    assert result == []
    # Historical path checks every eligible short segment against every wall.
    assert calls < 2000


def test_skewed_long_gap_broad_phase_does_not_drop_legacy_candidate():
    # Regression for the conservative endpoint radius: b is long and tilted
    # within legacy's 10-degree parallel tolerance.
    a = legacy.Segment(0.0, 0.0, 500.0, 0.0)
    angle = __import__("math").radians(9.0)
    b = legacy.Segment(
        650.0,
        -40.0,
        650.0 + 900.0 * __import__("math").cos(angle),
        -40.0 + 900.0 * __import__("math").sin(angle),
    )
    segments = [a, b]
    walls = [legacy.WallLine(a), legacy.WallLine(b)]
    assert indexed.detect_gap_candidates_indexed(
        segments, walls, ()
    ) == legacy.detect_gap_candidates(segments, walls, ())


def test_indexed_detectors_preserve_input_objects_and_wall_order():
    segments = _random_segments(4242, count=90)
    walls = _wall_lines(segments)
    before_segments = [
        (s.x1, s.y1, s.x2, s.y2, s.drawing_index)
        for s in segments
    ]
    before_walls = [
        (w.segment.x1, w.segment.y1, w.segment.x2, w.segment.y2, w.wall_ref)
        for w in walls
    ]
    indexed.detect_door_candidates_indexed(segments, walls, _words(), page_no=7)
    indexed.detect_gap_candidates_indexed(segments, walls, _words(), page_no=7)
    assert [
        (s.x1, s.y1, s.x2, s.y2, s.drawing_index)
        for s in segments
    ] == before_segments
    assert [
        (w.segment.x1, w.segment.y1, w.segment.x2, w.segment.y2, w.wall_ref)
        for w in walls
    ] == before_walls


def test_indexed_gap_output_order_matches_legacy_under_wall_permutations():
    base = [
        legacy.Segment(0, 0, 220, 0),
        legacy.Segment(300, 0, 620, 0),
        legacy.Segment(0, 200, 260, 200),
        legacy.Segment(340, 200, 700, 200),
        legacy.Segment(1000, 1000, 1400, 1000),
    ]
    import itertools
    for order in itertools.permutations(range(len(base))):
        segments = [base[i] for i in order]
        walls = _wall_lines(segments)
        expected = legacy.detect_gap_candidates(segments, walls, (), page_no=9)
        actual = indexed.detect_gap_candidates_indexed(segments, walls, (), page_no=9)
        assert actual == expected


def test_indexed_door_output_order_matches_legacy_under_segment_permutations():
    wall = legacy.Segment(0, 100, 800, 100)
    leaves = [
        legacy.Segment(150, 85, 150, 115),
        legacy.Segment(350, 85, 350, 115),
        legacy.Segment(550, 85, 550, 115),
    ]
    import itertools
    for order in itertools.permutations(leaves):
        segments = [wall, *order]
        walls = _wall_lines(segments)
        expected = legacy.detect_door_candidates(segments, walls, (), page_no=11)
        actual = indexed.detect_door_candidates_indexed(segments, walls, (), page_no=11)
        assert actual == expected
