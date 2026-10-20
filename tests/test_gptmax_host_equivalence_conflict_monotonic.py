"""Source-closed G17 host membership cannot recover a wall-pair contradiction."""
from __future__ import annotations

from itertools import permutations
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_binding_authority import (
    HOST_EQUIVALENCE_AMBIGUOUS,
    _normalize_role_candidates,
    _pair_lookup,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class
from test_raster_opening_split_centerline_host import _record

SAME = Class.SAME_PHYSICAL_WALL
DISTINCT = Class.DISTINCT_PHYSICAL_WALLS
UNKNOWN = Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def _source_equivalence(rows, groups=()):
    return SimpleNamespace(
        pair_classifications=tuple(rows),
        equivalence_groups=groups,
    )


@pytest.mark.parametrize("classes", [
    (SAME.value, DISTINCT.value, SAME.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
    (UNKNOWN.value, DISTINCT.value, DISTINCT.value),
    (SAME.value, "malformed_producer_class", SAME.value),
    (DISTINCT.value, None, DISTINCT.value),
])
def test_conflicting_original_pair_issuer_order_cannot_restore_host_class(classes):
    for order in set(permutations(classes)):
        original = tuple(("left", "right", label) for label in order)
        first = _pair_lookup(_source_equivalence(original))
        reverse = _pair_lookup(_source_equivalence(tuple(reversed(original))))
        assert first == reverse == {("left", "right"): UNKNOWN}


@pytest.mark.parametrize("positive", (SAME, DISTINCT, UNKNOWN))
def test_identical_issuer_replays_remain_unchanged(positive):
    rows = (("left", "right", positive.value),
            ("right", "left", positive.value))
    assert _pair_lookup(_source_equivalence(rows)) == {
        ("left", "right"): positive
    }


def test_unrelated_wall_pairs_preserve_independent_distinctness():
    rows = (
        ("left", "right", SAME.value),
        ("other_a", "other_b", DISTINCT.value),
        ("right", "left", DISTINCT.value),
        ("left", "right", SAME.value),
    )
    snapshot = tuple(rows)
    actual = _pair_lookup(_source_equivalence(rows))
    assert actual == {
        ("left", "right"): UNKNOWN,
        ("other_a", "other_b"): DISTINCT,
    }
    assert rows == snapshot


@pytest.mark.parametrize("order", [
    (SAME.value, DISTINCT.value, SAME.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
])
def test_real_host_role_normalizer_abstains_on_conflicted_pair(order):
    """Full consumer must block; unit lookup alone isn't a host safety gate."""
    left = _record("left", start=10.0, end=40.0)
    right = _record("right", start=10.0, end=40.0)
    source = _source_equivalence(
        [("left", "right", c) for c in order],
        groups=(),
    )
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8
    )
    assert status is Status.CONFLICT
    assert selected == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


def test_malformed_single_source_relation_fails_closed_in_host_admission():
    source = _source_equivalence((("left", "right", "untrusted_value"),))
    assert _pair_lookup(source) == {("left", "right"): UNKNOWN}
    left = _record("left", start=10.0, end=40.0)
    right = _record("right", start=10.0, end=40.0)
    status, rows, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8
    )
    assert status is Status.CONFLICT
    assert rows == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons
