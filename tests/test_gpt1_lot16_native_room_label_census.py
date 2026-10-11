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
        page.insert_text((205.0, 195.0), "LINEN", fontsize=12)
        page.insert_text((230.0, 195.0), "BROOM", fontsize=12)
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
