"""Raster Plan Dimension Authority customer-runtime bridge (AG-07).

Establishes and executes canonical dimension authority precedence across the
PlanReader customer runtime:

Authority Precedence:
1. Explicit Figured Dimension:
   Directly stated numerical dimension (e.g. "10000mm", "42.5 m²") on plan,
   schedule, or callout. Figured dimensions beat scaled geometry (reconcile_figured_and_scaled).
2. Authenticated Vector Geometry:
   Vector line / polygon geometry extracted from native PDF drawings / CAD streams
   (e.g. detect_dimension_calibration via get_drawings()).
3. Calibrated Raster Measurement:
   Raster plan dimension authority (pb_raster_plan_dimension_authority.py), where
   OCR text is bound to raster line/witness geometry, verified by contiguous child
   chain summation and orthogonal scale reconciliation.
4. Fallback / Printed Scale / Abstention:
   Title block printed scale (e.g. "1:100" provisional), or fail-closed CONFLICT/ABSTAINED
   when evidence is missing or contradictory beyond 5% tolerance.

Invariants:
- Weaker evidence (raster/fallback) NEVER overrides stronger evidence (explicit/vector).
- Disagreements between explicit dimensions and measured geometry trigger REVIEW_REQUIRED
  or CONFLICT rather than silent overwrite.
- Disagreements between vector geometry and raster geometry resolve in favor of vector.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pb_geometry_takeoff_model import AuthorityStatus, reconcile_figured_and_scaled
from pb_migration_contracts import EvidenceResolutionStatus
from pb_page_scale_calibration_authority import ScaleCalibrationStatus
from pb_raster_plan_dimension_authority import (
    RasterPlanDimensionAuthority,
    RasterPlanDimensionProducer,
    RasterPlanDimensionResult,
)


class DimensionPrecedenceTier:
    EXPLICIT = "explicit_dimension"
    VECTOR = "authenticated_vector_geometry"
    RASTER = "calibrated_raster_measurement"
    FALLBACK = "fallback_printed_scale"
    ABSTAINED = "abstained"


@dataclass(frozen=True)
class DimensionPrecedenceResult:
    """Outcome of resolving dimensions through the canonical 4-tier precedence hierarchy."""
    resolved_m: Optional[float]
    tier: str
    status: str  # AuthorityStatus value (firm, provisional, review_required, etc.)
    evidence_status: EvidenceResolutionStatus
    discrepancy_delta_m: Optional[float] = None
    discrepancy_ratio: Optional[float] = None
    notes: str = ""
    source_evidence: List[str] = field(default_factory=list)


def resolve_dimension_with_precedence(
    *,
    explicit_dim_m: Optional[float] = None,
    vector_geom_m: Optional[float] = None,
    raster_geom_m: Optional[float] = None,
    fallback_dim_m: Optional[float] = None,
    max_delta_ratio: float = 0.05,
    source_evidence_ids: Optional[Sequence[str]] = None,
) -> DimensionPrecedenceResult:
    """Resolve dimension using the strict 4-tier precedence hierarchy.

    Precedence order:
      Tier 1: explicit_dim_m (figured dimension beats all measured geometry)
      Tier 2: vector_geom_m (native vector drawings beat raster measurements)
      Tier 3: raster_geom_m (calibrated raster OCR + witness lines)
      Tier 4: fallback_dim_m (printed scale / fallback)

    Disagreement Rules:
    - If explicit dimension and measured geometry disagree beyond max_delta_ratio,
      explicit dimension prevails but status escalates to REVIEW_REQUIRED with notes.
    - If vector geometry and raster geometry disagree, vector geometry prevails.
    - If no valid dimension is provided, returns ABSTAINED.
    """
    ev_ids = list(source_evidence_ids or [])

    # Validate explicit dimension
    has_explicit = explicit_dim_m is not None and math.isfinite(explicit_dim_m) and explicit_dim_m > 0.0
    # Validate vector geometry
    has_vector = vector_geom_m is not None and math.isfinite(vector_geom_m) and vector_geom_m > 0.0
    # Validate raster geometry
    has_raster = raster_geom_m is not None and math.isfinite(raster_geom_m) and raster_geom_m > 0.0
    # Validate fallback
    has_fallback = fallback_dim_m is not None and math.isfinite(fallback_dim_m) and fallback_dim_m > 0.0

    # TIER 1: Explicit Figured Dimension
    if has_explicit:
        assert explicit_dim_m is not None
        figured_mm = explicit_dim_m * 1000.0

        # Check against measured geometry (prefer vector, then raster)
        measured_m = vector_geom_m if has_vector else (raster_geom_m if has_raster else None)
        scaled_mm = measured_m * 1000.0 if measured_m is not None else None

        length_m, auth_status, delta_mm, notes = reconcile_figured_and_scaled(
            figured_mm=figured_mm,
            scaled_mm=scaled_mm,
            max_delta_ratio=max_delta_ratio,
        )

        delta_m = round(delta_mm / 1000.0, 4) if delta_mm is not None else None
        delta_ratio = round(delta_m / explicit_dim_m, 4) if (delta_m is not None and explicit_dim_m > 0) else None

        resolution_status = (
            EvidenceResolutionStatus.CORROBORATED
            if auth_status == AuthorityStatus.FIRM.value
            else (
                EvidenceResolutionStatus.CONFLICT
                if auth_status == AuthorityStatus.REVIEW_REQUIRED.value
                else EvidenceResolutionStatus.CANDIDATE
            )
        )

        return DimensionPrecedenceResult(
            resolved_m=length_m,
            tier=DimensionPrecedenceTier.EXPLICIT,
            status=auth_status,
            evidence_status=resolution_status,
            discrepancy_delta_m=delta_m,
            discrepancy_ratio=delta_ratio,
            notes=notes,
            source_evidence=ev_ids,
        )

    # TIER 2: Authenticated Vector Geometry
    if has_vector:
        assert vector_geom_m is not None
        v_m = round(vector_geom_m, 4)

        # Cross-check against raster geometry if present
        if has_raster:
            assert raster_geom_m is not None
            delta_m = round(abs(v_m - raster_geom_m), 4)
            delta_ratio = round(delta_m / v_m, 4) if v_m > 0 else 0.0
            if delta_ratio > max_delta_ratio:
                notes = (
                    f"Vector geometry {v_m}m prevails over raster measurement {raster_geom_m}m "
                    f"(discrepancy: {delta_m}m, {delta_ratio*100:.1f}%)"
                )
                auth_status = AuthorityStatus.REVIEW_REQUIRED.value
                res_status = EvidenceResolutionStatus.CONFLICT
            else:
                notes = f"Vector geometry {v_m}m confirmed by raster measurement ({raster_geom_m}m)"
                auth_status = AuthorityStatus.FIRM.value
                res_status = EvidenceResolutionStatus.CORROBORATED
            return DimensionPrecedenceResult(
                resolved_m=v_m,
                tier=DimensionPrecedenceTier.VECTOR,
                status=auth_status,
                evidence_status=res_status,
                discrepancy_delta_m=delta_m,
                discrepancy_ratio=delta_ratio,
                notes=notes,
                source_evidence=ev_ids,
            )

        return DimensionPrecedenceResult(
            resolved_m=v_m,
            tier=DimensionPrecedenceTier.VECTOR,
            status=AuthorityStatus.PROVISIONAL.value,
            evidence_status=EvidenceResolutionStatus.CANDIDATE,
            discrepancy_delta_m=None,
            discrepancy_ratio=None,
            notes=f"Vector geometry measurement {v_m}m (no explicit figured dimension)",
            source_evidence=ev_ids,
        )

    # TIER 3: Calibrated Raster Measurement
    if has_raster:
        assert raster_geom_m is not None
        r_m = round(raster_geom_m, 4)
        return DimensionPrecedenceResult(
            resolved_m=r_m,
            tier=DimensionPrecedenceTier.RASTER,
            status=AuthorityStatus.PROVISIONAL.value,
            evidence_status=EvidenceResolutionStatus.CANDIDATE,
            discrepancy_delta_m=None,
            discrepancy_ratio=None,
            notes=f"Calibrated raster measurement {r_m}m from figured chain",
            source_evidence=ev_ids,
        )

    # TIER 4: Fallback Printed Scale
    if has_fallback:
        assert fallback_dim_m is not None
        f_m = round(fallback_dim_m, 4)
        return DimensionPrecedenceResult(
            resolved_m=f_m,
            tier=DimensionPrecedenceTier.FALLBACK,
            status=AuthorityStatus.PROVISIONAL.value,
            evidence_status=EvidenceResolutionStatus.CANDIDATE,
            discrepancy_delta_m=None,
            discrepancy_ratio=None,
            notes=f"Provisional fallback measurement {f_m}m based on printed scale",
            source_evidence=ev_ids,
        )

    # ABSTAINED: No evidence
    return DimensionPrecedenceResult(
        resolved_m=None,
        tier=DimensionPrecedenceTier.ABSTAINED,
        status=AuthorityStatus.UNVERIFIED.value,
        evidence_status=EvidenceResolutionStatus.ABSTAINED,
        discrepancy_delta_m=None,
        discrepancy_ratio=None,
        notes="No valid dimension or geometry evidence available",
        source_evidence=ev_ids,
    )


def detect_raster_plan_dimension_calibration(
    app: Any,
    page: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Detect page scale calibration from raster plan dimension authority.

    Invoked only when vector dimension lines are unavailable (Tier 3).
    Returns calibration dict matching detect_dimension_calibration layout, or None.
    """
    # 1. Check if precomputed raster plan dimension results exist on app
    results = getattr(app, "raster_plan_dimension_results", None)
    if isinstance(results, dict):
        page_id = str(page.get("id") or page.get("page_no") or "")
        res = results.get(page_id)
        if isinstance(res, RasterPlanDimensionResult) and res.status is EvidenceResolutionStatus.CANDIDATE:
            if res.scale_px_per_m is not None and res.scale_px_per_m > 0:
                dim_text = ""
                if res.horizontal:
                    dim_text = f"{res.horizontal.value_mm}mm"
                elif res.vertical:
                    dim_text = f"{res.vertical.value_mm}mm"
                return {
                    "px_per_m": round(res.scale_px_per_m, 4),
                    "dimension_text": dim_text or "raster chain",
                    "confidence": "Medium",
                    "method": "Raster figured chain",
                    "length_m": res.length_m,
                    "width_m": res.width_m,
                }

    # 2. Check if app has raster plan dimension authority configured
    authority = getattr(app, "raster_plan_dimension_authority", None)
    if isinstance(authority, RasterPlanDimensionAuthority):
        try:
            rev_id = str(getattr(app, "active_revision_id", "") or "default_rev")
            page_id = str(page.get("page_no") or page.get("id") or "1")
            res = authority.get(rev_id, page_id)
            if res is not None and res.status is EvidenceResolutionStatus.CANDIDATE:
                if res.scale_px_per_m is not None and res.scale_px_per_m > 0:
                    dim_text = f"{res.horizontal.value_mm}mm" if res.horizontal else "raster chain"
                    return {
                        "px_per_m": round(res.scale_px_per_m, 4),
                        "dimension_text": dim_text,
                        "confidence": "Medium",
                        "method": "Raster figured chain",
                        "length_m": res.length_m,
                        "width_m": res.width_m,
                    }
        except Exception:
            pass

    return None


__all__ = [
    "DimensionPrecedenceResult",
    "DimensionPrecedenceTier",
    "detect_raster_plan_dimension_calibration",
    "resolve_dimension_with_precedence",
]
