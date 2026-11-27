"""Report only (#4764 7211359981, geometry task C01): does a floor-plan view own each opening-to-wall binding?

For every corroborated opening host binding of a live wall/opening composition this asks whether the opening's whole source
support AND every member wall lie inside one and the same floor-plan view, using the repository's existing viewport builder:
once for authenticated floor-plan viewports and once for the stricter source-owned proven plan views. Ownership is
CORROBORATED only for exactly one view; none abstains and two or more conflict, each with a typed reason. Nothing on a live
path imports this module: it changes, publishes and promotes nothing.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Iterable, Optional, Sequence

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


def _pairs(values: Sequence[float]) -> list[Point]:
    if len(values) < 2 or len(values) % 2:
        return []
    return [(float(values[i]), float(values[i + 1])) for i in range(0, len(values), 2)]


def _opening_points(opening_authority, published, trace) -> list[Point]:
    """Every point of the opening's own source support, from the producer; empty when any part is unavailable."""
    def selector(observation_id):
        return ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id)

    record = opening_authority.prove_existence(selector(trace.representative_observation_id)).existence_record
    if record is None or record.record_id != trace.opening_identity_id or record.page_id != trace.page_id:
        return []
    if record.aperture_bbox_pt is not None:
        x0, y0, x1, y1 = record.aperture_bbox_pt
        return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    visibility = opening_authority.source_visibility_authority()
    points: list[Point] = []
    for observation_id in record.source_observation_ids:
        seen = visibility.resolve_visible(selector(observation_id)).observation
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


def _route(reason_codes: Sequence[str]) -> str:
    return next((code for code in reversed(reason_codes) if code.endswith("host_resolved")), "host_band")


def opening_host_plan_view_report(composition, source_producer: SourceVisibilityProducer) -> dict:
    """Ownership of every corroborated host binding, per topology page; the composition is only read."""
    if type(source_producer) is not SourceVisibilityProducer:
        raise TypeError("source_producer must be producer-owned")
    published = source_producer.published_snapshot_for_revision(composition.revision_id)
    if published is None:
        raise RuntimeError("source snapshot unavailable")
    source_bytes = source_producer._producer._store.source_bytes_by_revision[composition.revision_id]
    pages = []
    for page_id in composition.page_ids:
        traces = sorted((t for t in composition.opening_bindings if t.page_id == page_id),
                        key=lambda t: (str(t.opening_identity_id), t.representative_observation_id))
        bound = [t for t in traces
                 if t.status is EvidenceResolutionStatus.CORROBORATED and t.host_wall_id and t.opening_identity_id]
        views = {name: _plan_views(source_producer, published, source_bytes, page_id, proven=name == "proven")
                 for name in ("authenticated", "proven")}
        walls = _wall_points((composition.physical_wall_candidate_authority,
                              composition.supplemental_physical_wall_candidate_authority), published, page_id)
        rows = []
        for trace in bound:
            opening = _opening_points(composition.physical_opening_authority, published, trace)
            members = [walls.get(wall_id, []) for wall_id in trace.member_wall_candidate_ids]
            row = {"opening_identity_id": trace.opening_identity_id, "route": _route(trace.reason_codes)}
            for name, boxes in views.items():
                owner = asdict(plan_view_ownership(opening, members, boxes))
                row[name] = {**owner, "status": owner["status"].value, "reason_codes": list(owner["reason_codes"])}
            rows.append(row)
        summary = {name: {} for name in views}
        for row in rows:
            for name in views:
                reason = row[name]["reason_codes"][-1]
                summary[name][reason] = summary[name].get(reason, 0) + 1
        pages.append({"page_id": page_id, "plan_views": {name: len(boxes) for name, boxes in views.items()},
                      "host_bindings": len(bound), "other_opening_traces": len(traces) - len(bound),
                      "ownership": summary, "rows": rows})
    return {"source_sha256": published.revision.source_sha256, "revision_id": composition.revision_id, "pages": pages}
