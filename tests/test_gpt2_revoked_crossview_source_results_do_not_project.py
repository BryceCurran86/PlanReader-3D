"""Cross-view publication never trusts stale records inside an ABSTAINED result."""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_cross_view_ceiling_finish_authority import CrossViewCeilingFinishResult
from tests.test_gpt2_floor_finish_result_cross_room_source_quarantine import (
    _producer_result, _public_result,
)
from tests.test_cross_view_ceiling_finish_authority import (
    _independent_ceiling_source_records,
)
from tests.test_gpt2_malformed_ceiling_quantity_result_quarantine import _issued


@pytest.mark.parametrize("blocked", [
    EvidenceResolutionStatus.ABSTAINED,
    EvidenceResolutionStatus.CONFLICT,
])
def test_no_floor_finish_quantities_when_original_result_revoked(monkeypatch, blocked):
    record, _ = _producer_result(monkeypatch)
    result = replace(_public_result(record), status=blocked)
    assert result.records_by_floor_id == {}
    assert result.quantities == ()


@pytest.mark.parametrize("blocked", [
    EvidenceResolutionStatus.ABSTAINED,
    EvidenceResolutionStatus.CONFLICT,
])
def test_no_rcp_ceiling_bindings_when_original_result_revoked(monkeypatch, blocked):
    record, _other = _independent_ceiling_source_records(monkeypatch)
    result = CrossViewCeilingFinishResult(
        status=blocked, reason_codes=("source-owner-revoked",),
        records=(record,), unresolved_physical_room_ids=(),
    )
    assert result.records_by_physical_room_id == {}


@pytest.mark.parametrize("blocked", [
    EvidenceResolutionStatus.ABSTAINED,
    EvidenceResolutionStatus.CONFLICT,
])
def test_no_signed_ceiling_m2_when_original_result_revoked(blocked):
    result = replace(_issued(), status=blocked)
    assert result.records_by_ceiling_id == {}
    assert result.quantities == ()
    assert result.canonical_ceilings == ()


def test_corrob_and_partial_with_independent_original_records_are_retained(monkeypatch):
    floor_record, _ = _producer_result(monkeypatch)
    floor = replace(_public_result(floor_record), status=EvidenceResolutionStatus.CANDIDATE)
    assert len(floor.quantities) == 1
    ceiling_record, _ = _independent_ceiling_source_records(monkeypatch)
    rcp = CrossViewCeilingFinishResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("partial",),
        records=(ceiling_record,), unresolved_physical_room_ids=("other-room",),
    )
    assert len(rcp.records_by_physical_room_id) == 1
    metric = replace(_issued(), status=EvidenceResolutionStatus.CANDIDATE)
    assert len(metric.quantities) == 1
