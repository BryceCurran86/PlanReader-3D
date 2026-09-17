"""Producer-owned generic wall & finish recovery authority (Item 28).

Generic recovery of wall and finish quantities across complex drawing packages:
- Integrates physical wall candidates, wall role, thickness/face geometry, opening deductions,
  and wall finish propagation.
- Classifies root cause for any unresolvable quantity without hardcoding project names,
  benchmark rows, or expected values:
    - WALL_INSTANCE_MISSING
    - WALL_ROLE_UNRESOLVED
    - WALL_LENGTH_UNRESOLVED
    - WALL_HEIGHT_UNRESOLVED
    - WALL_THICKNESS_UNRESOLVED
    - OPENING_DEDUCTION_UNRESOLVED
    - FINISH_ASSIGNMENT_UNRESOLVED
    - INCOMPLETE_SOURCE_VISIBILITY
    - CROSS_SHEET_EVIDENCE_MISSING
- Reusable across all drawing sets (Umma, Lamu, Ghazi, KSTVET, Murera).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

GHAZI_RECOVERY_SCHEMA_VERSION = "1.0.0"

# Public reason codes
GHAZI_RECOVERY_RESOLVED = "ghazi_wall_finish_recovery_resolved"
GHAZI_RECOVERY_UNRESOLVED = "ghazi_wall_finish_recovery_unresolved"
GHAZI_RECOVERY_LINEAGE_MISMATCH = "ghazi_wall_finish_recovery_lineage_mismatch"
GHAZI_RECOVERY_HARDCODED_VALUES_REJECTED = "ghazi_wall_finish_recovery_hardcoded_values_rejected"
GHAZI_RECOVERY_RECORD_UNAVAILABLE = "ghazi_wall_finish_recovery_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class GhaziRecoveryRootCause(str, Enum):
    """Root cause classification for wall/finish quantity resolution."""
    WALL_INSTANCE_MISSING = "wall_instance_missing"
    WALL_ROLE_UNRESOLVED = "wall_role_unresolved"
    WALL_LENGTH_UNRESOLVED = "wall_length_unresolved"
    WALL_HEIGHT_UNRESOLVED = "wall_height_unresolved"
    WALL_THICKNESS_UNRESOLVED = "wall_thickness_unresolved"
    OPENING_DEDUCTION_UNRESOLVED = "opening_deduction_unresolved"
    FINISH_ASSIGNMENT_UNRESOLVED = "finish_assignment_unresolved"
    INCOMPLETE_SOURCE_VISIBILITY = "incomplete_source_visibility"
    CROSS_SHEET_EVIDENCE_MISSING = "cross_sheet_evidence_missing"
    RESOLVED = "resolved"


@dataclass(frozen=True)
class GhaziWallFinishRecoverySelector:
    """Sealed selector identifying exact physical wall and trade scope for recovery."""
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
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
            "trade_scope_id",
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
            self.decision_scope_id,
            self.physical_wall_id,
            self.trade_scope_id,
        )


@dataclass(frozen=True)
class GhaziWallFinishRecoveryEvidence:
    """Authenticated evidence supporting generic wall & finish recovery."""
    evidence_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    gross_area_m2: float
    net_area_m2: float
    root_cause: GhaziRecoveryRootCause
    kind: str           # e.g. "authenticated_finish_propagation", "reusable_wall_deduction"
    confidence: float
    is_hardcoded: bool = False

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "source_sha256",
            "revision_id",
            "snapshot_id",
            "page_id",
            "viewport_id",
            "kind",
        ):
            _required(getattr(self, name), name)
        if not isinstance(self.root_cause, GhaziRecoveryRootCause):
            raise TypeError("root_cause must be GhaziRecoveryRootCause")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class GhaziWallFinishRecoveryRecord:
    """Sealed record for generic wall & finish quantity recovery."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    trade_scope_id: str
    root_cause: GhaziRecoveryRootCause
    gross_area_m2: float
    net_area_m2: float
    corroborating_evidence_ids: Tuple[str, ...]
    schema_version: str = GHAZI_RECOVERY_SCHEMA_VERSION


@dataclass(frozen=True)
class GhaziWallFinishRecoveryResult:
    """Result of wall & finish recovery authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[GhaziWallFinishRecoveryRecord] = None
    schema_version: str = GHAZI_RECOVERY_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> GhaziWallFinishRecoveryResult:
    return GhaziWallFinishRecoveryResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> GhaziWallFinishRecoveryResult:
    return GhaziWallFinishRecoveryResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class GhaziWallFinishRecoveryAuthority:
    """Sealed selector-only lookup for published recovery records."""

    def __init__(
        self,
        results: Mapping[_Key, GhaziWallFinishRecoveryResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("GhaziWallFinishRecoveryAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: GhaziWallFinishRecoverySelector) -> GhaziWallFinishRecoveryResult:
        if type(selector) is not GhaziWallFinishRecoverySelector:
            raise TypeError("selector must be GhaziWallFinishRecoverySelector")
        return self._results.get(
            selector.key,
            _abstained(GHAZI_RECOVERY_RECORD_UNAVAILABLE),
        )


class GhaziWallFinishRecoveryProducer:
    """Trusted writer boundary for generic wall & finish recovery authority."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("GhaziWallFinishRecoveryProducer must be obtained via create()")
        self._results: dict[_Key, GhaziWallFinishRecoveryResult] = {}

    @classmethod
    def create(cls) -> "GhaziWallFinishRecoveryProducer":
        return cls(_seal=_PRODUCER_SEAL)

    def authority(self) -> GhaziWallFinishRecoveryAuthority:
        return GhaziWallFinishRecoveryAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: GhaziWallFinishRecoverySelector,
        result: GhaziWallFinishRecoveryResult,
    ) -> GhaziWallFinishRecoveryResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: GhaziWallFinishRecoverySelector,
        observations: Sequence[GhaziWallFinishRecoveryEvidence],
    ) -> GhaziWallFinishRecoveryResult:
        """Publish authenticated generic wall & finish recovery for selector."""
        if type(selector) is not GhaziWallFinishRecoverySelector:
            raise TypeError("selector must be GhaziWallFinishRecoverySelector")

        obs = list(observations or [])
        if not obs:
            return self._store(selector, _abstained(GHAZI_RECOVERY_UNRESOLVED, GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value))

        valid_obs: list[GhaziWallFinishRecoveryEvidence] = []
        hardcoded_count = 0
        stale_count = 0

        for ob in obs:
            if not isinstance(ob, GhaziWallFinishRecoveryEvidence):
                continue
            if ob.is_hardcoded or "hardcoded" in ob.kind.lower():
                hardcoded_count += 1
                continue
            # Lineage match
            if (
                ob.source_sha256 != selector.source_sha256
                or ob.revision_id != selector.revision_id
                or ob.snapshot_id != selector.snapshot_id
                or ob.page_id != selector.page_id
            ):
                stale_count += 1
                continue
            valid_obs.append(ob)

        if hardcoded_count and not valid_obs:
            return self._store(selector, _abstained(GHAZI_RECOVERY_HARDCODED_VALUES_REJECTED))
        if stale_count and not valid_obs:
            return self._store(selector, _conflict(GHAZI_RECOVERY_LINEAGE_MISMATCH))
        if not valid_obs:
            return self._store(selector, _abstained(GHAZI_RECOVERY_UNRESOLVED))

        # Check root causes
        causes = {ob.root_cause for ob in valid_obs}
        if GhaziRecoveryRootCause.RESOLVED in causes and len(causes) > 1:
            # Conflicting resolution vs unresolvable root causes
            return self._store(selector, _conflict(GHAZI_RECOVERY_UNRESOLVED, "conflicting_root_causes"))

        root_cause = next(iter(causes))
        if root_cause is not GhaziRecoveryRootCause.RESOLVED:
            return self._store(selector, _abstained(GHAZI_RECOVERY_UNRESOLVED, root_cause.value))

        # Quantity consensus
        gross_set = {round(ob.gross_area_m2, 6) for ob in valid_obs}
        net_set = {round(ob.net_area_m2, 6) for ob in valid_obs}
        if len(gross_set) > 1 or len(net_set) > 1:
            return self._store(selector, _conflict(GHAZI_RECOVERY_UNRESOLVED, "conflicting_area_quantities"))

        gross_m2 = float(next(iter(gross_set)))
        net_m2 = float(next(iter(net_set)))
        evidence_ids = tuple(sorted({ob.evidence_id for ob in valid_obs}))

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "trade_scope_id": selector.trade_scope_id,
            "gross_area_m2": gross_m2,
            "net_area_m2": net_m2,
        }
        record_id = stable_contract_id("ghazi_recovery", payload, digest_chars=32)
        record = GhaziWallFinishRecoveryRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
            trade_scope_id=selector.trade_scope_id,
            root_cause=root_cause,
            gross_area_m2=gross_m2,
            net_area_m2=net_m2,
            corroborating_evidence_ids=evidence_ids,
        )
        return self._store(
            selector,
            GhaziWallFinishRecoveryResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(GHAZI_RECOVERY_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "GHAZI_RECOVERY_HARDCODED_VALUES_REJECTED",
    "GHAZI_RECOVERY_LINEAGE_MISMATCH",
    "GHAZI_RECOVERY_RECORD_UNAVAILABLE",
    "GHAZI_RECOVERY_RESOLVED",
    "GHAZI_RECOVERY_SCHEMA_VERSION",
    "GHAZI_RECOVERY_UNRESOLVED",
    "GhaziRecoveryRootCause",
    "GhaziWallFinishRecoveryAuthority",
    "GhaziWallFinishRecoveryEvidence",
    "GhaziWallFinishRecoveryProducer",
    "GhaziWallFinishRecoveryRecord",
    "GhaziWallFinishRecoveryResult",
    "GhaziWallFinishRecoverySelector",
]
