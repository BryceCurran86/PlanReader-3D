"""Shadow net room-zone area from original source-owned figured perimeter voids.

A hole has to be independently source authenticated and its PDF native ring
fully contained within the one physical enclosing source ring. The resulting
m² remains a candidate: it never grants ceiling, floor, material or quantity
authority and never infers any missing dimension or page scale.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class SourceFiguredAreaVoid:
    physical_void_id: str
    figured_metric: FiguredPolygonMetricShadow
    source_pdf_ring: tuple[tuple[float, float], ...]
    source_void_boundary_evidence_ids: tuple[str, ...]


@dataclass(frozen=True)
class FiguredZoneNetAreaShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_net_area_m2: float | None
    gross_area_m2: float | None
    separately_measured_void_m2: tuple[tuple[str, float], ...]
    diagnostic_only: bool = True


def source_figured_net_zone_area_shadow(
    gross: FiguredPolygonMetricShadow,
    gross_source_pdf_ring: Sequence[tuple[float, float]],
    voids: Sequence[SourceFiguredAreaVoid],
) -> FiguredZoneNetAreaShadow:
    """Subtract only independently figured, physically contained source voids."""
    def block(reason: str) -> FiguredZoneNetAreaShadow:
        return FiguredZoneNetAreaShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,),
            None, None, (),
        )

    if (
        type(gross) is not FiguredPolygonMetricShadow
        or gross.status is not EvidenceResolutionStatus.CANDIDATE
        or gross.diagnostic_only is not True
        or type(gross.candidate_area_m2) is not float
        or not math.isfinite(gross.candidate_area_m2)
        or gross.candidate_area_m2 <= 0
    ):
        return block("figured_original_outer_metric_unavailable")
    if type(voids) not in (tuple, list):
        return block("figured_source_void_universe_unavailable")

    from shapely.geometry import Polygon

    def ring_polygon(raw: object):
        if type(raw) not in (tuple, list) or len(raw) < 3:
            return None
        points = []
        for value in raw:
            if (
                type(value) not in (tuple, list) or len(value) != 2
                or any(type(v) not in (int, float) for v in value)
            ):
                return None
            try:
                point = (float(value[0]), float(value[1]))
            except (TypeError, ValueError, OverflowError):
                return None
            if not all(math.isfinite(v) for v in point):
                return None
            points.append(point)
        if len(points) > 1 and points[0] == points[-1]:
            points.pop()
        if len(points) < 3 or len(set(points)) != len(points):
            return None
        try:
            polygon = Polygon(points)
            return polygon if polygon.is_valid and polygon.area > 0 else None
        except (ValueError, OverflowError):
            return None

    parent = ring_polygon(gross_source_pdf_ring)
    if parent is None:
        return block("figured_original_outer_ring_unclosed")

    holes = []
    physical_ids = set()
    source_receipt_ids = set()
    areas = []
    for void in voids:
        if type(void) is not SourceFiguredAreaVoid:
            return block("figured_source_void_record_untrusted")
        if (
            type(void.physical_void_id) is not str or not void.physical_void_id
            or void.physical_void_id in physical_ids
            or type(void.source_void_boundary_evidence_ids) not in (tuple, list)
            or len(void.source_void_boundary_evidence_ids) < 1
            or any(type(v) is not str or not v for v in void.source_void_boundary_evidence_ids)
            or source_receipt_ids.intersection(void.source_void_boundary_evidence_ids)
        ):
            return block("figured_source_void_identity_conflict")
        physical_ids.add(void.physical_void_id)
        source_receipt_ids.update(void.source_void_boundary_evidence_ids)
        measured = void.figured_metric
        if (
            type(measured) is not FiguredPolygonMetricShadow
            or measured.status is not EvidenceResolutionStatus.CANDIDATE
            or measured.source_sha256 != gross.source_sha256
            or measured.revision_id != gross.revision_id
            or measured.page_id != gross.page_id
            or measured.physical_room_id != gross.physical_room_id
            or measured.candidate_area_m2 is None
        ):
            return block("figured_source_void_metric_lineage_conflict")
        child = ring_polygon(void.source_pdf_ring)
        if child is None or not parent.contains(child):
            return block("figured_source_void_not_inside_original_room")
        if any(child.intersects(old) for old in holes):
            return block("figured_source_voids_overlap")
        holes.append(child)
        areas.append((void.physical_void_id, measured.candidate_area_m2))

    net = gross.candidate_area_m2 - math.fsum(area for _, area in areas)
    if not math.isfinite(net) or net <= 0:
        return block("figured_source_void_area_exceeds_room")
    return FiguredZoneNetAreaShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("figured_source_void_net_shadow_only",),
        net, gross.candidate_area_m2,
        tuple(sorted(areas)),
    )
