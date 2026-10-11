"""Q05: original text occurrences cannot replace physical room faces or m²."""
from __future__ import annotations

import fitz
import pytest

from tools.diag_lot16_room_face_scope import _native_word_label_census


def _two_linen_original_pdf() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=595.0, height=842.0)
        page.insert_text((90.0, 120.0), "WC", fontsize=12)
        page.insert_text((210.0, 145.0), "LINEN", fontsize=12)
        page.insert_text((205.0, 195.0), "LINEN /", fontsize=12)
        page.insert_text((280.0, 195.0), "BROOM", fontsize=12)
        return doc.tobytes()
    finally:
        doc.close()


def test_duplicate_native_linen_words_remain_distinct_untrusted_occurrences():
    result = _native_word_label_census(
        _two_linen_original_pdf(), 0, labels=("WC", "LINEN", "BROOM"),
    )
    assert result["diagnostic_only"] is True
    assert result["count_by_label"] == {"broom": 1, "linen": 2, "wc": 1}
    linen = [
        row for row in result["occurrences"]
        if row["raw_native_text"] == "LINEN"
    ]
    assert len(linen) == 2
    assert linen[0]["bbox_pt"] != linen[1]["bbox_pt"]
    assert {row["same_original_native_line_text_not_authority"] for row in linen} == {
        "LINEN", "LINEN /",
    }
    assert all(
        row["room_face_or_measurement_authority_granted"] is False
        for row in result["occurrences"]
    )
    assert all(row["source_page_index_zero_based"] == 0
               for row in result["occurrences"])


def test_no_native_label_filter_does_not_infer_room_vocabulary_from_text():
    result = _native_word_label_census(_two_linen_original_pdf(), 0)
    assert result["occurrences"] == []
    assert result["count_by_label"] == {}


def test_exact_unmatched_label_stays_missing_not_zero_room_area():
    result = _native_word_label_census(
        _two_linen_original_pdf(), 0, labels=("FREEZER",),
    )
    assert result["count_by_label"] == {}
    assert result["occurrences"] == []


def test_source_out_of_bounds_is_diagnostic_error_not_claimed_empty_area():
    with pytest.raises(ValueError, match="out of source bounds"):
        _native_word_label_census(
            _two_linen_original_pdf(), 999, labels=("WC",),
        )



def test_raw_planar_bbox_overlap_is_diagnostic_not_source_room_face_ownership():
    from tools.diag_lot16_room_face_scope import _raw_face_bbox_label_candidate_ledger

    # The point (80,80) is OUTSIDE the triangle even though inside its bbox.
    # Hence bbox-only matching can never grant physical room/metric authority.
    faces = (((0., 0.), (100., 0.), (0., 100.)),)
    words = {"occurrences": [
        {"raw_native_text": "WC", "bbox_pt": [79., 79., 81., 81.]},
    ]}
    result = _raw_face_bbox_label_candidate_ledger(faces, words)
    assert result["raw_candidate_count"] == 1
    assert result["bbox_rows"][0]["native_label_occurrence_indices_inside_bbox_only"] == [0]
    assert result["bbox_rows"][0]["room_face_or_measurement_authority_granted"] is False
    assert result["bbox_overlap_is_not_physical_ownership"] is True


def test_two_raw_candidate_bboxes_preserve_two_distinct_linen_word_locations():
    from tools.diag_lot16_room_face_scope import _raw_face_bbox_label_candidate_ledger

    faces = (
        ((0., 0.), (20., 0.), (20., 20.), (0., 20.)),
        ((25., 0.), (45., 0.), (45., 20.), (25., 20.)),
    )
    labels = {"occurrences": [
        {"raw_native_text": "LINEN", "bbox_pt": [8., 8., 9., 9.]},
        {"raw_native_text": "LINEN", "bbox_pt": [35., 8., 36., 9.]},
    ]}
    result = _raw_face_bbox_label_candidate_ledger(faces, labels)
    assert result["raw_candidate_count"] == 2
    assert result["bbox_rows"][0]["native_label_occurrence_indices_inside_bbox_only"] == [0]
    assert result["bbox_rows"][1]["native_label_occurrence_indices_inside_bbox_only"] == [1]
    assert not result["truncated"]
    assert all(
        row["room_face_or_measurement_authority_granted"] is False
        for row in result["bbox_rows"]
    )
