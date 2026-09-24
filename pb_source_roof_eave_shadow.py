"""Shadow-only source-native roof edge geometry.

This module retains path identities and native PDF coordinates. It never
calibrates a page, assigns metres, or emits a commercial quantity.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
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
    path_index: Optional[int] = None
    layer_name: Optional[str] = None
    clip_id: Optional[str] = None


@dataclass(frozen=True)
class RoofSourceScope:
    document_id: str
    revision_id: str
    source_sha256: str
    source_page: int
    viewport_id: str
    entity_id: str

    def __post_init__(self) -> None:
        if not self.document_id or not self.revision_id or not self.viewport_id or not self.entity_id:
            raise ValueError("document, revision, viewport and entity ownership are required")
        if len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256):
            raise ValueError("source_sha256 must be a lower-case SHA-256 digest")
        if self.source_page < 1:
            raise ValueError("source_page must be positive")


@dataclass(frozen=True)
class RoofMaterialAnnotation:
    annotation_id: str
    text: str
    scope: RoofSourceScope
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class RoofEdgeAlternative:
    start_pt: float
    end_pt: float
    path_ids: tuple[str, ...]
    candidate_id: str


@dataclass(frozen=True)
class RoofEdgeCandidate:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope: RoofSourceScope
    span_pt: Optional[float] = None
    start_pt: Optional[float] = None
    end_pt: Optional[float] = None
    path_ids: tuple[str, ...] = ()
    candidate_id: Optional[str] = None
    pitch_deg: Optional[float] = None
    material_annotation_ids: tuple[str, ...] = ()
    alternatives: tuple[RoofEdgeAlternative, ...] = ()

    @property
    def source_page(self) -> int:
        return self.scope.source_page

    @property
    def viewport_id(self) -> str:
        return self.scope.viewport_id


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
    source_scope: Optional[RoofSourceScope] = None
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


def _owned_material(
    annotations: Sequence[RoofMaterialAnnotation], scope: RoofSourceScope,
    viewport_bbox: tuple[float, float, float, float],
) -> tuple[str, ...]:
    x0, y0, x1, y1 = viewport_bbox
    return tuple(sorted({a.annotation_id for a in annotations
                         if isinstance(a, RoofMaterialAnnotation) and a.scope == scope
                         and a.annotation_id and "roof" in a.text.lower()
                         and x0 <= a.bbox[0] < a.bbox[2] <= x1
                         and y0 <= a.bbox[1] < a.bbox[3] <= y1}))


def _result(
    status: EvidenceResolutionStatus, reason: str, scope: RoofSourceScope,
    *, start: Optional[float] = None, end: Optional[float] = None,
    path_ids: tuple[str, ...] = (), pitch_deg: Optional[float] = None,
    material_annotation_ids: tuple[str, ...] = (),
    alternatives: tuple[RoofEdgeAlternative, ...] = (),
) -> RoofEdgeCandidate:
    span = None if start is None or end is None else round(end-start,4)
    cid = None if span is None else stable_contract_id("roof_edge", {
        "document_id":scope.document_id,"revision_id":scope.revision_id,
        "entity_id":scope.entity_id,
        "source_sha256":scope.source_sha256,
        "source_page":scope.source_page,"viewport_id":scope.viewport_id,
        "start_pt":round(start,4),"end_pt":round(end,4),
    })
    return RoofEdgeCandidate(status,(reason,),scope,span,start,end,path_ids,cid,pitch_deg,
                             material_annotation_ids,alternatives)


def _alternatives(
    scope: RoofSourceScope, candidates: Sequence[tuple[float, float, tuple[str, ...]]],
) -> tuple[RoofEdgeAlternative, ...]:
    retained=[]
    for start,end,ids in sorted(candidates):
        candidate=_result(EvidenceResolutionStatus.CANDIDATE,"native_points_only",scope,
                          start=start,end=end,path_ids=ids)
        retained.append(RoofEdgeAlternative(start,end,ids,candidate.candidate_id))
    return tuple(retained)


def _merge_horizontal_rows(
    rows: list[tuple[float, float, float, RoofPath]],
    *, xtol: float, ytol: float,
) -> list[tuple[float, float, float, tuple[str, ...]]]:
    """Combine continuous collinear strokes without discarding their path IDs."""
    layers: list[list[tuple[float, float, float, RoofPath]]] = []
    for row in sorted(rows, key=lambda r: (r[2], r[0], r[1], r[3].path_id)):
        found = next((layer for layer in layers if abs(layer[0][2]-row[2]) <= ytol/10), None)
        if found is None:
            layers.append([row])
        else:
            found.append(row)
    merged = []
    for layer in layers:
        runs: list[tuple[float, float, set[str]]] = []
        for lo, hi, _y, path in sorted(layer, key=lambda r: (r[0], r[1], r[3].path_id)):
            if runs and lo <= runs[-1][1]+xtol:
                a, b, ids = runs[-1]
                ids.add(path.path_id)
                runs[-1] = (a, max(b, hi), ids)
            else:
                runs.append((lo, hi, {path.path_id}))
        merged.extend((a,b,layer[0][2],tuple(sorted(ids))) for a,b,ids in runs)
    return merged


def collect_longitudinal_roof_edge(
    paths: Sequence[RoofPath], *, scope: RoofSourceScope,
    viewport_bbox: tuple[float,float,float,float],
    page_width_pt: float, roof_material_annotations: Sequence[RoofMaterialAnnotation],
) -> RoofEdgeCandidate:
    """Retain one roof-fascia outline enclosed by side edges in an elevation.

    Repeated horizontal strokes by themselves could be a dimension or title
    frame. Both side edges, solid stroke, a material callout, and one unique
    outline are required. All competing outlines remain a conflict.
    """
    owned_material = _owned_material(roof_material_annotations, scope, viewport_bbox)
    if not owned_material:
        return _result(EvidenceResolutionStatus.ABSTAINED,"roof_material_unowned",scope)
    vx0,vy0,vx1,vy1=viewport_bbox
    w,h=vx1-vx0,vy1-vy0
    if w<=0 or h<=0 or page_width_pt<=0:
        return _result(EvidenceResolutionStatus.ABSTAINED,"invalid_viewport",scope)
    xtol=.002*w
    ytol=.003*h
    scoped=[p for p in paths if _visible_line(p) and _inside(p,viewport_bbox)]
    hs=[]; vs=[]
    for p in scoped:
        (x0,y0),(x1,y1)=p.start,p.end
        if abs(y1-y0)<=ytol:
            hs.append((min(x0,x1),max(x0,x1),(y0+y1)/2,p))
        elif abs(x1-x0)<=xtol and abs(y1-y0)>ytol:
            vs.append(((x0+x1)/2,min(y0,y1),max(y0,y1),p))
    merged = _merge_horizontal_rows(hs,xtol=xtol,ytol=ytol)
    groups=[]
    for row in sorted(merged,key=lambda z:(z[0],z[1],z[2],z[3])):
        if not (.20*w <= row[1]-row[0] < .9*page_width_pt):
            continue
        found=next((g for g in groups if abs(g[0][0]-row[0])<=xtol and abs(g[0][1]-row[1])<=xtol),None)
        if found is None:groups.append([row])
        else:found.append(row)
    candidates=[]
    for group in groups:
        ys=sorted({round(r[2],4) for r in group})
        if len(ys)<2 or ys[-1]-ys[0]<=ytol:continue
        xlo=sum(r[0] for r in group)/len(group)
        xhi=sum(r[1] for r in group)/len(group)
        side_groups=[]
        for x in (xlo,xhi):
            options=[v for v in vs if abs(v[0]-x)<=xtol and v[1]<=ys[0]+ytol and v[2]>=ys[-1]-ytol]
            if not options:break
            side_groups.append(tuple(sorted(v[3].path_id for v in options)))
        if len(side_groups)!=2:continue
        ids=tuple(sorted({*(pid for r in group for pid in r[3]),
                          *(pid for side in side_groups for pid in side)}))
        candidates.append((round(xlo,4),round(xhi,4),ids))
    if not candidates:
        return _result(EvidenceResolutionStatus.ABSTAINED,"roof_outline_unavailable",scope)
    if len(candidates)>1:
        return _result(EvidenceResolutionStatus.CONFLICT,"competing_roof_outlines",scope,
                       alternatives=_alternatives(scope,candidates))
    a,b,ids=candidates[0]
    return _result(EvidenceResolutionStatus.CANDIDATE,"roof_outline_native_points_only",scope,
                   start=a,end=b,path_ids=ids,material_annotation_ids=owned_material)


def collect_gable_outer_roof_edge(
    paths: Sequence[RoofPath], *, scope: RoofSourceScope,
    viewport_bbox: tuple[float,float,float,float],
    apex_xy: tuple[float,float], pitch_deg: float,
    structural_left_x: float, structural_right_x: float,
    roof_material_annotations: Sequence[RoofMaterialAnnotation],
) -> RoofEdgeCandidate:
    """Keep both outer slope endpoints from one authenticated gable apex."""
    owned_material = _owned_material(roof_material_annotations, scope, viewport_bbox)
    if not owned_material:
        return _result(EvidenceResolutionStatus.ABSTAINED,"roof_material_unowned",scope)
    x0,y0,x1,y1=viewport_bbox
    if x1<=x0 or y1<=y0 or not (5<=pitch_deg<=65 and structural_left_x<structural_right_x):
        return _result(EvidenceResolutionStatus.ABSTAINED,"gable_context_invalid",scope)
    tol=.01*(x1-x0)
    join_tol=.001*(x1-x0)
    apex_x,apex_y=apex_xy
    sides={-1:[],1:[]}
    for p in paths:
        if not _visible_line(p) or not _inside(p,viewport_bbox):continue
        a,b=sorted((p.start,p.end),key=lambda pt:abs(pt[0]-apex_x))
        dx,dy=b[0]-a[0],b[1]-a[1]
        if abs(dx)<.001*(x1-x0):continue
        direction=-1 if dx<0 else 1
        near,far=direction*(a[0]-apex_x),direction*(b[0]-apex_x)
        if near < -join_tol or far <= near:continue
        intercept=a[1]-(a[0]-apex_x)*dy/dx
        if abs(intercept-apex_y)>tol:continue
        measured=math.degrees(math.atan2(abs(dy),abs(dx)))
        if abs(measured-pitch_deg)>1:continue
        sides[direction].append((max(0,near),far,p.path_id))
    if not sides[-1] or not sides[1]:
        return _result(EvidenceResolutionStatus.ABSTAINED,"outer_gable_pair_unavailable",scope)
    endpoint_options={}
    for direction, segments in sides.items():
        reachable=[]
        extent=join_tol
        for near,far,pid in sorted(segments):
            if near>extent+join_tol:continue
            extent=max(extent,far)
            reachable.append((near,far,pid))
        if not reachable:
            return _result(EvidenceResolutionStatus.ABSTAINED,"outer_gable_pair_unavailable",scope)
        support_distance=abs((structural_left_x if direction<0 else structural_right_x)-apex_x)
        terminals=[far for near,far,pid in reachable if far>support_distance+join_tol
                   if not any(abs(other_near-far)<=join_tol and other_far>far+join_tol
                              for other_near,other_far,_ in reachable)]
        if not terminals:
            return _result(EvidenceResolutionStatus.CONFLICT,"gable_edges_do_not_enclose_supports",scope)
        groups=[]
        for far in sorted(set(terminals)):
            found=next((group for group in groups if far-group[0]<=tol),None)
            if found is None: groups.append([far])
            else: found.append(far)
        options=[]
        for group in groups:
            endpoint=max(group)
            selected={(near,far,pid) for near,far,pid in reachable
                      if any(abs(far-t)<=join_tol for t in group)}
            frontier=[near for near,_,_ in selected]
            while frontier:
                distance=frontier.pop()
                for segment in reachable:
                    if segment not in selected and abs(segment[1]-distance)<=join_tol:
                        selected.add(segment)
                        frontier.append(segment[0])
            options.append((apex_x+direction*endpoint,tuple(sorted(pid for _,_,pid in selected))))
        endpoint_options[direction]=options
    pairs=[(round(left,4),round(right,4),tuple(sorted(set(left_ids+right_ids))))
           for (left,left_ids),(right,right_ids) in product(endpoint_options[-1],endpoint_options[1])]
    if len(pairs)>1:
        return _result(EvidenceResolutionStatus.CONFLICT,"competing_gable_edges",scope,
                       alternatives=_alternatives(scope,pairs))
    left,right,ids=pairs[0]
    if not (left<=structural_left_x<structural_right_x<=right):
        return _result(EvidenceResolutionStatus.CONFLICT,"gable_edges_do_not_enclose_supports",scope)
    return _result(EvidenceResolutionStatus.CANDIDATE,"gable_edge_native_points_only",scope,
                   start=left,end=right,path_ids=ids,pitch_deg=pitch_deg,
                   material_annotation_ids=owned_material)


def reconcile_roof_eave_geometry(
    longitudinal: Sequence[RoofEdgeCandidate], transverse: RoofEdgeCandidate,
    *, pitch_deg: float,
) -> RoofEaveGeometryShadow:
    """Corroborate native geometry, never its physical scale or a quantity."""
    if len(longitudinal)<2 or any(c.status is not EvidenceResolutionStatus.CANDIDATE for c in longitudinal) or transverse.status is not EvidenceResolutionStatus.CANDIDATE:
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED,("incomplete_roof_view_universe",),None,None,None,None,(),())
    if any((c.scope.document_id,c.scope.revision_id,c.scope.source_sha256,c.scope.source_page,c.scope.entity_id)!=(transverse.scope.document_id,transverse.scope.revision_id,transverse.scope.source_sha256,transverse.scope.source_page,transverse.scope.entity_id) for c in longitudinal):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT,("source_scope_conflict",),None,None,None,None,(),())
    view_ids=[c.viewport_id for c in longitudinal]+[transverse.viewport_id]
    if len(view_ids)!=len(set(view_ids)) or not math.isfinite(pitch_deg) or transverse.pitch_deg is None or abs(transverse.pitch_deg-pitch_deg)>.01:
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT,("roof_view_identity_conflict",),None,None,None,None,(),())
    spans=[c.span_pt for c in longitudinal]
    if any(v is None for v in spans) or max(spans)-min(spans)>.003*max(spans):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT,("longitudinal_elevations_disagree",),None,None,None,None,(),())
    ids=tuple(sorted({p for c in (*longitudinal,transverse) for p in c.path_ids}))
    return RoofEaveGeometryShadow(
        EvidenceResolutionStatus.CANDIDATE,("native_roof_edges_correspond_but_scale_unresolved",),
        round(sum(spans)/len(spans),4),transverse.span_pt,round(pitch_deg,4),
        transverse.source_page,tuple(sorted(view_ids)),ids,transverse.scope,
    )
