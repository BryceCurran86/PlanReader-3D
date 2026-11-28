"""Report only (#4764 7211359981, geometry task C01): does a floor-plan view own each opening-to-wall binding?

For every corroborated opening host binding of a live wall/opening composition this asks whether the opening's whole source
support AND every member wall lie inside one and the same floor-plan view, using the repository's existing viewport builder:
once for authenticated floor-plan viewports and once for the stricter source-owned proven plan views. Ownership is
CORROBORATED only for exactly one view; none abstains and two or more conflict, each with a typed reason. A binding is owned
when either builder owns it and neither conflicts. The report changes nothing. The composition imports
``published_hosts_without_plan_view_owner`` only when its default-off ``require_plan_view_host_ownership_shadow`` is set,
and then it can only withhold a host.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Iterable, Mapping, Optional, Sequence

from pb_drawing_evidence_binding import DrawingViewType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_host_binding_authority import _COORD_TOL
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateSelector,
    _build_authenticated_viewport_scope_results,
    _decision_scope_id,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

PLAN_VIEW_TYPES = (DrawingViewType.FLOOR_PLAN.value, DrawingViewType.FLOOR_FINISH_PLAN.value)

OWNED = "opening_host_plan_view_owned"
UNPROVEN = "opening_host_plan_view_ownership_unproven"
NO_PLAN_VIEW = "opening_host_page_has_no_plan_view"
OUTSIDE = "opening_host_outside_plan_view"
SPLIT = "opening_host_crosses_plan_view_boundary"
AMBIGUOUS = "opening_host_multiple_plan_view_owners"
UNAVAILABLE = "opening_host_geometry_unavailable"

Point = tuple[float, float]
View = tuple[str, tuple[float, float, float, float]]


@dataclass(frozen=True)
class PlanViewOwnership:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    view_id: Optional[str] = None


def _finite(points: Sequence[Point]) -> bool:
    return bool(points) and all(len(p) == 2 and math.isfinite(p[0]) and math.isfinite(p[1]) for p in points)


def _inside(point: Point, box: Sequence[float]) -> bool:
    x0, y0, x1, y1 = box
    return x0 - _COORD_TOL <= point[0] <= x1 + _COORD_TOL and y0 - _COORD_TOL <= point[1] <= y1 + _COORD_TOL


def plan_view_ownership(opening_points: Sequence[Point], member_points: Sequence[Sequence[Point]],
                        views: Iterable[View]) -> PlanViewOwnership:
    """One view must contain every opening point and every point of every member wall (a box is convex)."""
    if not _finite(opening_points) or not member_points or not all(_finite(member) for member in member_points):
        return PlanViewOwnership(EvidenceResolutionStatus.ABSTAINED, (UNPROVEN, UNAVAILABLE))
    boxes = sorted({(str(view_id), tuple(float(v) for v in box)) for view_id, box in views
                    if box is not None and len(box) == 4 and box[2] > box[0] and box[3] > box[1]})
    if not boxes:
        return PlanViewOwnership(EvidenceResolutionStatus.ABSTAINED, (UNPROVEN, NO_PLAN_VIEW))
    points = [*opening_points, *(point for member in member_points for point in member)]
    owners = [view_id for view_id, box in boxes if all(_inside(point, box) for point in points)]
    if len(owners) == 1:
        return PlanViewOwnership(EvidenceResolutionStatus.CORROBORATED, (OWNED,), owners[0])
    if owners:
        return PlanViewOwnership(EvidenceResolutionStatus.CONFLICT, (UNPROVEN, AMBIGUOUS))
    touching = any(_inside(point, box) for _view_id, box in boxes for point in points)
    return PlanViewOwnership(EvidenceResolutionStatus.ABSTAINED, (UNPROVEN, SPLIT if touching else OUTSIDE))


def combine_ownership(authenticated: PlanViewOwnership, proven: PlanViewOwnership) -> PlanViewOwnership:
    """Either view builder may own a binding; a conflict in either stays a conflict."""
    for result in (authenticated, proven):
        if result.status is EvidenceResolutionStatus.CONFLICT:
            return result
    for result in (authenticated, proven):
        if result.status is EvidenceResolutionStatus.CORROBORATED:
            return result
    return proven if authenticated.reason_codes[-1] == NO_PLAN_VIEW else authenticated


def _pairs(values: Sequence[float]) -> list[Point]:
    if len(values) < 2 or len(values) % 2:
        return []
    return [(float(values[i]), float(values[i + 1])) for i in range(0, len(values), 2)]


def _opening_points(opening_authority, selector: ObservationSelector, *, identity: str, page_id: str) -> list[Point]:
    """Every point of the opening's own source support, from the producer; empty when any part is unavailable."""
    record = opening_authority.prove_existence(selector).existence_record
    if record is None or record.record_id != identity or record.page_id != page_id:
        return []
    if record.aperture_bbox_pt is not None:
        x0, y0, x1, y1 = record.aperture_bbox_pt
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    visibility = opening_authority.source_visibility_authority()
    points: list[Point] = []
    for observation_id in record.source_observation_ids:
        seen = visibility.resolve_visible(replace(selector, observation_id=observation_id)).observation
        pairs = _pairs(seen.geometry) if seen is not None else []
        if not pairs:
            return []
        points.extend(pairs)
    return points


def _wall_points(authorities, published, page_id: str) -> dict[str, list[Point]]:
    """Every wall candidate the composition's own authorities hold for this page; disagreeing geometry is dropped."""
    identity = dict(document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
                    page_id=page_id)
    seen: dict[str, set[tuple]] = {}
    for authority in authorities:
        if authority is None:
            continue
        selectors = (PhysicalWallCandidateSelector(**identity, decision_scope_id=_decision_scope_id(page_id)),
                     *authority.selectors_for_authenticated_viewports(**identity))
        for selector in selectors:
            for record in authority.resolve_scope(selector).records:
                wall = record.wall_candidate
                geometry = tuple(wall.centerline_pts) + tuple(wall.curve_control_pts or ())
                seen.setdefault(record.wall_candidate_id, set()).add(geometry)
    return {wall_id: [(float(x), float(y)) for x, y in next(iter(values))]
            for wall_id, values in seen.items() if len(values) == 1}


def _plan_views(source_producer, published, source_bytes: bytes, page_id: str, *, proven: bool) -> list[View]:
    scopes = _build_authenticated_viewport_scope_results(
        source_producer=source_producer, published=published, source_bytes=source_bytes, page_id=page_id,
        physical_plan_view_shadow=proven)
    return [(scope.viewport_id, scope.viewport_bbox) for scope in scopes
            if scope.viewport_view_type in PLAN_VIEW_TYPES and scope.viewport_bbox is not None]


class _PageViews:
    """Both view builders' floor-plan boxes and the page's wall geometry, from one source snapshot."""

    def __init__(self, source_producer, published, source_bytes: bytes, page_id: str, wall_authorities):
        self.views = {name: _plan_views(source_producer, published, source_bytes, page_id, proven=name == "proven")
                      for name in ("authenticated", "proven")}
        self.walls = _wall_points(wall_authorities, published, page_id)

    def ownership(self, opening: Sequence[Point], member_ids: Sequence[str]) -> dict[str, PlanViewOwnership]:
        members = [self.walls.get(wall_id, []) for wall_id in member_ids]
        owners = {name: plan_view_ownership(opening, members, boxes) for name, boxes in self.views.items()}
        owners["combined"] = combine_ownership(owners["authenticated"], owners["proven"])
        return owners


def _published(source_producer: SourceVisibilityProducer, revision_id: str):
    if type(source_producer) is not SourceVisibilityProducer:
        raise TypeError("source_producer must be producer-owned")
    published = source_producer.published_snapshot_for_revision(revision_id)
    if published is None:
        raise RuntimeError("source snapshot unavailable")
    return published, source_producer._producer._store.source_bytes_by_revision[revision_id]


def published_hosts_without_plan_view_owner(*, source_producer: SourceVisibilityProducer, revision_id: str,
                                            binding_results: Mapping, opening_authority, opening_selectors: Mapping,
                                            wall_authorities) -> dict[str, tuple[str, ...]]:
    """Opening identity -> reasons, for every published host record that no floor-plan view owns."""
    published, source_bytes = _published(source_producer, revision_id)
    pages: dict[str, _PageViews] = {}
    withheld: dict[str, tuple[str, ...]] = {}
    for key, result in binding_results.items():
        record = result.record
        if record is None:
            continue
        page_id, identity = key[4], key[-1]
        if page_id not in pages:
            pages[page_id] = _PageViews(source_producer, published, source_bytes, page_id, wall_authorities)
        selector = opening_selectors.get(identity)
        opening = ([] if selector is None else
                   _opening_points(opening_authority, selector, identity=identity, page_id=page_id))
        combined = pages[page_id].ownership(opening, record.member_wall_candidate_ids)["combined"]
        if combined.status is not EvidenceResolutionStatus.CORROBORATED:
            withheld[identity] = combined.reason_codes
    return withheld


def _route(reason_codes: Sequence[str]) -> str:
    return next((code for code in reversed(reason_codes) if code.endswith("host_resolved")), "host_band")


def opening_host_plan_view_report(composition, source_producer: SourceVisibilityProducer) -> dict:
    """Ownership of every corroborated host binding, per topology page; the composition is only read."""
    published, source_bytes = _published(source_producer, composition.revision_id)
    pages = []
    for page_id in composition.page_ids:
        traces = sorted((t for t in composition.opening_bindings if t.page_id == page_id),
                        key=lambda t: (str(t.opening_identity_id), t.representative_observation_id))
        bound = [t for t in traces
                 if t.status is EvidenceResolutionStatus.CORROBORATED and t.host_wall_id and t.opening_identity_id]
        context = _PageViews(source_producer, published, source_bytes, page_id,
                             (composition.physical_wall_candidate_authority,
                              composition.supplemental_physical_wall_candidate_authority))
        rows = []
        for trace in bound:
            selector = ObservationSelector(
                document_id=published.revision.document_id, revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
                observation_id=trace.representative_observation_id)
            opening = _opening_points(composition.physical_opening_authority, selector,
                                      identity=trace.opening_identity_id, page_id=trace.page_id)
            row = {"opening_identity_id": trace.opening_identity_id, "route": _route(trace.reason_codes)}
            for name, owner in context.ownership(opening, trace.member_wall_candidate_ids).items():
                row[name] = {"status": owner.status.value, "reason_codes": list(owner.reason_codes),
                             "view_id": owner.view_id}
            rows.append(row)
        summary = {name: {} for name in ("authenticated", "proven", "combined")}
        for row in rows:
            for name, counts in summary.items():
                reason = row[name]["reason_codes"][-1]
                counts[reason] = counts.get(reason, 0) + 1
        pages.append({"page_id": page_id, "plan_views": {name: len(boxes) for name, boxes in context.views.items()},
                      "host_bindings": len(bound), "other_opening_traces": len(traces) - len(bound),
                      "ownership": summary, "rows": rows})
    return {"source_sha256": published.revision.source_sha256, "revision_id": composition.revision_id, "pages": pages}
