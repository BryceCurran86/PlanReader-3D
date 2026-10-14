"""Fail-closed tests for source-owned W4 -> SourceRoomFace shadow receipts."""
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from tools.diag_gpt2_source_owned_plan_face_first_failure import (
    _face_report, replay,
)


def _wall(**changes):
    attrs = dict(
        document_id="document-a", revision_id="source-revision-a",
        source_sha256="source-sha-a", snapshot_id="source-snapshot-a",
        page_id="11", decision_scope_id="wall-source:viewport:11:original",
        viewport_id="source-proven-view", viewport_view_type="floor_finish_plan",
        viewport_bbox=(10.0, 20.0, 150.0, 160.0),
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True, reason_codes=(), records=("w4-a", "w4-b"),
    )
    return SimpleNamespace(**dict(attrs, **changes))


def _face(**changes):
    attrs = dict(
        document_id="document-a", revision_id="source-revision-a",
        source_sha256="source-sha-a", snapshot_id="source-snapshot-a",
        page_id="11", decision_scope_id="wall-source:viewport:11:original",
        status=EvidenceResolutionStatus.ABSTAINED, scope_complete=False,
        face_universe_complete=False,
        reason_codes=("source_room_face_boundary_unresolved",),
        records=(), abstained_faces=(),
        ownership_evaluation=SimpleNamespace(
            status="evaluated", competing_edge_count=1,
            unowned_edge_count=2, unresolved_face_ids=("source-face-a",),
            competing_wall_ids=("wall-a", "wall-b"),
        ),
    )
    return SimpleNamespace(**dict(attrs, **changes))


def test_real_unresolved_edge_receipts_remain_explicit_abstentions():
    report = _face_report(_wall(), _face())
    assert report["w4_candidate_count"] == 2
    assert report["source_room_face_record_count"] == 0
    assert report["shadow_competing_wall_ids"] == ("wall-a", "wall-b")
    assert report["shadow_unowned_edge_count"] == 2
    assert report["source_room_face_universe_complete"] is False
    assert all(
        report[key] is False
        for key in (
            "unique_physical_room_label_claim_granted",
            "physical_cross_sheet_equivalence_granted",
            "ft3_definition_claim_granted",
            "metric_quantity_claim_granted",
            "customer_row_claim_granted",
            "benchmark_match_claim_granted",
        )
    )


@pytest.mark.parametrize("changed", [
    {"source_sha256": "wrong-source-sha"},
    {"revision_id": "wrong-source-revision"},
    {"snapshot_id": "other-source-snapshot"},
    {"page_id": "7"},
    {"decision_scope_id": "wall-source:viewport:7:foreign"},
    {"document_id": "foreign-document"},
])
def test_source_face_scope_owner_is_exact(changed):
    with pytest.raises(ValueError, match="source_face_cross_revision_or_scope_mismatch"):
        _face_report(_wall(), _face(**changed))


def test_bad_page_address_cannot_be_used_to_invent_source_room():
    for page in (0, -1, 1.5, "11", None):
        with pytest.raises(ValueError, match="source_page_number_invalid"):
            replay(b"not-a-pdf", page_number=page)
