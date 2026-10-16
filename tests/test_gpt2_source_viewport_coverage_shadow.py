"""Source-coverage shadow is not viewport, room, or material authority."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_source_viewport_coverage_shadow import (
    audit_candidate_viewport_source_coverage as audit,
    _position,
    _crossed_boundaries,
)

PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_outside_crossing_touch_and_sloped_lookalikes():
    box = (0., 10., 100., 100.)
    assert _position(box, (3,2,5,4)) == "outside_supplied_viewport"
    assert _position(box, (3,9,5,11)) == "straddles_supplied_viewport"
    assert _position(box, (3,11,5,12)) == "fully_within_supplied_viewport"
    assert _crossed_boundaries((30,0,30,20),box) == ["native_ymin"]
    assert _crossed_boundaries((30,10,30,20),box) == []
    assert _crossed_boundaries((30,0,31,20),box) == []
    assert _crossed_boundaries((101,0,101,20),box) == []


def test_synthetic_source_is_readonly_and_no_viewport_election():
    doc = fitz.open()
    page = doc.new_page(width=300,height=300)
    page.insert_text((20,30),"GRID",fontsize=12)
    page.draw_line((100,1),(100,210))
    first = audit(page,viewport_bbox=(0,150,300,300),raw_mark_tokens=("GRID",))
    assert len(first["raw_word_candidates"]) == 1
    assert first["raw_words_outside_count"] == 1
    assert first["source_crossing_primitive_candidates"][0]["candidate_crossed_bounds"] == ["native_ymin"]
    assert not first["view_authority_granted"] and not first["quantity_authority_granted"]
    assert first == audit(page,viewport_bbox=(0,150,300,300),raw_mark_tokens=("GRID",))
    with pytest.raises(ValueError):
        audit(page,viewport_bbox=(0,0,0,10))
    with pytest.raises(ValueError):
        audit(page,viewport_bbox=(0,0,300,300),raw_mark_tokens=["GRID"])
    doc.close()


def test_source_id_reversal_and_split_do_not_mint_single_view():
    class Page:
        def get_text(self, mode):
            return []
        def get_drawings(self):
            return [
                {"items":[("l",fitz.Point(20,30),fitz.Point(20,0))],"color":(0,0,0),"width":0.48},
                {"items":[("l",fitz.Point(20,0),fitz.Point(20,15)),
                          ("l",fitz.Point(20,15),fitz.Point(20,30))],"color":(0,0,0),"width":0.48},
            ]
    result = audit(Page(),viewport_bbox=(0,10,100,100),raw_mark_tokens=("GRID",))
    assert {x["original_source_primitive_id"] for x in result["source_crossing_primitive_candidates"]} == {"d0i0","d1i0"}
    assert all(not x["proof_of_single_view_continuity"] for x in result["source_crossing_primitive_candidates"])


def test_scope_cap_never_returns_partial_crossings_as_complete():
    class Page:
        def get_text(self, mode):
            return []
        def get_drawings(self):
            return [
                {"items":[("l",fitz.Point(i,0),fitz.Point(i,30)) for i in range(3)],
                 "color":(0,0,0)}
            ]
    result = audit(Page(),viewport_bbox=(0,10,100,100),max_native_segments=2)
    assert result["status"] == "original_vector_scope_exceeds_shadow_cap"
    assert result["source_crossing_primitive_candidates"] == []
    assert not result["source_crossing_universe_complete"]
    assert not result["view_authority_granted"]


def test_original_maryborough_p9_preserves_missing_sales_grid_and_rivals():
    source = PDF.read_bytes()
    assert hashlib.sha256(source).hexdigest() == SHA
    with fitz.open(stream=source,filetype="pdf") as doc:
        page = doc[8]
        result = audit(
            page,viewport_bbox=(0,1379.6826171875,1684,2384),
            raw_mark_tokens=("GRID","IPF1","CLD3","FPB","WFPB","IP")
        )
        assert page.rotation == 90
        assert result["status"] == "read_only_candidate_coverage_complete"
        assert len(result["raw_word_candidates"]) == 37
        assert result["raw_words_outside_count"] == 18
        assert len(result["source_crossing_primitive_candidates"]) == 73
        by_address = {tuple(r["original_source_word_address"]):r for r in result["raw_word_candidates"]}
        assert by_address[(114,1,0)]["candidate_location"] == "outside_supplied_viewport"
        assert by_address[(10,1,0)]["candidate_location"] == "fully_within_supplied_viewport"
        assert any(r["original_source_primitive_id"] == "d9755i0"
                   for r in result["source_crossing_primitive_candidates"])
        assert all(not r["original_ink_role_authenticated"]
                   for r in result["source_crossing_primitive_candidates"])
        assert not result["view_authority_granted"]
        assert not result["material_occurrence_authority_granted"]
        assert not result["quantity_authority_granted"]
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == SHA
