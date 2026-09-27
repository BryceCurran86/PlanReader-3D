"""Exact source-lineage bridge from viewport wall identity to page wall identity.

Item19B direct callouts are resolved inside authenticated viewports.  Existing
opening / deduction / net-wall composition addresses producer-owned page wall
scopes.  This authority bridges those identities only through immutable source
primitive ancestry already sealed into WallFinishCalloutWallBindingRecord.

No coordinates, proximity, wall dimensions, confidence ranking, project
identity, or benchmark values participate.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateScopeResult,
)
from pb_physical_wall_identity import PhysicalWallEquivalenceResolution
from pb_wall_finish_callout_wall_authority import (
    WallFinishCalloutWallBindingRecord,
    WallFinishCalloutWallProducer,
)


WALL_SCOPE_IDENTITY_BRIDGE_SCHEMA_VERSION = "1.0.0"
WALL_SCOPE_IDENTITY_BRIDGE_RESOLVED = "wall_scope_identity_bridge_resolved"
WALL_SCOPE_IDENTITY_BRIDGE_UNAVAILABLE = "wall_scope_identity_bridge_unavailable"
WALL_SCOPE_IDENTITY_BRIDGE_LINEAGE_MISMATCH = "wall_scope_identity_bridge_lineage_mismatch"
WALL_SCOPE_IDENTITY_BRIDGE_TARGET_SCOPE_INVALID = "wall_scope_identity_bridge_target_scope_invalid"
WALL_SCOPE_IDENTITY_BRIDGE_SOURCE_PRIMITIVE_UNOWNED = (
    "wall_scope_identity_bridge_source_primitive_unowned"
)
WALL_SCOPE_IDENTITY_BRIDGE_TARGET_AMBIGUOUS = "wall_scope_identity_bridge_target_ambiguous"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()


@dataclass(frozen=True)
class WallScopeIdentityBridgeRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    source_binding_id: str
    source_viewport_id: str
    source_wall_scope_id: str
    source_physical_wall_id: str
    target_page_scope_id: str
    target_physical_wall_id: str
    target_equivalence_group_wall_ids: tuple[str, ...]
    source_wall_primitive_ids: tuple[str, ...]
    raw_target_owner_wall_ids: tuple[str, ...]
    shared_source_primitive_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = WALL_SCOPE_IDENTITY_BRIDGE_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallScopeIdentityBridgeRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive bridge record must be CORROBORATED")
        if not self.source_wall_primitive_ids:
            raise ValueError("source_wall_primitive_ids are required")
        if not self.raw_target_owner_wall_ids:
            raise ValueError("raw_target_owner_wall_ids are required")
        if self.target_physical_wall_id not in self.target_equivalence_group_wall_ids:
            raise ValueError("target_physical_wall_id must belong to target group")


@dataclass(frozen=True)
class WallScopeIdentityBridgeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: WallScopeIdentityBridgeRecord | None = None
    schema_version: str = WALL_SCOPE_IDENTITY_BRIDGE_SCHEMA_VERSION


@dataclass(frozen=True)
class WallScopeIdentityBridgeSelector:
    source_binding_id: str

    def __post_init__(self) -> None:
        if not str(self.source_binding_id or "").strip():
            raise ValueError("source_binding_id must be non-empty")


def _blocked(reason: str, *, conflict: bool = False) -> WallScopeIdentityBridgeResult:
    return WallScopeIdentityBridgeResult(
        status=(
            EvidenceResolutionStatus.CONFLICT
            if conflict
            else EvidenceResolutionStatus.ABSTAINED
        ),
        reason_codes=(reason,),
        record=None,
    )


def _group_for_owner(
    equivalence: PhysicalWallEquivalenceResolution | None,
    wall_id: str,
) -> tuple[str, ...]:
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


def _resolve_exact_target_group(
    *,
    page_scope: PhysicalWallCandidateScopeResult,
    source_primitive_ids: tuple[str, ...],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]] | None:
    """Return (group, raw owners, shared ids) from exact primitive ownership.

    Every requested source primitive must be owned by at least one page wall
    candidate.  All such owners must normalize to exactly one positive physical
    equivalence group.  This function never ranks among candidate groups.
    """
    requested = tuple(sorted({str(raw) for raw in source_primitive_ids if str(raw)}))
    if not requested:
        return None

    owners_by_raw: dict[str, set[str]] = {raw: set() for raw in requested}
    source_ids_by_wall: dict[str, set[str]] = {}
    for record in tuple(page_scope.records or ()):
        wall_id = str(record.wall_candidate_id)
        ids = {
            str(raw)
            for raw in tuple(record.physical_identity.source_primitive_ids or ())
            if str(raw)
        }
        source_ids_by_wall[wall_id] = ids
        for raw in requested:
            if raw in ids:
                owners_by_raw[raw].add(wall_id)

    if any(not owners for owners in owners_by_raw.values()):
        return None

    raw_owners = tuple(sorted({wall for owners in owners_by_raw.values() for wall in owners}))
    normalized_groups = {
        _group_for_owner(page_scope.equivalence, wall_id)
        for wall_id in raw_owners
    }
    if any(not group for group in normalized_groups) or len(normalized_groups) != 1:
        return ((), raw_owners, requested)

    group = next(iter(normalized_groups))
    group_source_ids = {
        raw
        for wall_id in group
        for raw in source_ids_by_wall.get(wall_id, set())
    }
    if not set(requested) <= group_source_ids:
        return ((), raw_owners, requested)
    return (tuple(group), raw_owners, requested)


class WallScopeIdentityBridgeAuthority:
    def __init__(
        self,
        results: Mapping[str, WallScopeIdentityBridgeResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallScopeIdentityBridgeAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: WallScopeIdentityBridgeSelector,
    ) -> WallScopeIdentityBridgeResult:
        if type(selector) is not WallScopeIdentityBridgeSelector:
            raise TypeError("selector must be WallScopeIdentityBridgeSelector")
        return self._results.get(
            selector.source_binding_id,
            _blocked(WALL_SCOPE_IDENTITY_BRIDGE_UNAVAILABLE),
        )


class WallScopeIdentityBridgeProducer:
    def __init__(
        self,
        results: Mapping[str, WallScopeIdentityBridgeResult],
        *,
        _seal=None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallScopeIdentityBridgeProducer is producer-owned")
        self._results = MappingProxyType(dict(results))

    @classmethod
    def from_authorities(
        cls,
        *,
        callout_wall_producer: WallFinishCalloutWallProducer,
        page_wall_authority: PhysicalWallCandidateAuthority,
    ) -> "WallScopeIdentityBridgeProducer":
        if type(callout_wall_producer) is not WallFinishCalloutWallProducer:
            raise TypeError("callout_wall_producer must be producer-owned")
        if type(page_wall_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("page_wall_authority must be producer-owned")

        page_scopes: dict[tuple[str, ...], PhysicalWallCandidateScopeResult] = {}
        for scope in page_wall_authority._scopes.values():
            if str(getattr(scope, "scope_kind", "page")) != "page":
                continue
            expected_scope_id = f"wall-source:page-{scope.page_id}"
            if scope.decision_scope_id != expected_scope_id:
                continue
            key = (
                scope.document_id,
                scope.revision_id,
                scope.source_sha256,
                scope.snapshot_id,
                scope.page_id,
            )
            if key in page_scopes:
                # Two page scopes with the same immutable lineage is itself
                # an invalid target universe; exclude both by storing None-like
                # ambiguity through a sentinel list later.
                page_scopes[key] = None  # type: ignore[assignment]
            else:
                page_scopes[key] = scope

        results: dict[str, WallScopeIdentityBridgeResult] = {}
        for scope_result in callout_wall_producer.published_results():
            for binding in scope_result.bindings:
                lineage = (
                    binding.document_id,
                    binding.revision_id,
                    binding.source_sha256,
                    binding.snapshot_id,
                    binding.page_id,
                )
                page_scope = page_scopes.get(lineage)
                if page_scope is None:
                    results[binding.binding_id] = _blocked(
                        WALL_SCOPE_IDENTITY_BRIDGE_UNAVAILABLE
                    )
                    continue
                if (
                    page_scope.document_id != binding.document_id
                    or page_scope.revision_id != binding.revision_id
                    or page_scope.source_sha256 != binding.source_sha256
                    or page_scope.snapshot_id != binding.snapshot_id
                    or page_scope.page_id != binding.page_id
                ):
                    results[binding.binding_id] = _blocked(
                        WALL_SCOPE_IDENTITY_BRIDGE_LINEAGE_MISMATCH,
                        conflict=True,
                    )
                    continue
                if (
                    str(page_scope.scope_kind) != "page"
                    or page_scope.decision_scope_id != f"wall-source:page-{binding.page_id}"
                    or page_scope.status is not EvidenceResolutionStatus.CORROBORATED
                ):
                    results[binding.binding_id] = _blocked(
                        WALL_SCOPE_IDENTITY_BRIDGE_TARGET_SCOPE_INVALID
                    )
                    continue

                resolution = _resolve_exact_target_group(
                    page_scope=page_scope,
                    source_primitive_ids=tuple(binding.source_wall_primitive_ids),
                )
                if resolution is None:
                    results[binding.binding_id] = _blocked(
                        WALL_SCOPE_IDENTITY_BRIDGE_SOURCE_PRIMITIVE_UNOWNED
                    )
                    continue
                group, raw_owners, shared = resolution
                if not group:
                    results[binding.binding_id] = _blocked(
                        WALL_SCOPE_IDENTITY_BRIDGE_TARGET_AMBIGUOUS
                    )
                    continue

                representatives = set(
                    tuple(
                        getattr(page_scope.equivalence, "representative_wall_ids", ())
                        or ()
                    )
                )
                group_reps = tuple(sorted(set(group) & representatives))
                if len(group) == 1:
                    target_id = group[0]
                elif len(group_reps) == 1:
                    target_id = group_reps[0]
                else:
                    # Identity group is positive, but downstream needs one
                    # producer-selected physical wall handle. Do not invent it.
                    results[binding.binding_id] = _blocked(
                        WALL_SCOPE_IDENTITY_BRIDGE_TARGET_AMBIGUOUS
                    )
                    continue

                payload = {
                    "document_id": binding.document_id,
                    "revision_id": binding.revision_id,
                    "source_sha256": binding.source_sha256,
                    "snapshot_id": binding.snapshot_id,
                    "page_id": binding.page_id,
                    "source_binding_id": binding.binding_id,
                    "source_viewport_id": binding.viewport_id,
                    "source_wall_scope_id": binding.physical_wall_decision_scope_id,
                    "source_physical_wall_id": binding.physical_wall_id,
                    "target_page_scope_id": page_scope.decision_scope_id,
                    "target_physical_wall_id": target_id,
                    "target_equivalence_group_wall_ids": tuple(group),
                    "source_wall_primitive_ids": tuple(sorted(binding.source_wall_primitive_ids)),
                    "raw_target_owner_wall_ids": tuple(raw_owners),
                    "shared_source_primitive_ids": tuple(shared),
                }
                record = WallScopeIdentityBridgeRecord(
                    record_id=stable_contract_id(
                        "wall_scope_identity_bridge",
                        payload,
                        digest_chars=32,
                    ),
                    **payload,
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=(WALL_SCOPE_IDENTITY_BRIDGE_RESOLVED,),
                    _seal=_RECORD_SEAL,
                )
                results[binding.binding_id] = WallScopeIdentityBridgeResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    reason_codes=(WALL_SCOPE_IDENTITY_BRIDGE_RESOLVED,),
                    record=record,
                )

        return cls(results, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallScopeIdentityBridgeAuthority:
        return WallScopeIdentityBridgeAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def published_results(self) -> tuple[WallScopeIdentityBridgeResult, ...]:
        return tuple(self._results[key] for key in sorted(self._results))


__all__ = [
    "WALL_SCOPE_IDENTITY_BRIDGE_LINEAGE_MISMATCH",
    "WALL_SCOPE_IDENTITY_BRIDGE_RESOLVED",
    "WALL_SCOPE_IDENTITY_BRIDGE_SCHEMA_VERSION",
    "WALL_SCOPE_IDENTITY_BRIDGE_SOURCE_PRIMITIVE_UNOWNED",
    "WALL_SCOPE_IDENTITY_BRIDGE_TARGET_AMBIGUOUS",
    "WALL_SCOPE_IDENTITY_BRIDGE_TARGET_SCOPE_INVALID",
    "WALL_SCOPE_IDENTITY_BRIDGE_UNAVAILABLE",
    "WallScopeIdentityBridgeAuthority",
    "WallScopeIdentityBridgeProducer",
    "WallScopeIdentityBridgeRecord",
    "WallScopeIdentityBridgeResult",
    "WallScopeIdentityBridgeSelector",
    "_resolve_exact_target_group",
]
