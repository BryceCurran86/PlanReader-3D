"""Original source-native RCP words; no physical ceilings or square metres."""
import os
from hashlib import sha256
from pathlib import Path
import fitz
import pytest
from pb_gpt2_original_mary_rcp_native_word_scope_shadow import (
    inspect_original_mary_rcp_word_scope_shadow,
)


def _fixture():
    p=fitz.open();page=p.new_page(width=700,height=700)
    page.insert_text((180,180),'OFFICE',fontsize=10)
    page.insert_text((180,250),'2400',fontsize=10)
    page.insert_text((180,265),'GRID',fontsize=10)
    page.insert_text((180,350),'REVIEW IN OFFICE AREA',fontsize=10)
    page.insert_text((180,420),'GRID OFFICE',fontsize=10)
    b=p.tobytes();p.close();return b


def _go(b,address,bbox=(100,100,500,500),**kwargs):
    return inspect_original_mary_rcp_word_scope_shadow(
        b,expected_source_sha256=sha256(b).hexdigest(),page_number=1,
        native_word_address=address,candidate_plan_bbox_pdf_pt=bbox,**kwargs)


def test_standalone_room_word_is_not_material_ceiling():
    r=_go(_fixture(),(0,0,0))
    assert r.original_text=='OFFICE' and r.original_source_role=='SOURCE_NON_CEILING_CODE_WORD'
    assert not r.original_material_definition_authorized
    assert not r.firm_ceiling_quantity_authorized


def test_original_grid_pair_retains_2400_competitor_separate():
    b=_fixture();d=fitz.open(stream=b,filetype='pdf');words=d[0].get_text('words');d.close()
    grid=next(tuple(w[5:8]) for w in words if w[4]=='GRID')
    r=_go(b,grid)
    assert r.original_source_role=='SOURCE_CEILING_CODE_WORD_CANDIDATE'
    assert not r.metric_area_authorized


def test_real_short_note_inside_plan_does_not_win_room_or_ceiling():
    b=_fixture();d=fitz.open(stream=b,filetype='pdf');words=d[0].get_text('words');d.close()
    w=next(tuple(w[5:8]) for w in words if w[4]=='OFFICE' and w[5]!=0)
    r=_go(b,w)
    assert r.original_source_role=='SOURCE_GENERAL_NOTE_OR_MIXED_TEXT'
    assert r.original_block_words==('REVIEW','IN','OFFICE','AREA')
    assert not r.physical_ceiling_zone_authorized


def test_always_behind_source_identity_even_if_inside_caller_plan():
    r=_go(_fixture(),(0,0,0))
    assert not r.original_plan_viewport_authorized
    assert not r.w4_wall_face_authorized
    assert not r.commercial_projection_allowed


def test_forged_sha_missing_word_and_invalid_viewport_fail_closed():
    b=_fixture()
    with pytest.raises(ValueError,match='SHA'):
        inspect_original_mary_rcp_word_scope_shadow(b,expected_source_sha256='0'*64,
            page_number=1,native_word_address=(0,0,0),
            candidate_plan_bbox_pdf_pt=(100,100,500,500))
    with pytest.raises(ValueError,match='word'):_go(b,(0,99,0))
    with pytest.raises(ValueError,match='BBOX'):_go(b,(0,0,0),bbox=(100,100,99,500))


def test_original_source_candidate_rect_has_no_material_grant():
    r=_go(_fixture(),(0,0,0),bbox=(0,0,1,1))
    assert r.original_source_role=='SOURCE_OUTSIDE_PROPOSED_PLAN_VIEWPORT'
    assert not r.original_plan_viewport_authorized


def test_real_original_page9_native_source_rivals_if_available():
    path=os.getenv('PLANREADER_MARYBOROUGH_ORIGINAL_PDF')
    if not path:pytest.skip('private owner original not present on runner')
    b=Path(path).read_bytes()
    hash_expected=os.environ['PLANREADER_MARYBOROUGH_SOURCE_SHA256']
    def orig(addr):return inspect_original_mary_rcp_word_scope_shadow(
        b,expected_source_sha256=hash_expected,page_number=9,
        native_word_address=addr,candidate_plan_bbox_pdf_pt=(100,100,1100,1700))
    assert orig((9,0,0)).original_source_role=='SOURCE_NON_CEILING_CODE_WORD'
    grid=orig((10,1,0))
    assert grid.original_text=='GRID'
    # PyMuPDF native block grouping differs across pinned/source builds.
    # A GRID glyph with any unlisted sibling is a mixed source note,
    # not an independent ceiling-code lexical candidate.
    codes={'IPF1','GRID','WFPB','FPB','IP'}
    allowed=codes | {'CLG','CEILING','/'}
    siblings=tuple(t.upper() for t in grid.original_block_words)
    isolated=(len(siblings)<=4 and
              [t for t in siblings if t in codes]==['GRID'] and
              all(t in allowed or t.isdigit() for t in siblings))
    assert grid.original_source_role==(
        'SOURCE_CEILING_CODE_WORD_CANDIDATE' if isolated
        else 'SOURCE_GENERAL_NOTE_OR_MIXED_TEXT')
    assert not grid.original_material_definition_authorized
    assert not grid.physical_ceiling_zone_authorized
    assert orig((10,0,0)).original_source_role=='SOURCE_NUMERIC_CALLOUT_WORD'
    assert orig((212,0,2)).original_source_role=='SOURCE_GENERAL_NOTE_OR_MIXED_TEXT'
    assert orig((5,4,0)).original_source_role=='SOURCE_OUTSIDE_PROPOSED_PLAN_VIEWPORT'
    assert orig((85,5,0)).original_source_role=='SOURCE_GENERAL_NOTE_OR_MIXED_TEXT'
    assert orig((87,0,0)).original_source_role=='SOURCE_CEILING_CODE_WORD_CANDIDATE'
    assert all(not orig(addr).firm_ceiling_quantity_authorized for addr in
               [(9,0,0),(10,1,0),(212,0,2),(87,0,0)])


def test_two_word_mixed_native_grid_office_block_is_not_ceiling_mark():
    b=_fixture()
    with fitz.open(stream=b,filetype='pdf') as doc:
        words=doc[0].get_text('words')
    target=max((tuple(w[5:8]) for w in words if w[4]=='GRID'),key=lambda a:a[0])
    role=_go(b,target)
    assert role.original_block_words==('GRID','OFFICE')
    assert role.original_source_role=='SOURCE_GENERAL_NOTE_OR_MIXED_TEXT'
    assert not role.original_material_definition_authorized
    assert not role.physical_ceiling_zone_authorized
    assert not role.firm_ceiling_quantity_authorized
    assert not role.commercial_projection_allowed


@pytest.mark.parametrize("native_code_line", [
    "GRID IPF1",
    "IPF1 GRID",
    "GRID GRID",
    "IPF1 IPF1",
])
def test_competing_or_repeated_material_codes_in_same_source_block_abstain(native_code_line):
    doc=fitz.open()
    page=doc.new_page(width=700,height=700)
    page.insert_text((180,250),native_code_line,fontsize=10)
    raw=doc.tobytes()
    doc.close()
    with fitz.open(stream=raw,filetype="pdf") as document:
        original_words=document[0].get_text("words")
    addresses=[tuple(w[5:8]) for w in original_words if w[4] in ("GRID","IPF1")]
    assert len(addresses)==2
    for addr in addresses:
        result=_go(raw,addr)
        assert result.original_source_role=="SOURCE_GENERAL_NOTE_OR_MIXED_TEXT"
        assert not result.original_material_definition_authorized
        assert not result.physical_ceiling_zone_authorized
        assert not result.firm_ceiling_quantity_authorized


def test_one_source_code_with_one_height_word_remains_lexical_only():
    doc=fitz.open()
    page=doc.new_page(width=700,height=700)
    page.insert_text((180,250),"GRID 2400",fontsize=10)
    raw=doc.tobytes()
    doc.close()
    with fitz.open(stream=raw,filetype="pdf") as document:
        original_words=document[0].get_text("words")
    grid=next(tuple(w[5:8]) for w in original_words if w[4]=="GRID")
    result=_go(raw,grid)
    assert result.original_source_role=="SOURCE_CEILING_CODE_WORD_CANDIDATE"
    assert not result.metric_area_authorized
    assert not result.firm_ceiling_quantity_authorized
