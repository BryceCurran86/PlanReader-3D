"""Window elevation titles are group views, not one window per printed code."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_original_window_elevation_title_lineage_shadow import (
    audit_original_window_elevation_title_memberships as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
CODES=tuple(f"W{i:02d}" for i in range(1,7))


def test_original_p7_to_a601_p29_six_codes_four_true_elevation_titles():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        result=audit(doc[6],doc[28],expected_source_codes=CODES)
        title_groups=result["all_original_elevation_title_groups"]
        assert len(title_groups)==4
        assert [g["original_window_codes_in_same_title_block"]
                for g in title_groups]==[
                    ["W01"],["W02"],["W03","W04","W05"],["W06"]
                ]
        assert all(g["source_title_group_represents_one_elevation_view"]
                   and not g["source_named_view_or_physical_window_authenticated"]
                   for g in title_groups)
        names=result["source_plan_to_elevation_named_code_candidates"]
        assert len(names)==6
        assert all(n["one_source_plan_label_and_one_elevation_group_candidate_only"]
                   for n in names)
        assert all(len(n["original_plan_tag_word_candidates"])==1
                   and len(n["original_elevation_title_group_candidates"])==1
                   for n in names)
        assert all(not n["physical_opening_identity_authenticated"]
                   and not n["source_window_m2_granted"]
                   and n["default_one_window_count_forbidden"]
                   for n in names)
        assert not result["new_window_areas_m2"]
        assert not result["new_eligible_window_counts"]
        assert result["original_elevation_numeric_words_not_dimensions"]
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def test_original_three_codes_one_group_does_not_imply_three_frame_widths():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as doc:
        r=audit(doc[6],doc[28],expected_source_codes=CODES)
        g=next(x for x in r["all_original_elevation_title_groups"]
               if x["original_window_codes_in_same_title_block"]==[
                   "W03","W04","W05"
               ])
        assert len(g["original_source_title_word_ids"])>=4
        for code in ("W03","W04","W05"):
            row=next(x for x in r["source_plan_to_elevation_named_code_candidates"]
                     if x["original_window_code_literal_untrusted"]==code)
            assert row["original_elevation_title_group_candidates"][0][
                "original_source_title_block_id"
            ]==g["original_source_title_block_id"]
            assert not row["figured_elevation_width_and_height_authenticated"]


def test_synthetic_missing_plan_tag_and_multiple_caption_groups_abstain():
    d=fitz.open()
    d.new_page(width=350,height=300)
    p=d[0]
    p.insert_text((40,70),"W01")
    d.new_page(width=350,height=300)
    q=d[1]
    q.insert_text((50,100),"W01 ELEVATION")
    q.insert_text((50,140),"W01 ELEVATION")
    r=audit(d[0],q,expected_source_codes=("W01","W02"))
    rows={x["original_window_code_literal_untrusted"]:x
          for x in r["source_plan_to_elevation_named_code_candidates"]}
    assert not rows["W01"]["one_source_plan_label_and_one_elevation_group_candidate_only"]
    assert not rows["W02"]["one_source_plan_label_and_one_elevation_group_candidate_only"]
    assert not rows["W01"]["physical_opening_identity_authenticated"]
    d.close()


def test_synthetic_code_word_without_elevation_heading_is_not_source_title():
    d=fitz.open()
    d.new_page(width=350,height=300)
    d[0].insert_text((50,90),"W01")
    d.new_page(width=350,height=300)
    d[1].insert_text((50,90),"W01 MECHANICAL DETAIL")
    r=audit(d[0],d[1],expected_source_codes=("W01",))
    assert not r["all_original_elevation_title_groups"]
    assert not r["source_plan_to_elevation_named_code_candidates"][0][
        "one_source_plan_label_and_one_elevation_group_candidate_only"]
    d.close()


def test_duplicate_and_malformed_source_codes_fail_closed():
    d=fitz.open()
    d.new_page()
    for codes in ((),("W01","W01"),("W1",),("W01 ","W02"),["W01"]):
        with pytest.raises(ValueError,match="source_window_code_universe"):
            audit(d[0],d[0],expected_source_codes=codes)
    d.close()
