"""Producer-owned Opening Deduction target-scope and rule authority.

This module builds one authenticated proposition only: an exact physical
opening void applies to one exact measurement target under one exact
source-proven governing rule.

A physical void alone is not deduction permission.  Target scope and governing
rule must come from source-native, producer-owned, trusted PDF text.  No
defaults, standards, workspace settings, or caller-supplied booleans may
establish either.

Public publication surfaces accept selectors only.  Callers cannot supply
wall/trade/finish/assembly truth, applicability booleans, geometry, rule
versions, or commercial state.  Conflicting evidence fails closed.

Architecture
------------
``OpeningDeductionTargetScopeProducer`` reads the complete trusted PDF text
universe (via the sealed ``SourceVisibilityProducer``) and the sealed schedule
binding and host-binding authorities.  It recognises one explicit token class:

    ODTARGET(target=<id>,opening=<mark>,trade=<id>,finish=<id>,assembly=<id>)

``OpeningDeductionRuleProducer`` reads the same universe and recognises:

    ODRULE(target=<id>,opening=<mark>,trade=<id>,finish=<id>,assembly=<id>,
           id=<rule-id>,version=<version>,decision=DEDUCT|RETAIN)

Both producers resolve deterministically: if the complete universe produces
anything other than exactly one matching token the result is CONFLICT or
ABSTAINED.  They never select by confidence, nearest, first, or default.

``OpeningDeductionApplicabilityProducer`` joins the three sealed authorities
(physical void, target scope, governing rule) and verifies lineage, wall/trade/
finish/assembly consistency before emitting a positive applicability record.
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


# ---------------------------------------------------------------------------
# Schema + reason-code constants
# ---------------------------------------------------------------------------

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
OPENING_DEDUCTION_APPLICABILITY_RECORD_UNAVAILABLE = (
    "opening_deduction_applicability_record_unavailable"
)

# Internal-only reason codes (not in public __all__; used by sub-producers)
_TARGET_SCOPE_RESOLVED = "opening_deduction_target_scope_resolved"
_TARGET_SCOPE_UNRESOLVED = "opening_deduction_target_scope_unresolved"
_TARGET_SCOPE_CONFLICT = "opening_deduction_target_scope_conflict"
_RULE_RESOLVED = "opening_deduction_rule_resolved"
_RULE_UNRESOLVED = "opening_deduction_rule_unresolved"
_RULE_CONFLICT = "opening_deduction_rule_conflict"

# ---------------------------------------------------------------------------
# Seals — one per boundary; never shared
# ---------------------------------------------------------------------------
_TARGET_AUTHORITY_SEAL = object()
_RULE_AUTHORITY_SEAL = object()
_APPLICABILITY_AUTHORITY_SEAL = object()
_TARGET_PRODUCER_SEAL = object()
_RULE_PRODUCER_SEAL = object()
_APPLICABILITY_PRODUCER_SEAL = object()

_AppKey = tuple[str, str, str, str, str, str, str, str]

# ---------------------------------------------------------------------------
# Source-text token patterns
# ---------------------------------------------------------------------------
# These patterns accept tokens only from producer-owned trusted PDF text.
# They are intentionally explicit: no construction default, standard name,
# or workspace variable will satisfy the pattern.
_TARGET_RE = re.compile(
    r"^ODTARGET\(target=(?P<target>[A-Za-z0-9_.\-]+),"
    r"opening=(?P<opening>[A-Za-z0-9_.\-]+),"
    r"trade=(?P<trade>[A-Za-z0-9_.\-]+),"
    r"finish=(?P<finish>[A-Za-z0-9_.\-]+),"
    r"assembly=(?P<assembly>[A-Za-z0-9_.\-]+)\)$",
    re.IGNORECASE,
)
_RULE_RE = re.compile(
    r"^ODRULE\(target=(?P<target>[A-Za-z0-9_.\-]+),"
    r"opening=(?P<opening>[A-Za-z0-9_.\-]+),"
    r"trade=(?P<trade>[A-Za-z0-9_.\-]+),"
    r"finish=(?P<finish>[A-Za-z0-9_.\-]+),"
    r"assembly=(?P<assembly>[A-Za-z0-9_.\-]+),"
    r"id=(?P<rule_id>[A-Za-z0-9_.\-]+),"
    r"version=(?P<version>[A-Za-z0-9_.\-]+),"
    r"decision=(?P<decision>DEDUCT|RETAIN)\)$",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _norm(value: object) -> str:
    """Normalise to upper-case for comparison (never used as dedup key alone)."""
    return str(value or "").strip().upper()


def _lineage_ok(
    selector: "OpeningDeductionApplicabilitySelector",
    record: object,
) -> bool:
    """All four source-lineage fields must match the selector exactly."""
    return all(
        getattr(record, field, None) == getattr(selector, field)
        for field in ("document_id", "revision_id", "source_sha256", "snapshot_id")
    )


# ---------------------------------------------------------------------------
# Public selector  (address only — carries no applicability truth)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Target-scope records / results
# ---------------------------------------------------------------------------

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
class OpeningDeductionTargetScopeResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionTargetScopeRecord | None = None


# ---------------------------------------------------------------------------
# Rule records / results
# ---------------------------------------------------------------------------

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
class OpeningDeductionRuleResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionRuleRecord | None = None


# ---------------------------------------------------------------------------
# Applicability records / results
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Internal helpers: _blocked variants
# ---------------------------------------------------------------------------

def _blocked_target(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream: str,
) -> OpeningDeductionTargetScopeResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return OpeningDeductionTargetScopeResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(str(x) for x in upstream if str(x))])),
        record=None,
    )


def _blocked_rule(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream: str,
) -> OpeningDeductionRuleResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return OpeningDeductionRuleResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(str(x) for x in upstream if str(x))])),
        record=None,
    )


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


# ---------------------------------------------------------------------------
# Sealed authorities (lookup-only; minting is reserved for matching producer)
# ---------------------------------------------------------------------------

class OpeningDeductionTargetScopeAuthority:
    """Sealed selector-only lookup for source-proven measurement target scope.

    Minting is intentionally unavailable through this class. A reviewed producer
    derived from authenticated source text must fill it.
    """

    def __init__(
        self,
        results: Mapping[_AppKey, OpeningDeductionTargetScopeResult],
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
                reason_codes=(_TARGET_SCOPE_UNRESOLVED,),
            ),
        )


class OpeningDeductionRuleAuthority:
    """Sealed selector-only lookup for source-proven governing rule."""

    def __init__(
        self,
        results: Mapping[_AppKey, OpeningDeductionRuleResult],
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
                reason_codes=(_RULE_UNRESOLVED,),
            ),
        )


class OpeningDeductionApplicabilityAuthority:
    """Sealed selector-only lookup for published applicability records."""

    def __init__(
        self,
        results: Mapping[_AppKey, OpeningDeductionApplicabilityResult],
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
            OpeningDeductionApplicabilityResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(OPENING_DEDUCTION_APPLICABILITY_RECORD_UNAVAILABLE,),
            ),
        )


# ---------------------------------------------------------------------------
# Internal: complete trusted-text universe reader
# ---------------------------------------------------------------------------

class _TrustedTextUniverse:
    """Reads the complete, producer-owned trusted PDF text for a revision.

    Enforces: complete coverage, no failed pages, exact source lineage.
    Returns None on any breach so callers fail closed immediately.
    """

    def __init__(self, source: SourceVisibilityProducer) -> None:
        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        self._source = source

    def words(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> tuple[tuple[str, str, str], ...] | None:
        """Return (observation_id, trusted_text, page_id) for every trusted word.

        Returns None if the snapshot is missing, lineage mismatches, or coverage
        is not explicitly complete with no failed pages.
        """
        published = self._source.published_snapshot_for_revision(selector.revision_id)
        if published is None:
            return None
        rev = published.revision
        snap = published.snapshot
        cov = published.coverage
        if (
            rev.document_id != selector.document_id
            or rev.revision_id != selector.revision_id
            or rev.source_sha256 != selector.source_sha256
            or snap.snapshot_id != selector.snapshot_id
            or cov.state != "complete"
            or bool(cov.failed_pages)
        ):
            return None
        text_auth = self._source.text_integrity_authority()
        resolved: list[tuple[str, str, str]] = []
        for obs_id in published.text_observation_ids:
            result = text_auth.resolve_text(
                ObservationSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    observation_id=obs_id,
                )
            )
            if (
                result.status is EvidenceResolutionStatus.CORROBORATED
                and result.proposition == TRUSTED_PDF_TEXT
                and result.trusted_text is not None
                and result.receipt is not None
            ):
                resolved.append((obs_id, result.trusted_text, result.receipt.page_id))
        return tuple(resolved)


# ---------------------------------------------------------------------------
# Source-backed Target-Scope Producer
# ---------------------------------------------------------------------------

class OpeningDeductionTargetScopeProducer:
    """Derive a sealed target-scope record from complete trusted source text.

    Only ``ODTARGET(...)`` tokens from native, trusted PDF text are accepted.
    Schedule binding provides the opening mark; host binding provides the wall
    identity.  Any source universe gap or ambiguity fails closed.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        schedule_binding_authority: ScheduleOpeningInstanceBindingAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _TARGET_PRODUCER_SEAL:
            raise TypeError(
                "OpeningDeductionTargetScopeProducer must be obtained from from_authorities()"
            )
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

    def publish(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionTargetScopeResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        if selector.key in self._results:
            return self._results[selector.key]

        # 1. Resolve schedule binding → opening mark
        sched_result = self._schedule.resolve(
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
            sched_result.status is not EvidenceResolutionStatus.CORROBORATED
            or BINDING_RESOLVED not in sched_result.reason_codes
            or sched_result.record is None
        ):
            result = _blocked_target(
                sched_result.status,
                _TARGET_SCOPE_UNRESOLVED,
                *sched_result.reason_codes,
            )
            self._results[selector.key] = result
            return result
        opening_mark = _norm(sched_result.record.tag_mark)

        # 2. Resolve host binding → wall identity
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
        if (
            host_result.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_HOST_BINDING_RESOLVED not in host_result.reason_codes
            or host_result.record is None
        ):
            result = _blocked_target(
                host_result.status,
                _TARGET_SCOPE_UNRESOLVED,
                *host_result.reason_codes,
            )
            self._results[selector.key] = result
            return result
        host_record = host_result.record

        # 3. Enumerate complete trusted-text universe — fail if incomplete
        words = self._text.words(selector)
        if words is None:
            result = _blocked_target(EvidenceResolutionStatus.ABSTAINED, _TARGET_SCOPE_UNRESOLVED)
            self._results[selector.key] = result
            return result

        # 4. Match ODTARGET tokens deterministically
        #    Key: normalised (target, opening, trade, finish, assembly, page_id)
        #    Value: (observation_id, re.Match)
        #    Multiple distinct keys → CONFLICT; zero → ABSTAINED
        matches: dict[tuple[str, ...], tuple[str, re.Match[str]]] = {}
        for obs_id, raw, page_id in words:
            m = _TARGET_RE.fullmatch(raw.strip())
            if m is None:
                continue
            if _norm(m.group("target")) != _norm(selector.target_scope_id):
                continue
            if _norm(m.group("opening")) != opening_mark:
                continue
            payload_key = (
                _norm(m.group("target")),
                opening_mark,
                _norm(m.group("trade")),
                _norm(m.group("finish")),
                _norm(m.group("assembly")),
                page_id,
            )
            # First occurrence wins for an identical payload_key (deterministic)
            matches.setdefault(payload_key, (obs_id, m))

        if len(matches) == 0:
            result = _blocked_target(EvidenceResolutionStatus.ABSTAINED, _TARGET_SCOPE_UNRESOLVED)
            self._results[selector.key] = result
            return result
        if len(matches) > 1:
            result = _blocked_target(EvidenceResolutionStatus.CONFLICT, _TARGET_SCOPE_CONFLICT)
            self._results[selector.key] = result
            return result

        (_, _, trade_scope_id, finish_scope_id, assembly_scope_id, src_page_id), (
            obs_id,
            m,
        ) = next(iter(matches.items()))

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "target_scope_id": selector.target_scope_id,
            "opening_identity_id": selector.opening_identity_id,
            "opening_mark": opening_mark,
            "host_binding_record_id": host_record.record_id,
            "host_wall_id": host_record.host_wall_id,
            "trade_scope_id": trade_scope_id,
            "finish_scope_id": finish_scope_id,
            "assembly_scope_id": assembly_scope_id,
            "source_observation_id": obs_id,
        }
        record = OpeningDeductionTargetScopeRecord(
            record_id=stable_contract_id(
                "opening_deduction_target_scope", payload, digest_chars=32
            ),
            **payload,
        )
        result = OpeningDeductionTargetScopeResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(_TARGET_SCOPE_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningDeductionTargetScopeAuthority:
        return OpeningDeductionTargetScopeAuthority(
            self._results, _seal=_TARGET_AUTHORITY_SEAL
        )


# ---------------------------------------------------------------------------
# Source-backed Rule Producer
# ---------------------------------------------------------------------------

class OpeningDeductionRuleProducer:
    """Derive the exact governing rule from the complete trusted source-text universe.

    Only ``ODRULE(...)`` tokens from native, trusted PDF text are accepted.
    If the complete universe produces anything other than exactly one DEDUCT
    token for the given target/opening the result is CONFLICT or ABSTAINED.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _RULE_PRODUCER_SEAL:
            raise TypeError(
                "OpeningDeductionRuleProducer must be obtained from from_source_visibility_producer()"
            )
        self._text = _TrustedTextUniverse(source_visibility_producer)
        self._results: dict[_AppKey, OpeningDeductionRuleResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer: SourceVisibilityProducer,
    ) -> "OpeningDeductionRuleProducer":
        return cls(source_visibility_producer, _seal=_RULE_PRODUCER_SEAL)

    def publish(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionRuleResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        if selector.key in self._results:
            return self._results[selector.key]

        words = self._text.words(selector)
        if words is None:
            result = _blocked_rule(EvidenceResolutionStatus.ABSTAINED, _RULE_UNRESOLVED)
            self._results[selector.key] = result
            return result

        # Key: normalised (target, opening, trade, finish, assembly, rule_id, version, decision, page)
        matches: dict[tuple[str, ...], tuple[str, re.Match[str]]] = {}
        for obs_id, raw, page_id in words:
            m = _RULE_RE.fullmatch(raw.strip())
            if m is None:
                continue
            if _norm(m.group("target")) != _norm(selector.target_scope_id):
                continue
            payload_key = (
                _norm(m.group("target")),
                _norm(m.group("opening")),
                _norm(m.group("trade")),
                _norm(m.group("finish")),
                _norm(m.group("assembly")),
                _norm(m.group("rule_id")),
                _norm(m.group("version")),
                _norm(m.group("decision")),
                page_id,
            )
            matches.setdefault(payload_key, (obs_id, m))

        if len(matches) == 0:
            result = _blocked_rule(EvidenceResolutionStatus.ABSTAINED, _RULE_UNRESOLVED)
            self._results[selector.key] = result
            return result
        if len(matches) > 1:
            result = _blocked_rule(EvidenceResolutionStatus.CONFLICT, _RULE_CONFLICT)
            self._results[selector.key] = result
            return result

        (
            _,
            opening_mark,
            trade_scope_id,
            finish_scope_id,
            assembly_scope_id,
            rule_id,
            rule_version,
            decision,
            _,
        ), (obs_id, m) = next(iter(matches.items()))

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "target_scope_id": selector.target_scope_id,
            "opening_mark": opening_mark,
            "trade_scope_id": trade_scope_id,
            "finish_scope_id": finish_scope_id,
            "assembly_scope_id": assembly_scope_id,
            "rule_id": rule_id,
            "rule_version": rule_version,
            "decision": decision,
            "source_observation_id": obs_id,
        }
        record = OpeningDeductionRuleRecord(
            record_id=stable_contract_id(
                "opening_deduction_rule", payload, digest_chars=32
            ),
            **payload,
        )
        result = OpeningDeductionRuleResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(_RULE_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningDeductionRuleAuthority:
        return OpeningDeductionRuleAuthority(self._results, _seal=_RULE_AUTHORITY_SEAL)


# ---------------------------------------------------------------------------
# Applicability Producer
# ---------------------------------------------------------------------------

class OpeningDeductionApplicabilityProducer:
    """Join sealed physical-void, host-binding, target-scope and rule authorities.

    A positive applicability record is emitted only when:
    - the void is CORROBORATED with exact source lineage;
    - the host binding is CORROBORATED and wall identity matches the void;
    - the target scope is CORROBORATED, lineage and wall identity match;
    - the governing rule is CORROBORATED (not conflicted), lineage matches;
    - trade/finish/assembly are consistent between target and rule;
    - rule decision is ``DEDUCT`` (not ``RETAIN``).
    Any inconsistency fails closed.
    """

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
        for value, expected_type, name in (
            (physical_void_authority, PhysicalOpeningVoidAuthority, "physical_void_authority"),
            (host_binding_authority, OpeningHostBindingAuthority, "host_binding_authority"),
            (
                target_scope_authority,
                OpeningDeductionTargetScopeAuthority,
                "target_scope_authority",
            ),
            (rule_authority, OpeningDeductionRuleAuthority, "rule_authority"),
        ):
            if type(value) is not expected_type:
                raise TypeError(f"{name} must be producer-owned {expected_type.__name__}")
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

    def publish(
        self,
        selector: OpeningDeductionApplicabilitySelector,
    ) -> OpeningDeductionApplicabilityResult:
        if type(selector) is not OpeningDeductionApplicabilitySelector:
            raise TypeError("selector must be OpeningDeductionApplicabilitySelector")
        if selector.key in self._results:
            return self._results[selector.key]

        # 1. Re-resolve physical void (source lineage check)
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
            result = _blocked_applicability(
                void_result.status,
                OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
                *void_result.reason_codes,
            )
            self._results[selector.key] = result
            return result

        # 2. Re-resolve host binding and verify consistency with void
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
            status = (
                EvidenceResolutionStatus.CONFLICT
                if host is not None
                else host_result.status
            )
            result = _blocked_applicability(
                status,
                OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH,
                *host_result.reason_codes,
            )
            self._results[selector.key] = result
            return result

        # 3. Target scope
        target_result = self._target.resolve(selector)
        target = target_result.record
        if target_result.status is not EvidenceResolutionStatus.CORROBORATED or target is None:
            result = _blocked_applicability(
                target_result.status,
                OPENING_DEDUCTION_APPLICABILITY_TARGET_UNRESOLVED,
                *target_result.reason_codes,
            )
            self._results[selector.key] = result
            return result

        # Lineage + scope cross-check
        if (
            not _lineage_ok(selector, target)
            or target.page_id != selector.page_id
            or target.decision_scope_id != selector.decision_scope_id
            or _norm(target.target_scope_id) != _norm(selector.target_scope_id)
            or target.opening_identity_id != selector.opening_identity_id
        ):
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
            )
            self._results[selector.key] = result
            return result

        # Target must reference the same host as the void
        if (
            target.host_binding_record_id != host.record_id
            or target.host_wall_id != host.host_wall_id
        ):
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_WALL_SCOPE_MISMATCH,
            )
            self._results[selector.key] = result
            return result

        # 4. Rule
        rule_result = self._rule.resolve(selector)
        rule = rule_result.record
        if rule_result.status is EvidenceResolutionStatus.CONFLICT:
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_RULE_CONFLICT,
                *rule_result.reason_codes,
            )
            self._results[selector.key] = result
            return result
        if rule_result.status is not EvidenceResolutionStatus.CORROBORATED or rule is None:
            result = _blocked_applicability(
                rule_result.status,
                OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED,
                *rule_result.reason_codes,
            )
            self._results[selector.key] = result
            return result

        # Lineage check
        if (
            not _lineage_ok(selector, rule)
            or rule.decision_scope_id != selector.decision_scope_id
            or _norm(rule.target_scope_id) != _norm(selector.target_scope_id)
        ):
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_LINEAGE_MISMATCH,
            )
            self._results[selector.key] = result
            return result

        # Trade / finish / assembly consistency
        if _norm(target.trade_scope_id) != _norm(rule.trade_scope_id):
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_TRADE_SCOPE_MISMATCH,
            )
            self._results[selector.key] = result
            return result
        if _norm(target.finish_scope_id) != _norm(rule.finish_scope_id):
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_FINISH_SCOPE_MISMATCH,
            )
            self._results[selector.key] = result
            return result
        if _norm(target.assembly_scope_id) != _norm(rule.assembly_scope_id):
            result = _blocked_applicability(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_APPLICABILITY_ASSEMBLY_SCOPE_MISMATCH,
            )
            self._results[selector.key] = result
            return result

        # Rule must say DEDUCT (not RETAIN or anything else)
        if _norm(rule.decision) != "DEDUCT":
            result = _blocked_applicability(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_DEDUCTION_APPLICABILITY_RULE_UNRESOLVED,
            )
            self._results[selector.key] = result
            return result

        # 5. Positive record
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
            record_id=stable_contract_id(
                "opening_deduction_applicability", payload, digest_chars=32
            ),
            **payload,
        )
        result = OpeningDeductionApplicabilityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_DEDUCTION_APPLICABILITY_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningDeductionApplicabilityAuthority:
        return OpeningDeductionApplicabilityAuthority(
            self._results, _seal=_APPLICABILITY_AUTHORITY_SEAL
        )


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------

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
    "OpeningDeductionTargetScopeResult",
    "OpeningDeductionTargetScopeAuthority",
    "OpeningDeductionTargetScopeProducer",
    "OpeningDeductionRuleRecord",
    "OpeningDeductionRuleResult",
    "OpeningDeductionRuleAuthority",
    "OpeningDeductionRuleProducer",
    "OpeningDeductionApplicabilityRecord",
    "OpeningDeductionApplicabilityResult",
    "OpeningDeductionApplicabilityAuthority",
    "OpeningDeductionApplicabilityProducer",
]
