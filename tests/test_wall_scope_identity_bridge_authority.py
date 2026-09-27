from __future__ import annotations

from types import SimpleNamespace

from pb_wall_scope_identity_bridge_authority import _resolve_exact_target_group


def _record(wall_id: str, *raw_ids: str):
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        physical_identity=SimpleNamespace(source_primitive_ids=tuple(raw_ids)),
    )


def _scope(records, *, groups=(), reps=()):
    return SimpleNamespace(
        records=tuple(records),
        equivalence=SimpleNamespace(
            equivalence_groups=tuple(tuple(group) for group in groups),
            representative_wall_ids=tuple(reps),
        ),
    )


def test_exact_source_primitives_in_one_positive_same_group_resolve() -> None:
    scope=_scope(
        (
            _record("face-a","d10i1"),
            _record("face-b","d10i3"),
            _record("remote","d20i0"),
        ),
        groups=(("face-a","face-b"),),
        reps=("face-a","remote"),
    )
    group, owners, shared=_resolve_exact_target_group(
        page_scope=scope,
        source_primitive_ids=("d10i1","d10i3"),
    )
    assert group == ("face-a","face-b")
    assert owners == ("face-a","face-b")
    assert shared == ("d10i1","d10i3")


def test_source_primitives_owned_by_two_unrelated_walls_abstain() -> None:
    scope=_scope(
        (
            _record("wall-a","d10i0"),
            _record("wall-b","d20i0"),
        ),
        reps=("wall-a","wall-b"),
    )
    group, owners, shared=_resolve_exact_target_group(
        page_scope=scope,
        source_primitive_ids=("d10i0","d20i0"),
    )
    assert group == ()
    assert owners == ("wall-a","wall-b")
    assert shared == ("d10i0","d20i0")


def test_missing_exact_source_primitive_is_not_replaced_by_nearby_owner() -> None:
    scope=_scope((_record("wall-a","d10i0"),),reps=("wall-a",))
    assert _resolve_exact_target_group(
        page_scope=scope,
        source_primitive_ids=("d10i0","missing"),
    ) is None


def test_single_exact_owner_resolves_without_expanding_to_unrelated_candidate() -> None:
    scope=_scope(
        (
            _record("wall-a","d10i0"),
            _record("nearby","d10i9"),
        ),
        reps=("wall-a","nearby"),
    )
    group, owners, shared=_resolve_exact_target_group(
        page_scope=scope,
        source_primitive_ids=("d10i0",),
    )
    assert group == ("wall-a",)
    assert owners == ("wall-a",)
    assert shared == ("d10i0",)


def test_duplicate_raw_owners_must_normalize_to_same_positive_group() -> None:
    scope=_scope(
        (
            _record("face-a","d10i0"),
            _record("face-b","d10i0"),
        ),
        groups=(("face-a","face-b"),),
        reps=("face-a",),
    )
    group, owners, _shared=_resolve_exact_target_group(
        page_scope=scope,
        source_primitive_ids=("d10i0",),
    )
    assert group == ("face-a","face-b")
    assert owners == ("face-a","face-b")


def test_duplicate_raw_owners_without_positive_same_group_are_ambiguous() -> None:
    scope=_scope(
        (
            _record("wall-a","d10i0"),
            _record("wall-b","d10i0"),
        ),
        reps=("wall-a","wall-b"),
    )
    group, owners, _shared=_resolve_exact_target_group(
        page_scope=scope,
        source_primitive_ids=("d10i0",),
    )
    assert group == ()
    assert owners == ("wall-a","wall-b")
