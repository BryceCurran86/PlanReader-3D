"""Original FT2/FT3 printed words are indexed without assuming physical floors."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.gpt2_native_material_mark_census import census_native_plan_material_words

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _synthetic():
    pdf = fitz.open()
    page = pdf.new_page(width=600, height=400)
    page.insert_text((35, 45), "FT2", fontsize=10)
    page.insert_text((250, 45), "FT3", fontsize=10)
    page.insert_text((40, 60), "FT33", fontsize=10)
    data = pdf.tobytes()
    pdf.close()
    return data


def _census(data, bbox=(0, 0, 200, 200), sha=None):
    return census_native_plan_material_words(
        data,
        expected_sha256=sha or hashlib.sha256(data).hexdigest(),
        page_number=1,
        plan_view_bbox_pdf_pts=bbox,
        codes=("FT2", "FT3"),
        viewport_id="authentic-view-required-upstream",
    )


def test_native_code_words_inside_vs_outside_are_not_rekeyed_to_same_floor():
    data = _synthetic()
    result = _census(data)
    assert len(result["within_supplied_plan_view"]) == 1
    assert len(result["outside_supplied_plan_view"]) == 1
    assert result["within_supplied_plan_view"][0]["material_code_untrusted"] == "FT2"
    assert result["outside_supplied_plan_view"][0]["material_code_untrusted"] == "FT3"
    assert result["new_firm_floor_finish_quantities"] == 0
    assert result["cross_sheet_floor_correspondence_proven"] is False


@pytest.mark.parametrize("bbox", [
    (0, 0, 0, 4), (0, 0, 2, float("inf")), ("a", 0, 4, 5),
])
def test_invalid_drawing_viewport_cannot_claim_source_words(bbox):
    with pytest.raises(ValueError, match="original_plan_view_bbox_invalid"):
        _census(_synthetic(), bbox=bbox)


def test_foreign_pdf_sha_fails_closed_before_words_are_decoded():
    with pytest.raises(ValueError, match="immutable_original_source_sha_mismatch"):
        _census(_synthetic(), sha="0"*64)


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="owner-private original unavailable")
def test_original_a140_ft2_ft3_native_occurrence_universe_is_preserved():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = census_native_plan_material_words(
        raw, expected_sha256=SHA, page_number=11,
        plan_view_bbox_pdf_pts=(251.52, 471.2, 1195.44, 1946.48),
        codes=("FT2", "FT3"),
        viewport_id="source_plan_view_c57aa3592e81d66ad2fa5a92",
    )
    inside = result["within_supplied_plan_view"]
    outside = result["outside_supplied_plan_view"]
    assert sum(x["material_code_untrusted"] == "FT2" for x in inside) == 8
    assert sum(x["material_code_untrusted"] == "FT3" for x in inside) == 5
    assert {x["material_code_untrusted"] for x in outside} == {"FT2", "FT3"}
    assert len(outside) == 2
    assert len(set(x["source_word_address"] for x in (*inside, *outside))) == 15
    assert result["new_firm_floor_finish_quantities"] == 0
