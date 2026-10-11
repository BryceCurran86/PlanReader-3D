"""First Maryborough room-face failure must remain source-proven and nonpublishing."""
from dataclasses import replace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_physical_wall_candidate_authority import PhysicalWallCandidateScopeResult
from pb_source_room_label_authority import SourceRoomLabelScopeResult
from pb_source_room_face_authority import (
    SourceRoomFaceAbstention,
    SourceRoomFaceRecord,
    SourceRoomFaceScopeResult,
)
from tools.diag_gptmax_maryborough_room_first_owner_gate import (
    source_room_owner_first_gate,
    source_room_label_first_gate,
    source_withheld_boundary_w4_census,
    _distinct_source_faces_for_word_ownership,
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


def _label_scope():
    return SourceRoomLabelScopeResult(
        status=S.ABSTAINED, reason_codes=("source_room_label_unavailable",),
        records=(), split_face_candidates=(), **KEY,
    )


def test_no_authenticated_labels_does_not_elect_physical_room_identity():
    _, room = _scopes()
    result = source_room_label_first_gate(
        room, _label_scope(), expected_source_sha=SHA,
    )
    assert result["direct_source_label_count"] == 0
    assert result["split_source_label_candidate_count"] == 0
    assert result["original_label_reason_codes"] == ["source_room_label_unavailable"]
    assert result["firm_room_area_publication_allowed"] is False
    assert result["source_room_geometry_inferred_from_labels"] is False
    assert result["split_label_room_publication_allowed"] is False


@pytest.mark.parametrize("damage", [
    "foreign_revision", "foreign_snapshot", "foreign_page", "foreign_sha",
    "invalid_expected_sha", "invalid_reason", "forged_record",
    "forged_split_candidate", "duplicate_physical_face",
])
def test_label_source_scope_cannot_launder_foreign_room_or_text(damage):
    _, room = _scopes()
    labels = _label_scope()
    if damage == "foreign_revision":
        labels = replace(labels, revision_id="foreign")
    elif damage == "foreign_snapshot":
        labels = replace(labels, snapshot_id="foreign")
    elif damage == "foreign_page":
        labels = replace(labels, page_id="11")
    elif damage == "foreign_sha":
        labels = replace(labels, source_sha256="b" * 64)
    elif damage == "invalid_expected_sha":
        with pytest.raises(ValueError):
            source_room_label_first_gate(room, labels, expected_source_sha="not-sha")
        return
    elif damage == "invalid_reason":
        labels = replace(labels, reason_codes=("",))
    elif damage == "forged_record":
        labels = replace(labels, records=(object(),))
    elif damage == "forged_split_candidate":
        labels = replace(labels, split_face_candidates=(object(),))
    elif damage == "duplicate_physical_face":
        room = replace(room, records=(_face(), _face()))
    with pytest.raises((TypeError, ValueError)):
        source_room_label_first_gate(room, labels, expected_source_sha=SHA)


def test_split_source_words_can_repeat_the_same_authenticated_face():
    first = _face()
    second = replace(
        first, face_id="second-authenticated-face",
        record_id="second-authenticated-receipt",
    )
    inventory = {first.face_id:first, second.face_id:second}
    assert _distinct_source_faces_for_word_ownership(
        (first.face_id, first.face_id, second.face_id, second.face_id),
        (first.record_id, second.record_id),
        inventory,
    ) == (first.face_id, second.face_id)


@pytest.mark.parametrize("damage", [
    "foreign_face", "reversed_receipts", "duplicate_receipt", "bad_count",
    "only_one_face", "blank_word_face", "whitespace_word_face",
    "non_string_face", "missing_inventory", "malformed_receipts",
])
def test_split_word_owner_never_fabricates_original_room_face(damage):
    first = _face()
    second = replace(
        first, face_id="second-authenticated-face",
        record_id="second-authenticated-receipt",
    )
    inventory = {first.face_id:first, second.face_id:second}
    words = (first.face_id, first.face_id, second.face_id)
    receipts = (first.record_id, second.record_id)
    if damage == "foreign_face":
        words = (*words, "foreign")
    elif damage == "reversed_receipts":
        receipts = tuple(reversed(receipts))
    elif damage == "duplicate_receipt":
        receipts = (first.record_id, first.record_id)
    elif damage == "bad_count":
        receipts = (first.record_id,)
    elif damage == "only_one_face":
        words = (first.face_id, first.face_id)
        receipts = (first.record_id,)
    elif damage == "blank_word_face":
        words = (first.face_id, "", second.face_id)
    elif damage == "whitespace_word_face":
        words = (first.face_id, " " + second.face_id, second.face_id)
    elif damage == "non_string_face":
        words = (first.face_id, object(), second.face_id)
    elif damage == "missing_inventory":
        inventory.pop(second.face_id)
    elif damage == "malformed_receipts":
        receipts = (first.record_id, object())
    with pytest.raises((ValueError, TypeError)):
        _distinct_source_faces_for_word_ownership(words, receipts, inventory)


def _boundary_owner_source_fixture():
    """Two independent original face identities; shared W4 ID is NOT adjacency."""
    _, room = _scopes()
    face = _face()
    withheld = replace(
        _abstained(),
        reason="source_room_face_boundary_unresolved",
        bounding_wall_ids=("original-wall", "other-unproven-wall"),
    )
    room = replace(room, status=S.CORROBORATED, scope_complete=True,
                   records=(face,), abstained_faces=(withheld,))
    labels = {
        "firm_room_area_publication_allowed": False,
        "direct_source_labels": [{
            "label": "ORIGINAL LABEL",
            "source_face_id": face.face_id,
            "source_face_receipt_id": face.record_id,
        }],
    }
    return room, labels


def test_boundary_receipt_shared_wall_id_does_not_claim_adjacency_or_quantity():
    room, labels = _boundary_owner_source_fixture()
    result = source_withheld_boundary_w4_census(
        room, labels, expected_source_sha=SHA,
    )
    assert len(result) == 1
    row = result[0]
    assert row["source_withheld_face_id"] == "abstained-source-face-id"
    assert row["source_withheld_reason"] == "source_room_face_boundary_unresolved"
    assert row["original_w4_candidate_ids"] == [
        "original-wall", "other-unproven-wall",
    ]
    assert row["original_physical_wall_adjacency_proven"] is False
    assert row["original_withheld_face_room_publication_allowed"] is False
    assert row["original_metric_quantity_publication_allowed"] is False
    assert row["same_w4_candidate_receipt_seen_on_authenticated_label"] == [{
        "original_authenticated_label": "ORIGINAL LABEL",
        "source_positive_room_face_id": "original-face-id",
        "source_positive_room_face_receipt_id": "original-face-record",
        "shared_source_w4_candidate_ids": ["original-wall"],
        "physical_wall_adjacency_proven": False,
        "withheld_face_promotion_allowed": False,
    }]
    assert len(row["original_source_polygon_pdf_pts"]) == 3


def test_missing_shared_w4_id_does_not_mean_no_physical_adjacency():
    room, labels = _boundary_owner_source_fixture()
    withheld = replace(
        room.abstained_faces[0], bounding_wall_ids=("other-source-wall",)
    )
    room = replace(room, abstained_faces=(withheld,))
    result = source_withheld_boundary_w4_census(
        room, labels, expected_source_sha=SHA,
    )
    assert result[0]["same_w4_candidate_receipt_seen_on_authenticated_label"] == []
    assert result[0]["original_physical_wall_adjacency_proven"] is False


@pytest.mark.parametrize("damage", [
    "wrong_sha", "missing_positive", "duplicate_direct_label",
    "wrong_direct_face", "foreign_abstained", "duplicate_abstained",
    "duplicate_wall", "bad_wall", "bad_polygon", "wrong_label_gate",
])
def test_withheld_boundary_census_does_not_borrow_source_owner(damage):
    room, labels = _boundary_owner_source_fixture()
    if damage == "wrong_sha":
        room = replace(room, source_sha256="b"*64)
    elif damage == "missing_positive":
        room = replace(room, records=())
    elif damage == "duplicate_direct_label":
        labels["direct_source_labels"].append(
            dict(labels["direct_source_labels"][0])
        )
    elif damage == "wrong_direct_face":
        labels["direct_source_labels"][0]["source_face_id"] = "different"
    elif damage == "foreign_abstained":
        room = replace(room, abstained_faces=(
            replace(room.abstained_faces[0], revision_id="foreign"),))
    elif damage == "duplicate_abstained":
        room = replace(room, abstained_faces=(
            room.abstained_faces[0], room.abstained_faces[0]))
    elif damage == "duplicate_wall":
        room = replace(room, abstained_faces=(
            replace(room.abstained_faces[0],
                    bounding_wall_ids=("original-wall","original-wall")),))
    elif damage == "bad_wall":
        room = replace(room, abstained_faces=(
            replace(room.abstained_faces[0],bounding_wall_ids=("",)),))
    elif damage == "bad_polygon":
        room = replace(room, abstained_faces=(
            replace(room.abstained_faces[0],
                    polygon_pdf_pts=((0.,0.), (float("nan"),1.), (2.,2.))),))
    elif damage == "wrong_label_gate":
        labels["firm_room_area_publication_allowed"] = True
    with pytest.raises((TypeError, ValueError)):
        source_withheld_boundary_w4_census(
            room, labels, expected_source_sha=SHA,
        )
