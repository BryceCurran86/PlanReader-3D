"""Producer-owned cross-sheet plan <-> elevation <-> section registration authority (Item 32).

Proves that a physical building element on one sheet (e.g. plan) safely
corresponds to a DIFFERENT, independently-proven physical element on
another sheet (e.g. elevation, section):

- Requires exact document/revision/source/snapshot lineage.
- ``physical_element_id`` addresses the SOURCE element only. It is never
  used to select the target element -- a caller cannot launder identity by
  supplying the same id on both sides, because the target side never looks
  at it at all.
- The target element is instead discovered purely from real evidence: an
  explicit drafting cross-reference callout (``pb_cross_sheet_callout_evidence``)
  printed near the source element, naming the target sheet AND a mark; the
  target element is the one (and only one) producer-owned candidate on the
  target page with that SAME mark printed near ITS OWN geometry. Proving
  the callout points at the right SHEET is necessary but not sufficient --
  it must also identify which physical object on that sheet it refers to.
- Zero or more-than-one target candidate matching the mark fails closed
  (CORROBORATED requires an exact, unique target).
- Without a producer-owned ``SourceVisibilityProducer`` to derive that
  callout evidence from, this authority has no positive path at all and
  always abstains -- it never falls back to identity/mark matching.
- A view type absent from producer-owned wall-candidate data stays
  ``None`` (unknown); it is never defaulted to "plan" or "elevation".
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

import fitz

from pb_cross_sheet_callout_evidence import (
    find_callout_near_geometry,
    find_unique_page_sheet_code,
    mark_appears_near_geometry,
)
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)
from pb_source_visibility_authority import SourceVisibilityProducer

CROSS_SHEET_REGISTRATION_SCHEMA_VERSION = "3.0.0"

# Public reason codes
CROSS_SHEET_RESOLVED = "cross_sheet_registration_resolved"
CROSS_SHEET_UNRESOLVED = "cross_sheet_registration_unresolved"
CROSS_SHEET_SOURCE_PAGE_UNRESOLVED = "cross_sheet_registration_source_page_unresolved"
CROSS_SHEET_TARGET_PAGE_UNRESOLVED = "cross_sheet_registration_target_page_unresolved"
CROSS_SHEET_AMBIGUOUS_ELEMENT_MATCH = "cross_sheet_registration_ambiguous_element_match"
CROSS_SHEET_AMBIGUOUS_TARGET_MARK_MATCH = "cross_sheet_registration_ambiguous_target_mark_match"
CROSS_SHEET_CORRESPONDENCE_EVIDENCE_UNAVAILABLE = "cross_sheet_registration_correspondence_evidence_unavailable"
CROSS_SHEET_CORRESPONDENCE_UNRESOLVED = "cross_sheet_registration_correspondence_unresolved"
CROSS_SHEET_SOURCE_UNAVAILABLE = "cross_sheet_registration_source_unavailable"
CROSS_SHEET_PAGE_UNAVAILABLE = "cross_sheet_registration_page_unavailable"
CROSS_SHEET_RECORD_UNAVAILABLE = "cross_sheet_registration_record_unavailable"
CROSS_SHEET_SOURCE_INTEGRITY_FAILURE = "cross_sheet_registration_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/src_page/tgt_page/elem_id

_CALLOUT_PROXIMITY_PT = 120.0


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
    target_physical_element_id: str
    source_view_type: Optional[str]
    target_view_type: Optional[str]
    callout_mark: str
    referenced_sheet_code: str
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

    Element existence on both pages is resolved from producer-owned
    ``PhysicalWallCandidateAuthority``. That alone can never mint a
    registration. A positive result additionally requires a real,
    source-backed callout cross-reference re-derived from an optional
    producer-owned ``SourceVisibilityProducer``; without one, this producer
    has no positive path and always abstains.
    """

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        source_visibility_producer: Optional[SourceVisibilityProducer],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("CrossSheetRegistrationProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        if source_visibility_producer is not None and type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned SourceVisibilityProducer or None")
        self._wall_candidates = physical_wall_candidate_authority
        self._source = source_visibility_producer
        self._results: dict[_Key, CrossSheetRegistrationResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        source_visibility_producer: Optional[SourceVisibilityProducer] = None,
    ) -> "CrossSheetRegistrationProducer":
        return cls(
            physical_wall_candidate_authority,
            source_visibility_producer,
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

    def _matching_records(self, selector: CrossSheetRegistrationSelector, page_id: str, element_id: str):
        scope_id = f"wall-source:page-{page_id}"
        sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=page_id,
            decision_scope_id=scope_id,
        )
        res = self._wall_candidates.resolve_scope(sel)
        if res.status is not EvidenceResolutionStatus.CORROBORATED:
            return None, res
        matches = [
            r for r in getattr(res, "records", ())
            if getattr(r, "wall_candidate_id", None) == element_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None) == element_id
        ]
        return matches, res

    def _source_bytes(self, selector: CrossSheetRegistrationSelector) -> Optional[bytes]:
        if self._source is None:
            return None
        published = self._source.published_snapshot_for_revision(selector.revision_id)
        if published is None:
            return None
        if (
            published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or self._source._producer.current_revision_id(selector.document_id) != selector.revision_id
        ):
            return None
        source_bytes = self._source._producer._store.source_bytes_by_revision.get(selector.revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != selector.source_sha256:
            raise RuntimeError(CROSS_SHEET_SOURCE_INTEGRITY_FAILURE)
        return bytes(source_bytes)

    def publish(
        self,
        selector: CrossSheetRegistrationSelector,
    ) -> CrossSheetRegistrationResult:
        """Publish cross-sheet registration only when element existence AND a
        real source-backed callout cross-reference both corroborate."""
        if type(selector) is not CrossSheetRegistrationSelector:
            raise TypeError("selector must be CrossSheetRegistrationSelector")

        # 1. Source element existence -- physical_element_id addresses the
        # SOURCE side only. It is never consulted again for the target.
        src_matches, src_scope_res = self._matching_records(selector, selector.source_page_id, selector.physical_element_id)
        if src_matches is None:
            return self._store(
                selector,
                _abstained(
                    CROSS_SHEET_SOURCE_PAGE_UNRESOLVED,
                    *(getattr(src_scope_res, "reason_codes", ()) or ()),
                ),
            )
        if not src_matches:
            return self._store(selector, _abstained(CROSS_SHEET_SOURCE_PAGE_UNRESOLVED))
        if len(src_matches) > 1:
            return self._store(selector, _conflict(CROSS_SHEET_AMBIGUOUS_ELEMENT_MATCH))
        src_wc = getattr(src_matches[0], "wall_candidate", None)
        src_view = getattr(src_wc, "view_type", None)

        pts = getattr(src_wc, "centerline_pts", None)
        if not pts:
            return self._store(selector, _abstained(CROSS_SHEET_CORRESPONDENCE_UNRESOLVED))
        xs = [float(p[0]) for p in pts]
        ys = [float(p[1]) for p in pts]
        src_geometry_bbox = (min(xs), min(ys), max(xs), max(ys))

        # 2. Target page's full producer-owned candidate universe (NOT
        # filtered by physical_element_id -- the target is discovered by
        # mark evidence below, never by id equality).
        tgt_scope_id = f"wall-source:page-{selector.target_page_id}"
        tgt_scope_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.target_page_id,
            decision_scope_id=tgt_scope_id,
        )
        tgt_scope_res = self._wall_candidates.resolve_scope(tgt_scope_sel)
        if tgt_scope_res.status is not EvidenceResolutionStatus.CORROBORATED or not getattr(tgt_scope_res, "records", ()):
            return self._store(
                selector,
                _abstained(
                    CROSS_SHEET_TARGET_PAGE_UNRESOLVED,
                    *(getattr(tgt_scope_res, "reason_codes", ()) or ()),
                ),
            )

        # 3. A real source-backed correspondence callout is required
        # before target-mark matching is even attempted.
        source_bytes = self._source_bytes(selector)
        if source_bytes is None:
            return self._store(selector, _abstained(CROSS_SHEET_CORRESPONDENCE_EVIDENCE_UNAVAILABLE))

        try:
            src_page_num = int(str(selector.source_page_id))
            tgt_page_num = int(str(selector.target_page_id))
        except ValueError:
            return self._store(selector, _abstained(CROSS_SHEET_PAGE_UNAVAILABLE))

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            if src_page_num < 1 or src_page_num > pdf.page_count or tgt_page_num < 1 or tgt_page_num > pdf.page_count:
                return self._store(selector, _abstained(CROSS_SHEET_PAGE_UNAVAILABLE))
            source_page = pdf.load_page(src_page_num - 1)
            target_page = pdf.load_page(tgt_page_num - 1)

            target_sheet_code = find_unique_page_sheet_code(target_page)
            if target_sheet_code is None:
                return self._store(selector, _abstained(CROSS_SHEET_CORRESPONDENCE_UNRESOLVED))

            callout = find_callout_near_geometry(
                source_page,
                page_num=src_page_num,
                geometry_bbox=src_geometry_bbox,
                proximity_pt=_CALLOUT_PROXIMITY_PT,
            )
            if callout is None or callout.referenced_sheet_code != target_sheet_code:
                return self._store(selector, _abstained(CROSS_SHEET_CORRESPONDENCE_UNRESOLVED))

            # 4. The callout naming the right SHEET is necessary but not
            # sufficient -- find the exact target candidate whose OWN
            # geometry carries the SAME mark. This is the real
            # target-element correspondence proof; physical_element_id is
            # never consulted here.
            mark_matched_records = []
            for record in tgt_scope_res.records:
                tgt_wc_candidate = getattr(record, "wall_candidate", None)
                tgt_pts = getattr(tgt_wc_candidate, "centerline_pts", None)
                if not tgt_pts:
                    continue
                txs = [float(p[0]) for p in tgt_pts]
                tys = [float(p[1]) for p in tgt_pts]
                tgt_geometry_bbox = (min(txs), min(tys), max(txs), max(tys))
                if mark_appears_near_geometry(
                    target_page,
                    mark=callout.mark,
                    geometry_bbox=tgt_geometry_bbox,
                    proximity_pt=_CALLOUT_PROXIMITY_PT,
                ):
                    mark_matched_records.append(record)

            if not mark_matched_records:
                return self._store(selector, _abstained(CROSS_SHEET_CORRESPONDENCE_UNRESOLVED))
            if len(mark_matched_records) > 1:
                return self._store(selector, _conflict(CROSS_SHEET_AMBIGUOUS_TARGET_MARK_MATCH))

            tgt_record = mark_matched_records[0]
            tgt_wc = getattr(tgt_record, "wall_candidate", None)
            tgt_view = getattr(tgt_wc, "view_type", None)
            target_physical_element_id = (
                getattr(tgt_record, "wall_candidate_id", None)
                or getattr(getattr(tgt_record, "physical_identity", None), "physical_wall_id", None)
                or ""
            )
        finally:
            pdf.close()

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "source_page_id": selector.source_page_id,
            "target_page_id": selector.target_page_id,
            "physical_element_id": selector.physical_element_id,
            "target_physical_element_id": target_physical_element_id,
            "source_view_type": src_view,
            "target_view_type": tgt_view,
            "callout_mark": callout.mark,
            "referenced_sheet_code": callout.referenced_sheet_code,
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
            target_physical_element_id=target_physical_element_id,
            source_view_type=src_view,
            target_view_type=tgt_view,
            callout_mark=callout.mark,
            referenced_sheet_code=callout.referenced_sheet_code,
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
    "CROSS_SHEET_AMBIGUOUS_ELEMENT_MATCH",
    "CROSS_SHEET_AMBIGUOUS_TARGET_MARK_MATCH",
    "CROSS_SHEET_CORRESPONDENCE_EVIDENCE_UNAVAILABLE",
    "CROSS_SHEET_CORRESPONDENCE_UNRESOLVED",
    "CROSS_SHEET_PAGE_UNAVAILABLE",
    "CROSS_SHEET_RECORD_UNAVAILABLE",
    "CROSS_SHEET_REGISTRATION_SCHEMA_VERSION",
    "CROSS_SHEET_RESOLVED",
    "CROSS_SHEET_SOURCE_INTEGRITY_FAILURE",
    "CROSS_SHEET_SOURCE_PAGE_UNRESOLVED",
    "CROSS_SHEET_SOURCE_UNAVAILABLE",
    "CROSS_SHEET_TARGET_PAGE_UNRESOLVED",
    "CROSS_SHEET_UNRESOLVED",
    "CrossSheetRegistrationAuthority",
    "CrossSheetRegistrationProducer",
    "CrossSheetRegistrationRecord",
    "CrossSheetRegistrationResult",
    "CrossSheetRegistrationSelector",
]
