"""Original source label preflight cannot invent canonical label or physical room."""
from dataclasses import replace
from types import SimpleNamespace as O
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_source_room_label_authority import (
    SourceRoomLabelRecord, SourceRoomLabelWordEvidence, _RECORD_SEAL,
)
from tools.diag_gpt2_original_label_canonical_guard_preflight import (
    original_label_canonical_guard_preflight as inspect,
)

SHA = "c" * 64


def face():
    return O(
        document_id="doc", revision_id="rev", source_sha256=SHA,
        snapshot_id="snapshot", page_id="7",
        decision_scope_id="wall-source:viewport:7:v",
        face_id="source-face-one", record_id="source-face-receipt-one",
    )


def label(source=None):
    source = source or face()
    return SourceRoomLabelRecord(
        record_id="source-label-receipt-one",
        document_id=source.document_id, revision_id=source.revision_id,
        source_sha256=source.source_sha256,
        snapshot_id=source.snapshot_id, page_id=source.page_id,
        decision_scope_id=source.decision_scope_id,
        face_id=source.face_id,
        source_room_face_record_id=source.record_id,
        label="SALES", observation_ids=("native-word-one",),
        word_evidence=(SourceRoomLabelWordEvidence(
            observation_id="native-word-one", receipt_id="native-word-receipt-one",
            trusted_text="SALES", authority_kind="native_text_integrity",
            authority_record_id="text-auth-one",
            geometry=(10.0, 10.0, 40.0, 20.0), word_no=0,
        ),),
        source_bbox=(10.0, 10.0, 40.0, 20.0),
        status=S.CORROBORATED,
        reason_codes=("source_room_label_scope_resolved",), _seal=_RECORD_SEAL,
    )


def gate(faces=None, labels=None):
    result = inspect(
        faces if faces is not None else (face(),),
        labels if labels is not None else (label(),),
        expected_source_sha=SHA,
    )
    assert result["read_only"] is True
    assert result["benchmark_accuracy"] is None
    assert result["commercial_floor_or_finish_published"] is False
    return result["source_canonical_label_guard_preflights"]


def test_exact_original_face_and_native_word_can_pass_publisher_contract_without_area():
    row = gate()[0]
    assert row["original_direct_label"] == "SALES"
    assert row["first_unproved_source_canonical_guard"] == (
        "ORIGINAL_SOURCE_CANONICAL_LABEL_GUARD_ACCEPTS"
    )
    assert row["canonical_guard_accepts_original_label"] is True
    assert row["new_room_polygon_or_metric_inferred"] is False


@pytest.mark.parametrize("damage,first", [
    ("wrong_receipt", "ORIGINAL_FACE_RECEIPT_DOES_NOT_MATCH"),
    ("wrong_scope", "SOURCE_LABEL_CANONICAL_SCOPE_MISMATCH"),
    ("duplicate_face_label", "SOURCE_LABEL_UNIQUE_FACE_INDEX_WITHHELD"),
    ("missing_second_word", "ORIGINAL_WORD_WITNESS_INVENTORY_INCOMPLETE"),
    ("word_authority_untrusted", "CANONICAL_LABEL_NATIVE_WORD_WITNESS_REJECTED"),
])
def test_distinct_original_label_rejection_stage_is_not_repaired_by_name(damage, first):
    original = label()
    if damage == "wrong_receipt":
        original = replace(original, source_room_face_record_id="foreign-source-face")
    elif damage == "wrong_scope":
        original = replace(original, decision_scope_id="different-scope")
    elif damage == "missing_second_word":
        original = replace(original, observation_ids=("native-word-one", "word-two"))
    elif damage == "word_authority_untrusted":
        word = replace(original.word_evidence[0], authority_kind="untrusted-nearest")
        original = replace(original, word_evidence=(word,))
    if damage == "duplicate_face_label":
        rows = gate(labels=(original, replace(original, record_id="competing-label")))
    else:
        rows = gate(labels=(original,))
    assert all(r["first_unproved_source_canonical_guard"] == first for r in rows)
    assert all(not r["canonical_guard_accepts_original_label"] for r in rows)


@pytest.mark.parametrize("damage", [
    "duplicate_source_face", "duplicate_face_receipt", "wrong_sha",
    "untyped_source_label", "untrusted_expected_sha",
])
def test_source_face_inventory_must_be_exact_unambiguous_and_sha_authenticated(damage):
    f, records, labels, sha = face(), (face(),), (label(),), SHA
    if damage == "duplicate_source_face":
        records = (f, replace_on_namespace(f, record_id="other-source-receipt"))
    elif damage == "duplicate_face_receipt":
        records = (f, replace_on_namespace(
            f, face_id="other-source-face"
        ))
    elif damage == "wrong_sha":
        records = (replace_on_namespace(f, source_sha256="d"*64),)
    elif damage == "untyped_source_label":
        labels = (O(**vars(label())),)
    elif damage == "untrusted_expected_sha":
        sha = "not-a-source-hash"
    with pytest.raises(ValueError):
        inspect(records, labels, expected_source_sha=sha)


def replace_on_namespace(obj, **changes):
    values = dict(vars(obj))
    values.update(changes)
    return O(**values)
