"""Physical RCP source provenance may not be renamed to evade ownership guards."""
from __future__ import annotations

from dataclasses import replace

import pytest

import pb_cross_view_ceiling_finish_authority as ceiling
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_ceiling_finish_authority import (
    _independent_ceiling_source_records,
)


@pytest.mark.parametrize("first_field,second_field", [
    ("room_label_observation_ids", "occurrence_observation_ids"),
    ("occurrence_observation_ids", "room_label_observation_ids"),
    ("room_label_receipt_ids", "occurrence_receipt_ids"),
    ("occurrence_receipt_ids", "room_label_receipt_ids"),
])
def test_original_physical_source_cannot_be_reused_across_room_roles(
    monkeypatch, first_field, second_field,
):
    first, second = _independent_ceiling_source_records(monkeypatch)
    conflicting = replace(second, **{second_field: getattr(first, first_field)})
    for records in ((first, conflicting), (conflicting, first)):
        accepted, disputed = ceiling._quarantine_reused_ceiling_source_ownership(records)
        assert accepted == ()
        assert disputed == ("room-1", "room-2")
        published = ceiling.CrossViewCeilingFinishResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(ceiling.CROSS_VIEW_CEILING_FINISH_RESOLVED,),
            records=records, unresolved_physical_room_ids=(),
        )
        assert published.records_by_physical_room_id == {}


def test_typed_observation_and_receipt_namespace_does_not_confuse_ids(monkeypatch):
    first, second = _independent_ceiling_source_records(monkeypatch)
    unrelated = replace(
        second, occurrence_receipt_ids=first.room_label_observation_ids
    )
    accepted, disputed = ceiling._quarantine_reused_ceiling_source_ownership(
        (first, unrelated)
    )
    assert {r.physical_room_id for r in accepted} == {"room-1", "room-2"}
    assert disputed == ()


def test_independently_owned_ceiling_source_labels_and_finishes_still_publish(monkeypatch):
    first, second = _independent_ceiling_source_records(monkeypatch)
    accepted, disputed = ceiling._quarantine_reused_ceiling_source_ownership(
        (second, first)
    )
    assert {r.physical_room_id for r in accepted} == {"room-1", "room-2"}
    assert disputed == ()
    assert first.definition_record_id == second.definition_record_id
