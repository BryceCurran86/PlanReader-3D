from __future__ import annotations

from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE,
    STRUCTURAL_MEMBER_RELATION_CONFLICT,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberObservation,
    StructuralMemberRelation,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)
from pb_structural_member_cross_view_registration import (
    STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_AMBIGUOUS,
    STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_CONFLICT,
    STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_INVALID,
    STRUCTURAL_MEMBER_REGISTRATION_RESOLVED,
    StructuralMemberRegistrationAnchor,
    StructuralMemberRegistrationAnchorKind,
    build_structural_member_registration_shadow,
)


def selector() -> StructuralMemberSelector:
    return StructuralMemberSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        decision_scope_id="building-a:structural",
        member_kind="pier",
    )


def obs(oid: str, view: str, *, page: str | None = None) -> StructuralMemberObservation:
    return StructuralMemberObservation(
        observation_id=oid,
        member_kind="pier",
        page_id=page or view,
        view_id=view,
        view_type=view,
        source_evidence_ids=(f"src:{oid}",),
        source_primitive_ids=(f"primitive:{oid}",),
    )


def scope(view: str, *, complete: bool = True) -> StructuralMemberViewScope:
    return StructuralMemberViewScope(
        page_id=view,
        view_id=view,
        view_type=view,
        complete=complete,
        reason_codes=() if complete else ("cropped_view",),
    )


def anchor(
    oid: str,
    value: str,
    *,
    kind: StructuralMemberRegistrationAnchorKind = (
        StructuralMemberRegistrationAnchorKind.GRID_INTERSECTION
    ),
    registration_scope_id: str = "building-a:grid",
    evidence: str | None = None,
) -> StructuralMemberRegistrationAnchor:
    return StructuralMemberRegistrationAnchor(
        observation_id=oid,
        kind=kind,
        registration_scope_id=registration_scope_id,
        value=value,
        source_evidence_ids=(evidence or f"anchor:{oid}:{value}",),
    )


def resolve(observations, anchors, scopes):
    return build_structural_member_registration_shadow(
        selector=selector(),
        observations=observations,
        anchors=anchors,
        view_scopes=scopes,
    )


def test_unique_grid_registration_reconciles_same_members_across_views() -> None:
    observations = (
        *(obs(f"p{i}", "plan") for i in range(4)),
        *(obs(f"e{i}", "elevation") for i in range(4)),
    )
    anchors = tuple(
        anchor(oid, f"A/{index + 1}")
        for index in range(4)
        for oid in (f"p{index}", f"e{index}")
    )

    result = resolve(
        observations,
        anchors,
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.resolution.quantity == 4
    assert result.audit.same_relation_count == 4
    assert result.audit.distinct_relation_count == 12
    assert STRUCTURAL_MEMBER_REGISTRATION_RESOLVED in result.reason_codes
    assert all(
        set(member.view_ids) == {"plan", "elevation"}
        for member in result.resolution.members
    )


def test_equal_counts_without_positive_registration_abstain() -> None:
    result = resolve(
        (
            obs("p0", "plan"),
            obs("p1", "plan"),
            obs("e0", "elevation"),
            obs("e1", "elevation"),
        ),
        (),
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert result.relations == ()
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_partial_registration_abstains_instead_of_using_count_equality() -> None:
    result = resolve(
        (
            obs("p0", "plan"),
            obs("p1", "plan"),
            obs("e0", "elevation"),
            obs("e1", "elevation"),
        ),
        (
            anchor("p0", "A/1"),
            anchor("e0", "A/1"),
        ),
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_duplicate_anchor_in_one_view_is_ambiguous_not_first_match() -> None:
    result = resolve(
        (
            obs("p0", "plan"),
            obs("p1", "plan"),
            obs("e0", "elevation"),
            obs("e1", "elevation"),
        ),
        (
            anchor("p0", "A/1"),
            anchor("p1", "A/1"),
            anchor("e0", "A/1"),
            anchor("e1", "A/2"),
        ),
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_AMBIGUOUS in result.reason_codes
    assert result.audit.ambiguous_anchor_keys == ("grid_intersection|BUILDING-A:GRID|A/1",)
    assert not any(
        relation.relation is StructuralMemberRelation.SAME_PHYSICAL_MEMBER
        for relation in result.relations
    )


def test_agreeing_mark_and_disagreeing_grid_produce_existing_authority_conflict() -> None:
    observations = (obs("p0", "plan"), obs("e0", "elevation"))
    anchors = (
        anchor(
            "p0",
            "P1",
            kind=StructuralMemberRegistrationAnchorKind.MEMBER_MARK,
            registration_scope_id="building-a:member-marks",
        ),
        anchor(
            "e0",
            "P1",
            kind=StructuralMemberRegistrationAnchorKind.MEMBER_MARK,
            registration_scope_id="building-a:member-marks",
        ),
        anchor("p0", "A/1"),
        anchor("e0", "A/2"),
    )

    result = resolve(
        observations,
        anchors,
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.CONFLICT
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_RELATION_CONFLICT in result.resolution.reason_codes
    pair_relations = {relation.relation for relation in result.relations}
    assert pair_relations == {
        StructuralMemberRelation.SAME_PHYSICAL_MEMBER,
        StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS,
    }


def test_same_anchor_text_in_different_registration_scopes_does_not_match() -> None:
    result = resolve(
        (obs("p0", "plan"), obs("e0", "elevation")),
        (
            anchor("p0", "A/1", registration_scope_id="building-a:grid"),
            anchor("e0", "A/1", registration_scope_id="building-b:grid"),
        ),
        (scope("plan"), scope("elevation")),
    )

    assert result.relations == ()
    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.resolution.reason_codes


def test_cropped_view_remains_fail_closed_even_with_matching_anchor() -> None:
    result = resolve(
        (obs("p0", "plan"), obs("e0", "elevation")),
        (anchor("p0", "A/1"), anchor("e0", "A/1")),
        (scope("plan"), scope("elevation", complete=False)),
    )

    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_SCOPE_INCOMPLETE in result.resolution.reason_codes
    assert "cropped_view" in result.resolution.reason_codes


def test_anchor_for_unknown_observation_fails_all_views_closed() -> None:
    result = resolve(
        (obs("p0", "plan"), obs("e0", "elevation")),
        (
            anchor("p0", "A/1"),
            anchor("e0", "A/1"),
            anchor("ghost", "A/9"),
        ),
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.resolution.quantity is None
    assert STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_INVALID in result.reason_codes
    assert result.audit.invalid_observation_ids == ("ghost",)
    assert all(not view.complete for view in result.view_scopes)


def test_one_observation_claiming_two_values_for_same_family_fails_its_view_closed() -> None:
    result = resolve(
        (obs("p0", "plan"), obs("e0", "elevation")),
        (
            anchor("p0", "A/1"),
            anchor("p0", "A/2"),
            anchor("e0", "A/1"),
        ),
        (scope("plan"), scope("elevation")),
    )

    assert result.resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_CONFLICT in result.reason_codes
    assert result.audit.conflicting_observation_ids == ("p0",)
    assert {view.view_id: view.complete for view in result.view_scopes} == {
        "plan": False,
        "elevation": True,
    }


def test_relation_evidence_is_source_owned_and_input_order_invariant() -> None:
    observations = (obs("p0", "plan"), obs("e0", "elevation"))
    anchors = (
        anchor("p0", "A/1", evidence="grid:plan:A1"),
        anchor("e0", "A/1", evidence="grid:elevation:A1"),
    )
    scopes = (scope("plan"), scope("elevation"))

    forward = resolve(observations, anchors, scopes)
    backward = resolve(
        tuple(reversed(observations)),
        tuple(reversed(anchors)),
        tuple(reversed(scopes)),
    )

    assert forward.relations == backward.relations
    assert forward.resolution == backward.resolution
    assert forward.audit == backward.audit
    assert forward.relations[0].source_evidence_ids == (
        "grid:elevation:A1",
        "grid:plan:A1",
    )


def test_shadow_registration_is_not_imported_by_live_extractor() -> None:
    extractor = Path("pb_planreader_pdf_extractor.py").read_text(encoding="utf-8")
    assert "pb_structural_member_cross_view_registration" not in extractor
