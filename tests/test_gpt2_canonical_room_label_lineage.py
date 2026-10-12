"""Canonical room semantics must preserve exact source-owned face ancestry."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_live_canonical_room_composition import (
    _room_object_from_record,
    _unique_source_room_labels_by_face,
    _verified_source_room_label_for_face,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_room_label_authority import (
    SourceRoomLabelRecord,
    SourceRoomLabelWordEvidence,
    _RECORD_SEAL,
)


def _face():
    return SimpleNamespace(
        record_id="source-face-record-7",
        document_id="document-1",
        revision_id="revision-1",
        source_sha256="a" * 64,
        snapshot_id="snapshot-1",
        page_id="7",
        decision_scope_id="wall-source:page-7",
        face_id="face-7",
        polygon_pdf_pts=((10.0, 10.0), (80.0, 10.0), (80.0, 40.0), (10.0, 40.0)),
        bounding_wall_ids=("wall-1", "wall-2", "wall-3", "wall-4"),
        area_page_pts2=2100.0,
    )


def _label(face=None):
    face = face or _face()
    return SourceRoomLabelRecord(
        record_id="source-room-label-7",
        document_id=face.document_id,
        revision_id=face.revision_id,
        source_sha256=face.source_sha256,
        snapshot_id=face.snapshot_id,
        page_id=face.page_id,
        decision_scope_id=face.decision_scope_id,
        face_id=face.face_id,
        source_room_face_record_id=face.record_id,
        label="FREEZER",
        observation_ids=("native-word-7",),
        word_evidence=(SourceRoomLabelWordEvidence(
            observation_id="native-word-7",
            receipt_id="text-receipt-7",
            trusted_text="FREEZER",
            authority_kind="native_text_integrity",
            authority_record_id="text-receipt-7",
            geometry=(20.0, 20.0, 55.0, 28.0),
            word_no=0,
        ),),
        source_bbox=(20.0, 20.0, 55.0, 28.0),
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("source_room_label_scope_resolved",),
        _seal=_RECORD_SEAL,
    )


def _canonical(face, label):
    return _room_object_from_record(
        face,
        viewport_id=None,
        canonical_wall_ids_by_candidate=None,
        unresolved_wall_candidate_ids=None,
        room_label_record=label,
    )


def test_exact_source_owned_label_can_bind_to_same_face_without_granting_metric():
    face = _face()
    room = _canonical(face, _label(face))
    assert room.room_label == "FREEZER"
    assert room.room_label_binding_record_id == "source-room-label-7"
    assert room.source_room_face_record_id == face.record_id
    assert room.geometry_complete
    assert room.metric_geometry_complete is False
    assert room.area_page_pts2 == 2100.0
    assert room.coordinate_unit == "pdf_pt"


@pytest.mark.parametrize("field,replacement", [
    ("document_id", "other-doc"),
    ("revision_id", "other-revision"),
    ("source_sha256", "b" * 64),
    ("snapshot_id", "other-snapshot"),
    ("page_id", "8"),
    ("decision_scope_id", "wall-source:page-8"),
    ("face_id", "other-face"),
    ("source_room_face_record_id", "other-face-record"),
])
def test_stale_or_cross_face_label_cannot_relabel_valid_geometry(field, replacement):
    face = _face()
    invalid = replace(_label(face), **{field: replacement})
    plain = _canonical(face, None)
    room = _canonical(face, invalid)
    assert _verified_source_room_label_for_face(face, invalid) is None
    assert room.room_label is None
    assert room.room_label_binding_record_id is None
    assert room.room_label_evidence_ids == ()
    assert room.canonical_room_id == plain.canonical_room_id
    assert room.polygon_pdf_pts == plain.polygon_pdf_pts
    assert room.source_room_face_record_id == face.record_id


def test_duplicate_identical_receipt_is_idempotent_but_distinct_competitor_abstains():
    first = _label()
    duplicate = replace(first)
    competitor = replace(first, record_id="other-label-receipt", label="SALES")
    assert _unique_source_room_labels_by_face((first, duplicate)) == {"face-7": first}
    assert _unique_source_room_labels_by_face((first, competitor)) == {}
    assert _unique_source_room_labels_by_face((competitor, first)) == {}
    assert _unique_source_room_labels_by_face((first, competitor, first)) == {}


def test_distinct_faces_keep_independent_receipts_on_competition():
    face = _face()
    first = _label(face)
    # A distinct physical face needs an independent native word observation,
    # not merely a different label record ID. Reusing native-word-7 would
    # correctly quarantine both faces under the cross-face replay guard.
    second_word = replace(
        first.word_evidence[0], observation_id="native-word-8",
        receipt_id="text-receipt-8", authority_record_id="text-receipt-8",
    )
    second = replace(
        first, face_id="face-8", source_room_face_record_id="source-face-record-8",
        record_id="source-label-8", observation_ids=("native-word-8",),
        word_evidence=(second_word,),
    )
    competitor = replace(first, record_id="competing-face-7-receipt")
    assert _unique_source_room_labels_by_face((first, second, competitor)) == {
        "face-8": second
    }



@pytest.mark.parametrize("reuse", ["source_receipt", "text_authority"])
def test_one_original_text_proof_must_not_label_two_physical_faces(reuse):
    first = _label()
    native = first.word_evidence[0]
    second_word = replace(
        native,
        observation_id="native-word-8",
        receipt_id=(
            native.receipt_id if reuse == "source_receipt" else "receipt-word-8"
        ),
        authority_record_id=(
            native.authority_record_id
            if reuse == "text_authority" else "authority-word-8"
        ),
    )
    other = replace(
        first,
        face_id="face-8",
        source_room_face_record_id="source-face-record-8",
        record_id="source-room-label-8",
        observation_ids=("native-word-8",),
        word_evidence=(second_word,),
    )
    for labels in ((first, other), (other, first)):
        assert _unique_source_room_labels_by_face(labels) == {}
    # An unrelated room with independent receipt ancestry survives.
    independent = replace(
        other,
        face_id="face-9",
        source_room_face_record_id="source-face-record-9",
        record_id="source-room-label-9",
        observation_ids=("native-word-9",),
        word_evidence=(replace(
            native, observation_id="native-word-9", receipt_id="receipt-word-9",
            authority_record_id="authority-word-9",
        ),),
    )
    assert _unique_source_room_labels_by_face((first, other, independent)) == {
        "face-9": independent
    }


@pytest.mark.parametrize("malformed", [
    "nested_observation", "nonfinite_bbox", "boolean_bbox",
    "degenerate_bbox", "reversed_bbox", "list_bbox",
    "boolean_word_number", "negative_word_number",
    "shared_word_receipt", "shared_word_authority",
])
def test_original_label_text_proofs_must_be_typed_unique_and_physically_bounded(malformed):
    face = _face()
    first = _label(face)
    native = first.word_evidence[0]
    if malformed == "nested_observation":
        damaged = replace(first, observation_ids=(["native-word-7"],))
    elif malformed == "nonfinite_bbox":
        damaged = replace(first, word_evidence=(
            replace(native, geometry=(20.0, 20.0, float("nan"), 28.0)),))
    elif malformed == "boolean_bbox":
        damaged = replace(first, word_evidence=(
            replace(native, geometry=(False, 20.0, 55.0, 28.0)),))
    elif malformed == "degenerate_bbox":
        damaged = replace(first, word_evidence=(
            replace(native, geometry=(20.0, 20.0, 20.0, 28.0)),))
    elif malformed == "reversed_bbox":
        damaged = replace(first, word_evidence=(
            replace(native, geometry=(55.0, 20.0, 20.0, 28.0)),))
    elif malformed == "list_bbox":
        damaged = replace(first, word_evidence=(
            replace(native, geometry=[20.0, 20.0, 55.0, 28.0]),))
    elif malformed == "boolean_word_number":
        damaged = replace(first, word_evidence=(replace(native, word_no=True),))
    elif malformed == "negative_word_number":
        damaged = replace(first, word_evidence=(replace(native, word_no=-1),))
    else:
        next_word = replace(
            native, observation_id="native-word-8",
            receipt_id=(
                native.receipt_id if malformed == "shared_word_receipt"
                else "receipt-8"
            ),
            authority_record_id=(
                native.authority_record_id
                if malformed == "shared_word_authority" else "authority-8"
            ),
            word_no=1,
        )
        damaged = replace(
            first, observation_ids=("native-word-7", "native-word-8"),
            word_evidence=(native, next_word),
        )
    assert _verified_source_room_label_for_face(face, damaged) is None
    canonical = _canonical(face, damaged)
    assert canonical.room_label is None
    assert canonical.source_room_face_record_id == face.record_id
    assert canonical.metric_geometry_complete is False


@pytest.mark.parametrize("damage", [
    "missing_observations", "nested_observations", "list_observations",
    "duplicate_observations", "count_mismatch", "list_word_evidence",
    "foreign_word_object",
])
def test_malformed_source_label_inventory_abstains_before_unique_face_index(damage):
    source = _face()
    first = _label(source)
    good = replace(
        first,
        face_id="unrelated-face", source_room_face_record_id="unrelated-face-receipt",
        record_id="unrelated-label-receipt", observation_ids=("independent-word",),
        word_evidence=(replace(
            first.word_evidence[0], observation_id="independent-word",
            receipt_id="independent-receipt",
            authority_record_id="independent-authority",
        ),),
    )
    if damage == "missing_observations":
        damaged = replace(first, observation_ids=None)
    elif damage == "nested_observations":
        damaged = replace(first, observation_ids=(["native-word-7"],))
    elif damage == "list_observations":
        damaged = replace(first, observation_ids=["native-word-7"])
    elif damage == "duplicate_observations":
        damaged = replace(first, observation_ids=("native-word-7", "native-word-7"))
    elif damage == "count_mismatch":
        damaged = replace(first, observation_ids=("native-word-7", "other-word"))
    elif damage == "list_word_evidence":
        damaged = replace(first, word_evidence=[first.word_evidence[0]])
    else:
        damaged = replace(first, word_evidence=(object(),))
    for records in ((damaged, good), (good, damaged)):
        assert _unique_source_room_labels_by_face(records) == {
            "unrelated-face": good
        }
        # Even a malformed sibling for the same face cannot be silently
        # replaced by a separately valid competing original label.
        assert _unique_source_room_labels_by_face(
            (first, damaged, good)
        ) == {"unrelated-face": good}


def _producer_sealed_raster_line_label(face=None, *, tokens=("FOOD", "PREP")):
    """Build a synthetic witness with the EXACT source line-producer contract."""
    original = _label(face)
    authority = "source_room_label_line_raster_corroboration_" + "c" * 32
    words = tuple(
        replace(
            original.word_evidence[0],
            observation_id=f"native-raster-word-{index}",
            receipt_id=f"native-raster-receipt-{index}",
            trusted_text=token,
            authority_kind="raster_text_line_corroboration",
            authority_record_id=authority,
            geometry=(20.0 + index * 20.0, 20.0, 37.0 + index * 20.0, 28.0),
            word_no=index,
        )
        for index, token in enumerate(tokens)
    )
    return replace(
        original,
        label=" ".join(tokens),
        observation_ids=tuple(word.observation_id for word in words),
        word_evidence=words,
    )


@pytest.mark.parametrize("tokens", [("FREEZER",), ("FOOD", "PREP")])
def test_source_sealed_whole_line_raster_proof_survives_canonical_without_metric(
    tokens,
):
    """Two independent source renders make ONE line receipt, not N receipts."""
    face = _face()
    positive = _producer_sealed_raster_line_label(face, tokens=tokens)
    assert _unique_source_room_labels_by_face((positive,)) == {
        face.face_id: positive
    }
    assert _verified_source_room_label_for_face(face, positive) is positive
    canonical = _canonical(face, positive)
    assert canonical.room_label == " ".join(tokens)
    assert canonical.room_label_binding_record_id == positive.record_id
    assert canonical.room_label_evidence_ids
    assert canonical.source_room_face_record_id == face.record_id
    assert canonical.polygon_pdf_pts == face.polygon_pdf_pts
    assert canonical.metric_geometry_complete is False


@pytest.mark.parametrize("damage", [
    "mixed_native_authority",
    "mismatched_line_authority",
    "unsealed_line_receipt_kind",
    "duplicate_native_word_receipt",
    "duplicate_source_word_number",
    "out_of_order_native_words",
    "altered_literal_line",
    "wrong_source_room_face",
    "wrong_decision_scope",
])
def test_invalid_whole_line_raster_proof_cannot_label_real_face(damage):
    face = _face()
    original = _producer_sealed_raster_line_label(face)
    first, second = original.word_evidence
    if damage == "mixed_native_authority":
        second = replace(second, authority_kind="native_text_integrity")
    elif damage == "mismatched_line_authority":
        second = replace(
            second, authority_record_id="source_room_label_line_raster_corroboration_" + "d" * 32
        )
    elif damage == "unsealed_line_receipt_kind":
        second = replace(second, authority_record_id="foreign-source-claim")
        first = replace(first, authority_record_id="foreign-source-claim")
    elif damage == "duplicate_native_word_receipt":
        second = replace(second, receipt_id=first.receipt_id)
    elif damage == "duplicate_source_word_number":
        second = replace(second, word_no=first.word_no)
    elif damage == "out_of_order_native_words":
        first = replace(first, word_no=1)
        second = replace(second, word_no=0)
    elif damage == "altered_literal_line":
        original = replace(original, label="SALES")
    elif damage == "wrong_source_room_face":
        original = replace(original, source_room_face_record_id="foreign-face-receipt")
    elif damage == "wrong_decision_scope":
        original = replace(original, decision_scope_id="unrelated-source-viewport")
    damaged = replace(original, word_evidence=(first, second))
    assert _verified_source_room_label_for_face(face, damaged) is None
    canonical = _canonical(face, damaged)
    assert canonical.room_label is None
    assert canonical.room_label_binding_record_id is None
    assert canonical.source_room_face_record_id == face.record_id
    assert canonical.geometry_complete is True
    assert canonical.metric_geometry_complete is False


def test_line_raster_authority_cannot_be_reused_across_independent_room_faces():
    first = _producer_sealed_raster_line_label(tokens=("FREEZER",))
    second_word = replace(
        first.word_evidence[0],
        observation_id="source-word-different-face",
        receipt_id="source-word-different-receipt",
    )
    other = replace(
        first,
        face_id="separate-physical-face",
        source_room_face_record_id="independent-source-face-receipt",
        record_id="independent-source-label-receipt",
        observation_ids=(second_word.observation_id,),
        word_evidence=(second_word,),
    )
    # Shared raster authority ID across different physical faces is opposed,
    # independent of enumeration order, even though word receipts differ.
    assert _unique_source_room_labels_by_face((first, other)) == {}
    assert _unique_source_room_labels_by_face((other, first)) == {}
