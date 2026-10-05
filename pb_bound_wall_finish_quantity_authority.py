"""Source-bound wall-finish quantity authority.

This authority is the positive downstream companion to Item 19A/19B.

It consumes only:
1. producer-owned source-derived WallFinishFaceBindingAuthority; and
2. producer-owned NetWallBooleanUnionAuthority.

A numeric finish quantity can publish only when the finish authority proves a
COMPLETE exact physical-face universe for one trade/material and every covered
face resolves to authenticated net-wall geometry. Caller assignments, nearest
matching, page-wide finish keywords, expected benchmark values, and confidence
ranking are not inputs.

One exact physical face contributes one net-wall area. Replayed/duplicate source
evidence for the same physical_face_id is deduplicated. Two distinct proven
physical faces of the same physical wall may each contribute once when both are
members of the complete source-owned target-face universe.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionSelector,
)
from pb_wall_finish_surface_identity import physical_wall_finish_surface_id
from pb_wall_finish_face_binding_authority import (
    FinishScopeStatus,
    WallFinishFaceBindingAuthority,
    WallFinishFaceBindingScopeSelector,
)

SOURCE_BOUND_WALL_FINISH_QUANTITY_SCHEMA_VERSION = "1.0.0"

FINISH_QUANTITY_RESOLVED = "source_bound_wall_finish_quantity_resolved"
FINISH_QUANTITY_BINDING_SCOPE_UNAVAILABLE = "source_bound_wall_finish_binding_scope_unavailable"
FINISH_QUANTITY_SCOPE_INCOMPLETE = "source_bound_wall_finish_scope_incomplete"
FINISH_QUANTITY_SCOPE_CONFLICT = "source_bound_wall_finish_scope_conflict"
FINISH_QUANTITY_BINDING_MISSING = "source_bound_wall_finish_binding_missing"
FINISH_QUANTITY_BINDING_LINEAGE_MISMATCH = "source_bound_wall_finish_binding_lineage_mismatch"
FINISH_QUANTITY_FACE_UNIVERSE_MISMATCH = "source_bound_wall_finish_face_universe_mismatch"
FINISH_QUANTITY_NET_WALL_UNRESOLVED = "source_bound_wall_finish_net_wall_unresolved"
FINISH_QUANTITY_NET_WALL_LINEAGE_MISMATCH = "source_bound_wall_finish_net_wall_lineage_mismatch"
FINISH_QUANTITY_INVALID_AREA = "source_bound_wall_finish_invalid_area"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = tuple[str, str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class SourceBoundWallFinishQuantitySelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str
    trade_scope_id: str
    finish_material: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "viewport_id",
            "decision_scope_id",
            "trade_scope_id",
            "finish_material",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
            self.decision_scope_id,
            self.trade_scope_id,
            self.finish_material,
        )


@dataclass(frozen=True)
class SourceBoundWallFinishQuantityRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    decision_scope_id: str
    trade_scope_id: str
    finish_material: str
    quantity_m2: float
    physical_face_ids: tuple[str, ...]
    physical_wall_ids: tuple[str, ...]
    physical_surface_ids: tuple[str, ...]
    finish_binding_ids: tuple[str, ...]
    net_wall_record_ids: tuple[str, ...]
    finish_scope_record_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    schema_version: str = SOURCE_BOUND_WALL_FINISH_QUANTITY_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceBoundWallFinishQuantityRecord is producer-owned")
        if self.status is not EvidenceResolutionStatus.CORROBORATED:
            raise ValueError("positive quantity record must be CORROBORATED")
        if not math.isfinite(float(self.quantity_m2)) or float(self.quantity_m2) <= 0.0:
            raise ValueError("quantity_m2 must be finite and positive")
        if not self.physical_face_ids:
            raise ValueError("positive quantity requires physical faces")
        if len(set(self.physical_face_ids)) != len(self.physical_face_ids):
            raise ValueError("physical_face_ids must be unique")
        if not self.physical_surface_ids:
            raise ValueError("positive quantity requires physical finish surfaces")
        if len(set(self.physical_surface_ids)) != len(self.physical_surface_ids):
            raise ValueError("physical_surface_ids must be unique")
        if len(self.physical_surface_ids) != len(self.physical_face_ids):
            raise ValueError("each physical face must map to one physical finish surface")


@dataclass(frozen=True)
class SourceBoundWallFinishQuantityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceBoundWallFinishQuantityRecord | None = None
    schema_version: str = SOURCE_BOUND_WALL_FINISH_QUANTITY_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream_reasons: str,
) -> SourceBoundWallFinishQuantityResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(
        dict.fromkeys([reason, *(str(value) for value in upstream_reasons if str(value))])
    )
    return SourceBoundWallFinishQuantityResult(
        status=status,
        reason_codes=reasons,
        record=None,
    )


class SourceBoundWallFinishQuantityAuthority:
    def __init__(
        self,
        results: Mapping[_Key, SourceBoundWallFinishQuantityResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceBoundWallFinishQuantityAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: SourceBoundWallFinishQuantitySelector,
    ) -> SourceBoundWallFinishQuantityResult:
        if type(selector) is not SourceBoundWallFinishQuantitySelector:
            raise TypeError("selector must be SourceBoundWallFinishQuantitySelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                FINISH_QUANTITY_BINDING_SCOPE_UNAVAILABLE,
            ),
        )


class SourceBoundWallFinishQuantityProducer:
    def __init__(
        self,
        finish_binding_authority: WallFinishFaceBindingAuthority,
        net_wall_authority: NetWallBooleanUnionAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "SourceBoundWallFinishQuantityProducer must be obtained from_authorities()"
            )
        if type(finish_binding_authority) is not WallFinishFaceBindingAuthority:
            raise TypeError(
                "finish_binding_authority must be WallFinishFaceBindingAuthority"
            )
        if type(net_wall_authority) is not NetWallBooleanUnionAuthority:
            raise TypeError("net_wall_authority must be NetWallBooleanUnionAuthority")
        self._finish = finish_binding_authority
        self._net = net_wall_authority
        self._results: dict[_Key, SourceBoundWallFinishQuantityResult] = {}

    @classmethod
    def from_authorities(
        cls,
        finish_binding_authority: WallFinishFaceBindingAuthority,
        net_wall_authority: NetWallBooleanUnionAuthority,
    ) -> "SourceBoundWallFinishQuantityProducer":
        return cls(
            finish_binding_authority,
            net_wall_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> SourceBoundWallFinishQuantityAuthority:
        return SourceBoundWallFinishQuantityAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        selector: SourceBoundWallFinishQuantitySelector,
        result: SourceBoundWallFinishQuantityResult,
    ) -> SourceBoundWallFinishQuantityResult:
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            result = _blocked(
                EvidenceResolutionStatus.CONFLICT,
                FINISH_QUANTITY_SCOPE_CONFLICT,
                "finish_quantity_producer_equivocation",
            )
        self._results[selector.key] = result
        return result

    @staticmethod
    def _scope_lineage_matches(selector, record) -> bool:
        return all(
            getattr(record, name, None) == getattr(selector, name)
            for name in (
                "document_id",
                "revision_id",
                "source_sha256",
                "snapshot_id",
                "page_id",
                "viewport_id",
                "decision_scope_id",
            )
        )

    @staticmethod
    def _binding_lineage_matches(selector, binding) -> bool:
        return all(
            getattr(binding, name, None) == getattr(selector, name)
            for name in (
                "document_id",
                "revision_id",
                "source_sha256",
                "snapshot_id",
                "page_id",
                "viewport_id",
                "decision_scope_id",
            )
        )

    @staticmethod
    def _net_lineage_matches(selector, record) -> bool:
        return all(
            getattr(record, name, None) == getattr(selector, name)
            for name in (
                "document_id",
                "revision_id",
                "source_sha256",
                "snapshot_id",
                "page_id",
                "decision_scope_id",
            )
        )

    def publish(
        self,
        selector: SourceBoundWallFinishQuantitySelector,
    ) -> SourceBoundWallFinishQuantityResult:
        if type(selector) is not SourceBoundWallFinishQuantitySelector:
            raise TypeError("selector must be SourceBoundWallFinishQuantitySelector")

        finish_selector = WallFinishFaceBindingScopeSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=selector.viewport_id,
            decision_scope_id=selector.decision_scope_id,
        )
        finish_result = self._finish.resolve_scope(finish_selector)
        if finish_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _blocked(
                    finish_result.status,
                    FINISH_QUANTITY_BINDING_SCOPE_UNAVAILABLE,
                    *finish_result.reason_codes,
                ),
            )

        matching_scopes = [
            scope
            for scope in finish_result.scope_records
            if scope.trade_scope_id == selector.trade_scope_id
            and scope.finish_material == selector.finish_material
        ]
        if not matching_scopes:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    FINISH_QUANTITY_BINDING_SCOPE_UNAVAILABLE,
                ),
            )
        if len(matching_scopes) != 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    FINISH_QUANTITY_SCOPE_CONFLICT,
                    "multiple_finish_scope_records",
                ),
            )

        scope = matching_scopes[0]
        if not self._scope_lineage_matches(selector, scope):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    FINISH_QUANTITY_BINDING_LINEAGE_MISMATCH,
                    "finish_scope_lineage_mismatch",
                ),
            )
        if scope.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _blocked(
                    scope.status,
                    FINISH_QUANTITY_SCOPE_CONFLICT,
                    *scope.reason_codes,
                ),
            )
        target_faces = tuple(sorted(set(scope.target_face_ids)))
        covered_faces = tuple(sorted(set(scope.covered_face_ids)))
        if (
            scope.decision_scope_complete is not True
            or scope.scope_status is not FinishScopeStatus.COMPLETE
            or not target_faces
            or target_faces != covered_faces
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    FINISH_QUANTITY_SCOPE_INCOMPLETE,
                    *scope.reason_codes,
                ),
            )

        bindings_by_id = {binding.binding_id: binding for binding in finish_result.bindings}
        required_binding_ids = tuple(sorted(set(scope.binding_ids)))
        if not required_binding_ids or any(
            binding_id not in bindings_by_id
            for binding_id in required_binding_ids
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    FINISH_QUANTITY_BINDING_MISSING,
                ),
            )

        face_bindings: dict[str, object] = {}
        for binding_id in required_binding_ids:
            binding = bindings_by_id[binding_id]
            if not self._binding_lineage_matches(selector, binding):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        FINISH_QUANTITY_BINDING_LINEAGE_MISMATCH,
                        f"binding_id={binding_id}",
                    ),
                )
            if (
                binding.status is not EvidenceResolutionStatus.CORROBORATED
                or binding.trade_scope_id != selector.trade_scope_id
                or binding.finish_material != selector.finish_material
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        FINISH_QUANTITY_SCOPE_CONFLICT,
                        f"binding_id={binding_id}",
                    ),
                )
            if binding.physical_face_id not in target_faces:
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        FINISH_QUANTITY_FACE_UNIVERSE_MISMATCH,
                        f"binding_id={binding_id}",
                    ),
                )
            previous = face_bindings.get(binding.physical_face_id)
            if previous is not None and (
                getattr(previous, "physical_wall_id", None) != binding.physical_wall_id
                or getattr(previous, "physical_face_role", None) != binding.physical_face_role
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        FINISH_QUANTITY_SCOPE_CONFLICT,
                        f"physical_face_id={binding.physical_face_id}",
                    ),
                )
            face_bindings.setdefault(binding.physical_face_id, binding)

        if tuple(sorted(face_bindings)) != target_faces:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    FINISH_QUANTITY_FACE_UNIVERSE_MISMATCH,
                ),
            )

        quantity_m2 = 0.0
        net_record_ids: set[str] = set()
        physical_wall_ids: set[str] = set()
        physical_surface_ids: set[str] = set()

        for face_id in target_faces:
            binding = face_bindings[face_id]
            wall_id = str(getattr(binding, "physical_wall_id"))
            net_selector = NetWallBooleanUnionSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                physical_wall_id=wall_id,
                trade_scope_id=selector.trade_scope_id,
            )
            net_result = self._net.resolve(net_selector)
            net_record = net_result.record
            if (
                net_result.status is not EvidenceResolutionStatus.CORROBORATED
                or net_record is None
                or NET_WALL_BOOLEAN_UNION_RESOLVED not in net_result.reason_codes
            ):
                return self._store(
                    selector,
                    _blocked(
                        net_result.status,
                        FINISH_QUANTITY_NET_WALL_UNRESOLVED,
                        *net_result.reason_codes,
                    ),
                )
            if (
                not self._net_lineage_matches(selector, net_record)
                or net_record.physical_wall_id != wall_id
                or net_record.trade_scope_id != selector.trade_scope_id
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        FINISH_QUANTITY_NET_WALL_LINEAGE_MISMATCH,
                        f"physical_face_id={face_id}",
                    ),
                )
            area = net_record.net_area_m2
            if (
                area is None
                or not math.isfinite(float(area))
                or float(area) <= 0.0
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.ABSTAINED,
                        FINISH_QUANTITY_INVALID_AREA,
                        f"physical_face_id={face_id}",
                    ),
                )
            quantity_m2 += float(area)
            net_record_ids.add(net_record.record_id)
            physical_wall_ids.add(wall_id)
            physical_surface_ids.add(
                physical_wall_finish_surface_id(
                    document_id=selector.document_id,
                    physical_wall_id=wall_id,
                    physical_face_id=face_id,
                    trade_scope_id=selector.trade_scope_id,
                )
            )

        finish_binding_ids = tuple(sorted(required_binding_ids))
        net_ids = tuple(sorted(net_record_ids))
        wall_ids = tuple(sorted(physical_wall_ids))
        surface_ids = tuple(sorted(physical_surface_ids))
        payload = {
            "selector": selector.key,
            "finish_scope_record_id": scope.scope_id,
            "physical_face_ids": target_faces,
            "physical_wall_ids": wall_ids,
            "physical_surface_ids": surface_ids,
            "finish_binding_ids": finish_binding_ids,
            "net_wall_record_ids": net_ids,
            "quantity_m2": round(quantity_m2, 12),
            "schema_version": SOURCE_BOUND_WALL_FINISH_QUANTITY_SCHEMA_VERSION,
        }
        record = SourceBoundWallFinishQuantityRecord(
            record_id=stable_contract_id(
                "source_bound_wall_finish_quantity",
                payload,
                digest_chars=32,
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=selector.viewport_id,
            decision_scope_id=selector.decision_scope_id,
            trade_scope_id=selector.trade_scope_id,
            finish_material=selector.finish_material,
            quantity_m2=quantity_m2,
            physical_face_ids=target_faces,
            physical_wall_ids=wall_ids,
            physical_surface_ids=surface_ids,
            finish_binding_ids=finish_binding_ids,
            net_wall_record_ids=net_ids,
            finish_scope_record_id=scope.scope_id,
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(FINISH_QUANTITY_RESOLVED,),
            _seal=_RECORD_SEAL,
        )
        return self._store(
            selector,
            SourceBoundWallFinishQuantityResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(FINISH_QUANTITY_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "FINISH_QUANTITY_BINDING_LINEAGE_MISMATCH",
    "FINISH_QUANTITY_BINDING_MISSING",
    "FINISH_QUANTITY_BINDING_SCOPE_UNAVAILABLE",
    "FINISH_QUANTITY_FACE_UNIVERSE_MISMATCH",
    "FINISH_QUANTITY_INVALID_AREA",
    "FINISH_QUANTITY_NET_WALL_LINEAGE_MISMATCH",
    "FINISH_QUANTITY_NET_WALL_UNRESOLVED",
    "FINISH_QUANTITY_RESOLVED",
    "FINISH_QUANTITY_SCOPE_CONFLICT",
    "FINISH_QUANTITY_SCOPE_INCOMPLETE",
    "SOURCE_BOUND_WALL_FINISH_QUANTITY_SCHEMA_VERSION",
    "SourceBoundWallFinishQuantityAuthority",
    "SourceBoundWallFinishQuantityProducer",
    "SourceBoundWallFinishQuantityRecord",
    "SourceBoundWallFinishQuantityResult",
    "SourceBoundWallFinishQuantitySelector",
]
