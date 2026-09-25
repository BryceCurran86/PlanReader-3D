"""Source-owned bridge from Item19B viewport wall identity to page wall identity.

A direct finish callout is intentionally resolved inside an authenticated
viewport, while downstream opening/net-wall composition historically addresses
page wall scopes.  This module bridges those scopes only through immutable
source primitive ownership already sealed into a
WallFinishFaceBindingRecord.

No coordinate matching, nearest-wall selection, confidence ranking, or caller
geometry is accepted.  If the exact source face primitives do not resolve to
one target physical-wall equivalence group, the bridge abstains.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_wall_finish_face_binding_authority import WallFinishFaceBindingRecord


WALL_FINISH_SCOPE_BRIDGE_SCHEMA_VERSION = "1.0.0"
WALL_FINISH_SCOPE_BRIDGE_RESOLVED = "wall_finish_scope_bridge_resolved"
WALL_FINISH_SCOPE_BRIDGE_UNAVAILABLE = "wall_finish_scope_bridge_unavailable"
WALL_FINISH_SCOPE_BRIDGE_LINEAGE_MISMATCH = "wall_finish_scope_bridge_lineage_mismatch"
WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED = (
    "wall_finish_scope_bridge_source_wall_unresolved"
)
WALL_FINISH_SCOPE_BRIDGE_TARGET_WALL_UNRESOLVED = (
    "wall_finish_scope_bridge_target_wall_unresolved"
)
WALL_FINISH_SCOPE_BRIDGE_AMBIGUOUS_TARGET = "wall_finish_scope_bridge_ambiguous_target"


@dataclass(frozen=True)
class WallFinishScopeBridgeRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    finish_binding_id: str
    source_wall_decision_scope_id: str
    source_physical_wall_id: str
    target_wall_decision_scope_id: str
    target_physical_wall_id: str
    source_face_primitive_ids: tuple[str, ...]
    target_member_wall_ids: tuple[str, ...]
    shared_source_primitive_ids: tuple[str, ...]
    schema_version: str = WALL_FINISH_SCOPE_BRIDGE_SCHEMA_VERSION


@dataclass(frozen=True)
class WallFinishScopeBridgeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[WallFinishScopeBridgeRecord] = None
    schema_version: str = WALL_FINISH_SCOPE_BRIDGE_SCHEMA_VERSION


def _blocked(
    reason: str,
    *,
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
    extras: tuple[str, ...] = (),
) -> WallFinishScopeBridgeResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return WallFinishScopeBridgeResult(
        status=status,
        reason_codes=tuple(dict.fromkeys((reason, *extras))),
        record=None,
    )


def _group_for_wall(equivalence, wall_id: str) -> tuple[str, ...]:
    if equivalence is None:
        return (wall_id,)
    matches = [
        tuple(sorted(group))
        for group in tuple(equivalence.equivalence_groups or ())
        if wall_id in group
    ]
    if len(matches) > 1:
        return ()
    return matches[0] if matches else (wall_id,)


def _target_group_for_owners(equivalence, owner_ids: set[str]) -> tuple[str, ...]:
    """Return one positive SAME group covering every exact raw owner.

    A singleton owner is acceptable only as a singleton.  If exact primitive
    ownership lands in two unrelated groups, no identity is manufactured.
    """
    if not owner_ids:
        return ()
    groups = [_group_for_wall(equivalence, owner) for owner in sorted(owner_ids)]
    if any(not group for group in groups):
        return ()
    canonical = {tuple(group) for group in groups}
    if len(canonical) != 1:
        return ()
    group = next(iter(canonical))
    if not owner_ids <= set(group):
        return ()
    return group


def bridge_finish_binding_to_page_wall(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    binding_record: WallFinishFaceBindingRecord,
) -> WallFinishScopeBridgeResult:
    """Bridge one producer-owned direct finish binding to its page wall scope.

    The caller supplies no wall geometry and cannot nominate the target wall.
    The target is discovered solely by replaying exact source primitive
    ownership from the binding into the producer-owned page wall universe.
    """
    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be an actual SourceVisibilityProducer")
    if type(binding_record) is not WallFinishFaceBindingRecord:
        raise TypeError("binding_record must be a producer-owned WallFinishFaceBindingRecord")

    published = source_visibility_producer.published_snapshot_for_revision(
        binding_record.revision_id
    )
    if published is None:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_UNAVAILABLE)
    if (
        published.revision.document_id != binding_record.document_id
        or published.revision.revision_id != binding_record.revision_id
        or published.revision.source_sha256 != binding_record.source_sha256
        or published.snapshot.snapshot_id != binding_record.snapshot_id
    ):
        return _blocked(
            WALL_FINISH_SCOPE_BRIDGE_LINEAGE_MISMATCH,
            status=EvidenceResolutionStatus.CONFLICT,
        )

    page_id = str(binding_record.page_id)
    viewport_authority = PhysicalWallCandidateProducer.from_authenticated_viewports(
        source_visibility_producer,
        page_ids=(page_id,),
    ).authority()
    page_authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source_visibility_producer,
        page_ids=(page_id,),
    ).authority()

    source_selector = viewport_authority.selector_for_decision_scope(
        document_id=binding_record.document_id,
        revision_id=binding_record.revision_id,
        source_sha256=binding_record.source_sha256,
        snapshot_id=binding_record.snapshot_id,
        page_id=page_id,
        decision_scope_id=binding_record.physical_wall_decision_scope_id,
    )
    if source_selector is None:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED)
    source_scope = viewport_authority.resolve_scope(source_selector)
    if (
        source_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not source_scope.records
    ):
        return _blocked(
            WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED,
            extras=tuple(source_scope.reason_codes),
        )

    source_group = _group_for_wall(
        source_scope.equivalence,
        binding_record.physical_wall_id,
    )
    if not source_group:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED)
    if not any(
        record.wall_candidate_id == binding_record.physical_wall_id
        for record in source_scope.records
    ):
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED)

    face_raw_ids = tuple(
        sorted({str(value) for value in binding_record.source_face_segment_ids if str(value)})
    )
    if not face_raw_ids:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED)
    source_group_records = [
        record for record in source_scope.records
        if record.wall_candidate_id in set(source_group)
    ]
    source_group_raw_ids = {
        str(raw_id)
        for record in source_group_records
        for raw_id in record.physical_identity.source_primitive_ids
    }
    if not set(face_raw_ids) <= source_group_raw_ids:
        return _blocked(
            WALL_FINISH_SCOPE_BRIDGE_LINEAGE_MISMATCH,
            status=EvidenceResolutionStatus.CONFLICT,
        )

    target_scope_id = f"wall-source:page-{page_id}"
    target_selector = page_authority.selector_for_decision_scope(
        document_id=binding_record.document_id,
        revision_id=binding_record.revision_id,
        source_sha256=binding_record.source_sha256,
        snapshot_id=binding_record.snapshot_id,
        page_id=page_id,
        decision_scope_id=target_scope_id,
    )
    if target_selector is None:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_TARGET_WALL_UNRESOLVED)
    target_scope = page_authority.resolve_scope(target_selector)
    if (
        target_scope.status is not EvidenceResolutionStatus.CORROBORATED
        or not target_scope.records
    ):
        return _blocked(
            WALL_FINISH_SCOPE_BRIDGE_TARGET_WALL_UNRESOLVED,
            extras=tuple(target_scope.reason_codes),
        )

    face_set = set(face_raw_ids)
    target_owners = {
        record.wall_candidate_id
        for record in target_scope.records
        if face_set & set(record.physical_identity.source_primitive_ids)
    }
    if not target_owners:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_TARGET_WALL_UNRESOLVED)

    target_group = _target_group_for_owners(
        target_scope.equivalence,
        target_owners,
    )
    if not target_group:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_AMBIGUOUS_TARGET)

    target_group_raw_ids = {
        str(raw_id)
        for record in target_scope.records
        if record.wall_candidate_id in set(target_group)
        for raw_id in record.physical_identity.source_primitive_ids
    }
    shared = tuple(sorted(face_set & target_group_raw_ids))
    if set(shared) != face_set:
        return _blocked(WALL_FINISH_SCOPE_BRIDGE_AMBIGUOUS_TARGET)

    target_id = sorted(target_group)[0]
    payload = {
        "document_id": binding_record.document_id,
        "revision_id": binding_record.revision_id,
        "source_sha256": binding_record.source_sha256,
        "snapshot_id": binding_record.snapshot_id,
        "page_id": page_id,
        "finish_binding_id": binding_record.binding_id,
        "source_wall_decision_scope_id": binding_record.physical_wall_decision_scope_id,
        "source_physical_wall_id": binding_record.physical_wall_id,
        "target_wall_decision_scope_id": target_scope_id,
        "target_physical_wall_id": target_id,
        "source_face_primitive_ids": face_raw_ids,
        "target_member_wall_ids": target_group,
        "shared_source_primitive_ids": shared,
    }
    record = WallFinishScopeBridgeRecord(
        record_id=stable_contract_id(
            "wall_finish_scope_bridge",
            payload,
            digest_chars=32,
        ),
        **payload,
    )
    return WallFinishScopeBridgeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(WALL_FINISH_SCOPE_BRIDGE_RESOLVED,),
        record=record,
    )


__all__ = [
    "WALL_FINISH_SCOPE_BRIDGE_AMBIGUOUS_TARGET",
    "WALL_FINISH_SCOPE_BRIDGE_LINEAGE_MISMATCH",
    "WALL_FINISH_SCOPE_BRIDGE_RESOLVED",
    "WALL_FINISH_SCOPE_BRIDGE_SCHEMA_VERSION",
    "WALL_FINISH_SCOPE_BRIDGE_SOURCE_WALL_UNRESOLVED",
    "WALL_FINISH_SCOPE_BRIDGE_TARGET_WALL_UNRESOLVED",
    "WALL_FINISH_SCOPE_BRIDGE_UNAVAILABLE",
    "WallFinishScopeBridgeRecord",
    "WallFinishScopeBridgeResult",
    "bridge_finish_binding_to_page_wall",
]
