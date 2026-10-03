"""Figured opening-area authority for source-wide joinery height notes.

This authority combines two already-authenticated propositions for one proven
physical opening:

1. a source-bound single figured opening width; and
2. a source-owned document joinery height stated above finished level U.N.O.

It is deliberately limited to openings whose reconciled semantic kind is
"door". The result is a figured commercial area only. It does not claim a
physical sill, z0/z1, void profile, scale-derived height, or 3D placement.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

from pb_document_joinery_head_height_authority import (
    DocumentJoineryHeadHeightResult,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_kind_authority import OpeningKindResolution
from pb_opening_label_dimension_authority import OpeningLabelDimensionEvidence
from pb_physical_opening_authority import PhysicalOpeningExistenceRecord


OPENING_JOINERY_FIGURED_AREA_SCHEMA_VERSION = "1.0.0"
OPENING_JOINERY_FIGURED_AREA_RESOLVED = "opening_joinery_figured_area_resolved"
OPENING_JOINERY_FIGURED_AREA_UNAVAILABLE = "opening_joinery_figured_area_unavailable"
OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED = (
    "opening_joinery_figured_area_door_kind_required"
)
OPENING_JOINERY_FIGURED_AREA_SINGLE_WIDTH_REQUIRED = (
    "opening_joinery_figured_area_single_width_required"
)
OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT = (
    "opening_joinery_figured_area_lineage_conflict"
)


@dataclass(frozen=True)
class OpeningJoineryFiguredAreaEvidence:
    evidence_id: str
    opening_record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    viewport_id: Optional[str]
    width_mm: float
    height_mm: float
    area_m2: float
    label_evidence_id: str
    joinery_height_evidence_id: str
    source_text_observation_ids: tuple[str, ...]
    basis: str = "figured_opening_width_x_joinery_height"
    schema_version: str = OPENING_JOINERY_FIGURED_AREA_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningJoineryFiguredAreaResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: Optional[OpeningJoineryFiguredAreaEvidence] = None
    schema_version: str = OPENING_JOINERY_FIGURED_AREA_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> OpeningJoineryFiguredAreaResult:
    return OpeningJoineryFiguredAreaResult(
        status=status,
        reason_codes=tuple(dict.fromkeys(reason for reason in reasons if reason))
        or (OPENING_JOINERY_FIGURED_AREA_UNAVAILABLE,),
    )


def resolve_opening_joinery_figured_area(
    *,
    opening: PhysicalOpeningExistenceRecord,
    label: OpeningLabelDimensionEvidence,
    joinery_height: DocumentJoineryHeadHeightResult,
    opening_kind: OpeningKindResolution,
) -> OpeningJoineryFiguredAreaResult:
    """Resolve one door area from figured width times source-wide joinery height."""

    if type(opening) is not PhysicalOpeningExistenceRecord:
        raise TypeError("opening must be PhysicalOpeningExistenceRecord")
    if type(label) is not OpeningLabelDimensionEvidence:
        raise TypeError("label must be OpeningLabelDimensionEvidence")
    if type(joinery_height) is not DocumentJoineryHeadHeightResult:
        raise TypeError("joinery_height must be DocumentJoineryHeadHeightResult")
    if type(opening_kind) is not OpeningKindResolution:
        raise TypeError("opening_kind must be OpeningKindResolution")

    if (
        opening_kind.status is not EvidenceResolutionStatus.CORROBORATED
        or opening_kind.opening_kind != "door"
    ):
        status = (
            EvidenceResolutionStatus.CONFLICT
            if opening_kind.status is EvidenceResolutionStatus.CONFLICT
            else EvidenceResolutionStatus.ABSTAINED
        )
        return _blocked(status, OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED)

    if (
        label.opening_record_id != opening.record_id
        or str(label.page_id) != str(opening.page_id)
        or (
            label.viewport_id is not None
            and opening.viewport_id is not None
            and str(label.viewport_id) != str(opening.viewport_id)
        )
    ):
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT,
        )

    if (
        len(label.dimension_values_mm) != 1
        or label.area_m2 is not None
        or label.axis_order_resolved
    ):
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            OPENING_JOINERY_FIGURED_AREA_SINGLE_WIDTH_REQUIRED,
        )

    if (
        label.semantic_kind is not None
        and str(label.semantic_kind).strip().lower() != "door"
    ):
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED,
        )

    if (
        joinery_height.status is not EvidenceResolutionStatus.CORROBORATED
        or joinery_height.evidence is None
    ):
        status = (
            EvidenceResolutionStatus.CONFLICT
            if joinery_height.status is EvidenceResolutionStatus.CONFLICT
            else EvidenceResolutionStatus.ABSTAINED
        )
        return _blocked(
            status,
            *joinery_height.reason_codes,
            OPENING_JOINERY_FIGURED_AREA_UNAVAILABLE,
        )

    height = joinery_height.evidence
    if (
        height.document_id != opening.document_id
        or height.revision_id != opening.revision_id
        or height.source_sha256 != opening.source_sha256
        or height.snapshot_id != opening.snapshot_id
    ):
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT,
        )

    width_mm = float(label.dimension_values_mm[0])
    height_mm = float(height.head_height_mm)
    if (
        not math.isfinite(width_mm)
        or not math.isfinite(height_mm)
        or width_mm <= 0.0
        or height_mm <= 0.0
    ):
        return _blocked(
            EvidenceResolutionStatus.CONFLICT,
            OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT,
        )

    area_m2 = width_mm * height_mm / 1_000_000.0
    payload = {
        "schema_version": OPENING_JOINERY_FIGURED_AREA_SCHEMA_VERSION,
        "opening_record_id": opening.record_id,
        "document_id": opening.document_id,
        "revision_id": opening.revision_id,
        "source_sha256": opening.source_sha256,
        "snapshot_id": opening.snapshot_id,
        "viewport_id": opening.viewport_id,
        "width_mm": width_mm,
        "height_mm": height_mm,
        "label_evidence_id": label.evidence_id,
        "joinery_height_evidence_id": height.evidence_id,
    }
    evidence = OpeningJoineryFiguredAreaEvidence(
        evidence_id=stable_contract_id(
            "opening_joinery_figured_area",
            payload,
            digest_chars=32,
        ),
        opening_record_id=opening.record_id,
        document_id=opening.document_id,
        revision_id=opening.revision_id,
        source_sha256=opening.source_sha256,
        snapshot_id=opening.snapshot_id,
        viewport_id=opening.viewport_id,
        width_mm=width_mm,
        height_mm=height_mm,
        area_m2=area_m2,
        label_evidence_id=label.evidence_id,
        joinery_height_evidence_id=height.evidence_id,
        source_text_observation_ids=tuple(
            dict.fromkeys(
                (
                    *label.source_text_observation_ids,
                    *height.source_text_observation_ids,
                )
            )
        ),
    )
    return OpeningJoineryFiguredAreaResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(OPENING_JOINERY_FIGURED_AREA_RESOLVED,),
        evidence=evidence,
    )


__all__ = [
    "OPENING_JOINERY_FIGURED_AREA_KIND_REQUIRED",
    "OPENING_JOINERY_FIGURED_AREA_LINEAGE_CONFLICT",
    "OPENING_JOINERY_FIGURED_AREA_RESOLVED",
    "OPENING_JOINERY_FIGURED_AREA_SCHEMA_VERSION",
    "OPENING_JOINERY_FIGURED_AREA_SINGLE_WIDTH_REQUIRED",
    "OPENING_JOINERY_FIGURED_AREA_UNAVAILABLE",
    "OpeningJoineryFiguredAreaEvidence",
    "OpeningJoineryFiguredAreaResult",
    "resolve_opening_joinery_figured_area",
]
