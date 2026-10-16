"""True FT2/FT3 original native schedule rows, not guessed nearby words."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_original_native_finish_schedule_row_source_shadow import (
    audit_source_owned_material_schedule_rows as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
PLAN=(251.,471.,1195.5,1947.)
SCHEDULE=(1290.,1880.,1520.,2230.)


def _source(page):
    return audit(page,original_code_literals=("FT1","FT2","FT3","WT1"),
                 original_plan_candidate_bbox=PLAN,
                 original_schedule_candidate_bbox=SCHEDULE)


def test_original_ft2_ft3_have_same_native_source_block_floor_rows_and_real_marks():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        result=_source(doc[10])
        summary=result["all_original_source_finish_code_summaries"]
        assert summary["FT2"]["original_schedule_row_candidates"]==1
        assert summary["FT3"]["original_schedule_row_candidates"]==1
        assert summary["FT2"]["native_sameblock_floor_role_candidates"]==1
        assert summary["FT3"]["native_sameblock_floor_role_candidates"]==1
        assert summary["FT2"]["original_inplan_mark_word_candidates"]==8
        assert summary["FT3"]["original_inplan_mark_word_candidates"]==5
        assert summary["FT1"]["native_sameblock_floor_role_candidates"]==1
        assert summary["WT1"]["native_sameblock_floor_role_candidates"]==0
        assert not result["new_source_material_definitions"]
        assert not result["new_source_finish_occurrences"]
        assert not result["new_floor_finish_area_m2"]
        assert not result["new_customer_quantities"]
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def test_original_ft2_schedule_manufacturer_subtype_size_same_native_block():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as doc:
        res=_source(doc[10])
        row=next(r for r in res["original_source_schedule_row_candidates"]
                 if r["original_material_code_literal_untrusted"]=="FT2")
        assert row["source_native_same_block_floor_role_candidate"]
        assert row["original_manufacturer_line_untrusted"]==[
            "AMBER","TILES","LIVERPOOL"
        ]
        assert row["original_description_line_untrusted"][:3]==[
            "FLOOR","TILE","–"
        ]
        assert any("STOCKTON" in x for x in row["original_description_line_untrusted"])
        assert [x["original_pdf_text_literal_untrusted"]
                for x in row["original_source_dimension_word_candidates"]]==["800x400"]
        assert not row["source_schedule_definition_authentication_granted"]


def test_original_ft3_schedule_separate_dura_grey_600_square_from_ft2():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as doc:
        res=_source(doc[10])
        row=next(r for r in res["original_source_schedule_row_candidates"]
                 if r["original_material_code_literal_untrusted"]=="FT3")
        assert row["source_native_same_block_floor_role_candidate"]
        assert "“DURA" in row["original_description_line_untrusted"]
        assert "GREY”" in row["original_description_line_untrusted"]
        assert [x["original_pdf_text_literal_untrusted"]
                for x in row["original_source_dimension_word_candidates"]]==["600x600"]
        assert not row["source_original_text_trust_granted"]


def test_wall_tile_wt1_original_printed_800x400_not_a_floor_material():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as doc:
        res=_source(doc[10])
        row=next(r for r in res["original_source_schedule_row_candidates"]
                 if r["original_material_code_literal_untrusted"]=="WT1")
        assert row["source_native_wall_finish_row_not_floor"]
        assert not row["source_native_same_block_floor_role_candidate"]
        assert [w["original_pdf_text_literal_untrusted"]
                for w in row["original_source_dimension_word_candidates"]]==["800x400"]


def test_candidate_room_label_or_schedule_number_cannot_grant_area():
    doc=fitz.open()
    page=doc.new_page(width=400,height=300)
    page.insert_text((20,80),"FT2 OFFICE 800x400")
    page.insert_text((230,180),"FT2 AMBER TILES LIVERPOOL FLOOR TILE 800x400")
    result=audit(page,original_code_literals=("FT2",),
                 original_plan_candidate_bbox=(0,0,160,250),
                 original_schedule_candidate_bbox=(180,0,400,250))
    assert result["all_original_source_finish_code_summaries"]["FT2"]["native_sameblock_floor_role_candidates"]==0
    assert not result["original_source_physical_floor_correspondence"]
    assert result["new_floor_finish_area_m2"]==0
    doc.close()


def test_overlapping_scopes_malformed_codes_and_nonunique_lists_fail_closed():
    doc=fitz.open()
    page=doc.new_page()
    with pytest.raises(ValueError,match="overlapping"):
        audit(page,original_code_literals=("FT2",),
              original_plan_candidate_bbox=(0,0,100,100),
              original_schedule_candidate_bbox=(50,50,200,200))
    with pytest.raises(ValueError,match="distinct_native"):
        audit(page,original_code_literals=("FT2","FT2"),
              original_plan_candidate_bbox=(0,0,100,100),
              original_schedule_candidate_bbox=(150,0,250,100))
    with pytest.raises(ValueError,match="distinct_native"):
        audit(page,original_code_literals=("FT2 ","FT3"),
              original_plan_candidate_bbox=(0,0,100,100),
              original_schedule_candidate_bbox=(150,0,250,100))
    doc.close()
