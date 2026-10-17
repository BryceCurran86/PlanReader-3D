"""Independently marked interior floor/ceiling sections after exact wall-frame join.

A printed finish mark on the SECOND original sheet can only claim a SECTION
within a figured parent physical room when the structural wall frame has
already been independently resolved and the original mark polygon is INSIDE
that exact section. One physical room may have several distinct finish codes.
No source mark identity, original wall face or metric scale is invented.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from collections import defaultdict
from shapely.geometry import Polygon

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_gpt1_figured_metric_plane_shadow import (
    FiguredMetricPlaneShadow,OriginalInternalSourceSection,
    measure_source_internal_sections_on_metric_plane_shadow,
)
from pb_gpt1_original_two_view_wall_frame_shadow import SourceWallRingFrameShadow
from pb_gpt1_original_crosssheet_finish_binding_shadow import (
    PhysicalFloorFinishCorrespondenceShadow,AuthenticatedFloorFinishPlanMark,
)
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalSourceMarkedSectionsShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    measured_section_material_m2: tuple[tuple[str,str,str,float],...]
    measured_material_totals_m2: tuple[tuple[str,float],...]
    unallocated_parent_area_m2: float | None
    exact_occurrence_ids: tuple[str,...]
    diagnostic_only: bool = True


def measure_original_crosssheet_marked_sections_shadow(
    parent: FiguredPolygonMetricShadow,
    source_metric_plane: FiguredMetricPlaneShadow,
    original_sections: tuple[OriginalInternalSourceSection,...],
    physical_wall_frame: SourceWallRingFrameShadow,
    physical_floor: PhysicalFloorFinishCorrespondenceShadow,
    original_finish_marks: tuple[AuthenticatedFloorFinishPlanMark,...],
) -> OriginalSourceMarkedSectionsShadow:
    """Only original source-closed finish marks within one physical zone."""
    def block(reason):
        return OriginalSourceMarkedSectionsShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),(),(),None,()
        )
    partition=measure_source_internal_sections_on_metric_plane_shadow(
        parent,source_metric_plane,original_sections)
    if (
        partition.status is not EvidenceResolutionStatus.CANDIDATE
        or type(physical_wall_frame) is not SourceWallRingFrameShadow
        or physical_wall_frame.status is not EvidenceResolutionStatus.CANDIDATE
        or physical_wall_frame.original_finish_to_room_rigid_transform is None
        or type(physical_floor) is not PhysicalFloorFinishCorrespondenceShadow
        or physical_floor.status is not EvidenceResolutionStatus.CANDIDATE
        or (physical_floor.source_sha256,physical_floor.revision_id,
            physical_floor.physical_room_id)
           != (parent.source_sha256,parent.revision_id,parent.physical_room_id)
        or tuple(sorted(physical_wall_frame.matched_wall_equivalence_receipts))
           != tuple(sorted(physical_floor.wall_equivalence_receipts))
        or type(original_finish_marks) not in (tuple,list)
    ):
        return block("original_source_marked_section_crosssheet_scope_unavailable")
    cos,sin,tx,ty=physical_wall_frame.original_finish_to_room_rigid_transform
    def transfer(p):
        x,y=p
        return (cos*x-sin*y+tx,sin*x+cos*y+ty)
    sections={}
    for section in original_sections:
        if type(section) is not OriginalInternalSourceSection:
            return block("original_source_marked_section_record_untrusted")
        geometry=Polygon(section.source_pdf_ring)
        if not geometry.is_valid or geometry.area<=0:
            return block("original_source_marked_section_geometry_invalid")
        sections[section.source_section_id]=geometry
    if set(sections)!=set(partition.source_section_ids):
        return block("original_source_marked_section_scope_missing")
    measured=dict(partition.measured_section_areas_m2)
    mark_by_section={}
    seen_occurrences=set()
    for mark in original_finish_marks:
        if type(mark) is not AuthenticatedFloorFinishPlanMark:
            return block("original_source_marked_section_occurrence_untrusted")
        if (
            mark.source_occurrence_id in seen_occurrences
            or not mark.source_occurrence_id
            or not mark.original_glyph_paint_receipt_id
            or not mark.original_clip_receipt_id
            or mark.original_glyph_paint_receipt_id==mark.original_clip_receipt_id
            or (mark.source_sha256,mark.revision_id,mark.page_id)
               != (parent.source_sha256,parent.revision_id,
                   physical_floor.original_finish_page_id)
            or not mark.is_original_plan_occurrence
            or not mark.source_material_code or not mark.source_definition_id
        ):
            return block("original_source_marked_section_occurrence_scope_conflict")
        seen_occurrences.add(mark.source_occurrence_id)
        try:
            x0,y0,x1,y1=tuple(float(v) for v in mark.source_plan_bbox_pts)
        except (TypeError,ValueError,OverflowError):
            return block("original_source_marked_section_original_bbox_invalid")
        if not all(math.isfinite(v) for v in (x0,y0,x1,y1)) or x1<=x0 or y1<=y0:
            return block("original_source_marked_section_original_bbox_invalid")
        rect=Polygon(tuple(transfer(p) for p in (
            (x0,y0),(x1,y0),(x1,y1),(x0,y1)
        )))
        owners=[id for id,shape in sections.items() if shape.contains(rect)]
        if len(owners)!=1:
            return block("original_source_marked_section_mark_unowned_or_competing")
        section_id=owners[0]
        if section_id in mark_by_section:
            return block("original_source_marked_section_multiple_finish_marks")
        mark_by_section[section_id]=mark
    if set(mark_by_section)!=set(sections):
        return block("original_source_marked_section_finish_unassigned")
    rows=[]
    grouped=defaultdict(float)
    for section_id in sorted(sections):
        mark=mark_by_section[section_id]
        area=measured[section_id]
        grouped[mark.source_material_code]+=area
        rows.append((
            section_id,mark.source_material_code,
            mark.source_occurrence_id,area
        ))
    return OriginalSourceMarkedSectionsShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_marked_source_sections_shadow_only",),
        tuple(rows),tuple(sorted(grouped.items())),
        partition.remaining_unallocated_room_area_m2,
        tuple(sorted(seen_occurrences)),
    )
