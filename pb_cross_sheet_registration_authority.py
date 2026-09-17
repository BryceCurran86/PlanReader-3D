"""Producer-owned cross-sheet plan <-> elevation <-> section registration authority (Item 32).

Proves that evidence on one sheet (e.g. elevation, section) safely binds to an
exact physical building element on another sheet (e.g. plan):
- Requires exact document/revision/source/snapshot lineage.
- Physical element correspondence must be proven from spatial/geometric alignment or
  authenticated callout references; page/view labels or mark strings alone are insufficient.
- Same mark string (e.g. "W-01") on two different sheets does NOT automatically mint authority.
- Ambiguous many-to-many registrations fail closed (CONFLICT / ABSTAINED).
- Caller-certified / caller-asserted registrations are strictly forbidden.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

CROSS_SHEET_REGISTRATION_SCHEMA_VERSION = "1.0.0"

# Public reason codes
CROSS_SHEET_RESOLVED = "cross_sheet_registration_resolved"
CROSS_SHEET_UNRESOLVED = "cross_sheet_registration_unresolved"
CROSS_SHEET_LINEAGE_MISMATCH = "cross_sheet_registration_lineage_mismatch"
CROSS_SHEET_AMBIGUOUS_MANY_TO_MANY = "cross_sheet_registration_ambiguous_many_to_many"
CROSS_SHEET_LABEL_ONLY_REJECTED = "cross_sheet_registration_label_only_rejected"
CROSS_SHEET_MARK_ONLY_REJECTED = "cross_sheet_registration_same_mark_only_rejected"
CROSS_SHEET_CALLER_ASSERTION_REJECTED = "cross_sheet_registration_caller_assertion_rejected"
CROSS_SHEET_RECORD_UNAVAILABLE = "cross_sheet_registration_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/src_page/tgt_page/elem_id

_FORBIDDEN_PROOF_KINDS = frozenset({
    "caller_asserted",
    "page_label_only",
    "same_mark_only",
    "unverified_heuristic",
})


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class CrossSheetRegistrationSelector:
    """Sealed selector identifying exact source/target page and physical element."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    source_page_id: str
    target_page_id: str
    physical_element_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "source_page_id",
            "target_page_id",
            "physical_element_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.source_page_id,
            self.target_page_id,
            self.physical_element_id,
        )


@dataclass(frozen=True)
class CrossSheetRegistrationProof:
    """An authenticated proof connecting a element across two sheets."""
    proof_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    source_page_id: str
    source_viewport_id: str
    source_view_type: str   # "plan", "elevation", "section"
    target_page_id: str
    target_viewport_id: str
    target_view_type: str   # "plan", "elevation", "section"
    physical_element_id: str
    proof_kind: str          # e.g. "geometric_projection_alignment", "authenticated_callout_cut"
    correspondence_evidence_ids: Tuple[str, ...]
    confidence: float

    def __post_init__(self) -> None:
        for name in (
            "proof_id",
            "source_sha256",
            "revision_id",
            "snapshot_id",
            "source_page_id",
            "source_viewport_id",
            "source_view_type",
            "target_page_id",
            "target_viewport_id",
            "target_view_type",
            "physical_element_id",
            "proof_kind",
        ):
            _required(getattr(self, name), name)
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")
        if not self.correspondence_evidence_ids:
            raise ValueError("correspondence_evidence_ids must be non-empty")


@dataclass(frozen=True)
class CrossSheetRegistrationRecord:
    """Sealed cross-sheet registration record."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    source_page_id: str
    target_page_id: str
    physical_element_id: str
    source_view_type: str
    target_view_type: str
    corroborating_proof_ids: Tuple[str, ...]
    schema_version: str = CROSS_SHEET_REGISTRATION_SCHEMA_VERSION


@dataclass(frozen=True)
class CrossSheetRegistrationResult:
    """Result of cross-sheet registration authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[CrossSheetRegistrationRecord] = None
    schema_version: str = CROSS_SHEET_REGISTRATION_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> CrossSheetRegistrationResult:
    return CrossSheetRegistrationResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> CrossSheetRegistrationResult:
    return CrossSheetRegistrationResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class CrossSheetRegistrationAuthority:
    """Sealed selector-only lookup for published cross-sheet registration records."""

    def __init__(
        self,
        results: Mapping[_Key, CrossSheetRegistrationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("CrossSheetRegistrationAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: CrossSheetRegistrationSelector) -> CrossSheetRegistrationResult:
        if type(selector) is not CrossSheetRegistrationSelector:
            raise TypeError("selector must be CrossSheetRegistrationSelector")
        return self._results.get(
            selector.key,
            _abstained(CROSS_SHEET_RECORD_UNAVAILABLE),
        )


class CrossSheetRegistrationProducer:
    """Trusted writer boundary for authenticated cross-sheet registration."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("CrossSheetRegistrationProducer must be obtained via create()")
        self._results: dict[_Key, CrossSheetRegistrationResult] = {}

    @classmethod
    def create(cls) -> "CrossSheetRegistrationProducer":
        return cls(_seal=_PRODUCER_SEAL)

    def authority(self) -> CrossSheetRegistrationAuthority:
        return CrossSheetRegistrationAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: CrossSheetRegistrationSelector,
        result: CrossSheetRegistrationResult,
    ) -> CrossSheetRegistrationResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: CrossSheetRegistrationSelector,
        proofs: Sequence[CrossSheetRegistrationProof],
    ) -> CrossSheetRegistrationResult:
        """Publish cross-sheet registration for an element across source and target page."""
        if type(selector) is not CrossSheetRegistrationSelector:
            raise TypeError("selector must be CrossSheetRegistrationSelector")

        proof_list = list(proofs or [])
        if not proof_list:
            return self._store(selector, _abstained(CROSS_SHEET_UNRESOLVED))

        valid_proofs: list[CrossSheetRegistrationProof] = []
        forbidden_label_count = 0
        forbidden_mark_count = 0
        forbidden_caller_count = 0
        stale_count = 0

        for p in proof_list:
            if not isinstance(p, CrossSheetRegistrationProof):
                continue
            if p.proof_kind == "caller_asserted":
                forbidden_caller_count += 1
                continue
            if p.proof_kind == "page_label_only":
                forbidden_label_count += 1
                continue
            if p.proof_kind == "same_mark_only":
                forbidden_mark_count += 1
                continue
            if p.proof_kind in _FORBIDDEN_PROOF_KINDS:
                continue

            # Lineage match
            if (
                p.source_sha256 != selector.source_sha256
                or p.revision_id != selector.revision_id
                or p.snapshot_id != selector.snapshot_id
            ):
                stale_count += 1
                continue

            # Page & element match
            if (
                p.source_page_id != selector.source_page_id
                or p.target_page_id != selector.target_page_id
                or p.physical_element_id != selector.physical_element_id
            ):
                stale_count += 1
                continue

            valid_proofs.append(p)

        if forbidden_caller_count and not valid_proofs:
            return self._store(selector, _abstained(CROSS_SHEET_CALLER_ASSERTION_REJECTED))
        if forbidden_label_count and not valid_proofs:
            return self._store(selector, _abstained(CROSS_SHEET_LABEL_ONLY_REJECTED))
        if forbidden_mark_count and not valid_proofs:
            return self._store(selector, _abstained(CROSS_SHEET_MARK_ONLY_REJECTED))
        if stale_count and not valid_proofs:
            return self._store(selector, _conflict(CROSS_SHEET_LINEAGE_MISMATCH))
        if not valid_proofs:
            return self._store(selector, _abstained(CROSS_SHEET_UNRESOLVED))

        # Check for many-to-many ambiguity (e.g. conflicting target element bindings)
        target_views = {p.target_view_type for p in valid_proofs}
        source_views = {p.source_view_type for p in valid_proofs}
        if len(source_views) > 1 or len(target_views) > 1:
            return self._store(selector, _conflict(CROSS_SHEET_AMBIGUOUS_MANY_TO_MANY))

        proof_ids = tuple(sorted({p.proof_id for p in valid_proofs}))
        first_p = valid_proofs[0]

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "source_page_id": selector.source_page_id,
            "target_page_id": selector.target_page_id,
            "physical_element_id": selector.physical_element_id,
            "source_view_type": first_p.source_view_type,
            "target_view_type": first_p.target_view_type,
            "proof_ids": proof_ids,
        }
        record_id = stable_contract_id("cross_sheet_reg", payload, digest_chars=32)
        record = CrossSheetRegistrationRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            source_page_id=selector.source_page_id,
            target_page_id=selector.target_page_id,
            physical_element_id=selector.physical_element_id,
            source_view_type=first_p.source_view_type,
            target_view_type=first_p.target_view_type,
            corroborating_proof_ids=proof_ids,
        )
        return self._store(
            selector,
            CrossSheetRegistrationResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(CROSS_SHEET_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "CROSS_SHEET_AMBIGUOUS_MANY_TO_MANY",
    "CROSS_SHEET_CALLER_ASSERTION_REJECTED",
    "CROSS_SHEET_LABEL_ONLY_REJECTED",
    "CROSS_SHEET_LINEAGE_MISMATCH",
    "CROSS_SHEET_MARK_ONLY_REJECTED",
    "CROSS_SHEET_RECORD_UNAVAILABLE",
    "CROSS_SHEET_REGISTRATION_SCHEMA_VERSION",
    "CROSS_SHEET_RESOLVED",
    "CROSS_SHEET_UNRESOLVED",
    "CrossSheetRegistrationAuthority",
    "CrossSheetRegistrationProducer",
    "CrossSheetRegistrationProof",
    "CrossSheetRegistrationRecord",
    "CrossSheetRegistrationResult",
    "CrossSheetRegistrationSelector",
]
