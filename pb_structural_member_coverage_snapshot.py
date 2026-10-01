"""Shadow coverage-universe snapshot for StructuralMemberAuthority results.

The adapter accepts only a StructuralMemberResolution and reissues its producer-
owned physical-member universe into the frozen coverage registry contract. It
never discovers, admits, or repairs structural members.
"""
from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import StructuralMemberResolution
from pb_takeoff_coverage_registry import (
    ENUMERATION_COMPLETE,
    ENUMERATION_INCOMPLETE,
    ProducerObjectUniverseSnapshotV1,
)

STRUCTURAL_COVERAGE_PRODUCER = "structural_member"
STRUCTURAL_COVERAGE_OWNING_AUTHORITY = "StructuralMemberAuthority"
STRUCTURAL_MEMBER_ENUMERATION_INCOMPLETE = "structural_member_enumeration_incomplete"
STRUCTURAL_MEMBER_ENUMERATION_IDENTITY_INVALID = (
    "structural_member_enumeration_identity_invalid"
)


def _identity_valid(resolution: StructuralMemberResolution) -> tuple[bool, tuple[str, ...]]:
    kind = str(resolution.selector.member_kind or "").strip().lower()
    ids = tuple(
        str(member.physical_member_id or "").strip()
        for member in resolution.members
    )
    valid = (
        bool(ids)
        and all(ids)
        and len(set(ids)) == len(ids)
        and all(
            str(member.member_kind or "").strip().lower() == kind
            for member in resolution.members
        )
    )
    return valid, tuple(sorted(ids)) if valid else ()


def structural_member_resolution_to_coverage_snapshot(
    resolution: StructuralMemberResolution,
    *,
    registry_run_id: str,
) -> ProducerObjectUniverseSnapshotV1:
    """Project one structural authority result into its exact coverage universe."""
    if type(resolution) is not StructuralMemberResolution:
        raise TypeError("resolution must be StructuralMemberResolution")

    selector = resolution.selector
    category = str(selector.member_kind or "").strip().lower()
    valid_identity, admitted_ids = _identity_valid(resolution)

    if (
        resolution.status is EvidenceResolutionStatus.CORROBORATED
        and valid_identity
    ):
        status = ENUMERATION_COMPLETE
        reasons = tuple(
            dict.fromkeys(str(reason) for reason in resolution.reason_codes if str(reason))
        )
    else:
        status = ENUMERATION_INCOMPLETE
        admitted_ids = ()
        extra = (
            STRUCTURAL_MEMBER_ENUMERATION_IDENTITY_INVALID
            if resolution.status is EvidenceResolutionStatus.CORROBORATED
            else STRUCTURAL_MEMBER_ENUMERATION_INCOMPLETE
        )
        reasons = tuple(
            dict.fromkeys(
                str(reason)
                for reason in (*resolution.reason_codes, extra)
                if str(reason)
            )
        )

    return ProducerObjectUniverseSnapshotV1(
        producer=STRUCTURAL_COVERAGE_PRODUCER,
        owning_authority=STRUCTURAL_COVERAGE_OWNING_AUTHORITY,
        category=category,
        source_document_id=str(selector.document_id or "").strip(),
        revision_id=str(selector.revision_id or "").strip(),
        source_sha256=str(selector.source_sha256 or "").strip().lower(),
        registry_run_id=str(registry_run_id or "").strip(),
        snapshot_id=str(selector.snapshot_id or "").strip(),
        admitted_object_ids=admitted_ids,
        enumeration_status=status,
        reason_codes=reasons,
    )


__all__ = [
    "STRUCTURAL_COVERAGE_OWNING_AUTHORITY",
    "STRUCTURAL_COVERAGE_PRODUCER",
    "STRUCTURAL_MEMBER_ENUMERATION_IDENTITY_INVALID",
    "STRUCTURAL_MEMBER_ENUMERATION_INCOMPLETE",
    "structural_member_resolution_to_coverage_snapshot",
]
