"""Producer-owned opening-universe completeness authority.

This module proves only a conservative full-page enumeration proposition.  It
keeps source decode coverage, semantic enumeration completeness and exact
consumer decision-scope completeness separate.  A caller cannot pass a
``claimed_complete`` flag, candidate count, radius, hash, or universe body to
the read-only authority: ordinary consumers query only by immutable lineage and
decision-scope selectors.

The first production slice deliberately supports full-page, unclipped,
known-visible vector universes only.  Viewport-local, clipped, optional-content
ambiguous, truncated-XObject, partially decoded, or source/enumeration-mismatch
cases fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Iterable, Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import SourceDecodeCoverageRecord


OPENING_UNIVERSE_COMPLETE = "opening_universe_complete"
OPENING_UNIVERSE_UNAVAILABLE = "opening_universe_unavailable"
SOURCE_DECODE_INCOMPLETE = "source_decode_incomplete"
SOURCE_COVERAGE_LINEAGE_MISMATCH = "source_coverage_lineage_mismatch"
SOURCE_PRIMITIVE_INVALID = "source_primitive_invalid"
ENUMERATED_PRIMITIVE_INVALID = "enumerated_primitive_invalid"
ENUMERATION_SOURCE_MISMATCH = "enumeration_source_mismatch"
CLIP_STATE_UNRESOLVED = "clip_state_unresolved"
ACTIVE_CLIP_UNSUPPORTED = "active_clip_unsupported"
OPTIONAL_CONTENT_UNRESOLVED = "optional_content_unresolved"
XOBJECT_TRAVERSAL_TRUNCATED = "xobject_traversal_truncated"
VIEWPORT_SCOPE_UNSUPPORTED = "viewport_scope_unsupported"
PAGE_SCOPE_MISMATCH = "page_scope_mismatch"
SELECTOR_RECORD_UNAVAILABLE = "selector_record_unavailable"
PRODUCER_RECORD_CONFLICT = "producer_record_conflict"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GEOM_TOL = 1e-7
_KEY_DIGITS = 8
_COMPLETENESS_AUTHORITY_SEAL = object()


@dataclass(frozen=True)
class OpeningUniverseSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "snapshot_id", "decision_scope_id"):
            if not str(getattr(self, name) or "").strip():
                raise ValueError(f"{name} must be a non-empty string")
        source_sha = str(self.source_sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(source_sha):
            raise ValueError("source_sha256 must be a lowercase 64-character SHA-256")
        object.__setattr__(self, "source_sha256", source_sha)


@dataclass(frozen=True)
class OpeningUniverseCompletenessRecord:
    record_id: str
    decision_scope_id: str
    decision_scope_kind: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_ids: tuple[str, ...]
    viewport_id: Optional[str]
    enumeration_state: str
    accounted_member_ids: tuple[str, ...]
    universe_fingerprint: str
    producer_method: str
    producer_version: str


@dataclass(frozen=True)
class OpeningUniverseCompletenessResult:
    status: EvidenceResolutionStatus
    source_decode_complete: Optional[bool]
    semantic_enumeration_complete: Optional[bool]
    decision_scope_complete: Optional[bool]
    reason_codes: tuple[str, ...]
    record: Optional[OpeningUniverseCompletenessRecord] = None


@dataclass(frozen=True)
class _Primitive:
    primitive_id: str
    page_id: str
    geometry: tuple[float, float, float, float]
    layer: str
    clip_known: bool
    clip_present: bool
    clip: Optional[tuple[float, float, float, float]]


def _dedupe(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(value for value in values if value))


def _finite_geometry(value: object) -> tuple[float, float, float, float] | None:
    try:
        if len(value) != 4:  # type: ignore[arg-type]
            return None
        x0, y0, x1, y1 = (float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    result = (x0, y0, x1, y1)
    if not all(math.isfinite(item) for item in result):
        return None
    if math.hypot(x1 - x0, y1 - y0) <= _GEOM_TOL:
        return None
    return result


def _optional_clip(value: object) -> tuple[float, float, float, float] | None:
    if value is None:
        return None
    try:
        if len(value) != 4:  # type: ignore[arg-type]
            return None
        items = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in items):
        return None
    return items  # type: ignore[return-value]


def _adapt_primitive(value: object) -> _Primitive | None:
    try:
        primitive_id = str(getattr(value, "primitive_id") or "").strip()
        page_id = str(getattr(value, "page_id") or "").strip()
        geometry = _finite_geometry(getattr(value, "geometry"))
        layer = str(getattr(value, "layer", "") or "")
        clip_known = getattr(value, "clip_known") is True
        clip_present = getattr(value, "clip_present") is True
        raw_clip = getattr(value, "clip", None)
    except (AttributeError, TypeError):
        return None
    if not primitive_id or not page_id or geometry is None:
        return None
    clip = _optional_clip(raw_clip)
    if raw_clip is not None and clip is None:
        return None
    return _Primitive(
        primitive_id=primitive_id,
        page_id=page_id,
        geometry=geometry,
        layer=layer,
        clip_known=clip_known,
        clip_present=clip_present,
        clip=clip,
    )


def _adapt_many(values: Sequence[object]) -> tuple[_Primitive, ...] | None:
    records: list[_Primitive] = []
    for value in values:
        record = _adapt_primitive(value)
        if record is None:
            return None
        records.append(record)
    return tuple(records)


def _line_key_and_interval(
    geometry: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float], tuple[float, float]]:
    x0, y0, x1, y1 = geometry
    dx, dy = x1 - x0, y1 - y0
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    if ux < -_GEOM_TOL or (abs(ux) <= _GEOM_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    nx, ny = -uy, ux
    offset = nx * x0 + ny * y0
    first = ux * x0 + uy * y0
    second = ux * x1 + uy * y1
    low, high = sorted((first, second))
    key = (round(ux, _KEY_DIGITS), round(uy, _KEY_DIGITS), round(offset, _KEY_DIGITS))
    return key, (low, high)


def _canonical_universe(
    records: Sequence[_Primitive],
) -> tuple[tuple[object, ...], ...]:
    """Canonicalize line segmentation without erasing disjoint source members."""
    groups: dict[tuple[str, str, float, float, float], list[tuple[float, float]]] = {}
    for record in records:
        key, interval = _line_key_and_interval(record.geometry)
        group_key = (record.page_id, record.layer, *key)
        groups.setdefault(group_key, []).append(interval)

    canonical: list[tuple[object, ...]] = []
    for group_key, intervals in sorted(groups.items()):
        ordered = sorted(intervals)
        merged: list[list[float]] = []
        for low, high in ordered:
            if not merged or low > merged[-1][1] + _GEOM_TOL:
                merged.append([low, high])
            else:
                merged[-1][1] = max(merged[-1][1], high)
        for low, high in merged:
            canonical.append((*group_key, round(low, _KEY_DIGITS), round(high, _KEY_DIGITS)))
    return tuple(canonical)


def _universe_fingerprint(records: Sequence[_Primitive]) -> str:
    canonical = _canonical_universe(records)
    return stable_contract_id("opening_universe", canonical, digest_chars=64)


def _safe_clip_state(records: Sequence[_Primitive]) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    for record in records:
        if not record.clip_known:
            reasons.append(CLIP_STATE_UNRESOLVED)
        elif record.clip_present or record.clip is not None:
            reasons.append(ACTIVE_CLIP_UNSUPPORTED)
    return (not reasons, _dedupe(reasons))


def _coverage_complete(
    coverage: SourceDecodeCoverageRecord,
    *,
    document_id: str,
    revision_id: str,
    page_count: int,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if coverage.document_id != document_id or coverage.revision_id != revision_id:
        reasons.append(SOURCE_COVERAGE_LINEAGE_MISMATCH)
    if (
        coverage.state != "complete"
        or tuple(coverage.failed_pages)
        or int(coverage.total_pages) != page_count
        or len(tuple(coverage.decoded_pages)) != page_count
    ):
        reasons.append(SOURCE_DECODE_INCOMPLETE)
    return (not reasons, _dedupe(reasons))


class OpeningUniverseCompletenessProducer:
    """Trusted structural writer for enumeration-completeness records."""

    def __init__(self, *, producer_method: str, producer_version: str) -> None:
        self._producer_method = str(producer_method or "").strip()
        self._producer_version = str(producer_version or "").strip()
        if not self._producer_method or not self._producer_version:
            raise ValueError("producer_method and producer_version are required")
        self._results: dict[
            tuple[str, str, str, str, str], OpeningUniverseCompletenessResult
        ] = {}

    def authority(self) -> "OpeningUniverseCompletenessAuthority":
        return OpeningUniverseCompletenessAuthority(
            self._results,
            _seal=_COMPLETENESS_AUTHORITY_SEAL,
        )

    def publish_enumeration(
        self,
        *,
        decision_scope_id: str,
        decision_scope_kind: str,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_ids: Sequence[str],
        viewport_id: Optional[str],
        coverage: SourceDecodeCoverageRecord,
        source_primitives: Sequence[object],
        enumerated_primitives: Sequence[object],
        optional_content_state: str,
        xobject_traversal_truncated: bool,
    ) -> OpeningUniverseCompletenessResult:
        decision_scope_id = str(decision_scope_id or "").strip()
        decision_scope_kind = str(decision_scope_kind or "").strip()
        document_id = str(document_id or "").strip()
        revision_id = str(revision_id or "").strip()
        source_sha256 = str(source_sha256 or "").strip().lower()
        snapshot_id = str(snapshot_id or "").strip()
        pages = tuple(str(page or "").strip() for page in page_ids)
        if (
            not decision_scope_id
            or not decision_scope_kind
            or not document_id
            or not revision_id
            or not snapshot_id
            or not _SHA256_RE.fullmatch(source_sha256)
            or not pages
            or any(not page for page in pages)
            or len(set(pages)) != len(pages)
        ):
            raise ValueError("complete producer lineage and unique page_ids are required")

        key = (document_id, revision_id, source_sha256, snapshot_id, decision_scope_id)
        reasons: list[str] = []
        coverage_ok, coverage_reasons = _coverage_complete(
            coverage,
            document_id=document_id,
            revision_id=revision_id,
            page_count=len(pages),
        )
        reasons.extend(coverage_reasons)

        source = _adapt_many(source_primitives)
        enumerated = _adapt_many(enumerated_primitives)
        if source is None:
            reasons.append(SOURCE_PRIMITIVE_INVALID)
        if enumerated is None:
            reasons.append(ENUMERATED_PRIMITIVE_INVALID)

        semantic_ok = False
        fingerprint: Optional[str] = None
        accounted_ids: tuple[str, ...] = ()
        if source is not None and enumerated is not None:
            if any(item.page_id not in pages for item in (*source, *enumerated)):
                reasons.append(PAGE_SCOPE_MISMATCH)
            clip_ok, clip_reasons = _safe_clip_state((*source, *enumerated))
            reasons.extend(clip_reasons)
            if str(optional_content_state or "") != "known_visible":
                reasons.append(OPTIONAL_CONTENT_UNRESOLVED)
            if bool(xobject_traversal_truncated):
                reasons.append(XOBJECT_TRAVERSAL_TRUNCATED)
            # Phase 1 deliberately refuses local viewport proofs. A full-page
            # record may later be projected into local decisions by a separately
            # reviewed authority, but a local crop cannot mint completeness.
            if viewport_id is not None:
                reasons.append(VIEWPORT_SCOPE_UNSUPPORTED)

            source_fp = _universe_fingerprint(source)
            enumeration_fp = _universe_fingerprint(enumerated)
            fingerprint = enumeration_fp
            if source_fp != enumeration_fp:
                reasons.append(ENUMERATION_SOURCE_MISMATCH)
            semantic_ok = (
                clip_ok
                and source_fp == enumeration_fp
                and not any(
                    reason
                    in {
                        PAGE_SCOPE_MISMATCH,
                        OPTIONAL_CONTENT_UNRESOLVED,
                        XOBJECT_TRAVERSAL_TRUNCATED,
                        VIEWPORT_SCOPE_UNSUPPORTED,
                    }
                    for reason in reasons
                )
            )
            accounted_ids = tuple(sorted({item.primitive_id for item in enumerated}))

        decision_ok = coverage_ok and semantic_ok
        if decision_ok and fingerprint is not None:
            payload = {
                "decision_scope_id": decision_scope_id,
                "decision_scope_kind": decision_scope_kind,
                "document_id": document_id,
                "revision_id": revision_id,
                "source_sha256": source_sha256,
                "snapshot_id": snapshot_id,
                "page_ids": pages,
                "viewport_id": viewport_id,
                "enumeration_state": "complete",
                "accounted_member_ids": accounted_ids,
                "universe_fingerprint": fingerprint,
                "producer_method": self._producer_method,
                "producer_version": self._producer_version,
            }
            record = OpeningUniverseCompletenessRecord(
                record_id=stable_contract_id(
                    "opening_universe_completeness", payload, digest_chars=32
                ),
                decision_scope_id=decision_scope_id,
                decision_scope_kind=decision_scope_kind,
                document_id=document_id,
                revision_id=revision_id,
                source_sha256=source_sha256,
                snapshot_id=snapshot_id,
                page_ids=pages,
                viewport_id=viewport_id,
                enumeration_state="complete",
                accounted_member_ids=accounted_ids,
                universe_fingerprint=fingerprint,
                producer_method=self._producer_method,
                producer_version=self._producer_version,
            )
            result = OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                source_decode_complete=True,
                semantic_enumeration_complete=True,
                decision_scope_complete=True,
                reason_codes=(OPENING_UNIVERSE_COMPLETE,),
                record=record,
            )
        else:
            result = OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                source_decode_complete=coverage_ok,
                semantic_enumeration_complete=semantic_ok,
                decision_scope_complete=False,
                reason_codes=_dedupe(reasons) or (OPENING_UNIVERSE_UNAVAILABLE,),
                record=None,
            )

        prior = self._results.get(key)
        if prior is not None and prior != result:
            conflict = OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.CONFLICT,
                source_decode_complete=None,
                semantic_enumeration_complete=False,
                decision_scope_complete=False,
                reason_codes=(PRODUCER_RECORD_CONFLICT,),
                record=None,
            )
            self._results[key] = conflict
            return conflict
        self._results[key] = result
        return result


class OpeningUniverseCompletenessAuthority:
    """Read-only selector/query boundary over producer-owned results."""

    def __init__(
        self,
        results: Mapping[
            tuple[str, str, str, str, str], OpeningUniverseCompletenessResult
        ],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _COMPLETENESS_AUTHORITY_SEAL:
            raise TypeError(
                "OpeningUniverseCompletenessAuthority must be obtained from "
                "OpeningUniverseCompletenessProducer.authority()"
            )
        self._results = results

    def resolve(
        self, selector: OpeningUniverseSelector
    ) -> OpeningUniverseCompletenessResult:
        if not isinstance(selector, OpeningUniverseSelector):
            raise TypeError("selector must be OpeningUniverseSelector")
        key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.decision_scope_id,
        )
        result = self._results.get(key)
        if result is None:
            return OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                source_decode_complete=None,
                semantic_enumeration_complete=None,
                decision_scope_complete=None,
                reason_codes=(SELECTOR_RECORD_UNAVAILABLE,),
                record=None,
            )
        return result


__all__ = [
    "OpeningUniverseCompletenessAuthority",
    "OpeningUniverseCompletenessProducer",
    "OpeningUniverseCompletenessRecord",
    "OpeningUniverseCompletenessResult",
    "OpeningUniverseSelector",
    "OPENING_UNIVERSE_COMPLETE",
    "OPENING_UNIVERSE_UNAVAILABLE",
]
