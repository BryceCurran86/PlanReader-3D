"""A120 dark PDF wall bars: original painted long edges only, no extensions."""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from planreader_next.engine import NativePage, NativeRectangle, load_native_page, SourceConflict
from planreader_next.rcp_dark_bar_source_faces import (
    dark_filled_wall_bar_face_candidates,
    rcp_mask_source_dark_wall_edge_correspondence,
)


def _fixture() -> NativePage:
    dark=(0.195,0.195,0.195)
    return NativePage(
        "a"*64,8,(),(
            NativeRectangle("white-big-mask",(0,0,400,300),True,stroke_present=False,
                            fill_color=(1,1,1)),
            NativeRectangle("horizontal-real-dark-strip",(10,20,150,25),True,
                            stroke_present=False,fill_color=dark),
            NativeRectangle("vertical-real-dark-strip",(150,25,156,170),True,
                            stroke_present=False,fill_color=dark),
            NativeRectangle("short-black-decoration",(300,25,310,29),True,
                            stroke_present=False,fill_color=dark),
            NativeRectangle("wide-black-area",(300,100,350,170),True,
                            stroke_present=False,fill_color=dark),
            NativeRectangle("unknown-colour",(200,180,300,186),True,
                            stroke_present=None),
        ),(),
    )


def test_source_dark_fill_bars_get_exact_original_long_edges_not_mask_extents():
    page=_fixture()
    got=dark_filled_wall_bar_face_candidates(page)
    assert got["dark_painted_bar_count"]==2
    assert got["long_face_candidate_count"]==4
    by_ref={}
    for face in got["dark_bar_long_face_candidates"]:
        by_ref.setdefault(face["source_rectangle_ref"],[]).append(face)
        assert face["source_face_candidate_id"].startswith(face["source_rectangle_ref"]+"|")
        assert face["finished_wall_face_authenticated"] is False
        assert face["wall_height_mm"] is None
        assert face["commercial_publishable"] is False
        assert face["no_extension_beyond_original_source_bar"] is True
    assert sorted(item["source_long_edge_pdf_pts"] for item in by_ref[
        "horizontal-real-dark-strip"
    ])==[[10.0,20.0,150.0,20.0],[10.0,25.0,150.0,25.0]]
    assert sorted(item["source_long_edge_pdf_pts"] for item in by_ref[
        "vertical-real-dark-strip"
    ])==[[150.0,25.0,150.0,170.0],[156.0,25.0,156.0,170.0]]
    assert "white-big-mask" not in by_ref
    assert "short-black-decoration" not in by_ref
    assert "wide-black-area" not in by_ref
    assert "unknown-colour" not in by_ref
    assert got["official_score"] is None


def test_dark_filled_plus_stroked_bar_still_keeps_its_original_ink_edges():
    base=_fixture()
    source=NativeRectangle(
        "dark-stroked-source",(16,200,160,205),True,
        stroke_present=True,stroke_color=(0.1,0.1,0.1),
        stroke_width=0.4,fill_color=(0.195,0.195,0.195),
    )
    page=NativePage(base.source_sha256,base.page_index,base.words,
                    base.rectangles+(source,),base.segments)
    out=dark_filled_wall_bar_face_candidates(page)
    assert out["dark_painted_bar_count"]==3
    stroked=[x for x in out["dark_bar_long_face_candidates"]
             if x["source_rectangle_ref"]=="dark-stroked-source"]
    assert len(stroked)==2
    assert all(x["stroke_present"] is True for x in stroked)
    assert all(x["commercial_publishable"] is False for x in stroked)


def test_duplicate_dark_source_rectangles_cannot_create_double_face_provenance():
    page=_fixture()
    rect=next(x for x in page.rectangles if x.ref=="horizontal-real-dark-strip")
    repeated=NativePage(
        page.source_sha256,page.page_index,page.words,
        page.rectangles+(rect,),page.segments,
    )
    with pytest.raises(SourceConflict,match="duplicate_dark_wall_source_rect_ref"):
        dark_filled_wall_bar_face_candidates(repeated)


def _original_page():
    name=os.environ.get("PLANREADER_MARYBOROUGH_ORIGINAL_PDF")
    if not name or not Path(name).is_file():
        pytest.skip("ORIGINAL_SOURCE_NOT_RUN")
    return load_native_page(Path(name),8)


def test_original_maryborough_a120_dark_bar_inventory_rejects_all_white_masks():
    page=_original_page()
    assert page.source_sha256=="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
    audit=dark_filled_wall_bar_face_candidates(page)
    assert audit["dark_painted_bar_count"]==45
    assert audit["long_face_candidate_count"]==90
    assert all(face["stroke_present"] is False for face in audit[
        "dark_bar_long_face_candidates"
    ])
    refs={x["source_rectangle_ref"] for x in audit["dark_painted_bar_candidates"]}
    assert {"rect:p56:i0","rect:p63:i0","rect:p73:i0"} <= refs
    assert "rect:p141:i0" not in refs
    assert "rect:p114:i0" not in refs
    assert all(not item["physical_wall_identity_authenticated"] for item in audit[
        "dark_painted_bar_candidates"
    ])


def test_original_sales_wall_bar_must_stop_and_never_continue_through_sales():
    page=_original_page()
    packet=rcp_mask_source_dark_wall_edge_correspondence(page)
    sales=next(x for x in packet["layout_mask_boundary_source_correspondence"]
               if x["source_rectangle_ref"]=="rect:p141:i0")
    south=next(x for x in sales["side_source_dark_wall_face_evidence"]
               if x["layout_mask_side"]=="y_max")
    assert south["unsupported_layout_intervals_pdf_pts"]==[[694.08,1217.04]]
    assert south["source_bar_support_fraction"]==0.442
    ink=[x for x in south["dark_bar_long_face_candidates"]
         if x["source_rectangle_ref"]=="rect:p56:i0"]
    assert len(ink)==2
    assert all(float(x["actual_original_dark_bar_long_edge_pdf_pts"][2]) < 695
               for x in ink)
    assert all(x["source_original_edge_not_prolonged"] for x in ink)
    assert not packet["commercial_publishable"]


def test_original_rectangle_3_false_overhang_kept_separate_from_actual_lower_wall():
    page=_original_page()
    packet=rcp_mask_source_dark_wall_edge_correspondence(page)
    zone=next(x for x in packet["layout_mask_boundary_source_correspondence"]
              if x["source_rectangle_ref"]=="rect:p116:i0")
    north=next(x for x in zone["side_source_dark_wall_face_evidence"]
               if x["layout_mask_side"]=="y_min")
    assert north["unsupported_layout_intervals_pdf_pts"]==[[571.2,702.48]]
    refs={x["source_rectangle_ref"] for x in north["dark_bar_long_face_candidates"]}
    assert "rect:p63:i0" in refs
    # The lower wall rect:p73 is 28.08pt away from the incorrectly drawn
    # top bbox edge: do not force a straight path to join it.
    assert "rect:p73:i0" not in refs
    bottom_wall=[
        x for x in packet["source_dark_bar_long_face_candidates"]
        if x["source_rectangle_ref"]=="rect:p73:i0"
    ]
    assert len(bottom_wall)==2
    assert all(x["source_long_edge_pdf_pts"][1]>1580 for x in bottom_wall)
    assert packet["ceiling_area_count"]==0
