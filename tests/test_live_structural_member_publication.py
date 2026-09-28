"""Publication tests for source-owned structural-member quantities."""
from __future__ import annotations

import inspect

from pb_live_structural_member_publication import (
    LIVE_STRUCTURAL_MEMBER_PUBLICATION_RESOLVED,
    LIVE_STRUCTURAL_MEMBER_PUBLICATION_UNAVAILABLE,
    publish_live_structural_member_quantity,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    StructuralMemberProducer,
    StructuralMemberSelector,
)


def _producer_and_definition():
    producer = StructuralMemberProducer.for_source_snapshot(
        document_id="doc",
        revision_id="rev",
        source_sha256="b" * 64,
        snapshot_id="snap",
    )
    definition = producer.publish_definition(
        member_kind="chs_pillar",
        section_text="50 mm CHS pillar",
        source_evidence_ids=("definition",),
        source_page_ids=("10",),
        source_view_ids=("schedule",),
    )
    selector = StructuralMemberSelector(
        document_id=definition.document_id,
        revision_id=definition.revision_id,
        source_sha256=definition.source_sha256,
        snapshot_id=definition.snapshot_id,
        scope_id="scope-a",
        definition_id=definition.definition_id,
    )
    return producer, definition, selector


def _add_instance(producer, definition, index):
    record = producer.publish_instance(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        page_id="1",
        view_id="plan",
        view_kind="plan",
        source_evidence_ids=(f"instance-{index}",),
        source_role="structural_member",
        member_tag=f"P{index}",
        has_closed_geometry=True,
        bbox=(float(index * 20), 10.0, float(index * 20 + 5), 15.0),
    )
    assert record is not None
    return record


def test_definition_without_physical_instances_never_publishes_quantity() -> None:
    producer, definition, selector = _producer_and_definition()
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    publication = publish_live_structural_member_quantity(
        authority=producer.authority(),
        selector=selector,
    )

    assert publication.status is EvidenceResolutionStatus.ABSTAINED
    assert publication.quantity_evidence is None
    assert LIVE_STRUCTURAL_MEMBER_PUBLICATION_UNAVAILABLE in publication.reason_codes


def test_corrobated_physical_members_publish_traceable_quantity_evidence() -> None:
    producer, definition, selector = _producer_and_definition()
    instances = [_add_instance(producer, definition, index) for index in range(2)]
    producer.publish_completeness(
        scope_id="scope-a",
        definition_id=definition.definition_id,
        instance_bearing_view_ids=("plan",),
        complete_view_ids=("plan",),
        source_evidence_ids=("plan-complete",),
    )

    publication = publish_live_structural_member_quantity(
        authority=producer.authority(),
        selector=selector,
    )

    assert publication.status is EvidenceResolutionStatus.CORROBORATED
    assert publication.reason_codes == (LIVE_STRUCTURAL_MEMBER_PUBLICATION_RESOLVED,)
    assert publication.quantity_evidence is not None
    evidence = publication.quantity_evidence
    assert evidence.value == 2.0
    assert evidence.unit == "NO"
    assert evidence.family == "structural_member_count"
    assert evidence.authority == "source_owned_structural_member_identity"
    assert set(evidence.input_entity_ids) == set(publication.physical_member_ids)
    assert len(evidence.input_entity_ids) == 2
    assert set(evidence.evidence_ids) >= {
        "definition",
        "plan-complete",
        "instance-0",
        "instance-1",
    }
    assert evidence.metadata["definition_id"] == definition.definition_id
    assert tuple(evidence.metadata["physical_member_ids"]) == publication.physical_member_ids
    assert {record.candidate_id for record in instances}.issubset(
        {
            candidate_id
            for group in evidence.metadata["member_candidate_groups"]
            for candidate_id in group
        }
    )


def test_public_interface_has_no_count_or_quantity_truth_inputs() -> None:
    signature = inspect.signature(publish_live_structural_member_quantity)
    forbidden = {
        "count",
        "quantity",
        "expected",
        "confidence",
        "member_ids",
        "physical_member_ids",
        "override",
        "legacy_count",
    }
    assert not (forbidden & set(signature.parameters))
