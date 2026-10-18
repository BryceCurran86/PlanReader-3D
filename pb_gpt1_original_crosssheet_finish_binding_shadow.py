"""Exact original two-sheet physical boundary and floor finish association.

This is a SOURCE AUTHORITY INPUT CONTRACT, not an authority issuer. Only a
separate source producer may authenticate structural equivalence, schedule
definition and original paint/clip state. Geometry/labels/translations alone
cannot prove equivalence. Never constructs a FIRM finish quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from shapely.geometry import Polygon, box
from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalTwoSheetBoundaryOwner:
    physical_wall_id: str
    original_room_wall_source_segment_ids: tuple[str,...]
    original_finish_wall_source_segment_ids: tuple[str,...]
    original_wall_equivalence_receipt_id: str
    original_structural_wall_authority: str


@dataclass(frozen=True)
class OriginalPhysicalFloorToFinishScope:
    physical_room_id: str
    canonical_floor_id: str
    source_sha256: str
    revision_id: str
    producer_snapshot_id: str
    decision_scope_id: str
    original_room_page_id: str
    original_finish_page_id: str
    physical_boundary_source_ids: tuple[str,...]
    finish_support_source_ids: tuple[str,...]
    wall_owners: tuple[OriginalTwoSheetBoundaryOwner,...]
    original_finish_room_polygon_pts: tuple[tuple[float,float], ...]
    source_room_face_record_id: str = ""


@dataclass(frozen=True)
class PhysicalFloorFinishCorrespondenceShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    physical_room_id: str
    canonical_floor_id: str
    wall_equivalence_receipts: tuple[str,...]
    finish_support_polygon_pts: tuple[tuple[float,float],...]
    original_finish_page_id: str
    source_sha256: str
    revision_id: str
    producer_snapshot_id: str
    decision_scope_id: str
    diagnostic_only: bool = True
    source_room_face_record_id: str = ""
    original_room_page_id: str = ""


@dataclass(frozen=True)
class AuthenticatedFloorFinishPlanMark:
    source_occurrence_id: str
    source_definition_id: str
    original_glyph_paint_receipt_id: str
    original_clip_receipt_id: str
    source_partition_id: str
    source_material_code: str
    semantic_finish: str
    source_plan_bbox_pts: tuple[float,float,float,float]
    source_sha256: str
    revision_id: str
    page_id: str
    viewport_id: str
    is_original_plan_occurrence: bool


@dataclass(frozen=True)
class PhysicalFloorFinishCandidate:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    original_floor_id: str
    original_occurrence_id: str | None
    original_definition_id: str | None
    original_finish_code: str | None
    candidate_area_m2: float | None
    diagnostic_only: bool = True


def _ids(values):
    return (
        type(values) in (tuple,list) and bool(values)
        and all(type(v) is str and bool(v) and v==v.strip() for v in values)
        and len(set(values))==len(values)
    )


def _safe_polygon(raw):
    if type(raw) not in (tuple,list) or len(raw)<3:
        return None
    out=[]
    for p in raw:
        if type(p) not in (tuple,list) or len(p)!=2:
            return None
        if any(type(v) not in (int,float) for v in p):
            return None
        try:pair=(float(p[0]),float(p[1]))
        except (TypeError,ValueError,OverflowError):return None
        if not all(math.isfinite(v) for v in pair):
            return None
        out.append(pair)
    if len(out)>1 and out[0]==out[-1]:out.pop()
    if len(out)<3 or len(set(out))!=len(out):
        return None
    poly=Polygon(out)
    return poly if poly.is_valid and poly.area>0 else None


def resolve_source_physical_floor_correspondence_shadow(
    metric_room: FiguredPolygonMetricShadow,
    scope: OriginalPhysicalFloorToFinishScope,
) -> PhysicalFloorFinishCorrespondenceShadow:
    """Reject unproven wall equivalence instead of selecting best registration."""
    def block(reason):
        return PhysicalFloorFinishCorrespondenceShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),
            str(getattr(scope,"physical_room_id","")),
            str(getattr(scope,"canonical_floor_id","")),
            (),(),
            str(getattr(scope,"original_finish_page_id","")),
            str(getattr(scope,"source_sha256","")),
            str(getattr(scope,"revision_id","")),
            str(getattr(scope,"producer_snapshot_id","")),
            str(getattr(scope,"decision_scope_id","")),
        )
    if (
        type(metric_room) is not FiguredPolygonMetricShadow
        or metric_room.status is not EvidenceResolutionStatus.CANDIDATE
        or type(scope) is not OriginalPhysicalFloorToFinishScope
        or scope.physical_room_id != metric_room.physical_room_id
        or (scope.source_sha256,scope.revision_id)
           != (metric_room.source_sha256,metric_room.revision_id)
        or not _ids(scope.physical_boundary_source_ids)
        or not _ids(scope.finish_support_source_ids)
        or not _ids((scope.producer_snapshot_id,scope.decision_scope_id))
        or type(scope.canonical_floor_id) is not str or not scope.canonical_floor_id
        or type(scope.source_room_face_record_id) is not str
        or not scope.source_room_face_record_id
        or type(scope.original_room_page_id) is not str
        or scope.original_room_page_id != metric_room.page_id
        or type(scope.original_finish_page_id) is not str
        or not scope.original_finish_page_id
        or scope.original_finish_page_id==metric_room.page_id
    ):
        return block("original_crosssheet_floor_lineage_unavailable")
    polygon=_safe_polygon(scope.original_finish_room_polygon_pts)
    if polygon is None:
        return block("original_crosssheet_finish_room_perimeter_unavailable")
    if (
        type(scope.wall_owners) not in (tuple,list)
        or len(scope.wall_owners)!=len(metric_room.source_side_ids)
        or len(scope.wall_owners)<3
        or not metric_room.source_side_ids
    ):
        return block("original_crosssheet_wall_equivalence_unavailable")
    seen_walls=set();seen_receipts=set();room_segments=set();finish_segments=set()
    for owner in scope.wall_owners:
        if (
            type(owner) is not OriginalTwoSheetBoundaryOwner
            or type(owner.physical_wall_id) is not str
            or not owner.physical_wall_id or owner.physical_wall_id in seen_walls
            or type(owner.original_wall_equivalence_receipt_id) is not str
            or not owner.original_wall_equivalence_receipt_id
            or owner.original_wall_equivalence_receipt_id in seen_receipts
            or owner.original_structural_wall_authority != "source_closed_physical_wall_equivalence"
            or not _ids(owner.original_room_wall_source_segment_ids)
            or not _ids(owner.original_finish_wall_source_segment_ids)
            or room_segments.intersection(owner.original_room_wall_source_segment_ids)
            or finish_segments.intersection(owner.original_finish_wall_source_segment_ids)
        ):
            return block("original_crosssheet_wall_equivalence_conflict")
        seen_walls.add(owner.physical_wall_id)
        seen_receipts.add(owner.original_wall_equivalence_receipt_id)
        room_segments.update(owner.original_room_wall_source_segment_ids)
        finish_segments.update(owner.original_finish_wall_source_segment_ids)
    if room_segments != set(metric_room.source_segment_ids):
        return block("original_crosssheet_floor_wall_source_membership_conflict")
    if room_segments != set(scope.physical_boundary_source_ids):
        return block("original_crosssheet_floor_source_universe_incomplete")
    if finish_segments != set(scope.finish_support_source_ids):
        return block("original_crosssheet_finish_source_universe_incomplete")
    return PhysicalFloorFinishCorrespondenceShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_crosssheet_structural_equivalence_shadow_only",),
        scope.physical_room_id,scope.canonical_floor_id,
        tuple(sorted(seen_receipts)),
        tuple(tuple(p) for p in scope.original_finish_room_polygon_pts),
        scope.original_finish_page_id,scope.source_sha256,
        scope.revision_id,scope.producer_snapshot_id,scope.decision_scope_id,
        source_room_face_record_id=scope.source_room_face_record_id,
        original_room_page_id=scope.original_room_page_id,
    )


def bind_source_finish_mark_to_corresponded_floor_shadow(
    measured: FiguredPolygonMetricShadow,
    correspondence: PhysicalFloorFinishCorrespondenceShadow,
    marks: tuple[AuthenticatedFloorFinishPlanMark,...],
) -> PhysicalFloorFinishCandidate:
    """A unique original in-plan mark plus definition may qualify a candidate.

    Caller-provided mark text alone is never a positive material receipt.
    """
    def block(reason):
        return PhysicalFloorFinishCandidate(
            EvidenceResolutionStatus.ABSTAINED,(reason,),
            str(getattr(correspondence,"canonical_floor_id","")),
            None,None,None,None,
        )
    if (
        type(measured) is not FiguredPolygonMetricShadow
        or measured.status is not EvidenceResolutionStatus.CANDIDATE
        or type(correspondence) is not PhysicalFloorFinishCorrespondenceShadow
        or correspondence.status is not EvidenceResolutionStatus.CANDIDATE
        or (measured.source_sha256,measured.revision_id)
          != (correspondence.source_sha256,correspondence.revision_id)
        or measured.physical_room_id != correspondence.physical_room_id
        or type(marks) not in (list,tuple)
    ):
        return block("original_floor_finish_correspondence_unavailable")
    shape=_safe_polygon(correspondence.finish_support_polygon_pts)
    if shape is None:
        return block("original_floor_finish_support_polygon_invalid")
    candidates=[]
    for mark in marks:
        if type(mark) is not AuthenticatedFloorFinishPlanMark:
            return block("original_floor_finish_plan_mark_untrusted")
        if (
            not mark.is_original_plan_occurrence
            or (mark.source_sha256,mark.revision_id,mark.page_id)
              != (correspondence.source_sha256,correspondence.revision_id,
                  correspondence.original_finish_page_id)
        ):
            continue
        fields=(
            mark.source_occurrence_id,mark.source_definition_id,
            mark.original_glyph_paint_receipt_id,mark.original_clip_receipt_id,
            mark.source_partition_id,mark.source_material_code,mark.semantic_finish,
            mark.viewport_id
        )
        if any(type(v) is not str or not v or v!=v.strip() for v in fields):
            return block("original_floor_finish_occurrence_receipts_incomplete")
        raw=mark.source_plan_bbox_pts
        if type(raw) not in (list,tuple) or len(raw)!=4:
            return block("original_floor_finish_mark_geometry_unavailable")
        try:x0,y0,x1,y1=(float(v) for v in raw)
        except (TypeError,ValueError,OverflowError):
            return block("original_floor_finish_mark_geometry_unavailable")
        if (
            not all(math.isfinite(v) for v in (x0,y0,x1,y1))
            or x1<=x0 or y1<=y0
        ):
            return block("original_floor_finish_mark_geometry_unavailable")
        if shape.contains(box(x0,y0,x1,y1)):
            candidates.append(mark)
    if len(candidates)!=1:
        return block("original_floor_finish_mark_missing_or_competing")
    winner=candidates[0]
    return PhysicalFloorFinishCandidate(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_finish_mark_physical_floor_candidate_only",),
        correspondence.canonical_floor_id,winner.source_occurrence_id,
        winner.source_definition_id,winner.source_material_code,
        measured.candidate_area_m2,
    )
