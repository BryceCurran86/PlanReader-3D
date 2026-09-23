from __future__ import annotations

import random

from pb_accuracy_v13_engines_v145 import (
    _segment_intersection,
    segment_length,
    split_segments_at_intersections,
)


def _same(a, b, tol=1e-6):
    return abs(a[0] - b[0]) <= tol and abs(a[1] - b[1]) <= tol


def _quadratic_reference(segments):
    pts = [[tuple(map(float, s[0])), tuple(map(float, s[1]))] for s in segments]
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            p = _segment_intersection(segments[i], segments[j])
            if p is not None:
                pts[i].append(p)
                pts[j].append(p)

    out = []
    for original, candidates in zip(segments, pts):
        a, b = original
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        denom = dx * dx + dy * dy or 1.0
        unique = []
        for p in candidates:
            if not any(_same(p, q) for q in unique):
                unique.append(p)
        unique.sort(key=lambda p: ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denom)
        for p, q in zip(unique, unique[1:]):
            if segment_length((p, q)) > 1e-7:
                out.append((p, q))
    return out


def test_broadphase_matches_quadratic_reference_on_mixed_geometry() -> None:
    segments = [
        ((0.0, 0.0), (10.0, 0.0)),
        ((5.0, -5.0), (5.0, 5.0)),
        ((10.0, 0.0), (15.0, 5.0)),
        ((20.0, 20.0), (30.0, 30.0)),
        ((20.0, 30.0), (30.0, 20.0)),
        ((40.0, 0.0), (50.0, 0.0)),
        ((40.0, 1.0), (50.0, 1.0)),
    ]
    assert split_segments_at_intersections(segments) == _quadratic_reference(segments)


def test_broadphase_matches_reference_for_deterministic_random_segments() -> None:
    rng = random.Random(20260923)
    segments = []
    for _ in range(120):
        x1 = rng.uniform(-200.0, 200.0)
        y1 = rng.uniform(-200.0, 200.0)
        x2 = x1 + rng.uniform(-40.0, 40.0)
        y2 = y1 + rng.uniform(-40.0, 40.0)
        if abs(x2 - x1) + abs(y2 - y1) < 1e-6:
            x2 += 1.0
        segments.append(((x1, y1), (x2, y2)))

    assert split_segments_at_intersections(segments) == _quadratic_reference(segments)


def test_broadphase_does_not_drop_endpoint_touch_intersections() -> None:
    segments = [
        ((0.0, 0.0), (10.0, 10.0)),
        ((10.0, 10.0), (20.0, 0.0)),
        ((10.0, -5.0), (10.0, 10.0)),
    ]
    assert split_segments_at_intersections(segments) == _quadratic_reference(segments)
