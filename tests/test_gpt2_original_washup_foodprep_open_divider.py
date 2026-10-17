"""Original FT3 WASH UP and FOOD PREP share a north-open partition."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_original_open_functional_divider_shadow import (
    audit_original_open_functional_divider as audit,
)
SOURCE=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


@pytest.mark.skipif(not SOURCE.is_file(),reason="private original PDF unavailable; SHA-gated source review required")
def test_original_washup_foodprep_unclosed_divider_has_two_ft3_mark_sources():
    raw=SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    result=audit(raw,expected_sha256=SHA,page_1_based=11,
                 shared_north_source_id="d3561i0",
                 two_competing_divider_face_ids=("d3883i0","d3881i0"),
                 left_mark_word_address=(113,2,0),
                 right_mark_word_address=(114,0,0),
                 expected_original_mark_literal="FT3")
    assert result["original_north_open_span_pdf_pts"]==107.28
    assert result["original_competing_divider_face_separation_pdf_pts"]==6.24
    assert result["status"]=="original_partial_divider_has_open_north_connection"
    assert not result["source_floors_separated_or_room_split_proven"]
    assert not result["source_finish_zone_limits_issued"]
    assert result["new_firm_quantities"]==0
    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==SHA


def _synthetic(divider_start):
    doc=fitz.open();doc.new_page(width=300,height=240);p=doc[0]
    p.draw_line((10,30),(220,30),color=(0,0,0),width=.48)
    p.draw_line((95,divider_start),(95,180),color=(0,0,0),width=.48)
    p.draw_line((101,divider_start),(101,180),color=(0,0,0),width=.48)
    p.insert_text((40,115),"FT3",fontsize=11)
    p.insert_text((150,115),"FT3",fontsize=11)
    words=[w for w in p.get_text("words") if w[4]=="FT3"]
    assert len(words)==2
    words.sort(key=lambda x:x[0])
    raw=doc.tobytes()
    doc.close()
    return raw,tuple(tuple(int(v) for v in w[5:8]) for w in words)


@pytest.mark.parametrize("start,expected_gap",[(70.,40.),(30.,0.)])
def test_synthetic_true_source_divider_open_or_contacts_roof_never_room_claim(start,expected_gap):
    raw,addresses=_synthetic(start)
    result=audit(raw,expected_sha256=hashlib.sha256(raw).hexdigest(),page_1_based=1,
                 shared_north_source_id="d0i0",
                 two_competing_divider_face_ids=("d1i0","d2i0"),
                 left_mark_word_address=addresses[0],
                 right_mark_word_address=addresses[1],
                 expected_original_mark_literal="FT3")
    assert result["original_north_open_span_pdf_pts"]==expected_gap
    assert not result["source_wall_structural_role_issued"]
    assert not result["source_floors_separated_or_room_split_proven"]
    assert result["new_firm_quantities"]==0


def test_synthetic_swapped_original_marks_and_tampered_source_abstain():
    raw,ids=_synthetic(70.)
    options=dict(expected_sha256=hashlib.sha256(raw).hexdigest(),
                 page_1_based=1,shared_north_source_id="d0i0",
                 two_competing_divider_face_ids=("d1i0","d2i0"),
                 left_mark_word_address=ids[0],right_mark_word_address=ids[1],
                 expected_original_mark_literal="FT3")
    with pytest.raises(ValueError,match="original_mark_not_in_opposing"):
        audit(raw,**{**options,"left_mark_word_address":ids[1],
                     "right_mark_word_address":ids[0]})
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit(raw+b"tampered",**options)
    with pytest.raises(ValueError,match="original_source_stroke_missing"):
        audit(raw,**{**options,"shared_north_source_id":"d99999i0"})
