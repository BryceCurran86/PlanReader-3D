"""SAME / DISTINCT / AMBIGUOUS for live canonical openings (shadow).

Different record IDs do not prove DISTINCT. Closeness does not prove SAME.
This helper only reads source geometries already on the canonical objects; it
does not mint openings, hosts, kinds or quantities.

A jamb-bounded two-face interruption is often stored as three records: a short
hinge tick, the hosted wall-band cut, and the closed-leaf tip. Global SAME
requires matching document/revision/SHA/snapshot/page/viewport plus issued
host/frame ownership. Equal source geometries are not SAME without that
ownership. Shared vertices alone stay AMBIGUOUS. Distance beyond the
production 2.5 pt snap is not DISTINCT without an independently bounded
aperture. A painted-swing consumer may union AMBIGUOUS hits only when they
share this witness's hinge or closed-tip vertex, or share issued aperture;
it must never override DISTINCT.
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Sequence

from shapely.geometry import LineString

from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject

SAME = "same"
DISTINCT = "distinct"
AMBIGUOUS = "ambiguous"
# Vertex identity of one CAD corner, not the 2.5 pt opening-bind snap.
# 0.5 pt covers native PDF rounding of a shared jamb vertex; it does not
# join two openings that only pass near a hinge (those sit ~1 pt apart).
_SHARED_JAMB_VERTEX_PT = 0.5
_DISTINCT_SEPARATION_PT = 2.5


def _segment(opening: LiveCanonicalOpeningObject) -> LineString | None:
    geoms = opening.source_geometries or ()
    if len(geoms) != 1 or len(geoms[0]) < 4:
        return None
    geom = geoms[0]
    line = LineString(
        (
            (float(geom[0]), float(geom[1])),
            (float(geom[2]), float(geom[3])),
        )
    )
    if line.is_empty or line.length <= 0.0:
        return None
    return line


def _endpoints(opening: LiveCanonicalOpeningObject) -> tuple[tuple[float, float], ...]:
    line = _segment(opening)
    if line is None:
        return ()
    coords = tuple((float(x), float(y)) for x, y in line.coords)
    if len(coords) < 2:
        return ()
    return (coords[0], coords[-1])


def _vertex_join(left: LiveCanonicalOpeningObject, right: LiveCanonicalOpeningObject) -> bool:
    a_ends = _endpoints(left)
    b_ends = _endpoints(right)
    if not a_ends or not b_ends:
        return False
    return min(
        math.hypot(ax - bx, ay - by)
        for ax, ay in a_ends
        for bx, by in b_ends
    ) <= _SHARED_JAMB_VERTEX_PT


def _source_scope(
    opening: LiveCanonicalOpeningObject,
) -> tuple[str, str, str, str, str]:
    return (
        str(opening.document_id),
        str(opening.revision_id),
        str(opening.source_sha256),
        str(opening.snapshot_id),
        str(opening.page_id),
    )


def _viewport_token(opening: LiveCanonicalOpeningObject) -> str | None:
    token = str(opening.viewport_id or "").strip()
    return token or None


def share_source_jamb_vertex(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
) -> bool:
    """True when two source segments share a CAD jamb vertex.

    This is a local doorway-face witness, not global SAME identity.
    """
    return _vertex_join(left, right)


def source_segment_endpoint_at(
    opening: LiveCanonicalOpeningObject,
    point: tuple[float, float],
) -> bool:
    """True when a source-segment endpoint is this CAD point."""
    px, py = float(point[0]), float(point[1])
    return any(
        math.hypot(x - px, y - py) <= _SHARED_JAMB_VERTEX_PT
        for x, y in _endpoints(opening)
    )


def share_issued_aperture_ownership(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
) -> bool:
    """True when both records carry the same issued host or frame receipt."""
    return _issued_aperture_ownership(left, right)


def share_source_jamb_vertex_at(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
    point: tuple[float, float],
) -> bool:
    """True when the shared CAD vertex is this painted-swing hinge or tip.

    Sharing a different jamb corner is not this witness's doorway face.
    """
    if not _vertex_join(left, right):
        return False
    px, py = float(point[0]), float(point[1])
    for ax, ay in _endpoints(left):
        for bx, by in _endpoints(right):
            if math.hypot(ax - bx, ay - by) > _SHARED_JAMB_VERTEX_PT:
                continue
            if math.hypot(ax - px, ay - py) <= _SHARED_JAMB_VERTEX_PT:
                return True
            if math.hypot(bx - px, by - py) <= _SHARED_JAMB_VERTEX_PT:
                return True
    return False


def _issued_aperture_ownership(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
) -> bool:
    left_binding = str(left.host_binding_record_id or "").strip()
    right_binding = str(right.host_binding_record_id or "").strip()
    if (
        left_binding
        and left_binding == right_binding
        and left_binding in left.evidence_ids
        and right_binding in right.evidence_ids
    ):
        return True
    left_frame = str(left.host_frame_record_id or "").strip()
    right_frame = str(right.host_frame_record_id or "").strip()
    return bool(left_frame and left_frame == right_frame)


def compare_live_canonical_opening_identity(
    left: LiveCanonicalOpeningObject,
    right: LiveCanonicalOpeningObject,
) -> str:
    """Source-geometry identity of two live canonical openings.

    Unique ID strings are ignored except as a SAME shortcut when they match.
    Document/revision/SHA/snapshot/page/viewport must agree before any
    geometry shortcut. Equal source geometries still need issued host/frame
    ownership. Shared vertices alone are not SAME.
    """
    if type(left) is not LiveCanonicalOpeningObject:
        raise TypeError("left must be LiveCanonicalOpeningObject")
    if type(right) is not LiveCanonicalOpeningObject:
        raise TypeError("right must be LiveCanonicalOpeningObject")
    if _source_scope(left) != _source_scope(right):
        return DISTINCT
    left_viewport = _viewport_token(left)
    right_viewport = _viewport_token(right)
    if left_viewport is None or right_viewport is None:
        if left.canonical_opening_id == right.canonical_opening_id:
            return SAME
        if (
            left.physical_opening_id
            and left.physical_opening_id == right.physical_opening_id
        ):
            return SAME
        return AMBIGUOUS
    if left_viewport != right_viewport:
        return DISTINCT
    if left.canonical_opening_id == right.canonical_opening_id:
        return SAME
    if (
        left.physical_opening_id
        and left.physical_opening_id == right.physical_opening_id
    ):
        return SAME
    if left.source_geometries and left.source_geometries == right.source_geometries:
        if _issued_aperture_ownership(left, right):
            return SAME
        return AMBIGUOUS
    left_line = _segment(left)
    right_line = _segment(right)
    if left_line is None or right_line is None:
        return AMBIGUOUS
    if left_line.crosses(right_line):
        return AMBIGUOUS
    if _vertex_join(left, right):
        if _issued_aperture_ownership(left, right):
            return SAME
        return AMBIGUOUS
    if left_line.distance(right_line) > _DISTINCT_SEPARATION_PT:
        return AMBIGUOUS
    return AMBIGUOUS


def cluster_live_canonical_opening_identities(
    openings: Sequence[LiveCanonicalOpeningObject],
) -> tuple[tuple[str, ...], ...]:
    """Union-find clusters of proven-SAME openings. Order is input-stable."""
    items = [item for item in openings if type(item) is LiveCanonicalOpeningObject]
    ids = [item.canonical_opening_id for item in items]
    parent = {identity: identity for identity in ids}

    def find(identity: str) -> str:
        while parent[identity] != identity:
            parent[identity] = parent[parent[identity]]
            identity = parent[identity]
        return identity

    def union(left_id: str, right_id: str) -> None:
        root_left, root_right = find(left_id), find(right_id)
        if root_left != root_right:
            parent[root_right] = root_left

    for index, left in enumerate(items):
        for right in items[index + 1:]:
            if compare_live_canonical_opening_identity(left, right) == SAME:
                union(left.canonical_opening_id, right.canonical_opening_id)
    grouped: dict[str, list[str]] = defaultdict(list)
    for identity in ids:
        grouped[find(identity)].append(identity)
    seen: list[str] = []
    for identity in ids:
        root = find(identity)
        if root not in seen:
            seen.append(root)
    return tuple(tuple(grouped[root]) for root in seen)


def partition_unmapped_opening_outputs(
    openings: Sequence[LiveCanonicalOpeningObject],
    *,
    matched_physical_ids: Sequence[str] = (),
) -> tuple[dict[str, object], ...]:
    """Per-unmapped opening: source observations, jamb, host, label, identity.

    Equal area, proximity and unique IDs are not used to drop or merge rows.
    """
    matched = {
        str(identity).strip()
        for identity in matched_physical_ids
        if str(identity).strip()
    }
    rows: list[dict[str, object]] = []
    items = tuple(
        item
        for item in openings
        if type(item) is LiveCanonicalOpeningObject
        and item.physical_opening_id not in matched
        and item.canonical_opening_id not in matched
    )
    for item in items:
        identities = {
            other.canonical_opening_id: compare_live_canonical_opening_identity(item, other)
            for other in items
            if other.canonical_opening_id != item.canonical_opening_id
        }
        rows.append(
            {
                "canonical_opening_id": item.canonical_opening_id,
                "physical_opening_id": item.physical_opening_id,
                "page_id": item.page_id,
                "viewport_id": item.viewport_id,
                "structural_pattern": item.structural_pattern,
                "opening_kind": item.opening_kind,
                "host_wall_id": item.host_wall_id,
                "host_binding_record_id": item.host_binding_record_id,
                "representative_observation_id": item.representative_observation_id,
                "source_observation_ids": tuple(item.source_observation_ids),
                "source_geometries": tuple(item.source_geometries),
                "figured_single_axis_mm": item.figured_single_axis_mm,
                "figured_area_record_id": item.figured_area_record_id,
                "type_mark": item.type_mark,
                "area_m2": item.area_m2,
                "identities": identities,
            }
        )
    return tuple(rows)
