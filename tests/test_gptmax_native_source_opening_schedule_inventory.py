"""Native source words are never a unique opening/schedule instance binding."""
from copy import deepcopy

import fitz
import pytest

from tools.diag_gptmax_native_source_opening_schedule_inventory import (
    native_source_text_inventory,
)


def _native_source():
    pdf = fitz.open()
    p1 = pdf.new_page(width=720, height=480)
    p1.insert_text((20, 35), "DOOR SCHEDULE", fontsize=12)
    p1.insert_text((25, 120), "870", fontsize=11)
    p1.insert_text((110, 120), "2100", fontsize=11)
    p2 = pdf.new_page(width=720, height=480)
    p2.insert_text((35, 70), "870", fontsize=10)
    p2.insert_text((180, 280), "D03", fontsize=10)
    result = pdf.tobytes()
    pdf.close()
    return result


def test_original_pdf_words_preserve_page_and_native_box_source_address():
    original = _native_source()
    result = native_source_text_inventory(original)
    assert result["source_page_count"] == 2
    assert [p["page_id"] for p in result["pages"]] == ["1", "2"]
    assert all(p["word_count"] > 0 for p in result["pages"])
    assert all(word["bbox_pdf_pts"][2] > word["bbox_pdf_pts"][0]
               for p in result["pages"] for word in p["source_native_words"])
    assert any(w["text"] == "2100" for w in result["pages"][0]["source_native_words"])
    assert any(w["text"] == "870" for w in result["pages"][1]["source_native_words"])
    assert result["source_sha256"] != native_source_text_inventory(original+b"\n")["source_sha256"]
    assert result["opening_instance_bound"] is False
    assert result["opening_height_granted"] is False
    assert result["customer_quantity_granted"] is False
    assert result["benchmark_accuracy_granted"] is False


def test_native_word_reordering_cannot_infer_a_schedule_binding():
    original = _native_source()
    result = native_source_text_inventory(original)
    mutated = deepcopy(result)
    mutated["pages"][0]["source_native_words"].reverse()
    for report in (result, mutated):
        assert report["opening_instance_bound"] is False
        assert report["opening_height_granted"] is False
        assert report["customer_quantity_granted"] is False


@pytest.mark.parametrize("value", [b"", None, "not-bytes", 0])
def test_missing_or_forged_pdf_fails_closed(value):
    with pytest.raises((ValueError, TypeError, fitz.FileDataError)):
        native_source_text_inventory(value)
