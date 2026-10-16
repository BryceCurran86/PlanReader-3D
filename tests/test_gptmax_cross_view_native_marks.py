"""Negative authority tests for original native text cross-view research."""
from hashlib import sha256
from pathlib import Path
import sys

import fitz
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from diag_gptmax_cross_view_native_marks import (
    STATUS, inventory_native_marks, native_phrase_occurrences,
    original_pdf_mark_inventory,
)

def word(token, n, *, block=1, line=2, x=10.0, y=50.0):
    return (x, y, x + 6, y + 6, token, block, line, n)

class Page:
    def __init__(self, words):
        self.words = words
    def get_text(self, mode):
        assert mode == "words"
        return self.words

def test_native_phrase_includes_original_box_and_is_input_order_stable():
    words = [word("STACKER", 9, x=18), word("2127", 8)]
    a = native_phrase_occurrences(words, "2127 STACKER")
    b = native_phrase_occurrences(tuple(reversed(words)), "2127 STACKER")
    assert a == b and len(a) == 1
    assert a[0]["word_indices"] == [8, 9]
    assert a[0]["envelope_pdf_pt"] == [10.0, 50.0, 24.0, 56.0]
    assert a[0]["source_text_only"]

@pytest.mark.parametrize("words", [
    [word("2127", 0), word("STACKER", 2, x=18)],
    [word("2127", 0), word("STACKER", 1, line=3, x=18)],
    [word("2127", 0), word("STACKER", 1, block=2, x=18)],
    [word("2127", 0), word("SLIDER", 1, x=18)],
    [word("2127", 0), word("STACKER", 1, x=18, y=float("inf"))],
])
def test_no_remote_or_foreign_role_phrase_stitch(words):
    assert native_phrase_occurrences(words, "2127 STACKER") == ()

def test_repeated_plan_and_elevation_text_is_unbound():
    doc = [Page([]) for _ in range(6)]
    doc[3] = Page([word("2127", 0), word("STACKER", 1, x=18)])
    doc[5] = Page([word("2127", 0), word("STACKER", 1, x=18),
                   word("FSL", 0, line=8), word("68560", 0, line=9),
                   word("JL", 0, line=10), word("70660", 0, line=11),
                   word("2100", 0, line=12), word("2590", 0, line=13)])
    r = inventory_native_marks(doc, page_ids=[5, 3],
        phrase="2127 STACKER", datum_tokens=["FSL", "JL", "2100"])
    assert r["status"] == STATUS and r["occurrence_count"] == 2
    assert r["requested_source_page_indices"] == [3, 5]
    assert len(r["pages"][1]["datum_token_occurrences"]["2100"]) == 1
    for field in ("page_viewport_identity_proven",
                  "cross_sheet_physical_identity_proven",
                  "opening_kind_proven", "opening_host_proven",
                  "ordered_width_height_proven",
                  "datum_to_opening_alignment_proven",
                  "opening_count_proven", "firm_quantity_granted"):
        assert r[field] is False

def test_duplicate_marks_are_not_first_choice():
    marks = [word("2127", 0, line=0), word("STACKER", 1, line=0, x=18),
             word("2127", 0, line=1), word("STACKER", 1, line=1, x=18)]
    assert len(native_phrase_occurrences(marks, "2127 STACKER")) == 2

@pytest.mark.parametrize("pages", [[], [0, 0], [1], [-1]])
def test_bad_page_scope_fails_closed(pages):
    with pytest.raises(ValueError):
        inventory_native_marks([Page([])], page_ids=pages,
                               phrase="2127 STACKER", datum_tokens=[])

def test_original_pdf_sha_and_source_immutability(tmp_path):
    doc = fitz.open()
    doc.new_page().insert_text((20, 20), "2127 STACKER")
    src = tmp_path / "original.pdf"
    src.write_bytes(doc.tobytes())
    doc.close()
    initial = src.read_bytes()
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        original_pdf_mark_inventory(src, expected_sha256="0" * 64,
            page_ids=[0], phrase="2127 STACKER", datum_tokens=[])
    r = original_pdf_mark_inventory(src,
        expected_sha256=sha256(initial).hexdigest(),
        page_ids=[0], phrase="2127 STACKER", datum_tokens=[])
    assert r["source_sha256"] == sha256(initial).hexdigest()
    assert src.read_bytes() == initial
    assert r["firm_quantity_granted"] is False

def test_missing_phrase_abstains():
    with pytest.raises(ValueError):
        native_phrase_occurrences([], " ")
