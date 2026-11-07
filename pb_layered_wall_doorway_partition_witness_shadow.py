"""Sliding-leaf partition groups of doorway-closed rings (SHADOW ONLY, default-off, topology only).

A wardrobe opening closed by a sliding-leaf chord splits one printed room into a bedroom face and
a wardrobe-alcove face. Neither face alone has a printed figure, but the PAIR does: the union of
the parts is the printed room. This module finds those groups and validates their membership; it
never measures anything and never assigns the union's rectangle (or any area) to a part.

A group is defined ONLY by real sliding-leaf chords produced by the ring shadow (never a swing, a
stroke or a solid wall), and its membership must be exact and exhaustive or the whole group is
refused:

* every sliding chord borders exactly two rings and both are closed (CANDIDATE) faces of THIS
  source (same SHA, same page); no swing or stroke chord joins two members of the group;
* the chord is the same on both sides: each side's chord edges lie on one face line of the wall
  band (one on each face), run along the band and cover the chord's interval exactly;
* the members' interiors do not overlap;
* the union of the members and their chord bands is ONE region with no interior hole (a wall return
  attached to a wall is a notch, an unexplained void is a hole).

The group's outer envelope (bounding box of that union) is returned for a topology cross-check by
the caller against an independently authenticated figured pair. Nothing here is an area.
"""
from __future__ import annotations

from dataclasses import dataclass
from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_SLIDING_LEAF,
    NOISE_PT,
    LayeredDoorwayClosure,
    LayeredRoomRingRecord,
    LayeredRoomRingResult,
)
from pb_migration_contracts import EvidenceResolutionStatus

CLOSURE_OWNER_PREFIX = "layered_doorway_closure:"

REASON_MEMBERSHIP = "partition_membership_not_exact"
REASON_FOREIGN = "partition_member_not_from_this_source_page"
REASON_CHORD = "partition_chord_not_matched_on_both_sides"
REASON_OVERLAP = "partition_members_overlap"
REASON_HOLE = "partition_region_has_unexplained_void"
REASON_MIXED = "partition_joined_by_a_non_sliding_chord"
REASON_OPEN_MEMBER = "partition_member_not_a_closed_face"
REASON_ID_COLLISION = "partition_source_record_id_collision"


@dataclass(frozen=True)
class PartitionGroup:
    ring_record_ids: tuple[str, ...]
    sliding_closure_ids: tuple[str, ...]
    valid: bool
    reason: str
    envelope: tuple[float, float, float, float]  # meaningful only when valid


def _chord_edges(ring: LayeredRoomRingRecord, closure_id: str) -> list[tuple[tuple[float, float], tuple[float, float]]] | None:
    points = ring.polygon_pdf_pts
    if len(ring.edge_owner_ids) != len(points):
        return None
    owner = (f"{CLOSURE_OWNER_PREFIX}{closure_id}",)
    return [(points[i], points[(i + 1) % len(points)]) for i, owners in enumerate(ring.edge_owner_ids) if tuple(owners) == owner]


def _chord_side(ring: LayeredRoomRingRecord, closure: LayeredDoorwayClosure) -> float | None:
    """The face-line coordinate of the ring's chord edges if they are exactly the closure's interval, else None."""
    edges = _chord_edges(ring, closure.closure_id)
    if not edges:
        return None
    perps: list[float] = []
    spans: list[tuple[float, float]] = []
    for (ax, ay), (bx, by) in edges:
        if closure.horizontal:
            if abs(ay - by) > NOISE_PT:
                return None
            perps.append((ay + by) / 2.0)
            spans.append(tuple(sorted((ax, bx))))  # type: ignore[arg-type]
        else:
            if abs(ax - bx) > NOISE_PT:
                return None
            perps.append((ax + bx) / 2.0)
            spans.append(tuple(sorted((ay, by))))  # type: ignore[arg-type]
    if max(perps) - min(perps) > NOISE_PT:
        return None  # the chord edges sit on more than one line: not one face line of the band
    spans.sort()
    cursor_lo, cursor_hi = spans[0]
    for lo, hi in spans[1:]:
        if lo > cursor_hi + NOISE_PT:
            return None  # a piece of the interval is owned by something else
        cursor_hi = max(cursor_hi, hi)
    if abs(cursor_lo - closure.gap_interval[0]) > NOISE_PT or abs(cursor_hi - closure.gap_interval[1]) > NOISE_PT:
        return None
    return sum(perps) / len(perps)


def _closure_rect(closure: LayeredDoorwayClosure) -> Polygon:
    lo, hi = closure.gap_interval
    if closure.horizontal:
        return box(lo, closure.band[0], hi, closure.band[1])
    return box(closure.band[0], lo, closure.band[1], hi)


def partition_groups(
    ring_result: LayeredRoomRingResult, *, source_sha256: str, page_index: int,
) -> tuple[PartitionGroup, ...]:
    """Every group of rings joined by sliding-leaf chords, each validated or refused with a reason."""
    sliding_ids = {c.closure_id for c in ring_result.closures if c.kind == KIND_SLIDING_LEAF}
    if not sliding_ids:
        return ()
    # An id that appears twice is quarantined, never resolved by input order: whichever copy came last (or
    # first) would otherwise decide the provenance of a ring or a chord.
    rings, duplicate_rings = _by_id(ring_result.rings, lambda r: r.record_id)
    closures, duplicate_closures = _by_id(ring_result.closures, lambda c: c.closure_id)
    bordering: dict[str, list[str]] = {cid: [] for cid in sliding_ids}
    for ring in ring_result.rings:  # every copy, so a quarantined ring still joins (and refuses) its group
        for cid in ring.bounding_closure_ids:
            if cid in bordering and ring.record_id not in bordering[cid]:
                bordering[cid].append(ring.record_id)

    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.setdefault(x, x) != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for members in bordering.values():
        for other in members[1:]:
            parent[find(other)] = find(members[0])
        if members:
            find(members[0])
    components: dict[str, set[str]] = {}
    for ring_id in list(parent):
        components.setdefault(find(ring_id), set()).add(ring_id)

    groups: list[PartitionGroup] = []
    for members in components.values():
        member_ids = tuple(sorted(members))
        closure_ids = tuple(sorted(cid for cid, ids in bordering.items() if set(ids) & members))
        groups.append(_validate(
            member_ids, closure_ids, rings, closures, (duplicate_rings, duplicate_closures),
            source_sha256, page_index, bordering,
        ))
    groups.sort(key=lambda g: g.ring_record_ids)
    return tuple(groups)


def _by_id(items, key):
    """(items whose id is unique by id, the ids that occur more than once)."""
    seen: dict[str, object] = {}
    duplicated: set[str] = set()
    for item in items:
        item_id = key(item)
        if item_id in seen:
            duplicated.add(item_id)
        else:
            seen[item_id] = item
    return {i: v for i, v in seen.items() if i not in duplicated}, duplicated


def _refuse(member_ids, closure_ids, reason) -> PartitionGroup:
    return PartitionGroup(member_ids, closure_ids, False, reason, (0.0, 0.0, 0.0, 0.0))


def _validate(member_ids, closure_ids, rings, closures, collisions, source_sha256, page_index, bordering) -> PartitionGroup:
    duplicate_rings, duplicate_closures = collisions
    if set(member_ids) & duplicate_rings:
        return _refuse(member_ids, closure_ids, REASON_ID_COLLISION)
    members = [rings[i] for i in member_ids]
    # every chord of the group, sliding or not, is bordered by a member, so this covers all of them
    if duplicate_closures & {cid for r in members for cid in r.bounding_closure_ids}:
        return _refuse(member_ids, closure_ids, REASON_ID_COLLISION)
    if any(r.source_sha256 != source_sha256 or r.page_index != page_index for r in members):
        return _refuse(member_ids, closure_ids, REASON_FOREIGN)
    if any(r.status is not EvidenceResolutionStatus.CANDIDATE for r in members):
        return _refuse(member_ids, closure_ids, REASON_OPEN_MEMBER)
    if any(r.hole_count for r in members):
        return _refuse(member_ids, closure_ids, REASON_HOLE)
    # exact membership: every sliding chord of the group borders exactly two rings (a group is the connected
    # set of rings those chords join, so a chord with one neighbour is a missing partner and one with three
    # is an extra one)
    for cid in closure_ids:
        if len(bordering[cid]) != 2:
            return _refuse(member_ids, closure_ids, REASON_MEMBERSHIP)
    # no other kind of chord may join two members (a swing, a stroke): that would mix partition edges
    other_closures = [c for c in closures.values() if c.kind != KIND_SLIDING_LEAF]
    for closure in other_closures:
        touching = [r.record_id for r in members if closure.closure_id in r.bounding_closure_ids]
        if len(touching) >= 2:
            return _refuse(member_ids, closure_ids, REASON_MIXED)
    # the same chord, matched on both sides: one member on each face line of the wall band
    for cid in closure_ids:
        closure = closures[cid]
        sides = [_chord_side(rings[i], closure) for i in bordering[cid]]
        if any(side is None for side in sides):
            return _refuse(member_ids, closure_ids, REASON_CHORD)
        faces = sorted(closure.band)
        if any(abs(side - face) > NOISE_PT for side, face in zip(sorted(sides), faces)):  # type: ignore[type-var]
            return _refuse(member_ids, closure_ids, REASON_CHORD)
    polygons = []
    for ring in members:
        polygon = Polygon(ring.polygon_pdf_pts)
        if not polygon.is_valid or polygon.area <= 0.0:
            return _refuse(member_ids, closure_ids, REASON_MEMBERSHIP)
        polygons.append(polygon)
    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            if polygons[i].intersection(polygons[j]).area > NOISE_PT * NOISE_PT:
                return _refuse(member_ids, closure_ids, REASON_OVERLAP)
    closing = 0.03
    region = unary_union([p.buffer(closing, join_style=2) for p in polygons + [_closure_rect(closures[c]) for c in closure_ids]])
    region = region.buffer(-closing, join_style=2)
    if region.geom_type != "Polygon" or len(region.interiors) != 0:
        return _refuse(member_ids, closure_ids, REASON_HOLE)
    # The envelope is read from the members' own vertices (the buffered region is only for the void test, and
    # a chord band lies between two members, so it never extends the hull).
    xs = [x for ring in members for x, _y in ring.polygon_pdf_pts]
    ys = [y for ring in members for _x, y in ring.polygon_pdf_pts]
    envelope = (round(min(xs), 4), round(min(ys), 4), round(max(xs), 4), round(max(ys), 4))
    return PartitionGroup(member_ids, closure_ids, True, "partition_membership_exact", envelope)


__all__ = [
    "PartitionGroup",
    "partition_groups",
]
