"""Original W03/W04/W05 grouped elevation must not create three sizes."""
from pathlib import Path
import hashlib
import fitz
import pytest
from tools.diag_original_a601_window_dimension_group_ownership_shadow import (
    audit_source_window_figure_competitors as audit,
)

SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
CODES=("W01","W02","W03","W04","W05","W06")
SCOPES={
    ("W01",):(90.,1750.,550.,2230.),
    ("W02",):(90.,1030.,550.,1600.),
    ("W03","W04","W05"):(560.,495.,1060.,2220.),
    ("W06",):(1250.,1030.,1540.,1820.),
}


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_original_six_codes_four_elevation_titles_and_all_rival_numbers():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        r=audit(doc[6],doc[28],original_window_codes=CODES,group_scopes=SCOPES)
        assert r["all_caption_groups_explicitly_scoped"]
        assert len(r["original_grouped_elevation_title_receipts"])==4
        nums=[x for x in r["numeric_original_source_candidates"]
              if x["possible_caption_groups"]==[["W03","W04","W05"]]]
        raw_nums={n["original_numeric_literal_untrusted"] for n in nums}
        assert {"585","2415","1240","2020","4500","7585"}.issubset(raw_nums)
        assert all(not n["frame_axis_or_unique_window_owner_proven"] for n in nums)
        assert r["new_window_counts"]==r["new_window_metric_areas"]==0
        assert not r["physical_window_frame_universe_complete"]
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_independent_original_w01_and_w02_number_candidates_are_not_shared():
    with fitz.open(stream=SOURCE.read_bytes(),filetype="pdf") as doc:
        r=audit(doc[6],doc[28],original_window_codes=CODES,group_scopes=SCOPES)
        one=[n for n in r["numeric_original_source_candidates"]
             if n["possible_caption_groups"]==[["W01"]]]
        two=[n for n in r["numeric_original_source_candidates"]
             if n["possible_caption_groups"]==[["W02"]]]
        assert "3000" in {r["original_numeric_literal_untrusted"] for r in one}
        assert "1900" in {r["original_numeric_literal_untrusted"] for r in two}
        assert not ({tuple(x["original_source_word_address"]) for x in one}
                    & {tuple(x["original_source_word_address"]) for x in two})


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_conflicting_original_group_scopes_do_not_auto_assign_dimension():
    with fitz.open(stream=SOURCE.read_bytes(),filetype="pdf") as doc:
        bad={**SCOPES,("W01",):(90.,1030.,550.,2230.)}
        with pytest.raises(ValueError,match="overlapping_independent_elevation"):
            audit(doc[6],doc[28],original_window_codes=CODES,group_scopes=bad)
        missing={k:v for k,v in SCOPES.items() if k!=("W06",)}
        with pytest.raises(ValueError,match="all_printed_original_title_groups"):
            audit(doc[6],doc[28],original_window_codes=CODES,group_scopes=missing)
        with pytest.raises(ValueError,match="original_independent_elevation"):
            audit(doc[6],doc[28],original_window_codes=CODES,
                  group_scopes={**SCOPES,("W01",):(0.,0.,0.,1.)})


@pytest.mark.skipif(not SOURCE.is_file(), reason="private original PDF unavailable in merge CI; separate SHA-pinned source acceptance required")
def test_numeric_scope_cap_abstains_without_firm_window_dimension():
    with fitz.open(stream=SOURCE.read_bytes(),filetype="pdf") as doc:
        r=audit(doc[6],doc[28],original_window_codes=CODES,
                group_scopes=SCOPES,max_numeric_tokens=1)
        assert r["status"]=="number_universe_cap_exceeded"
        assert not r["source_numeric_universe_complete"]
        assert r["new_firm_quantities"]==0
