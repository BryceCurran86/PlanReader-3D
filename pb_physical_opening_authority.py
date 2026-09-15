"""G17 phase-2 physical-opening semantic existence authority.

Phase 1 proves immutable producer-owned source observations and lineage.  This
module adds one deliberately narrow positive semantic proposition on top of
that substrate: a physical opening may be said to exist when producer-owned
native geometry independently shows a jamb-bounded interruption on both faces
of one local wall band.

The positive rule is intentionally smaller than the existing hosted-opening
shadow detector.  It consumes only native source-segment observations from the
producer snapshot, re-derives the structural relationship deterministically,
and never trusts caller-created candidate lists, confidence, tags, schedules,
derived classifications or ``CORROBORATED`` flags to manufacture authority.

Existence remains separate from identity.  A resolved record does NOT establish
opening width/height/area, door/window schedule identity, exact instance
identity across views, host-wall identity/binding, opening-universe
completeness, physical void, net wall area, commercial publication or FIRM
quantity authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional, Sequence

import pb_hosted_opening_geometry as _hosted_geometry
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationAuthority,
    SourceObservationAuthorityResult,
    SourceObservationRecord,
)


PHYSICAL_OPENING_EXISTENCE_UNRESOLVED = "physical_opening_existence_unresolved"
PHYSICAL_OPENING_EXISTS = "physical_opening_exists"
PHYSICAL_OPENING_IDENTITY_UNRESOLVED = "physical_opening_identity_unresolved"

PHYSICAL_OPENING_CANDIDATE = "candidate"
PHYSICAL_OPENING_RESOLVED_EXISTENCE = "resolved_existence"
PHYSICAL_OPENING_BLOCKED = "blocked"
PHYSICAL_OPENING_AMBIGUOUS = "ambiguous"

AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE = (
    "authoritative_physical_opening_semantics_unavailable"
)
AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE = (
    "authoritative_physical_opening_identity_unavailable"
)
MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY = (
    "independent source-native physical opening instance semantic producer"
)

REASON_JAMB_BOUNDED_TWO_FACE_INTERRUPTION = (
    "producer_backed_jamb_bounded_two_face_interruption"
)
REASON_ALIGNED_TWO_FACE_GAP = "producer_backed_aligned_two_face_gap"
REASON_JAMB_BOUNDARIES_UNRESOLVED = "jamb_boundaries_unresolved"
REASON_MULTIPLE_PHYSICAL_OPENING_CANDIDATES = "multiple_physical_opening_candidates"
REASON_CROSS_ORIENTATION_AMBIGUITY = "cross_orientation_opening_ambiguity"


@dataclass(frozen=True)
class PhysicalOpeningExistenceRecord:
    """One local physical-opening existence decision with immutable trace.

    ``semantic_class`` is descriptive only.  ``opening`` means the structural
    evidence supports a local physical void-like opening; it is not door/window
    type authority and cannot be used as a schedule identity.
    """

    record_id: str
    source_observation_ids: tuple[str, ...]
    source_root_observation_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    semantic_class: str
    resolution_state: str
    status: EvidenceResolutionStatus
    confidence: float
    reason_codes: tuple[str, ...]
    blocking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class PhysicalOpeningExistenceResult:
    """Result for the physical-opening existence proposition."""

    status: EvidenceResolutionStatus
    proposition: Optional[str]
    physical_opening_existence: str
    reason_codes: tuple[str, ...]
    source_observation: Optional[SourceObservationAuthorityResult] = None
    missing_upstream_capability: Optional[str] = None
    record: Optional[PhysicalOpeningExistenceRecord] = None


@dataclass(frozen=True)
class PhysicalOpeningIdentityResult:
    """Fail-closed result for whether two observations denote one opening."""

    status: EvidenceResolutionStatus
    physical_opening_identity: str
    proven_same: bool
    reason_codes: tuple[str, ...]
    left_source_observation: Optional[SourceObservationAuthorityResult] = None
    right_source_observation: Optional[SourceObservationAuthorityResult] = None
    missing_upstream_capability: Optional[str] = None


@dataclass(frozen=True)
class _AxisSegment:
    observation_id: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass(frozen=True)
class _SupportInterval:
    lo: float
    hi: float
    observation_ids: tuple[str, ...]


@dataclass(frozen=True)
class _Gap:
    lo: float
    hi: float
    support_ids: tuple[str, ...]


@dataclass(frozen=True)
class _PageHit:
    resolution_state: str
    orientation: str
    bbox: tuple[float, float, float, float]
    source_observation_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    blocking_reasons: tuple[str, ...]


def _dedupe_reason_codes(*groups: tuple[str, ...]) -> tuple[str, ...]:
    result: list[str] = []
    for group in groups:
        for reason in group:
            clean = str(reason or "").strip()
            if clean and clean not in result:
                result.append(clean)
    return tuple(result)


def _source_failure_status(*results: SourceObservationAuthorityResult) -> EvidenceResolutionStatus:
    if any(result.status is EvidenceResolutionStatus.CONFLICT for result in results):
        return EvidenceResolutionStatus.CONFLICT
    return EvidenceResolutionStatus.ABSTAINED


def _finite_geometry(record: SourceObservationRecord) -> Optional[tuple[float, float, float, float]]:
    if record.observation_kind != "native_pdf_segment" or len(record.geometry) != 4:
        return None
    values = tuple(float(v) for v in record.geometry)
    if not all(math.isfinite(v) for v in values):
        return None
    x0, y0, x1, y1 = values
    if math.hypot(x1 - x0, y1 - y0) <= 0.5:
        return None
    return x0, y0, x1, y1


def _snapshot_results(
    authority: SourceObservationAuthority,
    seed: SourceObservationAuthorityResult,
) -> dict[str, SourceObservationAuthorityResult]:
    snapshot = seed.snapshot
    revision = seed.source_revision
    if snapshot is None or revision is None:
        return {}
    out: dict[str, SourceObservationAuthorityResult] = {}
    for observation_id in snapshot.observation_ids:
        result = authority.resolve(
            ObservationSelector(
                document_id=snapshot.document_id,
                revision_id=snapshot.revision_id,
                source_sha256=snapshot.source_sha256,
                snapshot_id=snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if result.status is EvidenceResolutionStatus.CORROBORATED and result.observation is not None:
            out[observation_id] = result
    return out


def _root_ids(
    observation_id: str,
    records: dict[str, SourceObservationRecord],
    *,
    _seen: Optional[set[str]] = None,
) -> tuple[str, ...]:
    seen = set(_seen or ())
    if observation_id in seen:
        return (observation_id,)
    seen.add(observation_id)
    record = records.get(observation_id)
    if record is None or not record.derivation_parent_ids:
        return (observation_id,)
    roots: set[str] = set()
    for parent_id in record.derivation_parent_ids:
        roots.update(_root_ids(parent_id, records, _seen=seen))
    return tuple(sorted(roots))


def _axis_segments(
    records: Sequence[SourceObservationRecord],
    *,
    page_id: str,
    swapped: bool,
) -> tuple[list[_AxisSegment], list[_AxisSegment]]:
    horizontal: list[_AxisSegment] = []
    vertical: list[_AxisSegment] = []
    for record in records:
        if record.page_id != page_id or record.origin_kind != "native":
            continue
        geometry = _finite_geometry(record)
        if geometry is None:
            continue
        x0, y0, x1, y1 = geometry
        if swapped:
            x0, y0, x1, y1 = y0, x0, y1, x1
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        segment = _AxisSegment(record.observation_id, x0, y0, x1, y1)
        if dy <= 0.5 and dx > 0.5:
            horizontal.append(segment)
        elif dx <= 0.5 and dy > 0.5:
            vertical.append(segment)
    horizontal.sort(key=lambda s: ((s.y0 + s.y1) / 2.0, min(s.x0, s.x1), max(s.x0, s.x1), s.observation_id))
    vertical.sort(key=lambda s: ((s.x0 + s.x1) / 2.0, min(s.y0, s.y1), max(s.y0, s.y1), s.observation_id))
    return horizontal, vertical


def _bucket_rows(segments: Sequence[_AxisSegment]) -> list[tuple[float, list[_AxisSegment]]]:
    rows: list[tuple[float, list[_AxisSegment]]] = []
    tolerance = float(_hosted_geometry._FACE_COORD_TOL_PT)
    for segment in segments:
        y = (segment.y0 + segment.y1) / 2.0
        for index, (row_y, members) in enumerate(rows):
            if abs(row_y - y) <= tolerance:
                updated = [*members, segment]
                rows[index] = (sum((m.y0 + m.y1) / 2.0 for m in updated) / len(updated), updated)
                break
        else:
            rows.append((y, [segment]))
    rows.sort(key=lambda row: row[0])
    return rows


def _merge_row(segments: Sequence[_AxisSegment]) -> list[_SupportInterval]:
    intervals = sorted(
        (
            _SupportInterval(
                min(segment.x0, segment.x1),
                max(segment.x0, segment.x1),
                (segment.observation_id,),
            )
            for segment in segments
        ),
        key=lambda interval: (interval.lo, interval.hi, interval.observation_ids),
    )
    merged: list[_SupportInterval] = []
    for interval in intervals:
        if not merged or interval.lo > merged[-1].hi + 1e-6:
            merged.append(interval)
            continue
        previous = merged[-1]
        merged[-1] = _SupportInterval(
            previous.lo,
            max(previous.hi, interval.hi),
            tuple(sorted(set(previous.observation_ids) | set(interval.observation_ids))),
        )
    return merged


def _row_is_credible(intervals: Sequence[_SupportInterval], span_lo: float, span_hi: float) -> bool:
    span = span_hi - span_lo
    if span < float(_hosted_geometry._MIN_BAND_RUN_PT):
        return False
    clipped: list[tuple[float, float]] = []
    for interval in intervals:
        lo = max(span_lo, interval.lo)
        hi = min(span_hi, interval.hi)
        if hi > lo:
            clipped.append((lo, hi))
    covered = sum(hi - lo for lo, hi in clipped)
    if covered / span < float(_hosted_geometry._MIN_BAND_COVERAGE_FRACTION):
        return False
    gaps = max(0, len(clipped) - 1)
    density = gaps / span * 100.0
    return density <= float(_hosted_geometry._MAX_GAP_DENSITY_PER_100PT)


def _gaps(intervals: Sequence[_SupportInterval], span_lo: float, span_hi: float) -> list[_Gap]:
    clipped = [interval for interval in intervals if interval.hi > span_lo and interval.lo < span_hi]
    gaps: list[_Gap] = []
    for left, right in zip(clipped, clipped[1:]):
        lo = max(span_lo, left.hi)
        hi = min(span_hi, right.lo)
        if hi <= lo:
            continue
        gaps.append(
            _Gap(
                lo,
                hi,
                tuple(sorted(set(left.observation_ids) | set(right.observation_ids))),
            )
        )
    return gaps


def _jamb_support(
    vertical: Sequence[_AxisSegment],
    *,
    x: float,
    near_y: float,
    far_y: float,
) -> tuple[str, ...]:
    coord_tol = float(_hosted_geometry._FACE_COORD_TOL_PT)
    coverage_tol = float(_hosted_geometry._JAMB_COVERAGE_TOL_PT)
    lo, hi = min(near_y, far_y), max(near_y, far_y)
    candidates: list[tuple[float, float, str]] = []
    for segment in vertical:
        sx = (segment.x0 + segment.x1) / 2.0
        if abs(sx - x) > coord_tol:
            continue
        candidates.append((min(segment.y0, segment.y1), max(segment.y0, segment.y1), segment.observation_id))
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    if not candidates:
        return ()

    run_lo, run_hi = candidates[0][0], candidates[0][1]
    support: set[str] = {candidates[0][2]}
    for seg_lo, seg_hi, observation_id in candidates[1:]:
        if seg_lo <= run_hi + coord_tol:
            run_hi = max(run_hi, seg_hi)
            support.add(observation_id)
        else:
            if run_lo <= lo + coverage_tol and run_hi >= hi - coverage_tol:
                return tuple(sorted(support))
            run_lo, run_hi = seg_lo, seg_hi
            support = {observation_id}
    if run_lo <= lo + coverage_tol and run_hi >= hi - coverage_tol:
        return tuple(sorted(support))
    return ()


def _normalize_bbox(values: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = values
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _detect_orientation(
    records: Sequence[SourceObservationRecord],
    *,
    page_id: str,
    swapped: bool,
) -> list[_PageHit]:
    horizontal, vertical = _axis_segments(records, page_id=page_id, swapped=swapped)
    rows = _bucket_rows(horizontal)
    hits: list[_PageHit] = []
    for row_index in range(len(rows)):
        y_a, segments_a = rows[row_index]
        merged_a = _merge_row(segments_a)
        if not merged_a:
            continue
        for other_index in range(row_index + 1, len(rows)):
            y_b, segments_b = rows[other_index]
            thickness = abs(y_b - y_a)
            if thickness < float(_hosted_geometry._MIN_WALL_THICKNESS_PT):
                continue
            if thickness > float(_hosted_geometry._MAX_WALL_THICKNESS_PT):
                break
            merged_b = _merge_row(segments_b)
            if not merged_b:
                continue
            span_lo = max(merged_a[0].lo, merged_b[0].lo)
            span_hi = min(merged_a[-1].hi, merged_b[-1].hi)
            if span_hi <= span_lo:
                continue
            if not (_row_is_credible(merged_a, span_lo, span_hi) and _row_is_credible(merged_b, span_lo, span_hi)):
                continue
            gaps_a = _gaps(merged_a, span_lo, span_hi)
            gaps_b = _gaps(merged_b, span_lo, span_hi)
            for gap_a in gaps_a:
                for gap_b in gaps_b:
                    if abs(gap_a.lo - gap_b.lo) > float(_hosted_geometry._FACE_COORD_TOL_PT):
                        continue
                    if abs(gap_a.hi - gap_b.hi) > float(_hosted_geometry._FACE_COORD_TOL_PT):
                        continue
                    gap_lo = max(gap_a.lo, gap_b.lo)
                    gap_hi = min(gap_a.hi, gap_b.hi)
                    gap_width = gap_hi - gap_lo
                    if gap_width < float(_hosted_geometry._MIN_GAP_PT):
                        continue
                    if gap_width < float(_hosted_geometry._MIN_GAP_TO_THICKNESS_RATIO) * thickness:
                        continue
                    start_jamb = _jamb_support(vertical, x=gap_lo, near_y=y_a, far_y=y_b)
                    end_jamb = _jamb_support(vertical, x=gap_hi, near_y=y_a, far_y=y_b)
                    support_ids = tuple(
                        sorted(
                            set(gap_a.support_ids)
                            | set(gap_b.support_ids)
                            | set(start_jamb)
                            | set(end_jamb)
                        )
                    )
                    if swapped:
                        bbox = _normalize_bbox((y_a, gap_lo, y_b, gap_hi))
                        orientation = "vertical"
                    else:
                        bbox = _normalize_bbox((gap_lo, y_a, gap_hi, y_b))
                        orientation = "horizontal"
                    if start_jamb and end_jamb:
                        hits.append(
                            _PageHit(
                                resolution_state=PHYSICAL_OPENING_RESOLVED_EXISTENCE,
                                orientation=orientation,
                                bbox=bbox,
                                source_observation_ids=support_ids,
                                reason_codes=(REASON_JAMB_BOUNDED_TWO_FACE_INTERRUPTION,),
                                blocking_reasons=(),
                            )
                        )
                    else:
                        hits.append(
                            _PageHit(
                                resolution_state=PHYSICAL_OPENING_CANDIDATE,
                                orientation=orientation,
                                bbox=bbox,
                                source_observation_ids=support_ids,
                                reason_codes=(REASON_ALIGNED_TWO_FACE_GAP,),
                                blocking_reasons=(REASON_JAMB_BOUNDARIES_UNRESOLVED,),
                            )
                        )
    unique: dict[tuple[object, ...], _PageHit] = {}
    for hit in hits:
        key = (
            hit.resolution_state,
            hit.orientation,
            tuple(round(v, 4) for v in hit.bbox),
            hit.source_observation_ids,
        )
        unique[key] = hit
    return sorted(
        unique.values(),
        key=lambda hit: (
            hit.resolution_state,
            hit.orientation,
            hit.bbox,
            hit.source_observation_ids,
        ),
    )


def _bbox_overlap(left: _PageHit, right: _PageHit) -> bool:
    lx0, ly0, lx1, ly1 = left.bbox
    rx0, ry0, rx1, ry1 = right.bbox
    return min(lx1, rx1) > max(lx0, rx0) and min(ly1, ry1) > max(ly0, ry0)


def _page_hits(records: Sequence[SourceObservationRecord], *, page_id: str) -> list[_PageHit]:
    return [
        *_detect_orientation(records, page_id=page_id, swapped=False),
        *_detect_orientation(records, page_id=page_id, swapped=True),
    ]


def _record_for_hit(
    *,
    hit: _PageHit,
    seed: SourceObservationAuthorityResult,
    records: dict[str, SourceObservationRecord],
    resolution_state: Optional[str] = None,
    status: Optional[EvidenceResolutionStatus] = None,
    reason_codes: Optional[tuple[str, ...]] = None,
    blocking_reasons: Optional[tuple[str, ...]] = None,
) -> PhysicalOpeningExistenceRecord:
    source = seed.observation
    revision = seed.source_revision
    snapshot = seed.snapshot
    if source is None or revision is None or snapshot is None:
        raise ValueError("producer-backed source observation required")
    support_ids = tuple(sorted(set(hit.source_observation_ids)))
    roots: set[str] = set()
    for observation_id in support_ids:
        roots.update(_root_ids(observation_id, records))
    support_records = [records[observation_id] for observation_id in support_ids if observation_id in records]
    viewport_values = {record.viewport_id for record in support_records if record.viewport_id is not None}
    viewport_id = next(iter(viewport_values)) if len(viewport_values) == 1 else None
    state = resolution_state or hit.resolution_state
    resolved_status = status or (
        EvidenceResolutionStatus.CORROBORATED
        if state == PHYSICAL_OPENING_RESOLVED_EXISTENCE
        else EvidenceResolutionStatus.CANDIDATE
    )
    reasons = reason_codes or hit.reason_codes
    blockers = blocking_reasons if blocking_reasons is not None else hit.blocking_reasons
    record_id = stable_contract_id(
        "physical_opening_existence",
        {
            "document_id": revision.document_id,
            "revision_id": revision.revision_id,
            "source_sha256": revision.source_sha256,
            "snapshot_id": snapshot.snapshot_id,
            "page_id": source.page_id,
            "source_observation_ids": support_ids,
            "source_root_observation_ids": sorted(roots),
            "resolution_state": state,
        },
        digest_chars=32,
    )
    confidence = 1.0 if state == PHYSICAL_OPENING_RESOLVED_EXISTENCE else 0.5
    if state in {PHYSICAL_OPENING_BLOCKED, PHYSICAL_OPENING_AMBIGUOUS}:
        confidence = 0.0
    return PhysicalOpeningExistenceRecord(
        record_id=record_id,
        source_observation_ids=support_ids,
        source_root_observation_ids=tuple(sorted(roots)),
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        page_id=source.page_id,
        viewport_id=viewport_id,
        semantic_class="opening" if state != PHYSICAL_OPENING_BLOCKED else "unknown",
        resolution_state=state,
        status=resolved_status,
        confidence=confidence,
        reason_codes=reasons,
        blocking_reasons=blockers,
    )


def _blocked_record(
    seed: SourceObservationAuthorityResult,
    records: dict[str, SourceObservationRecord],
) -> Optional[PhysicalOpeningExistenceRecord]:
    source = seed.observation
    revision = seed.source_revision
    snapshot = seed.snapshot
    if source is None or revision is None or snapshot is None:
        return None
    roots = _root_ids(source.observation_id, records)
    record_id = stable_contract_id(
        "physical_opening_existence",
        {
            "document_id": revision.document_id,
            "revision_id": revision.revision_id,
            "source_sha256": revision.source_sha256,
            "snapshot_id": snapshot.snapshot_id,
            "page_id": source.page_id,
            "source_observation_ids": [source.observation_id],
            "source_root_observation_ids": list(roots),
            "resolution_state": PHYSICAL_OPENING_BLOCKED,
        },
        digest_chars=32,
    )
    return PhysicalOpeningExistenceRecord(
        record_id=record_id,
        source_observation_ids=(source.observation_id,),
        source_root_observation_ids=roots,
        document_id=revision.document_id,
        revision_id=revision.revision_id,
        source_sha256=revision.source_sha256,
        snapshot_id=snapshot.snapshot_id,
        page_id=source.page_id,
        viewport_id=source.viewport_id,
        semantic_class="unknown",
        resolution_state=PHYSICAL_OPENING_BLOCKED,
        status=EvidenceResolutionStatus.ABSTAINED,
        confidence=0.0,
        reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
        blocking_reasons=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
    )


class PhysicalOpeningAuthority:
    """Read-only Phase-2 semantic authority over producer-owned Phase-1 data."""

    def __init__(self, source_observation_authority: SourceObservationAuthority) -> None:
        if type(source_observation_authority) is not SourceObservationAuthority:
            raise TypeError(
                "source_observation_authority must be the concrete producer-owned "
                "SourceObservationAuthority reader"
            )
        self._source_observation_authority = source_observation_authority

    @staticmethod
    def capabilities() -> dict[str, bool]:
        """Legacy downstream-promotion capabilities; intentionally unchanged.

        This method remains all-false so no existing consumer interprets the new
        semantic existence proposition as permission to publish dimensions,
        deductions, commercial quantities or FIRM authority.
        """

        return {
            "physical_opening_existence": False,
            "physical_opening_identity": False,
            "opening_universe_complete": False,
            "opening_dimensions": False,
            "host_identity": False,
            "host_binding": False,
            "physical_void": False,
            "net_wall_area": False,
        }

    @staticmethod
    def semantic_capabilities() -> dict[str, bool]:
        """Phase-2 semantic propositions this authority can now establish."""

        return {
            "physical_opening_existence": True,
            "physical_opening_identity": False,
            "opening_universe_complete": False,
            "opening_dimensions": False,
            "host_identity": False,
            "host_binding": False,
            "physical_void": False,
            "net_wall_area": False,
        }

    def prove_existence(self, selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        """Resolve one seed observation against producer-owned page geometry.

        The selector identifies the consumer's target observation only.  The
        caller cannot submit the candidate group, corroboration flag or evidence
        scope.  Candidate membership is re-derived from the complete producer
        snapshot for that page.
        """

        if not isinstance(selector, ObservationSelector):
            raise TypeError("selector must be ObservationSelector")

        source_result = self._source_observation_authority.resolve(selector)
        if source_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return PhysicalOpeningExistenceResult(
                status=_source_failure_status(source_result),
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=_dedupe_reason_codes(source_result.reason_codes),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        snapshot_results = _snapshot_results(self._source_observation_authority, source_result)
        records = {
            observation_id: result.observation
            for observation_id, result in snapshot_results.items()
            if result.observation is not None
        }
        source = source_result.observation
        if source is None:
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CONFLICT,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        seed_roots = set(_root_ids(source.observation_id, records))
        hits = _page_hits(tuple(records.values()), page_id=source.page_id)
        matching = [
            hit
            for hit in hits
            if seed_roots.intersection(hit.source_observation_ids)
            or source.observation_id in hit.source_observation_ids
        ]
        resolved = [hit for hit in matching if hit.resolution_state == PHYSICAL_OPENING_RESOLVED_EXISTENCE]

        if len(resolved) == 1:
            chosen = resolved[0]
            cross_conflict = any(
                other is not chosen
                and other.resolution_state == PHYSICAL_OPENING_RESOLVED_EXISTENCE
                and other.orientation != chosen.orientation
                and _bbox_overlap(chosen, other)
                for other in hits
            )
            if not cross_conflict:
                record = _record_for_hit(hit=chosen, seed=source_result, records=records)
                return PhysicalOpeningExistenceResult(
                    status=EvidenceResolutionStatus.CORROBORATED,
                    proposition=PHYSICAL_OPENING_EXISTS,
                    physical_opening_existence=PHYSICAL_OPENING_EXISTS,
                    reason_codes=record.reason_codes,
                    source_observation=source_result,
                    missing_upstream_capability=None,
                    record=record,
                )
            record = _record_for_hit(
                hit=chosen,
                seed=source_result,
                records=records,
                resolution_state=PHYSICAL_OPENING_AMBIGUOUS,
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(REASON_CROSS_ORIENTATION_AMBIGUITY,),
                blocking_reasons=(REASON_CROSS_ORIENTATION_AMBIGUITY,),
            )
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CONFLICT,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=record.reason_codes,
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
                record=record,
            )

        if len(resolved) > 1:
            support = tuple(sorted({observation_id for hit in resolved for observation_id in hit.source_observation_ids}))
            synthetic = _PageHit(
                resolution_state=PHYSICAL_OPENING_AMBIGUOUS,
                orientation="ambiguous",
                bbox=resolved[0].bbox,
                source_observation_ids=support,
                reason_codes=(REASON_MULTIPLE_PHYSICAL_OPENING_CANDIDATES,),
                blocking_reasons=(REASON_MULTIPLE_PHYSICAL_OPENING_CANDIDATES,),
            )
            record = _record_for_hit(
                hit=synthetic,
                seed=source_result,
                records=records,
                resolution_state=PHYSICAL_OPENING_AMBIGUOUS,
                status=EvidenceResolutionStatus.CONFLICT,
            )
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CONFLICT,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=record.reason_codes,
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
                record=record,
            )

        candidate_hits = [hit for hit in matching if hit.resolution_state == PHYSICAL_OPENING_CANDIDATE]
        if len(candidate_hits) == 1:
            record = _record_for_hit(hit=candidate_hits[0], seed=source_result, records=records)
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.CANDIDATE,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=record.reason_codes,
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
                record=record,
            )
        if len(candidate_hits) > 1:
            support = tuple(sorted({observation_id for hit in candidate_hits for observation_id in hit.source_observation_ids}))
            synthetic = _PageHit(
                resolution_state=PHYSICAL_OPENING_AMBIGUOUS,
                orientation="ambiguous",
                bbox=candidate_hits[0].bbox,
                source_observation_ids=support,
                reason_codes=(REASON_MULTIPLE_PHYSICAL_OPENING_CANDIDATES,),
                blocking_reasons=(REASON_MULTIPLE_PHYSICAL_OPENING_CANDIDATES,),
            )
            record = _record_for_hit(
                hit=synthetic,
                seed=source_result,
                records=records,
                resolution_state=PHYSICAL_OPENING_AMBIGUOUS,
                status=EvidenceResolutionStatus.ABSTAINED,
            )
            return PhysicalOpeningExistenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                proposition=None,
                physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
                reason_codes=record.reason_codes,
                source_observation=source_result,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
                record=record,
            )

        record = _blocked_record(source_result, records)
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            proposition=None,
            physical_opening_existence=PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
            reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE,),
            source_observation=source_result,
            missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            record=record,
        )

    def compare_identity(
        self,
        left_selector: ObservationSelector,
        right_selector: ObservationSelector,
    ) -> PhysicalOpeningIdentityResult:
        """Existence does not establish reusable physical-opening identity."""

        if not isinstance(left_selector, ObservationSelector):
            raise TypeError("left_selector must be ObservationSelector")
        if not isinstance(right_selector, ObservationSelector):
            raise TypeError("right_selector must be ObservationSelector")

        left = self._source_observation_authority.resolve(left_selector)
        right = self._source_observation_authority.resolve(right_selector)
        if (
            left.status is not EvidenceResolutionStatus.CORROBORATED
            or right.status is not EvidenceResolutionStatus.CORROBORATED
        ):
            return PhysicalOpeningIdentityResult(
                status=_source_failure_status(left, right),
                physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
                proven_same=False,
                reason_codes=_dedupe_reason_codes(left.reason_codes, right.reason_codes),
                left_source_observation=left,
                right_source_observation=right,
                missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
            )

        return PhysicalOpeningIdentityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            physical_opening_identity=PHYSICAL_OPENING_IDENTITY_UNRESOLVED,
            proven_same=False,
            reason_codes=(AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE,),
            left_source_observation=left,
            right_source_observation=right,
            missing_upstream_capability=MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY,
        )


__all__ = [
    "AUTHORITATIVE_PHYSICAL_OPENING_IDENTITY_UNAVAILABLE",
    "AUTHORITATIVE_PHYSICAL_OPENING_SEMANTICS_UNAVAILABLE",
    "MISSING_PHYSICAL_OPENING_SEMANTIC_CAPABILITY",
    "PHYSICAL_OPENING_AMBIGUOUS",
    "PHYSICAL_OPENING_BLOCKED",
    "PHYSICAL_OPENING_CANDIDATE",
    "PHYSICAL_OPENING_EXISTENCE_UNRESOLVED",
    "PHYSICAL_OPENING_EXISTS",
    "PHYSICAL_OPENING_IDENTITY_UNRESOLVED",
    "PHYSICAL_OPENING_RESOLVED_EXISTENCE",
    "REASON_ALIGNED_TWO_FACE_GAP",
    "REASON_CROSS_ORIENTATION_AMBIGUITY",
    "REASON_JAMB_BOUNDED_TWO_FACE_INTERRUPTION",
    "REASON_JAMB_BOUNDARIES_UNRESOLVED",
    "REASON_MULTIPLE_PHYSICAL_OPENING_CANDIDATES",
    "PhysicalOpeningAuthority",
    "PhysicalOpeningExistenceRecord",
    "PhysicalOpeningExistenceResult",
    "PhysicalOpeningIdentityResult",
]