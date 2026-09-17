"""Producer-owned target applicability authority for authenticated opening deductions.

This module proves one narrow proposition only: an exact authenticated physical
opening/void is governed by one exact target scope and one exact versioned rule.
It does not compute an area, net wall quantity, publication value, or downstream
commercial output.

All public lookup/publication surfaces are selector-only. Positive applicability
requires independently sealed physical-void, host-binding, target-scope and rule
authorities with matching source lineage. Ambiguity or disagreement fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_physical_opening_void_authority import (
    PHYSICAL_OPENING_VOID_RESOLVED,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidSelector,
)


OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION = "1.0.0"
OPENING_DEDUCTION_APPLICABILITY_RESOLVED = "opening_deduction_applicability_resolved"
OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED = (
    "opening_deduction_applicability_target_unresolved"
)
OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED = (
    "opening_deduction_applicability_rule_unresolved"
)
OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH = (
    "opening_deduction_applicability_wall_scope_mismatch"
)
OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH = (
    "opening_deduction_applicability_trade_scope_mismatch"
)
OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH = (
    "opening_deduction_applicability_finish_scope_mismatch"
)
OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH = (
    "opening_deduction_applicability_assembly_scope_mismatch"
)
OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH = (
    "opening_deduction_applicability_lineage_mismatch"
)
OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT = (
    "opening_deduction_applicability_rule_conflict"
)

TARGET_SCOPE_RESOLVED = "opening_deduction_target_scope_resolved"
TARGET_SCOPE_UNRESOLVED = "opening_deduction_target_scope_unresolved"
RULE_SCOPE_RESOLVED = "opening_deduction_rule_scope_resolved"
RULE_SCOPE_UNRESOLVED = "opening_deduction_rule_scope_unresolved"
SUBTRACT_AUTHENTICATED_PHYSICAL_VOID = "subtract_authenticated_physical_void"

_APPLICABILITY_AUTHORITY_SEAL = object()
_APPLICABILITY_PRODUCER_SEAL = object()
_TARGET_AUTHORITY_SEAL = object()
_RULE_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class OpeningDeductionApplicabilitySelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str
    target_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "opening_identity_id",
            "target_scope_id",
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
            self.opening_identity_id,
            self.target_scope_id,
        )


@dataclass(frozen=True)
class OpeningDeductionTargetScopeRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    target_scope_id: str
    host_wall_id: str
    trade_scope_id: str
    finish_scope_id: str
    assembly_scope_id: str
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionTargetScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionTargetScopeRecord | None = None
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionRuleRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    target_scope_id: str
    host_wall_id: str
    trade_scope_id: str
    finish_scope_id: str
    assembly_scope_id: str
    effect_kind: str
    rule_version: str
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionRuleResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionRuleRecord | None = None
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionApplicabilityRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str
    host_binding_record_id: str
    physical_void_record_id: str
    target_scope_id: str
    target_scope_record_id: str
    rule_record_id: str
    rule_version: str
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionApplicabilityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionApplicabilityRecord | None = None
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


def _blocked(reason: str, *extra: str) -> OpeningDeductionApplicabilityResult:
    reasons = tuple(dict.fromkeys((reason, *(item for item in extra if item))))
    return OpeningDeductionApplicabilityResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=reasons,
        record=None,
    )


def _same_lineage(selector: OpeningDeductionApplicabilitySelector, record: object) -> bool:
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


class OpeningDeductionTargetScopeAuthority:
    """Sealed selector-only target-scope lookup.

    Creation is intentionally sealed. A later reviewed producer must establish
    target-scope records from authenticated project/trade/finish/assembly evidence;
    this authority never accepts those propositions through its public resolver.
    """

    def __init__(
        self,
        results: Mapping[_Key, OpeningDeductionTargetScopeResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _TARGET_AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionTargetScopeAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionTargetScopeResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        return self._results.get(
            selector.key,
            OpeningDeductionTargetScopeResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(TARGET_SCOPE_UNRESOLVED,),
            ),
        )


class OpeningDeductionRuleAuthority:
    """Sealed selector-only governing-rule lookup."""

    def __init__(
        self,
        results: Mapping[_Key, OpeningDeductionRuleResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _RULE_AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionRuleAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionRuleResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        return self._results.get(
            selector.key,
            OpeningDeductionRuleResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(RULE_SCOPE_UNRESOLVED,),
            ),
        )


class OpeningDeductionApplicabilityAuthority:
    """Sealed selector-only applicability lookup."""

    def __init__(
        self,
        results: Mapping[_Key, OpeningDeductionApplicabilityResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _APPLICABILITY_AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionApplicabilityAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionApplicabilityResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        return self._results.get(
            selector.key,
            _blocked(OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED),
        )


class OpeningDeductionApplicabilityProducer:
    """Trusted writer joining exact physical, target-scope and rule authorities."""

    def __init__(
        self,
        physical_void_authority: PhysicalOpeningVoidAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        target_scope_authority: OpeningDeductionTargetScopeAuthority,
        rule_authority: OpeningDeductionRuleAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _APPLICABILITY_PRODUCER_SEAL:
            raise TypeError(
                "OpeningDeductionApplicabilityProducer must be obtained from from_authorities()"
            )
        expected = (
            (physical_void_authority, PhysicalOpeningVoidAuthority, "physical_void_authority"),
            (host_binding_authority, OpeningHostBindingAuthority, "host_binding_authority"),
            (
                target_scope_authority,
                OpeningDeductionTargetScopeAuthority,
                "target_scope_authority",
            ),
            (rule_authority, OpeningDeductionRuleAuthority, "rule_authority"),
        )
        for value, required_type, name in expected:
            if type(value) is not required_type:
                raise TypeError(f"{name} must be producer-owned {required_type.__name__}")
        self._void = physical_void_authority
        self._host = host_binding_authority
        self._target = target_scope_authority
        self._rule = rule_authority
        self._results: dict[_Key, OpeningDeductionApplicabilityResult] = {}

    @classmethod
    def from_authorities(
        cls,
        physical_void_authority: PhysicalOpeningVoidAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        target_scope_authority: OpeningDeductionTargetScopeAuthority,
        rule_authority: OpeningDeductionRuleAuthority,
    ) -> "OpeningDeductionApplicabilityProducer":
        return cls(
            physical_void_authority,
            host_binding_authority,
            target_scope_authority,
            rule_authority,
            _seal=_APPLICABILITY_PRODUCER_SEAL,
        )

    def authority(self) -> OpeningDeductionApplicabilityAuthority:
        return OpeningDeductionApplicabilityAuthority(
            self._results,
            _seal=_APPLICABILITY_AUTHORITY_SEAL,
        )

    def publish(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionApplicabilityResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")

        void_selector = PhysicalOpeningVoidSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
        )
        void_result = self._void.resolve(void_selector)
        if (
            void_result.status is not EvidenceResolutionStatus.CORROBORATED
            or PHYSICAL_OPENING_VOID_RESOLVED not in void_result.reason_codes
            or void_result.record is None
        ):
            result = _blocked(
                OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
                *(str(item) for item in void_result.reason_codes),
            )
            self._results[selector.key] = result
            return result

        host_selector = OpeningHostBindingSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
        )
        host_result = self._host.resolve(host_selector)
        if (
            host_result.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_HOST_BINDING_RESOLVED not in host_result.reason_codes
            or host_result.record is None
        ):
            result = _blocked(
                OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
                *(str(item) for item in host_result.reason_codes),
            )
            self._results[selector.key] = result
            return result

        void_record = void_result.record
        host_record = host_result.record
        if (
            not _same_lineage(selector, void_record)
            or not _same_lineage(selector, host_record)
            or void_record.opening_identity_id != selector.opening_identity_id
            or host_record.opening_identity_id != selector.opening_identity_id
            or void_record.host_binding_record_id != host_record.record_id
        ):
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH)
            self._results[selector.key] = result
            return result

        target_result = self._target.resolve(selector)
        if (
            target_result.status is not EvidenceResolutionStatus.CORROBORATED
            or target_result.record is None
        ):
            result = _blocked(
                OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
                *(str(item) for item in target_result.reason_codes),
            )
            self._results[selector.key] = result
            return result

        rule_result = self._rule.resolve(selector)
        if (
            rule_result.status is EvidenceResolutionStatus.CONFLICTING
            or OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT in rule_result.reason_codes
        ):
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT)
            self._results[selector.key] = result
            return result
        if (
            rule_result.status is not EvidenceResolutionStatus.CORROBORATED
            or rule_result.record is None
        ):
            result = _blocked(
                OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED,
                *(str(item) for item in rule_result.reason_codes),
            )
            self._results[selector.key] = result
            return result

        target_record = target_result.record
        rule_record = rule_result.record
        if (
            not _same_lineage(selector, target_record)
            or not _same_lineage(selector, rule_record)
            or target_record.target_scope_id != selector.target_scope_id
            or rule_record.target_scope_id != selector.target_scope_id
        ):
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH)
            self._results[selector.key] = result
            return result

        if host_record.host_wall_id != target_record.host_wall_id:
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH)
            self._results[selector.key] = result
            return result
        if target_record.host_wall_id != rule_record.host_wall_id:
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH)
            self._results[selector.key] = result
            return result
        if target_record.trade_scope_id != rule_record.trade_scope_id:
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH)
            self._results[selector.key] = result
            return result
        if target_record.finish_scope_id != rule_record.finish_scope_id:
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH)
            self._results[selector.key] = result
            return result
        if target_record.assembly_scope_id != rule_record.assembly_scope_id:
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH)
            self._results[selector.key] = result
            return result
        if rule_record.effect_kind != SUBTRACT_AUTHENTICATED_PHYSICAL_VOID:
            result = _blocked(OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED)
            self._results[selector.key] = result
            return result

        record_id = stable_contract_id(
            "opening_deduction_applicability",
            {
                "selector": selector.key,
                "host_binding_record_id": host_record.record_id,
                "physical_void_record_id": void_record.record_id,
                "target_scope_record_id": target_record.record_id,
                "rule_record_id": rule_record.record_id,
                "rule_version": rule_record.rule_version,
                "schema_version": OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION,
            },
            digest_chars=32,
        )
        record = OpeningDeductionApplicabilityRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
            host_binding_record_id=host_record.record_id,
            physical_void_record_id=void_record.record_id,
            target_scope_id=selector.target_scope_id,
            target_scope_record_id=target_record.record_id,
            rule_record_id=rule_record.record_id,
            rule_version=rule_record.rule_version,
        )
        result = OpeningDeductionApplicabilityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_DEDUCTION_APPLICABILITY_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = result
        return result


__all__ = [
    "OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION",
    "OPENING_DEDUCTION_APPLICABILITY_RESOLVED",
    "OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED",
    "OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED",
    "OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT",
    "OpeningDeductionApplicabilityAuthority",
    "OpeningDeductionApplicabilityProducer",
    "OpeningDeductionApplicabilityRecord",
    "OpeningDeductionApplicabilityResult",
    "OpeningDeductionApplicabilitySelector",
    "OpeningDeductionTargetScopeAuthority",
    "OpeningDeductionTargetScopeRecord",
    "OpeningDeductionTargetScopeResult",
    "OpeningDeductionRuleAuthority",
    "OpeningDeductionRuleRecord",
    "OpeningDeductionRuleResult",
]
