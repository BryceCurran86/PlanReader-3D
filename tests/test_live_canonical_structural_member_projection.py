from __future__ import annotations

from pb_live_canonical_structural_member_projection import (
    LIVE_CANONICAL_STRUCTURAL_MEMBER_RESOLVED,
    LIVE_CANONICAL_STRUCTURAL_MEMBER_UNAVAILABLE,
    project_structural_member_resolution,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    StructuralMemberDefinition,
    StructuralMemberObservation,
    StructuralMemberProducer,
    StructuralMemberRelation,
    StructuralMemberRelationEvidence,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)


def _selector(kind: str = "column") -> StructuralMemberSelector:
    return StructuralMemberSelector(
        document_id="doc",
        revision_id="rev",
        source_sha256="a" * 64,
        snapshot_id="snap",
        decision_scope_id="structural-scope",
        member_kind=kind,
    )


def _scope(*, complete: bool = True) -> StructuralMemberViewScope:
    return StructuralMemberViewScope(
        page_id="1",
        view_id="plan",
        view_type="plan",
        complete=complete,
        reason_codes=() if complete else ("cropped_view",),
    )

def _observation(index: int, *, kind: str = "column") -> StructuralMemberObservation:
    return StructuralMemberObservation(
        observation_id=f"col-{index}",
        member_kind=kind,
        page_id="1",
        view_id="plan",
        view_type="plan",
        source_evidence_ids=(f"src-col-{index}",),
        source_primitive_ids=(f"primitive-col-{index}",),
        definition_id=f"def-{kind}",
    )


def _definition(kind: str = "column") -> StructuralMemberDefinition:
    return StructuralMemberDefinition(
        definition_id=f"def-{kind}",
        member_kind=kind,
        section_spec="300 x 300 concrete column",
        source_evidence_ids=("schedule-column",),
        page_id="2",
        view_id="schedule",
    )


def _resolved(kind: str = "column"):
    observations = (_observation(1, kind=kind), _observation(2, kind=kind))
    relation = StructuralMemberRelationEvidence(
        left_observation_id=observations[0].observation_id,
        right_observation_id=observations[1].observation_id,
        relation=StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS,
        source_evidence_ids=("distinct-source",),
    )
    return StructuralMemberProducer.from_authenticated_evidence(
        selector=_selector(kind),
        definitions=(_definition(kind),),
        observations=observations,
        relations=(relation,),
        view_scopes=(_scope(),),
    ).publish()

def test_corroborated_members_project_to_stable_canonical_identities() -> None:
    resolution = _resolved()

    result = project_structural_member_resolution(resolution)

    assert resolution.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (LIVE_CANONICAL_STRUCTURAL_MEMBER_RESOLVED,)
    assert len(result.objects) == 2
    assert {
        member.canonical_structural_member_id for member in result.objects
    } == {
        member.physical_member_id for member in resolution.members
    }

    for member in result.objects:
        assert member.member_kind == "column"
        assert member.section_specs == ("300 x 300 concrete column",)
        assert member.source_primitive_ids
        assert member.source_evidence_ids
        assert member.geometry_complete is False
        assert member.commercial_quantity_authority is False
        payload = member.to_dict()
        assert payload["canonical_structural_member_id"] == member.physical_member_id
        assert payload["geometry_complete"] is False


def test_incomplete_structural_scope_does_not_mint_canonical_member() -> None:
    resolution = StructuralMemberProducer.from_authenticated_evidence(
        selector=_selector(),
        definitions=(_definition(),),
        observations=(_observation(1),),
        view_scopes=(_scope(complete=False),),
    ).publish()

    result = project_structural_member_resolution(resolution)

    assert resolution.status is EvidenceResolutionStatus.ABSTAINED
    assert result.objects == ()
    assert result.reason_codes == (
        LIVE_CANONICAL_STRUCTURAL_MEMBER_UNAVAILABLE,
    )
