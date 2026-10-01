"""Shadow structural coverage payload for GenericPlanReaderExtractor.

This module serializes producer-owned structural coverage records only. It does
not publish take-off rows, mutate extractor predictions, or establish physical
member authority.
"""
from __future__ import annotations

from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import StructuralMemberResolution
from pb_structural_member_coverage_snapshot import (
    structural_member_resolution_to_coverage_snapshot,
)
from pb_structural_member_quantity import build_structural_member_count_quantity
from pb_takeoff_coverage_registry import ENUMERATION_COMPLETE

STRUCTURAL_COVERAGE_SHADOW_NOT_COLLECTED = "not_collected"
STRUCTURAL_COVERAGE_SHADOW_COLLECTION_FAILED = "shadow_collection_failed"


def empty_structural_member_coverage_shadow(
    reason: str = STRUCTURAL_COVERAGE_SHADOW_NOT_COLLECTED,
) -> dict[str, Any]:
    clean_reason = str(reason or STRUCTURAL_COVERAGE_SHADOW_NOT_COLLECTED).strip()
    return {
        "status": "abstained",
        "reason_codes": [clean_reason],
        "registry_run_id": None,
        "physical_member_ids": [],
        "quantity_id": None,
        "object_universe_snapshot": None,
        "quantity_evidence": None,
    }


def collect_structural_member_coverage_shadow(
    resolution: StructuralMemberResolution,
    *,
    registry_run_id: str,
) -> dict[str, Any]:
    """Serialize exact structural producer coverage records for diagnostics."""
    if type(resolution) is not StructuralMemberResolution:
        raise TypeError("resolution must be StructuralMemberResolution")

    snapshot = structural_member_resolution_to_coverage_snapshot(
        resolution,
        registry_run_id=registry_run_id,
    )
    quantity = build_structural_member_count_quantity(resolution)
    status = (
        resolution.status
        if type(resolution.status) is EvidenceResolutionStatus
        else EvidenceResolutionStatus.ABSTAINED
    )
    if status is EvidenceResolutionStatus.CORROBORATED and (
        snapshot.enumeration_status != ENUMERATION_COMPLETE or quantity.abstained
    ):
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys((
        *resolution.reason_codes,
        *snapshot.reason_codes,
        *quantity.reason_codes,
        *quantity.blocking_reasons,
    )))
    return {
        "status": status.value,
        "reason_codes": list(reasons),
        "registry_run_id": snapshot.registry_run_id,
        "physical_member_ids": list(snapshot.admitted_object_ids),
        "quantity_id": quantity.quantity_id,
        "object_universe_snapshot": snapshot.to_dict(),
        "quantity_evidence": quantity.to_dict(),
    }


__all__ = [
    "STRUCTURAL_COVERAGE_SHADOW_COLLECTION_FAILED",
    "STRUCTURAL_COVERAGE_SHADOW_NOT_COLLECTED",
    "collect_structural_member_coverage_shadow",
    "empty_structural_member_coverage_shadow",
]
