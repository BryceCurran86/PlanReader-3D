"""Producer-owned role authority for the exact whole-wall identities used by gross/net geometry.

This adapter closes the identity gap between:
- candidate-addressed source topology (Item 26), and
- whole-wall gross/net records (opening-derived shared wall frames or
  zero-opening representative walls).

It never accepts a caller-supplied role or caller-supplied wall membership.
Membership is replayed only from a sealed GrossWallGeometryRecord. Each member
candidate is classified through the existing source-derived WallRoleProducer.

For a two-face physical wall, source topology can legitimately see the outside
face as EXTERNAL and the room-side face as INTERNAL because the bounded wall
body lies between them. The whole physical wall is therefore EXTERNAL when at
least one authenticated member is EXTERNAL and every member is otherwise
resolved as EXTERNAL/INTERNAL. It is INTERNAL only when every authenticated
member is INTERNAL. Other mixed role sets fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_gross_wall_geometry_authority import (
    GrossWallGeometryAuthority,
    GrossWallGeometrySelector,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority
from pb_wall_role_authority import (
    WallRoleClassification,
    WallRoleProducer,
    WallRoleSelector,
)

WHOLE_WALL_ROLE_SCHEMA_VERSION = "1.0.0"

WHOLE_WALL_ROLE_RESOLVED = "whole_wall_role_resolved"
WHOLE_WALL_ROLE_GROSS_UNRESOLVED = "whole_wall_role_gross_unresolved"
WHOLE_WALL_ROLE_LINEAGE_MISMATCH = "whole_wall_role_lineage_mismatch"
WHOLE_WALL_ROLE_MEMBERSHIP_UNAVAILABLE = "whole_wall_role_membership_unavailable"
WHOLE_WALL_ROLE_MEMBER_UNRESOLVED = "whole_wall_role_member_unresolved"
WHOLE_WALL_ROLE_MEMBER_CONFLICT = "whole_wall_role_member_conflict"
WHOLE_WALL_ROLE_RECORD_UNAVAILABLE = "whole_wall_role_record_unavailable"

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_RECORD_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{name} must be non-empty")
    return clean


def _reasons(*values: object) -> tuple[str, ...]:
    flat: list[str] = []
    for value in values:
        if isinstance(value, (tuple, list)):
            flat.extend(str(item) for item in value if str(item))
        elif value is not None and str(value):
            flat.append(str(value))
    return tuple(dict.fromkeys(flat))


@dataclass(frozen=True)
class WholeWallRoleSelector:
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
class WholeWallRoleRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    gross_geometry_record_id: str
    member_wall_candidate_ids: tuple[str, ...]
    member_wall_role_record_ids: tuple[str, ...]
    role: WallRoleClassification
    schema_version: str = WHOLE_WALL_ROLE_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WholeWallRoleRecord is producer-owned")


@dataclass(frozen=True)
class WholeWallRoleResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: WholeWallRoleRecord | None = None
    schema_version: str = WHOLE_WALL_ROLE_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extras: object,
) -> WholeWallRoleResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return WholeWallRoleResult(
        status=status,
        reason_codes=_reasons(reason, *extras),
        record=None,
    )


class WholeWallRoleAuthority:
    def __init__(
        self,
        results: Mapping[_Key, WholeWallRoleResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WholeWallRoleAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: WholeWallRoleSelector) -> WholeWallRoleResult:
        if type(selector) is not WholeWallRoleSelector:
            raise TypeError("selector must be WholeWallRoleSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                WHOLE_WALL_ROLE_RECORD_UNAVAILABLE,
            ),
        )


class WholeWallRoleProducer:
    """Replay candidate topology through sealed gross whole-wall membership."""

    def __init__(
        self,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        gross_wall_geometry_authority: GrossWallGeometryAuthority,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WholeWallRoleProducer must be obtained from from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned")
        if type(gross_wall_geometry_authority) is not GrossWallGeometryAuthority:
            raise TypeError("gross_wall_geometry_authority must be producer-owned")
        self._walls = physical_wall_candidate_authority
        self._gross = gross_wall_geometry_authority
        self._results: dict[_Key, WholeWallRoleResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        gross_wall_geometry_authority: GrossWallGeometryAuthority,
    ) -> "WholeWallRoleProducer":
        return cls(
            physical_wall_candidate_authority=physical_wall_candidate_authority,
            gross_wall_geometry_authority=gross_wall_geometry_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> WholeWallRoleAuthority:
        return WholeWallRoleAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: WholeWallRoleSelector,
        result: WholeWallRoleResult,
    ) -> WholeWallRoleResult:
        prior = self._results.get(selector.key)
        if prior is not None and prior != result:
            raise RuntimeError("whole-wall role producer equivocation")
        self._results[selector.key] = result
        return result

    def publish(self, selector: WholeWallRoleSelector) -> WholeWallRoleResult:
        if type(selector) is not WholeWallRoleSelector:
            raise TypeError("selector must be WholeWallRoleSelector")

        gross_selector = GrossWallGeometrySelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
        )
        gross_result = self._gross.resolve(gross_selector)
        gross = gross_result.record
        if (
            gross_result.status is not EvidenceResolutionStatus.CORROBORATED
            or gross is None
        ):
            return self._store(
                selector,
                _blocked(
                    gross_result.status,
                    WHOLE_WALL_ROLE_GROSS_UNRESOLVED,
                    gross_result.reason_codes,
                ),
            )

        if (
            gross.document_id != selector.document_id
            or gross.revision_id != selector.revision_id
            or gross.source_sha256 != selector.source_sha256
            or gross.snapshot_id != selector.snapshot_id
            or gross.page_id != selector.page_id
            or gross.decision_scope_id != selector.decision_scope_id
            or gross.physical_wall_id != selector.physical_wall_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WHOLE_WALL_ROLE_LINEAGE_MISMATCH,
                ),
            )

        member_ids = tuple(
            sorted(
                dict.fromkeys(
                    str(item)
                    for item in gross.member_wall_candidate_ids
                    if str(item)
                )
            )
        )
        if not member_ids:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    WHOLE_WALL_ROLE_MEMBERSHIP_UNAVAILABLE,
                ),
            )

        member_role_producer = WallRoleProducer.from_source_topology(
            physical_wall_candidate_authority=self._walls
        )
        member_records = []
        member_failures: list[str] = []
        member_conflict = False
        for member_id in member_ids:
            member_result = member_role_producer.publish(
                WallRoleSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=f"wall-source:page-{selector.page_id}",
                    physical_wall_id=member_id,
                )
            )
            if (
                member_result.status is EvidenceResolutionStatus.CORROBORATED
                and member_result.record is not None
            ):
                member_records.append(member_result.record)
                continue
            member_conflict = (
                member_conflict
                or member_result.status is EvidenceResolutionStatus.CONFLICT
            )
            member_failures.extend(
                (
                    f"member:{member_id}",
                    *member_result.reason_codes,
                )
            )

        if member_failures or len(member_records) != len(member_ids):
            return self._store(
                selector,
                _blocked(
                    (
                        EvidenceResolutionStatus.CONFLICT
                        if member_conflict
                        else EvidenceResolutionStatus.ABSTAINED
                    ),
                    WHOLE_WALL_ROLE_MEMBER_UNRESOLVED,
                    tuple(member_failures),
                ),
            )

        distinct_roles = {record.role for record in member_records}
        external_internal = {
            WallRoleClassification.EXTERNAL,
            WallRoleClassification.INTERNAL,
        }
        if distinct_roles and distinct_roles.issubset(external_internal):
            resolved_role = (
                WallRoleClassification.EXTERNAL
                if WallRoleClassification.EXTERNAL in distinct_roles
                else WallRoleClassification.INTERNAL
            )
        elif len(distinct_roles) == 1:
            resolved_role = next(iter(distinct_roles))
        else:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    WHOLE_WALL_ROLE_MEMBER_CONFLICT,
                    tuple(
                        f"member_role:{role.value}"
                        for role in sorted(distinct_roles, key=lambda item: item.value)
                    ),
                ),
            )

        member_role_record_ids = tuple(
            sorted(record.record_id for record in member_records)
        )
        payload = {
            "schema_version": WHOLE_WALL_ROLE_SCHEMA_VERSION,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "gross_geometry_record_id": gross.record_id,
            "member_wall_candidate_ids": member_ids,
            "member_wall_role_record_ids": member_role_record_ids,
            "role": resolved_role.value,
        }
        record = WholeWallRoleRecord(
            record_id=stable_contract_id(
                "whole_wall_role",
                payload,
                digest_chars=32,
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
            gross_geometry_record_id=gross.record_id,
            member_wall_candidate_ids=member_ids,
            member_wall_role_record_ids=member_role_record_ids,
            role=resolved_role,
            _seal=_RECORD_SEAL,
        )
        return self._store(
            selector,
            WholeWallRoleResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(WHOLE_WALL_ROLE_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "WHOLE_WALL_ROLE_GROSS_UNRESOLVED",
    "WHOLE_WALL_ROLE_LINEAGE_MISMATCH",
    "WHOLE_WALL_ROLE_MEMBER_CONFLICT",
    "WHOLE_WALL_ROLE_MEMBER_UNRESOLVED",
    "WHOLE_WALL_ROLE_MEMBERSHIP_UNAVAILABLE",
    "WHOLE_WALL_ROLE_RECORD_UNAVAILABLE",
    "WHOLE_WALL_ROLE_RESOLVED",
    "WHOLE_WALL_ROLE_SCHEMA_VERSION",
    "WholeWallRoleAuthority",
    "WholeWallRoleProducer",
    "WholeWallRoleRecord",
    "WholeWallRoleResult",
    "WholeWallRoleSelector",
]
