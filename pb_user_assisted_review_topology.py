"""Apply a guided-review correction packet to the canonical room tracer: user-assisted topology, never authority.

A packet (``pb_guided_plan_review_native.build_native_review_packet``) carries marks a person drew on one exact page. This module
checks that the packet belongs to this PDF, page and page frame, gives each mark one role and one outcome, and feeds the
topology marks into ``pb_next_wall_ring_preview`` through its ``barrier_view`` hook:

* wall marks are user walls and door, window and opening marks are temporary closures: both close rooms, neither is a wall
  face, an authenticated wall or an opening deduction;
* a reject mark removes a candidate only when it crosses exactly one closure or one wall piece (overlapping pieces count once);
* finish boundaries split finish regions of the traced rooms; exclusions flag rooms; room outlines are compared; a dimension
  line is not geometry.

A user line joins existing geometry only within the 2.5 pt snap at its ends, to every piece in reach; an end that reaches
nothing is reported open. The automatic result is never changed and nothing here is measured, priced or benchmarked.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import json
import math
import re
from typing import Any

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import nearest_points, unary_union

from pb_migration_contracts import stable_contract_id
from pb_next_wall_ring_preview import NOISE_PT, LayeredBarrierView

SCHEMA_VERSION = "1.0.0"
PRODUCER = "pb_user_assisted_review_topology"
PACKET_SCHEMA_VERSION = 1
PACKET_STATUS = "USER_CORRECTIONS_PENDING_CONSUMER"
SNAP_PT = 2.5  # the repository's snap, used only to join a user line's end to geometry
LINE_HALF_PT = 0.25
LABEL_PREFIX = "user_review_mark:"
RESIDUAL_STATUSES = (
    "unmatched_raw_wall_ink_terminal_needs_post_opening_review",
    "ambiguous_competing_hosted_apertures",
    "ambiguous_competing_source_roles",
)
OPEN_END_STATUS = "user_mark_end_open"

ROLE_WALL = "user_wall"
ROLE_CLOSURE = "user_temporary_closure"
ROLE_FINISH = "user_finish_boundary"
ROLE_REJECT = "user_reject"
ROLE_EXCLUSION = "user_exclusion"
ROLE_OUTLINE = "user_room_outline"
ROLE_DIMENSION = "user_dimension_witness"
ROLE_UNSUPPORTED = "unsupported"
LINE_ROLES = {
    "external_wall": ROLE_WALL, "internal_wall": ROLE_WALL,
    "swing_door": ROLE_CLOSURE, "cavity_slider": ROLE_CLOSURE, "garage_door": ROLE_CLOSURE, "window": ROLE_CLOSURE,
    "opening": ROLE_CLOSURE, "boundary": ROLE_FINISH, "reject_candidate": ROLE_REJECT, "dimension_witness": ROLE_DIMENSION,
}
POLYGON_ROLES = {"room_outline": ROLE_OUTLINE, "exclusion": ROLE_EXCLUSION}
_BARRIER_ROLES = (ROLE_WALL, ROLE_CLOSURE)
_SHA = re.compile(r"[0-9a-f]{64}")


class ReviewPacketError(ValueError):
    """The packet does not belong to this exact source, page and frame, or claims an authority."""


@dataclass(frozen=True)
class UserMark:
    correction_id: str
    category: str
    role: str
    points: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class ReviewPacket:
    review_revision: int
    packet_sha256: str
    marks: tuple[UserMark, ...]


def _digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _plain(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def _points(raw: Any, *, line: bool) -> tuple[tuple[float, float], ...]:
    if not isinstance(raw, (list, tuple)) or (len(raw) != 2 if line else not 3 <= len(raw) <= 128):
        raise ReviewPacketError("review_mark_points_invalid")
    points = []
    for item in raw:
        if (not isinstance(item, (list, tuple)) or len(item) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in item)):
            raise ReviewPacketError("review_mark_points_invalid")
        points.append((float(item[0]), float(item[1])))
    if line and math.dist(*points) <= NOISE_PT:
        raise ReviewPacketError("review_mark_points_invalid")
    if not line:
        polygon = Polygon(points)
        if not polygon.is_valid or polygon.area <= 0:
            raise ReviewPacketError("review_mark_outline_invalid")
    return tuple(points)


def read_review_packet(
    packet: Mapping[str, Any], *, source_sha256: str, page_index: int, coordinate_frame: Mapping[str, Any],
) -> ReviewPacket:
    """The marks of a packet that belongs to this exact source, page and native frame and claims no authority."""
    if not isinstance(packet, Mapping):
        raise ReviewPacketError("review_packet_not_a_mapping")
    payload = {key: value for key, value in packet.items() if key != "packet_sha256"}
    try:
        digest = _digest(payload)
    except (TypeError, ValueError) as exc:
        raise ReviewPacketError("review_packet_not_plain_json") from exc
    if packet.get("packet_sha256") != digest:
        raise ReviewPacketError("review_packet_digest_mismatch")
    if packet.get("schema_version") != PACKET_SCHEMA_VERSION or packet.get("status") != PACKET_STATUS:
        raise ReviewPacketError("review_packet_schema_or_status_unsupported")
    if any(packet.get(flag) is not False for flag in
           ("automatic_source_verified", "commercial_projection_allowed", "frozen_benchmark_allowed", "topology_recalculated")):
        raise ReviewPacketError("review_packet_claims_authority")
    scope = packet.get("scope")
    if not isinstance(scope, Mapping) or scope.get("source_sha256") != source_sha256 or scope.get("pdf_page") != page_index + 1:
        raise ReviewPacketError("review_packet_source_or_page_mismatch")
    if _plain(packet.get("coordinate_frame")) != _plain(coordinate_frame):
        raise ReviewPacketError("review_packet_page_frame_mismatch")
    revision = packet.get("review_revision")
    corrections = packet.get("corrections")
    if type(revision) is not int or revision < 1 or not isinstance(corrections, (list, tuple)) or len(corrections) > 500:
        raise ReviewPacketError("review_packet_corrections_invalid")
    marks, seen = [], set()
    for row in corrections:
        if not isinstance(row, Mapping) or row.get("authority") != "user_selected_geometry":
            raise ReviewPacketError("review_mark_not_user_geometry")
        identity, category, kind = row.get("correction_id"), row.get("category"), row.get("kind")
        if type(identity) is not str or not identity or identity in seen or type(category) is not str:
            raise ReviewPacketError("review_mark_identity_invalid")
        seen.add(identity)
        role = LINE_ROLES.get(category) if kind == "line" else POLYGON_ROLES.get(category) if kind == "polygon" else None
        points = _points(row.get("native_points_pdf_pts"), line=kind == "line") if role else ()
        marks.append(UserMark(identity, category, role or ROLE_UNSUPPORTED, points))
    return ReviewPacket(revision, digest, tuple(sorted(marks, key=lambda m: m.correction_id)))


# --------------------------------------------------------------------------------------------- barrier pieces

def _piece_key(index: int, polygon: Any) -> tuple:
    return (int(index), *(round(float(v), 4) for v in polygon.bounds))


@dataclass
class BarrierRecorder:
    """A ``barrier_view`` that changes nothing and remembers every barrier piece the tracer used (all tiles)."""

    strips: dict = field(default_factory=dict)
    fills: dict = field(default_factory=dict)
    closures: dict = field(default_factory=dict)

    def __call__(self, view: LayeredBarrierView) -> LayeredBarrierView:
        for strip in view.strips:
            self.strips[_piece_key(strip.path_index, strip.polygon)] = strip.polygon
        for index, polygon in view.other_fills:
            self.fills[_piece_key(index, polygon)] = polygon
        for closure_id, rect in view.closure_rects:
            self.closures[closure_id] = rect
        return view


@dataclass(frozen=True)
class ReviewPlan:
    removed_strips: frozenset
    removed_fills: frozenset
    removed_closures: frozenset
    extra_rects: tuple  # (label, polygon)
    outcomes: Mapping[str, Mapping[str, Any]]

    def __call__(self, view: LayeredBarrierView) -> LayeredBarrierView:
        return LayeredBarrierView(
            strips=tuple(s for s in view.strips if _piece_key(s.path_index, s.polygon) not in self.removed_strips),
            other_fills=tuple((i, p) for i, p in view.other_fills if _piece_key(i, p) not in self.removed_fills),
            closures=tuple(c for c in view.closures if c.closure_id not in self.removed_closures),
            closure_rects=tuple((cid, rect) for cid, rect in view.closure_rects if cid not in self.removed_closures),
            unresolved_gaps=tuple(gap for gap in view.unresolved_gaps if not self._closes(gap)),
            extra_rects=self.extra_rects,
        )

    def _closes(self, gap: Any) -> bool:
        """Whether the user's barriers run the whole length of this interruption, within the snap of its wall band."""
        if not self.extra_rects:
            return False
        low, high = gap.band[0] - SNAP_PT, gap.band[1] + SNAP_PT
        window = box(gap.lo, low, gap.hi, high) if gap.horizontal else box(low, gap.lo, high, gap.hi)
        covered = unary_union([rect for _label, rect in self.extra_rects]).intersection(window)
        if covered.is_empty:
            return False
        axis = 0 if gap.horizontal else 1
        reach = gap.lo
        for start, stop in sorted((part.bounds[axis], part.bounds[axis + 2]) for part in getattr(covered, "geoms", (covered,))):
            if start > reach + SNAP_PT:
                return False
            reach = max(reach, stop)
        return reach >= gap.hi - SNAP_PT


def _thin(line: LineString) -> Polygon:
    return line.buffer(LINE_HALF_PT, cap_style=2, join_style=2)


def _joins(line: LineString, targets: Sequence[Any]) -> tuple[list[LineString], list[tuple[float, float]], int]:
    """Connectors from each end to every target within the snap; the ends that reach nothing; the ends that reach something."""
    connectors, open_ends, joined = [], [], 0
    for x, y in (line.coords[0], line.coords[-1]):
        end = Point(x, y)
        near = [target for target in targets if target.distance(end) <= SNAP_PT]
        if not near:
            open_ends.append((round(x, 4), round(y, 4)))
            continue
        joined += 1
        for target in near:
            if target.distance(end) > NOISE_PT:
                tip = nearest_points(end, target)[1]
                connectors.append(LineString([(x, y), (tip.x, tip.y)]))
    return connectors, open_ends, joined


def _overlap_groups(polygons: Sequence[Any]) -> int:
    """How many separate things the polygons are: pieces that share area are one (the collectors can overlap)."""
    parent = list(range(len(polygons)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(polygons)):
        for j in range(i + 1, len(polygons)):
            if polygons[i].intersection(polygons[j]).area > NOISE_PT * NOISE_PT:
                parent[root(i)] = root(j)
    return len({root(i) for i in range(len(polygons))})


def _reject(line: LineString, recorder: BarrierRecorder) -> tuple[str, set, set, set]:
    closures = {cid for cid, rect in recorder.closures.items() if line.intersection(rect).length > NOISE_PT}
    strips = {key for key, poly in recorder.strips.items() if line.intersection(poly).length > NOISE_PT}
    fills = {key for key, poly in recorder.fills.items() if line.intersection(poly).length > NOISE_PT}
    crossed = [recorder.strips[k] for k in sorted(strips)] + [recorder.fills[k] for k in sorted(fills)]
    total = len(closures) + _overlap_groups(crossed)
    if total == 0:
        return "unbound_no_target", set(), set(), set()
    if total > 1:
        return "unbound_ambiguous", set(), set(), set()
    return "applied", strips, fills, closures


def plan_review(packet: ReviewPacket, recorder: BarrierRecorder) -> ReviewPlan:
    """Decide every mark against the pieces the automatic run used. Order of the marks does not matter."""
    outcomes: dict[str, dict[str, Any]] = {}
    removed_strips: set = set()
    removed_fills: set = set()
    removed_closures: set = set()
    for mark in packet.marks:
        if mark.role == ROLE_REJECT:
            outcome, strips, fills, closures = _reject(LineString(mark.points), recorder)
            outcomes[mark.correction_id] = {"outcome": outcome, "removed_piece_count": len(strips) + len(fills) + len(closures)}
            removed_strips |= strips
            removed_fills |= fills
            removed_closures |= closures
        elif mark.role == ROLE_DIMENSION:
            outcomes[mark.correction_id] = {"outcome": "not_geometry"}
        elif mark.role == ROLE_UNSUPPORTED:
            outcomes[mark.correction_id] = {"outcome": "unsupported_category"}
    remaining = (
        [p for k, p in recorder.strips.items() if k not in removed_strips]
        + [p for k, p in recorder.fills.items() if k not in removed_fills]
        + [r for k, r in recorder.closures.items() if k not in removed_closures]
    )
    barrier_marks = [mark for mark in packet.marks if mark.role in _BARRIER_ROLES]
    extra: list[tuple[str, Polygon]] = []
    for mark in barrier_marks:
        line = LineString(mark.points)
        others = [_thin(LineString(other.points)) for other in barrier_marks if other.correction_id != mark.correction_id]
        connectors, open_ends, joined = _joins(line, [*remaining, *others])
        label = LABEL_PREFIX + mark.correction_id
        extra.append((label, _thin(line)))
        extra.extend((label, connector.buffer(LINE_HALF_PT, cap_style=3, join_style=2)) for connector in connectors)
        outcomes[mark.correction_id] = {
            "outcome": "applied" if not open_ends else "applied_with_open_end",
            "joined_end_count": joined,
            "open_end_points_pdf_pts": [list(p) for p in sorted(open_ends)],
        }
    return ReviewPlan(frozenset(removed_strips), frozenset(removed_fills), frozenset(removed_closures), tuple(extra), outcomes)


# --------------------------------------------------------------------------------------------- the result block

def _ring_polygon(ring: Any) -> Polygon:
    return Polygon(ring.polygon_pdf_pts)


def _user_marks_on(ring: Any) -> list[str]:
    return sorted({
        owner[len(LABEL_PREFIX):] for owners in ring.edge_owner_ids for owner in owners if owner.startswith(LABEL_PREFIX)
    })


def _split(regions: list[Polygon], mark: UserMark) -> tuple[list[Polygon], bool]:
    line = LineString(mark.points)
    connectors, _open, _joined = _joins(line, [region.exterior for region in regions])
    cutter = unary_union([_thin(line), *(c.buffer(LINE_HALF_PT, cap_style=3) for c in connectors)])
    out, split = [], False
    for region in regions:
        parts = region.difference(cutter)
        pieces = [p for p in getattr(parts, "geoms", (parts,)) if p.geom_type == "Polygon" and p.area > NOISE_PT]
        if len(pieces) >= 2:
            out.extend(pieces)
            split = True
        else:
            out.append(region)
    return out, split


def _coords(polygon: Polygon) -> list[list[float]]:
    return [[round(float(x), 4), round(float(y), 4)] for x, y in list(polygon.exterior.coords)[:-1]]


def build_review_block(
    packet: ReviewPacket,
    plan: ReviewPlan,
    *,
    source_sha256: str,
    page_index: int,
    automatic_rings: Sequence[Any],
    user_rings: Sequence[Any],
    endpoint_reviews: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Rooms after the user's marks, each mark's outcome, finish regions and the places still open."""
    outcomes = {mark.correction_id: dict(plan.outcomes.get(mark.correction_id, {"outcome": "pending"})) for mark in packet.marks}
    automatic_ids = {ring.record_id for ring in automatic_rings}
    exclusions = [mark for mark in packet.marks if mark.role == ROLE_EXCLUSION]
    excluded_area = unary_union([Polygon(mark.points) for mark in exclusions]) if exclusions else None
    rooms = []
    for ring in sorted(user_rings, key=lambda r: r.record_id):
        polygon = _ring_polygon(ring)
        share = 0.0
        if excluded_area is not None and polygon.area > 0:
            share = polygon.intersection(excluded_area).area / polygon.area
        rooms.append({
            "room_id": ring.record_id,
            "status": ring.status.value,
            "reason_codes": list(ring.reason_codes),
            "polygon_pdf_pts": [list(p) for p in ring.polygon_pdf_pts],
            "area_pt2": ring.area_pt2,
            "user_mark_ids": _user_marks_on(ring),
            "same_as_automatic": ring.record_id in automatic_ids,
            "exclusion": "excluded" if share >= 0.99 else "partly_excluded" if share > 0.01 else "included",
            "excluded_area_share": round(share, 4),
        })
    for mark in packet.marks:
        if mark.role in _BARRIER_ROLES:
            outcomes[mark.correction_id]["bounds_room_ids"] = sorted(
                room["room_id"] for room in rooms if mark.correction_id in room["user_mark_ids"])
        elif mark.role == ROLE_EXCLUSION:
            area = Polygon(mark.points)
            hit = sorted(r.record_id for r in user_rings if _ring_polygon(r).intersection(area).area > 0)
            outcomes[mark.correction_id] = {"outcome": "flagged" if hit else "no_effect", "room_ids": hit}
        elif mark.role == ROLE_OUTLINE:
            drawn = Polygon(mark.points)
            matches = []
            for ring in user_rings:
                polygon = _ring_polygon(ring)
                union = polygon.union(drawn).area
                overlap = polygon.intersection(drawn).area
                if overlap > 0 and union > 0:
                    matches.append({"room_id": ring.record_id, "overlap_over_union": round(overlap / union, 4)})
            matches.sort(key=lambda m: (-m["overlap_over_union"], m["room_id"]))
            outcomes[mark.correction_id] = {"outcome": "compared", "matches": matches}
    finish_marks = [mark for mark in packet.marks if mark.role == ROLE_FINISH]
    finish_regions = []
    splits: dict[str, list[str]] = {mark.correction_id: [] for mark in finish_marks}
    for ring in sorted(user_rings, key=lambda r: r.record_id):
        regions = [_ring_polygon(ring)]
        used = []
        for mark in finish_marks:
            regions, did = _split(regions, mark)
            if did:
                used.append(mark.correction_id)
                splits[mark.correction_id].append(ring.record_id)
        if used:
            for region in sorted(regions, key=lambda p: tuple(round(v, 4) for v in p.bounds)):
                finish_regions.append({"room_id": ring.record_id, "user_mark_ids": used, "polygon_pdf_pts": _coords(region),
                                       "area_pt2": round(region.area, 4)})
    for mark in finish_marks:
        room_ids = splits[mark.correction_id]
        outcomes[mark.correction_id] = {"outcome": "applied" if room_ids else "no_split", "room_ids": room_ids}

    barriers = unary_union([rect for _label, rect in plan.extra_rects]) if plan.extra_rects else None
    residual = []
    for item in endpoint_reviews:
        point = item.get("endpoint_pdf_pts")
        if item.get("status") not in RESIDUAL_STATUSES or not point:
            continue
        if barriers is not None and barriers.distance(Point(float(point[0]), float(point[1]))) <= SNAP_PT:
            continue  # covered by the user's own barrier: still not source-proven, so only dropped from the to-do list
        residual.append({"status": item["status"], "endpoint_pdf_pts": [float(point[0]), float(point[1])]})
    for mark in packet.marks:
        for point in outcomes[mark.correction_id].get("open_end_points_pdf_pts", []):
            residual.append({"status": OPEN_END_STATUS, "endpoint_pdf_pts": list(point), "correction_id": mark.correction_id})
    unique = {}
    for item in residual:
        key = stable_contract_id("user_review_residual", {
            "source_sha256": source_sha256, "page_index": page_index, "status": item["status"],
            "point": [round(v, 3) for v in item["endpoint_pdf_pts"]],
        }, digest_chars=24)
        unique.setdefault(key, {"id": key, **item})
    return {
        "schema_version": SCHEMA_VERSION,
        "producer": PRODUCER,
        "source_sha256": source_sha256,
        "page_index": page_index,
        "review_revision": packet.review_revision,
        "packet_sha256": packet.packet_sha256,
        "status": "applied",
        "reason_codes": [],
        "marks": [{"correction_id": m.correction_id, "category": m.category, "role": m.role, **outcomes[m.correction_id]}
                  for m in packet.marks],
        "automatic_room_count": len(automatic_rings),
        "user_assisted_room_count": len(rooms),
        "rooms": rooms,
        "finish_regions": finish_regions,
        "residual_locations": [unique[key] for key in sorted(unique)],
        **_no_authority(),
    }


def abstained_review_block(packet: ReviewPacket, *, source_sha256: str, page_index: int, reason: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION, "producer": PRODUCER, "source_sha256": source_sha256, "page_index": page_index,
        "review_revision": packet.review_revision, "packet_sha256": packet.packet_sha256, "status": "abstained",
        "reason_codes": [reason], "marks": [{"correction_id": m.correction_id, "category": m.category, "role": m.role,
                                             "outcome": "not_applied"} for m in packet.marks],
        "automatic_room_count": 0, "user_assisted_room_count": 0, "rooms": [], "finish_regions": [], "residual_locations": [],
        **_no_authority(),
    }


def _no_authority() -> dict[str, bool]:
    return {
        "user_assisted": True, "automatic_result_unchanged": True, "physical_wall_authenticated": False,
        "measurement_authorized": False, "quantity_authorized": False, "commercial_publishable": False,
        "frozen_benchmark_allowed": False,
    }
