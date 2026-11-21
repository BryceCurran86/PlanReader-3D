"""Review-only core: the TWO traced wall-end sections of one doorway, from native paths of ANY drawing convention.

The owner's two-wall rule (hub 7056071002 / 7056082708, AGENTS.md) tags every opening with the two traced wall sections
that terminate at it: the walls either side of a straight gap, or two sections meeting at a corner or junction, never one
elected host. ``pb_opening_two_wall_contact_tags`` owns that vocabulary and its matching rule. This module only builds
that contract's INPUTS from native path rows, and it is deliberately convention agnostic:

* a wall end is a GROUP of native paths: one filled polygon (a solid strip), two stroked face lines (an outlined wall),
  one hairline, or a cavity pocket drawn as two lips; the group's own straight edges decide where it ends;
* the contact is anchored on the OPENING'S OWN edge (a jamb return, or the door interval a swing or leaf proves), never
  on the wall: the wall end must reach that anchor within the contract's original-PDF tolerance;
* the two ends may face each other along one axis (straight gap) or sit on perpendicular axes (corner, junction, angled
  opening); the contract then classifies the geometry.

Nothing is elected by proximity, rank or order: a wall end with no anchor meeting it, two anchors that disagree, a
group that ends on two sides at once, ends that face the same way, walls that are not collinear across a straight gap, or
a wall whose end does not reach its faces all stay UNRESOLVED with a named reason. A tag built from these inputs is
topology only: no physical wall, host, frame, kind, width, height or quantity is authenticated here (limits kept
explicit: axis aligned wall ends only, an absolute contract tolerance rather than a scale-relative one, and a doorway at
the FACE of a passing wall, where no wall section ends, is reported rather than tagged).
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_opening_two_wall_contact_tags import (
    _SOURCE_ENDPOINT_TOL_PT,
    DetectedOpeningContacts,
    OpeningWallContact,
    TracedWallSection,
)
from pb_migration_contracts import stable_contract_id

TOL = _SOURCE_ENDPOINT_TOL_PT

GATE_GROUP_INVALID = "wall_end_group_invalid"
GATE_GROUPS_OVERLAP = "wall_end_groups_share_a_native_path"
GATE_ROW_UNREADABLE = "wall_end_path_row_unreadable"
GATE_ANCHOR_MISSING = "opening_edge_does_not_meet_wall_end"
GATE_ANCHORS_DISAGREE = "opening_edges_disagree_at_wall_end"
GATE_END_SIDES_COMPETING = "wall_end_group_meets_opening_on_two_sides"
GATE_END_EDGE_MISSING = "wall_end_does_not_reach_its_faces_at_the_opening_edge"
GATE_ENDS_NOT_OPPOSED = "wall_ends_do_not_face_each_other_across_the_gap"
GATE_NOT_COLLINEAR = "wall_ends_not_collinear_across_the_gap"
GATE_WALL_THROUGH_OPENING = "wall_runs_through_the_other_wall_contact"
GATE_OPENING_PATHS_MISSING = "opening_native_paths_missing"
GATE_NO_ANCHORS = "opening_edge_rectangles_missing"
GATE_FACE_NOT_END = "wall_end_group_is_far_thicker_than_the_opening_edge_a_wall_face_not_an_end"

# A wall END spans the wall thickness, and the opening's own jamb return or door interval crosses that thickness
# (a cavity-slider cap may cover only part of it). A group whose extent across the wall exceeds this multiple of the
# opening edge that meets it is the FACE of a longer, perpendicular wall, where no wall section ends. Scale free.
END_THICKNESS_TO_OPENING_EDGE_RATIO = 6.0

Rect = tuple[float, float, float, float]


@dataclass(frozen=True)
class WallEndReceipt:
    opening_id: str
    scope: tuple[str, ...]
    opening_native_path_ids: tuple[int, ...]
    first_wall_end_path_ids: tuple[int, ...]
    second_wall_end_path_ids: tuple[int, ...]
    anchors: tuple[Rect, ...]


@dataclass(frozen=True)
class Blocked:
    reason: str


def scope_ok(scope: object) -> bool:
    return (
        type(scope) is tuple and len(scope) >= 2
        and all(type(v) is str and bool(v.strip()) for v in scope)
    )


# ---------------------------------------------------------------------------------------------------------------------
# native path rows
# ---------------------------------------------------------------------------------------------------------------------


def row_rect(row: object) -> Rect | None:
    if not isinstance(row, Mapping):
        return None
    rect = row.get("rect")
    if rect is None:
        return None
    try:
        values = tuple(float(v) for v in rect)
    except (TypeError, ValueError, OverflowError):
        return None
    if len(values) != 4 or not all(math.isfinite(v) for v in values):
        return None
    if values[2] < values[0] or values[3] < values[1]:
        return None
    return values  # type: ignore[return-value]


def _xy(point: object) -> tuple[float, float] | None:
    try:
        x, y = float(point.x), float(point.y)  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError, OverflowError):
        try:
            x, y = float(point[0]), float(point[1])  # type: ignore[index]
        except (TypeError, ValueError, IndexError, OverflowError):
            return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) else None


def straight_segments(row: object) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """Every straight edge a native row draws: line items, rectangle sides and quad sides. Curves are ignored."""
    if not isinstance(row, Mapping):
        return []
    items = row.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return []
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for item in items:
        if not isinstance(item, Sequence) or isinstance(item, (str, bytes)) or not item:
            continue
        kind = item[0]
        if kind == "l" and len(item) >= 3:
            a, b = _xy(item[1]), _xy(item[2])
            if a is not None and b is not None:
                segments.append((a, b))
        elif kind == "re" and len(item) >= 2:
            try:
                x0, y0, x1, y1 = (float(v) for v in item[1])
            except (TypeError, ValueError, OverflowError):
                continue
            if all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
                segments.extend((corners[i], corners[(i + 1) % 4]) for i in range(4))
        elif kind == "qu" and len(item) >= 2:
            corners_q = [_xy(getattr(item[1], name, None)) for name in ("ul", "ur", "lr", "ll")]
            if all(c is not None for c in corners_q):
                segments.extend((corners_q[i], corners_q[(i + 1) % 4]) for i in range(4))  # type: ignore[arg-type]
    return segments


def _valid_ids(ids: object, row_count: int) -> bool:
    return (
        type(ids) is tuple and bool(ids)
        and all(type(i) is int and 0 <= i < row_count for i in ids)
        and len(ids) == len(set(ids))
    )


def _overlap(a0: float, a1: float, b0: float, b1: float) -> float:
    return min(a1, b1) - max(a0, b0)


# ---------------------------------------------------------------------------------------------------------------------
# one wall-end group
# ---------------------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _End:
    axis: int          # the wall runs along this axis
    high: bool         # True when the wall end is the HIGH side of the group (the wall body lies below it)
    coordinate: float  # where the wall ends along ``axis``
    far: float         # the group's other extreme along ``axis``
    cross: float       # centre line of the group across the wall (axis 1 - ``axis``)
    box: Rect


def _anchor_touches(
    box: Rect, axis: int, high: bool, anchor: Rect,
) -> tuple[float, float] | None:
    """The anchor's facing coordinate and its extent across the wall when it meets this side of the group, else None."""
    across = 1 - axis
    coordinate = box[axis + 2] if high else box[axis]
    # the anchor lies in the opening: beside a HIGH wall end it begins at that end, beside a LOW end it finishes there
    facing = anchor[axis] if high else anchor[axis + 2]
    if abs(facing - coordinate) > TOL:
        return None
    thick = box[across + 2] - box[across]
    if thick > TOL:
        if _overlap(anchor[across], anchor[across + 2], box[across], box[across + 2]) <= 0:
            return None
    else:  # a hairline wall has no thickness: the anchor must cross its line
        mid = (box[across] + box[across + 2]) / 2.0
        if not (anchor[across] - TOL <= mid <= anchor[across + 2] + TOL):
            return None
    return facing, anchor[across + 2] - anchor[across]


def _wall_end_reaches_faces(
    segments: Sequence[tuple[tuple[float, float], tuple[float, float]]],
    axis: int, coordinate: float, lo: float, hi: float,
) -> bool:
    """The group really ends at ``coordinate`` and reaches BOTH of its faces there. Evidence is an edge across the wall
    (a filled end, a cap line, a lip of a cavity pocket) or the end of a face line (an outlined wall); a cavity pocket is
    two lips with a gap between them, so the evidence is taken together, not as one edge."""
    across = 1 - axis
    positions_lo: list[float] = []
    positions_hi: list[float] = []
    for a, b in segments:
        a_on = abs(a[axis] - coordinate) <= TOL
        b_on = abs(b[axis] - coordinate) <= TOL
        if a_on and b_on:
            if abs(a[across] - b[across]) <= TOL:
                continue  # a point, not an edge across the wall
            positions_lo.append(min(a[across], b[across]))
            positions_hi.append(max(a[across], b[across]))
        elif a_on != b_on:
            # an edge that leaves the end line: only a face line parallel to the wall axis counts
            if abs(a[across] - b[across]) <= TOL:
                point = a if a_on else b
                positions_lo.append(point[across])
                positions_hi.append(point[across])
    return bool(positions_lo) and (
        min(positions_lo) <= lo + TOL and max(positions_hi) >= hi - TOL
    )


def _group_end(
    drawings: Sequence[Any], ids: tuple[int, ...], anchors: Sequence[Rect],
) -> _End | Blocked:
    rects: list[Rect] = []
    segments: list[tuple[tuple[float, float], tuple[float, float]]] = []
    for i in ids:
        rect = row_rect(drawings[i])
        if rect is None:
            return Blocked(GATE_ROW_UNREADABLE)
        rects.append(rect)
        segments.extend(straight_segments(drawings[i]))
    box: Rect = (
        min(r[0] for r in rects), min(r[1] for r in rects),
        max(r[2] for r in rects), max(r[3] for r in rects),
    )
    found: dict[tuple[int, bool], list[tuple[float, float]]] = {}
    for axis in (0, 1):
        for high in (False, True):
            for anchor in anchors:
                touch = _anchor_touches(box, axis, high, anchor)
                if touch is not None:
                    found.setdefault((axis, high), []).append(touch)
    if not found:
        return Blocked(GATE_ANCHOR_MISSING)
    if len(found) > 1:
        return Blocked(GATE_END_SIDES_COMPETING)
    (axis, high), touches = next(iter(found.items()))
    facings = [facing for facing, _ in touches]
    if max(facings) - min(facings) > TOL:
        return Blocked(GATE_ANCHORS_DISAGREE)
    across = 1 - axis
    thickness = box[across + 2] - box[across]
    if thickness > TOL and thickness > END_THICKNESS_TO_OPENING_EDGE_RATIO * max(length for _, length in touches):
        return Blocked(GATE_FACE_NOT_END)
    coordinate = box[axis + 2] if high else box[axis]
    if not _wall_end_reaches_faces(segments, axis, coordinate, box[across], box[across + 2]):
        return Blocked(GATE_END_EDGE_MISSING)
    return _End(
        axis=axis, high=high, coordinate=coordinate,
        far=box[axis] if high else box[axis + 2],
        cross=(box[across] + box[across + 2]) / 2.0,
        box=box,
    )


def _point(end: _End, along: float) -> tuple[float, float]:
    return (along, end.cross) if end.axis == 0 else (end.cross, along)


# ---------------------------------------------------------------------------------------------------------------------
# a doorway: two ends -> the contract's inputs
# ---------------------------------------------------------------------------------------------------------------------


def build_contract_inputs(
    drawings: Sequence[Any], receipt: WallEndReceipt,
) -> tuple[DetectedOpeningContacts, tuple[TracedWallSection, ...]] | Blocked:
    row_count = len(drawings)
    groups = (receipt.first_wall_end_path_ids, receipt.second_wall_end_path_ids)
    if not all(_valid_ids(g, row_count) for g in groups):
        return Blocked(GATE_GROUP_INVALID)
    if set(groups[0]) & set(groups[1]):
        return Blocked(GATE_GROUPS_OVERLAP)
    if not _valid_ids(receipt.opening_native_path_ids, row_count) or set(receipt.opening_native_path_ids) & (
        set(groups[0]) | set(groups[1])
    ):
        return Blocked(GATE_OPENING_PATHS_MISSING)
    anchors = tuple(a for a in receipt.anchors if isinstance(a, tuple) and len(a) == 4
                    and all(type(v) in (int, float) and math.isfinite(v) for v in a)
                    and a[2] >= a[0] and a[3] >= a[1])
    if not anchors:
        return Blocked(GATE_NO_ANCHORS)

    ends: list[_End] = []
    for group in groups:
        end = _group_end(drawings, group, anchors)
        if isinstance(end, Blocked):
            return end
        ends.append(end)
    e0, e1 = ends

    if e0.axis == e1.axis:
        if e0.high == e1.high:
            return Blocked(GATE_ENDS_NOT_OPPOSED)
        low, high = (e0, e1) if e0.high else (e1, e0)   # ``high`` flag True = the wall body is the LOWER one
        if high.coordinate - low.coordinate <= TOL:
            return Blocked(GATE_ENDS_NOT_OPPOSED)         # no gap: the ends touch or cross
        across = 1 - e0.axis
        if _overlap(e0.box[across], e0.box[across + 2], e1.box[across], e1.box[across + 2]) <= 0 and not (
            # hairlines share no thickness; they are collinear only when they lie on one line
            e0.box[across + 2] - e0.box[across] <= TOL and e1.box[across + 2] - e1.box[across] <= TOL
            and abs(e0.cross - e1.cross) <= TOL
        ):
            return Blocked(GATE_NOT_COLLINEAR)
    else:
        # perpendicular ends (a corner, a junction, an angled opening): each wall must run away from the other contact
        for mine, other in ((e0, e1), (e1, e0)):
            contact_other = _point(other, other.coordinate)
            contact_mine = _point(mine, mine.coordinate)
            body = -1.0 if mine.high else 1.0        # direction of the wall body along its own axis
            toward = contact_other[mine.axis] - contact_mine[mine.axis]
            if body * toward > TOL:
                return Blocked(GATE_WALL_THROUGH_OPENING)

    sections: list[TracedWallSection] = []
    contacts: list[OpeningWallContact] = []
    ordered = sorted(zip(groups, ends), key=lambda pair: min(pair[0]))
    for group, end in ordered:
        sections.append(TracedWallSection(
            stable_contract_id(
                "native_wall_end_section", {"scope": list(receipt.scope), "native_path_ids": sorted(group)},
            ),
            receipt.scope,
            tuple(sorted(group)),
            _point(end, end.far),
            _point(end, end.coordinate),
        ))
        contacts.append(OpeningWallContact(_point(end, end.coordinate), tuple(sorted(group))))
    return (
        DetectedOpeningContacts(
            receipt.opening_id, receipt.scope, tuple(sorted(receipt.opening_native_path_ids)),
            contacts[0], contacts[1],
        ),
        tuple(sections),
    )
