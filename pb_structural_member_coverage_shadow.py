"""Shadow structural coverage payload for GenericPlanReaderExtractor.

This module serializes producer-owned structural coverage records only. It does
not publish take-off rows, mutate extractor predictions, or establish physical
member authority.
"""
from __future__ import annotations

from typing import Any, Callable

from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_structural_member_authority import StructuralMemberResolution
from pb_structural_member_coverage_snapshot import (
    STRUCTURAL_COVERAGE_PRODUCER,
    structural_member_resolution_to_coverage_snapshot,
)
from pb_structural_member_quantity import (
    STRUCTURAL_MEMBER_COUNT_FAMILY,
    build_structural_member_count_quantity,
)
from pb_takeoff_coverage_registry import (
    ENUMERATION_COMPLETE,
    CoverageRegistryRunManifestV1,
    ProducerObjectUniverseSnapshotV1,
    QuantityEvidenceUniverseSnapshotV1,
    build_coverage_registry_v1,
)

STRUCTURAL_COVERAGE_SHADOW_NOT_COLLECTED = "not_collected"
STRUCTURAL_COVERAGE_SHADOW_COLLECTION_FAILED = "shadow_collection_failed"
STRUCTURAL_COVERAGE_QUANTITY_SOURCE = STRUCTURAL_MEMBER_COUNT_FAMILY
STRUCTURAL_COVERAGE_TAKEOFF_SOURCE = STRUCTURAL_COVERAGE_PRODUCER
STRUCTURAL_COVERAGE_TAKEOFF_COLLECTION = STRUCTURAL_MEMBER_COUNT_FAMILY


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
        "coverage_registry_summary": None,
    }


def _member_metadata_by_id(
    resolution: StructuralMemberResolution,
    admitted_object_ids: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    admitted = set(admitted_object_ids)
    metadata: dict[str, dict[str, Any]] = {}
    for member in resolution.members:
        object_id = str(member.physical_member_id or "").strip()
        if object_id not in admitted:
            continue
        pages: set[int] = set()
        for raw_page in member.page_ids:
            try:
                page = int(raw_page)
            except (TypeError, ValueError, OverflowError):
                continue
            if page >= 0:
                pages.add(page)
        metadata[object_id] = {
            "object_type": str(member.member_kind or "").strip().lower(),
            "source_pages": tuple(sorted(pages)),
            "source_evidence_ids": tuple(member.source_evidence_ids),
            "source_primitive_ids": tuple(member.source_primitive_ids),
            "provenance": {
                "observation_ids": tuple(member.observation_ids),
                "view_ids": tuple(member.view_ids),
                "definition_ids": tuple(member.definition_ids),
                "decision_scope_id": resolution.selector.decision_scope_id,
            },
        }
    return metadata


def _build_structural_registry_summary(
    resolution: StructuralMemberResolution,
    *,
    snapshot: ProducerObjectUniverseSnapshotV1,
    quantity: QuantityEvidence,
) -> Any:
    quantity_key = (
        STRUCTURAL_COVERAGE_PRODUCER,
        STRUCTURAL_COVERAGE_QUANTITY_SOURCE,
    )
    row_key = (
        STRUCTURAL_COVERAGE_TAKEOFF_SOURCE,
        STRUCTURAL_COVERAGE_TAKEOFF_COLLECTION,
    )
    manifest = CoverageRegistryRunManifestV1(
        source_document_id=snapshot.source_document_id,
        revision_id=snapshot.revision_id,
        source_sha256=snapshot.source_sha256,
        registry_run_id=snapshot.registry_run_id,
        snapshot_id=snapshot.snapshot_id,
        expected_object_universe_keys=((snapshot.producer, snapshot.category),),
        expected_quantity_evidence_universe_keys=(quantity_key,),
        expected_takeoff_row_universe_keys=(row_key,),
    )
    quantity_snapshot = QuantityEvidenceUniverseSnapshotV1(
        producer=quantity_key[0],
        source=quantity_key[1],
        source_document_id=snapshot.source_document_id,
        revision_id=snapshot.revision_id,
        source_sha256=snapshot.source_sha256,
        registry_run_id=snapshot.registry_run_id,
        snapshot_id=snapshot.snapshot_id,
        quantity_ids=(quantity.quantity_id,),
        enumeration_status=ENUMERATION_COMPLETE,
    )
    return build_coverage_registry_v1(
        manifest=manifest,
        object_universe_snapshots=(snapshot,),
        quantity_evidence_universe_snapshots=(quantity_snapshot,),
        quantity_evidence_by_universe={quantity_key: (quantity,)},
        object_metadata_by_id=_member_metadata_by_id(
            resolution,
            snapshot.admitted_object_ids,
        ),
    )


def collect_structural_member_coverage_shadow(
    resolution: StructuralMemberResolution,
    *,
    registry_run_id: str,
    quantity_evidence_sink: Callable[[QuantityEvidence], None] | None = None,
) -> dict[str, Any]:
    """Serialize diagnostics, optionally retaining the original typed evidence.

    The sink is a diagnostic consumer only; it does not publish a takeoff row or
    allow the live extractor to recalculate this shadow quantity.
    """
    if type(resolution) is not StructuralMemberResolution:
        raise TypeError("resolution must be StructuralMemberResolution")

    snapshot = structural_member_resolution_to_coverage_snapshot(
        resolution,
        registry_run_id=registry_run_id,
    )
    quantity = build_structural_member_count_quantity(resolution)
    registry_summary = _build_structural_registry_summary(
        resolution,
        snapshot=snapshot,
        quantity=quantity,
    )
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
    if quantity_evidence_sink is not None:
        quantity_evidence_sink(quantity)
    return {
        "status": status.value,
        "reason_codes": list(reasons),
        "registry_run_id": snapshot.registry_run_id,
        "physical_member_ids": list(snapshot.admitted_object_ids),
        "quantity_id": quantity.quantity_id,
        "object_universe_snapshot": snapshot.to_dict(),
        "quantity_evidence": quantity.to_dict(),
        "coverage_registry_summary": registry_summary.to_dict(),
    }


__all__ = [
    "STRUCTURAL_COVERAGE_SHADOW_COLLECTION_FAILED",
    "STRUCTURAL_COVERAGE_SHADOW_NOT_COLLECTED",
    "collect_structural_member_coverage_shadow",
    "empty_structural_member_coverage_shadow",
]
