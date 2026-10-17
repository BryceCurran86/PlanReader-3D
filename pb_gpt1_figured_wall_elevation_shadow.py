"""Source-figured nonrectangular wall elevations and their true lining area.

A trapezoidal/stepped/gable wall face needs a complete sequence of source-owned
horizontal stations and independently figured heights. A height guessed from
wall style or nominal floor-to-ceiling spacing is not accepted. Shadow only.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class SourceFiguredElevationStation:
    longitudinal_mm: float
    vertical_height_mm: float
    longitudinal_figure_id: str
    height_figure_id: str
    original_witness_ids: tuple[str, ...]


@dataclass(frozen=True)
class FiguredWallElevationAreaShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_face_area_m2: float | None
    candidate_upper_edge_length_m: float | None
    original_station_ids: tuple[str, ...]
    diagnostic_only: bool = True


def measure_source_figured_wall_elevation_shadow(
    *,
    physical_wall_id: str,
    figured_wall_length_mm: float,
    source_wall_length_figure_id: str,
    source_sha256: str,
    revision_id: str,
    page_id: str,
    stations: tuple[SourceFiguredElevationStation, ...],
) -> FiguredWallElevationAreaShadow:
    """Trapezoid integration for source-measured slopes and steps.

    Every station is an authenticated figured elevation endpoint in the same
    original wall object, including both endpoints of the wall run.
    """
    def block(reason):
        return FiguredWallElevationAreaShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,), None, None, ()
        )
    if (
        type(physical_wall_id) is not str or not physical_wall_id
        or type(source_wall_length_figure_id) is not str or not source_wall_length_figure_id
        or type(source_sha256) is not str or len(source_sha256) != 64
        or any(type(t) is not str or not t for t in (revision_id,page_id))
        or type(figured_wall_length_mm) not in (int,float)
        or not math.isfinite(float(figured_wall_length_mm))
        or figured_wall_length_mm <= 0
        or type(stations) not in (tuple,list) or len(stations) < 2
    ):
        return block("original_figured_wall_elevation_scope_invalid")

    used = {source_wall_length_figure_id}
    positions, heights, receipt_ids = [], [], []
    for point in stations:
        if type(point) is not SourceFiguredElevationStation:
            return block("original_figured_wall_elevation_station_untrusted")
        if (type(point.longitudinal_mm) not in (int,float)
                or type(point.vertical_height_mm) not in (int,float)):
            return block("original_figured_wall_elevation_measurement_untyped")
        try:
            x,y = float(point.longitudinal_mm),float(point.vertical_height_mm)
        except (TypeError,ValueError,OverflowError):
            return block("original_figured_wall_elevation_measurement_untyped")
        if not math.isfinite(x) or not math.isfinite(y) or y <= 0:
            return block("original_figured_wall_elevation_measurement_invalid")
        if (type(point.longitudinal_figure_id) is not str
                or not point.longitudinal_figure_id
                or type(point.height_figure_id) is not str
                or not point.height_figure_id
                or type(point.original_witness_ids) not in (tuple,list)
                or len(point.original_witness_ids) < 2
                or any(type(s) is not str or not s for s in point.original_witness_ids)
                or len(set(point.original_witness_ids)) != len(point.original_witness_ids)):
            return block("original_figured_wall_elevation_receipts_incomplete")
        # Adjacent stations may share one original datum but not one height.
        if point.height_figure_id in used:
            return block("original_figured_wall_elevation_height_reused")
        used.add(point.height_figure_id)
        positions.append(x);heights.append(y)
        receipt_ids.extend((point.longitudinal_figure_id,
                            point.height_figure_id,*point.original_witness_ids))
    if (not math.isclose(positions[0],0.,abs_tol=1e-9)
            or not math.isclose(positions[-1], figured_wall_length_mm,
                                rel_tol=1e-10,abs_tol=1e-6)
            or any(b<=a for a,b in zip(positions,positions[1:]))):
        return block("original_figured_wall_elevation_extent_mismatch")
    area=math.fsum(
        (b-a)*(heights[i]+heights[i+1])/2
        for i,(a,b) in enumerate(zip(positions,positions[1:]))
    )/1_000_000
    edge=math.fsum(math.hypot(b-a,heights[i+1]-heights[i])
                   for i,(a,b) in enumerate(zip(positions,positions[1:]))) /1000
    if not math.isfinite(area) or area<=0 or not math.isfinite(edge):
        return block("original_figured_wall_elevation_area_unrepresentable")
    return FiguredWallElevationAreaShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_figured_wall_elevation_shadow_only",),
        area,edge,tuple(sorted(set(receipt_ids)))
    )
