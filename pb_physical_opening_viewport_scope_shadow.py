"""SHADOW: authenticated floor-plan viewport scope for G17 opening candidates.

G17 (``PhysicalOpeningAuthority``) discovers ``jamb_bounded_two_face_interruption``
candidates page-wide (``viewport_id`` is always ``None``). On multi-view sheets
that admits elevation window-pane grids, section linework, roof-sheet patterns
and legend/title geometry as "physical openings". This module measures, without
changing any live output, where every G17 candidate on a page falls relative to
the page's *authenticated* views:

- an authenticated view is a ``segment_page_viewports`` viewport that is either
  ``RESOLVED`` (a vector frame) or an authoritative ``DERIVED`` partition
  (``is_authoritative_derived_viewport``). Ordinary title partitions stay
  diagnostic evidence and never scope anything here;
- a candidate is in an authenticated view only when every endpoint of every
  support segment lies inside exactly one authenticated view.

Scopes:

``in_authenticated_floor_plan_viewport``
    the only scope in which a later promotion could let G17 existence stand.
``in_authenticated_non_plan_viewport``
    positive typed-negative evidence: the candidate is drawn inside an
    authenticated elevation / section / roof plan / legend / schedule / detail
    view, so it is not a floor-plan physical opening.
``outside_authenticated_viewports``
    the page has authenticated views but the candidate is in none of them
    (title block, notes, unframed linework): out of every authenticated scope.
``ambiguous_authenticated_viewport_ownership``
    the support straddles a view boundary or lies in overlapping views.
``no_authenticated_viewport``
    the page has no authenticated view at all, so the source cannot prove the
    candidate is plan geometry. This abstains; it is never a negative proof.

This is observation only. It does not mutate G17 records, does not change
existence, closure, enumeration, host binding, voids, walls or publication, and
it reads source bytes only from the producer's own content-addressed store.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    CandidateSemanticOpening,
    PhysicalOpeningAuthority,
    _line_geometry,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
)


OPENING_VIEWPORT_SCOPE_SHADOW_SCHEMA_VERSION = "1.0.0"

IN_AUTHENTICATED_FLOOR_PLAN = "in_authenticated_floor_plan_viewport"
IN_AUTHENTICATED_NON_PLAN = "in_authenticated_non_plan_viewport"
OUTSIDE_AUTHENTICATED_VIEWPORTS = "outside_authenticated_viewports"
AMBIGUOUS_AUTHENTICATED_OWNERSHIP = "ambiguous_authenticated_viewport_ownership"
NO_AUTHENTICATED_VIEWPORT = "no_authenticated_viewport"

OPENING_VIEWPORT_SCOPE_ASSESSED = "opening_viewport_scope_assessed"
OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE = "opening_viewport_scope_source_unavailable"
OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED = "opening_viewport_scope_segmentation_failed"
OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS = "opening_viewport_scope_no_visible_segments"

FLOOR_PLAN_VIEW_TYPE = "floor_plan"

_SCOPES = (
    IN_AUTHENTICATED_FLOOR_PLAN,
    IN_AUTHENTICATED_NON_PLAN,
    OUTSIDE_AUTHENTICATED_VIEWPORTS,
    AMBIGUOUS_AUTHENTICATED_OWNERSHIP,
    NO_AUTHENTICATED_VIEWPORT,
)


@dataclass(frozen=True)
class AuthenticatedViewportRecord:
    view_id: str
    view_type: str
    status: str
    boundary_source: str
    bounding_box: tuple[float, float, float, float]


@dataclass(frozen=True)
class OpeningCandidateViewportScope:
    candidate_id: str
    structural_pattern: str
    scope: str
    view_id: Optional[str]
    view_type: Optional[str]
    existence_corroborated: bool
    source_observation_ids: tuple[str, ...]


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


def _is_authenticated(viewport: SegmentedViewport) -> bool:
    if viewport.bounding_box is None:
        return False
    if viewport.status == ViewportSegmentationStatus.RESOLVED.value:
        return True
    return is_authoritative_derived_viewport(viewport)


def _inside(point: tuple[float, float], bbox: Sequence[float]) -> bool:
    x0, y0, x1, y1 = (float(value) for value in bbox)
    return x0 <= point[0] <= x1 and y0 <= point[1] <= y1


def _candidate_scope(
    points: Sequence[tuple[float, float]],
    viewports: Sequence[AuthenticatedViewportRecord],
) -> tuple[str, Optional[AuthenticatedViewportRecord]]:
    if not viewports:
        return NO_AUTHENTICATED_VIEWPORT, None
    containing = [
        viewport
        for viewport in viewports
        if all(_inside(point, viewport.bounding_box) for point in points)
    ]
    if len(containing) == 1:
        viewport = containing[0]
        if viewport.view_type == FLOOR_PLAN_VIEW_TYPE:
            return IN_AUTHENTICATED_FLOOR_PLAN, viewport
        return IN_AUTHENTICATED_NON_PLAN, viewport
    if len(containing) > 1:
        return AMBIGUOUS_AUTHENTICATED_OWNERSHIP, None
    touched = [
        viewport
        for viewport in viewports
        if any(_inside(point, viewport.bounding_box) for point in points)
    ]
    if touched:
        return AMBIGUOUS_AUTHENTICATED_OWNERSHIP, None
    return OUTSIDE_AUTHENTICATED_VIEWPORTS, None


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
                (item.view_id, item.view_type, item.status, item.bounding_box)
                for item in viewports
            ],
            "candidate_scopes": [
                (item.candidate_id, item.scope, item.view_id) for item in scopes
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
            and str(resolved.observation.page_id) == page_id
        ):
            seed_selector = selector
            break
    if seed_selector is None:
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS,),
        )

    try:
        document = fitz.open(stream=payload, filetype="pdf")
        try:
            segmented = segment_page_viewports(
                document.load_page(int(page_id) - 1),
                page_number=int(page_id),
            )
        finally:
            document.close()
    except Exception:
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED,),
        )

    authenticated = tuple(
        AuthenticatedViewportRecord(
            view_id=str(viewport.view_id),
            view_type=str(viewport.view_type),
            status=str(viewport.status),
            boundary_source=str(viewport.boundary_source),
            bounding_box=tuple(float(value) for value in viewport.bounding_box),  # type: ignore[arg-type]
        )
        for viewport in segmented
        if _is_authenticated(viewport)
    )
    unauthenticated = sum(1 for viewport in segmented if not _is_authenticated(viewport))

    physical = PhysicalOpeningAuthority(visibility)
    seed_result = visibility.resolve_visible(seed_selector)
    records, failures = physical._visible_snapshot_records(seed_result)
    if failures or seed_result.observation is None:
        return report(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=(OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE,),
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
        points: list[tuple[float, float]] = []
        for observation_id in candidate.source_observation_ids:
            line = _line_geometry(by_id[observation_id])
            if line is None:
                continue
            points.extend(((line[0], line[1]), (line[2], line[3])))
        scope, viewport = _candidate_scope(points, authenticated)
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
    "IN_AUTHENTICATED_FLOOR_PLAN",
    "IN_AUTHENTICATED_NON_PLAN",
    "NO_AUTHENTICATED_VIEWPORT",
    "OPENING_VIEWPORT_SCOPE_ASSESSED",
    "OPENING_VIEWPORT_SCOPE_SHADOW_SCHEMA_VERSION",
    "OPENING_VIEWPORT_SCOPE_SEGMENTATION_FAILED",
    "OPENING_VIEWPORT_SCOPE_SOURCE_UNAVAILABLE",
    "OPENING_VIEWPORT_SCOPE_NO_VISIBLE_SEGMENTS",
    "OUTSIDE_AUTHENTICATED_VIEWPORTS",
    "OpeningCandidateViewportScope",
    "OpeningViewportScopeShadowReport",
    "assess_opening_candidate_viewport_scope",
]
