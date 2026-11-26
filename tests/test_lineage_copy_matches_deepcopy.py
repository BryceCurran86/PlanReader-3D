"""The lineage copier returns what ``copy.deepcopy`` returns, with nothing shared with the original."""

import copy
import math
import random

import pytest

import pb_wall_room_topology_primitive_lineage as lineage


class _Custom:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return type(other) is _Custom and other.value == self.value


def _value(rng, depth):
    choice = rng.randrange(11 if depth < 4 else 6)
    if choice == 0:
        return rng.choice(["", "wall", "A-WALL", "id_7"])
    if choice == 1:
        return rng.randrange(-5, 500)
    if choice == 2:
        return rng.choice([0.0, -0.0, 1.5, float("inf"), float("nan")])
    if choice == 3:
        return rng.choice([True, False, None])
    if choice == 4:
        return _Custom([rng.random()])  # unknown types go to deepcopy
    if choice == 5:
        return frozenset({rng.randrange(3)})
    if choice in (6, 7):
        return {f"k{i}": _value(rng, depth + 1) for i in range(rng.randrange(4))}
    if choice in (8, 9):
        return [_value(rng, depth + 1) for _ in range(rng.randrange(4))]
    return tuple(_value(rng, depth + 1) for _ in range(rng.randrange(4)))


def _assert_same(copied, expected, original):
    assert type(copied) is type(expected)
    if isinstance(expected, float) and math.isnan(expected):
        assert math.isnan(copied)
        return
    if type(expected) is dict:
        assert list(copied) == list(expected)
        assert copied is not original
        for key in expected:
            _assert_same(copied[key], expected[key], original[key])
    elif type(expected) in (list, tuple):
        assert len(copied) == len(expected)
        if type(expected) is list:
            assert copied is not original
        for item, other, source in zip(copied, expected, original):
            _assert_same(item, other, source)
    else:
        assert copied == expected
        if type(expected) is _Custom:
            assert copied is not original and copied.value is not original.value


def test_copy_matches_deepcopy_on_random_structures():
    rng = random.Random(20261126)
    for _ in range(3000):
        original = {"source_records": [_value(rng, 0) for _ in range(rng.randrange(4))], "extra": _value(rng, 0)}
        _assert_same(lineage.isolated_lineage(original), copy.deepcopy(original), original)


def test_mutating_the_copy_leaves_the_original():
    payload = {"source_primitive_ids": ["a"], "source_records": [{"id": "a", "stroke": [0.0, 0.0], "ids": ("b", [1])}]}
    snapshot = copy.deepcopy(payload)
    copied = lineage.isolated_lineage(payload)
    copied["source_primitive_ids"].append("z")
    copied["source_records"][0]["stroke"][0] = 9.0
    copied["source_records"][0]["ids"][1].append(2)
    assert payload == snapshot


@pytest.mark.parametrize("payload", [None, {}])
def test_missing_lineage_is_the_empty_lineage(payload):
    assert lineage.isolated_lineage(payload) == lineage.empty_lineage()


def test_records_do_not_share_segment_values():
    segment = {"id": "s", "x1": 0.0, "y1": 0.0, "x2": 5.0, "y2": 0.0, "stroke": [0.0, 0.0, 0.0],
               "clip": {"rect": [0, 0, 1, 1]}, "layer": "walls"}
    record = lineage.source_record_from_segment(segment)
    assert record["stroke"] == [0.0, 0.0, 0.0] and record["stroke"] is not segment["stroke"]
    assert record["clip"] == segment["clip"] and record["clip"]["rect"] is not segment["clip"]["rect"]
    merged = lineage.union_lineage({"source_records": [record], "source_primitive_ids": ["s"]})
    assert merged["source_records"] == [record] and merged["source_records"][0] is not record
