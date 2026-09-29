"""SHADOW: authenticated floor-plan viewport scope for G17 opening candidates.

G17 (``PhysicalOpeningAuthority``) discovers ``jamb_bounded_two_face_interruption``
candidates page-wide (``viewport_id`` is always ``None``). On multi-view sheets
that admits elevation window-pane grids, section linework, roof-sheet patterns
and legend/title geometry as "physical openings". This module measures, without
changing any live output, where every G17 candidate on a page falls relative to
the page's *authenticated* views.

Authentication is NOT decided here. It reuses the existing F.07 gate
(``pb_physical_wall_candidate_authority._authenticated_viewports``): every row
must be a ``segment_page_viewports`` product; a ``RESOLVED`` vector frame is
authenticated; a ``DERIVED`` partition is authenticated only when it is an
authoritative columnar title grid AND the complete sibling set is
non-overlapping. Every other viewport remains unauthenticated. Only positive
source-drawn frame geometry may contest an authenticated view: an
unauthenticated ``VECTOR_FRAME`` bbox or a genuine ``candidate_frames``
alternative from an ambiguous view. Synthetic ``TITLE_PARTITION`` cells
remain abstention-class evidence but do not independently contest ownership
established by a drawn frame.

Scopes (a candidate is "in" a view only when every support segment lies inside
exactly one authenticated view and touches no contesting view):

``in_authenticated_floor_plan_viewport``
    the only scope in which a later promotion could let G17 existence stand. It
    is necessary, never sufficient: ``evidence_direction`` is ``scope_only``.
``in_authenticated_non_plan_viewport``
    drawn inside an authenticated elevation / section / roof plan / legend /
    schedule / specification view whose boundary is a *drawn vector frame*.
    This is evidence AGAINST promotion (``evidence_direction`` is
    ``against_promotion``). It is never proof of non-existence and never
    deletion authority: ``deletion_authority`` is always ``False``.
``in_authenticated_view_of_unproven_type``
    inside one authenticated view whose type cannot support either reading: a
    detail (may be an enlarged plan), a repeated/adjacent reference, an unknown
    or unrecognised type, or a non-plan type whose boundary is only a derived
    title partition (a bisector cell, not a drawn extent).
``outside_authenticated_viewports``
    the page has authenticated views, no source-drawn contest frame owns the
    candidate, and there is no unlocalised unauthenticated view that could still
    own it. Never a negative proof; only the floor-plan scope can promote.
``ambiguous_authenticated_viewport_ownership``
    the support straddles or crosses a view boundary, lies in overlapping
    authenticated views, or touches positive source-drawn competing frame
    geometry from an unauthenticated / ambiguous view.
``support_geometry_unreadable``
    a support observation has no usable finite geometry: abstains, never relaxes
    containment.
``no_authenticated_viewport``
    no authenticated view proves ownership: the page has none, or it has an
    unauthenticated view that could not be localised. Abstains; never negative.

This is observation only. It does not mutate G17 records, does not change
existence, closure, enumeration, host binding, voids, walls or publication, and
it reads source bytes only from the producer's own content-addressed store.
Abstain reports carry ``candidate_scopes == ()`` meaning candidates were not
enumerated, not that there are none. ``existence_corroborated`` re-states the
containment==1 proposition of ``prove_existence`` for reporting only.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    CandidateSemanticOpening,
    PhysicalOpeningAuthority,
    _line_geometry,
)
from pb_physical_wall_candidate_authority import _authenticated_viewports
from pb_source_observation_authority import STALE_REVISION, ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import SegmentedViewport, ViewportBoundarySource


OPENING_VIEWPORT_SCOPE_SHADOW_SCHEMA_VERSION = "2.0.0"

IN_AUTHENTICATED_FLOOR_PLAN = "in_authenticated_floor_plan_viewport"
IN_AUTHENTICATED_NON_PLAN = "in_authenticated_non_plan_viewport"
IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN = "in_authenticated_view_of_unproven_type"
OUTSIDE_AUTHENTICATED_VIEWPORTS = "outside_authenticated_viewports"
AMBIGUOUS_AUTHENTICATED_OWNERSHIP = "ambiguous_authenticated_viewport_ownership"
SUPPORT_GEOMETRY_UNREADABLE = "support_geometry_unreadable"
NO_AUTHENTICATED_VIEWPORT = "no_authenticated_viewport"

EVIDENCE_DIRECTION_SCOPE_ONLY = "scope_only"
EVIDENCE_DIRECTION_AGAINST_PROMOTION = "against_promotion"
EVIDENCE_DIRECTION_NONE = "none"

OPENING_VIEWPORT_SCOPE_ASSESSED = "opening_viewport_scope_assessed"
OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE = "opening_viewport_scope_source_unavailable"
OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED = "opening_viewport_scope_segmentation_failed"
OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS = "opening_viewport_scope_no_visible_segments"
OPENING_VIEWPORT_SCOPE_SNAPSHOT_INTEGRITY_FAILED = "opening_viewport_scope_snapshot_integrity_failed"

FLOOR_PLAN_VIEW_TYPE = DrawingViewType.FLOOR_PLAN.value
# Explicit allow-list: only these view types may yield a typed negative, and only
# when the view boundary is a drawn vector frame. Everything else abstains.
TYPED_NEGATIVE_VIEW_TYPES = frozenset(
    view_type.value
    for view_type in (
        DrawingViewType.ROOF_PLAN,
        DrawingViewType.ELEVATION,
        DrawingViewType.SECTION,
        DrawingViewType.SCHEDULE,
        DrawingViewType.LEGEND,
        DrawingViewType.SPECIFICATION,
    )
)

_SCOPES = (
    IN_AUTHENTICATED_FLOOR_PLAN,
    IN_AUTHENTICATED_NON_PLAN,
    IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN,
    OUTSIDE_AUTHENTICATED_VIEWPORTS,
    AMBIGUOUS_AUTHENTICATED_OWNERSHIP,
    SUPPORT_GEOMETRY_UNREADABLE,
    NO_AUTHENTICATED_VIEWPORT,
)

_BBOX_TOLERANCE = 0.5

BBox = tuple[float, float, float, float]
Segment = tuple[float, float, float, float]


@dataclass(frozen=True)
class AuthenticatedViewportRecord:
    view_id: str
    view_type: str
    status: str
    boundary_source: str
    bounding_box: BBox


@dataclass(frozen=True)
class OpeningCandidateViewportScope:
    candidate_id: str
    structural_pattern: str
    scope: str
    view_id: Optional[str]
    view_type: Optional[str]
    existence_corroborated: bool
    source_observation_ids: tuple[str, ...]
    boundary_source: Optional[str] = None
    evidence_direction: str = EVIDENCE_DIRECTION_NONE
    deletion_authority: bool = False
    takeoff_eligible: bool = False


@dataclass(frozen=True)
class OpeningViewportScopeShadowReport:
    record_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    authenticated_viewports: tuple[AuthenticatedViewportRecord, ...]
    unauthenticated_viewport_count: int
    candidate_scopes: tuple[OpeningCandidateViewportScope, ...]
    scope_counts: Mapping[str, int]
    corroborated_scope_counts: Mapping[str, int]
    schema_version: str = OPENING_VIEWPORT_SCOPE_SHADOW_SCHEMA_VERSION
    deletion_authority: bool = False
    takeoff_eligible: bool = False


def _finite_bbox(value: object) -> Optional[BBox]:
    try:
        x0, y0, x1, y1 = (float(item) for item in value)  # type: ignore[union-attr]
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(item) for item in (x0, y0, x1, y1)):
        return None
    return (min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1))


def _same_bbox(a: BBox, b: BBox) -> bool:
    return all(abs(left - right) <= _BBOX_TOLERANCE for left, right in zip(a, b))


def _inside(point: tuple[float, float], bbox: BBox) -> bool:
    x0, y0, x1, y1 = bbox
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def _segment_touches(segment: Segment, bbox: BBox) -> bool:
    """Boundary-inclusive segment/rectangle intersection (Liang-Barsky clip)."""

    x0, y0, x1, y1 = segment
    bx0, by0, bx1, by1 = bbox
    dx, dy = x1 - x0, y1 - y0
    t_min, t_max = 0.0, 1.0
    for p, q in ((-dx, x0 - bx0), (dx, bx1 - x0), (-dy, y0 - by0), (dy, by1 - y0)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        t = q / p
        if p < 0.0:
            if t > t_max:
                return False
            t_min = max(t_min, t)
        else:
            if t < t_min:
                return False
            t_max = min(t_max, t)
    return True


def _contained(segments: Sequence[Segment], bbox: BBox) -> bool:
    return all(
        _inside((x0, y0), bbox) and _inside((x1, y1), bbox) for x0, y0, x1, y1 in segments
    )


def _touched(segments: Sequence[Segment], bbox: BBox) -> bool:
    return any(_segment_touches(segment, bbox) for segment in segments)


def _contesting_boxes(
    rows: Sequence[SegmentedViewport],
    eligible_ids: frozenset[str],
    authenticated: Sequence[AuthenticatedViewportRecord],
) -> tuple[tuple[BBox, ...], bool]:
    """Source-drawn contest rectangles, plus whether other views lack localised frame proof."""

    boxes: list[BBox] = []
    unlocalised = False
    for viewport in rows:
        if str(viewport.view_id) in eligible_ids:
            continue
        localised: list[BBox] = []
        # A derived TITLE_PARTITION bbox is a synthetic ownership cell, not
        # source-drawn viewport geometry. It may remain unauthenticated evidence,
        # but it cannot independently contest positive ownership established by
        # an authenticated drawn frame. Only a source-owned VECTOR_FRAME may
        # contribute its own bbox as contest geometry.
        own = (
            _finite_bbox(viewport.bounding_box)
            if (
                viewport.bounding_box is not None
                and str(viewport.boundary_source)
                == ViewportBoundarySource.VECTOR_FRAME.value
            )
            else None
        )
        if own is not None:
            localised.append(own)
        provenance = getattr(viewport, "provenance", None) or {}
        for frame in provenance.get("candidate_frames") or ():
            parsed = _finite_bbox(frame)
            if parsed is not None:
                localised.append(parsed)
        if not localised:
            unlocalised = True
            continue
        for box in localised:
            # The outer frame listed among an ambiguous view's candidates is an
            # authenticated view already; it is not a contest against itself.
            if any(_same_bbox(box, item.bounding_box) for item in authenticated):
                continue
            boxes.append(box)
    return tuple(boxes), unlocalised


def _candidate_scope(
    segments: Sequence[Segment],
    viewports: Sequence[AuthenticatedViewportRecord],
    contesting: Sequence[BBox] = (),
    *,
    unlocalised_unauthenticated: bool = False,
) -> tuple[str, Optional[AuthenticatedViewportRecord]]:
    if not segments or not all(
        math.isfinite(value) for segment in segments for value in segment
    ):
        return SUPPORT_GEOMETRY_UNREADABLE, None
    if not viewports:
        return NO_AUTHENTICATED_VIEWPORT, None
    containing = [item for item in viewports if _contained(segments, item.bounding_box)]
    contested = any(_touched(segments, box) for box in contesting)
    if len(containing) == 1 and not contested:
        viewport = containing[0]
        if viewport.view_type == FLOOR_PLAN_VIEW_TYPE:
            return IN_AUTHENTICATED_FLOOR_PLAN, viewport
        if (
            viewport.view_type in TYPED_NEGATIVE_VIEW_TYPES
            and viewport.boundary_source == ViewportBoundarySource.VECTOR_FRAME.value
        ):
            return IN_AUTHENTICATED_NON_PLAN, viewport
        return IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN, viewport
    if containing:
        return AMBIGUOUS_AUTHENTICATED_OWNERSHIP, None
    if contested or any(_touched(segments, item.bounding_box) for item in viewports):
        return AMBIGUOUS_AUTHENTICATED_OWNERSHIP, None
    if unlocalised_unauthenticated:
        return NO_AUTHENTICATED_VIEWPORT, None
    return OUTSIDE_AUTHENTICATED_VIEWPORTS, None


def _evidence_direction(scope: str) -> str:
    if scope == IN_AUTHENTICATED_FLOOR_PLAN:
        return EVIDENCE_DIRECTION_SCOPE_ONLY
    if scope == IN_AUTHENTICATED_NON_PLAN:
        return EVIDENCE_DIRECTION_AGAINST_PROMOTION
    return EVIDENCE_DIRECTION_NONE


def _producer_source_bytes(
    source_visibility_producer: SourceVisibilityProducer,
    *,
    revision_id: str,
    source_sha256: str,
) -> Optional[bytes]:
    store = getattr(getattr(source_visibility_producer, "_producer", None), "_store", None)
    by_revision = getattr(store, "source_bytes_by_revision", None) or {}
    payload = by_revision.get(revision_id)
    if payload is None:
        return None
    payload = bytes(payload)
    if hashlib.sha256(payload).hexdigest() != source_sha256:
        return None
    return payload


def _counts(scopes: Sequence[OpeningCandidateViewportScope], *, corroborated_only: bool) -> Mapping[str, int]:
    counts = {scope: 0 for scope in _SCOPES}
    for item in scopes:
        if corroborated_only and not item.existence_corroborated:
            continue
        counts[item.scope] += 1
    return MappingProxyType(counts)


def _reason_codes_of(results: Sequence[object]) -> tuple[str, ...]:
    return tuple(
        sorted({str(code) for result in results for code in getattr(result, "reason_codes", ())})
    )


def assess_opening_candidate_viewport_scope(
    *,
    source_visibility_producer: SourceVisibilityProducer,
    revision_id: str,
    page_id: str,
) -> OpeningViewportScopeShadowReport:
    """Classify every G17 candidate on one page by authenticated view ownership."""

    if type(source_visibility_producer) is not SourceVisibilityProducer:
        raise TypeError("source_visibility_producer must be an actual SourceVisibilityProducer")
    page_id = str(page_id).strip()
    published = source_visibility_producer.published_snapshot_for_revision(str(revision_id))

    def report(
        *,
        status: EvidenceResolutionStatus,
        reasons: tuple[str, ...],
        viewports: tuple[AuthenticatedViewportRecord, ...] = (),
        unauthenticated: int = 0,
        scopes: tuple[OpeningCandidateViewportScope, ...] = (),
    ) -> OpeningViewportScopeShadowReport:
        document_id = published.revision.document_id if published else ""
        revision = published.revision.revision_id if published else str(revision_id)
        source_sha256 = published.revision.source_sha256 if published else ""
        snapshot_id = published.snapshot.snapshot_id if published else ""
        payload = {
            "schema_version": OPENING_VIEWPORT_SCOPE_SHADOW_SCHEMA_VERSION,
            "document_id": document_id,
            "revision_id": revision,
            "source_sha256": source_sha256,
            "snapshot_id": snapshot_id,
            "page_id": page_id,
            "status": status.value,
            "reason_codes": reasons,
            "authenticated_viewports": [
                (item.view_id, item.view_type, item.status, item.boundary_source, item.bounding_box)
                for item in viewports
            ],
            "candidate_scopes": [
                (item.candidate_id, item.scope, item.view_id, item.evidence_direction)
                for item in scopes
            ],
        }
        return OpeningViewportScopeShadowReport(
            record_id=stable_contract_id("opening_viewport_scope_shadow", payload, digest_chars=32),
            status=status,
            reason_codes=reasons,
            document_id=document_id,
            revision_id=revision,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            page_id=page_id,
            authenticated_viewports=viewports,
            unauthenticated_viewport_count=unauthenticated,
            candidate_scopes=scopes,
            scope_counts=_counts(scopes, corroborated_only=False),
            corroborated_scope_counts=_counts(scopes, corroborated_only=True),
        )

    if published is None:
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,),
        )

    payload = _producer_source_bytes(
        source_visibility_producer,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
    )
    if payload is None:
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,),
        )

    visibility = source_visibility_producer.authority()
    seed_selector: Optional[ObservationSelector] = None
    unresolved_seed_results = []
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        resolved = visibility.resolve_visible(selector)
        if (
            resolved.status is EvidenceResolutionStatus.CORROBORATED
            and resolved.observation is not None
        ):
            if str(resolved.observation.page_id) == page_id:
                seed_selector = selector
                break
        else:
            unresolved_seed_results.append(resolved)
    if seed_selector is None:
        # Type the failure like the live authority instead of calling a stale or
        # corrupted revision "no visible segments".
        codes = _reason_codes_of(unresolved_seed_results)
        if any(result.status is EvidenceResolutionStatus.CONFLICT for result in unresolved_seed_results):
            return report(
                status=EvidenceResolutionStatus.CONFLICT,
                reasons=(OPENING_VIEWPORT_SCOPE_SNAPSHOT_INTEGRITY_FAILED,) + codes,
            )
        if STALE_REVISION in codes:
            return report(
                status=EvidenceResolutionStatus.ABSTAINED,
                reasons=(OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE, STALE_REVISION),
            )
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS,),
        )

    try:
        document = fitz.open(stream=payload, filetype="pdf")
        try:
            gate = _authenticated_viewports(
                document.load_page(int(page_id) - 1),
                page_number=int(page_id),
            )
        finally:
            document.close()
    except Exception:
        gate = None
    if gate is None:
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED,),
        )
    rows, eligible = gate

    authenticated = tuple(
        AuthenticatedViewportRecord(
            view_id=str(viewport.view_id),
            view_type=str(viewport.view_type),
            status=str(viewport.status),
            boundary_source=str(viewport.boundary_source),
            bounding_box=box,
        )
        for viewport in eligible
        for box in (_finite_bbox(viewport.bounding_box),)
        if box is not None
    )
    authenticated_ids = frozenset(item.view_id for item in authenticated)
    unauthenticated = sum(1 for viewport in rows if str(viewport.view_id) not in authenticated_ids)
    contesting, unlocalised = _contesting_boxes(rows, authenticated_ids, authenticated)

    physical = PhysicalOpeningAuthority(visibility)
    seed_result = visibility.resolve_visible(seed_selector)
    records, failures = physical._visible_snapshot_records(seed_result)
    if failures or seed_result.observation is None:
        integrity = any(
            getattr(result, "status", None) is EvidenceResolutionStatus.CONFLICT
            for result in failures
        )
        return report(
            status=(
                EvidenceResolutionStatus.CONFLICT if integrity else EvidenceResolutionStatus.ABSTAINED
            ),
            reasons=(
                (OPENING_VIEWPORT_SCOPE_SNAPSHOT_INTEGRITY_FAILED,) + _reason_codes_of(failures)
                if integrity
                else (OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,)
            ),
            viewports=authenticated,
            unauthenticated=unauthenticated,
        )
    candidates: tuple[CandidateSemanticOpening, ...] = physical._visible_candidates_for(
        seed_result.observation, records
    )
    by_id = {record.observation_id: record for record in records}

    containment: dict[str, int] = {}
    for candidate in candidates:
        for observation_id in candidate.source_observation_ids:
            containment[observation_id] = containment.get(observation_id, 0) + 1

    scopes: list[OpeningCandidateViewportScope] = []
    for candidate in sorted(candidates, key=lambda item: item.candidate_id):
        segments: list[Segment] = []
        readable = True
        for observation_id in candidate.source_observation_ids:
            record = by_id.get(observation_id)
            line = None if record is None else _line_geometry(record)
            if line is None:
                readable = False
                break
            segments.append((float(line[0]), float(line[1]), float(line[2]), float(line[3])))
        if readable:
            scope, viewport = _candidate_scope(
                segments,
                authenticated,
                contesting,
                unlocalised_unauthenticated=unlocalised,
            )
        else:
            scope, viewport = SUPPORT_GEOMETRY_UNREADABLE, None
        # Same proposition prove_existence() uses: an observation contained in
        # exactly one candidate lets that candidate's existence be corroborated.
        corroborated = any(
            containment.get(observation_id) == 1
            for observation_id in candidate.source_observation_ids
        )
        scopes.append(
            OpeningCandidateViewportScope(
                candidate_id=candidate.candidate_id,
                structural_pattern=candidate.structural_pattern,
                scope=scope,
                view_id=None if viewport is None else viewport.view_id,
                view_type=None if viewport is None else viewport.view_type,
                existence_corroborated=corroborated,
                source_observation_ids=tuple(candidate.source_observation_ids),
                boundary_source=None if viewport is None else viewport.boundary_source,
                evidence_direction=_evidence_direction(scope),
            )
        )

    return report(
        status=EvidenceResolutionStatus.CORROBORATED,
        reasons=(OPENING_VIEWPORT_SCOPE_ASSESSED,),
        viewports=authenticated,
        unauthenticated=unauthenticated,
        scopes=tuple(scopes),
    )


__all__ = [
    "AMBIGUOUS_AUTHENTICATED_OWNERSHIP",
    "AuthenticatedViewportRecord",
    "EVIDENCE_DIRECTION_AGAINST_PROMOTION",
    "EVIDENCE_DIRECTION_NONE",
    "EVIDENCE_DIRECTION_SCOPE_ONLY",
    "IN_AUTHENTICATED_FLOOR_PLAN",
    "IN_AUTHENTICATED_NON_PLAN",
    "IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN",
    "NO_AUTHENTICATED_VIEWPORT",
    "OPENING_VIEWPORT_SCOPE_ASSESSED",
    "OPENING_VIEWPORT_SCOPE_SHADOW_SCHEMA_VERSION",
    "OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED",
    "OPENING_VIEWPORT_SCOPE_SNAPSHOT_INTEGRITY_FAILED",
    "OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE",
    "OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS",
    "OUTSIDE_AUTHENTICATED_VIEWPORTS",
    "OpeningCandidateViewportScope",
    "OpeningViewportScopeShadowReport",
    "SUPPORT_GEOMETRY_UNREADABLE",
    "TYPED_NEGATIVE_VIEW_TYPES",
    "assess_opening_candidate_viewport_scope",
]
