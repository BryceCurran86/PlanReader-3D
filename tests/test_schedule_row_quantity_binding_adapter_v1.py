"""Tests for the authority-resolved schedule quantity bridge."""
from __future__ import annotations

import inspect

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_schedule_opening_instance_binding_authority import (
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingRecord,
    ScheduleOpeningInstanceBindingResult,
    ScheduleOpeningInstanceBindingSelector,
    _AUTHORITY_SEAL as BINDING_AUTHORITY_SEAL,
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
SCOPE = "scope-1"
OPENING = "op-1"


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
        decision_scope_id=SCOPE,
        opening_record_id=OPENING,
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


def _binding_selector() -> ScheduleOpeningInstanceBindingSelector:
    return ScheduleOpeningInstanceBindingSelector(
        document_id=DOC,
        revision_id=REV,
        source_sha256=SHA,
        snapshot_id=SNAP,
        decision_scope_id=SCOPE,
        opening_record_id=OPENING,
    )


def _binding_authority(
    record: ScheduleOpeningInstanceBindingRecord | None,
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED,
) -> ScheduleOpeningInstanceBindingAuthority:
    selector = _binding_selector()
    result = ScheduleOpeningInstanceBindingResult(
        status=status,
        reason_codes=("binding_resolved",) if record is not None else ("binding_unavailable",),
        record=record,
    )
    key = (DOC, REV, SHA, SNAP, SCOPE, OPENING)
    return ScheduleOpeningInstanceBindingAuthority(
        {key: result},
        _seal=BINDING_AUTHORITY_SEAL,
    )


def test_explicit_count_publishes_only_after_authority_resolution() -> None:
    producer = ScheduleRowQuantityProducer.create()
    binding = _binding_authority(_binding_record(count=3, explicit=True))

    result = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        schedule_binding_authority=binding,
        binding_selector=_binding_selector(),
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.declared_count == 3
    assert result.record.type_mark == "W1"

    lookup = producer.authority().resolve(
        ScheduleRowQuantitySelector(
            document_id=DOC,
            revision_id=REV,
            source_sha256=SHA,
            snapshot_id=SNAP,
            schedule_page_id=PAGE,
            schedule_row_observation_ids=("row-1",),
        )
    )
    assert lookup.status is EvidenceResolutionStatus.CORROBORATED
    assert lookup.record is not None
    assert lookup.record.declared_count == 3


def test_constructible_binding_record_is_not_an_adapter_input() -> None:
    """A caller-created positive record cannot be passed directly anymore."""
    producer = ScheduleRowQuantityProducer.create()
    forged = _binding_record(count=999, explicit=True)

    with pytest.raises(TypeError):
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=producer,
            binding_record=forged,  # type: ignore[call-arg]
            universe_complete=True,
        )


def test_unresolved_binding_authority_cannot_publish_quantity() -> None:
    producer = ScheduleRowQuantityProducer.create()
    binding = _binding_authority(
        None,
        status=EvidenceResolutionStatus.ABSTAINED,
    )

    result = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        schedule_binding_authority=binding,
        binding_selector=_binding_selector(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert SCHEDULE_ROW_QTY_INCOMPLETE in result.reason_codes


def test_implicit_default_count_never_published_as_evidence() -> None:
    producer = ScheduleRowQuantityProducer.create()
    binding = _binding_authority(_binding_record(count=1, explicit=False))

    result = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        schedule_binding_authority=binding,
        binding_selector=_binding_selector(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert SCHEDULE_ROW_QTY_INCOMPLETE in result.reason_codes


def test_missing_count_value_abstains() -> None:
    producer = ScheduleRowQuantityProducer.create()
    binding = _binding_authority(_binding_record(count=None, explicit=False))

    result = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        schedule_binding_authority=binding,
        binding_selector=_binding_selector(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None


def test_incomplete_universe_forces_abstain_even_with_explicit_count() -> None:
    producer = ScheduleRowQuantityProducer.create()
    binding = _binding_authority(_binding_record(count=3, explicit=True))

    result = publish_schedule_row_quantity_from_binding(
        schedule_row_quantity_producer=producer,
        schedule_binding_authority=binding,
        binding_selector=_binding_selector(),
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None


def test_rejects_non_producer_owned_arguments() -> None:
    producer = ScheduleRowQuantityProducer.create()
    binding = _binding_authority(_binding_record(count=3, explicit=True))
    selector = _binding_selector()

    with pytest.raises(TypeError):
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=object(),  # type: ignore[arg-type]
            schedule_binding_authority=binding,
            binding_selector=selector,
        )
    with pytest.raises(TypeError):
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=producer,
            schedule_binding_authority=object(),  # type: ignore[arg-type]
            binding_selector=selector,
        )
    with pytest.raises(TypeError):
        publish_schedule_row_quantity_from_binding(
            schedule_row_quantity_producer=producer,
            schedule_binding_authority=binding,
            binding_selector=object(),  # type: ignore[arg-type]
            universe_complete=True,
        )
