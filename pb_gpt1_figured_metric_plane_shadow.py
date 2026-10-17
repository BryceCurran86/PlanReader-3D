"""Candidate PDF-point to metric plane anchored ONLY in source figured polygon.

Use a physically source-owned room perimeter with its independently figured
metric counterpart to derive a unique 2-D affine mapping. Every original wall
vertex must agree; a fit from a few convenient controls is not sufficient.

This is not an approved plan scale or authority for new FIRM quantities. Its
purpose is to measure internal candidate sections within an already measured
parent, with every residual/competitor retained for separate source review.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from shapely.geometry import Polygon
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class FiguredMetricPlaneShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    pdf_to_metric_affine: tuple[float, float, float, float, float, float] | None
    original_parent_source_side_ids: tuple[str, ...]
    original_parent_source_sha256: str
    original_revision_id: str
    original_page_id: str
    original_physical_room_id: str
    largest_original_vertex_residual_mm: float | None
    diagnostic_only: bool = True


@dataclass(frozen=True)
class OriginalInternalSourceSection:
    source_section_id: str
    source_section_boundary_ids: tuple[str, ...]
    source_pdf_ring: tuple[tuple[float, float], ...]
    source_section_mark_receipts: tuple[str, ...]


@dataclass(frozen=True)
class FiguredMappedSectionsShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    measured_section_areas_m2: tuple[tuple[str, float], ...]
    remaining_unallocated_room_area_m2: float | None
    source_section_ids: tuple[str, ...]
    diagnostic_only: bool = True


def _safe_ring(raw: object):
    if type(raw) not in (list,tuple) or len(raw)<3:
        return None
    points=[]
    for p in raw:
        if type(p) not in (tuple,list) or len(p)!=2 or any(
            type(n) not in (float,int) for n in p
        ):
            return None
        try:
            pair=(float(p[0]),float(p[1]))
        except (TypeError,ValueError,OverflowError):
            return None
        if not all(math.isfinite(n) for n in pair):
            return None
        points.append(pair)
    if len(points)>1 and points[0]==points[-1]:
        points.pop()
    if len(points)<3 or len(set(points))!=len(points):
        return None
    polygon=Polygon(points)
    return (tuple(points),polygon) if polygon.is_valid and polygon.area>0 else None


def _affine_from_three(a,b,c,u,v,w):
    """Solve a*x+b*y+t for independent source/metric triplets."""
    dx1=b[0]-a[0];dy1=b[1]-a[1]
    dx2=c[0]-a[0];dy2=c[1]-a[1]
    det=dx1*dy2-dy1*dx2
    if abs(det) <= 1e-12*max(1.,abs(dx1),abs(dx2),abs(dy1),abs(dy2))**2:
        return None
    mx1=v[0]-u[0];my1=v[1]-u[1]
    mx2=w[0]-u[0];my2=w[1]-u[1]
    ax=(mx1*dy2-mx2*dy1)/det
    ay=(mx2*dx1-mx1*dx2)/det
    bx=(my1*dy2-my2*dy1)/det
    by=(my2*dx1-my1*dx2)/det
    tx=u[0]-ax*a[0]-ay*a[1]
    ty=u[1]-bx*a[0]-by*a[1]
    result=(ax,ay,tx,bx,by,ty)
    return result if all(math.isfinite(f) for f in result) else None


def _map(affine,point):
    ax,ay,tx,bx,by,ty=affine
    x,y=point
    return (ax*x+ay*y+tx,bx*x+by*y+ty)


def resolve_source_figured_metric_plane_shadow(
    parent: FiguredPolygonMetricShadow,
) -> FiguredMetricPlaneShadow:
    def block(reason):
        return FiguredMetricPlaneShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),None,(),
            str(getattr(parent,"source_sha256","")),
            str(getattr(parent,"revision_id","")),
            str(getattr(parent,"page_id","")),
            str(getattr(parent,"physical_room_id","")),None,
        )
    if (
        type(parent) is not FiguredPolygonMetricShadow
        or parent.status is not EvidenceResolutionStatus.CANDIDATE
        or parent.diagnostic_only is not True
        or not parent.source_side_ids or not parent.source_segment_ids
        or len(parent.source_side_ids)!=len(parent.metric_vertices_mm)
        or len(parent.source_side_ids)!=len(parent.source_vertices_pdf_pts)
        or len(set(parent.source_side_ids))!=len(parent.source_side_ids)
    ):
        return block("source_figured_metric_plane_parent_unavailable")
    native=_safe_ring(parent.source_vertices_pdf_pts)
    metric=_safe_ring(parent.metric_vertices_mm)
    if native is None or metric is None:
        return block("source_figured_metric_plane_invalid_rings")
    source_points,source_polygon=native
    dest_points,dest_polygon=metric
    affine=None
    for i in range(len(source_points)-2):
        for j in range(i+1,len(source_points)-1):
            for k in range(j+1,len(source_points)):
                affine=_affine_from_three(
                    source_points[i],source_points[j],source_points[k],
                    dest_points[i],dest_points[j],dest_points[k],
                )
                if affine is not None:
                    break
            if affine is not None:
                break
        if affine is not None:
            break
    if affine is None:
        return block("source_figured_metric_plane_underconstrained")
    mapped=tuple(_map(affine,p) for p in source_points)
    max_residual=max(math.dist(x,y) for x,y in zip(mapped,dest_points))
    extent=max(1.,*(abs(v) for p in dest_points for v in p))
    if max_residual>1e-8*extent:
        return block("source_figured_metric_plane_competing_witnesses")
    if not math.isclose(
        abs(affine[0]*affine[4]-affine[1]*affine[3])*source_polygon.area,
        dest_polygon.area,rel_tol=1e-8,abs_tol=1e-6,
    ):
        return block("source_figured_metric_plane_area_conflict")
    return FiguredMetricPlaneShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("source_figured_metric_plane_shadow_only",),
        affine,tuple(parent.source_side_ids),
        parent.source_sha256,parent.revision_id,parent.page_id,
        parent.physical_room_id,max_residual,
    )


def measure_source_internal_sections_on_metric_plane_shadow(
    parent: FiguredPolygonMetricShadow,
    plane: FiguredMetricPlaneShadow,
    sections: Sequence[OriginalInternalSourceSection],
) -> FiguredMappedSectionsShadow:
    def block(reason):
        return FiguredMappedSectionsShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),(),None,(),
        )
    if (
        type(parent) is not FiguredPolygonMetricShadow
        or type(plane) is not FiguredMetricPlaneShadow
        or plane.status is not EvidenceResolutionStatus.CANDIDATE
        or plane.diagnostic_only is not True
        or plane.pdf_to_metric_affine is None
        or (plane.original_parent_source_sha256,plane.original_revision_id,
            plane.original_page_id,plane.original_physical_room_id)
           != (parent.source_sha256,parent.revision_id,parent.page_id,
               parent.physical_room_id)
        or plane.original_parent_source_side_ids!=parent.source_side_ids
        or type(sections) not in (tuple,list)
        or not sections
    ):
        return block("source_figured_metric_plane_lineage_conflict")
    physical=_safe_ring(parent.source_vertices_pdf_pts)
    metric=_safe_ring(parent.metric_vertices_mm)
    if physical is None or metric is None:
        return block("source_figured_metric_parent_geometry_unavailable")
    source_outer=physical[1];metric_outer=metric[1]
    selected = []
    measured = []
    section_ids=set();original_ink_ids=set();mark_ids=set()
    for row in sections:
        if type(row) is not OriginalInternalSourceSection:
            return block("source_metric_section_record_untrusted")
        if (
            type(row.source_section_id) is not str
            or not row.source_section_id or row.source_section_id in section_ids
            or type(row.source_section_boundary_ids) not in (tuple,list)
            or not row.source_section_boundary_ids
            or type(row.source_section_mark_receipts) not in (tuple,list)
            or not row.source_section_mark_receipts
            or any(type(k) is not str or not k for k in (
                *row.source_section_boundary_ids,*row.source_section_mark_receipts
            ))
            or len(set(row.source_section_mark_receipts))!=len(row.source_section_mark_receipts)
            or mark_ids.intersection(row.source_section_mark_receipts)
        ):
            return block("source_metric_section_original_ownership_conflict")
        original=_safe_ring(row.source_pdf_ring)
        if original is None or not source_outer.covers(original[1]):
            return block("source_metric_section_outside_measured_parent")
        if any(original[1].intersection(other).area>1e-9 for other in selected):
            return block("source_metric_section_original_overlap")
        mm=tuple(_map(plane.pdf_to_metric_affine,p) for p in original[0])
        mapped=_safe_ring(mm)
        if mapped is None or not metric_outer.covers(mapped[1]):
            return block("source_metric_section_mapped_polygon_unavailable")
        selected.append(original[1])
        section_ids.add(row.source_section_id)
        mark_ids.update(row.source_section_mark_receipts)
        measured.append((row.source_section_id,mapped[1].area/1e6))
    total=math.fsum(x for _,x in measured)
    residual=parent.candidate_area_m2-total
    if not math.isfinite(residual) or residual<-1e-8*max(1.,parent.candidate_area_m2):
        return block("source_metric_section_derived_area_overflow")
    return FiguredMappedSectionsShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("source_figured_internal_sections_shadow_only",),
        tuple(sorted(measured)),max(0.,residual),tuple(sorted(section_ids)),
    )
