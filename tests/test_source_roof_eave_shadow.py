from __future__ import annotations

from copy import deepcopy
from random import Random

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_roof_eave_shadow import (
    RoofPath,
    collect_gable_outer_roof_edge,
    collect_longitudinal_roof_edge,
    reconcile_roof_eave_geometry,
)


def _long_paths(dx: float = 0, dy: float = 0, scale: float = 1):
    def p(id, a, b, **kw):
        return RoofPath(id, tuple(scale*v+t for v,t in zip(a,(dx,dy))), tuple(scale*v+t for v,t in zip(b,(dx,dy))), **kw)
    return [
        p("roof-top",(20,20),(180,20)),
        p("roof-bottom",(20,30),(180,30)),
        p("roof-left",(20,20),(20,35)),
        p("roof-right",(180,20),(180,35)),
        p("dimension",(25,95),(175,95)),
        p("border-top",(1,1),(199,1),width_pt=0),
        p("border-bottom",(1,110),(199,110),width_pt=0),
        p("border-left",(1,1),(1,110),width_pt=0),
        p("border-right",(199,1),(199,110),width_pt=0),
    ]


def _long(paths=None, *, viewport="front", dy=0, scale=1, material=("corrugated roofing",)):
    if paths is None:
        paths=[RoofPath(f"{viewport}:{p.path_id}",p.start,p.end,p.stroke,p.width_pt,p.dashes)
               for p in _long_paths(dy=dy,scale=scale)]
    return collect_longitudinal_roof_edge(
        paths,
        source_page=1,viewport_id=viewport,
        viewport_bbox=(0,0+dy,200*scale,120*scale+dy),
        page_width_pt=200*scale,roof_material_annotations=material,
    )


def _gable(paths=None, *, dx=0, dy=0, scale=1, material=("sheet roofing",)):
    def pt(x,y):return (x*scale+dx,y*scale+dy)
    paths=paths if paths is not None else [
        RoofPath("left-outer",pt(15,65),pt(100,30)),
        RoofPath("right-outer",pt(100,30),pt(185,65)),
        RoofPath("left-inner",pt(40,55),pt(100,30)),
        RoofPath("right-inner",pt(100,30),pt(160,55)),
        RoofPath("frame",pt(1,110),pt(199,110),width_pt=0),
    ]
    # atan(35/85) is about 22.38 degrees; inner segments also share it.
    return collect_gable_outer_roof_edge(
        paths,source_page=1,viewport_id="gable",
        viewport_bbox=(dx,dy,200*scale+dx,120*scale+dy),
        apex_xy=pt(100,30),pitch_deg=22.38,
        structural_left_x=40*scale+dx,structural_right_x=160*scale+dx,
        roof_material_annotations=material,
    )


def test_two_owned_long_elevations_and_gable_keep_native_geometry_only():
    front=_long()
    rear=_long(viewport="rear",dy=150)
    gable=_gable()
    assert (front.status,rear.status,gable.status)==(Status.CANDIDATE,)*3
    assert front.span_pt==rear.span_pt==160
    assert gable.span_pt==170
    result=reconcile_roof_eave_geometry([front,rear],gable,pitch_deg=22.38)
    assert result.status is Status.CORROBORATED
    assert result.longitudinal_span_pt==160
    assert result.transverse_span_pt==170
    assert result.quantity_m2 is None
    assert len(result.path_ids)==10


def test_missing_material_border_dimension_and_dashes_do_not_mint_roof():
    assert _long(material=()).status is Status.ABSTAINED
    only_nonroof=[p for p in _long_paths() if p.path_id in {"dimension","border-top","border-bottom","border-left","border-right"}]
    assert _long(only_nonroof).status is Status.ABSTAINED
    dashed=[RoofPath(p.path_id,p.start,p.end,dashes="[3 2] 0") for p in _long_paths()]
    assert _long(dashed).status is Status.ABSTAINED
    assert _gable(material=()).status is Status.ABSTAINED


def test_competing_long_roof_rectangles_conflict_rather_than_choose_longest():
    paths=_long_paths()+[
        RoofPath("other-top",(30,40),(170,40)),
        RoofPath("other-bottom",(30,50),(170,50)),
        RoofPath("other-left",(30,40),(30,55)),
        RoofPath("other-right",(170,40),(170,55)),
    ]
    result=_long(paths)
    assert result.status is Status.CONFLICT
    assert result.span_pt is None


def test_gable_needs_opposing_roof_slopes_enclosing_structural_supports():
    p=[RoofPath("one-side",(15,65),(100,30))]
    assert _gable(p).status is Status.ABSTAINED
    p.append(RoofPath("inside-only",(100,30),(130,42.35)))
    assert _gable(p).status is Status.CONFLICT


def test_order_translation_and_scale_preserve_spans_without_mutating_inputs():
    original=_long_paths()
    before=deepcopy(original)
    reordered=original[:]
    Random(7).shuffle(reordered)
    assert _long(original)==_long(reordered)
    assert original==before
    shifted=_long(_long_paths(dx=11.75,dy=32.5),dy=32.5)
    assert shifted.span_pt==_long(original).span_pt
    doubled=_long(scale=2)
    assert doubled.span_pt==2*_long(original).span_pt
    gable=_gable()
    assert _gable(dx=11.75,dy=32.5).span_pt==gable.span_pt
    assert _gable(scale=2).span_pt==2*gable.span_pt


def test_incomplete_or_cross_page_view_universe_abstains():
    front=_long();gable=_gable()
    assert reconcile_roof_eave_geometry([front],gable,pitch_deg=22.38).status is Status.ABSTAINED
    rear=_long(viewport="rear",dy=150)
    swapped=type(rear)(rear.status,rear.reason_codes,2,rear.viewport_id,rear.span_pt,rear.start_pt,rear.end_pt,rear.path_ids,rear.candidate_id)
    assert reconcile_roof_eave_geometry([front,swapped],gable,pitch_deg=22.38).status is Status.CONFLICT
