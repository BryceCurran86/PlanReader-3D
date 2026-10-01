"""Shadow structural-member count QuantityEvidence adapter.

Projects an already-resolved producer-owned StructuralMemberResolution into the
existing QuantityEvidence contract. This module does not discover, reconcile,
or admit structural members and is not wired to commercial publication.
"""
from __future__ import annotations

import re

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence, stable_contract_id
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_SCHEMA_VERSION,
    StructuralMemberResolution,
)

STRUCTURAL_MEMBER_COUNT_FAMILY = "structural_member_count"
STRUCTURAL_MEMBER_COUNT_FORMULA = "count_of_authenticated_physical_structural_members"
STRUCTURAL_MEMBER_COUNT_NOT_CORROBORATED = "structural_member_resolution_not_corroborated"
STRUCTURAL_MEMBER_COUNT_LINEAGE_INVALID = "structural_member_selector_lineage_invalid"
STRUCTURAL_MEMBER_COUNT_STATUS_INVALID = "structural_member_resolution_status_invalid"
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _selector_lineage_valid(resolution: StructuralMemberResolution) -> bool:
    selector = resolution.selector
    required = (
        selector.document_id,
        selector.revision_id,
        selector.snapshot_id,
        selector.decision_scope_id,
        selector.member_kind,
    )
    return all(str(value or "").strip() for value in required) and bool(
        _SHA256_RE.fullmatch(str(selector.source_sha256 or "").strip().lower())
    )


def _semantic_key(resolution: StructuralMemberResolution) -> str:
    selector = resolution.selector
    return (
        f"{STRUCTURAL_MEMBER_COUNT_FAMILY}:"
        f"{str(selector.member_kind).strip().lower()}:"
        f"{str(selector.decision_scope_id).strip()}"
    )


def _metadata(
    resolution: StructuralMemberResolution,
    *,
    physical_member_ids: tuple[str, ...],
) -> dict[str, object]:
    selector = resolution.selector
    return {
        "document_id": str(selector.document_id),
        "revision_id": str(selector.revision_id),
        "source_sha256": str(selector.source_sha256),
        "snapshot_id": str(selector.snapshot_id),
        "decision_scope_id": str(selector.decision_scope_id),
        "member_kind": str(selector.member_kind).strip().lower(),
        "physical_member_ids": list(physical_member_ids),
        "resolution_reason_codes": list(resolution.reason_codes),
    }


def build_structural_member_count_quantity(
    resolution: StructuralMemberResolution,
) -> QuantityEvidence:
    """Return exact count trace for one producer-owned structural resolution.

    CORROBORATED resolutions count only their published PhysicalStructuralMember
    identities. Every other resolution returns an abstained QuantityEvidence and
    never exposes object ids or a numeric value.
    """
    if type(resolution) is not StructuralMemberResolution:
        raise TypeError("resolution must be StructuralMemberResolution")

    selector = resolution.selector
    semantic_key = _semantic_key(resolution)
    status = resolution.status if type(resolution.status) is EvidenceResolutionStatus else None
    lineage_valid = _selector_lineage_valid(resolution)
    raw_member_ids = tuple(
        str(member.physical_member_id or "").strip() for member in resolution.members
    )
    member_ids = tuple(sorted(raw_member_ids))
    selector_kind = str(selector.member_kind).strip().lower()
    member_identity_valid = (
        bool(member_ids)
        and all(member_ids)
        and len(set(member_ids)) == len(member_ids)
        and all(
            str(member.member_kind).strip().lower() == selector_kind
            for member in resolution.members
        )
    )

    payload = {
        "family": STRUCTURAL_MEMBER_COUNT_FAMILY,
        "semantic_key": semantic_key,
        "document_id": str(selector.document_id),
        "revision_id": str(selector.revision_id),
        "source_sha256": str(selector.source_sha256),
        "snapshot_id": str(selector.snapshot_id),
        "decision_scope_id": str(selector.decision_scope_id),
        "member_kind": str(selector.member_kind).strip().lower(),
        "physical_member_ids": member_ids,
        "resolution_status": status.value if status is not None else "invalid",
    }
    quantity_id = stable_contract_id("qty_structural_member_count", payload)

    if status is not EvidenceResolutionStatus.CORROBORATED or not lineage_valid:
        extra_reason = (
            STRUCTURAL_MEMBER_COUNT_STATUS_INVALID
            if status is None
            else STRUCTURAL_MEMBER_COUNT_LINEAGE_INVALID
            if not lineage_valid
            else STRUCTURAL_MEMBER_COUNT_NOT_CORROBORATED
        )
        blocking = tuple(
            dict.fromkeys(
                str(reason)
                for reason in (
                    *resolution.reason_codes,
                    extra_reason,
                    STRUCTURAL_MEMBER_COUNT_NOT_CORROBORATED,
                )
                if str(reason)
            )
        )
        return QuantityEvidence(
            quantity_id=quantity_id,
            family=STRUCTURAL_MEMBER_COUNT_FAMILY,
            semantic_key=semantic_key,
            value=None,
            unit="NO",
            input_entity_ids=(),
            formula=STRUCTURAL_MEMBER_COUNT_FORMULA,
            formula_version=STRUCTURAL_MEMBER_SCHEMA_VERSION,
            evidence_ids=(),
            authority=MeasurementAuthorityType.MODEL_DERIVED.value,
            status=AuthorityStatus.BLOCKED.value,
            confidence=0.0,
            abstained=True,
            blocking_reasons=blocking,
            reason_codes=tuple(resolution.reason_codes),
            metadata=_metadata(resolution, physical_member_ids=()),
        )

    if not member_identity_valid:
        # A CORROBORATED result without unique, non-empty physical identities
        # matching the selector kind is internally inconsistent. Fail closed
        # instead of counting rows.
        return QuantityEvidence(
            quantity_id=quantity_id,
            family=STRUCTURAL_MEMBER_COUNT_FAMILY,
            semantic_key=semantic_key,
            value=None,
            unit="NO",
            input_entity_ids=(),
            formula=STRUCTURAL_MEMBER_COUNT_FORMULA,
            formula_version=STRUCTURAL_MEMBER_SCHEMA_VERSION,
            evidence_ids=(),
            authority=MeasurementAuthorityType.MODEL_DERIVED.value,
            status=AuthorityStatus.BLOCKED.value,
            confidence=0.0,
            abstained=True,
            blocking_reasons=("structural_member_physical_identity_invalid",),
            reason_codes=("structural_member_physical_identity_invalid",),
            metadata=_metadata(resolution, physical_member_ids=()),
        )

    evidence_ids = tuple(
        sorted(
            {
                str(evidence_id)
                for member in resolution.members
                for evidence_id in member.source_evidence_ids
                if str(evidence_id)
            }
        )
    )
    return QuantityEvidence(
        quantity_id=quantity_id,
        family=STRUCTURAL_MEMBER_COUNT_FAMILY,
        semantic_key=semantic_key,
        value=float(len(member_ids)),
        unit="NO",
        input_entity_ids=member_ids,
        formula=STRUCTURAL_MEMBER_COUNT_FORMULA,
        formula_version=STRUCTURAL_MEMBER_SCHEMA_VERSION,
        evidence_ids=evidence_ids,
        authority=MeasurementAuthorityType.MODEL_DERIVED.value,
        status=AuthorityStatus.FIRM.value,
        confidence=1.0,
        abstained=False,
        metadata=_metadata(resolution, physical_member_ids=member_ids),
    )


__all__ = [
    "STRUCTURAL_MEMBER_COUNT_FAMILY",
    "STRUCTURAL_MEMBER_COUNT_FORMULA",
    "STRUCTURAL_MEMBER_COUNT_LINEAGE_INVALID",
    "STRUCTURAL_MEMBER_COUNT_NOT_CORROBORATED",
    "STRUCTURAL_MEMBER_COUNT_STATUS_INVALID",
    "build_structural_member_count_quantity",
]
