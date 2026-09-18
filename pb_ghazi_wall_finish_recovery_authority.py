"""Fail-closed generic wall and finish recovery authority (Item 28).

This is an orchestration boundary over already-authenticated upstream authorities.
It never invents wall role, thickness, length, height, gross area, net area, finish
assignment, or cross-sheet identity. Missing or conflicting upstream evidence
remains ABSTAINED/CONFLICT.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

from pb_cross_sheet_registration_authority import (
    CrossSheetRegistrationAuthority,
    CrossSheetRegistrationSelector,
)
from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometrySelector,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_net_wall_boolean_union_authority import (
    NetWallBooleanUnionAuthority,
    NetWallBooleanUnionSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_wall_finish_propagation_authority import (
    WallFinishPropagationAuthority,
    WallFinishPropagationSelector,
)
from pb_wall_role_authority import WallRoleAuthority, WallRoleSelector
from pb_wall_thickness_face_authority import (
    WallThicknessFaceAuthority,
    WallThicknessFaceSelector,
)

GHAZI_RECOVERY_SCHEMA_VERSION = "3.0.0"

GHAZI_RECOVERY_RESOLVED = "ghazi_wall_finish_recovery_resolved"
GHAZI_RECOVERY_UNRESOLVED = "ghazi_wall_finish_recovery_unresolved"
GHAZI_RECOVERY_LINEAGE_MISMATCH = "ghazi_wall_finish_recovery_lineage_mismatch"
GHAZI_RECOVERY_RECORD_UNAVAILABLE = "ghazi_wall_finish_recovery_record_unavailable"
GHAZI_RECOVERY_GROSS_NET_MISMATCH = "ghazi_wall_finish_recovery_gross_net_mismatch"
GHAZI_RECOVERY_SCOPE_MISMATCH = "ghazi_wall_finish_recovery_scope_mismatch"
GHAZI_RECOVERY_NET_AREA_UNAVAILABLE = "ghazi_wall_finish_recovery_net_area_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class GhaziRecoveryRootCause(str, Enum):
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
    wall_role: str
    corroborating_evidence_ids: Tuple[str, ...]
    schema_version: str = GHAZI_RECOVERY_SCHEMA_VERSION


@dataclass(frozen=True)
class GhaziWallFinishRecoveryResult:
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


def _same_lineage(record: object, selector: GhaziWallFinishRecoverySelector) -> bool:
    return (
        getattr(record, "document_id", None) == selector.document_id
        and getattr(record, "revision_id", None) == selector.revision_id
        and getattr(record, "source_sha256", None) == selector.source_sha256
        and getattr(record, "snapshot_id", None) == selector.snapshot_id
        and getattr(record, "page_id", getattr(record, "source_page_id", None)) == selector.page_id
    )


class GhaziWallFinishRecoveryAuthority:
    def __init__(
        self,
        results: Mapping[_Key, GhaziWallFinishRecoveryResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "GhaziWallFinishRecoveryAuthority is producer-owned and cannot be constructed directly"
            )
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: GhaziWallFinishRecoverySelector) -> GhaziWallFinishRecoveryResult:
        if type(selector) is not GhaziWallFinishRecoverySelector:
            raise TypeError("selector must be GhaziWallFinishRecoverySelector")
        return self._results.get(
            selector.key,
            _abstained(GHAZI_RECOVERY_RECORD_UNAVAILABLE),
        )


class GhaziWallFinishRecoveryProducer:
    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        wall_role_authority: Optional[WallRoleAuthority] = None,
        wall_thickness_face_authority: Optional[WallThicknessFaceAuthority] = None,
        gross_wall_geometry_authority: Optional[GrossWallGeometryAuthority] = None,
        net_wall_boolean_union_authority: Optional[NetWallBooleanUnionAuthority] = None,
        wall_finish_propagation_authority: Optional[WallFinishPropagationAuthority] = None,
        cross_sheet_registration_authority: Optional[CrossSheetRegistrationAuthority] = None,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "GhaziWallFinishRecoveryProducer must be obtained via from_authorities()"
            )
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority"
            )
        optional_types = (
            (wall_role_authority, WallRoleAuthority, "wall_role_authority"),
            (
                wall_thickness_face_authority,
                WallThicknessFaceAuthority,
                "wall_thickness_face_authority",
            ),
            (
                gross_wall_geometry_authority,
                GrossWallGeometryAuthority,
                "gross_wall_geometry_authority",
            ),
            (
                net_wall_boolean_union_authority,
                NetWallBooleanUnionAuthority,
                "net_wall_boolean_union_authority",
            ),
            (
                wall_finish_propagation_authority,
                WallFinishPropagationAuthority,
                "wall_finish_propagation_authority",
            ),
            (
                cross_sheet_registration_authority,
                CrossSheetRegistrationAuthority,
                "cross_sheet_registration_authority",
            ),
        )
        for value, expected, name in optional_types:
            if value is not None and type(value) is not expected:
                raise TypeError(f"{name} must be producer-owned {expected.__name__} or None")

        self._wall_candidates = physical_wall_candidate_authority
        self._role_auth = wall_role_authority
        self._thickness_auth = wall_thickness_face_authority
        self._gross_auth = gross_wall_geometry_authority
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
        gross_wall_geometry_authority: Optional[GrossWallGeometryAuthority] = None,
        net_wall_boolean_union_authority: Optional[NetWallBooleanUnionAuthority] = None,
        wall_finish_propagation_authority: Optional[WallFinishPropagationAuthority] = None,
        cross_sheet_registration_authority: Optional[CrossSheetRegistrationAuthority] = None,
    ) -> "GhaziWallFinishRecoveryProducer":
        return cls(
            physical_wall_candidate_authority=physical_wall_candidate_authority,
            wall_role_authority=wall_role_authority,
            wall_thickness_face_authority=wall_thickness_face_authority,
            gross_wall_geometry_authority=gross_wall_geometry_authority,
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
        target_elevation_page_id: Optional[str] = None,
    ) -> GhaziWallFinishRecoveryResult:
        if type(selector) is not GhaziWallFinishRecoverySelector:
            raise TypeError("selector must be GhaziWallFinishRecoverySelector")

        scope_id = selector.decision_scope_id

        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=scope_id,
        )
        cand_res = self._wall_candidates.resolve_scope(cand_sel)
        if cand_res.status is not EvidenceResolutionStatus.CORROBORATED:
            status = (
                EvidenceResolutionStatus.CONFLICT
                if cand_res.status is EvidenceResolutionStatus.CONFLICT
                else EvidenceResolutionStatus.ABSTAINED
            )
            result = (
                _conflict if status is EvidenceResolutionStatus.CONFLICT else _abstained
            )
            return self._store(
                selector,
                result(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value,
                    *(getattr(cand_res, "reason_codes", ()) or ()),
                ),
            )
        if (
            cand_res.document_id != selector.document_id
            or cand_res.revision_id != selector.revision_id
            or cand_res.source_sha256 != selector.source_sha256
            or cand_res.snapshot_id != selector.snapshot_id
            or cand_res.page_id != selector.page_id
            or cand_res.decision_scope_id != scope_id
        ):
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_LINEAGE_MISMATCH,
                    GHAZI_RECOVERY_SCOPE_MISMATCH,
                ),
            )
        matching = [
            r
            for r in cand_res.records
            if r.wall_candidate_id == selector.physical_wall_id
            or getattr(r.physical_identity, "physical_wall_id", None)
            == selector.physical_wall_id
        ]
        if len(matching) != 1:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_INSTANCE_MISSING.value,
                ),
            )
        candidate_record = matching[0]
        evidence_ids = [candidate_record.wall_candidate_id]

        if self._role_auth is None:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value,
                    "wall_role_authority_unavailable",
                ),
            )
        role_res = self._role_auth.resolve(
            WallRoleSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=scope_id,
                physical_wall_id=selector.physical_wall_id,
            )
        )
        if role_res.status is not EvidenceResolutionStatus.CORROBORATED or role_res.record is None:
            fn = _conflict if role_res.status is EvidenceResolutionStatus.CONFLICT else _abstained
            return self._store(
                selector,
                fn(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_ROLE_UNRESOLVED.value,
                    *(role_res.reason_codes or ()),
                ),
            )
        if (
            not _same_lineage(role_res.record, selector)
            or role_res.record.decision_scope_id != scope_id
            or role_res.record.physical_wall_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _conflict(GHAZI_RECOVERY_LINEAGE_MISMATCH, "wall_role_identity_mismatch"),
            )
        wall_role = (
            role_res.record.role.value
            if hasattr(role_res.record.role, "value")
            else str(role_res.record.role)
        )
        evidence_ids.append(role_res.record.record_id)

        if self._thickness_auth is None:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value,
                    "wall_thickness_authority_unavailable",
                ),
            )
        thick_res = self._thickness_auth.resolve(
            WallThicknessFaceSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=scope_id,
                physical_wall_id=selector.physical_wall_id,
            )
        )
        if thick_res.status is not EvidenceResolutionStatus.CORROBORATED or thick_res.record is None:
            fn = _conflict if thick_res.status is EvidenceResolutionStatus.CONFLICT else _abstained
            return self._store(
                selector,
                fn(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value,
                    *(thick_res.reason_codes or ()),
                ),
            )
        if (
            not _same_lineage(thick_res.record, selector)
            or thick_res.record.decision_scope_id != scope_id
            or thick_res.record.physical_wall_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_LINEAGE_MISMATCH,
                    "wall_thickness_identity_mismatch",
                ),
            )
        thickness_m = float(thick_res.record.thickness_m)
        if not math.isfinite(thickness_m) or thickness_m <= 0.0:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_THICKNESS_UNRESOLVED.value,
                ),
            )
        evidence_ids.append(thick_res.record.record_id)

        if self._gross_auth is None:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED.value,
                    "gross_wall_geometry_authority_unavailable",
                ),
            )
        gross_res = self._gross_auth.resolve(
            GrossWallGeometrySelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=scope_id,
                physical_wall_id=selector.physical_wall_id,
            )
        )
        if gross_res.status is not EvidenceResolutionStatus.CORROBORATED or gross_res.record is None:
            fn = _conflict if gross_res.status is EvidenceResolutionStatus.CONFLICT else _abstained
            reasons = tuple(gross_res.reason_codes or ())
            root = (
                GhaziRecoveryRootCause.WALL_LENGTH_UNRESOLVED
                if any("length" in str(r).lower() for r in reasons)
                else GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED
            )
            return self._store(
                selector,
                fn(GHAZI_RECOVERY_UNRESOLVED, root.value, *reasons),
            )
        gross_record = gross_res.record
        if (
            not _same_lineage(gross_record, selector)
            or gross_record.decision_scope_id != scope_id
            or gross_record.physical_wall_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_LINEAGE_MISMATCH,
                    "gross_wall_geometry_identity_mismatch",
                ),
            )
        length_m = float(gross_record.length_m)
        height_m = float(gross_record.height_m)
        gross_m2 = float(gross_record.gross_area_m2)
        if (
            not all(math.isfinite(v) for v in (length_m, height_m, gross_m2))
            or length_m <= 0.0
            or height_m <= 0.0
            or gross_m2 <= 0.0
        ):
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.WALL_HEIGHT_UNRESOLVED.value,
                ),
            )
        evidence_ids.append(gross_record.record_id)

        if self._net_wall_auth is None:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED.value,
                    "net_wall_boolean_union_authority_unavailable",
                ),
            )
        net_res = self._net_wall_auth.resolve(
            NetWallBooleanUnionSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=scope_id,
                physical_wall_id=selector.physical_wall_id,
                trade_scope_id=selector.trade_scope_id,
            )
        )
        if net_res.status is not EvidenceResolutionStatus.CORROBORATED or net_res.record is None:
            fn = _conflict if net_res.status is EvidenceResolutionStatus.CONFLICT else _abstained
            return self._store(
                selector,
                fn(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED.value,
                    *(net_res.reason_codes or ()),
                ),
            )
        net_record = net_res.record
        if (
            not _same_lineage(net_record, selector)
            or net_record.decision_scope_id != scope_id
            or net_record.physical_wall_id != selector.physical_wall_id
            or net_record.trade_scope_id != selector.trade_scope_id
        ):
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_LINEAGE_MISMATCH,
                    "net_wall_identity_mismatch",
                ),
            )
        if net_record.gross_wall_record_id != gross_record.record_id:
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_GROSS_NET_MISMATCH,
                    "net_wall_not_bound_to_exact_gross_wall_record",
                ),
            )
        if abs(float(net_record.gross_area_m2) - gross_m2) > 1e-6:
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_GROSS_NET_MISMATCH,
                    "gross_area_disagrees_with_net_wall_record",
                ),
            )
        if net_record.net_area_m2 is None:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.OPENING_DEDUCTION_UNRESOLVED.value,
                    GHAZI_RECOVERY_NET_AREA_UNAVAILABLE,
                ),
            )
        net_m2 = float(net_record.net_area_m2)
        if (
            not math.isfinite(net_m2)
            or net_m2 < 0.0
            or net_m2 > gross_m2 + 1e-6
        ):
            return self._store(
                selector,
                _conflict(
                    GHAZI_RECOVERY_GROSS_NET_MISMATCH,
                    "invalid_net_wall_area",
                ),
            )
        evidence_ids.append(net_record.record_id)

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
            cross_res = self._cross_sheet_auth.resolve(
                CrossSheetRegistrationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    source_page_id=selector.page_id,
                    target_page_id=target_elevation_page_id,
                    physical_element_id=selector.physical_wall_id,
                )
            )
            if (
                cross_res.status is not EvidenceResolutionStatus.CORROBORATED
                or cross_res.record is None
            ):
                fn = (
                    _conflict
                    if cross_res.status is EvidenceResolutionStatus.CONFLICT
                    else _abstained
                )
                return self._store(
                    selector,
                    fn(
                        GHAZI_RECOVERY_UNRESOLVED,
                        GhaziRecoveryRootCause.CROSS_SHEET_EVIDENCE_MISSING.value,
                        *(cross_res.reason_codes or ()),
                    ),
                )
            evidence_ids.append(cross_res.record.record_id)

        if self._finish_auth is None:
            return self._store(
                selector,
                _abstained(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value,
                    "wall_finish_propagation_authority_unavailable",
                ),
            )
        finish_res = self._finish_auth.resolve(
            WallFinishPropagationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=scope_id,
                physical_wall_id=selector.physical_wall_id,
                trade_scope_id=selector.trade_scope_id,
            )
        )
        if (
            finish_res.status is not EvidenceResolutionStatus.CORROBORATED
            or finish_res.record is None
        ):
            fn = (
                _conflict
                if finish_res.status is EvidenceResolutionStatus.CONFLICT
                else _abstained
            )
            return self._store(
                selector,
                fn(
                    GHAZI_RECOVERY_UNRESOLVED,
                    GhaziRecoveryRootCause.FINISH_ASSIGNMENT_UNRESOLVED.value,
                    *(finish_res.reason_codes or ()),
                ),
            )
        evidence_ids.append(finish_res.record.record_id)

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "trade_scope_id": selector.trade_scope_id,
            "length_m": length_m,
            "height_m": height_m,
            "thickness_m": thickness_m,
            "gross_area_m2": gross_m2,
            "net_area_m2": net_m2,
            "wall_role": wall_role,
        }
        record = GhaziWallFinishRecoveryRecord(
            record_id=stable_contract_id("ghazi_recovery", payload, digest_chars=32),
            root_cause=GhaziRecoveryRootCause.RESOLVED,
            corroborating_evidence_ids=tuple(dict.fromkeys(evidence_ids)),
            **payload,
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
    "GHAZI_RECOVERY_GROSS_NET_MISMATCH",
    "GHAZI_RECOVERY_LINEAGE_MISMATCH",
    "GHAZI_RECOVERY_NET_AREA_UNAVAILABLE",
    "GHAZI_RECOVERY_RECORD_UNAVAILABLE",
    "GHAZI_RECOVERY_RESOLVED",
    "GHAZI_RECOVERY_SCHEMA_VERSION",
    "GHAZI_RECOVERY_SCOPE_MISMATCH",
    "GHAZI_RECOVERY_UNRESOLVED",
    "GhaziRecoveryRootCause",
    "GhaziWallFinishRecoveryAuthority",
    "GhaziWallFinishRecoveryProducer",
    "GhaziWallFinishRecoveryRecord",
    "GhaziWallFinishRecoveryResult",
    "GhaziWallFinishRecoverySelector",
]
