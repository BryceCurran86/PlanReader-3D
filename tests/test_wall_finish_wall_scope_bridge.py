from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateScopeResult,
)
from pb_physical_wall_identity import (
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
)
from pb_wall_finish_wall_scope_bridge import (
    WALL_FINISH_SCOPE_BRIDGE_AMBIGUOUS_TARGET,
    _target_group_for_owners,
)


def _equivalence(groups=()):
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id="scope",
        representative_wall_ids=tuple(sorted(group[0] for group in groups if group)),
        abstained_wall_ids=(),
        equivalence_groups=tuple(tuple(group) for group in groups),
        ambiguous_wall_ids=(),
        same_wall_ids=tuple(sorted({v for group in groups for v in group})),
        pair_classifications=(),
        blocking_reasons_by_wall_id={},
    )


def test_exact_raw_owners_in_one_positive_same_group_bridge_to_one_wall() -> None:
    eq = _equivalence((("wall-a", "wall-b"),))
    assert _target_group_for_owners(eq, {"wall-a", "wall-b"}) == (
        "wall-a",
        "wall-b",
    )


def test_exact_raw_owners_in_two_unrelated_groups_abstain() -> None:
    eq = _equivalence((
        ("wall-a", "wall-b"),
        ("wall-c", "wall-d"),
    ))
    assert _target_group_for_owners(eq, {"wall-a", "wall-c"}) == ()


def test_single_exact_raw_owner_does_not_expand_to_nearby_wall() -> None:
    eq = _equivalence(())
    assert _target_group_for_owners(eq, {"wall-a"}) == ("wall-a",)


def test_owner_plus_unrelated_nearby_candidate_cannot_be_ranked_into_one_group() -> None:
    eq = _equivalence(())
    assert _target_group_for_owners(eq, {"wall-a", "wall-b"}) == ()


def test_multiple_exact_owners_must_all_be_members_of_same_positive_group() -> None:
    eq = _equivalence((("wall-a", "wall-b"),))
    assert _target_group_for_owners(eq, {"wall-a", "wall-b", "wall-c"}) == ()
