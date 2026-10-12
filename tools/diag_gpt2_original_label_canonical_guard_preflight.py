"""Original producer-owned room label -> canonical publisher guard preflight.

This is diagnostic ONLY. Do not attach a missing label or project a room area.
The caller must supply source room faces and native label receipts from one
producer-authenticated SHA/viewport scope, never name/nearest-face matches.
"""
from __future__ import annotations

from collections import Counter

from pb_live_canonical_room_composition import (
    _unique_source_room_labels_by_face,
    _verified_source_room_label_for_face,
)
from pb_source_room_label_authority import SourceRoomLabelRecord


_SCOPE = (
    "document_id", "revision_id", "source_sha256", "snapshot_id",
    "page_id", "decision_scope_id",
)


def original_label_canonical_guard_preflight(
    faces: tuple[object, ...],
    labels: tuple[SourceRoomLabelRecord, ...],
    *,
    expected_source_sha: str,
) -> dict:
    """Explain why an original source-positive label might be lost by canonical.

    A positive here means ONLY the canonical label gate would accept the
    producer-owned source receipt; this helper does not mutate any producer.
    """
    if (type(expected_source_sha) is not str
            or len(expected_source_sha) != 64
            or any(c not in "0123456789abcdef" for c in expected_source_sha)
            or type(faces) is not tuple or type(labels) is not tuple):
        raise ValueError("original typed source inventory required")

    def source_id(value):
        return value if type(value) is str and bool(value) and value == value.strip() else None

    faces_by_id = {}
    face_receipts = set()
    for face in faces:
        face_id = source_id(getattr(face, "face_id", None))
        receipt = source_id(getattr(face, "record_id", None))
        if (face_id is None or receipt is None or face_id in faces_by_id
                or receipt in face_receipts
                or getattr(face, "source_sha256", None) != expected_source_sha):
            raise ValueError("original physical room face scope or identity disputed")
        face_receipts.add(receipt)
        faces_by_id[face_id] = face

    for label in labels:
        if (type(label) is not SourceRoomLabelRecord
                or label.source_sha256 != expected_source_sha
                or source_id(label.face_id) is None
                or source_id(label.source_room_face_record_id) is None):
            raise ValueError("foreign or invalid original source label record")

    indexed = _unique_source_room_labels_by_face(labels)
    label_face_counts = Counter(row.face_id for row in labels)
    out = []
    for label in sorted(labels, key=lambda r: (r.face_id, r.record_id)):
        face = faces_by_id.get(label.face_id)
        exact_face = (
            face is not None
            and label.source_room_face_record_id == getattr(face, "record_id", None)
        )
        same_scope = face is not None and all(
            getattr(label, key, None) == getattr(face, key, None)
            for key in _SCOPE
        )
        words = label.observation_ids
        word_evidence = label.word_evidence
        source_word_inventory = (
            type(words) is tuple and type(word_evidence) is tuple
            and bool(words) and len(words) == len(word_evidence)
        )
        indexed_label = indexed.get(label.face_id)
        indexed_unique = (
            label_face_counts[label.face_id] == 1 and indexed_label == label
        )
        canonical_guard_accepts = False
        if indexed_unique and exact_face and same_scope and source_word_inventory:
            try:
                canonical_guard_accepts = (
                    _verified_source_room_label_for_face(face, indexed_label) is not None
                )
            except (TypeError, ValueError, AttributeError):
                # Keep malformed original producer evidence diagnostic-only.
                canonical_guard_accepts = False
        if not exact_face:
            first = "ORIGINAL_FACE_RECEIPT_DOES_NOT_MATCH"
        elif not same_scope:
            first = "SOURCE_LABEL_CANONICAL_SCOPE_MISMATCH"
        elif label_face_counts[label.face_id] != 1:
            # A genuinely competing face claim is distinct from quarantine of
            # one malformed native-word record by the canonical unique index.
            first = "SOURCE_LABEL_UNIQUE_FACE_INDEX_WITHHELD"
        elif not source_word_inventory:
            first = "ORIGINAL_WORD_WITNESS_INVENTORY_INCOMPLETE"
        elif not indexed_unique:
            first = "SOURCE_LABEL_UNIQUE_FACE_INDEX_WITHHELD"
        elif not canonical_guard_accepts:
            first = "CANONICAL_LABEL_NATIVE_WORD_WITNESS_REJECTED"
        else:
            first = "ORIGINAL_SOURCE_CANONICAL_LABEL_GUARD_ACCEPTS"
        out.append({
            "source_label_receipt_id": label.record_id,
            "source_room_face_record_id": label.source_room_face_record_id,
            "source_face_id": label.face_id,
            "original_direct_label": label.label,
            "original_face_receipt_exact": bool(exact_face),
            "original_scope_matches_canonical_guard": bool(same_scope),
            "source_word_receipt_count": len(words) if type(words) is tuple else None,
            "source_word_evidence_count": (
                len(word_evidence) if type(word_evidence) is tuple else None
            ),
            "unique_original_label_index_retains": bool(indexed_unique),
            "canonical_guard_accepts_original_label": bool(canonical_guard_accepts),
            "first_unproved_source_canonical_guard": first,
            "new_room_polygon_or_metric_inferred": False,
        })
    return {
        "original_source_sha256": expected_source_sha,
        "source_positive_label_count": len(labels),
        "source_canonical_label_guard_preflights": out,
        "read_only": True,
        "commercial_floor_or_finish_published": False,
        "benchmark_accuracy": None,
    }
