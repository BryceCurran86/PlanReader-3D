"""Item 21: External glazing/window schedule vs physical aperture & elevation reconciliation shadow.

Reconciles external glazing and window dimensions across three distinct source
authorities on the same authenticated document revision:
1. Schedule row witness (explicit mark, width_mm, height_mm, dimension basis, notes)
2. Physical plan aperture witness (host-authenticated span in pts + calibrated mm/pt)
3. Elevation witness (explicit elevation width_mm, height_mm, sill/head level, basis)

Never invents glass/frame area from plan aperture geometry alone, preserves
explicit dimension basis distinctions, abstains on measure-on-site/TBC disclaimers
or unresolved schedule/elevation/aperture conflicts, and contains zero job-specific
rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Sequence


_VALID_BASES = frozenset(
    {
        "frame_dimension",
        "structural_opening",
        "rough_opening",
        "clear_opening",
        "glass_sight_size",
        "unknown_basis",
    }
)

_DISCLAIMER_RE = re.compile(
    r"\b(?:measure\s+on\s+site|verify\s+on\s+site|check\s+on\s+site|"
    r"site\s+measure|by\s+others|tbc|to\s+be\s+confirmed|nts|as\s+per\s+glazier|"
    r"subject\s+to\s+site|custom\s+measure)\b",
    re.IGNORECASE,
)

_SCHED_ELEV_DIM_TOL_MM = 15.0
_APERTURE_WIDTH_ABS_TOL_MM = 50.0
_APERTURE_WIDTH_REL_TOL = 0.05


def _clean(value: object) -> str:
    return str(value or "").strip()


def _pos(value: float | None) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) and v > 0.0 else None


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class GlazingLineageRef:
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str

    def doc_rev_sha(self) -> tuple[str, str, str]:
        return (
            _clean(self.document_id),
            _clean(self.revision_id),
            _clean(self.source_sha256).lower(),
        )

    def is_valid(self) -> bool:
        return all(
            bool(_clean(v))
            for v in (
                self.document_id,
                self.revision_id,
                self.source_sha256,
                self.page_id,
                self.viewport_id,
            )
        )


@dataclass(frozen=True)
class PhysicalGlazingApertureWitness:
    opening_id: str
    lineage: GlazingLineageRef
    host_wall_id: str
    span_pts: float
    calibrated_mm_per_pt: float | None
    printed_mark: str | None = None
    is_exterior_opening: bool = True
    is_corner_leg: bool = False
    corner_total_span_mm: float | None = None


@dataclass(frozen=True)
class GlazingScheduleRowWitness:
    row_id: str
    lineage: GlazingLineageRef
    mark: str
    width_mm: float | None
    height_mm: float | None
    dimension_basis: str = "frame_dimension"
    notes: str = ""
    is_multi_leg_assembly: bool = False


@dataclass(frozen=True)
class GlazingElevationWitness:
    elevation_witness_id: str
    lineage: GlazingLineageRef
    linked_mark: str | None
    linked_opening_id: str | None
    width_mm: float | None
    height_mm: float | None
    sill_height_mm: float | None = None
    head_height_mm: float | None = None
    dimension_basis: str = "frame_dimension"
    notes: str = ""


@dataclass(frozen=True)
class ExternalGlazingReconciliationResult:
    reconciliation_id: str
    opening_id: str
    reconciled: bool
    abstained: bool
    resolved_width_mm: float | None
    resolved_height_mm: float | None
    resolved_basis: str | None
    plan_aperture_width_mm: float | None
    supporting_source_ids: tuple[str, ...]
    blocking_reasons: tuple[str, ...]
    aperture_geometry_used_as_area: bool = False
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "reconciliation_id": self.reconciliation_id,
            "opening_id": self.opening_id,
            "reconciled": self.reconciled,
            "abstained": self.abstained,
            "resolved_width_mm": self.resolved_width_mm,
            "resolved_height_mm": self.resolved_height_mm,
            "resolved_basis": self.resolved_basis,
            "plan_aperture_width_mm": self.plan_aperture_width_mm,
            "supporting_source_ids": list(self.supporting_source_ids),
            "blocking_reasons": list(self.blocking_reasons),
            "aperture_geometry_used_as_area": False,
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def reconcile_external_glazing_evidence_shadow(
    aperture: PhysicalGlazingApertureWitness,
    *,
    schedule_rows: Sequence[GlazingScheduleRowWitness] = (),
    elevation_witnesses: Sequence[GlazingElevationWitness] = (),
) -> ExternalGlazingReconciliationResult:
    """Reconcile schedule, plan aperture, and elevation dimensions for an external glazing opening."""
    opening_id = _clean(aperture.opening_id)
    if not opening_id:
        raise ValueError("opening_id is required")

    reasons: list[str] = []
    supporting: list[str] = []

    if not aperture.lineage.is_valid():
        reasons.append("invalid_aperture_lineage")
    if not _clean(aperture.host_wall_id):
        reasons.append("unhosted_glazing_aperture_rejected")
    if not aperture.is_exterior_opening:
        reasons.append("non_external_opening_rejected")

    span_pts = _pos(aperture.span_pts)
    mm_per_pt = _pos(aperture.calibrated_mm_per_pt)
    if span_pts is None:
        reasons.append("invalid_aperture_span_pts")
    plan_width_mm = (
        round(span_pts * mm_per_pt, 2)
        if (span_pts is not None and mm_per_pt is not None)
        else None
    )
    if aperture.is_corner_leg and _pos(aperture.corner_total_span_mm) is not None:
        effective_plan_width_mm = round(float(aperture.corner_total_span_mm), 2)
    else:
        effective_plan_width_mm = plan_width_mm

    ap_rev = aperture.lineage.doc_rev_sha()
    ap_mark = _clean(aperture.printed_mark).upper()

    # Validate schedule rows
    valid_sched: list[GlazingScheduleRowWitness] = []
    for row in schedule_rows:
        if not row.lineage.is_valid() or row.lineage.doc_rev_sha() != ap_rev:
            reasons.append("cross_revision_schedule_row_rejected")
            continue
        r_mark = _clean(row.mark).upper()
        if ap_mark and r_mark and r_mark != ap_mark:
            reasons.append("schedule_mark_mismatch")
            continue
        if _DISCLAIMER_RE.search(_clean(row.notes)):
            reasons.append("glazing_measure_on_site_abstention")
            continue
        basis = _clean(row.dimension_basis).lower() or "unknown_basis"
        if basis not in _VALID_BASES:
            reasons.append("invalid_schedule_dimension_basis")
            continue
        if aperture.is_corner_leg and not row.is_multi_leg_assembly and _pos(aperture.corner_total_span_mm) is None:
            reasons.append("corner_glazing_single_leg_vs_schedule_unreconciled")
            continue
        valid_sched.append(row)
        supporting.append(row.row_id)

    # Validate elevation witnesses
    valid_elev: list[GlazingElevationWitness] = []
    for elev in elevation_witnesses:
        if not elev.lineage.is_valid() or elev.lineage.doc_rev_sha() != ap_rev:
            reasons.append("cross_revision_elevation_witness_rejected")
            continue
        linked_ok = False
        if _clean(elev.linked_opening_id) == opening_id:
            linked_ok = True
        elif ap_mark and _clean(elev.linked_mark).upper() == ap_mark:
            linked_ok = True
        if not linked_ok:
            reasons.append("unlinked_elevation_witness_rejected")
            continue
        if _DISCLAIMER_RE.search(_clean(elev.notes)):
            reasons.append("glazing_measure_on_site_abstention")
            continue
        basis = _clean(elev.dimension_basis).lower() or "unknown_basis"
        if basis not in _VALID_BASES:
            reasons.append("invalid_elevation_dimension_basis")
            continue
        # Internal elevation sanity check: head - sill must match explicit height if all three given
        if elev.head_height_mm is not None and elev.sill_height_mm is not None:
            derived_h = float(elev.head_height_mm) - float(elev.sill_height_mm)
            if derived_h <= 0.0:
                reasons.append("invalid_elevation_sill_head_levels")
                continue
            if _pos(elev.height_mm) is not None and abs(derived_h - float(elev.height_mm)) > _SCHED_ELEV_DIM_TOL_MM:
                reasons.append("elevation_internal_sill_head_height_conflict")
                continue
        valid_elev.append(elev)
        supporting.append(elev.elevation_witness_id)

    if not valid_sched and not valid_elev:
        reasons.append("aperture_geometry_alone_cannot_supply_glazing_dimensions")

    # Collect explicit width/height/basis claims
    width_claims: list[tuple[str, float, str]] = []
    height_claims: list[tuple[str, float, str]] = []
    bases: set[str] = set()

    for r in valid_sched:
        b = _clean(r.dimension_basis).lower() or "unknown_basis"
        bases.add(b)
        if _pos(r.width_mm) is not None:
            width_claims.append((r.row_id, round(float(r.width_mm), 2), b))
        if _pos(r.height_mm) is not None:
            height_claims.append((r.row_id, round(float(r.height_mm), 2), b))

    for e in valid_elev:
        b = _clean(e.dimension_basis).lower() or "unknown_basis"
        bases.add(b)
        if _pos(e.width_mm) is not None:
            width_claims.append((e.elevation_witness_id, round(float(e.width_mm), 2), b))
        h_val = _pos(e.height_mm)
        if h_val is None and e.head_height_mm is not None and e.sill_height_mm is not None:
            derived = float(e.head_height_mm) - float(e.sill_height_mm)
            if derived > 0.0:
                h_val = derived
        if h_val is not None:
            height_claims.append((e.elevation_witness_id, round(float(h_val), 2), b))

    concrete_bases = bases - {"unknown_basis"}
    resolved_basis: str | None = None
    if len(concrete_bases) > 1:
        reasons.append("glazing_dimension_basis_mismatch")
    elif len(concrete_bases) == 1:
        resolved_basis = next(iter(concrete_bases))
    elif "unknown_basis" in bases:
        resolved_basis = "unknown_basis"

    resolved_w: float | None = None
    if width_claims:
        w_vals = [v for _, v, _ in width_claims]
        if max(w_vals) - min(w_vals) > _SCHED_ELEV_DIM_TOL_MM:
            reasons.append("schedule_vs_elevation_width_conflict")
        else:
            resolved_w = round(sum(w_vals) / len(w_vals), 2)
    else:
        reasons.append("glazing_explicit_width_missing")

    resolved_h: float | None = None
    if height_claims:
        h_vals = [v for _, v, _ in height_claims]
        if max(h_vals) - min(h_vals) > _SCHED_ELEV_DIM_TOL_MM:
            reasons.append("schedule_vs_elevation_height_conflict")
        else:
            resolved_h = round(sum(h_vals) / len(h_vals), 2)
    else:
        reasons.append("glazing_explicit_height_missing")

    # Cross-check explicit width against physical calibrated plan aperture width
    if resolved_w is not None and effective_plan_width_mm is not None:
        diff = abs(resolved_w - effective_plan_width_mm)
        rel = diff / max(resolved_w, effective_plan_width_mm, 1.0)
        if diff > _APERTURE_WIDTH_ABS_TOL_MM and rel > _APERTURE_WIDTH_REL_TOL:
            reasons.append("schedule_vs_physical_aperture_width_conflict")

    dedup = tuple(dict.fromkeys(reasons))
    reconciled = (
        resolved_w is not None
        and resolved_h is not None
        and not dedup
    )
    payload = {
        "opening_id": opening_id,
        "reconciled": reconciled,
        "resolved_width_mm": resolved_w if reconciled else None,
        "resolved_height_mm": resolved_h if reconciled else None,
        "resolved_basis": resolved_basis if reconciled else None,
        "plan_aperture_width_mm": effective_plan_width_mm,
        "supporting_source_ids": sorted(supporting),
        "blocking_reasons": list(dedup),
    }
    digest = _canonical_sha(payload)
    return ExternalGlazingReconciliationResult(
        reconciliation_id=f"glazing_reconcile_{digest[:16]}",
        opening_id=opening_id,
        reconciled=reconciled,
        abstained=not reconciled,
        resolved_width_mm=resolved_w if reconciled else None,
        resolved_height_mm=resolved_h if reconciled else None,
        resolved_basis=resolved_basis if reconciled else None,
        plan_aperture_width_mm=effective_plan_width_mm,
        supporting_source_ids=tuple(sorted(supporting)),
        blocking_reasons=dedup,
        aperture_geometry_used_as_area=False,
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
