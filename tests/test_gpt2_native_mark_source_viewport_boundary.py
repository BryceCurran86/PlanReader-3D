"""Original material annotation clipped by a view edge is not a plan finish."""
from pathlib import Path
import hashlib

import pytest

from tests.test_gpt2_native_ft2_ft3_original_mark_census import (
    _synthetic, _census,
)
from tools.gpt2_native_material_mark_census import census_native_plan_material_words

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_partially_cropped_ft2_stays_explicit_boundary_rival_not_plan_or_legend():
    raw = _synthetic()
    # The synthetic FT2 starts at PDF x=35 and ends east of x=40.
    result = _census(raw, bbox=(40, 0, 200, 200))
    assert result["within_supplied_plan_view"] == ()
    assert len(result["boundary_crossing_plan_words"]) == 1
    assert result["boundary_crossing_plan_words"][0]["material_code_untrusted"] == "FT2"
    assert len(result["outside_supplied_plan_view"]) == 1
    assert result["viewport_word_membership_unambiguous"] is False
    assert result["new_firm_floor_finish_quantities"] == 0


def test_uncropped_native_annotation_is_distinct_from_schedule_code():
    result = _census(_synthetic())
    assert len(result["within_supplied_plan_view"]) == 1
    assert len(result["outside_supplied_plan_view"]) == 1
    assert result["boundary_crossing_plan_words"] == ()
    assert result["viewport_word_membership_unambiguous"] is True


@pytest.mark.skipif(not ORIGINAL.is_file(), reason="owner-private original unavailable")
def test_original_a140_source_contains_no_half_cropped_ft2_ft3_words_in_issued_box():
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    result = census_native_plan_material_words(
        raw, expected_sha256=SHA, page_number=11,
        plan_view_bbox_pdf_pts=(251.52, 471.2, 1195.44, 1946.48),
        codes=("FT2", "FT3"),
        viewport_id="source_plan_view_c57aa3592e81d66ad2fa5a92",
    )
    assert result["boundary_crossing_plan_words"] == ()
    assert result["viewport_word_membership_unambiguous"] is True
    assert len(result["within_supplied_plan_view"]) == 13
    assert len(result["outside_supplied_plan_view"]) == 2
