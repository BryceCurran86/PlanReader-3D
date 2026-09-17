"""Producer-owned Opening Deduction Authority V2.

This is the final authorization boundary between an authenticated physical opening
void and an exact opening-deduction target.  It publishes a positive deduction
record only when the physical void, host binding, complete opening universe, and
separate producer-owned target-applicability authority all replay positively on the
same immutable source lineage.

The selector is address-only.  No geometry, scalar area, host choice, target
semantics, applicability boolean, rule identifier, confidence, or commercial state
is accepted at the public boundary.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_deduction_applicability_authority import (
    OPENING_DEDUCTION_APPLICABILITY_RESOLVED,
    OpeningDeductionApplicabilityAuthority,
    OpeningDeductionApplicabilitySelector,
)
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_physical_opening_void_authority import (
    PHYSICAL_OPENING_VOID_RESOLVED,
    PhysicalOpeningVoidAuthority,
    PhysicalOpeningVoidSelector,
)


OPENING_DEDUCTION_SCHEMA_VERSION = "2.0.0"
OPENING_DEDUCTION_AUTHORIZED = "opening_deduction_authorized"
OPENING_DEDUCTION_OPENING_UNRESOLVED = "opening_deduction_opening_unresolved"
OPENING_DEDUCTION_HOST_UNRESOLVED = "opening_deduction_host_unresolved"
OPENING_DEDUCTION_VOID_UNRESOLVED = "opening_deduction_void_unresolved"
OPENING_DEDUCTION_UNIVERSE_INCOMPLETE = "opening_deduction_universe_incomplete"
OPENING_DEDUCTION_WALL_SCOPE_MISMATCH = "opening_deduction_wall_scope_mismatch"
OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED = "opening_deduction_applicability_unresolved"
OPENING_DEDUCTION_LINEAGE_MISMATCH = "opening_deduction_lineage_mismatch"
OPENING_DEDUCTION_RECORD_UNAVAILABLE = "opening_deduction_record_unavailable"

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class OpeningDeductionSelector:
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
class OpeningDeductionRecord:
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
    opening_universe_record_id: str
    target_scope_id: str
    applicability_record_id: str
    schema_version: str = OPENING_DEDUCTION_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningDeductionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: OpeningDeductionRecord | None = None
    schema_version: str = OPENING_DEDUCTION_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream_reasons: str,
) -> OpeningDeductionResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return OpeningDeductionResult(
        status=status,
        reason_codes=tuple(
            dict.fromkeys([reason, *(str(item) for item in upstream_reasons if str(item))])
        ),
        record=None,
    )


def _lineage_matches(selector: OpeningDeductionSelector, record: object) -> bool:
    return all(
        getattr(record, name, None) == getattr(selector, name)
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id")
    )


class OpeningDeductionAuthority:
    """Sealed selector-only lookup for published deduction authorization records."""

    def __init__(
        self,
        results: Mapping[_Key, OpeningDeductionResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningDeductionAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningDeductionSelector) -> OpeningDeductionResult:
        if type(selector) is not OpeningDeductionSelector:
            raise TypeError("selector must be OpeningDeductionSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_DEDUCTION_RECORD_UNAVAILABLE,
                OPENING_DEDUCTION_OPENING_UNRESOLVED,
            ),
        )


class OpeningDeductionProducer:
    """Trusted writer over four separate sealed upstream propositions."""

    def __init__(
        self,
        physical_void_authority: PhysicalOpeningVoidAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        target_applicability_authority: OpeningDeductionApplicabilityAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("OpeningDeductionProducer must be obtained from from_authorities()")
        expected = (
            (physical_void_authority, PhysicalOpeningVoidAuthority, "physical_void_authority"),
            (host_binding_authority, OpeningHostBindingAuthority, "host_binding_authority"),
            (
                opening_universe_authority,
                OpeningUniverseCompletenessAuthority,
                "opening_universe_authority",
            ),
            (
                target_applicability_authority,
                OpeningDeductionApplicabilityAuthority,
                "target_applicability_authority",
            ),
        )
        for value, required_type, name in expected:
            if type(value) is not required_type:
                raise TypeError(f"{name} must be producer-owned {required_type.__name__}")
        self._void = physical_void_authority
        self._host = host_binding_authority
        self._universe = opening_universe_authority
        self._applicability = target_applicability_authority
        self._results: dict[_Key, OpeningDeductionResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_void_authority: PhysicalOpeningVoidAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        target_applicability_authority: OpeningDeductionApplicabilityAuthority,
    ) -> "OpeningDeductionProducer":
        return cls(
            physical_void_authority,
            host_binding_authority,
            opening_universe_authority,
            target_applicability_authority,
            _seal=_PRODUCER_SEAL,
        )

    def _store(
        self,
        selector: OpeningDeductionSelector,
        result: OpeningDeductionResult,
    ) -> OpeningDeductionResult:
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            result = _blocked(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_DEDUCTION_LINEAGE_MISMATCH,
                "opening_deduction_producer_equivocation",
            )
        self._results[selector.key] = result
        return result

    def publish(self, selector: OpeningDeductionSelector) -> OpeningDeductionResult:
        if type(selector) is not OpeningDeductionSelector:
            raise TypeError("selector must be OpeningDeductionSelector")

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
        void_record = void_result.record
        if (
            void_result.status is not EvidenceResolutionStatus.CORROBORATED
            or PHYSICAL_OPENING_VOID_RESOLVED not in void_result.reason_codes
            or void_record is None
        ):
            return self._store(
                selector,
                _blocked(
                    void_result.status,
                    OPENING_DEDUCTION_VOID_UNRESOLVED,
                    *void_result.reason_codes,
                ),
            )
        if (
            not _lineage_matches(selector, void_record)
            or void_record.page_id != selector.page_id
            or void_record.decision_scope_id != selector.decision_scope_id
            or void_record.opening_identity_id != selector.opening_identity_id
        ):
            return self._store(
                selector,
                _blocked(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_LINEAGE_MISMATCH),
            )

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
        host_record = host_result.record
        if (
            host_result.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_HOST_BINDING_RESOLVED not in host_result.reason_codes
            or host_record is None
        ):
            return self._store(
                selector,
                _blocked(
                    host_result.status,
                    OPENING_DEDUCTION_HOST_UNRESOLVED,
                    *host_result.reason_codes,
                ),
            )
        if (
            not _lineage_matches(selector, host_record)
            or host_record.page_id != selector.page_id
            or host_record.decision_scope_id != selector.decision_scope_id
            or host_record.opening_identity_id != selector.opening_identity_id
            or host_record.record_id != void_record.host_binding_record_id
            or host_record.host_wall_id != void_record.host_wall_id
        ):
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    OPENING_DEDUCTION_WALL_SCOPE_MISMATCH,
                    OPENING_DEDUCTION_LINEAGE_MISMATCH,
                ),
            )

        universe_selector = OpeningUniverseSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
        )
        universe_result = self._universe.resolve(universe_selector)
        universe_record = universe_result.record
        if (
            universe_result.status is not EvidenceResolutionStatus.CORROBORATED
            or universe_result.decision_scope_complete is not True
            or universe_record is None
            or universe_record.decision_scope_complete is not True
        ):
            return self._store(
                selector,
                _blocked(
                    universe_result.status,
                    OPENING_DEDUCTION_UNIVERSE_INCOMPLETE,
                    *universe_result.reason_codes,
                ),
            )
        if (
            not _lineage_matches(selector, universe_record)
            or universe_record.decision_scope_id != selector.decision_scope_id
            or selector.page_id not in universe_record.page_ids
            or universe_record.record_id != void_record.opening_universe_record_id
        ):
            return self._store(
                selector,
                _blocked(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_LINEAGE_MISMATCH),
            )

        applicability_selector = OpeningDeductionApplicabilitySelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
            target_scope_id=selector.target_scope_id,
        )
        applicability_result = self._applicability.resolve(applicability_selector)
        applicability_record = applicability_result.record
        if (
            applicability_result.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_DEDUCTION_APPLICABILITY_RESOLVED not in applicability_result.reason_codes
            or applicability_record is None
        ):
            return self._store(
                selector,
                _blocked(
                    applicability_result.status,
                    OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED,
                    *applicability_result.reason_codes,
                ),
            )
        if (
            not _lineage_matches(selector, applicability_record)
            or applicability_record.page_id != selector.page_id
            or applicability_record.decision_scope_id != selector.decision_scope_id
            or applicability_record.opening_identity_id != selector.opening_identity_id
            or applicability_record.target_scope_id != selector.target_scope_id
            or applicability_record.host_binding_record_id != host_record.record_id
            or applicability_record.physical_void_record_id != void_record.record_id
        ):
            return self._store(
                selector,
                _blocked(EvidenceResolutionStatus.CONFLICT, OPENING_DEDUCTION_LINEAGE_MISMATCH),
            )

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "opening_identity_id": selector.opening_identity_id,
            "host_binding_record_id": host_record.record_id,
            "physical_void_record_id": void_record.record_id,
            "opening_universe_record_id": universe_record.record_id,
            "target_scope_id": selector.target_scope_id,
            "applicability_record_id": applicability_record.record_id,
        }
        record = OpeningDeductionRecord(
            record_id=stable_contract_id("opening_deduction", payload, digest_chars=32),
            **payload,
        )
        return self._store(
            selector,
            OpeningDeductionResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(OPENING_DEDUCTION_AUTHORIZED,),
                record=record,
            ),
        )

    def authority(self) -> OpeningDeductionAuthority:
        return OpeningDeductionAuthority(self._results, _seal=_AUTHORITY_SEAL)


__all__ = [
    "OPENING_DEDUCTION_SCHEMA_VERSION",
    "OPENING_DEDUCTION_AUTHORIZED",
    "OPENING_DEDUCTION_OPENING_UNRESOLVED",
    "OPENING_DEDUCTION_HOST_UNRESOLVED",
    "OPENING_DEDUCTION_VOID_UNRESOLVED",
    "OPENING_DEDUCTION_UNIVERSE_INCOMPLETE",
    "OPENING_DEDUCTION_WALL_SCOPE_MISMATCH",
    "OPENING_DEDUCTION_APPLICABILITY_UNRESOLVED",
    "OPENING_DEDUCTION_LINEAGE_MISMATCH",
    "OPENING_DEDUCTION_RECORD_UNAVAILABLE",
    "OpeningDeductionSelector",
    "OpeningDeductionRecord",
    "OpeningDeductionResult",
    "OpeningDeductionAuthority",
    "OpeningDeductionProducer",
]
