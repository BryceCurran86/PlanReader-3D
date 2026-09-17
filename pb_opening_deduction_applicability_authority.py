"""Producer-owned Opening Deduction target-applicability authority.

This module proves one proposition only: one already-authenticated physical opening
void applies to one exact measurement target under one exact source-proven rule.
A physical void is never sufficient by itself.

Target and rule semantics are derived from the complete producer-owned trusted PDF
text universe.  Public publication boundaries accept selectors only; callers cannot
supply wall/trade/finish/assembly truth, applicability booleans, geometry, rule
versions, or commercial state.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_pdf_text_integrity_authority import TRUSTED_PDF_TEXT
from pb_physical_opening_void_authority import (
    PHYSICAL_OPENING_VOID_RESOLVED,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidSelector,
)
from pb_schedule_opening_instance_binding_authority import (
    BINDING_RESOLVED,
    ScheduleOpeningInstanceBindingAuthority,
    ScheduleOpeningInstanceBindingSelector,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION = "1.0.0"

OPENING_DEDUCTION_APPLICABILITY_RESOLVED = "opening_deduction_applicability_resolved"
OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED = "opening_deduction_applicability_target_unresolved"
OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED = "opening_deduction_applicability_rule_unresolved"
OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH = "opening_deduction_applicability_wall_scope_mismatch"
OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH = "opening_deduction_applicability_trade_scope_mismatch"
OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH = "opening_deduction_applicability_finish_scope_mismatch"
OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH = "opening_deduction_applicability_assembly_scope_mismatch"
OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH = "opening_deduction_applicability_lineage_mismatch"
OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT = "opening_deduction_applicability_rule_conflict"
OPENING_DEDUCTION_APPLICABILITY_RECORD_UNAVAILABLE = "opening_deduction_applicability_record_unavailable"

_TARGET_SCOPE_RESOLVED = "opening_deduction_target_scope_resolved"
_TARGET_SCOPE_UNRESOLVED = "opening_deduction_target_scope_unresolved"
_TARGET_SCOPE_CONFLICT = "opening_deduction_target_scope_conflict"
_RULE_RESOLVED = "opening_deduction_rule_resolved"
_RULE_UNRESOLVED = "opening_deduction_rule_unresolved"
_RULE_CONFLICT = "opening_deduction_rule_conflict"

_AUTHORITY_SEAL = object()
_TARGET_AUTHORITY_SEAL = object()
_RULE_AUTHORITY_SEAL = object()
_TARGET_PRODUCER_SEAL = object()
_RULE_PRODUCER_SEAL = object()
_APPLICABILITY_PRODUCER_SEAL = object()

_AppKey = tuple[str, str, str, str, str, str, str, str]

# Deliberately explicit project-source syntax. These tokens are evidence, not defaults.
# They are accepted only from producer-owned trusted native PDF text.
_TARGET_RE = re.compile(
    r"^ODTARGET\(target=(?P<target>[A-Za-z0-9_.-]+),"
    r"opening=(?P<opening>[A-Za-z0-9_.-]+),"
    r"trade=(?P<trade>[A-Za-z0-9_.-]+),"
    r"finish=(?P<finish>[A-Za-z0-9_.-]+),"
    r"assembly=(?P<assembly>[A-Za-z0-9_.-]+)\)$",
    re.IGNORECASE,
)
_RULE_RE = re.compile(
    r"^ODRULE\(target=(?P<target>[A-Za-z0-9_.-]+),"
    r"opening=(?P<opening>[A-Za-z0-9_.-]+),"
    r"trade=(?P<trade>[A-Za-z0-9_.-]+),"
    r"finish=(?P<finish>[A-Za-z0-9_.-]+),"
    r"assembly=(?P<assembly>[A-Za-z0-9_.-]+),"
    r"id=(?P<rule_id>[A-Za-z0-9_.-]+),"
    r"version=(?P<version>[A-Za-z0-9_.-]+),"
    r"decision=(?P<decision>DEDUCT|RETAIN)\)$",
    re.IGNORECASE,
)


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _norm(value: object) -> str:
    return str(value or "").strip().upper()


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
    def key(self) -> _AppKey:
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
    opening_identity_id: str
    opening_mark: str
    host_binding_record_id: str
    host_wall_id: str
    trade_scope_id: str
    finish_scope_id: str
    assembly_scope_id: str
    source_observation_id: str
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
    opening_mark: str
    trade_scope_id: str
    finish_scope_id: str
    assembly_scope_id: str
    rule_id: str
    rule_version: str
    decision: str
    source_observation_id: str
    schema_version: str = OPENING_DEDUCTION_APPLICABILITY_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionTargetScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionTargetScopeRecord | None = None


@dataclass(frozen=True)
class OpeningDeductionRuleResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionRuleRecord | None = None


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


def _blocked_applicability(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream: str,
) -> OpeningDeductionApplicabilityResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return OpeningDeductionApplicabilityResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(str(x) for x in upstream if str(x))])),
        record=None,
    )


def _lineage_matches(selector: OpeningDeductionApplicabilitySelector, record: object) -> bool:
    return all(
        getattr(record, name, None) == getattr(selector, name)
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id")
    )


class OpeningDeductionTargetScopeAuthority:
    """Sealed selector-only lookup for source-proven measurement target scope."""

    def __init__(
        self,
        results: Mapping[_AppKey, OpeningDeductionTargetScopeResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _TARGET_AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionTargetScopeAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningDeductionApplicabilitySelector) -> OpeningDeductionTargetScopeResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        return self._results.get(
            selector.key,
            OpeningDeductionTargetScopeResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(_TARGET_SCOPE_UNRESOLVED,),
            ),
        )


class OpeningDeductionRuleAuthority:
    """Sealed selector-only lookup for an exact source-proven governing rule."""

    def __init__(
        self,
        results: Mapping[_AppKey, OpeningDeductionRuleResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _RULE_AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionRuleAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningDeductionApplicabilitySelector) -> OpeningDeductionRuleResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        return self._results.get(
            selector.key,
            OpeningDeductionRuleResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(_RULE_UNRESOLVED,),
            ),
        )


class _TrustedTextUniverse:
    def __init__(self, source_visibility_producer: SourceVisibilityProducer) -> None:
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned SourceVisibilityProducer")
        self._source = source_visibility_producer

    def words(self, selector: OpeningDeductionApplicabilitySelector) -> tuple[tuple[str, str, str], ...] | None:
        published = self._source.published_snapshot_for_revision(selector.revision_id)
        if (
            published is None
            or published.revision.document_id != selector.document_id
            or published.revision.revision_id != selector.revision_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or published.coverage.state != "complete"
            or bool(published.coverage.failed_pages)
        ):
            return None
        text = self._source.text_integrity_authority()
        resolved: list[tuple[str, str, str]] = []
        for observation_id in published.text_observation_ids:
            result = text.resolve_text(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=observation_id,
                )
            )
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.proposition == TRUSTED_PDF_TEXT
                and result.trusted_text is not None
                and result.receipt is not None
            ):
                resolved.append((observation_id, result.trusted_text, result.receipt.page_id))
        return tuple(resolved)


class OpeningDeductionTargetScopeProducer:
    """Derive an exact target from complete trusted source text and sealed bindings."""

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        schedule_binding_authority: ScheduleOpeningInstanceBindingAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _TARGET_PRODUCER_SEAL:
            raise TypeError("OpeningDeductionTargetScopeProducer must be obtained from from_authorities()")
        if type(schedule_binding_authority) is not ScheduleOpeningInstanceBindingAuthority:
            raise TypeError("schedule_binding_authority must be producer-owned")
        if type(host_binding_authority) is not OpeningHostBindingAuthority:
            raise TypeError("host_binding_authority must be producer-owned")
        self._text = _TrustedTextUniverse(source_visibility_producer)
        self._schedule = schedule_binding_authority
        self._host = host_binding_authority
        self._results: dict[_AppKey, OpeningDeductionTargetScopeResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        source_visibility_producer: SourceVisibilityProducer,
        schedule_binding_authority: ScheduleOpeningInstanceBindingAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
    ) -> "OpeningDeductionTargetScopeProducer":
        return cls(
            source_visibility_producer,
            schedule_binding_authority,
            host_binding_authority,
            _seal=_TARGET_PRODUCER_SEAL,
        )

    def publish(self, selector: OpeningDeductionApplicabilitySelector) -> OpeningDeductionTargetScopeResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        schedule = self._schedule.resolve(
            ScheduleOpeningInstanceBindingSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                decision_scope_id=selector.decision_scope_id,
                opening_record_id=selector.opening_identity_id,
            )
        )
        if (
            schedule.status is not EvidenceResolutionStatus.CORROBORATED
            or BINDING_RESOLVED not in schedule.reason_codes
            or schedule.record is None
        ):
            result = OpeningDeductionTargetScopeResult(
                EvidenceResolutionStatus.ABSTAINED,
                (_TARGET_SCOPE_UNRESOLVED, *schedule.reason_codes),
            )
            self._results[selector.key] = result
            return result
        host = self._host.resolve(
            OpeningHostBindingSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                opening_identity_id=selector.opening_identity_id,
            )
        )
        if (
            host.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_HOST_BINDING_RESOLVED not in host.reason_codes
            or host.record is None
        ):
            result = OpeningDeductionTargetScopeResult(
                EvidenceResolutionStatus.ABSTAINED,
                (_TARGET_SCOPE_UNRESOLVED, *host.reason_codes),
            )
            self._results[selector.key] = result
            return result
        words = self._text.words(selector)
        if words is None:
            result = OpeningDeductionTargetScopeResult(
                EvidenceResolutionStatus.ABSTAINED, (_TARGET_SCOPE_UNRESOLVED,)
            )
            self._results[selector.key] = result
            return result
        matches: dict[tuple[str, ...], tuple[str, re.Match[str]]] = {}
        for observation_id, raw, page_id in words:
            match = _TARGET_RE.fullmatch(raw.strip())
            if match is None:
                continue
            if _norm(match.group("target")) != _norm(selector.target_scope_id):
                continue
            if _norm(match.group("opening")) != _norm(schedule.record.tag_mark):
                continue
            payload_key = (
                _norm(match.group("target")),
                _norm(match.group("opening")),
                _norm(match.group("trade")),
                _norm(match.group("finish")),
                _norm(match.group("assembly")),
                page_id,
            )
            matches.setdefault(payload_key, (observation_id, match))
        if len(matches) != 1:
            status = EvidenceResolutionStatus.CONFLICT if len(matches) > 1 else EvidenceResolutionStatus.ABSTAINED
            reason = _TARGET_SCOPE_CONFLICT if len(matches) > 1 else _TARGET_SCOPE_UNRESOLVED
            result = OpeningDeductionTargetScopeResult(status, (reason,))
            self._results[selector.key] = result
            return result
        (_, _, trade_scope_id, finish_scope_id, assembly_scope_id, source_page_id), (observation_id, match) = next(iter(matches.items()))
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "target_scope_id": selector.target_scope_id,
            "opening_identity_id": selector.opening_identity_id,
            "opening_mark": _norm(schedule.record.tag_mark),
            "host_binding_record_id": host.record.record_id,
            "host_wall_id": host.record.host_wall_id,
            "trade_scope_id": trade_scope_id,
            "finish_scope_id": finish_scope_id,
            "assembly_scope_id": assembly_scope_id,
            "source_observation_id": observation_id,
            "source_page_id": source_page_id,
        }
        record = OpeningDeductionTargetScopeRecord(
            record_id=stable_contract_id("opening_deduction_target_scope", payload, digest_chars=32),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            target_scope_id=selector.target_scope_id,
            opening_identity_id=selector.opening_identity_id,
            opening_mark=_norm(schedule.record.tag_mark),
            host_binding_record_id=host.record.record_id,
            host_wall_id=host.record.host_wall_id,
            trade_scope_id=trade_scope_id,
            finish_scope_id=finish_scope_id,
            assembly_scope_id=assembly_scope_id,
            source_observation_id=observation_id,
        )
        result = OpeningDeductionTargetScopeResult(
            EvidenceResolutionStatus.CORROBORATED, (_TARGET_SCOPE_RESOLVED,), record
        )
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningDeductionTargetScopeAuthority:
        return OpeningDeductionTargetScopeAuthority(self._results, _seal=_TARGET_AUTHORITY_SEAL)


class OpeningDeductionRuleProducer:
    """Derive the exact governing rule from the complete trusted source-text universe."""

    def __init__(self, source_visibility_producer: SourceVisibilityProducer, *, _seal: object = None) -> None:
        if _seal is not _RULE_PRODUCER_SEAL:
            raise TypeError("OpeningDeductionRuleProducer must be obtained from from_source_visibility_producer()")
        self._text = _TrustedTextUniverse(source_visibility_producer)
        self._results: dict[_AppKey, OpeningDeductionRuleResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls, source_visibility_producer: SourceVisibilityProducer
    ) -> "OpeningDeductionRuleProducer":
        return cls(source_visibility_producer, _seal=_RULE_PRODUCER_SEAL)

    def publish(self, selector: OpeningDeductionApplicabilitySelector) -> OpeningDeductionRuleResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        words = self._text.words(selector)
        if words is None:
            result = OpeningDeductionRuleResult(EvidenceResolutionStatus.ABSTAINED, (_RULE_UNRESOLVED,))
            self._results[selector.key] = result
            return result
        matches: dict[tuple[str, ...], tuple[str, re.Match[str], str]] = {}
        for observation_id, raw, page_id in words:
            match = _RULE_RE.fullmatch(raw.strip())
            if match is None or _norm(match.group("target")) != _norm(selector.target_scope_id):
                continue
            key = tuple(
                _norm(match.group(name))
                for name in ("target", "opening", "trade", "finish", "assembly", "rule_id", "version", "decision")
            )
            matches.setdefault(key, (observation_id, match, page_id))
        if not matches:
            result = OpeningDeductionRuleResult(EvidenceResolutionStatus.ABSTAINED, (_RULE_UNRESOLVED,))
            self._results[selector.key] = result
            return result
        if len(matches) != 1:
            result = OpeningDeductionRuleResult(EvidenceResolutionStatus.CONFLICT, (_RULE_CONFLICT,))
            self._results[selector.key] = result
            return result
        key, (observation_id, match, source_page_id) = next(iter(matches.items()))
        target_scope_id, opening_mark, trade_scope_id, finish_scope_id, assembly_scope_id, rule_id, rule_version, decision = key
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "decision_scope_id": selector.decision_scope_id,
            "target_scope_id": target_scope_id,
            "opening_mark": opening_mark,
            "trade_scope_id": trade_scope_id,
            "finish_scope_id": finish_scope_id,
            "assembly_scope_id": assembly_scope_id,
            "rule_id": rule_id,
            "rule_version": rule_version,
            "decision": decision,
            "source_observation_id": observation_id,
            "source_page_id": source_page_id,
        }
        record = OpeningDeductionRuleRecord(
            record_id=stable_contract_id("opening_deduction_rule", payload, digest_chars=32),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=source_page_id,
            decision_scope_id=selector.decision_scope_id,
            target_scope_id=target_scope_id,
            opening_mark=opening_mark,
            trade_scope_id=trade_scope_id,
            finish_scope_id=finish_scope_id,
            assembly_scope_id=assembly_scope_id,
            rule_id=rule_id,
            rule_version=rule_version,
            decision=decision,
            source_observation_id=observation_id,
        )
        result = OpeningDeductionRuleResult(EvidenceResolutionStatus.CORROBORATED, (_RULE_RESOLVED,), record)
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningDeductionRuleAuthority:
        return OpeningDeductionRuleAuthority(self._results, _seal=_RULE_AUTHORITY_SEAL)


class OpeningDeductionApplicabilityAuthority:
    """Sealed selector-only lookup for published applicability decisions."""

    def __init__(
        self,
        results: Mapping[_AppKey, OpeningDeductionApplicabilityResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionApplicabilityAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningDeductionApplicabilitySelector) -> OpeningDeductionApplicabilityResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        return self._results.get(
            selector.key,
            _blocked_applicability(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_DEDUCTION_APPLICABILITY_RECORD_UNAVAILABLE,
            ),
        )


class OpeningDeductionApplicabilityProducer:
    """Join exact physical void, host, target scope and governing rule authorities."""

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
            raise TypeError("OpeningDeductionApplicabilityProducer must be obtained from from_authorities()")
        expected = (
            (physical_void_authority, PhysicalOpeningVoidAuthority, "physical_void_authority"),
            (host_binding_authority, OpeningHostBindingAuthority, "host_binding_authority"),
            (target_scope_authority, OpeningDeductionTargetScopeAuthority, "target_scope_authority"),
            (rule_authority, OpeningDeductionRuleAuthority, "rule_authority"),
        )
        for value, required_type, name in expected:
            if type(value) is not required_type:
                raise TypeError(f"{name} must be producer-owned {required_type.__name__}")
        self._void = physical_void_authority
        self._host = host_binding_authority
        self._target = target_scope_authority
        self._rule = rule_authority
        self._results: dict[_AppKey, OpeningDeductionApplicabilityResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
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

    def _store(
        self,
        selector: OpeningDeductionApplicabilitySelector,
        result: OpeningDeductionApplicabilityResult,
    ) -> OpeningDeductionApplicabilityResult:
        previous = self._results.get(selector.key)
        if previous is not None and previous != result:
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
                "opening_deduction_applicability_producer_equivocation",
            )
        self._results[selector.key] = result
        return result

    def publish(self, selector: OpeningDeductionApplicabilitySelector) -> OpeningDeductionApplicabilityResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        void_result = self._void.resolve(
            PhysicalOpeningVoidSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                opening_identity_id=selector.opening_identity_id,
            )
        )
        void = void_result.record
        if (
            void_result.status is not EvidenceResolutionStatus.CORROBORATED
            or PHYSICAL_OPENING_VOID_RESOLVED not in void_result.reason_codes
            or void is None
        ):
            return self._store(
                selector,
                _blocked_applicability(
                    void_result.status,
                    OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
                    *void_result.reason_codes,
                ),
            )
        host_result = self._host.resolve(
            OpeningHostBindingSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
                opening_identity_id=selector.opening_identity_id,
            )
        )
        host = host_result.record
        if (
            host_result.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_HOST_BINDING_RESOLVED not in host_result.reason_codes
            or host is None
            or host.record_id != void.host_binding_record_id
            or host.host_wall_id != void.host_wall_id
        ):
            return self._store(
                selector,
                _blocked_applicability(
                    EvidenceResolutionStatus.CONFLICT if host is not None else host_result.status,
                    OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH,
                    *host_result.reason_codes,
                ),
            )
        target_result = self._target.resolve(selector)
        target = target_result.record
        if target_result.status is not EvidenceResolutionStatus.CORROBORATED or target is None:
            return self._store(
                selector,
                _blocked_applicability(
                    target_result.status,
                    OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
                    *target_result.reason_codes,
                ),
            )
        if (
            not _lineage_matches(selector, target)
            or target.page_id != selector.page_id
            or target.decision_scope_id != selector.decision_scope_id
            or target.target_scope_id != selector.target_scope_id
            or target.opening_identity_id != selector.opening_identity_id
        ):
            return self._store(
                selector,
                _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH),
            )
        if target.host_binding_record_id != host.record_id or target.host_wall_id != host.host_wall_id:
            return self._store(
                selector,
                _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH),
            )
        rule_result = self._rule.resolve(selector)
        rule = rule_result.record
        if rule_result.status is EvidenceResolutionStatus.CONFLICT:
            return self._store(
                selector,
                _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT, *rule_result.reason_codes),
            )
        if rule_result.status is not EvidenceResolutionStatus.CORROBORATED or rule is None:
            return self._store(
                selector,
                _blocked_applicability(rule_result.status, OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED, *rule_result.reason_codes),
            )
        if (
            not _lineage_matches(selector, rule)
            or rule.decision_scope_id != selector.decision_scope_id
            or _norm(rule.target_scope_id) != _norm(selector.target_scope_id)
        ):
            return self._store(
                selector,
                _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH),
            )
        if _norm(target.opening_mark) != _norm(rule.opening_mark):
            return self._store(
                selector,
                _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH),
            )
        if _norm(target.trade_scope_id) != _norm(rule.trade_scope_id):
            return self._store(selector, _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH))
        if _norm(target.finish_scope_id) != _norm(rule.finish_scope_id):
            return self._store(selector, _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH))
        if _norm(target.assembly_scope_id) != _norm(rule.assembly_scope_id):
            return self._store(selector, _blocked_applicability(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH))
        if _norm(rule.decision) != "DEDUCT":
            return self._store(selector, _blocked_applicability(EvidenceResolutionStatus.ABSTAINED, OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED))
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "opening_identity_id": selector.opening_identity_id,
            "host_binding_record_id": host.record_id,
            "physical_void_record_id": void.record_id,
            "target_scope_id": selector.target_scope_id,
            "target_scope_record_id": target.record_id,
            "rule_record_id": rule.record_id,
            "rule_version": rule.rule_version,
        }
        record = OpeningDeductionApplicabilityRecord(
            record_id=stable_contract_id("opening_deduction_applicability", payload, digest_chars=32),
            **payload,
        )
        return self._store(
            selector,
            OpeningDeductionApplicabilityResult(
                EvidenceResolutionStatus.CORROBORATED,
                (OPENING_DEDUCTION_APPLICABILITY_RESOLVED,),
                record,
            ),
        )

    def authority(self) -> OpeningDeductionApplicabilityAuthority:
        return OpeningDeductionApplicabilityAuthority(self._results, _seal=_AUTHORITY_SEAL)


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
    "OPENING_DEDUCTION_APPLICABILITY_RECORD_UNAVAILABLE",
    "OpeningDeductionApplicabilitySelector",
    "OpeningDeductionTargetScopeRecord",
    "OpeningDeductionRuleRecord",
    "OpeningDeductionTargetScopeResult",
    "OpeningDeductionRuleResult",
    "OpeningDeductionApplicabilityRecord",
    "OpeningDeductionApplicabilityResult",
    "OpeningDeductionTargetScopeAuthority",
    "OpeningDeductionRuleAuthority",
    "OpeningDeductionTargetScopeProducer",
    "OpeningDeductionRuleProducer",
    "OpeningDeductionApplicabilityAuthority",
    "OpeningDeductionApplicabilityProducer",
]
