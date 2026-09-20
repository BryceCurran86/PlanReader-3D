"""Producer-owned opening-universe completeness authority.

This module establishes a narrow in-process producer/query trust boundary for
opening/host decision-scope completeness.  It deliberately keeps three
propositions separate:

1. source decode coverage;
2. semantic enumeration completeness; and
3. decision-scope completeness.

It is not a cryptographic security proof.  Deterministic fingerprints bind
producer-owned lineage and normalized universe state after the producer has
established those facts.  Ordinary consumers provide only an
``OpeningUniverseSelector``; they cannot submit a completeness claim, candidate
list, count, radius, hash, or seal to ``resolve``.

This authority is upstream of host binding, opening dimensions, physical voids,
deductions, net-wall quantities, commercial publication, and JobHub.  Nothing
in this module unlocks those downstream capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import SourceDecodeCoverageRecord


OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION = "1.0.0"

SOURCE_DECODE_INCOMPLETE = "source_decode_coverage_incomplete"
SOURCE_DECODE_SCOPE_MISMATCH = "source_decode_scope_mismatch"
SEMANTIC_ENUMERATION_INCOMPLETE = "semantic_enumeration_incomplete"
SEMANTIC_MEMBER_INVALID = "semantic_member_invalid"
SEMANTIC_MEMBER_SCOPE_MISMATCH = "semantic_member_scope_mismatch"
SEMANTIC_MEMBER_DUPLICATE_CONFLICT = "semantic_member_duplicate_conflict"
SEMANTIC_DISPOSITION_INVALID = "semantic_opening_disposition_invalid"
SEMANTIC_SOURCE_MEMBER_UNDISPOSITIONED = "semantic_source_member_undispositioned"
SEMANTIC_SOURCE_MEMBER_UNRESOLVED = "semantic_source_member_unresolved"
SEMANTIC_SELECTOR_OUTSIDE_SOURCE = "semantic_opening_selector_outside_source"
SEMANTIC_DISPOSITION_DUPLICATE_CONFLICT = "semantic_disposition_duplicate_conflict"
CLIP_STATE_UNKNOWN = "opening_universe_clip_state_unknown"
ACTIVE_CLIP_UNRESOLVED = "opening_universe_active_clip_unresolved"
OPTIONAL_CONTENT_UNRESOLVED = "opening_universe_optional_content_unresolved"
XOBJECT_TRAVERSAL_TRUNCATED = "opening_universe_xobject_traversal_truncated"
VIEWPORT_LIMITED_SCOPE = "opening_universe_viewport_limited_scope"
COMPLETENESS_RECORD_UNAVAILABLE = "opening_universe_completeness_record_unavailable"
PRODUCER_EQUIVOCATION = "opening_universe_producer_equivocation"


class SourceEnumerationState(str, Enum):
    """Producer-owned state of the semantic universe enumeration."""

    COMPLETE = "complete"
    INCOMPLETE = "incomplete"


class SemanticSourceDispositionState(str, Enum):
    """Disposition of one authenticated source primitive for opening semantics."""

    OPENING_MEMBER = "opening_member"
    NON_OPENING = "non_opening"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class SemanticOpeningMemberDisposition:
    """Producer-side semantic disposition for one authenticated source primitive.

    Many source primitives may map to the same opening selector observation id.
    This permits a multi-segment source pattern to become one semantic opening
    while preserving complete source coverage.  The selector id must be one of
    the authenticated source primitive ids so PhysicalOpeningAuthority can replay it.
    """

    source_primitive_id: str
    state: str
    opening_selector_observation_id: Optional[str] = None

    def __post_init__(self) -> None:
        source_id = str(self.source_primitive_id or "").strip()
        if not source_id:
            raise ValueError("semantic disposition source_primitive_id is unbound")
        try:
            state = SemanticSourceDispositionState(str(self.state))
        except ValueError as exc:
            raise ValueError("semantic disposition state is invalid") from exc
        selector_id = str(self.opening_selector_observation_id or "").strip()
        if state is SemanticSourceDispositionState.OPENING_MEMBER and not selector_id:
            raise ValueError("opening-member disposition requires selector observation id")
        if state is not SemanticSourceDispositionState.OPENING_MEMBER and selector_id:
            raise ValueError("non-opening/unresolved disposition cannot carry opening selector id")


@dataclass(frozen=True)
class OpeningUniverseSelector:
    """Read-only lookup key supplied by ordinary consumers."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str


@dataclass(frozen=True)
class OpeningUniverseScope:
    """Producer-owned lineage and decision-scope identity."""

    decision_scope_id: str
    decision_scope_kind: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_ids: tuple[str, ...]
    viewport_id: Optional[str]
    schema_version: str = OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningUniverseMember:
    """Normalized producer-side primitive member before semantic coalescing."""

    member_id: str
    primitive_id: str
    page_id: str
    geometry: tuple[float, float, float, float]
    layer: str
    clip_known: bool
    clip_present: bool
    clip: Optional[tuple[float, float, float, float]]
    schema_version: str = OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningUniverseCompletenessRecord:
    """Immutable producer-owned result for one exact decision scope."""

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
    source_decode_complete: bool
    semantic_enumeration_complete: bool
    decision_scope_complete: bool
    accounted_member_ids: tuple[str, ...]
    universe_fingerprint: str
    reason_codes: tuple[str, ...]
    schema_version: str = OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningUniverseCompletenessResult:
    """Consumer-facing completeness resolution."""

    status: EvidenceResolutionStatus
    source_decode_complete: Optional[bool]
    semantic_enumeration_complete: Optional[bool]
    decision_scope_complete: Optional[bool]
    reason_codes: tuple[str, ...]
    record: Optional[OpeningUniverseCompletenessRecord] = None


_AUTHORITY_SEAL = object()
_EPSILON = 1e-8


def _clean(value: object) -> str:
    return str(value or "").strip()


def _ordered_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _finite_geometry(value: object) -> tuple[float, float, float, float]:
    try:
        coords = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("opening universe primitive geometry is invalid") from exc
    if len(coords) != 4 or not all(math.isfinite(item) for item in coords):
        raise ValueError("opening universe primitive geometry is invalid")
    x0, y0, x1, y1 = coords
    if math.hypot(x1 - x0, y1 - y0) <= _EPSILON:
        raise ValueError("opening universe primitive geometry is degenerate")
    return (x0, y0, x1, y1)


def _optional_clip(value: object) -> Optional[tuple[float, float, float, float]]:
    if value is None:
        return None
    try:
        coords = tuple(float(item) for item in value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as exc:
        raise ValueError("opening universe clip geometry is invalid") from exc
    if len(coords) != 4 or not all(math.isfinite(item) for item in coords):
        raise ValueError("opening universe clip geometry is invalid")
    return coords  # type: ignore[return-value]


def build_opening_universe_member_from_indexed_primitive(
    primitive: object,
) -> OpeningUniverseMember:
    """Adapt one producer-side indexed primitive into a deterministic member.

    The adapter intentionally accepts structural producer objects rather than a
    public claim type.  Required fields are read from producer-owned material.
    """

    primitive_id = _clean(getattr(primitive, "primitive_id", ""))
    page_id = _clean(getattr(primitive, "page_id", ""))
    if not primitive_id or not page_id:
        raise ValueError("opening universe primitive identity is unbound")
    geometry = _finite_geometry(getattr(primitive, "geometry", None))
    layer = _clean(getattr(primitive, "layer", ""))
    clip_known = getattr(primitive, "clip_known", None) is True
    clip_present = getattr(primitive, "clip_present", None) is True
    clip = _optional_clip(getattr(primitive, "clip", None))
    payload = {
        "schema_version": OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION,
        "primitive_id": primitive_id,
        "page_id": page_id,
        "geometry": geometry,
        "layer": layer,
        "clip_known": clip_known,
        "clip_present": clip_present,
        "clip": clip,
    }
    return OpeningUniverseMember(
        member_id=stable_contract_id("opening_universe_member", payload, digest_chars=32),
        primitive_id=primitive_id,
        page_id=page_id,
        geometry=geometry,
        layer=layer,
        clip_known=clip_known,
        clip_present=clip_present,
        clip=clip,
    )


def build_opening_universe_scope(
    *,
    decision_scope_id: str,
    decision_scope_kind: str,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_ids: Sequence[str],
    viewport_id: Optional[str],
) -> OpeningUniverseScope:
    values = {
        "decision_scope_id": _clean(decision_scope_id),
        "decision_scope_kind": _clean(decision_scope_kind),
        "document_id": _clean(document_id),
        "revision_id": _clean(revision_id),
        "source_sha256": _clean(source_sha256),
        "snapshot_id": _clean(snapshot_id),
    }
    if any(not value for value in values.values()):
        raise ValueError("opening universe scope identity is unbound")
    pages = tuple(sorted({_clean(page_id) for page_id in page_ids if _clean(page_id)}))
    if not pages:
        raise ValueError("opening universe scope requires at least one page")
    return OpeningUniverseScope(
        decision_scope_id=values["decision_scope_id"],
        decision_scope_kind=values["decision_scope_kind"],
        document_id=values["document_id"],
        revision_id=values["revision_id"],
        source_sha256=values["source_sha256"],
        snapshot_id=values["snapshot_id"],
        page_ids=pages,
        viewport_id=_clean(viewport_id) or None,
    )


def _member_key(member: OpeningUniverseMember) -> tuple[object, ...]:
    return (
        member.primitive_id,
        member.page_id,
        member.geometry,
        member.layer,
        member.clip_known,
        member.clip_present,
        member.clip,
    )


def _dedupe_members(
    primitives: Sequence[object],
) -> tuple[tuple[OpeningUniverseMember, ...], tuple[str, ...]]:
    by_primitive_id: dict[str, OpeningUniverseMember] = {}
    reasons: list[str] = []
    for primitive in primitives:
        try:
            member = build_opening_universe_member_from_indexed_primitive(primitive)
        except (TypeError, ValueError):
            reasons.append(SEMANTIC_MEMBER_INVALID)
            continue
        prior = by_primitive_id.get(member.primitive_id)
        if prior is None:
            by_primitive_id[member.primitive_id] = member
        elif _member_key(prior) != _member_key(member):
            reasons.append(SEMANTIC_MEMBER_DUPLICATE_CONFLICT)
    members = tuple(
        sorted(
            by_primitive_id.values(),
            key=lambda item: (item.page_id, item.layer, item.primitive_id, item.geometry),
        )
    )
    return members, _ordered_unique(reasons)


def _canonical_endpoints(
    geometry: tuple[float, float, float, float],
) -> tuple[tuple[float, float], tuple[float, float]]:
    a = (float(geometry[0]), float(geometry[1]))
    b = (float(geometry[2]), float(geometry[3]))
    return (a, b) if a <= b else (b, a)


def _cross(ax: float, ay: float, bx: float, by: float) -> float:
    return ax * by - ay * bx


def _merge_pair(
    first: tuple[tuple[float, float], tuple[float, float]],
    second: tuple[tuple[float, float], tuple[float, float]],
) -> Optional[tuple[tuple[float, float], tuple[float, float]]]:
    a0, a1 = first
    b0, b1 = second
    vx, vy = a1[0] - a0[0], a1[1] - a0[1]
    wx, wy = b1[0] - b0[0], b1[1] - b0[1]
    length = math.hypot(vx, vy)
    if length <= _EPSILON:
        return None
    scale = max(length, math.hypot(wx, wy), 1.0)
    if abs(_cross(vx, vy, wx, wy)) > _EPSILON * scale * scale:
        return None
    if abs(_cross(vx, vy, b0[0] - a0[0], b0[1] - a0[1])) > _EPSILON * scale * scale:
        return None

    ux, uy = vx / length, vy / length

    def project(point: tuple[float, float]) -> float:
        return (point[0] - a0[0]) * ux + (point[1] - a0[1]) * uy

    first_min, first_max = sorted((project(a0), project(a1)))
    second_min, second_max = sorted((project(b0), project(b1)))
    if second_min > first_max + _EPSILON or first_min > second_max + _EPSILON:
        return None
    lower = min(first_min, second_min)
    upper = max(first_max, second_max)
    start = (a0[0] + lower * ux, a0[1] + lower * uy)
    end = (a0[0] + upper * ux, a0[1] + upper * uy)
    return (start, end) if start <= end else (end, start)


def _normalised_semantic_segments(
    members: Sequence[OpeningUniverseMember],
) -> tuple[tuple[object, ...], ...]:
    """Return segmentation-invariant geometry for the semantic universe."""

    groups: dict[
        tuple[str, str, bool, bool, Optional[tuple[float, float, float, float]]],
        list[tuple[tuple[float, float], tuple[float, float]]],
    ] = {}
    for member in members:
        group_key = (
            member.page_id,
            member.layer,
            member.clip_known,
            member.clip_present,
            member.clip,
        )
        groups.setdefault(group_key, []).append(_canonical_endpoints(member.geometry))

    normalised: list[tuple[object, ...]] = []
    for group_key in sorted(groups, key=repr):
        segments = list(dict.fromkeys(groups[group_key]))
        changed = True
        while changed:
            changed = False
            for left_index in range(len(segments)):
                if changed:
                    break
                for right_index in range(left_index + 1, len(segments)):
                    merged = _merge_pair(segments[left_index], segments[right_index])
                    if merged is None:
                        continue
                    segments[left_index] = merged
                    del segments[right_index]
                    changed = True
                    break
        for start, end in sorted(segments):
            geometry = tuple(round(value, 9) for value in (*start, *end))
            normalised.append((*group_key, geometry))
    return tuple(sorted(normalised, key=repr))


def _universe_fingerprint(members: Sequence[OpeningUniverseMember]) -> str:
    payload = {
        "schema_version": OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION,
        "semantic_segments": _normalised_semantic_segments(members),
    }
    return stable_contract_id("opening_universe", payload, digest_chars=64)


def _coverage_complete(
    coverage: SourceDecodeCoverageRecord,
    scope: OpeningUniverseScope,
) -> tuple[bool, tuple[str, ...]]:
    reasons: list[str] = []
    if (
        _clean(getattr(coverage, "document_id", "")) != scope.document_id
        or _clean(getattr(coverage, "revision_id", "")) != scope.revision_id
    ):
        reasons.append(SOURCE_DECODE_SCOPE_MISMATCH)

    try:
        total_pages = int(getattr(coverage, "total_pages"))
        decoded_pages = tuple(int(value) for value in getattr(coverage, "decoded_pages"))
        failed_pages = tuple(int(value) for value in getattr(coverage, "failed_pages"))
    except (AttributeError, TypeError, ValueError):
        reasons.append(SOURCE_DECODE_INCOMPLETE)
        return False, _ordered_unique(reasons)

    if (
        _clean(getattr(coverage, "state", "")) != "complete"
        or total_pages != len(scope.page_ids)
        or total_pages <= 0
        or failed_pages
        or len(set(decoded_pages)) != total_pages
    ):
        reasons.append(SOURCE_DECODE_INCOMPLETE)
    return not reasons, _ordered_unique(reasons)


def _scope_member_reasons(
    scope: OpeningUniverseScope,
    source_members: Sequence[OpeningUniverseMember],
    enumerated_members: Sequence[OpeningUniverseMember],
) -> tuple[str, ...]:
    reasons: list[str] = []
    allowed_pages = set(scope.page_ids)
    for member in (*source_members, *enumerated_members):
        if member.page_id not in allowed_pages:
            reasons.append(SEMANTIC_MEMBER_SCOPE_MISMATCH)
        if not member.clip_known:
            reasons.append(CLIP_STATE_UNKNOWN)
        if member.clip_present or member.clip is not None:
            reasons.append(ACTIVE_CLIP_UNRESOLVED)
    return _ordered_unique(reasons)


def _record_key(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
) -> tuple[str, str, str, str, str]:
    return (
        _clean(document_id),
        _clean(revision_id),
        _clean(source_sha256),
        _clean(snapshot_id),
        _clean(decision_scope_id),
    )


class OpeningUniverseCompletenessProducer:
    """Trusted writer that owns source-vs-enumeration reconciliation."""

    def __init__(self, *, producer_method: str, producer_version: str) -> None:
        self._producer_method = _clean(producer_method)
        self._producer_version = _clean(producer_version)
        if not self._producer_method or not self._producer_version:
            raise ValueError("completeness producer identity is unbound")
        self._records: dict[
            tuple[str, str, str, str, str], OpeningUniverseCompletenessRecord
        ] = {}

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
        semantic_enumeration_proven: bool = True,
    ) -> OpeningUniverseCompletenessRecord:
        scope = build_opening_universe_scope(
            decision_scope_id=decision_scope_id,
            decision_scope_kind=decision_scope_kind,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_ids=page_ids,
            viewport_id=viewport_id,
        )
        source_members, source_reasons = _dedupe_members(tuple(source_primitives))
        enumerated_members, enumeration_reasons = _dedupe_members(
            tuple(enumerated_primitives)
        )

        reasons: list[str] = [*source_reasons, *enumeration_reasons]
        decode_complete, decode_reasons = _coverage_complete(coverage, scope)
        reasons.extend(decode_reasons)
        reasons.extend(_scope_member_reasons(scope, source_members, enumerated_members))

        source_fingerprint = _universe_fingerprint(source_members)
        enumerated_fingerprint = _universe_fingerprint(enumerated_members)
        semantic_complete = (
            bool(semantic_enumeration_proven)
            and not source_reasons
            and not enumeration_reasons
            and source_fingerprint == enumerated_fingerprint
        )
        if not semantic_complete:
            reasons.append(SEMANTIC_ENUMERATION_INCOMPLETE)

        if _clean(optional_content_state) != "known_visible":
            reasons.append(OPTIONAL_CONTENT_UNRESOLVED)
        if bool(xobject_traversal_truncated):
            reasons.append(XOBJECT_TRAVERSAL_TRUNCATED)

        # A local viewport is not a proof of the complete decision competitor
        # scope. A future producer may introduce a separately authenticated
        # viewport-scope contract; this first authority remains full-page/scope.
        if scope.viewport_id is not None:
            reasons.append(VIEWPORT_LIMITED_SCOPE)

        unique_reasons = _ordered_unique(reasons)
        semantic_complete = semantic_complete and not any(
            reason
            in {
                SEMANTIC_MEMBER_INVALID,
                SEMANTIC_MEMBER_SCOPE_MISMATCH,
                SEMANTIC_MEMBER_DUPLICATE_CONFLICT,
                CLIP_STATE_UNKNOWN,
                ACTIVE_CLIP_UNRESOLVED,
                OPTIONAL_CONTENT_UNRESOLVED,
                XOBJECT_TRAVERSAL_TRUNCATED,
                VIEWPORT_LIMITED_SCOPE,
            }
            for reason in unique_reasons
        )
        decision_complete = decode_complete and semantic_complete and not unique_reasons
        enumeration_state = (
            SourceEnumerationState.COMPLETE.value
            if decision_complete
            else SourceEnumerationState.INCOMPLETE.value
        )

        accounted_ids = tuple(
            sorted({member.member_id for member in enumerated_members})
        )
        record_payload = {
            "schema_version": OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION,
            "producer_method": self._producer_method,
            "producer_version": self._producer_version,
            "scope": scope,
            "enumeration_state": enumeration_state,
            "source_decode_complete": decode_complete,
            "semantic_enumeration_complete": semantic_complete,
            "decision_scope_complete": decision_complete,
            "accounted_member_ids": accounted_ids,
            "universe_fingerprint": source_fingerprint,
            "reason_codes": unique_reasons,
        }
        record = OpeningUniverseCompletenessRecord(
            record_id=stable_contract_id(
                "opening_universe_completeness", record_payload, digest_chars=32
            ),
            decision_scope_id=scope.decision_scope_id,
            decision_scope_kind=scope.decision_scope_kind,
            document_id=scope.document_id,
            revision_id=scope.revision_id,
            source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id,
            page_ids=scope.page_ids,
            viewport_id=scope.viewport_id,
            enumeration_state=enumeration_state,
            source_decode_complete=decode_complete,
            semantic_enumeration_complete=semantic_complete,
            decision_scope_complete=decision_complete,
            accounted_member_ids=accounted_ids,
            universe_fingerprint=source_fingerprint,
            reason_codes=unique_reasons,
        )
        key = _record_key(
            document_id=scope.document_id,
            revision_id=scope.revision_id,
            source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id,
            decision_scope_id=scope.decision_scope_id,
        )
        prior = self._records.get(key)
        if prior is not None and prior != record:
            raise RuntimeError(PRODUCER_EQUIVOCATION)
        self._records[key] = record
        return record

    def publish_semantic_enumeration(
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
        dispositions: Sequence[SemanticOpeningMemberDisposition],
        optional_content_state: str,
        xobject_traversal_truncated: bool,
    ) -> OpeningUniverseCompletenessRecord:
        """Publish semantic completeness from exhaustive source dispositions.

        This path permits many authenticated source primitives to coalesce onto
        one physical-opening selector observation id.  Every source primitive
        must be dispositioned as opening_member, non_opening, or unresolved.
        Missing, unresolved, conflicting, or out-of-scope dispositions fail closed.

        This generic producer does not by itself authenticate the semantic
        classifier.  A source-bound adapter must still earn any private commercial
        completeness seal after deriving these dispositions from producer-owned
        source evidence.
        """
        scope = build_opening_universe_scope(
            decision_scope_id=decision_scope_id,
            decision_scope_kind=decision_scope_kind,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_ids=page_ids,
            viewport_id=viewport_id,
        )
        source_members, source_reasons = _dedupe_members(tuple(source_primitives))
        reasons: list[str] = list(source_reasons)
        decode_complete, decode_reasons = _coverage_complete(coverage, scope)
        reasons.extend(decode_reasons)
        reasons.extend(_scope_member_reasons(scope, source_members, ()))

        source_ids = {member.primitive_id for member in source_members}
        by_source: dict[str, SemanticOpeningMemberDisposition] = {}
        for disposition in dispositions:
            if type(disposition) is not SemanticOpeningMemberDisposition:
                reasons.append(SEMANTIC_DISPOSITION_INVALID)
                continue
            source_id = _clean(disposition.source_primitive_id)
            if source_id not in source_ids:
                reasons.append(SEMANTIC_DISPOSITION_INVALID)
                continue
            prior = by_source.get(source_id)
            if prior is not None and prior != disposition:
                reasons.append(SEMANTIC_DISPOSITION_DUPLICATE_CONFLICT)
                continue
            by_source[source_id] = disposition

        if source_ids - set(by_source):
            reasons.append(SEMANTIC_SOURCE_MEMBER_UNDISPOSITIONED)

        opening_selector_ids: set[str] = set()
        for disposition in by_source.values():
            try:
                state = SemanticSourceDispositionState(str(disposition.state))
            except ValueError:
                reasons.append(SEMANTIC_DISPOSITION_INVALID)
                continue
            if state is SemanticSourceDispositionState.UNRESOLVED:
                reasons.append(SEMANTIC_SOURCE_MEMBER_UNRESOLVED)
            elif state is SemanticSourceDispositionState.OPENING_MEMBER:
                selector_id = _clean(disposition.opening_selector_observation_id)
                if selector_id not in source_ids:
                    reasons.append(SEMANTIC_SELECTOR_OUTSIDE_SOURCE)
                else:
                    opening_selector_ids.add(selector_id)

        if _clean(optional_content_state) != "known_visible":
            reasons.append(OPTIONAL_CONTENT_UNRESOLVED)
        if bool(xobject_traversal_truncated):
            reasons.append(XOBJECT_TRAVERSAL_TRUNCATED)
        if scope.viewport_id is not None:
            reasons.append(VIEWPORT_LIMITED_SCOPE)

        unique_reasons = _ordered_unique(reasons)
        blocking_semantic_reasons = {
            SEMANTIC_MEMBER_INVALID,
            SEMANTIC_MEMBER_SCOPE_MISMATCH,
            SEMANTIC_MEMBER_DUPLICATE_CONFLICT,
            SEMANTIC_DISPOSITION_INVALID,
            SEMANTIC_SOURCE_MEMBER_UNDISPOSITIONED,
            SEMANTIC_SOURCE_MEMBER_UNRESOLVED,
            SEMANTIC_SELECTOR_OUTSIDE_SOURCE,
            SEMANTIC_DISPOSITION_DUPLICATE_CONFLICT,
            CLIP_STATE_UNKNOWN,
            ACTIVE_CLIP_UNRESOLVED,
            OPTIONAL_CONTENT_UNRESOLVED,
            XOBJECT_TRAVERSAL_TRUNCATED,
            VIEWPORT_LIMITED_SCOPE,
        }
        semantic_complete = not any(
            reason in blocking_semantic_reasons for reason in unique_reasons
        )
        if not semantic_complete:
            unique_reasons = _ordered_unique(
                (*unique_reasons, SEMANTIC_ENUMERATION_INCOMPLETE)
            )

        decision_complete = decode_complete and semantic_complete and not unique_reasons
        enumeration_state = (
            SourceEnumerationState.COMPLETE.value
            if decision_complete
            else SourceEnumerationState.INCOMPLETE.value
        )
        accounted_ids = tuple(sorted(opening_selector_ids))
        disposition_payload = tuple(
            sorted(
                (
                    source_id,
                    disposition.state,
                    disposition.opening_selector_observation_id or "",
                )
                for source_id, disposition in by_source.items()
            )
        )
        universe_fingerprint = stable_contract_id(
            "semantic_opening_universe",
            {
                "schema_version": OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION,
                "source_fingerprint": _universe_fingerprint(source_members),
                "dispositions": disposition_payload,
                "opening_selector_ids": accounted_ids,
            },
            digest_chars=64,
        )
        record_payload = {
            "schema_version": OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION,
            "producer_method": self._producer_method,
            "producer_version": self._producer_version,
            "scope": scope,
            "enumeration_state": enumeration_state,
            "source_decode_complete": decode_complete,
            "semantic_enumeration_complete": semantic_complete,
            "decision_scope_complete": decision_complete,
            "accounted_member_ids": accounted_ids,
            "universe_fingerprint": universe_fingerprint,
            "reason_codes": unique_reasons,
        }
        record = OpeningUniverseCompletenessRecord(
            record_id=stable_contract_id(
                "opening_universe_completeness", record_payload, digest_chars=32
            ),
            decision_scope_id=scope.decision_scope_id,
            decision_scope_kind=scope.decision_scope_kind,
            document_id=scope.document_id,
            revision_id=scope.revision_id,
            source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id,
            page_ids=scope.page_ids,
            viewport_id=scope.viewport_id,
            enumeration_state=enumeration_state,
            source_decode_complete=decode_complete,
            semantic_enumeration_complete=semantic_complete,
            decision_scope_complete=decision_complete,
            accounted_member_ids=accounted_ids,
            universe_fingerprint=universe_fingerprint,
            reason_codes=unique_reasons,
        )
        key = _record_key(
            document_id=scope.document_id,
            revision_id=scope.revision_id,
            source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id,
            decision_scope_id=scope.decision_scope_id,
        )
        prior = self._records.get(key)
        if prior is not None and prior != record:
            raise RuntimeError(PRODUCER_EQUIVOCATION)
        self._records[key] = record
        return record

    def authority(self) -> "OpeningUniverseCompletenessAuthority":
        return OpeningUniverseCompletenessAuthority(
            MappingProxyType(dict(self._records)),
            _seal=_AUTHORITY_SEAL,
        )


class OpeningUniverseCompletenessAuthority:
    """Read-only selector resolver for producer-owned completeness records."""

    def __init__(
        self,
        records: Mapping[
            tuple[str, str, str, str, str], OpeningUniverseCompletenessRecord
        ],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "OpeningUniverseCompletenessAuthority must be obtained from "
                "OpeningUniverseCompletenessProducer.authority()"
            )
        self._records = records

    def resolve(
        self, selector: OpeningUniverseSelector
    ) -> OpeningUniverseCompletenessResult:
        key = _record_key(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
        )
        if any(not value for value in key):
            return OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                source_decode_complete=None,
                semantic_enumeration_complete=None,
                decision_scope_complete=None,
                reason_codes=(COMPLETENESS_RECORD_UNAVAILABLE,),
            )
        record = self._records.get(key)
        if record is None:
            return OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                source_decode_complete=None,
                semantic_enumeration_complete=None,
                decision_scope_complete=None,
                reason_codes=(COMPLETENESS_RECORD_UNAVAILABLE,),
            )
        if record.decision_scope_complete:
            return OpeningUniverseCompletenessResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                source_decode_complete=True,
                semantic_enumeration_complete=True,
                decision_scope_complete=True,
                reason_codes=(),
                record=record,
            )
        return OpeningUniverseCompletenessResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            source_decode_complete=record.source_decode_complete,
            semantic_enumeration_complete=record.semantic_enumeration_complete,
            decision_scope_complete=record.decision_scope_complete,
            reason_codes=record.reason_codes or (SEMANTIC_ENUMERATION_INCOMPLETE,),
            record=record,
        )


__all__ = [
    "OPENING_UNIVERSE_COMPLETENESS_SCHEMA_VERSION",
    "OpeningUniverseCompletenessAuthority",
    "OpeningUniverseCompletenessProducer",
    "OpeningUniverseCompletenessRecord",
    "OpeningUniverseCompletenessResult",
    "SemanticOpeningMemberDisposition",
    "SemanticSourceDispositionState",
    "OpeningUniverseMember",
    "OpeningUniverseScope",
    "OpeningUniverseSelector",
    "SourceEnumerationState",
    "build_opening_universe_member_from_indexed_primitive",
    "build_opening_universe_scope",
]
