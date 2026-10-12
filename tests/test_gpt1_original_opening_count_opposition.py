"""Preserved GPT1 Q04 complete opening-count source opposition on current main.

Tests migrated from older #2257/#2288 branches, without replaying their now
superseded production implementations. Count=1 positive source fixture is
*explicitly scheduled*, not a detector-default or full Lot16 count.
"""
from __future__ import annotations

from copy import copy
from dataclasses import replace
from unittest.mock import patch

import pytest

from tests.test_live_opening_count_quantity_publication import (
    _floor_plan_with_schedule_quantity,
)

@pytest.mark.parametrize("extra_member", ("", "duplicate"))
def test_count_bridge_refuses_malformed_representative_universe(extra_member):
    """A 'complete' count may not omit blank or duplicated source members."""
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import (
        compose_live_wall_opening_authority,
    )
    from pb_source_visibility_authority import SourceVisibilityProducer

    source = SourceVisibilityProducer(
        producer_method="count-representative-universe-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-representative-universe-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-representative-universe-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    original = composition.semantic_enumeration_result
    assert original.record is not None
    reps = original.record.representative_observation_ids
    assert reps
    extra = reps[0] if extra_member == "duplicate" else ""
    forged_record = copy(original.record)
    object.__setattr__(forged_record, "representative_observation_ids", (*reps, extra))
    malformed = replace(original, record=forged_record)
    changed = replace(composition, semantic_enumeration_result=malformed)
    quantities = publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=changed,
    )
    assert quantities == ()

def test_count_bridge_rejects_two_representatives_for_same_opening():
    """Source identity collision must not overwrite a schedule binding."""
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_source_observation_authority import ObservationSelector

    source = SourceVisibilityProducer(
        producer_method="count-binding-collision-test", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-binding-collision-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-binding-collision-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    result = composition.semantic_enumeration_result
    assert result.record is not None
    original_id = result.record.representative_observation_ids[0]
    original_selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=original_id,
    )
    same_opening = composition.physical_opening_authority.prove_existence(original_selector)
    assert same_opening.existence_record is not None
    forged_record = copy(result.record)
    object.__setattr__(
        forged_record, "representative_observation_ids",
        (original_id, "second-observation"),
    )
    object.__setattr__(
        forged_record, "physical_opening_record_ids",
        (*result.record.physical_opening_record_ids, "source-second-opening"),
    )
    duplicated = replace(
        composition,
        semantic_enumeration_result=replace(result, record=forged_record),
    )
    forged_existence = replace(
        same_opening,
        existence_record=replace(
            same_opening.existence_record,
            source_observation_ids=(original_id, "second-observation"),
        ),
    )
    with patch.object(
        composition.physical_opening_authority,
        "prove_existence",
        return_value=forged_existence,
    ):
        assert publish_live_authenticated_opening_count_quantities(
            source_visibility_producer=source,
            wall_opening_composition=duplicated,
        ) == ()

@pytest.mark.parametrize("field,value", (
    ("physical_opening_universe_complete", 1),
    ("physical_opening_universe_complete", "true"),
    ("representative_observation_ids", None),
    ("representative_observation_ids", "observation-one"),
    ("representative_observation_ids", (42,)),
    ("representative_observation_ids", ("   ",)),
    ("representative_observation_ids", ("same", "same")),
    ("snapshot_id", "foreign-snapshot"),
    ("structural_enumeration_complete", False),
    ("page_ids", ("2",)),
    ("page_ids", ("1", "1")),
    ("page_ids", (None,)),
    ("physical_opening_record_ids", ("foreign-opening",)),
    ("physical_opening_record_ids", ("   ",)),
    ("physical_opening_record_ids", ("same", "same")),
))
def test_count_bridge_rejects_malformed_source_inventory_cases(field, value):
    """No schedule count may be published from an untrusted semantic inventory."""
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    source = SourceVisibilityProducer(
        producer_method="count-malformed-source-inventory-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-malformed-source-inventory-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-malformed-source-inventory-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    result = composition.semantic_enumeration_result
    assert result.record is not None
    forged_record = copy(result.record)
    object.__setattr__(forged_record, field, value)
    altered = replace(
        composition,
        semantic_enumeration_result=replace(result, record=forged_record),
    )
    assert publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=altered,
    ) == ()

@pytest.mark.parametrize("defect", (
    "unresolved_member", "foreign_document", "foreign_revision",
    "foreign_sha", "foreign_snapshot", "foreign_page", "blank_physical_id",
))
def test_count_universe_never_silently_drops_or_replays_physical_member(defect):
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_source_observation_authority import ObservationSelector
    from pb_migration_contracts import EvidenceResolutionStatus

    source = SourceVisibilityProducer(
        producer_method="count-member-integrity-test", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-member-integrity-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-member-integrity-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    semantic = composition.semantic_enumeration_result
    assert semantic.record is not None
    original_selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=semantic.record.representative_observation_ids[0],
    )
    original = composition.physical_opening_authority.prove_existence(original_selector)
    assert original.existence_record is not None
    if defect == "unresolved_member":
        replay = replace(original, status=EvidenceResolutionStatus.ABSTAINED)
    else:
        change = {
            "foreign_document": {"document_id": "other-document"},
            "foreign_revision": {"revision_id": "other-revision"},
            "foreign_sha": {"source_sha256": "other-sha"},
            "foreign_snapshot": {"snapshot_id": "other-snapshot"},
            "foreign_page": {"page_id": "other-page"},
            "blank_physical_id": {"record_id": "   "},
        }[defect]
        replay = replace(original, existence_record=replace(original.existence_record, **change))
    with patch.object(
        composition.physical_opening_authority,
        "prove_existence",
        return_value=replay,
    ):
        assert publish_live_authenticated_opening_count_quantities(
            source_visibility_producer=source,
            wall_opening_composition=composition,
        ) == ()


def test_count_bridge_rejects_replayed_or_unbound_schedule_members_without_partial_count():
    """The source-closed universe cannot publish from altered schedule receipts."""
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_source_observation_authority import ObservationSelector
    from pb_schedule_opening_instance_binding_authority import (
        ScheduleOpeningInstanceBindingProducer,
    )
    from pb_migration_contracts import EvidenceResolutionStatus

    source = SourceVisibilityProducer(
        producer_method="count-schedule-receipt-test", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-schedule-receipt-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-schedule-receipt-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    semantic = composition.semantic_enumeration_result
    assert semantic.record is not None
    opening_selector = ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=semantic.record.representative_observation_ids[0],
    )
    producer = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    legitimate = producer.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=semantic.record.decision_scope_id,
    )
    assert legitimate.status is EvidenceResolutionStatus.CORROBORATED
    assert legitimate.record is not None
    for defect in (
        {"tag_mark": "Z99"},
        {"schedule_row_type_mark": "Z99"},
        {"schedule_row_count_explicit": 1},
        {"schedule_row_count": 0},
        {"page_id": "foreign-plan-page"},
        {"decision_scope_id": "foreign-scope"},
        {"tag_observation_id": "   "},
    ):
        forged_record = copy(legitimate.record)
        for field, value in defect.items():
            object.__setattr__(forged_record, field, value)
        forged_result = replace(legitimate, record=forged_record)
        with patch.object(
            ScheduleOpeningInstanceBindingProducer,
            "publish_scope",
            return_value=forged_result,
        ):
            assert publish_live_authenticated_opening_count_quantities(
                source_visibility_producer=source,
                wall_opening_composition=composition,
            ) == (), defect
    unresolved = replace(legitimate, status=EvidenceResolutionStatus.ABSTAINED)
    with patch.object(
        ScheduleOpeningInstanceBindingProducer,
        "publish_scope",
        return_value=unresolved,
    ):
        assert publish_live_authenticated_opening_count_quantities(
            source_visibility_producer=source,
            wall_opening_composition=composition,
        ) == ()


def test_live_count_rejects_forged_final_customer_count_and_physical_receipts():
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_generic_opening_count_authority import GenericOpeningCountProducer
    from pb_migration_contracts import EvidenceResolutionStatus

    source = SourceVisibilityProducer(
        producer_method="count-commercial-handoff-replay", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-commercial-handoff-replay",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-commercial-handoff-replay.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    real_publish = GenericOpeningCountProducer.publish
    for target, field, forged_value in (
        ("quantity", "value", 2.0),
        ("quantity", "evidence_ids", ()),
        ("quantity", "evidence_ids", ("unrelated-original-source-receipt",)),
        ("quantity", "unit", "m2"),
        ("quantity", "family", "floor_area"),
        ("quantity", "input_entity_ids", ("foreign-opening",)),
        ("record", "count", 2),
        ("record", "physical_instance_record_ids", ("foreign-opening",)),
        ("record", "decision_scope_id", "foreign-scope"),
        ("record", "opening_mark", "Z99"),
    ):
        def corrupted_publish(self, selector):
            real = real_publish(self, selector)
            assert real.status is EvidenceResolutionStatus.CORROBORATED
            assert real.record is not None
            forged_record = copy(real.record)
            if target == "record":
                object.__setattr__(forged_record, field, forged_value)
            else:
                assert real.record.quantity_evidence is not None
                forged_quantity = copy(real.record.quantity_evidence)
                object.__setattr__(forged_quantity, field, forged_value)
                object.__setattr__(forged_record, "quantity_evidence", forged_quantity)
            return replace(real, record=forged_record)

        with patch.object(GenericOpeningCountProducer, "publish", corrupted_publish):
            assert publish_live_authenticated_opening_count_quantities(
                source_visibility_producer=source,
                wall_opening_composition=composition,
            ) == (), (target, field)
