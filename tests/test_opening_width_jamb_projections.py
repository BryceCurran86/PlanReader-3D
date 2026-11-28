"""Reading the jambs once per opening matches the same candidate lines as reading them for every line."""

import random
from types import SimpleNamespace

import pb_opening_dimension_authority as dimension


def _previous(line, jambs, axis):
    jamb_lines = tuple(dimension._line(item) for item in jambs)
    if any(item is None for item in jamb_lines):
        return False
    mids = tuple(dimension._midpoint(item) for item in jamb_lines)
    expected = sorted(dimension._projection(point, axis) for point in mids)
    actual = sorted(dimension._projection(point, axis) for point in dimension._endpoints(line))
    return all(abs(a - b) <= dimension._COORD_TOL for a, b in zip(actual, expected))


def test_same_matches_as_reading_the_jambs_every_time():
    rng = random.Random(20261126)
    matched = 0
    for _ in range(4000):
        x = [rng.uniform(0, 500), rng.uniform(0, 500)]
        jambs = (
            SimpleNamespace(geometry=(x[0], 0.0, x[0], 10.0)),
            SimpleNamespace(geometry=(x[1], 0.0, x[1], rng.choice((10.0, 0.0)))),
        )
        if rng.random() < 0.05:
            jambs = (jambs[0], SimpleNamespace(geometry=(1.0, 2.0, float("nan"), 3.0)))
        offset = rng.choice((0.0, 0.0, dimension._COORD_TOL / 2, dimension._COORD_TOL * 2, 3.0))
        ends = [x[0] + offset, x[1]]
        rng.shuffle(ends)
        line = (ends[0], 40.0, ends[1], 40.0)
        axis = rng.choice(((1.0, 0.0), (-1.0, 0.0), (0.6, 0.8)))
        expected = dimension._jamb_midpoint_projections(jambs, axis)
        actual = expected is not None and dimension._matches_endpoint_set(line, expected, axis)
        assert actual == _previous(line, jambs, axis)
        matched += actual
    assert matched > 300
