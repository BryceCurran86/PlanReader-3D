from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_COUNT_CONFLICT,
    STRUCTURAL_MEMBER_DEFINITION_ONLY,
    STRUCTURAL_MEMBER_DEFINITION_CONFLICT,
    STRUCTURAL_MEMBER_GEOMETRY_CONFLICT,
    STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE,
    STRUCTURAL_MEMBER_RELATION_AMBIGUOUS,
    STRUCTURAL_MEMBER_RELATION_CONFLICT,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberDefinition,
    StructuralMemberObservation,
    StructuralMemberProducer,
    StructuralMemberRelation,
    StructuralMemberRelationEvidence,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)


def selector(kind="column"):
    return StructuralMemberSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        decision_scope_id="structural-scope",
        member_kind=kind,
    )


def definition(*, kind="column"):
    return StructuralMemberDefinition(
        definition_id=f"def:{kind}",
        member_kind=kind,
        section_spec="50 mm CHS pillar" if kind == "chs_pillar" else "300 x 300 concrete column",
        source_evidence_ids=(f"schedule:{kind}",),
        page_id="2",
        view_id="schedule",
    )


def obs(
    oid,
    view,
    *,
    kind="column",
    page="1",
    definition_id=None,
    primitive=None,
    bbox=None,
    bbox_primitive=None,
):
    primitive_id = primitive or f"prim:{oid}"
    return StructuralMemberObservation(
        observation_id=oid,
        member_kind=kind,
        page_id=page,
        view_id=view,
        view_type=view,
        source_evidence_ids=(f"src:{oid}",),
        source_primitive_ids=(primitive_id,),
        source_primitive_bboxes=(
            (
                (
                    bbox_primitive or primitive_id,
                    tuple(float(value) for value in bbox),
                ),
            )
            if bbox is not None
            else ()
        ),
        definition_id=definition_id,
    )


def scope(view, *, page="1", complete=True, reason=()):
    return StructuralMemberViewScope(
        page_id=page,
        view_id=view,
        view_type=view,
        complete=complete,
        reason_codes=reason,
    )


def relation(a, b, rel):
    return StructuralMemberRelationEvidence(
        left_observation_id=a,
        right_observation_id=b,
        relation=rel,
        source_evidence_ids=(f"rel:{a}:{b}:{rel.value}",),
    )


def resolve(*, kind="column", definitions=(), observations=(), relations=(), scopes=()):
    return StructuralMemberProducer.from_authenticated_evidence(
        selector=selector(kind),
        definitions=definitions,
        observations=observations,
        relations=relations,
        view_scopes=scopes,
    ).publish()


def test_schedule_definition_without_physical_instance_abstains():
    result = resolve(
        kind="chs_pillar",
        definitions=(definition(kind="chs_pillar"),),
        scopes=(scope("schedule", page="2"),),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_DEFINITION_ONLY in result.reason_codes


def test_four_plan_instances_plus_same_four_elevation_instances_count_four():
    plan = tuple(obs(f"p{i}", "plan") for i in range(4))
    elev = tuple(obs(f"e{i}", "elevation") for i in range(4))
    relations = tuple(
        relation(f"p{i}", f"e{i}", StructuralMemberRelation.SAME_PHYSICAL_MEMBER)
        for i in range(4)
    )
    result = resolve(
        observations=(*plan, *elev),
        relations=relations,
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 4
    assert all(set(member.view_ids) == {"plan", "elevation"} for member in result.members)


def test_four_plan_plus_three_complete_elevation_instances_conflict():
    plan = tuple(obs(f"p{i}", "plan") for i in range(4))
    elev = tuple(obs(f"e{i}", "elevation") for i in range(3))
    result = resolve(
        observations=(*plan, *elev),
        relations=tuple(
            relation(f"p{i}", f"e{i}", StructuralMemberRelation.SAME_PHYSICAL_MEMBER)
            for i in range(3)
        ),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_COUNT_CONFLICT in result.reason_codes


def test_repeated_identical_chs_pillars_remain_distinct_instances():
    observations = tuple(
        obs(f"c{i}", "plan", kind="chs_pillar", definition_id="def:chs_pillar")
        for i in range(4)
    )
    relations = tuple(
        relation(
            f"c{i}",
            f"c{j}",
            StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS,
        )
        for i in range(4)
        for j in range(i + 1, 4)
    )
    result = resolve(
        kind="chs_pillar",
        definitions=(definition(kind="chs_pillar"),),
        observations=observations,
        relations=relations,
        scopes=(scope("plan"),),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 4
    assert len({m.physical_member_id for m in result.members}) == 4


def test_owned_primitive_bbox_is_preserved_on_physical_member():
    observation = obs(
        "p0",
        "plan",
        bbox=(10.0, 20.0, 14.0, 24.0),
    )
    result = resolve(
        observations=(observation,),
        scopes=(scope("plan"),),
    )

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 1
    assert result.members[0].source_primitive_bboxes == (
        ("prim:p0", (10.0, 20.0, 14.0, 24.0)),
    )


def test_primitive_bbox_for_unowned_primitive_fails_closed():
    observation = obs(
        "p0",
        "plan",
        primitive="prim:p0",
        bbox=(10.0, 20.0, 14.0, 24.0),
        bbox_primitive="prim:other",
    )
    result = resolve(
        observations=(observation,),
        scopes=(scope("plan"),),
    )

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_GEOMETRY_CONFLICT in result.reason_codes


def test_cropped_plan_abstains_on_completeness():
    result = resolve(
        observations=(obs("p0", "plan"),),
        scopes=(scope("plan", complete=False, reason=("cropped_view",)),),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_SCOPE_INCOMPLETE in result.reason_codes
    assert "cropped_view" in result.reason_codes


def test_ambiguous_plan_elevation_registration_abstains():
    result = resolve(
        observations=(obs("p0", "plan"), obs("e0", "elevation")),
        relations=(
            relation("p0", "e0", StructuralMemberRelation.AMBIGUOUS),
        ),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_RELATION_AMBIGUOUS in result.reason_codes


def test_duplicate_cad_primitive_deduplicates_only_with_positive_same_relation():
    observations = (
        obs("raw-a", "plan", primitive="cad:17"),
        obs("raw-b", "plan", primitive="cad:17"),
    )
    unresolved = resolve(
        observations=observations,
        scopes=(scope("plan"),),
    )
    assert unresolved.status is EvidenceResolutionStatus.CORROBORATED
    assert unresolved.quantity == 2

    resolved = resolve(
        observations=observations,
        relations=(
            relation("raw-a", "raw-b", StructuralMemberRelation.SAME_PHYSICAL_MEMBER),
        ),
        scopes=(scope("plan"),),
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.quantity == 1


def test_equal_count_complete_views_without_positive_registration_abstain():
    result = resolve(
        observations=(
            *(obs(f"p{i}", "plan") for i in range(4)),
            *(obs(f"e{i}", "elevation") for i in range(4)),
        ),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.reason_codes


def test_partial_cross_view_registration_abstains():
    result = resolve(
        observations=(
            *(obs(f"p{i}", "plan") for i in range(4)),
            *(obs(f"e{i}", "elevation") for i in range(4)),
        ),
        relations=tuple(
            relation(f"p{i}", f"e{i}", StructuralMemberRelation.SAME_PHYSICAL_MEMBER)
            for i in range(3)
        ),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE in result.reason_codes


def test_contradictory_same_and_distinct_relation_conflicts():
    result = resolve(
        observations=(obs("p0", "plan"), obs("e0", "elevation")),
        relations=(
            relation("p0", "e0", StructuralMemberRelation.SAME_PHYSICAL_MEMBER),
            relation("p0", "e0", StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS),
        ),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_RELATION_CONFLICT in result.reason_codes


def test_definition_binding_does_not_add_quantity():
    observations = (
        obs("c0", "plan", kind="chs_pillar", definition_id="def:chs_pillar"),
        obs("c1", "plan", kind="chs_pillar", definition_id="def:chs_pillar"),
    )
    result = resolve(
        kind="chs_pillar",
        definitions=(definition(kind="chs_pillar"),),
        observations=observations,
        relations=(
            relation("c0", "c1", StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS),
        ),
        scopes=(scope("plan"),),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 2
    assert all(member.definition_ids == ("def:chs_pillar",) for member in result.members)


def test_missing_definition_reference_cannot_publish_an_unowned_type():
    result = resolve(
        observations=(obs("p0", "plan", definition_id="unknown-definition"),),
        scopes=(scope("plan"),),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_DEFINITION_CONFLICT in result.reason_codes


def test_duplicate_definition_identity_abstains_even_for_one_physical_member():
    duplicated = definition()
    result = resolve(
        definitions=(duplicated, duplicated),
        observations=(obs("p0", "plan", definition_id=duplicated.definition_id),),
        scopes=(scope("plan"),),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert STRUCTURAL_MEMBER_DEFINITION_CONFLICT in result.reason_codes


def test_registered_cross_view_member_cannot_inherit_conflicting_definitions():
    first = definition()
    second = StructuralMemberDefinition(
        definition_id="def:other-column", member_kind="column",
        section_spec="another column type", source_evidence_ids=("schedule:other",),
        page_id="3", view_id="schedule",
    )
    result = resolve(
        definitions=(first, second),
        observations=(
            obs("plan-0", "plan", definition_id=first.definition_id),
            obs("elev-0", "elevation", definition_id=second.definition_id),
        ),
        relations=(relation(
            "plan-0", "elev-0", StructuralMemberRelation.SAME_PHYSICAL_MEMBER
        ),),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_DEFINITION_CONFLICT in result.reason_codes


def test_registered_views_with_one_owned_definition_keep_one_physical_member():
    owned = definition()
    result = resolve(
        definitions=(owned,),
        observations=(
            obs("plan-0", "plan", definition_id=owned.definition_id),
            obs("elev-0", "elevation"),
        ),
        relations=(relation(
            "plan-0", "elev-0", StructuralMemberRelation.SAME_PHYSICAL_MEMBER
        ),),
        scopes=(scope("plan"), scope("elevation")),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 1
    assert result.members[0].definition_ids == (owned.definition_id,)


def test_wall_end_or_jamb_shape_alone_cannot_mint_member_quantity():
    result = resolve(scopes=(scope("plan"),))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_SCOPE_INCOMPLETE in result.reason_codes
