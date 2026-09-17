"""Wall-finish and quantity propagation authority by exact physical wall identity (Item 19).

Proves and publishes quantity takeoff and wall-finish evidence by propagating
surface finishes across exact physical wall identities (physical_wall_id).

Key invariants:
1. Exact Physical Wall Identity:
   - Finishes are bound strictly to exact physical_wall_id / PhysicalWallIdentity.
   - Distinct physical walls NEVER get merged into a lossy anonymous lump.
   - Every finish record preserves its physical wall lineage and candidate IDs.
2. Net Area Propagation Respects Boolean Union (Item 17):
   - Propagates net wall area derived from NetWallBooleanUnionAuthority.
   - Applies face multipliers (left_face=1.0, right_face=1.0, both_faces=2.0).
3. Fail-Closed on Unresolved Net Wall Geometry:
   - If NetWallBooleanUnionAuthority is not CORROBORATED for the wall and trade scope,
     finish quantity propagation fails closed with ABSTAINED / CONFLICT and
     WALL_FINISH_NET_GEOMETRY_UNRESOLVED.
   - Total finish area remains None; no fabricated or naive gross quantities are emitted.
4. Scope Summary Completeness:
   - Aggregations across physical walls for a trade scope fail closed
     (total_trade_area_m2 = None) if ANY contributing wall net geometry is unresolved.
5. Strict Lineage Integrity:
   - Requires document_id, revision_id, source_sha256, snapshot_id, page_id, and
     decision_scope_id to match across finish assignments and upstream authorities.
6. Sealed Producer/Authority Architecture:
   - Constructed exclusively via WallFinishPropagationProducer.from_authorities().
   - Consumer addressing only via immutable selectors.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import math
from types import MappingProxyType
from typing import Any, Optional

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_net_wall_boolean_union_authority import (
    NET_WALL_BOOLEAN_UNION_RESOLVED,
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionRecord,
    NetWallBooleanUnionSelector,
)
from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateRecord,
    PhysicalWallCandidateSelector,
)

WALL_FINISH_PROPAGATION_SCHEMA_VERSION = "1.0.0"

WALL_FINISH_PROPAGATION_RESOLVED = "wall_finish_propagation_resolved"
WALL_FINISH_NET_GEOMETRY_UNRESOLVED = "wall_finish_net_geometry_unresolved"
WALL_FINISH_PHYSICAL_WALL_UNRESOLVED = "wall_finish_physical_wall_unresolved"
WALL_FINISH_ASSIGNMENT_UNAVAILABLE = "wall_finish_assignment_unavailable"
WALL_FINISH_ASSIGNMENT_CONFLICT = "wall_finish_assignment_conflict"
WALL_FINISH_LINEAGE_MISMATCH = "wall_finish_lineage_mismatch"
WALL_FINISH_FACE_AMBIGUOUS = "wall_finish_face_ambiguous"
WALL_FINISH_SCOPE_INCOMPLETE = "wall_finish_scope_incomplete"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_WallKey = tuple[str, str, str, str, str, str, str, str]  # doc, rev, sha, snap, page, scope, wall_id, trade_id
_ScopeKey = tuple[str, str, str, str, str, str, str]  # doc, rev, sha, snap, page, scope, trade_id


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WallFinishAssignment:
    """Authenticated assignment of a surface finish trade to a physical wall."""

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
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.page_id, "page_id")
        _require_nonempty(self.decision_scope_id, "decision_scope_id")
        _require_nonempty(self.physical_wall_id, "physical_wall_id")
        _require_nonempty(self.trade_scope_id, "trade_scope_id")

    @property
    def key(self) -> _WallKey:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.physical_wall_id,
            self.trade_scope_id,
        )

    @property
    def scope_key(self) -> _ScopeKey:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.trade_scope_id,
        )


@dataclass(frozen=True)
class WallFinishPropagationRecord:
    """Immutable quantity takeoff publication record for a single physical wall finish."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    trade_scope_id: str
    assignment_id: str
    wall_face_target: str
    net_area_per_face_m2: float
    face_multiplier: float
    total_finish_area_m2: float
    unit: str = "m2"
    net_wall_record_id: str = ""
    gross_geometry_record_id: str = ""
    contributing_candidate_ids: tuple[str, ...] = ()
    is_authoritative: bool = True
    schema_version: str = WALL_FINISH_PROPAGATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.physical_wall_id, "physical_wall_id")
        _require_nonempty(self.trade_scope_id, "trade_scope_id")
        if self.face_multiplier not in {1.0, 2.0}:
            raise ValueError("face_multiplier must be 1.0 or 2.0")
        if not math.isfinite(self.total_finish_area_m2) or self.total_finish_area_m2 < 0.0:
            raise ValueError("total_finish_area_m2 must be a non-negative finite float")


@dataclass(frozen=True)
class WallFinishScopeSummaryRecord:
    """Immutable aggregation across all physical walls in a decision scope for a trade."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    trade_scope_id: str
    total_trade_area_m2: Optional[float]
    unit: str
    contributing_wall_records: tuple[WallFinishPropagationRecord, ...]
    unresolved_wall_ids: tuple[str, ...]
    is_scope_complete: bool
    schema_version: str = WALL_FINISH_PROPAGATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.trade_scope_id, "trade_scope_id")


@dataclass(frozen=True)
class WallFinishPropagationResult:
    """Result envelope for wall finish propagation."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[WallFinishPropagationRecord] = None
    summary: Optional[WallFinishScopeSummaryRecord] = None
    schema_version: str = WALL_FINISH_PROPAGATION_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra_reasons: str,
    summary: Optional[WallFinishScopeSummaryRecord] = None,
) -> WallFinishPropagationResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys([reason, *(r for r in extra_reasons if r)]))
    return WallFinishPropagationResult(
        status=status,
        reason_codes=reasons,
        record=None,
        summary=summary,
    )


# ---------------------------------------------------------------------------
# Authority and Producer
# ---------------------------------------------------------------------------

class WallFinishPropagationAuthority:
    """Read-only exact-scope selector lookup for wall finish propagation."""

    def __init__(
        self,
        results: Mapping[_WallKey, WallFinishPropagationResult],
        scope_summaries: Mapping[_ScopeKey, WallFinishScopeSummaryRecord],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallFinishPropagationAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))
        self._scope_summaries = MappingProxyType(dict(scope_summaries))

    def resolve(
        self, selector: WallFinishPropagationSelector
    ) -> WallFinishPropagationResult:
        if type(selector) is not WallFinishPropagationSelector:
            raise TypeError("selector must be WallFinishPropagationSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                WALL_FINISH_ASSIGNMENT_UNAVAILABLE,
            ),
        )

    def resolve_scope_summary(
        self,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        decision_scope_id: str,
        trade_scope_id: str,
    ) -> Optional[WallFinishScopeSummaryRecord]:
        key = (
            document_id,
            revision_id,
            source_sha256,
            snapshot_id,
            page_id,
            decision_scope_id,
            trade_scope_id,
        )
        return self._scope_summaries.get(key)


class WallFinishPropagationProducer:
    """Producer constructing verified wall finish quantity propagation evidence."""

    def __init__(
        self,
        physical_wall_authority: PhysicalWallCandidateAuthority,
        net_wall_authority: NetWallBooleanUnionAuthority,
        assignments: Sequence[WallFinishAssignment],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "WallFinishPropagationProducer must be obtained from from_authorities()"
            )
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
        self._scope_summaries: dict[_ScopeKey, WallFinishScopeSummaryRecord] = {}

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
        return WallFinishPropagationAuthority(
            self._results,
            self._scope_summaries,
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        selector: WallFinishPropagationSelector,
        result: WallFinishPropagationResult,
    ) -> WallFinishPropagationResult:
        self._results[selector.key] = result
        return result

    def publish(
        self, selector: WallFinishPropagationSelector
    ) -> WallFinishPropagationResult:
        if type(selector) is not WallFinishPropagationSelector:
            raise TypeError("selector must be WallFinishPropagationSelector")

        # 1. Locate matching finish assignment
        matching_assignments = [
            a
            for a in self._assignments
            if a.physical_wall_id == selector.physical_wall_id
            and a.trade_scope_id == selector.trade_scope_id
        ]
        if not matching_assignments:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    WALL_FINISH_ASSIGNMENT_UNAVAILABLE,
                ),
            )
        if len(matching_assignments) > 1:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WALL_FINISH_ASSIGNMENT_CONFLICT,
                ),
            )

        assignment = matching_assignments[0]

        # 2. Verify Physical Wall Candidate Exists
        wall_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
        )
        resolve_wall_fn = getattr(self._physical_wall_auth, "resolve_scope", None) or getattr(self._physical_wall_auth, "resolve")
        wall_scope_res = resolve_wall_fn(wall_sel)
        if (
            wall_scope_res is None
            or wall_scope_res.status is not EvidenceResolutionStatus.CORROBORATED
            or not hasattr(wall_scope_res, "records")
            or not wall_scope_res.records
        ):
            blocked_status = (
                wall_scope_res.status
                if wall_scope_res and wall_scope_res.status is not EvidenceResolutionStatus.CORROBORATED
                else EvidenceResolutionStatus.ABSTAINED
            )
            reason_codes = wall_scope_res.reason_codes if wall_scope_res else ()
            return self._store(
                selector,
                _blocked(
                    blocked_status,
                    WALL_FINISH_PHYSICAL_WALL_UNRESOLVED,
                    *reason_codes,
                ),
            )

        # Match exact physical wall identity
        matching_wall_records = [
            r
            for r in wall_scope_res.records
            if getattr(r, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "candidate_identity_id", None) == selector.physical_wall_id
        ]
        if not matching_wall_records:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    WALL_FINISH_PHYSICAL_WALL_UNRESOLVED,
                    f"no_physical_wall_{selector.physical_wall_id}_in_scope",
                ),
            )

        candidate_ids = tuple(
            r.wall_candidate_id
            for r in matching_wall_records
            if getattr(r, "wall_candidate_id", None)
        )

        # 3. Resolve Net Wall Boolean Union Geometry (Item 17 Prerequisite)
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

        # Fail closed if net wall geometry is unresolved or missing
        if (
            net_res is None
            or net_res.status is not EvidenceResolutionStatus.CORROBORATED
            or net_res.record is None
        ):
            blocked_status = (
                net_res.status
                if net_res and net_res.status is not EvidenceResolutionStatus.CORROBORATED
                else EvidenceResolutionStatus.ABSTAINED
            )
            reason_codes = net_res.reason_codes if net_res else ()
            return self._store(
                selector,
                _blocked(
                    blocked_status,
                    WALL_FINISH_NET_GEOMETRY_UNRESOLVED,
                    *reason_codes,
                ),
            )

        net_record: NetWallBooleanUnionRecord = net_res.record

        # Strict validation of net_record:
        # A. Net area must be present, finite, and non-negative
        if (
            net_record.net_area_m2 is None
            or not math.isfinite(net_record.net_area_m2)
            or net_record.net_area_m2 < 0.0
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WALL_FINISH_NET_GEOMETRY_UNRESOLVED,
                    "net_area_unresolved_or_invalid",
                ),
            )

        # B. Gross geometry record ID must be present
        if not net_record.gross_geometry_record_id:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WALL_FINISH_NET_GEOMETRY_UNRESOLVED,
                    "missing_gross_geometry_record_id",
                ),
            )

        # C. Exact physical wall identity match on the net wall record
        if net_record.physical_wall_id != selector.physical_wall_id:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WALL_FINISH_PHYSICAL_WALL_UNRESOLVED,
                    "net_wall_physical_wall_id_mismatch",
                ),
            )

        # D. Strict Lineage match
        if (
            net_record.document_id != selector.document_id
            or net_record.revision_id != selector.revision_id
            or net_record.source_sha256 != selector.source_sha256
            or net_record.snapshot_id != selector.snapshot_id
            or net_record.page_id != selector.page_id
            or net_record.decision_scope_id != selector.decision_scope_id
            or (net_record.trade_scope_id and net_record.trade_scope_id != selector.trade_scope_id)
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WALL_FINISH_LINEAGE_MISMATCH,
                ),
            )

        # 4. Calculate Face Multiplier and Total Finish Area
        face_target = assignment.wall_face_target
        if face_target == "both_faces":
            face_mult = 2.0
        elif face_target in {"left_face", "right_face"}:
            face_mult = 1.0
        else:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WALL_FINISH_FACE_AMBIGUOUS,
                ),
            )

        net_face_area = net_record.net_area_m2
        total_finish_area = round(net_face_area * face_mult, 4)

        # 5. Build WallFinishPropagationRecord
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "trade_scope_id": selector.trade_scope_id,
            "assignment_id": assignment.assignment_id,
            "wall_face_target": face_target,
            "net_area_per_face_m2": net_face_area,
            "face_multiplier": face_mult,
            "total_finish_area_m2": total_finish_area,
            "unit": "m2",
            "net_wall_record_id": net_record.record_id,
            "gross_geometry_record_id": net_record.gross_geometry_record_id,
            "contributing_candidate_ids": candidate_ids,
        }
        record_id = stable_contract_id(
            "wall_finish_propagation_record", payload, digest_chars=32
        )
        record = WallFinishPropagationRecord(
            record_id=record_id,
            **payload,
        )

        result = WallFinishPropagationResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(WALL_FINISH_PROPAGATION_RESOLVED,),
            record=record,
        )
        return self._store(selector, result)

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
        """Aggregate all wall finishes for a trade scope, failing closed if any is unresolved."""
        scope_key = (
            document_id,
            revision_id,
            source_sha256,
            snapshot_id,
            page_id,
            decision_scope_id,
            trade_scope_id,
        )

        # Get relevant assignments
        target_assignments = [
            a for a in self._assignments if a.trade_scope_id == trade_scope_id
        ]

        contributing_records: list[WallFinishPropagationRecord] = []
        unresolved_walls: list[str] = []

        for assignment in target_assignments:
            sel = WallFinishPropagationSelector(
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                snapshot_id=snapshot_id,
                page_id=page_id,
                decision_scope_id=decision_scope_id,
                physical_wall_id=assignment.physical_wall_id,
                trade_scope_id=trade_scope_id,
            )
            res = self.publish(sel)
            if res.status is EvidenceResolutionStatus.CORROBORATED and res.record is not None:
                contributing_records.append(res.record)
            else:
                unresolved_walls.append(assignment.physical_wall_id)

        unresolved_tuple = tuple(dict.fromkeys(unresolved_walls))
        is_complete = (len(unresolved_tuple) == 0) and bool(contributing_records)
        total_trade_area = (
            round(sum(r.total_finish_area_m2 for r in contributing_records), 4)
            if is_complete
            else None
        )

        payload = {
            "document_id": document_id,
            "revision_id": revision_id,
            "source_sha256": source_sha256,
            "snapshot_id": snapshot_id,
            "page_id": page_id,
            "decision_scope_id": decision_scope_id,
            "trade_scope_id": trade_scope_id,
            "total_trade_area_m2": total_trade_area,
            "unit": "m2",
            "is_scope_complete": is_complete,
        }
        record_id = stable_contract_id(
            "wall_finish_scope_summary_record", payload, digest_chars=32
        )
        summary = WallFinishScopeSummaryRecord(
            record_id=record_id,
            contributing_wall_records=tuple(contributing_records),
            unresolved_wall_ids=unresolved_tuple,
            **payload,
        )
        self._scope_summaries[scope_key] = summary
        return summary


__all__ = [
    "WALL_FINISH_ASSIGNMENT_CONFLICT",
    "WALL_FINISH_ASSIGNMENT_UNAVAILABLE",
    "WALL_FINISH_FACE_AMBIGUOUS",
    "WALL_FINISH_LINEAGE_MISMATCH",
    "WALL_FINISH_NET_GEOMETRY_UNRESOLVED",
    "WALL_FINISH_PHYSICAL_WALL_UNRESOLVED",
    "WALL_FINISH_PROPAGATION_RESOLVED",
    "WALL_FINISH_PROPAGATION_SCHEMA_VERSION",
    "WALL_FINISH_SCOPE_INCOMPLETE",
    "WallFinishAssignment",
    "WallFinishPropagationAuthority",
    "WallFinishPropagationProducer",
    "WallFinishPropagationRecord",
    "WallFinishPropagationResult",
    "WallFinishPropagationSelector",
    "WallFinishScopeSummaryRecord",
]
