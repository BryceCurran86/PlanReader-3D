"""Fail-closed gate: topology rings may not mint FIRM metric areas without
authenticated page-scale measurement authority.

Title-block-only scale stays provisional under
``measurement_authority_for_page_scale`` and cannot seal metric quantities.
This module never invents scale, never calls commercial sealers, and never
mutates customer rows.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Sequence

from pb_geometry_takeoff_model import AuthorityStatus, ScaleCalibration
from pb_page_scale_calibration_authority import (
    ScaleCalibrationStatus,
    ScaleSourceType,
    measurement_authority_for_page_scale,
    unknown_calibration,
)


_SEALABLE_MEASUREMENT_AUTHORITIES = frozenset(
    {
        AuthorityStatus.FIRM.value,
        AuthorityStatus.USER_APPROVED.value,
    }
)


@dataclass(frozen=True)
class TopologyMetricSealGateResult:
    """Audit of whether a topology candidate may enter metric seal review."""

    page_no: int
    seal_eligible: bool
    first_remaining_gate: str
    measurement_authority: str
    scale_source_type: str
    scale_status: str
    shadow_only: bool = True
    measurement_published: bool = False
    customer_rows_mutated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "page_no": self.page_no,
            "seal_eligible": self.seal_eligible,
            "first_remaining_gate": self.first_remaining_gate,
            "measurement_authority": self.measurement_authority,
            "scale_source_type": self.scale_source_type,
            "scale_status": self.scale_status,
            "shadow_only": self.shadow_only,
            "measurement_published": self.measurement_published,
            "customer_rows_mutated": self.customer_rows_mutated,
        }


def _as_calibration(raw: Optional[ScaleCalibration | Mapping[str, Any]], page_no: int) -> ScaleCalibration:
    if raw is None:
        return unknown_calibration(page_no)
    if isinstance(raw, ScaleCalibration):
        return raw
    if not isinstance(raw, Mapping):
        return unknown_calibration(page_no)
    try:
        return ScaleCalibration(
            page_no=int(raw.get("page_no", page_no)),
            ratio_str=str(raw.get("ratio_str") or "UNKNOWN"),
            px_per_m=float(raw.get("px_per_m") or 0.0),
            method=str(raw.get("method") or "UNKNOWN"),
            is_verified=bool(raw.get("is_verified", False)),
            confidence=float(raw.get("confidence") or 0.0),
            sheet_label=str(raw.get("sheet_label") or ""),
            scale_text=str(raw.get("scale_text") or ""),
            source_type=str(raw.get("source_type") or ScaleSourceType.UNKNOWN.value),
            status=str(raw.get("status") or ScaleCalibrationStatus.UNKNOWN.value),
            issues=list(raw.get("issues") or []),
            revision_id=raw.get("revision_id"),
            approved_by=raw.get("approved_by"),
            approved_at=raw.get("approved_at"),
        )
    except (TypeError, ValueError, OverflowError):
        return unknown_calibration(page_no)


def assess_topology_metric_seal_gate(
    *,
    page_no: int,
    calibration: Optional[ScaleCalibration | Mapping[str, Any]] = None,
    topology_candidates_present: bool = False,
    source_lineage_complete: bool = False,
) -> TopologyMetricSealGateResult:
    """Return the first remaining gate for metric seal of topology areas.

    Observed Acacia p2 behaviour: title-block ``1:100`` alone yields provisional
    measurement authority — first gate is authenticated non-title-block scale.
    """
    calib = _as_calibration(calibration, int(page_no))
    authority = measurement_authority_for_page_scale(calib)
    source_type = str(calib.source_type or ScaleSourceType.UNKNOWN.value)
    status = str(calib.status or ScaleCalibrationStatus.UNKNOWN.value)

    if not topology_candidates_present:
        gate = "seal_blocked_no_topology_candidates"
    elif not source_lineage_complete:
        gate = "seal_blocked_incomplete_source_lineage"
    elif source_type == ScaleSourceType.TITLE_BLOCK.value and authority != AuthorityStatus.USER_APPROVED.value:
        gate = "seal_blocked_title_block_scale_not_firm"
    elif authority not in _SEALABLE_MEASUREMENT_AUTHORITIES:
        gate = "seal_blocked_page_scale_not_firm"
    elif not calib.is_usable_for_firm_measurement():
        gate = "seal_blocked_scale_calibration_unusable"
    else:
        gate = "topology_metric_seal_review_only"

    return TopologyMetricSealGateResult(
        page_no=int(page_no),
        seal_eligible=False,
        first_remaining_gate=gate,
        measurement_authority=authority,
        scale_source_type=source_type,
        scale_status=status,
    )


def assess_acacia_p2_title_block_only_gate(
    *,
    page_no: int = 2,
    scale_text: str = "1:100",
    topology_candidate_count: int = 0,
) -> TopologyMetricSealGateResult:
    """Convenience probe matching Acacia House p2: title-block scale only."""
    from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1

    ratio = 100.0
    calib = ScaleCalibration(
        page_no=int(page_no),
        ratio_str="1:100",
        px_per_m=POINTS_PER_METRE_AT_1_1 / ratio,
        method="OCR_TEXT",
        is_verified=True,
        confidence=1.0,
        sheet_label="p2",
        scale_text=str(scale_text or "1:100"),
        source_type=ScaleSourceType.TITLE_BLOCK.value,
        status=ScaleCalibrationStatus.VALID.value,
        issues=["title-block scale only; no figured dimension or scale bar corroboration"],
    )
    return assess_topology_metric_seal_gate(
        page_no=int(page_no),
        calibration=calib,
        topology_candidates_present=int(topology_candidate_count) > 0,
        source_lineage_complete=True,
    )


def summarize_gate_batch(
    results: Sequence[TopologyMetricSealGateResult],
) -> dict[str, Any]:
    """Aggregate first-gate counts without promoting any measurement."""
    counts: dict[str, int] = {}
    for row in results:
        counts[row.first_remaining_gate] = counts.get(row.first_remaining_gate, 0) + 1
    return {
        "count": len(results),
        "any_seal_eligible": False,
        "first_gate_counts": counts,
        "shadow_only": True,
    }
