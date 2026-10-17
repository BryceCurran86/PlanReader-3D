"""Source-figured suspended ceiling grid layout takeoff — shadow only.

Requires an independently figured canonical ceiling polygon and exact
source-backed grid module pitch, origin and bearing axis. No industry-default
600x600, decorative grid inference or ceiling material promotion.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from shapely.geometry import LineString, Polygon, box
from shapely.affinity import rotate

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class DocumentedCeilingGridSystem:
    physical_ceiling_surface_id: str
    grid_origin_metric_mm: tuple[float, float]
    module_width_mm: float
    module_height_mm: float
    grid_rotation_degrees: float
    source_grid_module_evidence_ids: tuple[str, ...]
    source_grid_origin_evidence_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str


@dataclass(frozen=True)
class FiguredCeilingGridTakeoffShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    full_panel_count_candidate: int | None
    cut_panel_count_candidate: int | None
    total_panel_count_candidate: int | None
    coverage_area_m2: float | None
    grid_tee_length_m_by_axis: tuple[float, float] | None
    source_grid_evidence_ids: tuple[str, ...]
    diagnostic_only: bool = True


def _finite(value: object, *, positive: bool = False) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(number) or (positive and number <= 0):
        return None
    return number


def measure_source_figured_ceiling_grid_shadow(
    ceiling: FiguredPolygonMetricShadow,
    layout: DocumentedCeilingGridSystem,
) -> FiguredCeilingGridTakeoffShadow:
    """Tessellate physically bounded ceiling metric polygon by sourced grid.

    Cut-panel counts are individual cells intersecting the ceiling, not an
    ordering forecast or waste allowance. A non-grid ceiling receives no result.
    """
    def block(reason):
        return FiguredCeilingGridTakeoffShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,),
            None, None, None, None, None, ()
        )
    if (type(ceiling) is not FiguredPolygonMetricShadow
            or ceiling.status is not EvidenceResolutionStatus.CANDIDATE
            or ceiling.diagnostic_only is not True
            or not ceiling.metric_vertices_mm):
        return block("original_ceiling_metric_footprint_unavailable")
    if type(layout) is not DocumentedCeilingGridSystem:
        return block("original_ceiling_grid_system_untrusted")
    if (
        (layout.source_sha256, layout.revision_id, layout.page_id)
        != (ceiling.source_sha256, ceiling.revision_id, ceiling.page_id)
        or type(layout.physical_ceiling_surface_id) is not str
        or not layout.physical_ceiling_surface_id
        or type(layout.grid_origin_metric_mm) not in (tuple, list)
        or len(layout.grid_origin_metric_mm) != 2
        or any(_finite(n) is None for n in layout.grid_origin_metric_mm)
        or _finite(layout.module_width_mm, positive=True) is None
        or _finite(layout.module_height_mm, positive=True) is None
        or _finite(layout.grid_rotation_degrees) is None
        or type(layout.source_grid_module_evidence_ids) not in (tuple, list)
        or type(layout.source_grid_origin_evidence_ids) not in (tuple, list)
        or not layout.source_grid_module_evidence_ids
        or not layout.source_grid_origin_evidence_ids
    ):
        return block("original_ceiling_grid_source_authority_unavailable")
    ids = tuple(layout.source_grid_module_evidence_ids) + tuple(
        layout.source_grid_origin_evidence_ids
    )
    if (
        any(type(n) is not str or not n or n != n.strip() for n in ids)
        or len(ids) != len(set(ids))
    ):
        return block("original_ceiling_grid_source_identity_conflict")
    try:
        original = Polygon(ceiling.metric_vertices_mm)
        if not original.is_valid or original.area <= 0:
            return block("original_ceiling_grid_physical_polygon_invalid")
        origin = tuple(map(float, layout.grid_origin_metric_mm))
        local = rotate(original, -layout.grid_rotation_degrees, origin=origin)
        dx, dy = float(layout.module_width_mm), float(layout.module_height_mm)
        x0, y0, x1, y1 = local.bounds
        ix0 = math.floor((x0-origin[0])/dx)
        ix1 = math.ceil((x1-origin[0])/dx)
        iy0 = math.floor((y0-origin[1])/dy)
        iy1 = math.ceil((y1-origin[1])/dy)
        count = (ix1-ix0)*(iy1-iy0)
        # A broken/caller-inflated grid pitch would create unbounded work.
        if count <= 0 or count > 20000:
            return block("original_ceiling_grid_layout_unbounded")
        full, cut = 0, 0
        area = 0.0
        for ix in range(ix0, ix1):
            for iy in range(iy0, iy1):
                cell = box(origin[0]+ix*dx, origin[1]+iy*dy,
                           origin[0]+(ix+1)*dx, origin[1]+(iy+1)*dy)
                interior = cell.intersection(local)
                if interior.area <= 1e-9:
                    continue
                area += interior.area
                if cell.difference(local).area <= 1e-8 * dx * dy:
                    full += 1
                else:
                    cut += 1
        axis_lengths = []
        for axis in (0, 1):
            total_length = 0.0
            if axis == 0:
                coords = (origin[0]+ix*dx for ix in range(ix0, ix1+1))
                edges = (LineString([(x, y0-1), (x, y1+1)]) for x in coords)
            else:
                coords = (origin[1]+iy*dy for iy in range(iy0, iy1+1))
                edges = (LineString([(x0-1, y), (x1+1, y)]) for y in coords)
            for line in edges:
                total_length += line.intersection(local).length
            axis_lengths.append(total_length / 1000.0)
        if (
            not math.isclose(area, local.area, rel_tol=1e-8, abs_tol=1e-4)
            or not math.isclose(area / 1e6, ceiling.candidate_area_m2,
                             rel_tol=1e-8, abs_tol=1e-8)
        ):
            return block("original_ceiling_grid_metric_coverage_conflict")
        return FiguredCeilingGridTakeoffShadow(
            EvidenceResolutionStatus.CANDIDATE,
            ("figured_source_ceiling_grid_shadow_only",),
            full, cut, full+cut, area / 1e6,
            tuple(axis_lengths), tuple(sorted(ids)),
        )
    except (ValueError, TypeError, OverflowError):
        return block("original_ceiling_grid_geometry_unrepresentable")
