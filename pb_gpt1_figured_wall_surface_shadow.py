"""Dimensional wall takeoff candidates from one source-figured physical room.

Wall linings, skirting and opening deductions share original physical side
ownership; no finish codes, construction rates, opening count or commercial
quantity authority are fabricated by these calculations. Shadow only.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence

from pb_gpt1_figured_chain_metric_shadow import FiguredPhysicalSide, FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class DocumentedWallHeight:
    source_side_id: str
    height_mm: float
    height_evidence_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str


@dataclass(frozen=True)
class DocumentedWallOpening:
    physical_opening_id: str
    host_source_side_id: str
    opening_width_mm: float
    opening_height_mm: float
    source_opening_area_id: str
    host_binding_evidence_ids: tuple[str, ...]
    physical_frame_evidence_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str
    published_original_opening_area_m2: float | None = None


@dataclass(frozen=True)
class FiguredWallTakeoffShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_perimeter_m: float | None
    candidate_gross_lining_m2: float | None
    candidate_net_lining_m2: float | None
    candidate_opening_deductions_m2: tuple[tuple[str, float], ...]
    candidate_skirting_m: float | None
    original_figured_source_ids: tuple[str, ...]
    diagnostic_only: bool = True


def _number(v: object) -> float | None:
    if type(v) not in (int, float):
        return None
    try:
        f = float(v)
    except (TypeError, ValueError, OverflowError):
        return None
    return f if math.isfinite(f) and f > 0 else None


def _receipts(ids: object) -> bool:
    return (type(ids) in (list, tuple) and len(ids) > 0
            and all(type(x) is str and x and x == x.strip() for x in ids)
            and len(set(ids)) == len(ids))


def _linage_tuple(*items):
    return tuple(items)


def measure_figured_wall_lining_shadow(
    ring: Sequence[FiguredPhysicalSide],
    measured: FiguredPolygonMetricShadow,
    wall_heights: Sequence[DocumentedWallHeight],
    openings: Sequence[DocumentedWallOpening] = (),
) -> FiguredWallTakeoffShadow:
    """Wall side length and height are independently figured; no px-to-mm.

    The physical opening's structural host, full frame and signed area receipt
    must all be supplied from separate producers. This does NOT validate that
    provenance; it refuses inconsistent declarations, then returns CANDIDATE.
    """
    def block(reason: str) -> FiguredWallTakeoffShadow:
        return FiguredWallTakeoffShadow(EvidenceResolutionStatus.ABSTAINED,
                                       (reason,), None, None, None, (), None, ())
    if (type(measured) is not FiguredPolygonMetricShadow
            or measured.status is not EvidenceResolutionStatus.CANDIDATE
            or measured.diagnostic_only is not True
            or type(ring) not in (tuple, list)
            or len(ring) != len(measured.metric_vertices_mm)
            or not ring):
        return block("source_figured_wall_metric_ring_unavailable")
    if (type(wall_heights) not in (tuple, list)
            or type(openings) not in (tuple, list)):
        return block("source_figured_wall_inputs_untrusted")
    if (
        measured.source_side_ids != tuple(side.source_side_id for side in ring)
        or measured.source_segment_ids != tuple(sorted(
            segment for side in ring for segment in side.source_segment_ids
        ))
    ):
        return block("source_figured_wall_side_lineage_mismatch")
    metric_points = measured.metric_vertices_mm
    side_lengths = {}
    for i, side in enumerate(ring):
        if type(side) is not FiguredPhysicalSide:
            return block("source_figured_wall_side_untrusted")
        if side.source_side_id in side_lengths:
            return block("source_figured_wall_side_duplicate")
        first, second = metric_points[i], metric_points[(i+1) % len(metric_points)]
        length = math.dist(first, second)
        if not math.isfinite(length) or length <= 0:
            return block("source_figured_wall_side_unmeasured")
        side_lengths[side.source_side_id] = length
    heights = {}
    all_receipts = set(measured.source_figure_ids)
    for source in wall_heights:
        if (type(source) is not DocumentedWallHeight
                or source.source_side_id not in side_lengths
                or source.source_side_id in heights
                or _number(source.height_mm) is None
                or not _receipts(source.height_evidence_ids)
                or (source.source_sha256, source.revision_id, source.page_id)
                != (measured.source_sha256, measured.revision_id, measured.page_id)):
            return block("source_figured_wall_height_unavailable_or_conflicting")
        if all_receipts.intersection(source.height_evidence_ids):
            return block("source_figured_wall_receipt_alias")
        heights[source.source_side_id] = source.height_mm
        all_receipts.update(source.height_evidence_ids)
    if set(heights) != set(side_lengths):
        return block("source_figured_wall_heights_incomplete")
    perimeter = math.fsum(side_lengths.values()) / 1000.0
    gross = math.fsum(
        length * heights[side_id]
        for side_id, length in side_lengths.items()
    ) / 1_000_000.0
    deductions: list[tuple[str, float]] = []
    opening_ids, opening_source_ids = set(), set()
    side_opening_widths = {side_id: 0.0 for side_id in side_lengths}
    side_opening_areas = {side_id: 0.0 for side_id in side_lengths}
    for opening in openings:
        if (type(opening) is not DocumentedWallOpening
                or type(opening.physical_opening_id) is not str
                or not opening.physical_opening_id
                or opening.physical_opening_id in opening_ids
                or type(opening.source_opening_area_id) is not str
                or not opening.source_opening_area_id
                or opening.source_opening_area_id in opening_source_ids
                or opening.host_source_side_id not in side_lengths
                or _number(opening.opening_width_mm) is None
                or _number(opening.opening_height_mm) is None
                or _number(opening.published_original_opening_area_m2) is None
                or not _receipts(opening.host_binding_evidence_ids)
                or not _receipts(opening.physical_frame_evidence_ids)
                or (opening.source_sha256, opening.revision_id, opening.page_id)
                != (measured.source_sha256, measured.revision_id, measured.page_id)):
            return block("source_figured_wall_opening_identity_unavailable")
        if (opening.opening_height_mm > heights[opening.host_source_side_id]
                or all_receipts.intersection(opening.host_binding_evidence_ids)
                or all_receipts.intersection(opening.physical_frame_evidence_ids)
                or set(opening.host_binding_evidence_ids).intersection(
                    opening.physical_frame_evidence_ids)):
            return block("source_figured_wall_opening_frame_or_height_conflict")
        all_receipts.update(opening.host_binding_evidence_ids)
        all_receipts.update(opening.physical_frame_evidence_ids)
        opening_ids.add(opening.physical_opening_id)
        opening_source_ids.add(opening.source_opening_area_id)
        side_opening_widths[opening.host_source_side_id] += opening.opening_width_mm
        area = (opening.opening_width_mm * opening.opening_height_mm) / 1_000_000.0
        if not math.isclose(
            area, opening.published_original_opening_area_m2,
            rel_tol=0.0, abs_tol=1e-9
        ):
            return block("source_figured_wall_opening_signed_area_conflict")
        side_opening_areas[opening.host_source_side_id] += area
        deductions.append((opening.physical_opening_id, area))
    if any(side_opening_widths[k] > side_lengths[k] + 1e-9
           or side_opening_areas[k] > side_lengths[k] * heights[k] / 1_000_000.0 + 1e-9
           for k in side_lengths):
        return block("source_figured_wall_openings_exceed_physical_host")
    net = gross - math.fsum(area for _, area in deductions)
    skirting = perimeter - math.fsum(side_opening_widths.values()) / 1000.0
    if not all(math.isfinite(x) for x in (gross, net, skirting)) or net <= 0 or skirting < 0:
        return block("source_figured_wall_net_surface_unavailable")
    return FiguredWallTakeoffShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("source_figured_wall_surface_shadow_only",),
        perimeter, gross, net, tuple(sorted(deductions)), skirting,
        tuple(sorted(all_receipts)),
    )
