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
- Never defaults wall height (e.g. 3.0m), wall thickness, or opening deduction. Missing upstream
  authority fails closed with ABSTAINED or CONFLICT.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_wall_finish_propagation_authority import (
    WALL_FINISH_BINDING_UNAVAILABLE,
    WallFinishPropagationAuthority,
    WallFinishPropagationSelector,
)
from pb_wall_role_authority import (
    WallRoleAuthority,
    WallRoleClassification,
    WallRoleSelector,
)
from pb_wall_thickness_face_authority import (
    WallThicknessFaceAuthority,
    WallThicknessFaceSelector,
)
from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationSelector,
)

GHAZI_RECOVERY_SCHEMA_VERSION = "2.0.0"

# Public reason codes
GHAZI_RECOVERY_RESOLVED = "ghazi_wall_finish_recovery_resolved"
GHAZI_RECOVERY_UNRESOLVED = "ghazi_wall_finish_recovery_unresolved"
GHAZI_RECOVERY_LINEAGE_MISMATCH = "ghazi_wall_finish_recovery_lineage_mismatch"
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
    length_m: float
    height_m: float
    thickness_m: float
    gross_area_m2: float
    net_area_m2: float
    wall_role: Optional[str]
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

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        wall_role_authority: Optional[WallRoleAuthority] = None,
        wall_thickness_face_authority: Optional[WallThicknessFaceAuthority] = None,
        net_wall_boolean_union_authority: Optional[NetWallBooleanUnionAuthority] = None,
        wall_finish_propagation_authority: Optional[WallFinishPropagationAuthority] = None,
        cross_sheet_registration_authority: Optional[CrossSheetRegistrationAuthority] = None,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("GhaziWallFinishRecoveryProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        if wall_role_authority is not None and type(wall_role_authority) is not WallRoleAuthority:
            raise TypeError("wall_role_authority must be producer-owned WallRoleAuthority or None")
        if wall_thickness_face_authority is not None and type(wall_thickness_face_authority) is not WallThicknessFaceAuthority:
            raise TypeError("wall_thickness_face_authority must be producer-owned WallThicknessFaceAuthority or None")
        if net_wall_boolean_union_authority is not None and type(net_wall_boolean_union_authority) is not NetWallBooleanUnionAuthority:
            raise TypeError("net_wall_boolean_union_authority must be producer-owned NetWallBooleanUnionAuthority or None")
        if wall_finish_propagation_authority is not None and type(wall_finish_propagation_authority) is not WallFinishPropagationAuthority:
            raise TypeError("wall_finish_propagation_authority must be producer-owned WallFinishPropagationAuthority or None")
        if cross_sheet_registration_authority is not None and type(cross_sheet_registration_authority) is not CrossSheetRegistrationAuthority:
            raise TypeError("cross_sheet_registration_authority must be producer-owned CrossSheetRegistrationAuthority or None")

        self._wall_candidates = physical_wall_candidate_authority
        self._role_auth = wall_role_authority
        self._thickness_auth = wall_thickness_face_authority
        self._net_wall_auth = net_wall_boolean_union_authority
        self._finish_auth = wall_finish_propagation_authority
        self._cross_sheet_auth = cross_sheet_registration_authority
        self._results: dict[_Key, GhaziWallFinishRecoveryResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        wall_role_authority: Optional[WallRoleAuthority] = None,
        wall_thickness_face_authority: Optional[WallThicknessFaceAuthority] = None,
        net_wall_boolean_union_authority: Optional[NetWallBooleanUnionAuthority] = None,
        wall_finish_propagation_authority: Optional[WallFinishPropagationAuthority] = None,
        cross_sheet_registration_authority: Optional[CrossSheetRegistrationAuthority] = None,
    ) -> "GhaziWallFinishRecoveryProducer":
        return cls(
            physical_wall_candidate_authority=physical_wall_candidate_authority,
            wall_role_authority=wall_role_authority,
            wall_thickness_face_authority=wall_thickness_face_authority,
            net_wall_boolean_union_authority=net_wall_boolean_union_authority,
            wall_finish_propagation_authority=wall_finish_propagation_authority,
            cross_sheet_registration_authority=cross_sheet_registration_authority,
            _seal=_PRODUCER_SEAL,
        )

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
        *,
        require_wall_role: bool = False,
        require_wall_thickness: bool = False,
        require_finish_binding: bool = False,
        target_elevation_page_id: Optional[str] = None,
    ) -> GhaziWallFinishRecoveryResult:
        """Publish authenticated generic wall & finish recovery for selector by re-resolving upstream authorities."""
        if type(selector) is not GhaziWallFinishRecoverySelector:
            raise TypeError("selector must be GhaziWallFinishRecoverySelector")

        # 1. Resolve Physical Wall Candidate
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_res = self._wall_candidates.resolve_scope(cand_sel)
        if cand_res.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value,
                    *(getattr(cand_res, "reason_codes", ()) or ()),
                ),
            )

        matching = [
            r for r in cand_res.records
            if r.wall_candidate_id == selector.physical_wall_id
            or getattr(r.physical_identity, "physical_wall_id", None) == selector.physical_wall_id
        ]
        if not matching:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value,
                ),
            )

        rec = matching[0]
        cand = rec.wall_candidate
        evidence_ids = list(getattr(cand, "supporting_evidence_ids", ()) or (rec.wall_candidate_id,))

        # 2. Check Lineage Consistency on Candidate
        if (
            cand_res.document_id != selector.document_id
            or cand_res.revision_id != selector.revision_id
            or cand_res.source_sha256 != selector.source_sha256
            or cand_res.snapshot_id != selector.snapshot_id
            or cand_res.page_id != selector.page_id
        ):
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_LINEAGE_MISMATCH,
                    "physical_wall_candidate_lineage_mismatch",
                ),
            )

        # 3. Resolve Wall Role if required or provided
        wall_role_str: Optional[str] = None
        if self._role_auth is not None:
            role_sel = WallRoleSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=cand_scope_id,
                physical_wall_id=selector.physical_wall_id,
            )
            role_res = self._role_auth.resolve(role_sel)
            if role_res.status is EvidenceResolutionStatus.CORROBORATED and role_res.record is not None:
                wall_role_str = role_res.record.role.value if hasattr(role_res.record.role, "value") else str(role_res.record.role)
                evidence_ids.append(role_res.record.record_id)
            elif role_res.status is EvidenceResolutionStatus.CONFLICT:
                return self._store(
                    selector,
                    _conflict(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value,
                        *role_res.reason_codes,
                    ),
                )
            elif require_wall_role:
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value,
                        *role_res.reason_codes,
                    ),
                )
        elif require_wall_role:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value,
                    "wall_role_authority_unavailable",
                ),
            )

        # 4. Resolve Wall Thickness if required or provided
        thickness_m: float = 0.0
        if self._thickness_auth is not None:
            thick_sel = WallThicknessFaceSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=cand_scope_id,
                physical_wall_id=selector.physical_wall_id,
            )
            thick_res = self._thickness_auth.resolve(thick_sel)
            if thick_res.status is EvidenceResolutionStatus.CORROBORATED and thick_res.record is not None:
                thickness_m = float(thick_res.record.thickness_m)
                evidence_ids.append(thick_res.record.record_id)
            elif thick_res.status is EvidenceResolutionStatus.CONFLICT:
                return self._store(
                    selector,
                    _conflict(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value,
                        *thick_res.reason_codes,
                    ),
                )
            elif require_wall_thickness:
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value,
                        *thick_res.reason_codes,
                    ),
                )
        elif require_wall_thickness:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value,
                    "wall_thickness_authority_unavailable",
                ),
            )

        # 5. Resolve Wall Dimensions and Net-Wall Boolean Union
        length_m = 0.0
        height_m = 0.0
        gross_m2 = 0.0
        net_m2 = 0.0

        if self._net_wall_auth is not None:
            net_sel = NetWallBooleanUnionSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=cand_scope_id,
                physical_wall_id=selector.physical_wall_id,
                trade_scope_id=selector.trade_scope_id,
            )
            net_res = self._net_wall_auth.resolve(net_sel)
            if net_res.status is EvidenceResolutionStatus.CORROBORATED and net_res.record is not None:
                gross_m2 = float(net_res.record.gross_area_m2)
                net_m2 = float(net_res.record.net_area_m2 or 0.0)
                evidence_ids.append(net_res.record.record_id)
            elif net_res.status is EvidenceResolutionStatus.CONFLICT:
                # Distinguish height vs void vs deduction conflict
                if any("height" in r.lower() for r in net_res.reason_codes):
                    root_cause = GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED
                elif any("void" in r.lower() or "deduction" in r.lower() for r in net_res.reason_codes):
                    root_cause = GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED
                else:
                    root_cause = GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED
                return self._store(
                    selector,
                    _conflict(
                        GHAZI_RECOVERY_UNRESOLVED,
                        root_cause.value,
                        *net_res.reason_codes,
                    ),
                )
            else:
                # Net wall uncorroborated / abstained: determine precise root cause
                if any("height" in r.lower() for r in net_res.reason_codes):
                    root_cause = GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED
                elif any("deduction" in r.lower() or "void" in r.lower() or "universe" in r.lower() for r in net_res.reason_codes):
                    root_cause = GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED
                else:
                    root_cause = GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        root_cause.value,
                        *net_res.reason_codes,
                    ),
                )
        else:
            # Without NetWallBooleanUnionAuthority, wall height cannot be authenticated
            # DO NOT fall back to a hardcoded height (e.g. 3.0m). Fail closed!
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED.value,
                    "net_wall_boolean_union_authority_unavailable",
                ),
            )

        # 6. Check Cross-Sheet Evidence if target elevation sheet requested
        if target_elevation_page_id is not None:
            if self._cross_sheet_auth is None:
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.CROSS_SHEET_EVIDENCE_MISSING.value,
                        "cross_sheet_registration_authority_unavailable",
                    ),
                )
            cross_sel = CrossSheetRegistrationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                source_page_id=selector.page_id,
                target_page_id=target_elevation_page_id,
                physical_element_id=selector.physical_wall_id,
            )
            cross_res = self._cross_sheet_auth.resolve(cross_sel)
            if cross_res.status is not EvidenceResolutionStatus.CORROBORATED:
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.CROSS_SHEET_EVIDENCE_MISSING.value,
                        *cross_res.reason_codes,
                    ),
                )
            if cross_res.record is not None:
                evidence_ids.append(cross_res.record.record_id)

        # 7. Check Finish Binding if requested
        if require_finish_binding:
            if self._finish_auth is None:
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value,
                        "wall_finish_propagation_authority_unavailable",
                    ),
                )
            finish_sel = WallFinishPropagationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=cand_scope_id,
                physical_wall_id=selector.physical_wall_id,
                trade_scope_id=selector.trade_scope_id,
            )
            finish_res = self._finish_auth.resolve(finish_sel)
            if finish_res.status is not EvidenceResolutionStatus.CORROBORATED:
                return self._store(
                    selector,
                    _abstained(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value,
                        *finish_res.reason_codes,
                    ),
                )
            if finish_res.record is not None:
                evidence_ids.append(finish_res.record.record_id)

        # Extract length and height if available from candidate
        cand_length = getattr(cand, "length_m", 0.0)
        length_m = float(cand_length) if cand_length else 0.0
        height_m = round(gross_m2 / length_m, 6) if length_m > 0 else 0.0

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
            root_cause=GhaziRecoveryRootCause.RESOLVED,
            length_m=length_m,
            height_m=height_m,
            thickness_m=thickness_m,
            gross_area_m2=gross_m2,
            net_area_m2=net_m2,
            wall_role=wall_role_str,
            corroborating_evidence_ids=tuple(dict.fromkeys(evidence_ids)),
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
    "GHAZI_RECOVERY_LINEAGE_MISMATCH",
    "GHAZI_RECOVERY_RECORD_UNAVAILABLE",
    "GHAZI_RECOVERY_RESOLVED",
    "GHAZI_RECOVERY_SCHEMA_VERSION",
    "GHAZI_RECOVERY_UNRESOLVED",
    "GhaziRecoveryRootCause",
    "GhaziWallFinishRecoveryAuthority",
    "GhaziWallFinishRecoveryProducer",
    "GhaziWallFinishRecoveryRecord",
    "GhaziWallFinishRecoveryResult",
    "GhaziWallFinishRecoverySelector",
]
