"""RCP OFFICE source wall/door gap diagnostics cannot publish square metres."""
from pathlib import Path
import hashlib

import fitz
import pytest

from tools.diag_gpt2_office_rcp_door_gap_shadow import (
    original_crosssheet_open_wall_ceiling_ink_shadow as audit,
)

PRIVATE = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _pages(*, shift=(85, 12), room_width=144., omit_floor_side=False,
           omit_rcp_top=False, extra_floor_gap=False, color=(0, 0, 0)):
    doc = fitz.open()
    floor = doc.new_page(width=1000, height=1000)
    rcp = doc.new_page(width=1000, height=1000)
    x0,y0,x1,y1 = (200.,300.,200.+room_width,500.)
    dx,dy=shift
    floor_box=(x0,y0,x1,y1)
    rcp_box=(x0+dx,y0+dy,x1+dx,y1+dy)
    for page,box,is_floor in ((floor,floor_box,True),(rcp,rcp_box,False)):
        ax,ay,bx,by=box
        page.draw_line((ax,ay),(ax,by),color=color,width=.48)
        if not (is_floor and omit_floor_side):
            page.draw_line((bx,ay),(bx,by),color=color,width=.48)
        page.draw_line((ax,by),(bx,by),color=color,width=.48)
        if is_floor:
            page.draw_line((ax,ay),(ax+28,ay),color=color,width=.48)
            if extra_floor_gap:
                page.draw_line((ax+68,ay),(ax+90,ay),color=color,width=.48)
                page.draw_line((ax+112,ay),(bx,ay),color=color,width=.48)
            else:
                page.draw_line((ax+68,ay),(bx,ay),color=color,width=.48)
        elif not omit_rcp_top:
            page.draw_line((ax,ay),(bx,ay),color=color,width=.48)
    return doc,floor_box,rcp_box


def test_open_doorway_is_not_a_missing_ceiling_wall_and_no_firm_is_issued():
    doc,f,c=_pages()
    try:
        a=audit(doc[0],doc[1],floor_face_bbox=f,rcp_face_bbox=c)
        assert a["status"]=="source_ink_candidate"
        assert a["floor_uncovered_stroke_intervals"]["top"] == ((228.,268.),)
        assert all(not holes for holes in a["rcp_uncovered_stroke_intervals"].values())
        assert a["source_frame_translation_pdf_pts"]==(85.,12.)
        assert a["firm_ceiling_area_m2"] is None
        assert a["original_door_identity_proven"] is False
        assert a["new_firm_quantities"]==0
    finally:
        doc.close()


@pytest.mark.parametrize("changes",[
    {"omit_floor_side":True},
    {"omit_rcp_top":True},
    {"extra_floor_gap":True},
    {"color":(0,0.5,0)},
])
def test_invalid_ink_or_incomplete_enclosing_wall_stays_abstained(changes):
    doc,f,c=_pages(**changes)
    try:
        assert audit(doc[0],doc[1],floor_face_bbox=f,
                     rcp_face_bbox=c)["status"] == "abstained"
    finally:
        doc.close()


@pytest.mark.parametrize("dx,dy",[(0,0),(106.32,0),(88.4,66.7)])
def test_translation_does_not_change_source_ownership_or_grant_quantity(dx,dy):
    doc,f,c=_pages(shift=(dx,dy))
    try:
        result=audit(doc[0],doc[1],floor_face_bbox=f,rcp_face_bbox=c)
        assert result["status"]=="source_ink_candidate"
        assert result["dimensions_equivalent"] is True
        assert result["source_metric_scale_proven"] is False
        assert result["firm_ceiling_area_m2"] is None
    finally:
        doc.close()


def test_mismatched_physical_extents_do_not_become_authoritative():
    doc,f,c=_pages()
    try:
        damaged=(c[0],c[1],c[2]+1,c[3])
        result=audit(doc[0],doc[1],floor_face_bbox=f,rcp_face_bbox=damaged)
        assert result["status"]=="abstained"
        assert result["dimensions_equivalent"] is False
    finally:
        doc.close()


def test_original_office_a110_d15_gap_and_a120_ceiling_wall_difference():
    if not PRIVATE.is_file():
        pytest.skip("PRIVATE Maryborough PDF missing: no source-positive approval")
    raw=PRIVATE.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        assert len(doc)==31
        assert doc[6].rotation==doc[8].rotation==90
        result=audit(
            doc[6],doc[8],
            floor_face_bbox=(173.52,1383.20,316.32,1584.56),
            rcp_face_bbox=(279.84,1383.20,422.64,1584.56),
        )
        assert result["status"]=="source_ink_candidate"
        assert result["source_frame_translation_pdf_pts"]==pytest.approx(
            (106.32,0),abs=.001)
        assert result["floor_uncovered_stroke_intervals"]["top"] == (
            (179.28,231.36),
        )
        assert all(not holes for holes in result["rcp_uncovered_stroke_intervals"].values())
        original_d15=[word for word in doc[6].get_text("words")
                      if word[4]=="D15" and 179.28 < (word[0]+word[2])/2 < 231.36]
        assert len(original_d15)==1
        assert tuple(original_d15[0][5:8]) == (183,0,0)
        assert any(row[2]==52239 for row in result["floor_boundary_source_paths"]["left"])
        assert any(row[2]==66216 for row in result["floor_boundary_source_paths"]["right"])
        assert any(row[2]==1112 for row in result["rcp_boundary_source_paths"]["left"])
        assert any(row[2]==2080 for row in result["rcp_boundary_source_paths"]["right"])
        assert result["firm_ceiling_area_m2"] is None
        assert result["new_firm_quantities"]==0
    assert hashlib.sha256(PRIVATE.read_bytes()).hexdigest()==SHA
