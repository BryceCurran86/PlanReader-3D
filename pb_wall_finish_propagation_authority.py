"""Wall-finish quantity propagation authority by exact physical wall identity (Item 19A).

Item 19A is intentionally fail-closed and has no positive publication path.

Caller-supplied ``WallFinishAssignment`` values (material, trade, face
target, including ``both_faces``) are diagnostic/request information only.
A caller cannot establish which physical wall face receives a finish, nor
which trade/material applies to it -- an exact-class dataclass and a sealed
producer/authority boundary authenticate *shape*, not *provenance*. Proving
finish/face binding requires a producer-owned, source-derived binding (a
future Item 19B authority, e.g. from a documented finish schedule or
specification bound to the exact physical wall face) that does not exist
yet in this codebase.

Until that authority exists, ``publish()`` unconditionally abstains with
``WALL_FINISH_BINDING_UNAVAILABLE`` once the wall and net-wall geometry
prerequisites are themselves verified -- it never reaches a CORROBORATED
result, never applies a ``both_faces`` area multiplier, and never
publishes a numeric authoritative quantity from caller input. Scope-level
aggregation mirrors this: ``total_trade_area_m2`` is always ``None`` and
``is_scope_complete`` is always ``False`` (unless zero assignments were
requested), because no wall in scope can ever resolve to a real quantity.

Do not add a positive publication path here. Item 19B (a real
producer-owned finish/face binding authority) is a separate, later,
research-gated workstream.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)

WALL_FINISH_PROPAGATION_SCHEMA_VERSION = "2.0.0"

WALL_FINISH_PHYSICAL_WALL_UNRESOLVED = "wall_finish_physical_wall_unresolved"
WALL_FINISH_NET_GEOMETRY_UNRESOLVED = "wall_finish_net_geometry_unresolved"
WALL_FINISH_ASSIGNMENT_UNAVAILABLE = "wall_finish_assignment_unavailable"
WALL_FINISH_ASSIGNMENT_CONFLICT = "wall_finish_assignment_conflict"
WALL_FINISH_BINDING_UNAVAILABLE = "wall_finish_binding_unavailable"
WALL_FINISH_LINEAGE_MISMATCH = "wall_finish_lineage_mismatch"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_WallKey = tuple[str, str, str, str, str, str, str, str]  # doc, rev, sha, snap, page, scope, wall_id, trade_id


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


@dataclass(frozen=True)
class WallFinishAssignment:
    """Caller-facing diagnostic finish claim -- never measurement authority.

    May be supplied for diagnostics / replay only. Cannot mint CORROBORATED
    wall-finish quantity; missing a producer-owned finish/face binding
    always fails closed with ``WALL_FINISH_BINDING_UNAVAILABLE``.
    """

    assignment_id: str
    physical_wall_id: str
    trade_scope_id: str
    wall_face_target: str  # "left_face", "right_face", "both_faces"
    finish_material: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.assignment_id, "assignment_id")
        _require_nonempty(self.physical_wall_id, "physical_wall_id")
        _require_nonempty(self.trade_scope_id, "trade_scope_id")
        if self.wall_face_target not in {"left_face", "right_face", "both_faces"}:
            raise ValueError(f"Invalid wall_face_target: {self.wall_face_target}")


@dataclass(frozen=True)
class WallFinishPropagationSelector:
    """Consumer addressing selector for wall finish propagation."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    trade_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "page_id", "decision_scope_id", "physical_wall_id", "trade_scope_id",
        ):
            _require_nonempty(getattr(self, name), name)

    @property
    def key(self) -> _WallKey:
        return (
            self.document_id, self.revision_id, self.source_sha256, self.snapshot_id,
            self.page_id, self.decision_scope_id, self.physical_wall_id, self.trade_scope_id,
        )


@dataclass(frozen=True)
class WallFinishScopeSummaryRecord:
    """Aggregation across all requested physical walls in a decision scope
    for a trade. Always incomplete with ``total_trade_area_m2 is None`` --
    Item 19A never resolves any wall to a real quantity."""

    trade_scope_id: str
    total_trade_area_m2: Optional[float]
    unit: str
    contributing_wall_records: tuple[object, ...]
    unresolved_wall_ids: tuple[str, ...]
    is_scope_complete: bool
    schema_version: str = WALL_FINISH_PROPAGATION_SCHEMA_VERSION


@dataclass(frozen=True)
class WallFinishPropagationResult:
    """Result envelope for wall finish propagation. ``record`` is always
    ``None`` in Item 19A -- there is no positive publication path."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: None = None
    schema_version: str = WALL_FINISH_PROPAGATION_SCHEMA_VERSION


def _blocked(status: EvidenceResolutionStatus, reason: str, *extra_reasons: str) -> WallFinishPropagationResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys([reason, *(r for r in extra_reasons if r)]))
    return WallFinishPropagationResult(status=status, reason_codes=reasons, record=None)


class WallFinishPropagationAuthority:
    """Read-only exact-scope selector lookup for wall finish propagation."""

    def __init__(
        self,
        results: Mapping[_WallKey, WallFinishPropagationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishPropagationAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: WallFinishPropagationSelector) -> WallFinishPropagationResult:
        if type(selector) is not WallFinishPropagationSelector:
            raise TypeError("selector must be WallFinishPropagationSelector")
        return self._results.get(
            selector.key,
            _blocked(EvidenceResolutionStatus.ABSTAINED, WALL_FINISH_ASSIGNMENT_UNAVAILABLE),
        )


class WallFinishPropagationProducer:
    """Producer boundary for wall-finish quantity propagation (Item 19A)."""

    def __init__(
        self,
        physical_wall_authority: PhysicalWallCandidateAuthority,
        net_wall_authority: NetWallBooleanUnionAuthority,
        assignments: Sequence[WallFinishAssignment],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallFinishPropagationProducer must be obtained from from_authorities()")
        if type(physical_wall_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_authority must be PhysicalWallCandidateAuthority")
        if type(net_wall_authority) is not NetWallBooleanUnionAuthority:
            raise TypeError("net_wall_authority must be NetWallBooleanUnionAuthority")
        if not isinstance(assignments, Sequence) or isinstance(assignments, (str, bytes)):
            raise TypeError("assignments must be a sequence of WallFinishAssignment")
        for a in assignments:
            if type(a) is not WallFinishAssignment:
                raise TypeError("assignments must contain only WallFinishAssignment instances")

        self._physical_wall_auth = physical_wall_authority
        self._net_wall_auth = net_wall_authority
        self._assignments = tuple(assignments)
        self._results: dict[_WallKey, WallFinishPropagationResult] = {}

    @classmethod
    def from_authorities(
        cls,
        physical_wall_authority: PhysicalWallCandidateAuthority,
        net_wall_authority: NetWallBooleanUnionAuthority,
        assignments: Sequence[WallFinishAssignment],
    ) -> "WallFinishPropagationProducer":
        return cls(
            physical_wall_authority=physical_wall_authority,
            net_wall_authority=net_wall_authority,
            assignments=assignments,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> WallFinishPropagationAuthority:
        return WallFinishPropagationAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self, selector: WallFinishPropagationSelector, result: WallFinishPropagationResult
    ) -> WallFinishPropagationResult:
        self._results[selector.key] = result
        return result

    def publish(self, selector: WallFinishPropagationSelector) -> WallFinishPropagationResult:
        if type(selector) is not WallFinishPropagationSelector:
            raise TypeError("selector must be WallFinishPropagationSelector")

        matching_assignments = [
            a for a in self._assignments
            if a.physical_wall_id == selector.physical_wall_id and a.trade_scope_id == selector.trade_scope_id
        ]
        if not matching_assignments:
            return self._store(selector, _blocked(EvidenceResolutionStatus.ABSTAINED, WALL_FINISH_ASSIGNMENT_UNAVAILABLE))
        if len(matching_assignments) > 1:
            return self._store(selector, _blocked(EvidenceResolutionStatus.CONFLICT, WALL_FINISH_ASSIGNMENT_CONFLICT))
        assignment = matching_assignments[0]

        wall_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        )
        wall_scope_res = self._physical_wall_auth.resolve_scope(wall_sel)
        if (
            wall_scope_res is None
            or wall_scope_res.status is not EvidenceResolutionStatus.CORROBORATED
            or not wall_scope_res.records
        ):
            blocked_status = (
                wall_scope_res.status
                if wall_scope_res and wall_scope_res.status is not EvidenceResolutionStatus.CORROBORATED
                else EvidenceResolutionStatus.ABSTAINED
            )
            reason_codes = wall_scope_res.reason_codes if wall_scope_res else ()
            return self._store(selector, _blocked(blocked_status, WALL_FINISH_PHYSICAL_WALL_UNRESOLVED, *reason_codes))

        if (
            wall_scope_res.document_id != selector.document_id
            or wall_scope_res.source_sha256 != selector.source_sha256
            or wall_scope_res.revision_id != selector.revision_id
            or wall_scope_res.snapshot_id != selector.snapshot_id
            or wall_scope_res.page_id != selector.page_id
            or wall_scope_res.decision_scope_id != selector.decision_scope_id
        ):
            return self._store(
                selector,
                _blocked(EvidenceResolutionStatus.CONFLICT, WALL_FINISH_LINEAGE_MISMATCH, "physical_wall_scope_lineage_mismatch"),
            )

        matching_wall_records = [
            r for r in wall_scope_res.records
            if getattr(r, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "candidate_identity_id", None) == selector.physical_wall_id
        ]
        if not matching_wall_records:
            return self._store(
                selector,
                _blocked(EvidenceResolutionStatus.ABSTAINED, WALL_FINISH_PHYSICAL_WALL_UNRESOLVED, f"no_physical_wall_{selector.physical_wall_id}_in_scope"),
            )

        net_sel = NetWallBooleanUnionSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
            trade_scope_id=selector.trade_scope_id,
        )
        net_res = self._net_wall_auth.resolve(net_sel)
        if net_res is None or net_res.status is not EvidenceResolutionStatus.CORROBORATED or net_res.record is None:
            blocked_status = (
                net_res.status
                if net_res and net_res.status is not EvidenceResolutionStatus.CORROBORATED
                else EvidenceResolutionStatus.ABSTAINED
            )
            reason_codes = net_res.reason_codes if net_res else ()
            return self._store(selector, _blocked(blocked_status, WALL_FINISH_NET_GEOMETRY_UNRESOLVED, *reason_codes))

        net_record = net_res.record
        if net_record.physical_wall_id != selector.physical_wall_id:
            return self._store(
                selector,
                _blocked(EvidenceResolutionStatus.CONFLICT, WALL_FINISH_PHYSICAL_WALL_UNRESOLVED, "net_wall_physical_wall_id_mismatch"),
            )
        if (
            net_record.document_id != selector.document_id
            or net_record.revision_id != selector.revision_id
            or net_record.source_sha256 != selector.source_sha256
            or net_record.snapshot_id != selector.snapshot_id
            or net_record.page_id != selector.page_id
            or net_record.decision_scope_id != selector.decision_scope_id
            or (net_record.trade_scope_id and net_record.trade_scope_id != selector.trade_scope_id)
        ):
            return self._store(selector, _blocked(EvidenceResolutionStatus.CONFLICT, WALL_FINISH_LINEAGE_MISMATCH))

        # Wall and net-wall geometry are both verified. Item 19A still has
        # no positive publication path: no producer-owned finish/face
        # binding exists to authenticate which face(s) the caller's
        # assignment actually applies to, or under what trade/material.
        # Fail closed rather than trust the caller's own shape-valid claim.
        return self._store(
            selector,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                WALL_FINISH_BINDING_UNAVAILABLE,
                f"assignment_id={assignment.assignment_id}",
                f"physical_wall_id={selector.physical_wall_id}",
                f"trade_scope_id={selector.trade_scope_id}",
                f"caller_face_target={assignment.wall_face_target}",
            ),
        )

    def publish_scope_summary(
        self,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        decision_scope_id: str,
        trade_scope_id: str,
    ) -> WallFinishScopeSummaryRecord:
        """Aggregate all requested wall finishes for a trade scope.

        Always ``total_trade_area_m2 is None`` and ``is_scope_complete`` is
        ``False`` (unless there were zero assignments to begin with) -- no
        wall in Item 19A can ever resolve to a real quantity.
        """
        for val, name in (
            (document_id, "document_id"), (revision_id, "revision_id"),
            (source_sha256, "source_sha256"), (snapshot_id, "snapshot_id"),
            (page_id, "page_id"), (decision_scope_id, "decision_scope_id"),
            (trade_scope_id, "trade_scope_id"),
        ):
            _require_nonempty(val, name)

        target_assignments = [a for a in self._assignments if a.trade_scope_id == trade_scope_id]
        unresolved_walls: list[str] = []
        for assignment in target_assignments:
            sel = WallFinishPropagationSelector(
                document_id=document_id, revision_id=revision_id, source_sha256=source_sha256,
                snapshot_id=snapshot_id, page_id=page_id, decision_scope_id=decision_scope_id,
                physical_wall_id=assignment.physical_wall_id, trade_scope_id=trade_scope_id,
            )
            res = self.publish(sel)
            if res.status is not EvidenceResolutionStatus.CORROBORATED:
                unresolved_walls.append(assignment.physical_wall_id)

        unresolved_tuple = tuple(dict.fromkeys(unresolved_walls))
        # No wall can ever resolve to CORROBORATED in Item 19A, so
        # is_scope_complete is always False and total_trade_area_m2 is
        # always None -- there is nothing left to branch on here.
        return WallFinishScopeSummaryRecord(
            trade_scope_id=trade_scope_id,
            total_trade_area_m2=None,
            unit="m2",
            contributing_wall_records=(),
            unresolved_wall_ids=unresolved_tuple,
            is_scope_complete=False,
        )


__all__ = [
    "WALL_FINISH_ASSIGNMENT_CONFLICT",
    "WALL_FINISH_ASSIGNMENT_UNAVAILABLE",
    "WALL_FINISH_BINDING_UNAVAILABLE",
    "WALL_FINISH_LINEAGE_MISMATCH",
    "WALL_FINISH_NET_GEOMETRY_UNRESOLVED",
    "WALL_FINISH_PHYSICAL_WALL_UNRESOLVED",
    "WALL_FINISH_PROPAGATION_SCHEMA_VERSION",
    "WallFinishAssignment",
    "WallFinishPropagationAuthority",
    "WallFinishPropagationProducer",
    "WallFinishPropagationResult",
    "WallFinishPropagationSelector",
    "WallFinishScopeSummaryRecord",
]
