"""A reconstructed RCP result cannot mint rows from malformed source records."""
from __future__ import annotations

import pytest

import pb_cross_view_ceiling_finish_authority as ceiling
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_ceiling_finish_authority import (
    _independent_ceiling_source_records,
)


@pytest.mark.parametrize("rogue", [None, object(), {}, (), "another-room"])
def test_untyped_ceiling_source_record_quarantines_the_entire_result(
    monkeypatch, rogue,
):
    first, second = _independent_ceiling_source_records(monkeypatch)
    for records in ((first, rogue, second), (rogue, first, second),
                    (second, first, rogue)):
        result = ceiling.CrossViewCeilingFinishResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(ceiling.CROSS_VIEW_CEILING_FINISH_RESOLVED,),
            records=records,
            unresolved_physical_room_ids=(),
        )
        assert result.records_by_physical_room_id == {}


def test_valid_independent_ceiling_source_records_still_project(monkeypatch):
    first, second = _independent_ceiling_source_records(monkeypatch)
    result = ceiling.CrossViewCeilingFinishResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(ceiling.CROSS_VIEW_CEILING_FINISH_RESOLVED,),
        records=(second, first), unresolved_physical_room_ids=(),
    )
    assert set(result.records_by_physical_room_id) == {"room-1", "room-2"}
