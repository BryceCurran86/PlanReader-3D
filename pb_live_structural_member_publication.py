"""Live publication boundary for corroborated physical structural members.

Consumes only the producer-sealed structural-member authority. It cannot accept
caller counts, expected quantities, nearest-choice hints, or legacy guessed
structural counts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)
from pb_structural_member_authority import (
    StructuralMemberAuthority,
    StructuralMemberSelector,
)


LIVE_STRUCTURAL_MEMBER_PUBLICATION_SCHEMA_VERSION = "1.0.0"
LIVE_STRUCTURAL_MEMBER_PUBLICATION_RESOLVED = (
    "live_structural_member_publication_resolved"
)
LIVE_STRUCTURAL_MEMBER_PUBLICATION_UNAVAILABLE = (
    "live_structural_member_publication_unavailable"
)


@dataclass(frozen=True)
class LiveStructuralMemberPublication:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    definition_id: str
    scope_id: str
    physical_member_ids: tuple[str, ...]
    quantity_evidence: Optional[QuantityEvidence]
    schema_version: str = LIVE_STRUCTURAL_MEMBER_PUBLICATION_SCHEMA_VERSION


def publish_live_structural_member_quantity(
    *,
    authority: StructuralMemberAuthority,
    selector: StructuralMemberSelector,
) -> LiveStructuralMemberPublication:
    """Publish count evidence only from corroborated physical member identities."""
    if type(authority) is not StructuralMemberAuthority:
        raise TypeError("authority must be producer-owned StructuralMemberAuthority")
    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")

    result = authority.resolve(selector)
    if (
        result.status is not EvidenceResolutionStatus.CORROBORATED
        or result.quantity is None
        or result.quantity <= 0
        or not result.physical_member_ids
    ):
        return LiveStructuralMemberPublication(
            status=result.status,
            reason_codes=tuple(
                dict.fromkeys(
                    (
                        LIVE_STRUCTURAL_MEMBER_PUBLICATION_UNAVAILABLE,
                        *result.reason_codes,
                    )
                )
            ),
            definition_id=selector.definition_id,
            scope_id=selector.scope_id,
            physical_member_ids=(),
            quantity_evidence=None,
        )

    payload = {
        "document_id": selector.document_id,
        "revision_id": selector.revision_id,
        "source_sha256": selector.source_sha256,
        "snapshot_id": selector.snapshot_id,
        "scope_id": selector.scope_id,
        "definition_id": selector.definition_id,
        "physical_member_ids": result.physical_member_ids,
        "source_evidence_ids": result.source_evidence_ids,
    }
    quantity_id = stable_contract_id(
        "structural_member_quantity_v1",
        payload,
        digest_chars=32,
    )
    evidence = QuantityEvidence(
        quantity_id=quantity_id,
        family="structural_member_count",
        semantic_key=f"structural_member:{selector.definition_id}",
        value=float(result.quantity),
        unit="NO",
        input_entity_ids=tuple(result.physical_member_ids),
        formula="count(unique source-authenticated physical structural member identities)",
        formula_version=LIVE_STRUCTURAL_MEMBER_PUBLICATION_SCHEMA_VERSION,
        evidence_ids=tuple(result.source_evidence_ids),
        authority="source_owned_structural_member_identity",
        status=EvidenceResolutionStatus.CORROBORATED.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=(LIVE_STRUCTURAL_MEMBER_PUBLICATION_RESOLVED,),
        metadata={
            "definition_id": selector.definition_id,
            "scope_id": selector.scope_id,
            "source_page_ids": result.source_page_ids,
            "source_view_ids": result.source_view_ids,
            "physical_member_ids": result.physical_member_ids,
            "member_candidate_groups": result.member_candidate_groups,
        },
    )
    return LiveStructuralMemberPublication(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(LIVE_STRUCTURAL_MEMBER_PUBLICATION_RESOLVED,),
        definition_id=selector.definition_id,
        scope_id=selector.scope_id,
        physical_member_ids=tuple(result.physical_member_ids),
        quantity_evidence=evidence,
    )


__all__ = [
    "LIVE_STRUCTURAL_MEMBER_PUBLICATION_RESOLVED",
    "LIVE_STRUCTURAL_MEMBER_PUBLICATION_SCHEMA_VERSION",
    "LIVE_STRUCTURAL_MEMBER_PUBLICATION_UNAVAILABLE",
    "LiveStructuralMemberPublication",
    "publish_live_structural_member_quantity",
]
