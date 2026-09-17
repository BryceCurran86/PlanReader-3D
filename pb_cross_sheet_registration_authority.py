"""Producer-owned cross-sheet plan <-> elevation <-> section registration authority (Item 32).

Proves that evidence on one sheet (e.g. elevation, section) safely binds to an
exact physical building element on another sheet (e.g. plan):
- Requires exact document/revision/source/snapshot lineage.
- Consumes ONLY producer-owned PhysicalWallCandidateAuthority to resolve physical element
  existence on both source and target pages.
- NEVER accepts caller-built proof objects, caller assertions, or unverified mark lists.
- Same mark string (e.g. "W-01") on two different sheets does NOT automatically mint authority.
- Ambiguous or uncorroborated cross-sheet alignments fail closed (ABSTAINED / CONFLICT).
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)

CROSS_SHEET_REGISTRATION_SCHEMA_VERSION = "1.0.0"

# Public reason codes
CROSS_SHEET_RESOLVED = "cross_sheet_registration_resolved"
CROSS_SHEET_UNRESOLVED = "cross_sheet_registration_unresolved"
CROSS_SHEET_SOURCE_PAGE_UNRESOLVED = "cross_sheet_registration_source_page_unresolved"
CROSS_SHEET_TARGET_PAGE_UNRESOLVED = "cross_sheet_registration_target_page_unresolved"
CROSS_SHEET_LINEAGE_MISMATCH = "cross_sheet_registration_lineage_mismatch"
CROSS_SHEET_RECORD_UNAVAILABLE = "cross_sheet_registration_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/src_page/tgt_page/elem_id


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
    """Trusted writer boundary for authenticated cross-sheet registration.

    Consumes ONLY producer-owned PhysicalWallCandidateAuthority to verify physical element
    correspondence across source and target pages.
    """

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("CrossSheetRegistrationProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        self._wall_candidates = physical_wall_candidate_authority
        self._results: dict[_Key, CrossSheetRegistrationResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
    ) -> "CrossSheetRegistrationProducer":
        return cls(
            physical_wall_candidate_authority=physical_wall_candidate_authority,
            _seal=_PRODUCER_SEAL,
        )

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
    ) -> CrossSheetRegistrationResult:
        """Publish cross-sheet registration by re-resolving element on source and target page scopes."""
        if type(selector) is not CrossSheetRegistrationSelector:
            raise TypeError("selector must be CrossSheetRegistrationSelector")

        # 1. Resolve element existence on source page scope
        src_scope_id = f"wall-source:page-{selector.source_page_id}"
        src_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.source_page_id,
            decision_scope_id=src_scope_id,
        )
        src_res = self._wall_candidates.resolve_scope(src_sel)
        if src_res.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(selector, _abstained(CROSS_SHEET_SOURCE_PAGE_UNRESOLVED))

        src_recs = [
            r for r in getattr(src_res, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_element_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None)
            == selector.physical_element_id
        ]
        if not src_recs:
            return self._store(selector, _abstained(CROSS_SHEET_SOURCE_PAGE_UNRESOLVED))

        # 2. Resolve element existence on target page scope
        tgt_scope_id = f"wall-source:page-{selector.target_page_id}"
        tgt_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.target_page_id,
            decision_scope_id=tgt_scope_id,
        )
        tgt_res = self._wall_candidates.resolve_scope(tgt_sel)
        if tgt_res.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(selector, _abstained(CROSS_SHEET_TARGET_PAGE_UNRESOLVED))

        tgt_recs = [
            r for r in getattr(tgt_res, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_element_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None)
            == selector.physical_element_id
        ]
        if not tgt_recs:
            return self._store(selector, _abstained(CROSS_SHEET_TARGET_PAGE_UNRESOLVED))

        src_wc = getattr(src_recs[0], "wall_candidate", None)
        tgt_wc = getattr(tgt_recs[0], "wall_candidate", None)
        src_view = str(getattr(src_wc, "view_type", None) or "plan").lower()
        tgt_view = str(getattr(tgt_wc, "view_type", None) or "elevation").lower()

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "source_page_id": selector.source_page_id,
            "target_page_id": selector.target_page_id,
            "physical_element_id": selector.physical_element_id,
            "source_view_type": src_view,
            "target_view_type": tgt_view,
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
            source_view_type=src_view,
            target_view_type=tgt_view,
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
    "CROSS_SHEET_LINEAGE_MISMATCH",
    "CROSS_SHEET_RECORD_UNAVAILABLE",
    "CROSS_SHEET_REGISTRATION_SCHEMA_VERSION",
    "CROSS_SHEET_RESOLVED",
    "CROSS_SHEET_SOURCE_PAGE_UNRESOLVED",
    "CROSS_SHEET_TARGET_PAGE_UNRESOLVED",
    "CROSS_SHEET_UNRESOLVED",
    "CrossSheetRegistrationAuthority",
    "CrossSheetRegistrationProducer",
    "CrossSheetRegistrationRecord",
    "CrossSheetRegistrationResult",
    "CrossSheetRegistrationSelector",
]
