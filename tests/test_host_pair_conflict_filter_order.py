"""Checking group membership first gives the same conflicting pairs as classifying every pair first."""

import random

from pb_opening_host_binding_authority import _source_same_group_distinct_pair_conflicts
from pb_physical_wall_identity import PhysicalEquivalenceClass, PhysicalWallEquivalenceResolution


def _classify_every_pair(equivalence):
    """The previous order of the same two conditions, kept as the reference."""
    groups_by_member = {}
    for index, group in enumerate(equivalence.equivalence_groups):
        for wall_id in group:
            groups_by_member.setdefault(str(wall_id), set()).add(index)
    result = set()
    for left, right, raw in equivalence.pair_classifications:
        try:
            classification = PhysicalEquivalenceClass(raw)
        except (TypeError, ValueError):
            classification = PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE
        if classification is PhysicalEquivalenceClass.SAME_PHYSICAL_WALL:
            continue
        a, b = str(left), str(right)
        if groups_by_member.get(a, set()) & groups_by_member.get(b, set()):
            result.add(tuple(sorted((a, b))))
    return frozenset(result)


def _equivalence(groups, pairs):
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="v", representative_wall_ids=(), abstained_wall_ids=(),
        equivalence_groups=groups, ambiguous_wall_ids=(), same_wall_ids=(),
        pair_classifications=pairs, blocking_reasons_by_wall_id={},
    )


def test_same_conflicts_as_classifying_every_pair():
    rng = random.Random(20261126)
    classes = [member.value for member in PhysicalEquivalenceClass] + ["not-a-class", "", None]
    conflicts = 0
    for _ in range(400):
        walls = [f"w{i}" for i in range(rng.randint(2, 14))]
        groups = tuple(  # groups may overlap, hold one member, or name a wall that has no pair
            tuple(rng.sample(walls, rng.randint(1, min(5, len(walls))))) for _ in range(rng.randint(0, 4))
        )
        pairs = tuple(
            (a, b, rng.choice(classes))
            for a, b in (rng.sample(walls, 2) for _ in range(rng.randint(0, 40)))
        )
        equivalence = _equivalence(groups, pairs)
        expected = _classify_every_pair(equivalence)
        assert _source_same_group_distinct_pair_conflicts(equivalence) == expected
        conflicts += len(expected)
    assert conflicts > 200  # the cases really contain conflicts


def test_reversed_and_malformed_pairs_inside_one_group_conflict():
    groups = (("a", "b", "c"),)
    pairs = (("b", "a", PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value),
             ("a", "c", "broken"),
             ("b", "c", PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value),
             ("a", "z", PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS.value))
    assert _source_same_group_distinct_pair_conflicts(_equivalence(groups, pairs)) == {("a", "b"), ("a", "c")}
    assert _source_same_group_distinct_pair_conflicts(_equivalence((), pairs)) == frozenset()
