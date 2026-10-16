"""Source-only G17 raw-gap membership in one authenticated FLOOR_PLAN view.

An original gap outside this floor-plan viewport may belong to another drawing
view. It is NOT proof of a nonexistent opening or page-universe completeness.
Original source snapshots, G17 source members and F07 ownership are obtained
again from the same actual producer. No authority or customer path imports this.
"""
from __future__ import annotations

from math import isfinite

from pb_g17_plan_wall_scope_shadow import build_g17_plan_wall_scope_shadow
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _rect(value):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(type(v) not in (int, float) or not isfinite(v) for v in value)):
        raise ValueError("untrusted or incomplete source bbox")
    x0, y0, x1, y1 = map(float, value)
    if x1 <= x0 or y1 <= y0:
        raise ValueError("source bbox is empty or reversed")
    return (x0, y0, x1, y1)


def _line_scope(geometry, bbox):
    if (not isinstance(geometry, (tuple, list)) or len(geometry) != 4
            or any(type(v) not in (int, float) or not isfinite(v) for v in geometry)):
        return "unreadable"
    x0, y0, x1, y1 = map(float, geometry)
    left, top, right, bottom = bbox
    if (left <= min(x0, x1) <= max(x0, x1) <= right
            and top <= min(y0, y1) <= max(y0, y1) <= bottom):
        return "inside"
    if (max(x0, x1) < left or min(x0, x1) > right
            or max(y0, y1) < top or min(y0, y1) > bottom):
        return "outside"
    return "crossing"


def _scope_for_group(source_lines, original_aperture_bbox, plan_bbox):
    """A source group is scoped only by every entire original support."""
    if not source_lines:
        return "source_members_unavailable"
    kinds = tuple(_line_scope(line, plan_bbox) for line in source_lines)
    aperture = _rect(original_aperture_bbox)
    corners = ((aperture[0], aperture[1]), (aperture[2], aperture[3]))
    a_kinds = tuple(_line_scope((*corner, *corner), plan_bbox) for corner in corners)
    if "unreadable" in kinds:
        return "source_members_unreadable"
    if all(x == "inside" for x in kinds) and all(x == "inside" for x in a_kinds):
        return "inside_this_authenticated_floor_plan"
    if all(x == "outside" for x in kinds) and all(x == "outside" for x in a_kinds):
        # Outside this one plan does NOT mean a typed non-plan or non-opening.
        return "outside_this_authenticated_floor_plan_other_role_unproven"
    return "crossing_or_competing_view_owner_unproven"


def audit_original_g17_raw_plan_view_scope(
    source: SourceVisibilityProducer, *, revision_id: str, page_id: str,
) -> dict:
    if type(source) is not SourceVisibilityProducer:
        raise TypeError("actual current source producer required")
    if type(page_id) is not str or not page_id.isdecimal() or str(int(page_id)) != page_id or int(page_id) < 1:
        raise ValueError("canonical original page id required")
    published = source.published_snapshot_for_revision(revision_id)
    if published is None or (source._producer.current_revision_id(published.revision.document_id)
                             != revision_id):
        raise ValueError("original source revision unavailable or stale")
    original_sha = published.revision.source_sha256
    vis = source.authority()
    members = {}
    for oid in sorted(published.raster_opening_primitive_observation_ids):
        selector = ObservationSelector(published.revision.document_id, revision_id,
                                      original_sha, published.snapshot.snapshot_id, oid)
        proof = vis.resolve_raster_opening_primitive(selector)
        if proof.status is not EvidenceResolutionStatus.CORROBORATED or proof.observation is None:
            raise RuntimeError("registered original raster source observation is not authenticated")
        if proof.observation.page_id == page_id:
            members[oid] = (selector, proof.observation)
    if not members:
        return dict(status="abstained", reason_codes=["no_original_G17_page_members"],
                    source_sha256=original_sha, raw_groups=[], opening_host_granted=False,
                    opening_count_granted=False, metric_quantity_granted=False)
    physical = source.physical_opening_authority()
    selector = next(iter(members.values()))[0]
    groups = physical.audited_unresolved_source_candidate_groups(selector, family="raster")
    closure_before = physical.assess_raster_candidate_closure(selector)
    if (closure_before.status is not EvidenceResolutionStatus.CORROBORATED
            or {g["candidate_id"] for g in groups} != set(closure_before.unresolved_candidate_ids)
            or len(groups) != len(closure_before.unresolved_candidate_ids)):
        raise RuntimeError("original raw candidate closure and group membership disagree")

    plan = build_g17_plan_wall_scope_shadow(source, revision_id=revision_id, page_id=page_id)
    viewport_bbox = plan.get("source_viewport_bbox")
    scope_id = plan.get("source_viewport_ownership_id")
    source_rows = {r["observation_id"]: r for r in plan["source_primitive_dispositions"]}
    if set(members) != set(source_rows):
        raise RuntimeError("original G17 source and F07 observation inventories disagree")
    bbox = _rect(viewport_bbox) if scope_id and viewport_bbox else None
    dispositions = []
    for group in sorted(groups, key=lambda g: g["candidate_id"]):
        ids = tuple(group["source_observation_ids"])
        if not ids or len(ids) != len(set(ids)):
            raise RuntimeError("original candidate source member identities incomplete")
        source_lines = []
        paint_flags = []
        for oid in ids:
            entry = members.get(oid)
            row = source_rows.get(oid)
            if entry is None or row is None:
                raise RuntimeError("raw source candidate has foreign or missing F07 support")
            actual = entry[1]
            if (tuple(actual.geometry) != tuple(row["geometry"])
                    or actual.source_primitive_ref != "visible:" + row["source_primitive_id"]
                    or actual.source_sha256 != original_sha
                    or actual.snapshot_id != published.snapshot.snapshot_id):
                raise RuntimeError("raw G17 member differs from actual producer source receipt")
            source_lines.append(tuple(actual.geometry))
            paint_flags.append(bool(row["source_paint"]["original_solid_and_unchanged"]))
            if bbox is not None and row.get("drawing_disposition") != _line_scope(actual.geometry, bbox):
                # The F07-owned observer and direct geometry must agree; no favourable classification.
                raise RuntimeError("original F07/G17 source segment scope contradicts")
        location = (_scope_for_group(source_lines, group["aperture_bbox_pt"], bbox)
                    if bbox is not None else "authenticated_floor_plan_view_unavailable")
        dispositions.append(dict(
            raw_candidate_id=group["candidate_id"],
            source_observation_ids=ids,
            original_source_segment_dispositions=tuple(
                _line_scope(line, bbox) for line in source_lines) if bbox is not None else (),
            original_whole_segment_ink_positive_count=sum(paint_flags),
            original_whole_segment_count=len(source_lines),
            exact_original_aperture_bbox_pt=tuple(group["aperture_bbox_pt"]),
            authenticated_floor_plan_membership=location,
            physical_nonexistence_proven=False,
            typed_non_plan_opposition_proven=False,
            physical_opening_existence_granted=False,
            host_binding_granted=False,
            opening_count_granted=False,
        ))
    if (source.published_snapshot_for_revision(revision_id) != published
            or physical.assess_raster_candidate_closure(selector) != closure_before):
        raise RuntimeError("read-only source census changed original published state or gap closure")
    for oid, (_, original) in members.items():
        test = vis.resolve_raster_opening_primitive(
            ObservationSelector(published.revision.document_id, revision_id, original_sha,
                                published.snapshot.snapshot_id, oid))
        if test.status is not EvidenceResolutionStatus.CORROBORATED or test.observation != original:
            raise RuntimeError("original raster member changed during source read")
    return dict(
        status="candidate_only", source_sha256=original_sha,
        snapshot_id=published.snapshot.snapshot_id,
        revision_id=revision_id, page_id=page_id,
        authenticated_floor_plan_viewport_ownership_id=scope_id,
        authenticated_floor_plan_bbox_pt=bbox,
        original_page_raw_candidate_count=closure_before.raw_candidate_count,
        original_page_resolved_candidate_count=closure_before.resolved_candidate_count,
        original_page_unresolved_count=len(closure_before.unresolved_candidate_ids),
        original_page_candidate_universe_complete=closure_before.candidate_universe_complete,
        raw_groups=dispositions,
        source_view_ownership_not_commercial_count_proof=True,
        outside_one_floor_plan_does_not_prove_nonexistence=True,
        physical_wall_role_granted=False, opening_host_granted=False,
        opening_count_granted=False, metric_quantity_granted=False,
    )
