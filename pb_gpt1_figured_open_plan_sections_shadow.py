"""Source-figured sections inside ONE open-plan physical room, not new rooms.

Each section has a separately authenticated sectional boundary and metric
polygon. Shared divider lines are counted once. This never invents walls from
semantic labels such as FOOD SERVICE or POS COUNTER.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from shapely.geometry import Polygon

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalOpenPlanSection:
    source_section_id: str
    enclosing_physical_room_id: str
    original_pdf_ring: tuple[tuple[float, float], ...]
    metric_candidate: FiguredPolygonMetricShadow
    source_boundary_ids: tuple[str, ...]
    source_section_mark_receipts: tuple[str, ...]


@dataclass(frozen=True)
class FiguredOpenPlanSectionTakeoff:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_section_areas_m2: tuple[tuple[str, float], ...]
    candidate_unallocated_area_m2: float | None
    candidate_shared_divider_length_m: float | None
    shared_source_divider_ids: tuple[str, ...]
    diagnostic_only: bool = True


def partition_figured_open_plan_sections_shadow(
    room: FiguredPolygonMetricShadow,
    original_room_pdf_ring: tuple[tuple[float, float], ...],
    sections: tuple[OriginalOpenPlanSection, ...],
) -> FiguredOpenPlanSectionTakeoff:
    def block(reason: str):
        return FiguredOpenPlanSectionTakeoff(
            EvidenceResolutionStatus.ABSTAINED, (reason,), (), None, None, ()
        )
    if (type(room) is not FiguredPolygonMetricShadow
            or room.status is not EvidenceResolutionStatus.CANDIDATE
            or room.candidate_area_m2 is None
            or type(sections) not in (tuple, list) or not sections):
        return block("original_open_plan_source_room_unmeasured")

    def polygon(vertices):
        if type(vertices) not in (tuple, list) or len(vertices) < 3:
            return None
        result = []
        for p in vertices:
            if type(p) not in (list, tuple) or len(p) != 2:
                return None
            if any(type(x) not in (int, float) for x in p):
                return None
            try:
                xy = (float(p[0]), float(p[1]))
            except (ValueError, TypeError, OverflowError):
                return None
            if not all(math.isfinite(x) for x in xy):
                return None
            result.append(xy)
        if result[-1] == result[0]:
            result.pop()
        if len(result) < 3 or len(set(result)) != len(result):
            return None
        shape = Polygon(result)
        return shape if shape.is_valid and shape.area > 0 else None

    outer = polygon(original_room_pdf_ring)
    if outer is None:
        return block("original_open_plan_source_room_unclosed")
    shapes = []
    section_ids = set()
    mark_ids = set()
    boundary_members: dict[str, list[tuple[str, float]]] = {}
    areas = []
    for section in sections:
        if type(section) is not OriginalOpenPlanSection:
            return block("original_open_plan_section_record_untrusted")
        metric = section.metric_candidate
        if (
            type(section.source_section_id) is not str or not section.source_section_id
            or section.source_section_id in section_ids
            or section.enclosing_physical_room_id != room.physical_room_id
            or type(metric) is not FiguredPolygonMetricShadow
            or metric.status is not EvidenceResolutionStatus.CANDIDATE
            or metric.candidate_area_m2 is None
            or (metric.source_sha256, metric.revision_id, metric.page_id,
                metric.physical_room_id)
            != (room.source_sha256, room.revision_id, room.page_id, room.physical_room_id)
            or type(section.source_boundary_ids) not in (tuple, list)
            or len(section.source_boundary_ids) != len(metric.metric_vertices_mm)
            or len(set(section.source_boundary_ids)) != len(section.source_boundary_ids)
            or any(type(i) is not str or not i for i in section.source_boundary_ids)
            or type(section.source_section_mark_receipts) not in (tuple, list)
            or not section.source_section_mark_receipts
            or any(type(i) is not str or not i for i in section.source_section_mark_receipts)
            or mark_ids.intersection(section.source_section_mark_receipts)
        ):
            return block("original_open_plan_section_source_proof_incomplete")
        ink = polygon(section.original_pdf_ring)
        if ink is None or not outer.covers(ink):
            return block("original_open_plan_section_not_inside_parent")
        if any(ink.intersection(existing).area > 1e-9 for existing in shapes):
            return block("original_open_plan_sections_overlap")
        shapes.append(ink)
        mark_ids.update(section.source_section_mark_receipts)
        section_ids.add(section.source_section_id)
        areas.append((section.source_section_id, metric.candidate_area_m2))
        metric_points = metric.metric_vertices_mm
        for i, boundary_id in enumerate(section.source_boundary_ids):
            length = math.dist(
                metric_points[i], metric_points[(i+1)%len(metric_points)]
            )
            if not math.isfinite(length) or length <= 0:
                return block("original_open_plan_divider_metric_invalid")
            boundary_members.setdefault(boundary_id, []).append(
                (section.source_section_id, length)
            )
    shared = {}
    for key, members in boundary_members.items():
        if len(members) > 2:
            return block("original_open_plan_divider_multiple_physical_owners")
        if len(members) == 2:
            if members[0][0] == members[1][0] or not math.isclose(
                members[0][1], members[1][1], rel_tol=1e-10, abs_tol=1e-6
            ):
                return block("original_open_plan_divider_conflicting_measures")
            shared[key] = members[0][1]
    summed = math.fsum(a for _, a in areas)
    remainder = room.candidate_area_m2 - summed
    if not math.isfinite(remainder) or remainder < -1e-8:
        return block("original_open_plan_sections_exceed_room")
    return FiguredOpenPlanSectionTakeoff(
        EvidenceResolutionStatus.CANDIDATE,
        ("source_figured_open_plan_sections_shadow_only",),
        tuple(sorted(areas)), max(0.0, remainder),
        math.fsum(shared.values()) / 1000.0, tuple(sorted(shared)),
    )
