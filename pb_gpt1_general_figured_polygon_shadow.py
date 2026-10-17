"""General, non-orthogonal figured source-side metric polygon solver.

This is shadow computation only. Directions come from separately evidenced
native source geometry and lengths only from producer-owned figured dimensions.
No PDF-point length is used as a metric scale. At most two missing metric
lengths may be solved from exact closed-ring vector constraints. A source
drawing can be distorted: caller must independently authenticate wall-face
roles and angled-bearing authority before any commercial promotion.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
import re
from typing import Sequence
from shapely.geometry import Polygon
from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide, FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


def measure_general_figured_polygon_shadow(
    sides: Sequence[FiguredPhysicalSide], *,
    source_sha256: str, revision_id: str, page_id: str, physical_room_id: str,
) -> FiguredPolygonMetricShadow:
    """Solve source-figured vector polygon, never select an arbitrary scale."""
    def blocked(reason: str) -> FiguredPolygonMetricShadow:
        return FiguredPolygonMetricShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),None,(),(),(),
            str(source_sha256),str(revision_id),str(page_id),str(physical_room_id)
        )
    if (
        type(source_sha256) is not str or not re.fullmatch("[0-9a-f]{64}",source_sha256)
        or any(type(v) is not str or not v or v!=v.strip()
               for v in (revision_id,page_id,physical_room_id))
        or type(sides) not in (tuple,list) or len(sides)<3
    ):
        return blocked("source_general_polygon_lineage_unavailable")
    start,end,unit,lengths=[],[],[],[]
    figures,side_ids,segment_ids=set(),set(),set()
    for side in sides:
        if type(side) is not FiguredPhysicalSide:
            return blocked("source_general_polygon_side_untrusted")
        if (
            type(side.source_side_id) is not str or not side.source_side_id
            or side.source_side_id in side_ids
            or type(side.source_segment_ids) not in (tuple,list)
            or not side.source_segment_ids
            or any(type(v) is not str or not v or v in segment_ids
                   for v in side.source_segment_ids)
        ):
            return blocked("source_general_polygon_side_identity_conflict")
        side_ids.add(side.source_side_id)
        segment_ids.update(side.source_segment_ids)
        def coord(raw):
            if type(raw) not in (tuple,list) or len(raw)!=2 or any(
                type(x) not in (int,float) for x in raw
            ):
                return None
            try:
                item=tuple(float(x) for x in raw)
            except (TypeError,ValueError,OverflowError):
                return None
            return item if all(math.isfinite(x) for x in item) else None
        a,b=coord(side.start_pdf_pt),coord(side.end_pdf_pt)
        if a is None or b is None or a==b:
            return blocked("source_general_polygon_geometry_unavailable")
        vec=(b[0]-a[0],b[1]-a[1])
        magnitude=math.hypot(*vec)
        if magnitude==0 or not math.isfinite(magnitude):
            return blocked("source_general_polygon_geometry_unavailable")
        start.append(a);end.append(b);unit.append(tuple(x/magnitude for x in vec))
        if side.length_mm is None:
            if side.figured_dimension_id is not None or side.witness_observation_ids:
                return blocked("source_general_polygon_figured_dimension_incomplete")
            lengths.append(None)
        else:
            if type(side.length_mm) not in (int,float):
                return blocked("source_general_polygon_figured_dimension_invalid")
            try:
                mm=float(side.length_mm)
            except (TypeError,ValueError,OverflowError):
                return blocked("source_general_polygon_figured_dimension_invalid")
            if (
                not math.isfinite(mm) or mm<=0
                or type(side.figured_dimension_id) is not str
                or not side.figured_dimension_id
                or side.figured_dimension_id in figures
                or type(side.witness_observation_ids) not in (tuple,list)
                or len(side.witness_observation_ids)<2
                or any(type(v) is not str or not v for v in side.witness_observation_ids)
                or len(set(side.witness_observation_ids)) != len(side.witness_observation_ids)
            ):
                return blocked("source_general_polygon_figured_dimension_invalid")
            figures.add(side.figured_dimension_id)
            lengths.append(mm)
    if any(end[i]!=start[(i+1)%len(start)] for i in range(len(start))):
        return blocked("source_general_polygon_physical_ring_unclosed")
    if len(set(start))!=len(start):
        return blocked("source_general_polygon_physical_ring_repeated_vertex")
    original=Polygon(start)
    if not original.is_valid or original.area<=0:
        return blocked("source_general_polygon_physical_ring_not_simple")
    unknown=[i for i,x in enumerate(lengths) if x is None]
    if len(unknown)>2:
        return blocked("source_general_polygon_underconstrained")
    rhs=tuple(-math.fsum(axis[k]*lengths[i]
                         for i,axis in enumerate(unit) if lengths[i] is not None)
              for k in (0,1))
    if len(unknown)==1:
        u=unit[unknown[0]]
        answer=u[0]*rhs[0]+u[1]*rhs[1]
        residual=math.hypot(rhs[0]-answer*u[0],rhs[1]-answer*u[1])
        if answer<=0 or residual>1e-8*max(1,math.hypot(*rhs)):
            return blocked("source_general_polygon_figures_conflict")
        lengths[unknown[0]]=answer
    elif len(unknown)==2:
        i,j=unknown
        u,v=unit[i],unit[j]
        det=u[0]*v[1]-u[1]*v[0]
        if abs(det)<1e-10:
            return blocked("source_general_polygon_underconstrained")
        left=(rhs[0]*v[1]-rhs[1]*v[0])/det
        right=(u[0]*rhs[1]-u[1]*rhs[0])/det
        if left<=0 or right<=0 or not all(math.isfinite(x) for x in (left,right)):
            return blocked("source_general_polygon_figures_conflict")
        lengths[i],lengths[j]=left,right
    else:
        if math.hypot(*rhs)>1e-8*max(1,math.fsum(lengths)):
            return blocked("source_general_polygon_figures_conflict")

    metric=[(0.,0.)]
    for (dx,dy),mm in zip(unit,lengths):
        x,y=metric[-1];metric.append((x+mm*dx,y+mm*dy))
    if math.dist(metric[-1],metric[0])>1e-8*max(1.,*(abs(c) for p in metric for c in p)):
        return blocked("source_general_polygon_metric_closure_conflict")
    closed=Polygon(metric[:-1])
    if not closed.is_valid or not math.isfinite(closed.area) or closed.area<=0:
        return blocked("source_general_polygon_metric_ring_not_simple")
    return FiguredPolygonMetricShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("source_general_figured_polygon_shadow_only",),
        closed.area/1e6, tuple(metric[:-1]),tuple(sorted(figures)),
        tuple(sorted(sides[i].source_side_id for i in unknown)),
        source_sha256,revision_id,page_id,physical_room_id,True,
        tuple(side.source_side_id for side in sides),
        tuple(sorted(segment_ids)),tuple(start),
    )
