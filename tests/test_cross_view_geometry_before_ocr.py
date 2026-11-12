"""Fail-closed geometry preflight for source dimension OCR."""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
import pb_cross_view_room_area_authority as authority
from tests import test_cross_view_room_area_authority_v1 as fixture


def test_unowned_native_strokes_reject_before_isolated_dimension_ocr(monkeypatch):
    source, rooms = fixture._source_and_room()
    fixture._force_dimension_words_to_isolated_authority(
        monkeypatch, source, rooms.rooms[0].revision_id
    )
    # No exact native stroke geometry can bind any of the source-only figured
    # dimensions. The issuer must abstain without attempting expensive OCR.
    monkeypatch.setattr(
        authority, "_canonical_segment_geometry", lambda values: None
    )

    def unexpected_ocr(*args, **kwargs):
        raise AssertionError("unowned geometry must never request OCR")

    monkeypatch.setattr(
        authority, "_isolated_dimension_numeric_corroboration", unexpected_ocr
    )
    result = authority.CrossViewRoomAreaProducer.from_source(
        source=source, rooms=rooms
    ).publish()
    assert result.records == ()
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT
    }
