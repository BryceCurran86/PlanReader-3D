"""Tests for pb_schedule_row_quantity_binding_adapter.py.

publish_schedule_row_quantity_from_binding() is the one lawful production
path from a CORROBORATED ScheduleOpeningInstanceBindingRecord to a published
ScheduleRowQuantityAuthority entry -- it must never publish a declared_count
that was not explicitly source-backed (schedule_row_count_explicit).
"""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingRecord,
)
from pb_schedule_row_quantity_authority import (
    SCHEDULE_ROW_QTY_INCOMPLETE,
    ScheduleRowQuantityProducer,
    ScheduleRowQuantitySelector,
)
from pb_schedule_row_quantity_binding_adapter import (
    publish_schedule_row_quantity_from_binding,
)

DOC = "doc-1"
REV = "rev-1"
SHA = "a" * 64
SNAP = "snap-1"
PAGE = "1"


def _binding_record(
    *,
    count: int | None,
    explicit: bool,
    row_ids: tuple[str, ...] = ("row-1",),
    mark: str = "W1",
) -> ScheduleOpeningInstanceBindingRecord:
    return ScheduleOpeningInstanceBindingRecord(
        record_id="bind-1",
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        page_id=PAGE,
        decision_scope_id="scope-1",
        opening_record_id="op-1",
        tag_observation_id="tag-1",
        tag_mark=mark,
        schedule_page_id=PAGE,
        schedule_row_observation_ids=row_ids,
        schedule_row_type_mark=mark,
        schedule_row_width_mm=900,
        schedule_row_height_mm=2100,
        schedule_row_count=count,
        schedule_row_count_explicit=explicit,
    )


def test_explicit_count_publishes_corroborated() -> None:
    producer = ScheduleRowQuantityProducer.create()
    record = _binding_record(count=3, explicit=True)
    res = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        binding_record=record,
        universe_complete=True,
    )
    assert res.status is EvidenceResolutionStatus.CORROBORATED
    assert res.record is not None
    assert res.record.declared_count == 3
    assert res.record.type_mark == "W1"

    # Resolves back out through the authority the same way GenericOpeningCountAuthority does.
    authority = producer.authority()
    lookup = authority.resolve(
        ScheduleRowQuantitySelector(
            document_id=DOC, revision_id=REV, source_sha256=SHA,
            snapshot_id=SNAP, schedule_page_id=PAGE,
            schedule_row_observation_ids=("row-1",),
        )
    )
    assert lookup.status is EvidenceResolutionStatus.CORROBORATED
    assert lookup.record is not None
    assert lookup.record.declared_count == 3


def test_implicit_default_count_never_published_as_evidence() -> None:
    """schedule_row_count_explicit=False (the historical default-to-1 case)
    must always abstain, never publish a fabricated declared_count."""
    producer = ScheduleRowQuantityProducer.create()
    record = _binding_record(count=1, explicit=False)
    res = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        binding_record=record,
        universe_complete=True,
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None
    assert SCHEDULE_ROW_QTY_INCOMPLETE in res.reason_codes


def test_missing_count_value_abstains() -> None:
    producer = ScheduleRowQuantityProducer.create()
    record = _binding_record(count=None, explicit=False)
    res = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        binding_record=record,
        universe_complete=True,
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


def test_incomplete_universe_forces_abstain_even_with_explicit_count() -> None:
    producer = ScheduleRowQuantityProducer.create()
    record = _binding_record(count=3, explicit=True)
    res = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        binding_record=record,
        universe_complete=False,
    )
    assert res.status is EvidenceResolutionStatus.ABSTAINED
    assert res.record is None


def test_rejects_non_producer_owned_arguments() -> None:
    record = _binding_record(count=3, explicit=True)
    with pytest.raises(TypeError):
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=object(),
            binding_record=record,
            universe_complete=True,
        )
    producer = ScheduleRowQuantityProducer.create()
    with pytest.raises(TypeError):
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=producer,
            binding_record=object(),
            universe_complete=True,
        )
