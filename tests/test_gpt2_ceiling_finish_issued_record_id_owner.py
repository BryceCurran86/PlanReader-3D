"""Cross-view RCP finish record IDs are physical source ownership, not aliases."""
from __future__ import annotations

from dataclasses import replace

import pb_cross_view_ceiling_finish_authority as ceiling
from pb_migration_contracts import EvidenceResolutionStatus
from tests.test_cross_view_ceiling_finish_authority import (
    _independent_ceiling_source_records,
)


def test_reissued_ceiling_finish_record_identity_quarantines_both_rooms(monkeypatch):
    first, second = _independent_ceiling_source_records(monkeypatch)
    conflicting = replace(second, record_id=first.record_id)
    for records in ((first, conflicting), (conflicting, first)):
        accepted, disputed = ceiling._quarantine_reused_ceiling_source_ownership(records)
        assert accepted == ()
        assert disputed == ("room-1", "room-2")
        result = ceiling.CrossViewCeilingFinishResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(ceiling.CROSS_VIEW_CEILING_FINISH_RESOLVED,),
            records=records, unresolved_physical_room_ids=(),
        )
        assert result.records_by_physical_room_id == {}


def test_malformed_ceiling_finish_record_identity_never_projects(monkeypatch):
    first, second = _independent_ceiling_source_records(monkeypatch)
    for bad in ("", " ", "\t", None):
        changed = replace(second, record_id=bad)
        accepted, disputed = ceiling._quarantine_reused_ceiling_source_ownership(
            (changed, first)
        )
        assert accepted == (first,)
        assert disputed == ("room-2",)


def test_independent_ceiling_record_ids_remain_owned(monkeypatch):
    first, second = _independent_ceiling_source_records(monkeypatch)
    assert first.record_id != second.record_id
    accepted, disputed = ceiling._quarantine_reused_ceiling_source_ownership(
        (second, first)
    )
    assert {record.physical_room_id for record in accepted} == {
        "room-1", "room-2"
    }
    assert disputed == ()
