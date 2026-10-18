"""Real SHA-pinned Maryborough A110↔A120 individual source ceiling marks.

Owner-only positive tests. The intentionally-private original PDF is not
published on GitHub; public CI skips when missing, rather than impersonating
original drawing acceptance with synthetic receipts.
"""
import hashlib
from pathlib import Path

import pytest

from tools.diag_gpt2_source_rcp_geometry_shadow import (
    audit_original_rcp_mark_in_source_ink_enclosure as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

OFFICE={
    "left":("d52239i0","d2532i0"),
    "right":("d66216i0","d2534i0"),
    "bottom":("d53725i0","d1954i0"),
    "top_partial":("d52625i0","d1859i0"),
}
PWD={
    "left":("d66215i0","d2343i0"),
    "right":("d53702i0","d1934i0"),
    "bottom":("d53724i0","d1955i0"),
    "top_partial":("d52626i0","d1858i0"),
}

@pytest.mark.skipif(not PDF.is_file(),reason="owner-private source required; not CI-verified")
@pytest.mark.parametrize("pairs,code,word_address,anchor,gap",[
    (OFFICE,"GRID",[10,1,0],"right",60.24),
    (PWD,"IPF1",[80,3,0],"left",59.52),
])
def test_original_p7_p9_ink_encloses_one_actual_mark_without_m2(
    pairs,code,word_address,anchor,gap
):
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(
        raw,expected_sha256=SHA,
        floor_page_1_based=7,rcp_page_1_based=9,
        original_side_pairs=pairs,
        expected_translation_pdf_pts=(106.32,0.),
        ceiling_code_literal=code,
    )
    assert result["status"]=="original_RCP_ink_enclosed_ceiling_mark_candidate_only"
    assert result["source_rcp_partial_wall_anchor"]==anchor
    source_gap=result["source_original_unclosed_door_gap_pdf_pts"]
    assert round(source_gap[1][0]-source_gap[0][0],2)==gap
    marks=result["original_RCP_source_mark_census"]
    assert marks["unique_native_code_word_in_enclosure"]
    assert len(marks["in_enclosure_candidates"])==1
    assert marks["in_enclosure_candidates"][0][
        "original_source_word_address"]==word_address
    assert not result["source_ceiling_material_occurrence_issued"]
    assert not result["physical_ceiling_room_identity_proven"]
    assert not result["original_top_door_gap_physically_closed"]
    assert result["ceiling_metric_area_m2"] is None
    assert result["new_firm_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not PDF.is_file(),reason="owner-private source required")
def test_original_rcp_office_different_material_or_transform_cannot_mint_area():
    raw=PDF.read_bytes()
    wrong=audit(
        raw,expected_sha256=SHA,floor_page_1_based=7,rcp_page_1_based=9,
        original_side_pairs=OFFICE,
        expected_translation_pdf_pts=(106.32,0.),
        ceiling_code_literal="IPF1",
    )
    assert wrong["status"]=="original_RCP_source_mark_unavailable"
    assert wrong["first_failure"]=="original_rcp_mark_missing_or_competing"
    assert wrong["new_firm_quantities"]==0
    with pytest.raises(ValueError,match="source_side_ink_or_translation_conflict"):
        audit(raw,expected_sha256=SHA,floor_page_1_based=7,
              rcp_page_1_based=9,original_side_pairs=PWD,
              expected_translation_pdf_pts=(78.,0.),
              ceiling_code_literal="IPF1")
