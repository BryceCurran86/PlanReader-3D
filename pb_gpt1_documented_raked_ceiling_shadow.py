"""Optional documented raked-ceiling area from a figured physical footprint.

Computes a genuine geometrical surface area only when a source-owned pitch
record and a separately figured flat footprint are both present. This remains
a CANDIDATE shadow, not a finish or commercial quantity authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_gpt1_figured_chain_metric_shadow import FiguredPolygonMetricShadow
from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class DocumentedSourceCeilingPitch:
    physical_ceiling_surface_id: str
    source_pitch_evidence_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str
    slope_degrees: float | None = None
    documented_rise_mm: float | None = None
    documented_run_mm: float | None = None


@dataclass(frozen=True)
class FiguredSlopedSurfaceAreaShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_surface_m2: float | None
    original_plan_area_m2: float | None
    resolved_pitch_degrees: float | None
    physical_ceiling_surface_id: str
    original_pitch_evidence_ids: tuple[str, ...]
    diagnostic_only: bool = True


def _float(value: object) -> float | None:
    if type(value) not in (float, int):
        return None
    try:
        val = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return val if math.isfinite(val) else None


def measure_figured_raked_ceiling_shadow(
    footprint: FiguredPolygonMetricShadow,
    pitch: DocumentedSourceCeilingPitch,
) -> FiguredSlopedSurfaceAreaShadow:
    """Calculate inclined planar surface / horizontal documented footprint."""
    def block(reason: str) -> FiguredSlopedSurfaceAreaShadow:
        return FiguredSlopedSurfaceAreaShadow(
            EvidenceResolutionStatus.ABSTAINED, (reason,),
            None, None, None,
            str(getattr(pitch, "physical_ceiling_surface_id", "")),
            (),
        )
    if (
        type(footprint) is not FiguredPolygonMetricShadow
        or footprint.status is not EvidenceResolutionStatus.CANDIDATE
        or footprint.diagnostic_only is not True
        or _float(footprint.candidate_area_m2) is None
        or footprint.candidate_area_m2 <= 0
    ):
        return block("source_figured_ceiling_footprint_unavailable")
    if type(pitch) is not DocumentedSourceCeilingPitch:
        return block("original_raked_pitch_record_untrusted")
    if (
        pitch.source_sha256 != footprint.source_sha256
        or pitch.revision_id != footprint.revision_id
        or pitch.page_id != footprint.page_id
        or type(pitch.physical_ceiling_surface_id) is not str
        or not pitch.physical_ceiling_surface_id
        or type(pitch.source_pitch_evidence_ids) not in (tuple, list)
        or not pitch.source_pitch_evidence_ids
        or any(type(value) is not str or not value or value != value.strip()
               for value in pitch.source_pitch_evidence_ids)
        or len(set(pitch.source_pitch_evidence_ids)) != len(pitch.source_pitch_evidence_ids)
    ):
        return block("original_raked_pitch_lineage_unavailable")

    given_angle = _float(pitch.slope_degrees)
    if pitch.slope_degrees is not None and (
        given_angle is None or given_angle < 0 or given_angle >= 90
    ):
        return block("source_raked_pitch_outside_physical_domain")
    rise = _float(pitch.documented_rise_mm)
    run = _float(pitch.documented_run_mm)
    if (pitch.documented_rise_mm is None) != (pitch.documented_run_mm is None):
        return block("original_raked_rise_run_incomplete")
    derived_angle = None
    if pitch.documented_rise_mm is not None:
        if rise is None or run is None or rise < 0 or run <= 0:
            return block("original_raked_rise_run_invalid")
        derived_angle = math.degrees(math.atan2(rise, run))
    if given_angle is None and derived_angle is None:
        return block("original_raked_pitch_unavailable")
    if given_angle is not None and derived_angle is not None:
        if not math.isclose(given_angle, derived_angle, rel_tol=1e-10, abs_tol=1e-10):
            return block("original_raked_pitch_competing_figures")
    angle = given_angle if given_angle is not None else derived_angle
    cosine = math.cos(math.radians(angle))
    if not math.isfinite(cosine) or cosine <= 0:
        return block("source_raked_pitch_outside_physical_domain")
    surface = footprint.candidate_area_m2 / cosine
    if not math.isfinite(surface) or surface <= 0:
        return block("raked_source_surface_measurement_unrepresentable")
    return FiguredSlopedSurfaceAreaShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("documented_source_raked_surface_shadow_only",),
        surface, footprint.candidate_area_m2, angle,
        pitch.physical_ceiling_surface_id,
        tuple(sorted(pitch.source_pitch_evidence_ids)),
    )
