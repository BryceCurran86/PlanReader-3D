"""A source grid is not a schedule merely because fixture centres repeat."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import fitz
import pytest
import pb_viewport_segmentation as v

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
A120_FALSE_TABLE = (279.8399963378906,471.2000732421875,1217.0399169921875,1376.719970703125)


def _make_source_rectangles(*, gap=0, rows=3, columns=3):
    doc = fitz.open()
    page = doc.new_page(width=300,height=300)
    for row in range(rows):
        for col in range(columns):
            x=40+col*(20+gap)
            y=50+row*(15+gap)
            page.draw_rect(fitz.Rect(x,y,x+20,y+15),color=(0,0,0),width=.48)
    return doc,page


def test_native_connected_cells_positive_and_false_periodic_fixture_negative():
    table,t = _make_source_rectangles(gap=0)
    assert v._source_connected_native_cell_family_shadow((0,0,300,300),t)
    table.close()
    lights,p = _make_source_rectangles(gap=13)
    assert not v._source_connected_native_cell_family_shadow((0,0,300,300),p)
    lights.close()


def test_optin_is_an_explicit_bool_without_changing_existing_callers(monkeypatch):
    FRAME=(10.,10.,200.,200.)
    ANCHOR=v._TitleAnchor(
        "CEILING FINISHES SCHEDULE",(220.,60.,270.,100.),
        v.DrawingViewType.SCHEDULE.value,
    )
    calibration=v.ViewportLayoutCalibration(
        median_word_height_pt=8.,title_frame_gap_pt=20.,
        minimum_frame_span_pt=25.,title_separation_pt=25.,
        page_width_pt=300.,page_height_pt=300.,
    )
    monkeypatch.setattr(v,"_text_fragments",lambda _page:[])
    monkeypatch.setattr(v,"_frame_candidates_for_title",lambda *a,**kw:[FRAME])
    monkeypatch.setattr(v,"_rejected_ownership_frame",lambda *a,**kw:False)
    monkeypatch.setattr(v,"_frame_looks_like_table",lambda *a,**kw:True)
    monkeypatch.setattr(v,"_frame_looks_like_line_grid_table",lambda *a,**kw:False)
    monkeypatch.setattr(v,"_extract_scales_for_bbox",lambda *a,**kw:(None,None,False,[]))
    # Default remains the exact legacy F.07 acceptance path.
    existing,consumed=v._frame_resolved_viewports(
        SimpleNamespace(),(ANCHOR,),(FRAME,),calibration,page_number=9,
    )
    assert consumed=={0} and len(existing)==1
    assert existing[0].status==v.ViewportSegmentationStatus.RESOLVED.value

    monkeypatch.setattr(v,"_source_connected_native_cell_family_shadow",
                        lambda frame,page:False)
    shadow,consumed=v._frame_resolved_viewports(
        SimpleNamespace(),(ANCHOR,),(FRAME,),calibration,page_number=9,
        source_connected_table_cell_shadow=True,
    )
    assert shadow==[] and consumed==set()
    monkeypatch.setattr(v,"_source_connected_native_cell_family_shadow",
                        lambda frame,page:True)
    positive,consumed=v._frame_resolved_viewports(
        SimpleNamespace(),(ANCHOR,),(FRAME,),calibration,page_number=9,
        source_connected_table_cell_shadow=True,
    )
    assert len(positive)==1 and consumed=={0}
    with pytest.raises(ValueError,match="explicit_bool"):
        v._frame_resolved_viewports(
            SimpleNamespace(),(ANCHOR,),(FRAME,),calibration,page_number=9,
            source_connected_table_cell_shadow=1,
        )


def test_original_sha_a120_false_schedule_frame_abstains_only_when_opted_in():
    data=ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest()==SHA
    with fitz.open(stream=data,filetype="pdf") as doc:
        page=doc[8]
        assert not v._source_connected_native_cell_family_shadow(
            A120_FALSE_TABLE,page
        )
        baseline=v.segment_page_viewports(page,page_number=9)
        default=v.segment_page_viewports(
            page,page_number=9,source_connected_table_cell_shadow=False
        )
        assert baseline==default
        alleged=[
            p for p in baseline if p.view_id=="view_p9_4"
        ]
        assert len(alleged)==1 and alleged[0].status=="resolved"
        shadow=v.segment_page_viewports(
            page,page_number=9,source_connected_table_cell_shadow=True
        )
        mistaken=[
            p for p in shadow if p.view_id=="view_p9_4"
            and p.status=="resolved"
            and p.bounding_box==A120_FALSE_TABLE
        ]
        assert not mistaken
        assert all(p.view_id!="view_p9_5" or (
            p.provenance.get("separator_view_id")!="view_p9_4"
        ) for p in shadow)
        # Removing a FALSE schedule separator does NOT prove the ceiling.
        assert not any(p.view_id=="view_p9_5" and p.status=="resolved" for p in shadow)
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA


def test_the_guard_does_not_select_from_border_only_or_first_closest_rectangle():
    doc,page = _make_source_rectangles(gap=0, rows=1, columns=10)
    assert not v._source_connected_native_cell_family_shadow(
        (0,0,300,300),page
    )
    doc.close()
