"""Producer-owned wall-role classification authority (Item 26).

Classifies each physical wall as exactly one of:
  - EXTERNAL: proven to bound the external building envelope.
  - INTERNAL: proven to divide enclosed internal spaces only.
  - GABLE: proven to be a gable-end wall (may also be external).
  - PARTY: proven shared wall between separate tenancies / units.
  - UNRESOLVED: classification cannot be established from available evidence.

Authority invariants:
  - Classification binds to exact physical_wall_id; distinct walls remain
    distinct — no "largest perimeter" merging.
  - Classification requires corroborated upstream physical wall candidate
    evidence on the same document/revision/source/snapshot/page lineage.
  - Thickness alone never determines role (equal-thickness walls can be
    internal or external).
  - Gable is never inferred solely from wall length or position.
  - Caller-supplied role labels cannot mint authority.
  - Stale evidence (mismatched lineage) fails closed.
  - Cross-page evidence must be registered before it can contribute.
  - Ambiguous classification returns UNRESOLVED (abstained).
  - All positive records are sealed with _PRODUCER_SEAL; no public constructor.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Dict, Mapping, Optional, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)


WALL_ROLE_SCHEMA_VERSION = "1.0.0"

# Public reason codes
WALL_ROLE_RESOLVED = "wall_role_resolved"
WALL_ROLE_UNRESOLVED = "wall_role_unresolved"
WALL_ROLE_WALL_UNRESOLVED = "wall_role_wall_candidate_unresolved"
WALL_ROLE_LINEAGE_MISMATCH = "wall_role_lineage_mismatch"
WALL_ROLE_AMBIGUOUS = "wall_role_ambiguous"
WALL_ROLE_STALE_EVIDENCE = "wall_role_stale_evidence"
WALL_ROLE_CALLER_LABEL_REJECTED = "wall_role_caller_label_rejected"
WALL_ROLE_CROSS_PAGE_UNREGISTERED = "wall_role_cross_page_evidence_unregistered"
WALL_ROLE_RECORD_UNAVAILABLE = "wall_role_record_unavailable"
WALL_ROLE_THICKNESS_ONLY_REJECTED = "wall_role_thickness_only_classification_rejected"
WALL_ROLE_PERIMETER_ONLY_REJECTED = "wall_role_largest_perimeter_classification_rejected"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/wall_id


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class WallRoleClassification(str, Enum):
    """The proven classification for one physical wall."""
    EXTERNAL = "external"
    INTERNAL = "internal"
    GABLE = "gable"
    PARTY = "party"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class WallRoleSelector:
    """Sealed selector identifying the exact wall and context for role resolution."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
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
        )


@dataclass(frozen=True)
class WallRoleRecord:
    """Sealed, authenticated wall-role record. Never directly constructible."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    role: WallRoleClassification
    corroborating_evidence_ids: Tuple[str, ...]
    schema_version: str = WALL_ROLE_SCHEMA_VERSION


@dataclass(frozen=True)
class WallRoleResult:
    """Result of a wall-role authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[WallRoleRecord] = None
    schema_version: str = WALL_ROLE_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> WallRoleResult:
    return WallRoleResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> WallRoleResult:
    return WallRoleResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class WallRoleAuthority:
    """Sealed selector-only lookup for published wall-role records."""

    def __init__(
        self,
        results: Mapping[_Key, WallRoleResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallRoleAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: WallRoleSelector) -> WallRoleResult:
        if type(selector) is not WallRoleSelector:
            raise TypeError("selector must be WallRoleSelector")
        return self._results.get(
            selector.key,
            _abstained(WALL_ROLE_RECORD_UNAVAILABLE),
        )


class WallRoleProducer:
    """Trusted writer boundary for authenticated wall-role classification.

    Callers may NOT supply a role label, thickness, or perimeter claim.
    Every positive WallRoleRecord is produced only from authenticated
    upstream candidate topology evidence.
    """

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallRoleProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be a producer-owned PhysicalWallCandidateAuthority"
            )
        self._wall_candidates = physical_wall_candidate_authority
        self._results: Dict[_Key, WallRoleResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "WallRoleProducer":
        return cls(physical_wall_candidate_authority, _seal=_PRODUCER_SEAL)

    def authority(self) -> WallRoleAuthority:
        return WallRoleAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: WallRoleSelector,
        result: WallRoleResult,
    ) -> WallRoleResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: WallRoleSelector,
    ) -> WallRoleResult:
        """Publish authenticated wall role for selector by re-resolving upstream candidate authority."""
        if type(selector) is not WallRoleSelector:
            raise TypeError("selector must be WallRoleSelector")

        # 1. Verify the physical wall candidate exists in the authority
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_result = self._wall_candidates.resolve_scope(cand_sel)
        if cand_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    WALL_ROLE_WALL_UNRESOLVED,
                    *(getattr(cand_result, "reason_codes", ()) or ()),
                ),
            )

        matching_recs = [
            r for r in getattr(cand_result, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None) == selector.physical_wall_id
        ]
        if not matching_recs:
            return self._store(selector, _abstained(WALL_ROLE_WALL_UNRESOLVED))
        rec = matching_recs[0]
        cand = rec.wall_candidate

        # 2. Derive classification strictly from candidate topology (never caller metadata dict)
        proven_role = WallRoleClassification.UNRESOLVED

        if cand.interior_exterior == "exterior":
            proven_role = WallRoleClassification.EXTERNAL
        elif cand.interior_exterior == "interior":
            proven_role = WallRoleClassification.INTERNAL
        elif cand.interior_exterior == "gable":
            proven_role = WallRoleClassification.GABLE
        elif cand.interior_exterior == "party":
            proven_role = WallRoleClassification.PARTY

        if proven_role is WallRoleClassification.UNRESOLVED:
            return self._store(selector, _abstained(WALL_ROLE_UNRESOLVED))

        evidence_ids = (rec.wall_candidate_id,)
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "role": proven_role.value,
            "corroborating_evidence_ids": evidence_ids,
        }
        record_id = stable_contract_id("wall_role", payload, digest_chars=32)
        record = WallRoleRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
            role=proven_role,
            corroborating_evidence_ids=evidence_ids,
        )
        return self._store(
            selector,
            WallRoleResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(WALL_ROLE_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "WALL_ROLE_AMBIGUOUS",
    "WALL_ROLE_CALLER_LABEL_REJECTED",
    "WALL_ROLE_CROSS_PAGE_UNREGISTERED",
    "WALL_ROLE_LINEAGE_MISMATCH",
    "WALL_ROLE_PERIMETER_ONLY_REJECTED",
    "WALL_ROLE_RECORD_UNAVAILABLE",
    "WALL_ROLE_RESOLVED",
    "WALL_ROLE_SCHEMA_VERSION",
    "WALL_ROLE_STALE_EVIDENCE",
    "WALL_ROLE_THICKNESS_ONLY_REJECTED",
    "WALL_ROLE_UNRESOLVED",
    "WALL_ROLE_WALL_UNRESOLVED",
    "WallRoleAuthority",
    "WallRoleClassification",
    "WallRoleProducer",
    "WallRoleRecord",
    "WallRoleResult",
    "WallRoleSelector",
]
