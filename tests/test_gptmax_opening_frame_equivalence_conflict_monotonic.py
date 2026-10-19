"""Exact W4 wall-pair equivalence is not last-write-wins.

Source-neutral original-record-shaped tuples only. A repeated wall pair that
contradicts an earlier authenticated physical classification stays AMBIGUOUS
for every ordering and can never unblock a physical opening host frame.
"""
from itertools import permutations
from types import SimpleNamespace

import pytest

from pb_opening_host_frame_authority import _pair_lookup
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class


SAME = Class.SAME_PHYSICAL_WALLS if hasattr(Class, "SAME_PHYSICAL_WALLS") else Class.SAME_PHYSICAL_WALL
DISTINCT = Class.DISTINCT_PHYSICAL_WALLS
AMBIGUOUS = Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def _lookup(rows):
    return _pair_lookup(SimpleNamespace(pair_classifications=rows))


@pytest.mark.parametrize("classes", [
    (SAME.value, DISTINCT.value, SAME.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
    (AMBIGUOUS.value, SAME.value, SAME.value),
    (AMBIGUOUS.value, DISTINCT.value, DISTINCT.value),
    (SAME.value, "unknown_source_role", SAME.value),
])
def test_wall_pair_conflicts_stay_ambiguous_across_all_input_orders(classes):
    for order in set(permutations(classes)):
        rows = [("wall_a", "wall_b", label) for label in order]
        result = _lookup(rows)
        assert result == {("wall_a", "wall_b"): AMBIGUOUS}


@pytest.mark.parametrize("classification", [SAME, DISTINCT, AMBIGUOUS])
def test_repeated_identical_wall_pair_does_not_invent_an_opposite_class(classification):
    rows = [
        ("wall_b", "wall_a", classification.value),
        ("wall_a", "wall_b", classification.value),
        ("wall_b", "wall_a", classification.value),
    ]
    assert _lookup(rows) == {("wall_a", "wall_b"): classification}


def test_unrelated_wall_pair_never_changes_when_first_pair_conflicts():
    rows = [
        ("wall_a", "wall_b", SAME.value),
        ("wall_c", "wall_d", DISTINCT.value),
        ("wall_b", "wall_a", DISTINCT.value),
        ("wall_a", "wall_b", SAME.value),
    ]
    assert _lookup(rows) == {
        ("wall_a", "wall_b"): AMBIGUOUS,
        ("wall_c", "wall_d"): DISTINCT,
    }


def test_ambiguous_relation_is_retained_not_treated_as_positive_distinct():
    contradiction = [
        ("aligned_competitor", "host_component", DISTINCT.value),
        ("host_component", "aligned_competitor", SAME.value),
        ("aligned_competitor", "host_component", DISTINCT.value),
    ]
    classification = _lookup(contradiction)[
        ("aligned_competitor", "host_component")
    ]
    assert classification is AMBIGUOUS
    assert classification is not Class.DISTINCT_PHYSICAL_WALLS


def test_pair_lookup_never_mutates_original_issuer_rows():
    rows = [
        ("left", "right", SAME.value),
        ("right", "left", DISTINCT.value),
        ("right", "left", SAME.value),
    ]
    original = list(rows)
    assert _lookup(rows) == {("left", "right"): AMBIGUOUS}
    assert rows == original
