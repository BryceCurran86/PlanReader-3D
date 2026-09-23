"""Bridge producer-owned physical scale evidence into existing page calibration.

This module does not create a second scale resolver. It accepts only sealed
PhysicalScaleAuthority output, converts its native graphic-scale-bar mapping
into the existing ScaleSourceReading(SCALE_BAR) contract, and delegates the
actual ScaleCalibration status to resolve_page_scale_calibration.

The original PhysicalScaleEvidence is retained alongside the calibration so
the source observation lineage is not lost at the adapter boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from pb_geometry_takeoff_model import AuthorityStatus, ScaleCalibration
from pb_migration_contracts import EvidenceResolutionStatus, ViewportEvidence
from pb_migration_provider_envelope import ProviderContext
from pb_page_scale_calibration_authority import (
    POINTS_PER_METRE_AT_1_1,
    ScaleSourceReading,
    ScaleSourceType,
    measurement_authority_for_page_scale,
    resolve_page_scale_calibration,
)
from pb_physical_scale_authority import (
    PHYSICAL_SCALE_RESOLVED,
    PhysicalScaleAuthority,
    PhysicalScaleEvidence,
    PhysicalScaleSelector,
)


PHYSICAL_SCALE_CALIBRATION_SCHEMA_VERSION = "1.0.0"
PHYSICAL_SCALE_CALIBRATION_RESOLVED = "physical_scale_calibration_resolved"
PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE = "physical_scale_calibration_unavailable"
PHYSICAL_SCALE_CALIBRATION_CONTEXT_MISMATCH = "physical_scale_calibration_context_mismatch"
PHYSICAL_SCALE_CALIBRATION_INVALID = "physical_scale_calibration_invalid"


@dataclass(frozen=True)
class PhysicalScaleCalibrationBridgeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    calibration: Optional[ScaleCalibration]
    physical_scale_evidence: Optional[PhysicalScaleEvidence]
    schema_version: str = PHYSICAL_SCALE_CALIBRATION_SCHEMA_VERSION


def _context_matches(
    *,
    selector: PhysicalScaleSelector,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> bool:
    if not context.revision_id or not context.current_revision_id:
        return False
    if context.revision_id != context.current_revision_id:
        return False
    if selector.document_id != context.document_id:
        return False
    if selector.revision_id != context.current_revision_id:
        return False
    if selector.source_sha256 != context.source_sha256:
        return False
    if selector.page_id != viewport.page_id:
        return False
    try:
        if int(selector.page_id) != int(page_no):
            return False
    except (TypeError, ValueError):
        return False
    if viewport.document_id != context.document_id:
        return False
    if viewport.viewport_id not in context.trusted_viewport_ids():
        return False
    if int(page_no) not in context.trusted_page_numbers():
        return False
    mapped = context.page_for_viewport(viewport.viewport_id)
    if mapped is not None and int(mapped) != int(page_no):
        return False
    # Scoped physical scale must match the exact viewport. A page-wide selector
    # is allowed only because PhysicalScaleProducer itself permits it solely
    # when no usable segmented viewport exists.
    if selector.viewport_id is not None and selector.viewport_id != viewport.viewport_id:
        return False
    return True


def build_physical_scale_calibration(
    *,
    physical_scale_authority: PhysicalScaleAuthority,
    selector: PhysicalScaleSelector,
    context: ProviderContext,
    viewport: ViewportEvidence,
    page_no: int,
) -> PhysicalScaleCalibrationBridgeResult:
    """Resolve a FIRM existing ScaleCalibration from a native graphic scale bar."""

    if type(physical_scale_authority) is not PhysicalScaleAuthority:
        raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
    if type(selector) is not PhysicalScaleSelector:
        raise TypeError("selector must be PhysicalScaleSelector")

    if not _context_matches(
        selector=selector,
        context=context,
        viewport=viewport,
        page_no=page_no,
    ):
        return PhysicalScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(PHYSICAL_SCALE_CALIBRATION_CONTEXT_MISMATCH,),
            calibration=None,
            physical_scale_evidence=None,
        )

    result = physical_scale_authority.resolve(selector)
    evidence = result.evidence
    if (
        result.status is not EvidenceResolutionStatus.CORROBORATED
        or result.reason_codes != (PHYSICAL_SCALE_RESOLVED,)
        or evidence is None
    ):
        return PhysicalScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE,),
            calibration=None,
            physical_scale_evidence=None,
        )

    if (
        evidence.selector != selector
        or evidence.source_kind != "native_graphic_scale_bar"
        or evidence.viewport_id != selector.viewport_id
        or not evidence.source_segment_observation_ids
        or not evidence.source_text_observation_ids
    ):
        return PhysicalScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(PHYSICAL_SCALE_CALIBRATION_INVALID,),
            calibration=None,
            physical_scale_evidence=evidence,
        )

    points_per_mm = float(evidence.points_per_mm)
    if not math.isfinite(points_per_mm) or points_per_mm <= 0.0:
        return PhysicalScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(PHYSICAL_SCALE_CALIBRATION_INVALID,),
            calibration=None,
            physical_scale_evidence=evidence,
        )

    px_per_m = points_per_mm * 1000.0
    ratio = POINTS_PER_METRE_AT_1_1 / px_per_m
    if not math.isfinite(ratio) or ratio <= 0.0:
        return PhysicalScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(PHYSICAL_SCALE_CALIBRATION_INVALID,),
            calibration=None,
            physical_scale_evidence=evidence,
        )

    calibration = resolve_page_scale_calibration(
        page_no=int(page_no),
        sheet_label="",
        readings=[
            ScaleSourceReading(
                source_type=ScaleSourceType.SCALE_BAR.value,
                scale_text=f"1:{ratio:.12g}",
                ratio=ratio,
                confidence=1.0,
            )
        ],
        revision_id=context.current_revision_id,
    )
    tolerance = max(1e-9, abs(px_per_m) * 1e-12)
    if (
        abs(float(calibration.px_per_m) - px_per_m) > tolerance
        or measurement_authority_for_page_scale(calibration) != AuthorityStatus.FIRM.value
    ):
        return PhysicalScaleCalibrationBridgeResult(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(PHYSICAL_SCALE_CALIBRATION_INVALID,),
            calibration=None,
            physical_scale_evidence=evidence,
        )

    return PhysicalScaleCalibrationBridgeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(PHYSICAL_SCALE_CALIBRATION_RESOLVED,),
        calibration=calibration,
        physical_scale_evidence=evidence,
    )


__all__ = [
    "PHYSICAL_SCALE_CALIBRATION_CONTEXT_MISMATCH",
    "PHYSICAL_SCALE_CALIBRATION_INVALID",
    "PHYSICAL_SCALE_CALIBRATION_RESOLVED",
    "PHYSICAL_SCALE_CALIBRATION_SCHEMA_VERSION",
    "PHYSICAL_SCALE_CALIBRATION_UNAVAILABLE",
    "PhysicalScaleCalibrationBridgeResult",
    "build_physical_scale_calibration",
]
