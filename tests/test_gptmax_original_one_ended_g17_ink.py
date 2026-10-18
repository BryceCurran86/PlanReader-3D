"""Actual one-ended original ink cannot require an invented outer end."""
import cv2
import numpy as np
import pytest

from pb_raster_unchanged_band_segments import (
    detect_original_one_ended_ink_band_segments,
    detect_unchanged_terminal_band_segments,
    ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION,
)
from pb_raster_visible_segment_detector import _MIN_LINE_LENGTH_PT


def png(a):
    ok, content=cv2.imencode(".png",a)
    assert ok
    return content.tobytes()


def draw(cells,*,axis="horizontal",overpaint=None):
    a=np.full((64,96,3),255,dtype=np.uint8)
    x,y=24,26
    if axis=="horizontal":
        a[y:y+10,x:x+cells]=0
        box=(x*72/300,y*72/300,(x+cells-1)*72/300,(y+9)*72/300)
    else:
        a[y:y+cells,x:x+10]=0
        box=(x*72/300,y*72/300,(x+9)*72/300,(y+cells-1)*72/300)
    b=a.copy()
    if overpaint=="centre":
        if axis=="horizontal":b[y+5,x+cells//2]=(255,0,0)
        else:b[y+cells//2,x+5]=(255,0,0)
    elif overpaint=="outer_edge":
        b[y,x]=255
    return png(a),png(b),(axis,box)


def source(cells,*,axis="horizontal",overpaint=None):
    a,b,box=draw(cells,axis=axis,overpaint=overpaint)
    return detect_original_one_ended_ink_band_segments(
        a,b,dpi=300,source_closed_flank_boxes=(box,))


def test_seventeen_original_cells_retain_their_full_408pt_ink_extent():
    rows=source(17)
    assert len(rows)==1
    assert _MIN_LINE_LENGTH_PT==4.0
    assert rows[0].pixel_support_bounds[2]-rows[0].pixel_support_bounds[0]==16
    assert 17*72/300>=_MIN_LINE_LENGTH_PT
    assert (17-1)*72/300<_MIN_LINE_LENGTH_PT
    assert rows[0].geometry_pt[2]-rows[0].geometry_pt[0]==pytest.approx(4.08)
    assert rows[0].pixel_geometry[0]==23.5
    assert rows[0].pixel_geometry[2]==40.5
    assert ORIGINAL_G17_ONE_END_SOURCE_IDENTITY_VERSION.startswith("original_g17_one_end")


@pytest.mark.parametrize("axis",["horizontal","vertical"])
def test_old_long_source_line_endpoints_are_unchanged(axis):
    rows=source(21,axis=axis)
    assert len(rows)==1
    line=rows[0].pixel_geometry
    along=(line[0],line[2]) if axis=="horizontal" else (line[1],line[3])
    assert along[1]-along[0]==pytest.approx(20.0)


def test_repaired_four_point_span_is_not_an_invented_outer_jamb():
    r=source(17)[0]
    # Only the actual source-painted pixel cells are expanded. The physical
    # wall-role and the downstream W4/host source end still need proof.
    x0,y0,x1,y1=r.pixel_support_bounds
    assert r.pixel_geometry[0]==x0-0.5
    assert r.pixel_geometry[2]==x1+0.5
    assert r.geometry_pt[2]-r.geometry_pt[0]<_MIN_LINE_LENGTH_PT+0.2


@pytest.mark.parametrize("cells",[0,9,16])
def test_shorter_or_incomplete_source_pixels_are_not_published(cells):
    assert not source(cells)


@pytest.mark.parametrize("axis",["horizontal","vertical"])
def test_original_both_orientations_support_unchanged_flank(axis):
    assert len(source(21,axis=axis))==1


def test_source_rgb_change_in_core_rejects():
    assert source(17,overpaint="centre")==()


def test_unrelated_native_paint_at_outer_border_is_not_bridge_authority():
    assert len(source(17,overpaint="outer_edge"))==1


@pytest.mark.parametrize("value",[None,-1,"300",300.0,0,True])
def test_invalid_original_dpi_rejected(value):
    a,b,box=draw(17)
    with pytest.raises(ValueError):
        detect_original_one_ended_ink_band_segments(a,b,dpi=value,
                                                   source_closed_flank_boxes=(box,))


def test_exact_original_source_box_must_match_render_lattice():
    a,b,box=draw(17)
    axis,bounds=box
    moved=tuple(v+0.1 if i==0 else v for i,v in enumerate(bounds))
    with pytest.raises(ValueError,match="lattice"):
        detect_original_one_ended_ink_band_segments(
            a,b,dpi=300,source_closed_flank_boxes=((axis,moved),))


def test_conflicting_duplicate_source_boxes_are_never_two_walls():
    a,b,box=draw(17)
    with pytest.raises(ValueError,match="duplicate"):
        detect_original_one_ended_ink_band_segments(
            a,b,dpi=300,source_closed_flank_boxes=(box,box))


def test_one_end_source_is_deterministic_under_inventory_permutation():
    a=np.full((64,96,3),255,dtype=np.uint8)
    a[26:36,24:41]=0
    a[26:36,65:82]=0
    p=png(a)
    boxes=(("horizontal",(24*72/300,26*72/300,40*72/300,35*72/300)),
           ("horizontal",(65*72/300,26*72/300,81*72/300,35*72/300)))
    assert detect_original_one_ended_ink_band_segments(p,p,dpi=300,source_closed_flank_boxes=boxes)==detect_original_one_ended_ink_band_segments(p,p,dpi=300,source_closed_flank_boxes=boxes[::-1])
