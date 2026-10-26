"""Real producer -> issuer -> customer batch must be all-or-nothing."""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_bound_wall_finish_customer_bridge import build_bound_wall_finish_rows
from pb_bound_wall_finish_quantity_authority import (
    SourceBoundWallFinishQuantityResult,
)
from pb_live_wall_finish_quantity_publication import publish_bound_wall_finish_quantity
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_bound_wall_finish_quantity_authority_v1 import (
    _binding, _finish_authority, _net_authority, _producer, _selector,
)


def _real():
    binding = _binding("b1", "face-1", "wall-1")
    producer = _producer(
        _finish_authority((binding,)),
        _net_authority({"wall-1": 12.5}),
    )
    result = producer.publish(_selector())
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    return producer, result.record


def _direct(items, *, fallback=None):
    app = SimpleNamespace(resolve_bound_wall_finishes=lambda _: items)
    if fallback is not None:
        app.source_bound_wall_finish_authority = fallback
        app.source_bound_wall_finish_selectors = (_selector(),)
    return build_bound_wall_finish_rows(app, 7, [])


def test_real_source_producer_reaches_single_customer_row_and_report():
    _, record = _real()
    rows, reports = _direct([record])
    assert len(rows) == len(reports) == 1
    assert rows[0][6] == 12.5
    assert rows[0][7] == "m²"
    assert reports[0]["quantity_id"] == publish_bound_wall_finish_quantity(record).quantity_id
    assert reports[0]["physical_surface_ids"] == list(record.physical_surface_ids)


@pytest.mark.parametrize("reverse", [False, True])
def test_forged_later_or_earlier_source_record_cannot_leave_partial_customer_rows(reverse):
    _, record = _real()
    forged = replace(record, quantity_m2=record.quantity_m2 + 1)
    with pytest.raises(ValueError, match="seal mismatch"):
        publish_bound_wall_finish_quantity(forged)
    batch = [record, forged]
    if reverse:
        batch.reverse()
    assert _direct(batch) == ([], [])


@pytest.mark.parametrize("reverse", [False, True])
def test_replayed_original_record_never_double_counts(reverse):
    _, record = _real()
    batch = [record, record]
    if reverse:
        batch.reverse()
    assert _direct(batch) == ([], [])


def test_resolver_generator_failure_after_first_valid_record_aborts_entire_batch():
    _, record = _real()
    def broken():
        yield record
        raise RuntimeError("original source inventory interrupted")
    assert _direct(broken()) == ([], [])


def test_valid_original_and_unresolved_independent_result_keep_valid_customer_row():
    _, record = _real()
    unresolved = SourceBoundWallFinishQuantityResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("original_finish_material_unavailable",),
        record=None,
    )
    rows, reports = _direct([unresolved, record])
    assert len(rows) == len(reports) == 1


def test_invalid_resolver_does_not_fall_back_to_valid_registered_authority():
    producer, record = _real()
    forged = replace(record, quantity_m2=record.quantity_m2 + 1)
    assert _direct([record, forged], fallback=producer.authority()) == ([], [])


def test_repeated_registered_selector_does_not_publish_duplicate_wall_finish():
    producer, _ = _real()
    app = SimpleNamespace(
        source_bound_wall_finish_authority=producer.authority(),
        source_bound_wall_finish_selectors=(_selector(), _selector()),
    )
    assert build_bound_wall_finish_rows(app, 7, []) == ([], [])


def test_registered_authority_single_valid_original_is_preserved():
    producer, record = _real()
    app = SimpleNamespace(
        source_bound_wall_finish_authority=producer.authority(),
        source_bound_wall_finish_selectors=(_selector(),),
    )
    rows, reports = build_bound_wall_finish_rows(app, 7, [])
    assert len(rows) == len(reports) == 1
    assert reports[0]["record_id"] == record.record_id


@pytest.mark.parametrize("reverse", [False, True])
def test_untyped_positive_resolver_member_does_not_silently_disappear(reverse):
    _, record = _real()
    batch = [record, {"quantity_m2": 12.5, "status": "corroborated"}]
    if reverse:
        batch.reverse()
    assert _direct(batch) == ([], [])


def test_input_original_source_batch_is_not_mutated():
    _, record = _real()
    source = [record, record]
    before = tuple(source)
    assert _direct(source) == ([], [])
    assert tuple(source) == before


@pytest.mark.parametrize("status", [
    EvidenceResolutionStatus.ABSTAINED,
    EvidenceResolutionStatus.CONFLICT,
])
def test_explicit_original_source_negative_cannot_borrow_fallback_authority(status):
    producer, _ = _real()
    source_negative = SourceBoundWallFinishQuantityResult(
        status=status,
        reason_codes=("original_finish_scope_not_proven",),
        record=None,
    )
    assert _direct([source_negative], fallback=producer.authority()) == ([], [])


def test_truly_empty_resolver_can_use_authenticated_fallback():
    producer, record = _real()
    rows, reports = _direct([], fallback=producer.authority())
    assert len(rows) == len(reports) == 1
    assert reports[0]["record_id"] == record.record_id
