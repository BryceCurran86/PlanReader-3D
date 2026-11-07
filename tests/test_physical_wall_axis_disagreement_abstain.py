"""A dominant-axis disagreement cannot prove two source-related walls distinct.

These are source-neutral safety cases. They do not create an installed wall,
grant metric/customer authority or re-sign any historical original quantity.
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallIdentity,
    classify_physical_wall_pair,
    resolve_physical_wall_equivalence,
)


def _wall(wall_id, path, primitives):
    return PhysicalWallIdentity(
        wall_candidate_id=wall_id,
        viewport_id="source-viewport",
        candidate_identity_id=f"candidate-{wall_id}",
        path_fingerprint=tuple(path),
        source_primitive_ids=tuple(primitives),
        edge_ids=(f"edge-{wall_id}",),
        status=EvidenceResolutionStatus.CORROBORATED,
    )


@pytest.mark.parametrize(
    "left_primitives,right_primitives",
    [
        (("native-a",), ("native-a",)),
        (("native-a", "native-b"), ("native-a", "native-c")),
    ],
    ids=("equal-ancestry", "partly-shared-ancestry"),
)
def test_cross_axis_intervals_with_shared_source_abstain_in_both_orders(
    left_primitives, right_primitives
):
    # Both paths trace almost the same diagonal physical run. A slight
    # endpoint difference reverses the dominant-axis label: h versus v.
    # x and y interval endpoints are not comparable disjointness witnesses.
    left = _wall(
        "a", ((0.0, 0.0), (100.0, 99.0)), left_primitives
    )
    right = _wall(
        "b", ((0.0, 0.0), (99.0, 100.0)), right_primitives
    )

    for first, second in ((left, right), (right, left)):
        assert classify_physical_wall_pair(
            first, second
        ) is PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

    result = resolve_physical_wall_equivalence((left, right))
    assert set(result.ambiguous_wall_ids) == {"a", "b"}
    assert set(result.abstained_wall_ids) == {"a", "b"}
    assert result.representative_wall_ids == ()
    assert result.pair_classifications == (
        ("a", "b", PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value),
    )


def test_same_axis_disjoint_ancestry_is_still_proven_distinct():
    left = _wall("a", ((0.0, 0.0), (20.0, 0.0)), ("native-a",))
    right = _wall("b", ((40.0, 0.0), (60.0, 0.0)), ("native-a",))
    assert classify_physical_wall_pair(
        left, right
    ) is PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS


def test_same_path_and_equal_ancestry_remain_same_wall():
    path = ((0.0, 0.0), (20.0, 0.0))
    left = _wall("a", path, ("native-a",))
    right = _wall("b", path, ("native-a",))
    assert classify_physical_wall_pair(
        left, right
    ) is PhysicalEquivalenceClass.SAME_PHYSICAL_WALL


def test_cross_axis_without_shared_source_does_not_gain_identity():
    left = _wall("a", ((0.0, 0.0), (100.0, 99.0)), ("native-a",))
    right = _wall("b", ((0.0, 0.0), (99.0, 100.0)), ("native-b",))
    assert classify_physical_wall_pair(
        left, right
    ) is PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
