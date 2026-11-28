"""The plain-float shortcut of the room-edge check answers as the general check does."""

import math
import random

import numpy as np

from pb_source_room_face_authority import _edge_contains_edge, _finite_source_edge


def _general(value):
    try:
        if len(value) != 2 or any(len(point) != 2 for point in value):
            return False
        first, second = (tuple(float(c) for c in point) for point in value)
        if not all(math.isfinite(c) for point in (first, second) for c in point):
            return False
        return math.isfinite(math.hypot(second[0] - first[0], second[1] - first[1]))
    except (TypeError, ValueError, OverflowError):
        return False


_ODD = [0.0, -0.0, 1.5, float("nan"), float("inf"), -float("inf"), 1.7e308, -1.7e308, 3, True, "4", "x", None,
        np.float64(2.0), np.float32("nan"), 10 ** 400]


def _coordinate(rng):
    return rng.uniform(-1e4, 1e4) if rng.random() < 0.6 else rng.choice(_ODD)


def _edge(rng):
    point = lambda: tuple(_coordinate(rng) for _ in range(rng.choice((2, 2, 2, 2, 1, 3))))
    points = [point() for _ in range(rng.choice((2, 2, 2, 2, 1, 3)))]
    shape = rng.random()
    if shape < 0.8:
        return tuple(points)
    if shape < 0.9:
        return points
    return tuple(list(p) for p in points)


def test_same_answer_for_every_shape():
    rng = random.Random(20261126)
    answers = set()
    for _ in range(40000):
        edge = _edge(rng)
        assert _finite_source_edge(edge) == _general(edge), edge
        answers.add(_finite_source_edge(edge))
    assert answers == {True, False}
    for odd in (None, 5, "ab", ((1.0, 2.0), None), ((1.0, 2.0), "34"), (("1", "2"), ("3", "4"))):
        assert _finite_source_edge(odd) == _general(odd), odd


def test_containment_is_unchanged_for_float_and_list_edges():
    parent = ((0.0, 0.0), (10.0, 0.0))
    child = ((2.0, 0.0), (5.0, 0.0))
    assert _edge_contains_edge(parent, child)
    assert _edge_contains_edge([[0, 0], [10, 0]], [[2, 0], [5, 0]])
    assert not _edge_contains_edge(parent, ((2.0, 0.0), (float("nan"), 0.0)))
