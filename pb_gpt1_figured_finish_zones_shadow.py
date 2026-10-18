"""CANDIDATE floor/ceiling finish quantities from independent figured zones.

The same original finish occurrence cannot be recycled across competing
physical zones; material definitions and occurrence provenance are inputs from
an independent source/material binder. This does not grant source authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence
from shapely.geometry import Polygon

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalFiguredFinishZone:
    physical_zone_id: str
    original_zone_pdf_ring: tuple[tuple[float, float], ...]
    measured_zone: FiguredPolygonMetricShadow
    material_code: str
    semantic_finish: str
    source_definition_id: str
    source_occurrence_id: str
    source_material_evidence_ids: tuple[str, ...]
    support_page_id: str
    source_registration_receipt_id: str


@dataclass(frozen=True)
class FiguredFinishZoneTakeoffShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_finish_areas_m2: tuple[tuple[str, str, float], ...]
    candidate_remaining_unassigned_m2: float | None
    physical_zone_ids: tuple[str, ...]
    source_occurrence_ids: tuple[str, ...]
    diagnostic_only: bool = True


def _ring_polygon(points: object):
    if type(points) not in (list, tuple) or len(points) < 3:
        return None
    safe = []
    for xy in points:
        if type(xy) not in (list, tuple) or len(xy) != 2:
            return None
        if any(type(v) not in (int, float) for v in xy):
            return None
        try:
            pair = (float(xy[0]), float(xy[1]))
        except (TypeError, ValueError, OverflowError):
            return None
        if not all(math.isfinite(v) for v in pair):
            return None
        safe.append(pair)
    if len(safe) > 1 and safe[0] == safe[-1]:
        safe.pop()
    if len(safe) < 3 or len(set(safe)) != len(safe):
        return None
    try:
        poly = Polygon(safe)
        return poly if poly.is_valid and poly.area > 0 else None
    except (ValueError, OverflowError):
        return None


def measure_figured_finish_zones_shadow(
    enclosing_room: FiguredPolygonMetricShadow,
    enclosing_original_pdf_ring: Sequence[tuple[float, float]],
    finish_zones: Sequence[OriginalFiguredFinishZone],
    *,
    require_complete_finish_coverage: bool = False,
) -> FiguredFinishZoneTakeoffShadow:
    """Measure non-overlapping, source-owned distinct finish zones.

    Partial coverage is retained as explicitly UNASSIGNED instead of assigning
    the remainder to the first/nearest finish or treating open-plan sections as
    physical rooms. No material-specific quantity is commercially published.
    """
    def block(reason):
        return FiguredFinishZoneTakeoffShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,), (), None, (), ()
        )
    if (
        type(enclosing_room) is not FiguredPolygonMetricShadow
        or enclosing_room.status is not EvidenceResolutionStatus.CANDIDATE
        or enclosing_room.diagnostic_only is not True
        or type(enclosing_room.candidate_area_m2) is not float
        or not math.isfinite(enclosing_room.candidate_area_m2)
        or enclosing_room.candidate_area_m2 <= 0
    ):
        return block("figured_finish_parent_metric_unavailable")
    if type(finish_zones) not in (tuple, list) or not finish_zones:
        return block("figured_finish_zone_unavailable")
    parent = _ring_polygon(enclosing_original_pdf_ring)
    if parent is None:
        return block("figured_finish_parent_source_ring_unavailable")
    seen_physical, seen_occurrence, used_evidence = set(), set(), set()
    measured_rows, physicals, occurrences, shapes = [], [], [], []
    for row in finish_zones:
        if type(row) is not OriginalFiguredFinishZone:
            return block("figured_finish_source_record_invalid")
        data = (
            row.physical_zone_id, row.material_code, row.semantic_finish,
            row.source_definition_id, row.source_occurrence_id,
            row.support_page_id, row.source_registration_receipt_id,
        )
        if (
            any(type(s) is not str or not s or s != s.strip() for s in data)
            or row.physical_zone_id in seen_physical
            or row.source_occurrence_id in seen_occurrence
            or type(row.source_material_evidence_ids) not in (tuple, list)
            or not row.source_material_evidence_ids
            or any(type(x) is not str or not x or x != x.strip()
                   for x in row.source_material_evidence_ids)
            or used_evidence.intersection(row.source_material_evidence_ids)
            or len(set(row.source_material_evidence_ids)) != len(row.source_material_evidence_ids)
        ):
            return block("figured_finish_original_material_identity_conflict")
        metric = row.measured_zone
        if (type(metric) is not FiguredPolygonMetricShadow
                or metric.status is not EvidenceResolutionStatus.CANDIDATE
                or metric.diagnostic_only is not True
                or metric.candidate_area_m2 is None
                or not math.isfinite(metric.candidate_area_m2)
                or metric.candidate_area_m2 <= 0
                or (metric.source_sha256, metric.revision_id, metric.page_id,
                    metric.physical_room_id)
                != (enclosing_room.source_sha256, enclosing_room.revision_id,
                    enclosing_room.page_id, enclosing_room.physical_room_id)):
            return block("figured_finish_source_metric_lineage_conflict")
        polygon = _ring_polygon(row.original_zone_pdf_ring)
        if polygon is None or not parent.covers(polygon):
            return block("figured_finish_zone_not_owned_by_room")
        # Shared boundaries are expected for adjoining tile/finish zones.
        if any(polygon.intersection(previous).area > 1e-9
               for previous in shapes):
            return block("figured_finish_original_zones_overlap")
        shapes.append(polygon)
        seen_physical.add(row.physical_zone_id)
        seen_occurrence.add(row.source_occurrence_id)
        used_evidence.update(row.source_material_evidence_ids)
        physicals.append(row.physical_zone_id)
        occurrences.append(row.source_occurrence_id)
        measured_rows.append((
            row.physical_zone_id, row.material_code, metric.candidate_area_m2
        ))
    total = math.fsum(r[2] for r in measured_rows)
    residual = enclosing_room.candidate_area_m2 - total
    if not math.isfinite(residual) or residual < -1e-8 * max(1., enclosing_room.candidate_area_m2):
        return block("figured_finish_total_exceeds_source_room")
    if require_complete_finish_coverage and abs(residual) > 1e-8 * max(1., total):
        return block("figured_finish_physical_zone_coverage_incomplete")
    return FiguredFinishZoneTakeoffShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("figured_source_finish_zones_shadow_only",),
        tuple(sorted(measured_rows)), max(0., residual),
        tuple(sorted(physicals)), tuple(sorted(occurrences)),
    )
