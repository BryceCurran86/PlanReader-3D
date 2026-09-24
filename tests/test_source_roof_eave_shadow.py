from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from random import Random

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_roof_eave_shadow import (
    RoofMaterialAnnotation,
    RoofPath,
    RoofSourceScope,
    collect_gable_outer_roof_edge,
    collect_longitudinal_roof_edge,
    reconcile_roof_eave_geometry,
)


def _scope(viewport: str, page: int = 1, revision: str = "rev-1") -> RoofSourceScope:
    return RoofSourceScope("doc-1", revision, "0"*64, page, viewport, "roof-1")


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
        scope=_scope(viewport),
        viewport_bbox=(0,0+dy,200*scale,120*scale+dy),
        page_width_pt=200*scale,
        roof_material_annotations=tuple(RoofMaterialAnnotation(
            f"callout:{i}",text,_scope(viewport),
            (40*scale,10*scale+dy,90*scale,18*scale+dy))
            for i,text in enumerate(material)),
    )


def _gable(paths=None, *, dx=0, dy=0, scale=1, material=("sheet roofing",), apex=None):
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
        paths,scope=_scope("gable"),
        viewport_bbox=(dx,dy,200*scale+dx,120*scale+dy),
        apex_xy=apex if apex is not None else pt(100,30),pitch_deg=22.38,
        structural_left_x=40*scale+dx,structural_right_x=160*scale+dx,
        roof_material_annotations=tuple(RoofMaterialAnnotation(
            f"gable-callout:{i}",text,_scope("gable"),
            (40*scale+dx,5*scale+dy,90*scale+dx,18*scale+dy))
            for i,text in enumerate(material)),
    )


def test_two_owned_long_elevations_and_gable_keep_native_geometry_only():
    front=_long()
    rear=_long(viewport="rear",dy=150)
    gable=_gable()
    assert (front.status,rear.status,gable.status)==(Status.CANDIDATE,)*3
    assert front.span_pt==rear.span_pt==160
    assert gable.span_pt==170
    result=reconcile_roof_eave_geometry([front,rear],gable,pitch_deg=22.38)
    assert result.status is Status.CANDIDATE
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


def test_material_callout_must_share_viewport_source_and_entity():
    for wrong in (
        RoofMaterialAnnotation("x","roofing",_scope("rear"),(40,10,90,18)),
        RoofMaterialAnnotation("x","roofing",replace(_scope("front"),entity_id="other"),(40,10,90,18)),
        RoofMaterialAnnotation("x","roofing",replace(_scope("front"),source_sha256="1"*64),(40,10,90,18)),
        RoofMaterialAnnotation("x","roofing",_scope("front"),(40,121,90,130)),
        RoofMaterialAnnotation("x","window",_scope("front"),(40,10,90,18)),
    ):
        result=collect_longitudinal_roof_edge(
            _long_paths(),scope=_scope("front"),viewport_bbox=(0,0,200,120),
            page_width_pt=200,roof_material_annotations=(wrong,),
        )
        assert result.status is Status.ABSTAINED


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
    assert {a.end_pt-a.start_pt for a in result.alternatives}=={140,160}
    assert all(a.candidate_id for a in result.alternatives)


def test_duplicate_side_strokes_are_retained_without_first_match_selection():
    paths=_long_paths()+[RoofPath("roof-left-second",(20,20),(20,35))]
    result=_long(paths)
    assert result.status is Status.CANDIDATE
    assert {"roof-left","roof-left-second"} <= set(result.path_ids)


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
    swapped=replace(rear,scope=_scope("rear",page=2))
    assert reconcile_roof_eave_geometry([front,swapped],gable,pitch_deg=22.38).status is Status.CONFLICT


def test_cross_revision_and_source_hash_cannot_reconcile():
    front=_long();rear=_long(viewport="rear",dy=150);gable=_gable()
    other_revision=replace(rear,scope=_scope("rear",revision="rev-2"))
    assert reconcile_roof_eave_geometry([front,other_revision],gable,pitch_deg=22.38).status is Status.CONFLICT
    changed_hash=replace(rear,scope=replace(rear.scope,source_sha256="1"*64))
    assert reconcile_roof_eave_geometry([front,changed_hash],gable,pitch_deg=22.38).status is Status.CONFLICT


def test_split_paths_preserve_geometry_and_contract_id():
    original=_long()
    whole=_long_paths()
    split=[]
    for p in whole:
        if p.path_id in {"roof-top","roof-bottom"}:
            middle=((p.start[0]+p.end[0])/2,p.start[1])
            split.extend([replace(p,path_id=p.path_id+":a",end=middle),
                          replace(p,path_id=p.path_id+":b",start=middle)])
        else:
            split.append(p)
    result=_long(split)
    assert result.status is Status.CANDIDATE
    assert result.span_pt==original.span_pt
    assert result.candidate_id==original.candidate_id
    assert len(result.path_ids)==len(original.path_ids)+2

    gable=_gable()
    def bisect(p):
        middle=tuple((x+y)/2 for x,y in zip(p.start,p.end))
        return [replace(p,path_id=p.path_id+":a",end=middle),
                replace(p,path_id=p.path_id+":b",start=middle)]
    split_gable=[*bisect(RoofPath("left-outer",(15,65),(100,30))),
                 *bisect(RoofPath("right-outer",(100,30),(185,65)))]
    gable_result=_gable(split_gable)
    assert gable_result.status is Status.CANDIDATE
    assert gable_result.span_pt==gable.span_pt
    assert gable_result.candidate_id==gable.candidate_id


def test_unrelated_content_and_viewport_expansion_preserve_candidate():
    original=_long()
    expanded=collect_longitudinal_roof_edge(
        _long_paths()+[RoofPath("furniture",(205,60),(220,70)),
                       RoofPath("grid",(10,90),(190,90),dashes="[2 2] 0")],
        scope=_scope("front"),viewport_bbox=(-10,-10,230,140),
        page_width_pt=230,roof_material_annotations=(RoofMaterialAnnotation(
            "callout:0","corrugated roofing",_scope("front"),(40,10,90,18)),),
    )
    assert expanded.status is Status.CANDIDATE
    assert expanded.span_pt==original.span_pt
    assert expanded.candidate_id==original.candidate_id


def test_rotation_180_preserves_long_span_and_gable_span():
    original=_long()
    def turn(p):
        return replace(p,start=(200-p.start[0],120-p.start[1]),
                       end=(200-p.end[0],120-p.end[1]))
    turned=collect_longitudinal_roof_edge(
        [turn(p) for p in _long_paths()],scope=_scope("front"),
        viewport_bbox=(0,0,200,120),page_width_pt=200,
        roof_material_annotations=(RoofMaterialAnnotation(
            "callout:0","corrugated roofing",_scope("front"),(40,10,90,18)),),
    )
    assert turned.status is Status.CANDIDATE
    assert turned.span_pt==original.span_pt
    paths=[RoofPath("left-outer",(15,65),(100,30)),
           RoofPath("right-outer",(100,30),(185,65))]
    turned_gable=_gable([turn(p) for p in paths],apex=(100,90))
    assert turned_gable.status is Status.CANDIDATE
    assert turned_gable.span_pt==_gable().span_pt


def test_competing_gable_endpoints_and_entity_or_pitch_conflicts_abstain():
    ambiguous=[RoofPath("left-a",(15,65),(100,30)),
               RoofPath("left-b",(25,60.88),(100,30)),
               RoofPath("right",(100,30),(185,65))]
    gable_conflict=_gable(ambiguous)
    assert gable_conflict.status is Status.CONFLICT
    assert len(gable_conflict.alternatives)==2
    assert {a.start_pt for a in gable_conflict.alternatives}=={15,25}
    front=_long();rear=_long(viewport="rear",dy=150);gable=_gable()
    other_entity=replace(rear,scope=replace(rear.scope,entity_id="roof-2"))
    assert reconcile_roof_eave_geometry([front,other_entity],gable,pitch_deg=22.38).status is Status.CONFLICT
    assert reconcile_roof_eave_geometry([front,rear],gable,pitch_deg=30).status is Status.CONFLICT


def test_replay_is_deterministic_and_inputs_are_unchanged():
    paths=_long_paths()
    original=deepcopy(paths)
    results=[_long(paths) for _ in range(4)]
    assert all(r==results[0] for r in results)
    assert results[0].candidate_id
    assert paths==original
