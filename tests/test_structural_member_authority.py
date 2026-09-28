"""Adversarial contract tests for generic physical structural-member authority."""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE,
    STRUCTURAL_MEMBER_CROSS_VIEW_REGISTRATION_AMBIGUOUS,
    STRUCTURAL_MEMBER_INSTANCE_UNAVAILABLE,
    STRUCTURAL_MEMBER_SCOPE_CROPPED,
    STRUCTURAL_MEMBER_VIEW_COUNT_CONFLICT,
    StructuralMemberIdentityClass,
    StructuralMemberProducer,
    StructuralMemberSelector,
)


def _producer():
    return StructuralMemberProducer.for_source_snapshot(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="a" * 64,
        snapshot_id="snap-1",
    )


def _definition(producer, *, kind="chs_pillar", section="50 mm CHS pillar"):
    return producer.publish_definition(
        member_kind=kind,
        section_text=section,
        source_evidence_ids=("definition-evidence",),
        source_page_ids=("10",),
        source_view_ids=("schedule",),
    )


def _selector(definition, *, scope="scope-a"):
    return StructuralMemberSelector(
        document_id=definition.document_id,
        revision_id=definition.revision_id,
        source_sha256=definition.source_sha256,
        snapshot_id=definition.snapshot_id,
        scope_id=scope,
        definition_id=definition.definition_id,
    )


def _instance(
    producer,
    definition,
    *,
    evidence,
    page="1",
    view="plan",
    tag="P1",
    bbox=(10.0, 10.0, 15.0, 15.0),
    role="structural_member",
):
    return producer.publish_instance(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        page_id=page,
        view_id=view,
        view_kind=view,
        source_evidence_ids=(evidence,),
        source_role=role,
        member_tag=tag,
        has_closed_geometry=True,
        bbox=bbox,
    )


def test_schedule_definition_without_physical_instance_abstains() -> None:
    producer = _producer()
    definition = _definition(producer)
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("complete-plan",),
    )

    result = producer.authority().resolve(_selector(definition))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_INSTANCE_UNAVAILABLE in result.reason_codes


def test_four_plan_instances_and_same_four_elevation_instances_count_four() -> None:
    producer = _producer()
    definition = _definition(producer, kind="column", section="C1 concrete column")

    plan = [
        _instance(
            producer,
            definition,
            evidence=f"plan-{index}",
            view="plan",
            tag=f"C{index}",
            bbox=(index * 20.0, 10.0, index * 20.0 + 5.0, 15.0),
        )
        for index in range(4)
    ]
    elevation = [
        _instance(
            producer,
            definition,
            evidence=f"elevation-{index}",
            page="2",
            view="elevation",
            tag=f"C{index}",
            bbox=(index * 20.0, 30.0, index * 20.0 + 5.0, 35.0),
        )
        for index in range(4)
    ]
    for index, (left, right) in enumerate(zip(plan, elevation)):
        assert left is not None and right is not None
        producer.publish_relation(
            left_candidate_id=left.candidate_id,
            right_candidate_id=right.candidate_id,
            classification=StructuralMemberIdentityClass.SAME_PHYSICAL_MEMBER,
            source_evidence_ids=(f"registration-{index}",),
        )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan", "elevation"),
        complete_view_ids=("plan", "elevation"),
        cross_view_registration_complete=True,
        source_evidence_ids=("complete-plan", "complete-elevation", "registration-complete"),
    )

    result = producer.authority().resolve(_selector(definition))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 4
    assert len(result.physical_member_ids) == 4
    assert all(len(group) == 2 for group in result.member_candidate_groups)


def test_four_plan_and_three_conflicting_elevation_instances_conflict() -> None:
    producer = _producer()
    definition = _definition(producer, kind="column", section="C1 concrete column")
    plan = [
        _instance(
            producer,
            definition,
            evidence=f"plan-{index}",
            view="plan",
            tag=f"C{index}",
            bbox=(index * 20.0, 10.0, index * 20.0 + 5.0, 15.0),
        )
        for index in range(4)
    ]
    elevation = [
        _instance(
            producer,
            definition,
            evidence=f"elevation-{index}",
            page="2",
            view="elevation",
            tag=f"C{index}",
            bbox=(index * 20.0, 30.0, index * 20.0 + 5.0, 35.0),
        )
        for index in range(3)
    ]
    for index in range(3):
        assert plan[index] is not None and elevation[index] is not None
        producer.publish_relation(
            left_candidate_id=plan[index].candidate_id,
            right_candidate_id=elevation[index].candidate_id,
            classification=StructuralMemberIdentityClass.SAME_PHYSICAL_MEMBER,
            source_evidence_ids=(f"registration-{index}",),
        )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan", "elevation"),
        complete_view_ids=("plan", "elevation"),
        cross_view_registration_complete=True,
        source_evidence_ids=("both-views-complete",),
    )

    result = producer.authority().resolve(_selector(definition))

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_VIEW_COUNT_CONFLICT in result.reason_codes


def test_wall_end_resembling_pier_is_not_a_member() -> None:
    producer = _producer()
    definition = _definition(producer, kind="masonry_pier", section="Masonry pier")
    candidate = _instance(
        producer,
        definition,
        evidence="wall-end-primitive",
        role="wall_end",
        tag="P1",
    )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    assert candidate is None
    authority = producer.authority()
    assert "wall-end-primitive" in authority.rejected_instance_evidence_ids
    result = authority.resolve(_selector(definition))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None


def test_opening_jamb_resembling_pier_is_not_a_member() -> None:
    producer = _producer()
    definition = _definition(producer, kind="masonry_pier", section="Masonry pier")
    candidate = _instance(
        producer,
        definition,
        evidence="jamb-primitive",
        role="opening_jamb",
        tag="P1",
    )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    assert candidate is None
    assert "jamb-primitive" in producer.authority().rejected_instance_evidence_ids


def test_closed_structural_section_with_explicit_tag_is_valid_instance() -> None:
    producer = _producer()
    definition = _definition(producer, kind="chs_pillar", section="50 mm CHS pillar")
    candidate = _instance(
        producer,
        definition,
        evidence="closed-section-P1",
        tag="P1",
    )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    assert candidate is not None
    result = producer.authority().resolve(_selector(definition))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 1
    assert len(result.physical_member_ids) == 1


def test_repeated_identical_chs_pillars_remain_distinct_instances() -> None:
    producer = _producer()
    definition = _definition(producer, kind="chs_pillar", section="50 mm CHS pillar")
    for index in range(4):
        candidate = _instance(
            producer,
            definition,
            evidence=f"physical-pillar-{index}",
            tag="P1",
            # Deliberately identical geometry: proximity/shape may not deduplicate.
            bbox=(10.0, 10.0, 15.0, 15.0),
        )
        assert candidate is not None
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    result = producer.authority().resolve(_selector(definition))

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 4
    assert len(result.physical_member_ids) == 4


def test_cropped_plan_completeness_abstains() -> None:
    producer = _producer()
    definition = _definition(producer, kind="column", section="C1 column")
    assert _instance(producer, definition, evidence="plan-instance") is not None
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=(),
        cropped_view_ids=("plan",),
        source_evidence_ids=("crop-receipt",),
    )

    result = producer.authority().resolve(_selector(definition))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_SCOPE_CROPPED in result.reason_codes


def test_duplicate_cad_primitive_does_not_double_count() -> None:
    producer = _producer()
    definition = _definition(producer, kind="column", section="C1 column")
    first = _instance(
        producer,
        definition,
        evidence="same-native-primitive",
        tag="C1",
        bbox=(10.0, 10.0, 15.0, 15.0),
    )
    duplicate = _instance(
        producer,
        definition,
        evidence="same-native-primitive",
        tag="C1",
        bbox=(10.0, 10.0, 15.0, 15.0),
    )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    assert first is not None and duplicate is not None
    assert first.candidate_id == duplicate.candidate_id
    result = producer.authority().resolve(_selector(definition))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.quantity == 1


def test_ambiguous_plan_elevation_registration_abstains() -> None:
    producer = _producer()
    definition = _definition(producer, kind="column", section="C1 column")
    assert _instance(
        producer,
        definition,
        evidence="plan-instance",
        view="plan",
        tag="C1",
    ) is not None
    assert _instance(
        producer,
        definition,
        evidence="elevation-instance",
        page="2",
        view="elevation",
        tag="C1",
    ) is not None
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan", "elevation"),
        complete_view_ids=("plan", "elevation"),
        cross_view_registration_complete=False,
        source_evidence_ids=("views-complete-but-registration-ambiguous",),
    )

    result = producer.authority().resolve(_selector(definition))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_CROSS_VIEW_REGISTRATION_AMBIGUOUS in result.reason_codes


def test_conflicting_identity_evidence_conflicts_instead_of_choosing() -> None:
    producer = _producer()
    definition = _definition(producer, kind="column", section="C1 column")
    left = _instance(producer, definition, evidence="left", tag="C1")
    right = _instance(
        producer,
        definition,
        evidence="right",
        tag="C2",
        bbox=(30.0, 10.0, 35.0, 15.0),
    )
    assert left is not None and right is not None
    producer.publish_relation(
        left_candidate_id=left.candidate_id,
        right_candidate_id=right.candidate_id,
        classification=StructuralMemberIdentityClass.SAME_PHYSICAL_MEMBER,
        source_evidence_ids=("same-proof",),
    )
    producer.publish_relation(
        left_candidate_id=left.candidate_id,
        right_candidate_id=right.candidate_id,
        classification=StructuralMemberIdentityClass.DISTINCT_PHYSICAL_MEMBERS,
        source_evidence_ids=("distinct-proof",),
    )
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    result = producer.authority().resolve(_selector(definition))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.quantity is None



def test_completeness_for_one_definition_cannot_authorize_another() -> None:
    producer = _producer()
    chs = _definition(producer, kind="chs_pillar", section="50 mm CHS pillar")
    pier = producer.publish_definition(
        member_kind="masonry_pier",
        section_text="Masonry pier",
        source_evidence_ids=("pier-definition",),
        source_page_ids=("1",),
        source_view_ids=("plan",),
    )
    assert _instance(
        producer,
        chs,
        evidence="chs-instance",
        tag="P1",
    ) is not None
    pier_instance = producer.publish_instance(
        scope_id="scope-a",
        definition_id=pier.definition_id,
        page_id="1",
        view_id="plan",
        view_kind="plan",
        source_evidence_ids=("pier-instance",),
        source_role="structural_member",
        member_tag="MP1",
        has_closed_geometry=True,
        bbox=(30.0, 10.0, 35.0, 15.0),
    )
    assert pier_instance is not None

    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=chs.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("chs-plan-complete",),
    )

    result = producer.authority().resolve(_selector(pier))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.quantity is None
    assert STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE in result.reason_codes
