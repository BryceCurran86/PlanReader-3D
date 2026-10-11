"""Source-closed opening count must reject replayed schedule and physical receipts."""
from __future__ import annotations

from copy import copy
from dataclasses import replace
from unittest.mock import patch

from pb_generic_opening_count_authority import GenericOpeningCountProducer
from pb_live_opening_count_quantity_publication import (
    publish_live_authenticated_opening_count_quantities,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingProducer,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_live_opening_count_quantity_publication import (
    _floor_plan_with_schedule_quantity,
)


def _source():
    source = SourceVisibilityProducer(
        producer_method="count-commercial-replay-test", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-commercial-replay-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-commercial-replay-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    return source, published, composition


def test_live_count_rejects_replayed_final_number_and_physical_receipts():
    source, _, composition = _source()
    real_publish = GenericOpeningCountProducer.publish
    for target, field, value in (
        ("quantity", "value", 2.0),
        ("quantity", "evidence_ids", ()),
        ("quantity", "evidence_ids", ("unrelated-original-source-receipt",)),
        ("quantity", "only_physical_receipts", None),
        ("record", "schedule_row_ids", ("foreign-original-schedule-row",)),
        ("quantity", "unit", "m2"),
        ("quantity", "family", "floor_area"),
        ("quantity", "input_entity_ids", ("foreign-opening",)),
        ("record", "count", 2),
        ("record", "physical_instance_record_ids", ("foreign-opening",)),
        ("record", "decision_scope_id", "foreign-scope"),
        ("record", "opening_mark", "Z99"),
    ):
        def corrupted_publish(self, selector):
            genuine = real_publish(self, selector)
            assert genuine.status is EvidenceResolutionStatus.CORROBORATED
            assert genuine.record is not None
            corrupted = copy(genuine.record)
            if target == "record":
                object.__setattr__(corrupted, field, value)
            else:
                assert genuine.record.quantity_evidence is not None
                quantity = copy(genuine.record.quantity_evidence)
                field_name = field
                forged_value = value
                if field_name == "only_physical_receipts":
                    field_name = "evidence_ids"
                    forged_value = tuple(
                        receipt for receipt in quantity.evidence_ids
                        if receipt not in genuine.record.schedule_row_ids
                    )
                object.__setattr__(quantity, field_name, forged_value)
                object.__setattr__(corrupted, "quantity_evidence", quantity)
            return replace(genuine, record=corrupted)

        with patch.object(GenericOpeningCountProducer, "publish", corrupted_publish):
            assert publish_live_authenticated_opening_count_quantities(
                source_visibility_producer=source,
                wall_opening_composition=composition,
            ) == (), (target, field)

    # The unchanged original source supports exactly one W1 opening count.
    quantities = publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=composition,
    )
    assert len(quantities) == 1
    assert quantities[0].value == 1.0
    assert quantities[0].unit == "ea"


def test_live_count_rejects_replayed_schedule_tag_scope_and_row_metadata():
    source, published, composition = _source()
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
    original = producer.publish_scope(
        opening_selector=opening_selector,
        decision_scope_id=semantic.record.decision_scope_id,
    )
    assert original.status is EvidenceResolutionStatus.CORROBORATED
    assert original.record is not None
    for changed in (
        {"tag_mark": "Z99"},
        {"schedule_row_type_mark": "Z99"},
        {"schedule_row_count_explicit": 1},
        {"schedule_row_count": 0},
        {"page_id": "foreign-plan-page"},
        {"decision_scope_id": "foreign-scope"},
        {"tag_observation_id": "   "},
    ):
        forged = copy(original.record)
        for field, value in changed.items():
            object.__setattr__(forged, field, value)
        with patch.object(
            ScheduleOpeningInstanceBindingProducer,
            "publish_scope",
            return_value=replace(original, record=forged),
        ):
            assert publish_live_authenticated_opening_count_quantities(
                source_visibility_producer=source,
                wall_opening_composition=composition,
            ) == (), changed
