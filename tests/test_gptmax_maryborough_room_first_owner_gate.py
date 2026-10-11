"""First Maryborough room-face failure must remain source-proven and nonpublishing."""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_physical_wall_candidate_authority import PhysicalWallCandidateScopeResult
from pb_source_room_face_authority import (
    SourceRoomFaceAbstention,
    SourceRoomFaceRecord,
    SourceRoomFaceScopeResult,
)
from tools.diag_gptmax_maryborough_room_first_owner_gate import (
    source_room_owner_first_gate,
)

SHA = "a" * 64
KEY = {
    "document_id": "live-source:" + SHA[:32],
    "revision_id": "revision-authenticated",
    "source_sha256": SHA,
    "snapshot_id": "snapshot-authenticated",
    "page_id": "7",
    "decision_scope_id": "wall-source:page-7",
}


def _scopes():
    wall = PhysicalWallCandidateScopeResult(
        status=S.ABSTAINED,
        scope_complete=False,
        records=(),
        source_observation_ids=(),
        reason_codes=("physical_wall_candidate_scope_bounds_unresolved",),
        **KEY,
    )
    room = SourceRoomFaceScopeResult(
        status=S.ABSTAINED,
        scope_complete=False,
        records=(),
        reason_codes=("source_room_face_scope_unavailable",),
        **KEY,
    )
    return wall, room


def _face():
    return SourceRoomFaceRecord(
        record_id="original-face-record",
        face_id="original-face-id",
        polygon_pdf_pts=((0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
        bounding_wall_ids=("original-wall",),
        area_page_pts2=0.5,
        **KEY,
    )


def _abstained():
    return SourceRoomFaceAbstention(
        face_id="abstained-source-face-id",
        reason="source_room_face_edge_owner_missing",
        polygon_pdf_pts=((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)),
        bounding_wall_ids=("original-wall",),
        area_page_pts2=2.0,
        **KEY,
    )


def test_original_wall_scope_first_gate_is_not_published():
    wall, room = _scopes()
    out = source_room_owner_first_gate(wall, room, expected_source_sha=SHA)
    assert out["first_unproved_authority"] == "PHYSICAL_WALL_SCOPE_NOT_AUTHENTICATED"
    assert out["room_source_face_count"] == 0
    assert out["room_abstained_face_count"] == 0
    assert out["decision_scope_id"] == "wall-source:page-7"
    assert out["wall_host_publication_allowed"] is False
    assert out["room_area_quantity_publication_allowed"] is False
    assert out["room_face_promotion_allowed"] is False
    assert out["benchmark_accuracy"] is None


def test_valid_wall_scope_without_source_room_face_never_promotes_label():
    wall, room = _scopes()
    wall = replace(wall, status=S.CORROBORATED, records=(object(),))
    out = source_room_owner_first_gate(wall, room, expected_source_sha=SHA)
    assert out["first_unproved_authority"] == "SOURCE_ROOM_FACE_SCOPE_NOT_AUTHENTICATED"
    assert out["room_source_face_receipt_ids"] == []


def test_partial_source_face_universe_retains_exact_abstention():
    wall, room = _scopes()
    wall = replace(wall, status=S.CORROBORATED, records=(object(),))
    room = replace(room, status=S.CORROBORATED,
                   records=(_face(),), abstained_faces=(_abstained(),))
    out = source_room_owner_first_gate(wall, room, expected_source_sha=SHA)
    assert out["first_unproved_authority"] == "PARTIAL_SOURCE_ROOM_FACE_UNIVERSE"
    assert out["room_source_face_receipt_ids"] == ["original-face-record"]
    assert out["room_abstention_reason_counts"] == {
        "source_room_face_edge_owner_missing": 1
    }
    assert out["room_area_quantity_publication_allowed"] is False


@pytest.mark.parametrize("damage", [
    "wrong_source_sha", "wrong_revision", "wrong_page", "bad_wall_scope",
    "bad_room_scope", "wrong_record_source", "wrong_abstention_source",
    "duplicate_face_id", "duplicate_record_id", "empty_record_id",
    "invalid_expected_sha", "invalid_reason",
])
def test_foreign_or_conflicted_source_receipts_fail_closed(damage):
    wall, room = _scopes()
    room = replace(room, status=S.CORROBORATED, records=(_face(),))
    if damage == "wrong_source_sha":
        wall = replace(wall, source_sha256="b" * 64)
    elif damage == "wrong_revision":
        room = replace(room, revision_id="foreign-revision")
    elif damage == "wrong_page":
        room = replace(room, page_id="11")
    elif damage == "bad_wall_scope":
        wall = object()
    elif damage == "bad_room_scope":
        room = object()
    elif damage == "wrong_record_source":
        room = replace(room, records=(replace(_face(), snapshot_id="foreign"),))
    elif damage == "wrong_abstention_source":
        room = replace(room, abstained_faces=(replace(_abstained(), source_sha256="b"*64),))
    elif damage == "duplicate_face_id":
        room = replace(room, records=(_face(), replace(_face(), record_id="second")))
    elif damage == "duplicate_record_id":
        room = replace(room, records=(_face(), replace(_face(), face_id="second")))
    elif damage == "empty_record_id":
        room = replace(room, records=(replace(_face(), record_id=""),))
    elif damage == "invalid_expected_sha":
        with pytest.raises(ValueError):
            source_room_owner_first_gate(wall, room, expected_source_sha="wrong")
        return
    elif damage == "invalid_reason":
        wall = replace(wall, reason_codes=("",))
    with pytest.raises((ValueError, TypeError)):
        source_room_owner_first_gate(wall, room, expected_source_sha=SHA)
