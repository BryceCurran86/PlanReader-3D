"""Shadow-only source-native roof edge geometry.

This module retains path identities and native PDF coordinates. It never
calibrates a page, assigns metres, or emits a commercial quantity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


@dataclass(frozen=True)
class RoofPath:
    path_id: str
    start: tuple[float, float]
    end: tuple[float, float]
    stroke: tuple[float, float, float] = (0.0, 0.0, 0.0)
    width_pt: float = 1.0
    dashes: str = "[] 0"


@dataclass(frozen=True)
class RoofEdgeCandidate:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    source_page: int
    viewport_id: str
    span_pt: Optional[float] = None
    start_pt: Optional[float] = None
    end_pt: Optional[float] = None
    path_ids: tuple[str, ...] = ()
    candidate_id: Optional[str] = None


@dataclass(frozen=True)
class RoofEaveGeometryShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    longitudinal_span_pt: Optional[float]
    transverse_span_pt: Optional[float]
    pitch_deg: Optional[float]
    source_page: Optional[int]
    viewport_ids: tuple[str, ...]
    path_ids: tuple[str, ...]
    quantity_m2: None = None  # Native geometry cannot confer measurement authority.


def _visible_line(path: RoofPath) -> bool:
    return (
        bool(path.path_id)
        and math.isfinite(path.width_pt)
        and path.width_pt > 0
        and len(path.stroke) >= 3
        and all(math.isfinite(v) and 0 <= v <= .15 for v in path.stroke[:3])
        and str(path.dashes).strip() in {"[] 0", "[] 0.0", ""}
        and all(math.isfinite(v) for v in (*path.start, *path.end))
    )


def _inside(path: RoofPath, bbox: tuple[float, float, float, float]) -> bool:
    x0,y0,x1,y1=bbox
    return all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (path.start,path.end))


def _result(
    status: EvidenceResolutionStatus, reason: str, page: int, viewport: str,
    *, start: Optional[float] = None, end: Optional[float] = None,
    path_ids: tuple[str, ...] = (),
) -> RoofEdgeCandidate:
    span = None if start is None or end is None else round(end-start,4)
    cid = None if span is None else stable_contract_id("roof_edge", {
        "source_page":page,"viewport_id":viewport,
        "start_pt":round(start,4),"end_pt":round(end,4),
        "path_ids":path_ids,
    })
    return RoofEdgeCandidate(status,(reason,),page,viewport,span,start,end,path_ids,cid)


def collect_longitudinal_roof_edge(
    paths: Sequence[RoofPath], *, source_page: int, viewport_id: str,
    viewport_bbox: tuple[float,float,float,float],
    page_width_pt: float, roof_material_annotations: Sequence[str],
) -> RoofEdgeCandidate:
    """Retain one roof-fascia outline enclosed by side edges in an elevation.

    Repeated horizontal strokes by themselves could be a dimension or title
    frame. Both side edges, solid stroke, a material callout, and one unique
    outline are required. All competing outlines remain a conflict.
    """
    if not roof_material_annotations or not any(str(s).strip() for s in roof_material_annotations):
        return _result(EvidenceResolutionStatus.ABSTAINED,"roof_material_unowned",source_page,viewport_id)
    vx0,vy0,vx1,vy1=viewport_bbox
    w,h=vx1-vx0,vy1-vy0
    if w<=0 or h<=0 or page_width_pt<=0:
        return _result(EvidenceResolutionStatus.ABSTAINED,"invalid_viewport",source_page,viewport_id)
    xtol=.002*w
    ytol=.003*h
    scoped=[p for p in paths if _visible_line(p) and _inside(p,viewport_bbox)]
    hs=[]; vs=[]
    for p in scoped:
        (x0,y0),(x1,y1)=p.start,p.end
        if abs(y1-y0)<=ytol and .20*w<=abs(x1-x0)<.9*page_width_pt:
            hs.append((min(x0,x1),max(x0,x1),(y0+y1)/2,p))
        elif abs(x1-x0)<=xtol and abs(y1-y0)>ytol:
            vs.append(((x0+x1)/2,min(y0,y1),max(y0,y1),p))
    groups=[]
    for row in sorted(hs,key=lambda z:(z[0],z[1],z[2],z[3].path_id)):
        found=next((g for g in groups if abs(g[0][0]-row[0])<=xtol and abs(g[0][1]-row[1])<=xtol),None)
        if found is None:groups.append([row])
        else:found.append(row)
    candidates=[]
    for group in groups:
        ys=sorted({round(r[2],4) for r in group})
        if len(ys)<2 or ys[-1]-ys[0]<=ytol:continue
        xlo=sum(r[0] for r in group)/len(group)
        xhi=sum(r[1] for r in group)/len(group)
        side=[]
        for x in (xlo,xhi):
            options=[v for v in vs if abs(v[0]-x)<=xtol and v[1]<=ys[0]+ytol and v[2]>=ys[-1]-ytol]
            if not options:break
            side.append(sorted(options,key=lambda v:v[3].path_id)[0][3].path_id)
        if len(side)!=2:continue
        ids=tuple(sorted({*(r[3].path_id for r in group),*side}))
        candidates.append((round(xlo,4),round(xhi,4),ids))
    if not candidates:
        return _result(EvidenceResolutionStatus.ABSTAINED,"roof_outline_unavailable",source_page,viewport_id)
    if len(candidates)>1:
        return _result(EvidenceResolutionStatus.CONFLICT,"competing_roof_outlines",source_page,viewport_id)
    a,b,ids=candidates[0]
    return _result(EvidenceResolutionStatus.CANDIDATE,"roof_outline_native_points_only",source_page,viewport_id,start=a,end=b,path_ids=ids)


def collect_gable_outer_roof_edge(
    paths: Sequence[RoofPath], *, source_page: int, viewport_id: str,
    viewport_bbox: tuple[float,float,float,float],
    apex_xy: tuple[float,float], pitch_deg: float,
    structural_left_x: float, structural_right_x: float,
    roof_material_annotations: Sequence[str],
) -> RoofEdgeCandidate:
    """Keep both outer slope endpoints from one authenticated gable apex."""
    if not roof_material_annotations or not any(str(s).strip() for s in roof_material_annotations):
        return _result(EvidenceResolutionStatus.ABSTAINED,"roof_material_unowned",source_page,viewport_id)
    x0,y0,x1,y1=viewport_bbox
    if x1<=x0 or y1<=y0 or not (5<=pitch_deg<=65 and structural_left_x<structural_right_x):
        return _result(EvidenceResolutionStatus.ABSTAINED,"gable_context_invalid",source_page,viewport_id)
    tol=.01*(x1-x0)
    apex_x,apex_y=apex_xy
    sides={-1:[],1:[]}
    for p in paths:
        if not _visible_line(p) or not _inside(p,viewport_bbox):continue
        a,b=sorted((p.start,p.end),key=lambda pt:pt[1])
        dx,dy=b[0]-a[0],b[1]-a[1]
        if abs(dx)<.03*(x1-x0) or dy<=0:continue
        if math.hypot(a[0]-apex_x,a[1]-apex_y)>tol:continue
        measured=math.degrees(math.atan2(dy,abs(dx)))
        if abs(measured-pitch_deg)>1:continue
        direction=-1 if dx<0 else 1
        sides[direction].append((b[0],p.path_id))
    if not sides[-1] or not sides[1]:
        return _result(EvidenceResolutionStatus.ABSTAINED,"outer_gable_pair_unavailable",source_page,viewport_id)
    left=min(x for x,_ in sides[-1]);right=max(x for x,_ in sides[1])
    if not (left<=structural_left_x<structural_right_x<=right):
        return _result(EvidenceResolutionStatus.CONFLICT,"gable_edges_do_not_enclose_supports",source_page,viewport_id)
    ids=tuple(sorted({pid for x,pid in sides[-1] if abs(x-left)<=tol}|{pid for x,pid in sides[1] if abs(x-right)<=tol}))
    return _result(EvidenceResolutionStatus.CANDIDATE,"gable_edge_native_points_only",source_page,viewport_id,start=round(left,4),end=round(right,4),path_ids=ids)


def reconcile_roof_eave_geometry(
    longitudinal: Sequence[RoofEdgeCandidate], transverse: RoofEdgeCandidate,
    *, pitch_deg: float,
) -> RoofEaveGeometryShadow:
    """Corroborate native geometry, never its physical scale or a quantity."""
    if len(longitudinal)<2 or any(c.status is not EvidenceResolutionStatus.CANDIDATE for c in longitudinal) or transverse.status is not EvidenceResolutionStatus.CANDIDATE:
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED,("incomplete_roof_view_universe",),None,None,None,None,(),())
    if any(c.source_page!=transverse.source_page for c in longitudinal):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT,("cross_page_building_identity_unresolved",),None,None,None,None,(),())
    view_ids=[c.viewport_id for c in longitudinal]+[transverse.viewport_id]
    if len(view_ids)!=len(set(view_ids)) or not math.isfinite(pitch_deg):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT,("roof_view_identity_conflict",),None,None,None,None,(),())
    spans=[c.span_pt for c in longitudinal]
    if any(v is None for v in spans) or max(spans)-min(spans)>.003*max(spans):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT,("longitudinal_elevations_disagree",),None,None,None,None,(),())
    ids=tuple(sorted({p for c in (*longitudinal,transverse) for p in c.path_ids}))
    return RoofEaveGeometryShadow(
        EvidenceResolutionStatus.CORROBORATED,("native_roof_edges_correspond_but_scale_unresolved",),
        round(sum(spans)/len(spans),4),transverse.span_pt,round(pitch_deg,4),
        transverse.source_page,tuple(sorted(view_ids)),ids,
    )
