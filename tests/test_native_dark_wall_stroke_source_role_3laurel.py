"""3Laurel native dark 0.71-pt wall stroke recognition, not generic ink.

The original 3Laurel p3 PDF uses source-named wall faces as single
0.71pt strokes as well as dark filled rectangles. Floor-finish/annotation
lines are thinner; source role is mandatory for the lower width class.
All receipts remain topology-only and noncommercial.
"""
import fitz

from pb_next_wall_ring_preview import _collect_source_heavy_stroke_strips


def _stroke(width=.71, layer="Enclosure_WallExternal", color=(0.,0.,0.),
            start=(100., 50.), end=(200., 50.), fill=None,
            opacity=1.):
    return {
        "layer": layer,
        "color": color,
        "fill": fill,
        "width": width,
        "stroke_opacity": opacity,
        "rect": fitz.Rect(min(start[0],end[0]),min(start[1],end[1]),
                          max(start[0],end[0]),max(start[1],end[1])),
        "items": [("l",fitz.Point(*start),fitz.Point(*end))],
    }


def test_source_named_dark_wall_071pt_stroke_produces_topology_candidate():
    for layer in ("Enclosure_WallExternal","Enclosure_WallInternal"):
        rows=_collect_source_heavy_stroke_strips((_stroke(layer=layer),))
        assert len(rows)==1
        assert rows[0].path_index==0
        assert rows[0].x0==100.
        assert rows[0].x1==200.
        assert round(rows[0].y1-rows[0].y0,3)==.71
        assert rows[0].native_path_indices()==(0,)


def test_native_stroke_071_requires_original_wall_layer_not_floor_annotation():
    for layer in ("Annotation_FloorPlan","Annotation_General",
                  "Finish_Floor","Interior_Joinery","Enclosure_Roof",""):
        rows=_collect_source_heavy_stroke_strips((_stroke(layer=layer,width=.71),))
        assert rows==[]


def test_existing_untyped_192pt_wall_stroke_lane_is_retained():
    rows=_collect_source_heavy_stroke_strips((_stroke(width=1.92,layer=""),))
    assert len(rows)==1
    assert rows[0].native_path_indices()==(0,)


def test_below_wall_width_or_wrong_color_or_opaque_gate_still_rejects():
    assert _collect_source_heavy_stroke_strips((_stroke(width=.43),))==[]
    assert _collect_source_heavy_stroke_strips((_stroke(width=.37,layer="Enclosure_WallInternal"),))==[]
    assert _collect_source_heavy_stroke_strips((_stroke(color=(.8,.8,.8)),))==[]
    assert _collect_source_heavy_stroke_strips((_stroke(opacity=.2),))==[]
    assert _collect_source_heavy_stroke_strips((_stroke(fill=(0.,0.,0.)),))==[]


def test_wall_stroke_must_be_long_and_axis_aligned_not_diagonal_hatch():
    assert _collect_source_heavy_stroke_strips((_stroke(end=(110.,50.)),))==[]
    assert _collect_source_heavy_stroke_strips((_stroke(end=(180.,110.)),))==[]


def test_multiple_source_wall_strokes_keep_unique_native_path_owners():
    rows=_collect_source_heavy_stroke_strips((
        _stroke(start=(100.,50.),end=(200.,50.)),
        _stroke(start=(100.,52.5),end=(200.,52.5)),
        _stroke(layer="Finish_Floor",width=.43,start=(100.,48.),end=(200.,48.)),
    ))
    assert len(rows)==2
    assert {row.path_index for row in rows}=={0,1}
    assert all(row.native_path_indices() for row in rows)
