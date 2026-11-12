"""Shared source-page text is authenticated once, without merging room owners."""
from __future__ import annotations

import pb_same_view_room_area_authority as same_view
from tests import test_same_view_room_area_authority_v1 as fixtures


def test_same_view_batches_distinct_room_labels_on_one_source_page(monkeypatch):
    source, rooms = fixtures._source_and_rooms(second_label=True)
    real = same_view._trusted_lines_for_page
    calls = []

    def counted(*args, **kwargs):
        calls.append((kwargs["page_id"], tuple(kwargs["candidate_labels"])))
        return real(*args, **kwargs)

    monkeypatch.setattr(same_view, "_trusted_lines_for_page", counted)
    result = same_view.SameViewRoomAreaProducer.from_source(
        source=source, rooms=rooms
    ).publish()
    assert calls == [("1", ("spare room", "test room"))]
    # A second label outside the authentic dimension box cannot steal the
    # first room's valid measurement or multiply its customer quantity.
    assert len(result.records) == 1
    assert result.records[0].area_evidence.normalized_value == 8.64
    assert result.records[0].physical_room_id == "physical-room-1"
