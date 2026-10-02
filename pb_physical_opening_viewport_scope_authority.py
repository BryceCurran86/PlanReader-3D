"""Authenticated viewport ownership for physical-opening candidate promotion.

This authority is deliberately narrow. It does not create opening candidates,
host walls, dimensions, quantities, or commercial rows. It classifies
producer-owned physical-opening candidates against producer-authenticated
viewport geometry so that page-wide source geometry cannot self-promote
elevation/detail/schedule linework as a floor-plan opening.

Only a candidate wholly owned by exactly one authenticated FLOOR_PLAN viewport,
with no source-drawn competing viewport touching its support geometry, is
eligible for downstream physical-opening existence promotion. Every other
state fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import _authenticated_viewports
from pb_viewport_segmentation import SegmentedViewport, ViewportBoundarySource


IN_AUTHENTICATED_FLOOR_PLAN = "in_authenticated_floor_plan_viewport"
IN_AUTHENTICATED_NON_PLAN = "in_authenticated_non_plan_viewport"
IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN = "in_authenticated_view_of_unproven_type"
OUTSIDE_AUTHENTICATED_VIEWPORTS = "outside_authenticated_viewports"
AMBIGUOUS_AUTHENTICATED_OWNERSHIP = "ambiguous_authenticated_viewport_ownership"
SUPPORT_GEOMETRY_UNREADABLE = "support_geometry_unreadable"
NO_AUTHENTICATED_VIEWPORT = "no_authenticated_viewport"

OPENING_VIEWPORT_SCOPE_RESOLVED = "opening_viewport_scope_resolved"
OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE = "opening_viewport_scope_source_unavailable"
OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED = "opening_viewport_scope_segmentation_failed"
OPENING_VIEWPORT_SCOPE_SNAPSHOT_MISMATCH = "opening_viewport_scope_snapshot_mismatch"

FLOOR_PLAN_VIEW_TYPE = DrawingViewType.FLOOR_PLAN.value
TYPED_NON_PLAN_VIEW_TYPES = frozenset(
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
class OpeningCandidateViewportDecision:
    candidate_id: str
    scope: str
    viewport_id: Optional[str]
    view_type: Optional[str]
    boundary_source: Optional[str]
    source_observation_ids: tuple[str, ...]
    promotable: bool
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class OpeningViewportScopeAuthorityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    decisions: Mapping[str, OpeningCandidateViewportDecision]
    authenticated_viewports: tuple[AuthenticatedViewportRecord, ...]


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
        _inside((x0, y0), bbox) and _inside((x1, y1), bbox)
        for x0, y0, x1, y1 in segments
    )


def _touched(segments: Sequence[Segment], bbox: BBox) -> bool:
    return any(_segment_touches(segment, bbox) for segment in segments)


def _line_geometry(record: object) -> Optional[Segment]:
    geometry = tuple(getattr(record, "geometry", ()) or ())
    if len(geometry) != 4:
        return None
    try:
        values = tuple(float(value) for value in geometry)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in values):
        return None
    x1, y1, x2, y2 = values
    if math.hypot(x2 - x1, y2 - y1) <= 1e-6:
        return None
    return (x1, y1, x2, y2)


def _contesting_boxes(
    rows: Sequence[SegmentedViewport],
    authenticated_ids: frozenset[str],
    authenticated: Sequence[AuthenticatedViewportRecord],
) -> tuple[tuple[BBox, ...], bool]:
    boxes: list[BBox] = []
    unlocalised = False
    for viewport in rows:
        if str(viewport.view_id) in authenticated_ids:
            continue
        localised: list[BBox] = []
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
            if any(_same_bbox(box, item.bounding_box) for item in authenticated):
                continue
            boxes.append(box)
    return tuple(boxes), unlocalised


def _candidate_scope(
    segments: Sequence[Segment],
    viewports: Sequence[AuthenticatedViewportRecord],
    contesting: Sequence[BBox],
    *,
    unlocalised_unauthenticated: bool,
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
            viewport.view_type in TYPED_NON_PLAN_VIEW_TYPES
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


def _producer_source_bytes(source_visibility_producer, revision_id: str, source_sha256: str) -> Optional[bytes]:
    store = getattr(getattr(source_visibility_producer, "_producer", None), "_store", None)
    by_revision = getattr(store, "source_bytes_by_revision", None) or {}
    payload = by_revision.get(str(revision_id))
    if payload is None:
        return None
    payload = bytes(payload)
    if hashlib.sha256(payload).hexdigest() != str(source_sha256):
        return None
    return payload


def classify_opening_candidate_viewport_scopes(
    *,
    source_visibility_producer,
    revision_id: str,
    page_id: str,
    snapshot_id: str,
    candidates: Sequence[object],
    records: Sequence[object],
) -> OpeningViewportScopeAuthorityResult:
    """Classify already-produced candidates by authenticated viewport ownership.

    Caller candidate lists cannot create authority: every candidate must already
    be producer-owned physical-opening evidence, and the source bytes plus
    viewport gate are re-read from the producer's immutable revision.
    """

    published = source_visibility_producer.published_snapshot_for_revision(str(revision_id))
    if published is None:
        return OpeningViewportScopeAuthorityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,),
            decisions=MappingProxyType({}),
            authenticated_viewports=(),
        )
    if (
        str(published.snapshot.snapshot_id) != str(snapshot_id)
        or str(published.revision.revision_id) != str(revision_id)
    ):
        return OpeningViewportScopeAuthorityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(OPENING_VIEWPORT_SCOPE_SNAPSHOT_MISMATCH,),
            decisions=MappingProxyType({}),
            authenticated_viewports=(),
        )

    payload = _producer_source_bytes(
        source_visibility_producer,
        revision_id=str(revision_id),
        source_sha256=str(published.revision.source_sha256),
    )
    if payload is None:
        return OpeningViewportScopeAuthorityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,),
            decisions=MappingProxyType({}),
            authenticated_viewports=(),
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
        return OpeningViewportScopeAuthorityResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED,),
            decisions=MappingProxyType({}),
            authenticated_viewports=(),
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
    contesting, unlocalised = _contesting_boxes(rows, authenticated_ids, authenticated)
    by_id = {
        str(getattr(record, "observation_id", "")): record
        for record in records
        if str(getattr(record, "observation_id", ""))
    }

    decisions: dict[str, OpeningCandidateViewportDecision] = {}
    for candidate in candidates:
        candidate_id = str(getattr(candidate, "candidate_id", ""))
        source_ids = tuple(str(value) for value in getattr(candidate, "source_observation_ids", ()) or ())
        segments: list[Segment] = []
        readable = bool(source_ids)
        for observation_id in source_ids:
            record = by_id.get(observation_id)
            line = None if record is None else _line_geometry(record)
            if line is None:
                readable = False
                break
            segments.append(line)
        if readable:
            scope, viewport = _candidate_scope(
                segments,
                authenticated,
                contesting,
                unlocalised_unauthenticated=unlocalised,
            )
        else:
            scope, viewport = SUPPORT_GEOMETRY_UNREADABLE, None

        promotable = scope == IN_AUTHENTICATED_FLOOR_PLAN and viewport is not None
        reason_codes = (
            OPENING_VIEWPORT_SCOPE_RESOLVED,
            scope,
        )
        decisions[candidate_id] = OpeningCandidateViewportDecision(
            candidate_id=candidate_id,
            scope=scope,
            viewport_id=None if viewport is None else viewport.view_id,
            view_type=None if viewport is None else viewport.view_type,
            boundary_source=None if viewport is None else viewport.boundary_source,
            source_observation_ids=source_ids,
            promotable=promotable,
            reason_codes=reason_codes,
        )

    return OpeningViewportScopeAuthorityResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(OPENING_VIEWPORT_SCOPE_RESOLVED,),
        decisions=MappingProxyType(decisions),
        authenticated_viewports=authenticated,
    )


__all__ = [
    "AMBIGUOUS_AUTHENTICATED_OWNERSHIP",
    "AuthenticatedViewportRecord",
    "IN_AUTHENTICATED_FLOOR_PLAN",
    "IN_AUTHENTICATED_NON_PLAN",
    "IN_AUTHENTICATED_VIEW_TYPE_UNPROVEN",
    "NO_AUTHENTICATED_VIEWPORT",
    "OPENING_VIEWPORT_SCOPE_RESOLVED",
    "OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED",
    "OPENING_VIEWPORT_SCOPE_SNAPSHOT_MISMATCH",
    "OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE",
    "OUTSIDE_AUTHENTICATED_VIEWPORTS",
    "OpeningCandidateViewportDecision",
    "OpeningViewportScopeAuthorityResult",
    "SUPPORT_GEOMETRY_UNREADABLE",
    "classify_opening_candidate_viewport_scopes",
]
