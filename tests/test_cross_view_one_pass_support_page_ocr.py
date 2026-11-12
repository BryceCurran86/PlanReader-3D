"""Cross-view source labels and annotations share one authenticated page read.

The strict same-page exclusion, exact-label prerequisites, and independent
dimension/witness checks still own the decision; only repeated OCR is removed.
"""
from __future__ import annotations

import pb_cross_view_room_area_authority as cross_view
from tests import test_cross_view_room_area_authority_v1 as fixtures
from pb_migration_contracts import EvidenceResolutionStatus


def test_original_support_page_labels_authenticate_only_once(monkeypatch):
    source, rooms = fixtures._source_and_room()
    original = cross_view._trusted_lines_for_page
    requests = []

    def counted(source_arg, **kwargs):
        requests.append((kwargs["page_id"], kwargs.get("allow_compound_annotations", False)))
        return original(source_arg, **kwargs)

    monkeypatch.setattr(cross_view, "_trusted_lines_for_page", counted)
    result = cross_view.CrossViewRoomAreaProducer.from_source(
        source=source, rooms=rooms
    ).publish()
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert len(result.records) == 1
    assert result.records[0].area_evidence.normalized_value == 8.64
    assert requests == [("2", True)]


def test_compound_only_source_label_still_cannot_issue_an_area(monkeypatch):
    source, rooms = fixtures._source_and_room()
    compound = cross_view._TrustedLine(
        page_id="2",
        text="TEST ROOM / STORE",
        bbox=(100.0, 70.0, 180.0, 78.0),
        observation_ids=("compound-only",),
        receipt_ids=("receipt-compound",),
        source_partition_id="partition-2",
        block_no=10,
        line_no=0,
        label_members=("test room", "store"),
    )
    requested = []

    def only_compound(source_arg, **kwargs):
        requested.append(kwargs.get("allow_compound_annotations", False))
        return (compound,)

    def forbidden_dimension(*args, **kwargs):
        raise AssertionError("compound-only label must not reach dimension authority")

    monkeypatch.setattr(cross_view, "_trusted_lines_for_page", only_compound)
    monkeypatch.setattr(cross_view, "_trusted_native_dimensions_for_page", forbidden_dimension)
    result = cross_view.CrossViewRoomAreaProducer.from_source(
        source=source, rooms=rooms
    ).publish()
    assert result.records == ()
    assert result.status in {
        EvidenceResolutionStatus.ABSTAINED,
        EvidenceResolutionStatus.CONFLICT,
    }
    assert requested == [True]
