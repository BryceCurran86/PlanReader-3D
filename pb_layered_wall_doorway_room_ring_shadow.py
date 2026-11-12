"""Doorway-closed room rings from layered native wall ink (SHADOW ONLY, default-unwired).

Why this exists. On a layered CAD floor plan the wall layer already draws every room as a
ring of filled wall strips, but each door leaves a gap in the ring, so a planar-face
authority that only sees wall edges finds no room. This module reads ONE SHA-pinned page's
native drawings and answers a single question: which free-space regions are enclosed by
wall ink plus source-attested doorway closures, and which stay open?

What counts as evidence (all of it is original native ink on an explicit wall layer):

* wall strips: filled opaque-black axis-aligned rectangles (a ``re``/``qu`` item or a closed
  4-``l`` path). Anything else that is filled black on a wall layer is counted and flagged,
  never silently dropped.
* a source stroke closure: an unfilled axis-aligned stroke that lies on a wall face line and
  spans an interruption of that wall exactly end to end (a glazed or fixed opening drawn
  by the source). It closes the gap by the source's own ink.
* a sliding-leaf opening (its OWN default-off control, ``sliding_leaf_frame_closure``): a white frame
  box at EACH end of the interruption and exactly two overlapping leaf strokes between them, none of
  it painted over by a later opaque fill. A missing, duplicated, shifted or non-overlapping frame or
  leaf, ink on another layer, one stroke shared by two openings, or a second doorway claim in the same
  interruption all abstain;
* a swing doorway: a single circular quarter-arc (``c``) with a leaf stroke from its centre
  to one arc end; the other arc end is the closed-door tip. The doorway is the MAXIMAL
  interruption of the wall line (between two wall strips of one band) that contains the
  closed-door segment. It is unique by construction: no nearest, first or smallest choice.

An interruption with no such evidence is never closed. A free-space region adjacent to one
is reported ``open_wall_gap_unresolved``; a region that reaches the page frame of the wall
ink is ``open_to_exterior``. Nothing is snapped beyond 0.05 pt of representation noise (the
2.5 pt production snap and the 20,000 primitive cap are untouched). A closure is a barrier
for planarization only: it is never a wall, has no length, host or deduction, and places the
floor boundary at the threshold, so a finish never runs under a wall.

Grants no authority: status CANDIDATE, ``takeoff_eligible=False``,
``commercial_projection_allowed=False``. No physical room identity, scale, area, finish or
quantity is issued. Imported by no live path.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import math
from typing import Any, Iterable, Mapping, Optional, Sequence

from shapely.geometry import Point, Polygon, box
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name

LAYERED_ROOM_RING_SCHEMA_VERSION = "1.0.0"

NOISE_PT = 0.05  # representation noise only; NOT the 2.5 pt production snap
_CLOSING_PT = 0.03  # hairline closing between exactly shared strip edges
_BLACK_MAX = 0.04
_ARC_CIRCULARITY = 0.002  # relative; a cubic Bezier quarter circle deviates by about 0.0003

REASON_RING_CLOSED = "layered_wall_ring_closed_by_source_ink"
REASON_OPEN_GAP = "open_wall_gap_unresolved"
REASON_OPEN_EXTERIOR = "open_to_exterior"
REASON_NO_WALL_INK = "no_wall_layer_strips"
REASON_PRIMITIVE_CAP = "page_primitive_cap_exceeded"
_PRIMITIVE_CAP = 20000
_STROKE_PAIR_THICK_MIN = 1.2
_STROKE_PAIR_THICK_MAX = 8.0
_DARK_FILL_THICK_MIN = 1.2
_DARK_FILL_THICK_MAX = 14.0  # GPT A120 dark-wall witness band; not the 2.5 pt snap
_STROKE_PAIR_MIN_SPAN = 8.0
_WALL_END_SUPPORT_SPAN = 80.0  # PDF-pt CANDIDATE heuristic only; not a physical wall
_WALL_END_CLOSER_SPAN = 20.0
_STROKE_PAIR_FACE_PT = 0.35
_STROKE_PAIR_CLUSTER_PT = 0.8  # CAD double-stroke faces; never the 2.5 pt snap
REASON_UNOWNED_EDGE = "ring_edge_without_source_owner"
REASON_SOURCE_HASH = "source_sha256_mismatch"

KIND_SWING = "swing_doorway"
KIND_STROKE = "source_stroke_closure"
KIND_SLIDING_LEAF = "sliding_leaf_frame_closure"
KIND_CAVITY_SLIDER = "cavity_slider_cs_closure"
KIND_PANEL_LIFT = "panel_lift_door_topology_closure"

_RECORD_SEAL = object()


def _xy(point: Any) -> tuple[float, float]:
    return float(point.x), float(point.y)


def _is_black(color: Any) -> bool:
    return (
        isinstance(color, (tuple, list))
        and len(color) == 3
        and all(type(v) in (int, float) and math.isfinite(v) and 0.0 <= v <= _BLACK_MAX for v in color)
    )


_DARK_FILL_MAX = 0.25  # A120 structural fills are ~0.195 gray; white masks are 1.0


def _is_dark_structural_fill(color: Any) -> bool:
    """Opaque dark-gray/black fill, not a white layout mask and not a light hatch."""
    if not (
        isinstance(color, (tuple, list))
        and len(color) == 3
        and all(type(v) in (int, float) and math.isfinite(v) and 0.0 <= v <= _DARK_FILL_MAX for v in color)
    ):
        return False
    return (max(color) - min(color)) <= _BLACK_MAX


def _close(a: float, b: float, tol: float = NOISE_PT) -> bool:
    return abs(a - b) <= tol


def _rect_of_item(item: Sequence[Any]) -> Optional[tuple[float, float, float, float]]:
    kind = item[0]
    if kind == "re":
        r = item[1]
        return float(r.x0), float(r.y0), float(r.x1), float(r.y1)
    if kind == "qu":
        q = item[1]
        pts = [_xy(q.ul), _xy(q.ur), _xy(q.lr), _xy(q.ll)]
        xs = sorted({round(p[0], 6) for p in pts})
        ys = sorted({round(p[1], 6) for p in pts})
        if len(xs) != 2 or len(ys) != 2:
            return None
        return xs[0], ys[0], xs[1], ys[1]
    return None


def _rect_of_closed_line_path(items: Sequence[Sequence[Any]]) -> Optional[tuple[float, float, float, float]]:
    if len(items) != 4 or any(it[0] != "l" for it in items):
        return None
    pts = []
    for it in items:
        pts.append(_xy(it[1]))
        pts.append(_xy(it[2]))
    xs = sorted({round(p[0], 4) for p in pts})
    ys = sorted({round(p[1], 4) for p in pts})
    if len(xs) != 2 or len(ys) != 2:
        return None
    for it in items:
        (ax, ay), (bx, by) = _xy(it[1]), _xy(it[2])
        if not ((_close(ax, bx, 1e-3) and not _close(ay, by, 1e-3)) or (_close(ay, by, 1e-3) and not _close(ax, bx, 1e-3))):
            return None
    return xs[0], ys[0], xs[1], ys[1]


@dataclass(frozen=True)
class _Strip:
    path_index: int
    x0: float
    y0: float
    x1: float
    y1: float
    polygon: Any = None  # exact outline (mitred ends keep their shape); bbox drives run analysis only
    forced: Optional[str] = None  # "h"/"v": a jamb cap takes the orientation of the wall it ends
    path_indices: tuple[int, ...] = ()

    def native_path_indices(self) -> tuple[int, ...]:
        if self.path_indices:
            return tuple(sorted(set(self.path_indices)))
        return (self.path_index,)

    @property
    def horizontal(self) -> bool:
        if self.forced is not None:
            return self.forced == "h"
        return (self.x1 - self.x0) > (self.y1 - self.y0) + NOISE_PT

    @property
    def vertical(self) -> bool:
        if self.forced is not None:
            return self.forced == "v"
        return (self.y1 - self.y0) > (self.x1 - self.x0) + NOISE_PT

    def band(self) -> tuple[float, float]:
        return (self.y0, self.y1) if self.horizontal else (self.x0, self.x1)

    def span(self) -> tuple[float, float]:
        return (self.x0, self.x1) if self.horizontal else (self.y0, self.y1)


@dataclass(frozen=True)
class _Gap:
    horizontal: bool
    band: tuple[float, float]
    lo: float
    hi: float
    left_path_indices: tuple[int, ...]
    right_path_indices: tuple[int, ...]
    collinear: bool = False  # both ends are wall runs of this very band (an interruption of one wall)

    def rect(self) -> Polygon:
        if self.horizontal:
            return box(self.lo, self.band[0], self.hi, self.band[1])
        return box(self.band[0], self.lo, self.band[1], self.hi)


@dataclass(frozen=True)
class LayeredDoorwayClosure:
    closure_id: str
    kind: str
    horizontal: bool
    band: tuple[float, float]
    gap_interval: tuple[float, float]
    native_path_indices: tuple[int, ...]
    wall_path_indices: tuple[int, ...]
    # Original native text witnesses for a panel door; these are not wall geometry.
    native_word_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class LayeredRoomRingRecord:
    record_id: str
    source_sha256: str
    page_index: int
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    hole_count: int
    area_pt2: float
    bbox_pdf_pts: tuple[float, float, float, float]
    wall_edge_count: int
    closure_edge_count: int
    bounding_closure_ids: tuple[str, ...]
    bounding_wall_path_indices: tuple[int, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    # One tuple of owner ids per polygon edge: wall strips/fills by native path index, or a doorway closure.
    edge_owner_ids: tuple[tuple[str, ...], ...] = ()
    schema_version: str = LAYERED_ROOM_RING_SCHEMA_VERSION
    takeoff_eligible: bool = False
    commercial_projection_allowed: bool = False
    diagnostic_only: bool = True
    physical_room_identity_issued: bool = False
    metric_area_issued: bool = False
    floor_finish_issued: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("LayeredRoomRingRecord is producer-owned")


@dataclass(frozen=True)
class LayeredRoomRingResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    rings: tuple[LayeredRoomRingRecord, ...]
    closures: tuple[LayeredDoorwayClosure, ...]
    wall_strip_count: int
    wall_gap_count: int
    unresolved_gap_count: int
    non_strip_wall_fill_count: int
    unplaced_swing_count: int
    ambiguous_swing_count: int
    sliver_region_count: int = 0
    schema_version: str = LAYERED_ROOM_RING_SCHEMA_VERSION


def _wall_rows(drawings: Sequence[Mapping[str, Any] | None]) -> Iterable[tuple[int, Mapping[str, Any]]]:
    for index, row in enumerate(drawings):
        if row is None:
            continue
        if is_explicit_wall_layer_name(str(row.get("layer") or "")):
            yield index, row


def _source_rows(
    drawings: Sequence[Mapping[str, Any] | None], *, all_ink: bool,
) -> Iterable[tuple[int, Mapping[str, Any]]]:
    if all_ink:
        for index, row in enumerate(drawings):
            if row is not None:
                yield index, row
        return
    yield from _wall_rows(drawings)


def _drawing_bbox(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    rect = row.get("rect")
    try:
        return float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
    except (AttributeError, TypeError, ValueError):
        return None


def _intersects_viewport(
    row: Mapping[str, Any], viewport: tuple[float, float, float, float],
) -> bool:
    bbox = _drawing_bbox(row)
    if bbox is None:
        return False
    x0, y0, x1, y1 = bbox
    vx0, vy0, vx1, vy1 = viewport
    return not (x1 < vx0 or x0 > vx1 or y1 < vy0 or y0 > vy1)


def _selected_primitive_count(drawings: Sequence[Mapping[str, Any] | None]) -> int:
    """Count native items on selected drawings, not drawing-row count."""
    total = 0
    for row in drawings:
        if row is None:
            continue
        items = row.get("items")
        if not items:
            continue
        total += len(items)
        if total > _PRIMITIVE_CAP:
            return total
    return total


def _as_viewports(
    viewport: tuple[float, float, float, float] | Sequence[tuple[float, float, float, float]] | None,
) -> list[tuple[float, float, float, float]] | None:
    if viewport is None:
        return None
    if len(viewport) == 4 and not isinstance(viewport[0], (tuple, list)):
        x0, y0, x1, y1 = (float(value) for value in viewport)
        return [(x0, y0, x1, y1)]
    return [tuple(float(value) for value in item) for item in viewport]


def _clip_drawings(
    drawings: Sequence[Mapping[str, Any]],
    viewport: tuple[float, float, float, float] | Sequence[tuple[float, float, float, float]] | None,
) -> list[Mapping[str, Any] | None]:
    """Keep original path indices; drop out-of-viewport rows as None."""
    viewports = _as_viewports(viewport)
    if viewports is None:
        return list(drawings)
    clipped: list[Mapping[str, Any] | None] = []
    for row in drawings:
        clipped.append(row if any(_intersects_viewport(row, item) for item in viewports) else None)
    return clipped


def _bbox_intersects(
    bbox: tuple[float, float, float, float],
    viewport: tuple[float, float, float, float],
) -> bool:
    x0, y0, x1, y1 = bbox
    vx0, vy0, vx1, vy1 = viewport
    return not (x1 < vx0 or x0 > vx1 or y1 < vy0 or y0 > vy1)


def _item_bbox(item: Sequence[Any]) -> tuple[float, float, float, float] | None:
    kind = item[0] if item else None
    if kind == "l" and len(item) >= 3:
        (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
    rect = _rect_of_item(item)
    if rect is not None:
        return rect
    if kind == "c" and len(item) >= 5:
        pts = [_xy(item[i]) for i in range(1, 5)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    return None


def _clip_drawing_items(
    drawings: Sequence[Mapping[str, Any] | None],
    viewport: tuple[float, float, float, float] | Sequence[tuple[float, float, float, float]] | None,
) -> list[Mapping[str, Any] | None]:
    """Keep original path indices; count/pair only items that intersect the clip.

    A drawing path whose bbox merely overlaps a labelled neighbourhood must not
    contribute its far-page primitives to the 20,000-item cap. This is not a
    raised limit and not a wall layer.
    """
    viewports = _as_viewports(viewport)
    if viewports is None:
        return list(drawings)
    clipped: list[Mapping[str, Any] | None] = []
    for row in drawings:
        if row is None:
            clipped.append(None)
            continue
        kept: list[Any] = []
        for item in row.get("items", ()):
            bbox = _item_bbox(item)
            if bbox is None:
                if any(_intersects_viewport(row, vp) for vp in viewports):
                    kept.append(item)
                continue
            if any(_bbox_intersects(bbox, vp) for vp in viewports):
                kept.append(item)
        if not kept:
            clipped.append(None)
            continue
        copied = dict(row)
        copied["items"] = kept
        clipped.append(copied)
    return clipped


_STROKE_PAIR_HALO_PT = 160.0
_STROKE_PAIR_GROW_PAD_PT = 2.0


def _strip_intersects_box(strip: _Strip, box: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = box
    return not (strip.x1 < x0 or strip.x0 > x1 or strip.y1 < y0 or strip.y0 > y1)


def _strips_touch(left: _Strip, right: _Strip) -> bool:
    """Representation-noise contact only. Never the 2.5 pt production snap."""
    return not (
        left.x1 + NOISE_PT < right.x0
        or left.x0 - NOISE_PT > right.x1
        or left.y1 + NOISE_PT < right.y0
        or left.y0 - NOISE_PT > right.y1
    )


def _halo_box(
    seed: tuple[float, float, float, float], pad: float,
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = seed
    return (x0 - pad, y0 - pad, x1 + pad, y1 + pad)


def _clip_if_under_cap(
    drawings: Sequence[Mapping[str, Any]],
    box: tuple[float, float, float, float],
) -> list[Mapping[str, Any] | None] | None:
    clipped = _clip_drawing_items(drawings, box)
    if _selected_primitive_count(clipped) > _PRIMITIVE_CAP:
        return None
    return clipped


def _largest_halo_under_cap(
    drawings: Sequence[Mapping[str, Any]],
    seed: tuple[float, float, float, float],
) -> tuple[tuple[float, float, float, float], list[Mapping[str, Any] | None]] | None:
    """Largest pad ≤ 160 pt whose item-clipped halo stays inside the 20k cap.

    One extra primitive at the 160 pt rim must not discard the whole
    neighbourhood. This does not raise the cap and is not a wall layer.
    """
    full = _clip_if_under_cap(drawings, _halo_box(seed, _STROKE_PAIR_HALO_PT))
    if full is not None:
        return _halo_box(seed, _STROKE_PAIR_HALO_PT), full
    lo, hi = 0.0, _STROKE_PAIR_HALO_PT
    best: tuple[tuple[float, float, float, float], list[Mapping[str, Any] | None]] | None = None
    for _ in range(12):
        pad = (lo + hi) / 2.0
        box = _halo_box(seed, pad)
        clipped = _clip_if_under_cap(drawings, box)
        if clipped is None:
            hi = pad
            continue
        best = (box, clipped)
        lo = pad
    return best


def expand_labelled_stroke_pair_viewports(
    drawings: Sequence[Mapping[str, Any]],
    seeds: Sequence[tuple[float, float, float, float]],
) -> list[tuple[float, float, float, float]]:
    """Grow a labelled neighbourhood along unique connected stroke-pair strips.

    Pairing looks at a bounded halo around the label cluster, then keeps only
    strips that touch the seed or uniquely abut those strips. Page-hull clips
    and over-cap expansions are rejected. Topology only; not a wall layer.
    """
    grown: list[tuple[float, float, float, float]] = []
    for seed in seeds:
        x0, y0, x1, y1 = (float(value) for value in seed)
        seed_box = (x0, y0, x1, y1)
        current = seed_box
        expanded = seed_box
        for _ in range(12):
            halo_hit = _largest_halo_under_cap(drawings, current)
            if halo_hit is None:
                break
            halo, clipped = halo_hit
            filled, _other = _collect_strips(clipped)
            strips = (
                _collect_stroke_pair_strips(clipped)
                + list(filled)
                + _collect_dark_fill_strips(clipped)
            )
            kept = [strip for strip in strips if _strip_intersects_box(strip, current)]
            if not kept:
                kept = [strip for strip in strips if _strip_intersects_box(strip, halo)]
            if not kept:
                break
            frontier = list(kept)
            while frontier:
                node = frontier.pop()
                for candidate in strips:
                    if candidate in kept:
                        continue
                    if _strips_touch(node, candidate):
                        kept.append(candidate)
                        frontier.append(candidate)
            pad = _STROKE_PAIR_GROW_PAD_PT
            nxt = (
                min(x0, min(strip.x0 for strip in kept) - pad),
                min(y0, min(strip.y0 for strip in kept) - pad),
                max(x1, max(strip.x1 for strip in kept) + pad),
                max(y1, max(strip.y1 for strip in kept) + pad),
            )
            if _selected_primitive_count(_clip_drawing_items(drawings, nxt)) > _PRIMITIVE_CAP:
                nxt = (
                    min(x0, min(strip.x0 for strip in kept)),
                    min(y0, min(strip.y0 for strip in kept)),
                    max(x1, max(strip.x1 for strip in kept)),
                    max(y1, max(strip.y1 for strip in kept)),
                )
                if _selected_primitive_count(_clip_drawing_items(drawings, nxt)) > _PRIMITIVE_CAP:
                    break
            if max(abs(a - b) for a, b in zip(nxt, current)) <= NOISE_PT:
                expanded = nxt
                break
            current = nxt
            expanded = nxt
        grown.append(expanded)
    return grown


def _is_wall_stroke_color(color: Any) -> bool:
    """Default CAD stroke (None) or opaque black. Grey grid and green hatch are not walls."""
    return color is None or _is_black(color)


def _axis_strokes(
    drawings: Sequence[Mapping[str, Any] | None],
) -> list[tuple[int, bool, float, float, float]]:
    """Axis-aligned black wall strokes, shorts merged collinearly before the 8 pt span gate.

    Double-drawn CAD faces (~0.48 pt) collapse to one perp. Door-sized gaps stay open.
    """
    raw: list[tuple[int, bool, float, float, float]] = []
    for index, row in enumerate(drawings):
        if row is None or row.get("fill") is not None:
            continue
        if not _is_wall_stroke_color(row.get("color")):
            continue
        for item in row.get("items", ()):
            if item[0] != "l":
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if _close(ay, by, 1e-3) and abs(bx - ax) > NOISE_PT:
                lo, hi = sorted((ax, bx))
                raw.append((index, True, (ay + by) / 2.0, lo, hi))
            elif _close(ax, bx, 1e-3) and abs(by - ay) > NOISE_PT:
                lo, hi = sorted((ay, by))
                raw.append((index, False, (ax + bx) / 2.0, lo, hi))
    merged: list[tuple[int, bool, float, float, float]] = []
    for horiz in (True, False):
        members = [item for item in raw if item[1] is horiz]
        members.sort(key=lambda item: (item[2], item[3], item[4]))
        groups: list[list[tuple[int, bool, float, float, float]]] = []
        for stroke in members:
            if groups and abs(stroke[2] - groups[-1][0][2]) <= _STROKE_PAIR_CLUSTER_PT:
                groups[-1].append(stroke)
                continue
            groups.append([stroke])
        for group in groups:
            ordered = sorted(group, key=lambda item: (item[3], item[4]))
            run = [ordered[0]]
            lo, hi = ordered[0][3], ordered[0][4]
            for stroke in ordered[1:]:
                if stroke[3] <= hi + _STROKE_PAIR_CLUSTER_PT:
                    run.append(stroke)
                    hi = max(hi, stroke[4])
                    continue
                if hi - lo >= _STROKE_PAIR_MIN_SPAN:
                    perp = sum(item[2] for item in run) / len(run)
                    for item in run:
                        merged.append((item[0], horiz, perp, lo, hi))
                run = [stroke]
                lo, hi = stroke[3], stroke[4]
            if hi - lo >= _STROKE_PAIR_MIN_SPAN:
                perp = sum(item[2] for item in run) / len(run)
                for item in run:
                    merged.append((item[0], horiz, perp, lo, hi))
    return merged


def _stroke_partners(
    stroke: tuple[int, bool, float, float, float],
    pool: Sequence[tuple[int, bool, float, float, float]],
    *,
    lo: float | None = None,
    hi: float | None = None,
) -> list[tuple[int, bool, float, float, float]]:
    found: list[tuple[int, bool, float, float, float]] = []
    _index, _horiz, perp, stroke_lo, stroke_hi = stroke
    lo = stroke_lo if lo is None else lo
    hi = stroke_hi if hi is None else hi
    span = hi - lo
    if span < _STROKE_PAIR_MIN_SPAN:
        return found
    for other in pool:
        if other == stroke or other[0] == _index:
            continue
        gap = abs(other[2] - perp)
        if gap < _STROKE_PAIR_THICK_MIN or gap > _STROKE_PAIR_THICK_MAX:
            continue
        overlap = min(hi, other[4]) - max(lo, other[3])
        shorter = min(span, other[4] - other[3])
        if shorter > 0 and overlap >= 0.7 * shorter:
            found.append(other)
    return found


def _cluster_strokes_by_perp(
    strokes: Sequence[tuple[int, bool, float, float, float]],
) -> list[tuple[float, list[tuple[int, bool, float, float, float]]]]:
    grouped: list[tuple[float, list[tuple[int, bool, float, float, float]]]] = []
    for stroke in sorted(strokes, key=lambda item: item[2]):
        if grouped and abs(stroke[2] - grouped[-1][0]) <= _STROKE_PAIR_CLUSTER_PT:
            grouped[-1][1].append(stroke)
            continue
        grouped.append((stroke[2], [stroke]))
    return grouped


def _partner_face_clusters(
    stroke: tuple[int, bool, float, float, float],
    pool: Sequence[tuple[int, bool, float, float, float]],
    *,
    lo: float | None = None,
    hi: float | None = None,
) -> list[tuple[float, list[tuple[int, bool, float, float, float]]]]:
    return _cluster_strokes_by_perp(_stroke_partners(stroke, pool, lo=lo, hi=hi))


def _merged_along_spans(
    strokes: Sequence[tuple[int, bool, float, float, float]],
) -> list[tuple[float, float]]:
    ordered = sorted((stroke[3], stroke[4]) for stroke in strokes)
    merged: list[tuple[float, float]] = []
    for lo, hi in ordered:
        if merged and lo <= merged[-1][1] + _STROKE_PAIR_CLUSTER_PT:
            merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
        else:
            merged.append((lo, hi))
    return merged


def _collect_stroke_pair_strips(
    drawings: Sequence[Mapping[str, Any] | None],
) -> list[_Strip]:
    """Unlabelled parallel stroke pairs as topology-only wall-face candidates.

    These are not an authenticated wall layer. Ambiguous three-line hatch and
    over-thick furniture pairs are left unpaired. Split collinear ink on the
    same opposite face is one face, not several rival partners.
    """
    strokes = _axis_strokes(drawings)
    strips: list[_Strip] = []
    seen: set[tuple[float, float, float, float]] = set()
    by_dir = {True: [s for s in strokes if s[1]], False: [s for s in strokes if not s[1]]}
    for horiz, pool in by_dir.items():
        for stroke in pool:
            clusters = _partner_face_clusters(stroke, pool)
            if len(clusters) != 1:
                continue
            _opp_perp, partners = clusters[0]
            window_lo, window_hi = stroke[3], stroke[4]
            if any(
                len(_partner_face_clusters(other, pool, lo=window_lo, hi=window_hi)) != 1
                for other in partners
            ):
                continue
            members = (stroke,) + tuple(partners)
            perps = sorted(item[2] for item in members)
            low_perp, high_perp = perps[0], perps[-1]
            if high_perp - low_perp < _STROKE_PAIR_THICK_MIN:
                continue
            low_face = [item for item in members if abs(item[2] - low_perp) <= _STROKE_PAIR_CLUSTER_PT]
            high_face = [item for item in members if abs(item[2] - high_perp) <= _STROKE_PAIR_CLUSTER_PT]
            for lo0, hi0 in _merged_along_spans(low_face):
                for lo1, hi1 in _merged_along_spans(high_face):
                    lo, hi = max(lo0, lo1), min(hi0, hi1)
                    if hi - lo < _STROKE_PAIR_MIN_SPAN:
                        continue
                    if horiz:
                        x0, x1, y0, y1 = lo, hi, low_perp, high_perp
                    else:
                        x0, x1, y0, y1 = low_perp, high_perp, lo, hi
                    key = (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
                    if key in seen:
                        continue
                    seen.add(key)
                    covering = [
                        item for item in members
                        if min(item[4], hi) - max(item[3], lo) > _STROKE_PAIR_FACE_PT
                    ]
                    paths = tuple(sorted({item[0] for item in covering} or {stroke[0]}))
                    polygon = box(x0, y0, x1, y1)
                    strips.append(_Strip(paths[0], x0, y0, x1, y1, polygon, path_indices=paths))
    # Both face directions can propose the same wall, or a long face can
    # propose a full span in addition to its individually paired collinear
    # subspans. Keep only maximal, source-consistent spans on each band.
    # Otherwise one real wall is reconstructed twice and may inflate counts
    # or make the same edge carry mutually inconsistent source owners.
    by_band: dict[tuple[bool, float, float], list[_Strip]] = {}
    for strip in strips:
        band = strip.band()
        key = (strip.horizontal, round(band[0], 3), round(band[1], 3))
        by_band.setdefault(key, []).append(strip)
    maximal: list[_Strip] = []
    for group in by_band.values():
        accepted: list[_Strip] = []
        for strip in sorted(group, key=lambda item: (-(item.span()[1] - item.span()[0]), item.span())):
            span_lo, span_hi = strip.span()
            refs = set(strip.native_path_indices())
            if any(
                (prior.span()[0] <= span_lo + _STROKE_PAIR_FACE_PT)
                and (prior.span()[1] >= span_hi - _STROKE_PAIR_FACE_PT)
                and refs.issubset(prior.native_path_indices())
                for prior in accepted
            ):
                continue
            accepted.append(strip)
        maximal.extend(accepted)
    return maximal


def _polygon_of_closed_line_path(items: Sequence[Sequence[Any]]) -> Optional[Polygon]:
    """Exact outline of a closed straight-line path (any simple polygon), else None."""
    if len(items) < 3 or any(it[0] != "l" for it in items):
        return None
    pts = [_xy(items[0][1])]
    for it in items:
        end = _xy(it[2])
        if _close(end[0], pts[0][0], 1e-3) and _close(end[1], pts[0][1], 1e-3):
            break
        pts.append(end)
    if len(pts) < 3 or not all(math.isfinite(v) for p in pts for v in p):
        return None
    polygon = Polygon(pts)
    return polygon if polygon.is_valid and polygon.area > 0.0 else None


def _collect_strips(drawings: Sequence[Mapping[str, Any]]) -> tuple[list[_Strip], list[tuple[int, Polygon]]]:
    """Filled opaque-black wall-layer paths. Near-rectangular ones (rectangles and mitred strips whose
    outline fills at least 85% of its bounding box) are strips for run/gap analysis; every other
    filled shape is kept as a plain barrier polygon and counted, never dropped."""
    strips: list[_Strip] = []
    other: list[tuple[int, Polygon]] = []
    for index, row in _wall_rows(drawings):
        fill = row.get("fill")
        if fill is None or not _is_black(fill):
            continue
        items = list(row.get("items", ()))
        shapes: list[Polygon] = []
        for item in items:
            rect = _rect_of_item(item)
            if rect is not None and rect[2] > rect[0] and rect[3] > rect[1]:
                shapes.append(box(*rect))
        if not shapes:
            polygon = _polygon_of_closed_line_path(items)
            if polygon is not None:
                shapes.append(polygon)
        for polygon in shapes:
            x0, y0, x1, y1 = polygon.bounds
            bbox_area = (x1 - x0) * (y1 - y0)
            if bbox_area > 0.0 and polygon.area >= 0.85 * bbox_area:
                strips.append(_Strip(index, x0, y0, x1, y1, polygon))
            else:
                other.append((index, polygon))
    return _attach_caps(strips), other


def _collect_dark_fill_strips(
    drawings: Sequence[Mapping[str, Any] | None],
) -> list[_Strip]:
    """Unlabelled dark-filled thin rectangles as topology-only wall strips.

    A120 paints structural walls as opaque ~0.195 gray ``re`` fills with no
    wall layer and often no stroke. White layout masks stay out. This is not
    a wall layer and not a finished-face quantity.
    """
    strips: list[_Strip] = []
    for index, row in enumerate(drawings):
        if row is None:
            continue
        fill = row.get("fill")
        if fill is None or not _is_dark_structural_fill(fill) or not _opaque(row):
            continue
        if row.get("color") is not None:
            continue
        for item in row.get("items", ()):
            rect = _rect_of_item(item)
            if rect is None:
                continue
            x0, y0, x1, y1 = rect
            width, height = x1 - x0, y1 - y0
            thick, span = min(width, height), max(width, height)
            if thick < _DARK_FILL_THICK_MIN or thick > _DARK_FILL_THICK_MAX:
                continue
            if span < _STROKE_PAIR_MIN_SPAN:
                continue
            strips.append(_Strip(index, x0, y0, x1, y1, box(x0, y0, x1, y1)))
    return _attach_caps(strips)


def _major_structural_strips(strips: Sequence[_Strip]) -> list[_Strip]:
    """Long thick wall runs. Short ceiling-grid modules are not supports."""
    major: list[_Strip] = []
    for strip in strips:
        thick = min(strip.x1 - strip.x0, strip.y1 - strip.y0)
        span = max(strip.x1 - strip.x0, strip.y1 - strip.y0)
        if span >= _WALL_END_SUPPORT_SPAN and _STROKE_PAIR_THICK_MIN <= thick <= _DARK_FILL_THICK_MAX:
            major.append(strip)
    return major


def _collect_wall_end_closing_strips(
    drawings: Sequence[Mapping[str, Any] | None],
    strips: Sequence[_Strip],
) -> list[_Strip]:
    """Single black strokes that already meet two major walls at their native ends.

    The stroke is not extended, snapped, or prolonged through an unsupported
    field. A line that only meets one wall, or that rides a ceiling-grid
    module, is not a closer. This is topology-only; it is not a wall quantity.
    """
    supports = _major_structural_strips(strips)
    if len(supports) < 2:
        return []
    half = _STROKE_PAIR_THICK_MIN / 2.0
    found: list[_Strip] = []
    seen: set[tuple[float, float, float, float]] = set()
    for index, row in enumerate(drawings):
        if row is None or row.get("fill") is not None:
            continue
        if not _is_wall_stroke_color(row.get("color")):
            continue
        for item in row.get("items", ()):
            if item[0] != "l":
                continue
            ax, ay = _xy(item[1])
            bx, by = _xy(item[2])
            horizontal = _close(ay, by, 1e-3) and abs(bx - ax) >= _WALL_END_CLOSER_SPAN
            vertical = _close(ax, bx, 1e-3) and abs(by - ay) >= _WALL_END_CLOSER_SPAN
            if not horizontal and not vertical:
                continue
            start = Point(ax, ay)
            end = Point(bx, by)
            mid = Point((ax + bx) / 2.0, (ay + by) / 2.0)
            hits_a = [s for s in supports if s.polygon.distance(start) <= _STROKE_PAIR_FACE_PT]
            hits_b = [s for s in supports if s.polygon.distance(end) <= _STROKE_PAIR_FACE_PT]
            if not hits_a or not hits_b:
                continue
            if set(id(s) for s in hits_a) & set(id(s) for s in hits_b):
                continue
            if any(s.polygon.distance(mid) <= _STROKE_PAIR_FACE_PT for s in supports):
                continue
            if horizontal:
                if not any(s.vertical for s in hits_a) or not any(s.vertical for s in hits_b):
                    continue
                y = (ay + by) / 2.0
                x0, x1 = sorted((ax, bx))
                x0_b, y0_b, x1_b, y1_b = x0, y - half, x1, y + half
                # Close CAD double-stroke misalignment to the already-hit wall, never past 0.8 pt.
                for strip in hits_a + hits_b:
                    if not strip.vertical:
                        continue
                    if 0.0 < x0_b - strip.x1 <= _STROKE_PAIR_CLUSTER_PT:
                        x0_b = strip.x1
                    if 0.0 < strip.x0 - x1_b <= _STROKE_PAIR_CLUSTER_PT:
                        x1_b = strip.x0
            else:
                if not any(s.horizontal for s in hits_a) or not any(s.horizontal for s in hits_b):
                    continue
                x = (ax + bx) / 2.0
                y0, y1 = sorted((ay, by))
                x0_b, y0_b, x1_b, y1_b = x - half, y0, x + half, y1
                for strip in hits_a + hits_b:
                    if not strip.horizontal:
                        continue
                    if 0.0 < y0_b - strip.y1 <= _STROKE_PAIR_CLUSTER_PT:
                        y0_b = strip.y1
                    if 0.0 < strip.y0 - y1_b <= _STROKE_PAIR_CLUSTER_PT:
                        y1_b = strip.y0
            key = (round(x0_b, 2), round(y0_b, 2), round(x1_b, 2), round(y1_b, 2))
            if key in seen:
                continue
            seen.add(key)
            found.append(_Strip(index, x0_b, y0_b, x1_b, y1_b, box(x0_b, y0_b, x1_b, y1_b)))
    return found


def _attach_caps(strips: list[_Strip]) -> list[_Strip]:
    """A strip drawn across the END of a wall (same band as that wall, touching it end to end)
    belongs to that wall's run whatever its own aspect ratio; otherwise it would read as a
    one-piece wall of the perpendicular orientation and fake an interruption. Caps may chain
    (a cap beside a cap), so this runs to a fixed point."""
    current = list(strips)
    for _ in range(len(current)):
        changed = False
        for index, strip in enumerate(current):
            for other in current:
                if other is strip:
                    continue
                if other.vertical and not strip.vertical and _close(strip.x0, other.x0, 0.02) and _close(strip.x1, other.x1, 0.02)                         and (_close(strip.y0, other.y1) or _close(strip.y1, other.y0)):
                    forced = "v"
                elif other.horizontal and not strip.horizontal and _close(strip.y0, other.y0, 0.02) and _close(strip.y1, other.y1, 0.02)                         and (_close(strip.x0, other.x1) or _close(strip.x1, other.x0)):
                    forced = "h"
                else:
                    continue
                current[index] = _Strip(
                    strip.path_index, strip.x0, strip.y0, strip.x1, strip.y1, strip.polygon,
                    forced, strip.path_indices,
                )
                changed = True
                break
        if not changed:
            break
    return current


def _runs(strips: Sequence[_Strip], horizontal: bool) -> list[tuple[tuple[float, float], float, float, tuple[int, ...]]]:
    """Merge collinear touching strips of one band into runs: (band, lo, hi, path_indices)."""
    members = [s for s in strips if (s.horizontal if horizontal else s.vertical)]
    members.sort(key=lambda s: (round(s.band()[0], 1), s.band()[1], s.span()[0]))
    groups: list[list[_Strip]] = []
    for strip in members:
        for group in groups:
            b = group[0].band()
            if _close(strip.band()[0], b[0], 0.02) and _close(strip.band()[1], b[1], 0.02):
                group.append(strip)
                break
        else:
            groups.append([strip])
    out = []
    for group in groups:
        band = group[0].band()
        group.sort(key=lambda s: s.span()[0])
        lo, hi = group[0].span()
        paths = list(group[0].native_path_indices())
        for strip in group[1:]:
            s_lo, s_hi = strip.span()
            if s_lo <= hi + NOISE_PT:
                hi = max(hi, s_hi)
                paths.extend(strip.native_path_indices())
            else:
                out.append((band, lo, hi, tuple(sorted(set(paths)))))
                lo, hi, paths = s_lo, s_hi, list(strip.native_path_indices())
        out.append((band, lo, hi, tuple(sorted(set(paths)))))
    return out


def _gaps(strips: Sequence[_Strip], union: Any, domain: Any) -> list[_Gap]:
    """Maximal bounded interruptions of every wall band.

    From each wall run's free end, take the free part of the band (the band rectangle minus all
    wall ink) that starts exactly there. It is a gap only if it is bounded by wall ink at the
    other end too (a perpendicular wall, a jamb cap, or another run), spans the whole band
    width and is not partly blocked. Each interval is unique by construction; the same one is
    reached from both of its ends and is kept once.
    """
    minx, miny, maxx, maxy = domain.bounds
    found: dict[tuple[bool, int, int, int, int], _Gap] = {}
    for horizontal in (True, False):
        for band, lo, hi, _paths in _runs(strips, horizontal):
            band_rect = box(minx, band[0], maxx, band[1]) if horizontal else box(band[0], miny, band[1], maxy)
            for component in _polygon_parts(band_rect.difference(union)):
                c0, c1, c2, c3 = component.bounds
                a, b = (c0, c2) if horizontal else (c1, c3)
                touches_run_end = _close(a, hi) or _close(b, lo)
                across = (c3 - c1, band[1] - band[0]) if horizontal else (c2 - c0, band[1] - band[0])
                limit_lo, limit_hi = (minx, maxx) if horizontal else (miny, maxy)
                bounded = a > limit_lo + NOISE_PT and b < limit_hi - NOISE_PT
                full_width = across[0] >= across[1] - NOISE_PT
                clean = component.area >= 0.9 * ((c2 - c0) * (c3 - c1))
                if not (touches_run_end and bounded and full_width and clean and b - a > NOISE_PT):
                    continue
                # A real interruption connects two sides: free space must lie just beyond the band
                # on BOTH sides at the middle of the interval. A band bordered by wall ink on one
                # side (a jamb cap, a lining sliver) is not an interruption of a wall line.
                mid = (a + b) / 2.0
                if horizontal:
                    probes = (Point(mid, band[0] - 2 * NOISE_PT), Point(mid, band[1] + 2 * NOISE_PT))
                else:
                    probes = (Point(band[0] - 2 * NOISE_PT, mid), Point(band[1] + 2 * NOISE_PT, mid))
                if any(union.contains(probe) for probe in probes):
                    continue
                key = (horizontal, round(band[0] / 0.02), round(band[1] / 0.02), round(a / 0.02), round(b / 0.02))
                if key in found:
                    continue
                rect = box(a, band[0], b, band[1]) if horizontal else box(band[0], a, band[1], b)
                touching = tuple(sorted({
                    index
                    for s in strips if s.polygon.buffer(NOISE_PT).intersects(rect)
                    for index in s.native_path_indices()
                }))
                same_band = [r for r in _runs(strips, horizontal) if _close(r[0][0], band[0], 0.02) and _close(r[0][1], band[1], 0.02)]
                collinear = any(_close(r[2], a) for r in same_band) and any(_close(r[1], b) for r in same_band)
                found[key] = _Gap(horizontal, band, a, b, touching, (), collinear)
    return list(found.values())


def _swing_arcs(
    drawings: Sequence[Mapping[str, Any] | None], *, all_ink: bool = False,
) -> tuple[list[dict], int]:
    arcs: list[dict] = []
    rejected = 0
    leaves: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    for index, row in _source_rows(drawings, all_ink=all_ink):
        if row.get("fill") is not None:
            continue
        items = list(row.get("items", ()))
        if len(items) == 1 and items[0][0] == "l":
            leaves.append((index, _xy(items[0][1]), _xy(items[0][2])))
    for index, row in _source_rows(drawings, all_ink=all_ink):
        if row.get("fill") is not None:
            continue
        items = list(row.get("items", ()))
        if len(items) != 1 or items[0][0] != "c":
            continue
        p1, p2, p3, p4 = (_xy(items[0][i]) for i in range(1, 5))
        xs = [p1[0], p4[0]]
        ys = [p1[1], p4[1]]
        width, height = abs(xs[0] - xs[1]), abs(ys[0] - ys[1])
        if width <= NOISE_PT or not _close(width, height, 0.002 * max(width, height)):
            rejected += 1
            continue
        radius = width
        corners = [(xs[0], ys[1]), (xs[1], ys[0])]
        # The centre is the corner of the arc's bounding square farthest from the control points.
        centre = max(corners, key=lambda c: math.hypot(c[0] - p2[0], c[1] - p2[1]) + math.hypot(c[0] - p3[0], c[1] - p3[1]))
        mid = (
            (p1[0] + 3 * p2[0] + 3 * p3[0] + p4[0]) / 8.0,
            (p1[1] + 3 * p2[1] + 3 * p3[1] + p4[1]) / 8.0,
        )
        if abs(math.hypot(mid[0] - centre[0], mid[1] - centre[1]) - radius) > _ARC_CIRCULARITY * radius:
            rejected += 1
            continue
        if not (_close(math.hypot(p1[0] - centre[0], p1[1] - centre[1]), radius, 0.002 * radius)
                and _close(math.hypot(p4[0] - centre[0], p4[1] - centre[1]), radius, 0.002 * radius)):
            rejected += 1
            continue
        leaf_hits = []
        for leaf_index, a, b in leaves:
            for tip, other in ((p1, p4), (p4, p1)):
                touches = (
                    (_close(a[0], centre[0]) and _close(a[1], centre[1]) and _close(b[0], tip[0]) and _close(b[1], tip[1]))
                    or (_close(b[0], centre[0]) and _close(b[1], centre[1]) and _close(a[0], tip[0]) and _close(a[1], tip[1]))
                )
                if touches:
                    leaf_hits.append((leaf_index, tip, other))
        if len(leaf_hits) != 1:
            rejected += 1
            continue
        leaf_index, open_tip, closed_tip = leaf_hits[0]
        arcs.append({"arc": index, "leaf": leaf_index, "centre": centre, "closed_tip": closed_tip, "radius": radius})
    return arcs, rejected


def _place_swings(arcs: Sequence[dict], gaps: Sequence[_Gap]) -> tuple[dict[int, dict], int, int]:
    """Map gap index -> swing; count swings with no gap and swings with several."""
    placed: dict[int, list[dict]] = {}
    unplaced = 0
    ambiguous = 0
    for arc in arcs:
        centre, tip = arc["centre"], arc["closed_tip"]
        candidates = []
        for gap_index, gap in enumerate(gaps):
            thickness = gap.band[1] - gap.band[0]
            if gap.horizontal:
                on_line = _close(centre[1], tip[1], NOISE_PT) and gap.band[0] - thickness <= centre[1] <= gap.band[1] + thickness
                seg = sorted((centre[0], tip[0]))
            else:
                on_line = _close(centre[0], tip[0], NOISE_PT) and gap.band[0] - thickness <= centre[0] <= gap.band[1] + thickness
                seg = sorted((centre[1], tip[1]))
            if on_line and gap.lo - NOISE_PT <= seg[0] and seg[1] <= gap.hi + NOISE_PT:
                candidates.append(gap_index)
        if len(candidates) == 1:
            placed.setdefault(candidates[0], []).append(arc)
        elif not candidates:
            unplaced += 1
        else:
            ambiguous += 1
    unique = {}
    for gap_index, items in placed.items():
        if len(items) == 1:
            unique[gap_index] = items[0]
        else:
            ambiguous += len(items)
    return unique, unplaced, ambiguous


def _stroke_closed(
    drawings: Sequence[Mapping[str, Any] | None], gap: _Gap, *, all_ink: bool = False,
) -> Optional[tuple[int, ...]]:
    """Native path index of one unfilled wall-layer stroke parallel to the gap and spanning it end to end.

    The stroke may sit on a face line or on the wall's own lining line just outside the band (never
    farther than one wall thickness): CAD exports draw glazing and lining on either.
    """
    thickness = gap.band[1] - gap.band[0]
    for index, row in _source_rows(drawings, all_ink=all_ink):
        if row.get("fill") is not None:
            continue
        for item in row.get("items", ()):
            if item[0] != "l":
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if gap.horizontal:
                if not _close(ay, by, 1e-3):
                    continue
                perp = ay
                lo, hi = sorted((ax, bx))
            else:
                if not _close(ax, bx, 1e-3):
                    continue
                perp = ax
                lo, hi = sorted((ay, by))
            near_band = gap.band[0] - thickness <= perp <= gap.band[1] + thickness
            span = gap.hi - gap.lo
            # Face identity (0.35) only on opening-sized interruptions. A hall-length
            # band with a lining 0.28 pt short of the ends is not a window.
            end_tol = (
                _STROKE_PAIR_FACE_PT
                if 10.0 <= span <= 140.0
                else NOISE_PT
            )
            if near_band and _close(lo, gap.lo, end_tol) and _close(hi, gap.hi, end_tol):
                return (index,)
    return None


def _jamb_cap_closed(
    drawings: Sequence[Mapping[str, Any] | None], gap: _Gap, *, all_ink: bool = False,
) -> Optional[tuple[int, ...]]:
    """Unique perpendicular caps at both gap ends spanning the wall band.

    Stroke-pair walls often omit a leaf/swing. Both unique jambs still close the
    interruption. Competing caps abstain. Representation noise only; never 2.5 pt snap.
    """
    thickness = gap.band[1] - gap.band[0]
    if thickness <= NOISE_PT or gap.hi - gap.lo <= NOISE_PT:
        return None

    def caps(station: float) -> list[int]:
        hits: list[int] = []
        for index, row in _source_rows(drawings, all_ink=all_ink):
            if row.get("fill") is not None:
                continue
            for item in row.get("items", ()):
                if item[0] != "l":
                    continue
                (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
                if gap.horizontal:
                    if not _close(ax, bx, _STROKE_PAIR_FACE_PT):
                        continue
                    if abs(((ax + bx) / 2.0) - station) > _STROKE_PAIR_FACE_PT:
                        continue
                    lo, hi = sorted((ay, by))
                else:
                    if not _close(ay, by, _STROKE_PAIR_FACE_PT):
                        continue
                    if abs(((ay + by) / 2.0) - station) > _STROKE_PAIR_FACE_PT:
                        continue
                    lo, hi = sorted((ax, bx))
                if lo - _STROKE_PAIR_FACE_PT > gap.band[0] or hi + _STROKE_PAIR_FACE_PT < gap.band[1]:
                    continue
                if (hi - lo) > thickness + 2.0 * _STROKE_PAIR_FACE_PT:
                    continue
                hits.append(index)
        return list(dict.fromkeys(hits))

    low, high = caps(gap.lo), caps(gap.hi)
    if not (1 <= len(low) <= 2 and 1 <= len(high) <= 2):
        return None
    if set(low) & set(high):
        return None
    return tuple(sorted(set(low) | set(high)))


def _row_bounds(row: Mapping[str, Any]) -> tuple[float, float, float, float]:
    """Bounding box of one native drawing: its own ``rect`` when present, else of its items' points."""
    rect = row.get("rect")
    if rect is not None:
        return float(rect.x0), float(rect.y0), float(rect.x1), float(rect.y1)
    xs: list[float] = []
    ys: list[float] = []
    for item in row.get("items", ()):
        if item[0] == "re":
            xs += [item[1].x0, item[1].x1]
            ys += [item[1].y0, item[1].y1]
        elif item[0] == "qu":
            for point in (item[1].ul, item[1].ur, item[1].lr, item[1].ll):
                xs.append(point.x)
                ys.append(point.y)
        else:
            for point in item[1:]:
                if hasattr(point, "x"):
                    xs.append(point.x)
                    ys.append(point.y)
    if not xs:
        return (math.inf, math.inf, -math.inf, -math.inf)
    return float(min(xs)), float(min(ys)), float(max(xs)), float(max(ys))


def _is_white(color: Any) -> bool:
    return (
        isinstance(color, (tuple, list)) and len(color) == 3
        and all(type(v) in (int, float) and math.isfinite(v) and v >= 1.0 - _BLACK_MAX for v in color)
    )


def _opaque(row: Mapping[str, Any]) -> bool:
    opacity = row.get("fill_opacity")
    return opacity is None or (type(opacity) in (int, float) and opacity >= 1.0 - 1e-9)


def _white_frame_boxes(drawings: Sequence[Mapping[str, Any]]) -> list[tuple[float, float, float, float, int]]:
    """Opaque white rectangles on a wall layer: (x0, y0, x1, y1, native path index)."""
    boxes: list[tuple[float, float, float, float, int]] = []
    for index, row in _wall_rows(drawings):
        fill = row.get("fill")
        if fill is None or not _is_white(fill) or not _opaque(row):
            continue
        items = list(row.get("items", ()))
        rects = [r for r in (_rect_of_item(it) for it in items) if r is not None]
        if not rects:
            whole = _rect_of_closed_line_path(items)
            rects = [whole] if whole is not None else []
        for x0, y0, x1, y1 in rects:
            if x1 - x0 > NOISE_PT and y1 - y0 > NOISE_PT:
                boxes.append((x0, y0, x1, y1, index))
    return boxes


def _frame_anchored_gaps(drawings: Sequence[Mapping[str, Any]], union: Any, known: Sequence[_Gap]) -> list[_Gap]:
    """Openings anchored on two collinear white frame boxes that each abut black wall ink.

    A wall run seeds an interruption only when its end piece is a recognised strip; a wardrobe or
    sliding door often ends in a chamfered or narrow block that is not. Here the interruption is the
    interval between two ADJACENT frame boxes of one band (no other frame box between them), bounded
    at both ends by black wall ink of one and the same band thickness, free of black ink between, and
    open on both sides of the band at its middle. Intervals already found from wall runs are not added.
    """
    boxes = _white_frame_boxes(drawings)
    found: list[_Gap] = []
    for horizontal in (True, False):
        groups: dict[tuple[int, int], list[tuple[float, float, int]]] = {}
        for x0, y0, x1, y1, index in boxes:
            lo, hi = (x0, x1) if horizontal else (y0, y1)
            p0, p1 = (y0, y1) if horizontal else (x0, x1)
            groups.setdefault((round(p0 / 0.02), round(p1 / 0.02)), []).append((lo, hi, index))
        for (k0, k1), members in groups.items():
            p0, p1 = k0 * 0.02, k1 * 0.02
            members.sort()
            for (lo1, hi1, _i1), (lo2, hi2, _i2) in zip(members, members[1:]):
                if lo2 - hi1 <= NOISE_PT:
                    continue
                bands = []
                for edge, direction in ((lo1, -1), (hi2, 1)):
                    a, b = (edge - 0.1, edge) if direction < 0 else (edge, edge + 0.1)
                    slab = box(a, p0, b, p1) if horizontal else box(p0, a, p1, b)
                    inter = union.intersection(slab)
                    if inter.is_empty or inter.area < 0.5 * slab.area:
                        bands = []
                        break
                    bx0, by0, bx1, by1 = inter.bounds
                    bands.append((by0, by1) if horizontal else (bx0, bx1))
                if len(bands) != 2 or not (_close(bands[0][0], bands[1][0], 0.02) and _close(bands[0][1], bands[1][1], 0.02)):
                    continue
                band = bands[0]
                if band[1] - band[0] <= NOISE_PT:
                    continue
                gap = _Gap(horizontal, band, lo1, hi2, (), (), True)
                rect = gap.rect()
                # the opening is ONE interruption: no black ink inside it beyond noise at its two end faces
                if rect.intersection(union).area > NOISE_PT * 2.0 * (band[1] - band[0]):
                    continue
                mid = (lo1 + hi2) / 2.0
                probes = (
                    (Point(mid, band[0] - 2 * NOISE_PT), Point(mid, band[1] + 2 * NOISE_PT)) if horizontal
                    else (Point(band[0] - 2 * NOISE_PT, mid), Point(band[1] + 2 * NOISE_PT, mid))
                )
                if any(union.contains(probe) for probe in probes):
                    continue
                if any(
                    g.horizontal == horizontal and _close(g.band[0], band[0], 0.02) and _close(g.band[1], band[1], 0.02)
                    and _close(g.lo, lo1) and _close(g.hi, hi2) for g in known
                ):
                    continue
                found.append(gap)
    return found


def _sliding_leaf_evidence(drawings: Sequence[Mapping[str, Any]], gap: _Gap) -> Optional[tuple[int, ...]]:
    """A sliding-door opening: a frame box at EACH end of the interruption and exactly two overlapping
    leaf strokes between them, all native wall-layer ink on this page, none hidden by a later opaque fill.

    Returns the native path indices (frames then leaves) or None. Every defect abstains: a missing or
    duplicated frame, a missing, extra, duplicated, shifted or non-overlapping leaf, ink on another layer,
    a leaf or frame painted over by a later fill.
    """
    thickness = gap.band[1] - gap.band[0]
    horizontal = gap.horizontal
    frames: list[tuple[float, float, int]] = []
    for x0, y0, x1, y1, index in _white_frame_boxes(drawings):
        lo, hi = (x0, x1) if horizontal else (y0, y1)
        p0, p1 = (y0, y1) if horizontal else (x0, x1)
        if p1 < gap.band[0] - thickness or p0 > gap.band[1] + thickness:
            continue
        inside = gap.lo - NOISE_PT <= lo and hi <= gap.hi + NOISE_PT
        if hi - lo > NOISE_PT and inside and (_close(lo, gap.lo) or _close(hi, gap.hi)):
            frames.append((lo, hi, index))
    low = [f for f in frames if _close(f[0], gap.lo)]
    high = [f for f in frames if _close(f[1], gap.hi)]
    if len(low) != 1 or len(high) != 1 or low[0][2] == high[0][2]:
        return None
    inner_lo, inner_hi = low[0][1], high[0][0]
    if inner_hi - inner_lo <= NOISE_PT:
        return None
    leaves: list[tuple[float, float, float, int]] = []
    for index, row in _wall_rows(drawings):
        if row.get("fill") is not None:
            continue
        for item in row.get("items", ()):
            if item[0] != "l":
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if horizontal:
                if not _close(ay, by, 1e-3):
                    continue
                perp = ay
                lo, hi = sorted((ax, bx))
            else:
                if not _close(ax, bx, 1e-3):
                    continue
                perp = ax
                lo, hi = sorted((ay, by))
            if not (gap.band[0] - thickness <= perp <= gap.band[1] + thickness):
                continue
            lo, hi = max(lo, inner_lo), min(hi, inner_hi)
            if hi - lo > NOISE_PT:
                leaves.append((lo, hi, perp, index))
    if len(leaves) != 2:
        return None  # one leaf, three leaves or a duplicate leaf: not exactly the sliding pair
    leaves.sort()
    first, second = leaves
    if not (_close(first[0], inner_lo) and _close(second[1], inner_hi)):
        return None  # a leaf is missing, shifted or short of its frame
    if not (second[0] < first[1] - NOISE_PT):
        return None  # a sliding pair overlaps; leaves that merely touch or leave a hole are not one
    # none of the evidence may be painted over by a LATER opaque fill (paint order is the source's own)
    band_mid = (gap.band[0] + gap.band[1]) / 2.0
    evidence = [
        (low[0][2], (low[0][0] + low[0][1]) / 2.0, band_mid),
        (high[0][2], (high[0][0] + high[0][1]) / 2.0, band_mid),
        (first[3], (first[0] + first[1]) / 2.0, first[2]),
        (second[3], (second[0] + second[1]) / 2.0, second[2]),
    ]
    for index, along, perp in evidence:
        x, y = (along, perp) if horizontal else (perp, along)
        for later in range(index + 1, len(drawings)):
            row = drawings[later]
            if row.get("fill") is None or not _opaque(row):
                continue
            x0, y0, x1, y1 = _row_bounds(row)
            if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
                return None
    return tuple(sorted({low[0][2], high[0][2], first[3], second[3]}))


def _panel_lift_word_evidence(
    gap: _Gap, source_words: Sequence[Mapping[str, Any]],
) -> tuple[str, ...] | None:
    """A printed 'Panel Lift Door' beside ONE bounded wall interruption.

    The word coordinates come from the SHA-verified source page. Require the
    three adjacent words on one baseline, a source-drawn large numeric opening
    figure, and a real original wall band. No inferred garage shape or solid
    wall is created. The evidence permits only a temporary 2D barrier.
    """
    if not gap.collinear or gap.hi - gap.lo < 10.0:
        return None
    if not gap.left_path_indices and not gap.right_path_indices:
        return None
    horizontal = gap.horizontal
    centre = (gap.band[0] + gap.band[1]) / 2.0
    near: dict[str, list[tuple[float, float, float, str]]] = {}
    figured: list[tuple[int, str]] = []
    for word in source_words:
        if not isinstance(word, Mapping):
            continue
        t = str(word.get("text", "")).strip()
        bounds = word.get("bbox_pdf_pts")
        ref = str(word.get("source_ref", ""))
        if not ref or not isinstance(bounds, (tuple, list)) or len(bounds) != 4:
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in bounds)
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 < x0 or y1 < y0:
            continue
        along0, along1 = (x0, x1) if horizontal else (y0, y1)
        cross = ((y0 + y1) / 2.0) if horizontal else ((x0 + x1) / 2.0)
        if abs(cross - centre) > 12.0 or along0 < gap.lo - 1.0 or along1 > gap.hi + 1.0:
            continue
        name = t.upper()
        near.setdefault(name, []).append((along0, along1, cross, ref))
        digits = t.replace(",", "")
        if digits.isdecimal() and 2000 <= int(digits) <= 12000:
            figured.append((int(digits), ref))
    if any(len(near.get(term, [])) != 1 for term in ("DOOR", "LIFT", "PANEL")) or not figured:
        return None
    # A real contiguous annotation reading "Door Lift Panel" in page-axis order
    # for this orientation. A random collection of distant text must not
    # authorize an opening.
    label = sorted([near[t][0] for t in ("DOOR", "LIFT", "PANEL")])
    if any(label[i + 1][0] - label[i][1] > 7.0 for i in range(2)):
        return None
    if max(w[2] for w in label) - min(w[2] for w in label) > 2.5:
        return None
    if label[-1][1] - label[0][0] > 0.75 * (gap.hi - gap.lo):
        return None
    # Prefer the largest printed dimension (door width, not height) as a
    # separate source witness, without converting the PDF span into metres.
    _figure, figure_ref = max(figured)
    return tuple(w[3] for w in label) + (figure_ref,)


def _is_cs_token(text: str) -> bool:
    token = str(text or "").strip().upper().replace(".", "")
    return token in {"CS", "CSL"}


def _paired_cavity_leaves(
    drawings: Sequence[Mapping[str, Any]], gap: _Gap,
) -> Optional[tuple[int, ...]]:
    """Exactly two overlapping unfilled leaf strokes in a collinear wall interruption.

    These strokes are the cavity-slider leaves, never physical walls. Missing,
    extra, non-overlapping or perpendicular strokes abstain.
    """
    if not gap.collinear:
        return None
    thickness = gap.band[1] - gap.band[0]
    reach = max(thickness * 4.0, 16.0)
    span = max(gap.hi - gap.lo, NOISE_PT)
    horizontal = gap.horizontal
    leaves: list[tuple[float, float, float, int]] = []
    for index, row in _wall_rows(drawings):
        if row.get("fill") is not None:
            continue
        for item in row.get("items", ()):
            if item[0] != "l":
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if horizontal:
                if not _close(ay, by, 1e-3):
                    continue
                perp = ay
                lo, hi = sorted((ax, bx))
            else:
                if not _close(ax, bx, 1e-3):
                    continue
                perp = ax
                lo, hi = sorted((ay, by))
            if not (gap.band[0] - reach <= perp <= gap.band[1] + reach):
                continue
            lo, hi = max(lo, gap.lo), min(hi, gap.hi)
            if (hi - lo) / span >= 0.70:
                leaves.append((lo, hi, perp, index))
    unique: list[tuple[float, float, float, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for item in leaves:
        key = (item[3], round(item[0], 2), round(item[1], 2), round(item[2], 2))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    if len(unique) != 2:
        return None
    unique.sort()
    first, second = unique
    if first[3] == second[3]:
        return None
    if not (second[0] < first[1] - NOISE_PT):
        return None
    return tuple(sorted({first[3], second[3]}))


def _axis_aligned_wall_strokes(
    drawings: Sequence[Mapping[str, Any]],
) -> list[tuple[bool, float, float, float, int]]:
    """Unfilled axis-aligned wall-layer strokes: (horizontal, perp, lo, hi, path_index)."""
    strokes: list[tuple[bool, float, float, float, int]] = []
    for index, row in _wall_rows(drawings):
        if row.get("fill") is not None:
            continue
        for item in row.get("items", ()):
            if item[0] != "l":
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if _close(ay, by, 1e-3) and not _close(ax, bx, 1e-3):
                lo, hi = sorted((ax, bx))
                if hi - lo >= 8.0:
                    strokes.append((True, ay, lo, hi, index))
            elif _close(ax, bx, 1e-3) and not _close(ay, by, 1e-3):
                lo, hi = sorted((ay, by))
                if hi - lo >= 8.0:
                    strokes.append((False, ax, lo, hi, index))
    return strokes


def _exactly_two_overlapping_paths(
    items: Sequence[tuple[float, float, float, int]],
) -> Optional[tuple[int, ...]]:
    unique: list[tuple[float, float, float, int]] = []
    seen: set[tuple[int, int, int, int]] = set()
    for item in items:
        key = (item[3], round(item[0], 2), round(item[1], 2), round(item[2], 2))
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    if len(unique) != 2 or unique[0][3] == unique[1][3]:
        return None
    first, second = sorted(unique)
    if not (second[0] < first[1] - NOISE_PT):
        return None
    return tuple(sorted({first[3], second[3]}))


def _pocket_cavity_leaves(
    drawings: Sequence[Mapping[str, Any]], gap: _Gap,
) -> Optional[tuple[int, ...]]:
    """Exactly two overlapping leaf/face strokes in the collinear pocket beside a gap.

    Cavity sliders often draw the door inside the adjacent wall run, not across
    the walk-through. Wall-face strokes of that pocket are not physical walls of
    a second room. Extra unmatched strokes on a side abstain.
    """
    if not gap.collinear:
        return None
    thickness = gap.band[1] - gap.band[0]
    span = max(gap.hi - gap.lo, NOISE_PT)
    low_side: list[tuple[float, float, float, int]] = []
    high_side: list[tuple[float, float, float, int]] = []
    for horizontal, perp, lo, hi, index in _axis_aligned_wall_strokes(drawings):
        if horizontal != gap.horizontal:
            continue
        if not (gap.band[0] - thickness <= perp <= gap.band[1] + thickness):
            continue
        length = hi - lo
        if length < 0.80 * span or length > 1.50 * span:
            continue
        if hi <= gap.lo + NOISE_PT and gap.lo - hi <= 16.0:
            low_side.append((lo, hi, perp, index))
        elif lo >= gap.hi - NOISE_PT and lo - gap.hi <= 16.0:
            high_side.append((lo, hi, perp, index))
    pairs: list[tuple[int, ...]] = []
    for side in (low_side, high_side):
        if not side:
            continue
        pair = _exactly_two_overlapping_paths(side)
        if pair is None:
            return None
        pairs.append(pair)
    if not pairs:
        return None
    return tuple(sorted({index for pair in pairs for index in pair}))


def _cs_face_interruption_gaps(
    drawings: Sequence[Mapping[str, Any]],
    known: Sequence[_Gap],
    source_words: Sequence[Mapping[str, Any]],
) -> list[_Gap]:
    """Collinear CS openings recovered from paired wall-face interruptions.

    A filled-strip gap finder misses cavity sliders whose jambs are chamfered or
    whose faces are stroked without a strip-bounded interruption. Unique CS plus
    two parallel wall faces that share one interruption still close topology only.
    Two CS marks in one interruption abstain.
    """
    grouped: dict[tuple[bool, int], list[tuple[float, float, int]]] = {}
    for horizontal, perp, lo, hi, index in _axis_aligned_wall_strokes(drawings):
        grouped.setdefault((horizontal, round(perp / 0.02)), []).append((lo, hi, index))
    interruptions: list[tuple[bool, float, float, float]] = []
    for (horizontal, key), segs in grouped.items():
        segs = sorted(segs)
        merged: list[tuple[float, float]] = []
        for lo, hi, _index in segs:
            if merged and lo <= merged[-1][1] + 0.5:
                merged[-1] = (merged[-1][0], max(merged[-1][1], hi))
            else:
                merged.append((lo, hi))
        perp = key * 0.02
        for left, right in zip(merged, merged[1:]):
            glo, ghi = left[1], right[0]
            if 10.0 < ghi - glo < 140.0:
                interruptions.append((horizontal, perp, glo, ghi))
    clustered: dict[tuple[bool, int, int], list[tuple[float, float, float]]] = {}
    for horizontal, perp, lo, hi in interruptions:
        clustered.setdefault((horizontal, round(lo * 2.0), round(hi * 2.0)), []).append((perp, lo, hi))
    found: list[_Gap] = []
    for (horizontal, _lo_key, _hi_key), items in clustered.items():
        perps = sorted({round(item[0], 2) for item in items})
        if len(perps) < 2:
            continue
        bands: list[list[float]] = [[perps[0]]]
        for perp in perps[1:]:
            if perp - bands[-1][-1] <= 8.0:
                bands[-1].append(perp)
            else:
                bands.append([perp])
        if len(bands) != 1 or not (2 <= len(bands[0]) <= 6):
            continue
        band_perps = bands[0]
        band = (band_perps[0], band_perps[-1])
        if not (1.0 <= band[1] - band[0] <= 8.0):
            continue
        gap_lo = max(item[1] for item in items)
        gap_hi = min(item[2] for item in items)
        if gap_hi - gap_lo < 10.0:
            continue
        gap = _Gap(horizontal, band, gap_lo, gap_hi, (), (), True)
        if any(
            known_gap.horizontal == horizontal
            and _close(known_gap.band[0], band[0], 0.05)
            and _close(known_gap.band[1], band[1], 0.05)
            and _close(known_gap.lo, gap_lo, 0.5)
            and _close(known_gap.hi, gap_hi, 0.5)
            for known_gap in known
        ):
            continue
        if _cavity_slider_word_evidence(gap, source_words) is None:
            continue
        found.append(gap)
    return found


def _prefer_prior_cs_gaps(
    cavity_by_gap: Mapping[int, tuple[tuple[int, ...], tuple[str, ...]]],
    prior_gap_count: int,
) -> dict[int, tuple[tuple[int, ...], tuple[str, ...]]]:
    """A strip/frame CS opening wins over a reconstructed face interruption of the same mark."""
    by_words: dict[tuple[str, ...], list[int]] = {}
    for gap_index, evidence in cavity_by_gap.items():
        by_words.setdefault(evidence[1], []).append(gap_index)
    drop: set[int] = set()
    for members in by_words.values():
        prior = [index for index in members if index < prior_gap_count]
        later = [index for index in members if index >= prior_gap_count]
        if prior:
            drop.update(later)
            continue
        with_leaves = [index for index in members if cavity_by_gap[index][0]]
        if with_leaves:
            drop.update(index for index in members if not cavity_by_gap[index][0])
    return {
        gap_index: evidence
        for gap_index, evidence in cavity_by_gap.items()
        if gap_index not in drop
    }


def _keep_thickest_split_band_cs(
    gaps: Sequence[_Gap],
    cavity_by_gap: Mapping[int, tuple[tuple[int, ...], tuple[str, ...]]],
) -> dict[int, tuple[tuple[int, ...], tuple[str, ...]]]:
    """One CS opening drawn as two lining slivers is one interruption, not a conflict."""
    by_words: dict[tuple[str, ...], list[int]] = {}
    for gap_index, evidence in cavity_by_gap.items():
        by_words.setdefault(evidence[1], []).append(gap_index)
    drop: set[int] = set()
    for members in by_words.values():
        groups: dict[tuple[bool, int, int], list[int]] = {}
        for gap_index in members:
            gap = gaps[gap_index]
            key = (gap.horizontal, round(gap.lo), round(gap.hi))
            groups.setdefault(key, []).append(gap_index)
        for clustered in groups.values():
            if len(clustered) < 2:
                continue
            clustered.sort(key=lambda index: gaps[index].band[1] - gaps[index].band[0], reverse=True)
            drop.update(clustered[1:])
    return {
        gap_index: evidence
        for gap_index, evidence in cavity_by_gap.items()
        if gap_index not in drop
    }


def _cavity_slider_word_evidence(
    gap: _Gap, source_words: Sequence[Mapping[str, Any]],
) -> tuple[str, ...] | None:
    """A unique CS mark beside one collinear wall interruption, with an optional unique width.

    Paired leaf lines are required separately. A CS mark alone, or a double-line
    gap without CS, does not close the opening.
    """
    if not gap.collinear or gap.hi - gap.lo < 10.0 or gap.hi - gap.lo > 140.0:
        return None
    horizontal = gap.horizontal
    centre = (gap.band[0] + gap.band[1]) / 2.0
    marks: list[tuple[float, float, float, str]] = []
    widths: list[tuple[float, float, float, str, int]] = []
    for word in source_words:
        if not isinstance(word, Mapping):
            continue
        text = str(word.get("text", "")).strip()
        bounds = word.get("bbox_pdf_pts")
        ref = str(word.get("source_ref", ""))
        if not ref or not isinstance(bounds, (tuple, list)) or len(bounds) != 4:
            continue
        try:
            x0, y0, x1, y1 = (float(v) for v in bounds)
        except (TypeError, ValueError, OverflowError):
            continue
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x1 < x0 or y1 < y0:
            continue
        along0, along1 = (x0, x1) if horizontal else (y0, y1)
        cross = ((y0 + y1) / 2.0) if horizontal else ((x0 + x1) / 2.0)
        along_mid = (along0 + along1) / 2.0
        if along_mid < gap.lo - 22.0 or along_mid > gap.hi + 22.0:
            continue
        if abs(cross - centre) > 36.0:
            continue
        if _is_cs_token(text):
            marks.append((along0, along1, cross, ref))
            continue
        digits = text.replace(",", "")
        if digits.isdecimal() and 600 <= int(digits) <= 2400:
            widths.append((along0, along1, cross, ref, int(digits)))
    if len(marks) != 1:
        return None
    mark = marks[0]
    mark_along = (mark[0] + mark[1]) / 2.0
    nearby_widths = [
        item for item in widths
        if abs((item[0] + item[1]) / 2.0 - mark_along) <= 8.0
        and min(
            abs(item[1] - mark[0]),
            abs(item[0] - mark[1]),
            abs(item[2] - mark[2]),
        ) <= 36.0
    ]
    if len(nearby_widths) > 1:
        return None
    refs = [mark[3]]
    if len(nearby_widths) == 1:
        refs.append(nearby_widths[0][3])
    return tuple(refs)


def _closed_union(polygons: Iterable[Polygon]) -> Any:
    merged = unary_union([p.buffer(_CLOSING_PT, join_style=2) for p in polygons])
    return merged.buffer(-_CLOSING_PT, join_style=2)


def _polygon_parts(geom: Any) -> list[Polygon]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "Polygon"]


def _dedupe_ring(coords: Sequence[tuple[float, float]]) -> tuple[tuple[float, float], ...]:
    """Drop consecutive repeated vertices (and a repeat across the closing edge). Planarization and
    the 0.03 pt closing leave sub-rounding jogs; a ring with a repeated vertex is not a simple ring
    to downstream room-area code, and no distinct vertex is removed."""
    out: list[tuple[float, float]] = []
    for point in coords:
        if not out or point != out[-1]:
            out.append(point)
    while len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return tuple(out)


def _split_at_closures(
    coords: Sequence[tuple[float, float]], closures: Sequence[tuple[bool, tuple[float, float], float, float]],
) -> tuple[tuple[float, float], ...]:
    """Insert a vertex wherever an axis-aligned ring edge enters or leaves a doorway closure, so
    every ring edge is wholly a wall edge or wholly a doorway chord (no edge mixes owners)."""
    out: list[tuple[float, float]] = []
    count = len(coords)
    for index, a in enumerate(coords):
        b = coords[(index + 1) % count]
        out.append(a)
        horizontal_edge = _close(a[1], b[1], 1e-3) and not _close(a[0], b[0], 1e-3)
        vertical_edge = _close(a[0], b[0], 1e-3) and not _close(a[1], b[1], 1e-3)
        if not (horizontal_edge or vertical_edge):
            continue
        along = 0 if horizontal_edge else 1
        perp = a[1 - along]
        lo_e, hi_e = sorted((a[along], b[along]))
        cuts: set[float] = set()
        for gap_horizontal, band, lo, hi in closures:
            if gap_horizontal != horizontal_edge or not (band[0] - NOISE_PT <= perp <= band[1] + NOISE_PT):
                continue
            lo_c, hi_c = max(lo_e, lo), min(hi_e, hi)
            if hi_c - lo_c > NOISE_PT:
                cuts.update(v for v in (lo_c, hi_c) if lo_e + NOISE_PT < v < hi_e - NOISE_PT)
        for value in sorted(cuts, reverse=a[along] > b[along]):
            point = [0.0, 0.0]
            point[along], point[1 - along] = round(value, 4), perp
            out.append((point[0], point[1]))
    return tuple(out)


def _merge_ring_results(parts: Sequence[LayeredRoomRingResult]) -> LayeredRoomRingResult:
    """Keep per-neighbourhood topology when the union of clips exceeds the 20k cap."""
    if not parts:
        return LayeredRoomRingResult(
            EvidenceResolutionStatus.ABSTAINED, (REASON_NO_WALL_INK,), (), (), 0, 0, 0, 0, 0, 0,
        )
    rings = tuple(sorted({ring.record_id: ring for part in parts for ring in part.rings}.values(), key=lambda r: r.record_id))
    closures = tuple(sorted(
        {item.closure_id: item for part in parts for item in part.closures}.values(),
        key=lambda item: item.closure_id,
    ))
    reasons: list[str] = []
    any_strips = any(part.wall_strip_count for part in parts)
    for part in parts:
        for reason in part.reason_codes:
            if reason == REASON_PRIMITIVE_CAP:
                continue
            if reason == REASON_NO_WALL_INK and any_strips:
                continue
            if reason not in reasons:
                reasons.append(reason)
    if any(ring.status is EvidenceResolutionStatus.CANDIDATE for ring in rings):
        status = EvidenceResolutionStatus.CANDIDATE
        if REASON_RING_CLOSED not in reasons:
            reasons.insert(0, REASON_RING_CLOSED)
    elif all(part.reason_codes == (REASON_PRIMITIVE_CAP,) for part in parts):
        status = EvidenceResolutionStatus.ABSTAINED
        reasons = [REASON_PRIMITIVE_CAP]
    else:
        status = EvidenceResolutionStatus.ABSTAINED
        if not reasons:
            reasons = [REASON_OPEN_EXTERIOR]
    return LayeredRoomRingResult(
        status=status,
        reason_codes=tuple(reasons),
        rings=rings,
        closures=closures,
        wall_strip_count=sum(part.wall_strip_count for part in parts),
        wall_gap_count=sum(part.wall_gap_count for part in parts),
        unresolved_gap_count=sum(part.unresolved_gap_count for part in parts),
        non_strip_wall_fill_count=sum(part.non_strip_wall_fill_count for part in parts),
        unplaced_swing_count=sum(part.unplaced_swing_count for part in parts),
        ambiguous_swing_count=sum(part.ambiguous_swing_count for part in parts),
        sliver_region_count=sum(part.sliver_region_count for part in parts),
    )


def build_layered_wall_doorway_room_rings(
    drawings: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
    page_index: int,
    sliding_leaf_frame_closure: bool = False,
    panel_lift_label_closure: bool = False,
    source_words: Sequence[Mapping[str, Any]] = (),
    stroke_pair_wall_faces: bool = False,
    wall_end_stroke_closures: bool = False,
    viewport_pdf_pts: tuple[float, float, float, float] | Sequence[tuple[float, float, float, float]] | None = None,
) -> LayeredRoomRingResult:
    """Rings enclosed by wall ink plus source-attested doorway closures. Never mutates ``drawings``.

    ``sliding_leaf_frame_closure`` (default False, its own control) additionally closes an interruption
    that carries a frame box at each end and exactly two overlapping sliding leaves between them.
    ``stroke_pair_wall_faces`` (default False) adds unlabelled parallel-stroke face candidates.
    Those candidates are not an authenticated wall layer and never a quantity.
    ``wall_end_stroke_closures`` (default False) adds a single black stroke only when both of
    its native endpoints already meet major structural strips. The stroke is not extended.
    """
    if type(sliding_leaf_frame_closure) is not bool:
        raise ValueError("sliding_leaf_frame_closure must be an explicit boolean")
    if type(panel_lift_label_closure) is not bool:
        raise ValueError("panel_lift_label_closure must be an explicit boolean")
    if type(stroke_pair_wall_faces) is not bool:
        raise ValueError("stroke_pair_wall_faces must be an explicit boolean")
    if type(wall_end_stroke_closures) is not bool:
        raise ValueError("wall_end_stroke_closures must be an explicit boolean")
    if type(source_sha256) is not str or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("source_sha256 must be a 64-char lowercase hex digest")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must be a non-negative int")
    if stroke_pair_wall_faces and viewport_pdf_pts is not None:
        indexed = _clip_drawing_items(drawings, viewport_pdf_pts)
        if _selected_primitive_count(indexed) > _PRIMITIVE_CAP:
            viewports = _as_viewports(viewport_pdf_pts) or []
            if len(viewports) > 1:
                return _merge_ring_results([
                    build_layered_wall_doorway_room_rings(
                        drawings,
                        source_sha256=source_sha256,
                        page_index=page_index,
                        sliding_leaf_frame_closure=sliding_leaf_frame_closure,
                        panel_lift_label_closure=panel_lift_label_closure,
                        source_words=source_words,
                        stroke_pair_wall_faces=True,
                        wall_end_stroke_closures=wall_end_stroke_closures,
                        viewport_pdf_pts=box,
                    )
                    for box in viewports
                ])
            return LayeredRoomRingResult(
                EvidenceResolutionStatus.ABSTAINED, (REASON_PRIMITIVE_CAP,), (), (), 0, 0, 0, 0, 0, 0,
            )
    else:
        indexed = _clip_drawings(drawings, viewport_pdf_pts)
        if _selected_primitive_count(indexed) > _PRIMITIVE_CAP:
            return LayeredRoomRingResult(
                EvidenceResolutionStatus.ABSTAINED, (REASON_PRIMITIVE_CAP,), (), (), 0, 0, 0, 0, 0, 0,
            )
    strips, other_fills = _collect_strips(indexed)
    if stroke_pair_wall_faces:
        strips = strips + _collect_stroke_pair_strips(indexed) + _collect_dark_fill_strips(indexed)
        if wall_end_stroke_closures:
            strips = strips + _collect_wall_end_closing_strips(indexed, strips)
    unsupported = len(other_fills)
    if not strips:
        return LayeredRoomRingResult(EvidenceResolutionStatus.ABSTAINED, (REASON_NO_WALL_INK,), (), (), 0, 0, 0, unsupported, 0, 0)
    polygons = [s.polygon for s in strips] + [polygon for _index, polygon in other_fills]
    union = _closed_union(polygons)
    domain = union.envelope.buffer(1.0, join_style=2)
    gaps = _gaps(strips, union, domain)
    prior_gap_count = len(gaps)
    if sliding_leaf_frame_closure:
        gaps = gaps + _frame_anchored_gaps(indexed, union, gaps)
        prior_gap_count = len(gaps)
        gaps = gaps + _cs_face_interruption_gaps(indexed, gaps, source_words)
    arcs, _rejected_arcs = _swing_arcs(indexed, all_ink=stroke_pair_wall_faces)
    swing_by_gap, unplaced, ambiguous = _place_swings(arcs, gaps)

    closures: list[LayeredDoorwayClosure] = []
    unresolved: list[_Gap] = []
    closure_rects: list[tuple[str, Polygon]] = []
    sliding_by_gap: dict[int, tuple[int, ...]] = {}
    cavity_by_gap: dict[int, tuple[tuple[int, ...], tuple[str, ...]]] = {}
    if sliding_leaf_frame_closure:
        for gap_index, gap in enumerate(gaps):
            evidence = _sliding_leaf_evidence(indexed, gap)
            if evidence is not None:
                sliding_by_gap[gap_index] = evidence
            cs_words = _cavity_slider_word_evidence(gap, source_words)
            leaves = _paired_cavity_leaves(indexed, gap) or _pocket_cavity_leaves(indexed, gap)
            # Face-reconstructed CS openings already required a unique CS mark;
            # the paired wall faces are the leaf evidence of that interruption.
            if cs_words is not None and (leaves is not None or gap_index >= prior_gap_count):
                cavity_by_gap[gap_index] = (leaves or (), cs_words)
        cavity_by_gap = _prefer_prior_cs_gaps(cavity_by_gap, prior_gap_count)
        cavity_by_gap = _keep_thickest_split_band_cs(gaps, cavity_by_gap)
        # one native stroke or box may evidence only ONE interruption; a shared one is a one-to-many span
        uses = Counter(index for evidence in sliding_by_gap.values() for index in evidence)
        sliding_by_gap = {g: e for g, e in sliding_by_gap.items() if all(uses[i] == 1 for i in e)}
        cs_word_uses = Counter(ref for _leaves, words in cavity_by_gap.values() for ref in words)
        cs_leaf_uses = Counter(index for leaves, _words in cavity_by_gap.values() for index in leaves)
        cavity_by_gap = {
            gap_index: evidence
            for gap_index, evidence in cavity_by_gap.items()
            if all(cs_word_uses[ref] == 1 for ref in evidence[1])
            and all(cs_leaf_uses[index] == 1 for index in evidence[0])
        }
    for gap_index, gap in enumerate(gaps):
        swing = swing_by_gap.get(gap_index)
        stroke = None if swing is not None else _stroke_closed(
            indexed, gap, all_ink=stroke_pair_wall_faces,
        )
        if stroke is None and swing is None and stroke_pair_wall_faces:
            stroke = _jamb_cap_closed(indexed, gap, all_ink=True)
        sliding = sliding_by_gap.get(gap_index)
        cavity = cavity_by_gap.get(gap_index)
        panel_words = (
            _panel_lift_word_evidence(gap, source_words)
            if panel_lift_label_closure else None
        )
        owners = sum(
            1
            for item in (swing, stroke, sliding, cavity, panel_words)
            if item is not None
        )
        if owners > 1:
            unresolved.append(gap)  # Competing source owners; no arbitrary priority.
            continue
        if owners == 0:
            unresolved.append(gap)
            continue
        word_refs: tuple[str, ...] = ()
        if swing is not None:
            kind, native = KIND_SWING, (swing["arc"], swing["leaf"])
        elif stroke is not None:
            kind, native = KIND_STROKE, tuple(stroke)
        elif sliding is not None:
            kind, native = KIND_SLIDING_LEAF, tuple(sliding)
        elif cavity is not None:
            kind, native = KIND_CAVITY_SLIDER, tuple(cavity[0])
            word_refs = tuple(cavity[1])
        else:
            kind, native = KIND_PANEL_LIFT, ()
            word_refs = tuple(panel_words or ())
        payload = {
            "source_sha256": source_sha256,
            "page_index": page_index,
            "kind": kind,
            "horizontal": gap.horizontal,
            "band": [round(v, 3) for v in gap.band],
            "gap": [round(gap.lo, 3), round(gap.hi, 3)],
            "native": list(native),
        }
        # Historic swing/stroke/sliding IDs must stay byte-identical when new
        # kinds are disabled. Word refs belong only to CS and panel-lift kinds.
        if kind in (KIND_CAVITY_SLIDER, KIND_PANEL_LIFT):
            payload["native_word_refs"] = list(word_refs)
        closure_id = stable_contract_id(
            "layered_doorway_closure",
            payload,
            digest_chars=24,
        )
        closures.append(LayeredDoorwayClosure(
            closure_id=closure_id, kind=kind, horizontal=gap.horizontal,
            band=gap.band, gap_interval=(gap.lo, gap.hi), native_path_indices=tuple(native),
            wall_path_indices=tuple(sorted(set(gap.left_path_indices) | set(gap.right_path_indices))),
            native_word_refs=word_refs,
        ))
        closure_rects.append((closure_id, gap.rect()))

    barrier = _closed_union([*polygons, *(rect for _cid, rect in closure_rects)])
    free = domain.difference(barrier)
    rings: list[LayeredRoomRingRecord] = []
    thicknesses = sorted(min(s.x1 - s.x0, s.y1 - s.y0) for s in strips)
    median_thickness = thicknesses[len(thicknesses) // 2]
    sliver_count = 0
    for part in _polygon_parts(free):
        if part.area <= NOISE_PT * NOISE_PT:
            continue
        # A free region narrower than the page's own median wall thickness is a drafting gap
        # between wall pieces, not a room.
        if part.buffer(-median_thickness / 2.0, join_style=2).is_empty:
            sliver_count += 1
            continue
        reasons: list[str] = []
        touches_domain = part.boundary.intersects(domain.boundary.buffer(NOISE_PT))
        if touches_domain:
            continue  # the exterior region: not a room
        # Only a collinear interruption (a wall cut in two) is a defect of the ring. A free band
        # interval that ends at a perpendicular wall is indistinguishable from a stub's open side
        # without door evidence, so it is not asserted either way; the downstream figured-box
        # corroboration decides whether the region is one room.
        adjacent_open = any(gap.collinear and part.buffer(NOISE_PT).intersects(gap.rect()) for gap in unresolved)
        if adjacent_open:
            reasons.append(REASON_OPEN_GAP)
        base = _dedupe_ring(tuple((round(x, 4), round(y, 4)) for x, y in list(part.exterior.coords)[:-1]))
        coords = _dedupe_ring(_split_at_closures(base, [(c.horizontal, c.band, c.gap_interval[0], c.gap_interval[1]) for c in closures]))
        closure_edges = 0
        wall_edges = 0
        unowned_edges = 0
        bounding_closures: set[str] = set()
        edge_owners: list[tuple[str, ...]] = []
        for a, b in zip(coords, coords[1:] + coords[:1]):
            mid = Point((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            owner = next((cid for cid, rect in closure_rects if rect.buffer(NOISE_PT).contains(mid)), None)
            if owner is not None:
                closure_edges += 1
                bounding_closures.add(owner)
                edge_owners.append((f"layered_doorway_closure:{owner}",))
                continue
            owners = tuple(sorted(
                [f"layered_wall_strip:{index}"
                 for s in strips if s.polygon.distance(mid) <= NOISE_PT * 2
                 for index in s.native_path_indices()]
                + [f"layered_wall_fill:{index}" for index, polygon in other_fills if polygon.distance(mid) <= NOISE_PT * 2]
            ))
            if owners:
                wall_edges += 1
            else:
                unowned_edges += 1
            edge_owners.append(owners)
        if unowned_edges:
            reasons.append(REASON_UNOWNED_EDGE)
        wall_paths = tuple(sorted({
            index
            for s in strips if part.buffer(NOISE_PT * 2).intersects(s.polygon)
            for index in s.native_path_indices()
        }))
        status = EvidenceResolutionStatus.ABSTAINED if reasons else EvidenceResolutionStatus.CANDIDATE
        if not reasons:
            reasons.append(REASON_RING_CLOSED)
        minx, miny, maxx, maxy = part.bounds
        record_id = stable_contract_id(
            "layered_wall_doorway_room_ring",
            {"source_sha256": source_sha256, "page_index": page_index, "polygon": coords,
             "closures": sorted(bounding_closures), "reasons": reasons, "owners": [list(o) for o in edge_owners]},
            digest_chars=32,
        )
        rings.append(LayeredRoomRingRecord(
            record_id=record_id, source_sha256=source_sha256, page_index=page_index,
            polygon_pdf_pts=coords, hole_count=len(part.interiors), area_pt2=round(part.area, 4),
            bbox_pdf_pts=(round(minx, 4), round(miny, 4), round(maxx, 4), round(maxy, 4)),
            wall_edge_count=wall_edges, closure_edge_count=closure_edges,
            bounding_closure_ids=tuple(sorted(bounding_closures)), bounding_wall_path_indices=wall_paths,
            status=status, reason_codes=tuple(reasons), edge_owner_ids=tuple(edge_owners), _seal=_RECORD_SEAL,
        ))
    rings.sort(key=lambda r: r.record_id)
    closures.sort(key=lambda c: c.closure_id)
    candidate = any(r.status is EvidenceResolutionStatus.CANDIDATE for r in rings)
    return LayeredRoomRingResult(
        status=EvidenceResolutionStatus.CANDIDATE if candidate else EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(REASON_RING_CLOSED,) if candidate else (REASON_OPEN_EXTERIOR,),
        rings=tuple(rings), closures=tuple(closures), wall_strip_count=len(strips),
        wall_gap_count=len(gaps), unresolved_gap_count=len([g for g in unresolved if g.collinear]),
        non_strip_wall_fill_count=unsupported, unplaced_swing_count=unplaced, ambiguous_swing_count=ambiguous,
        sliver_region_count=sliver_count,
    )


def build_from_pdf_bytes(
    source_bytes: bytes, *, source_sha256: str, page_index: int, sliding_leaf_frame_closure: bool = False,
) -> LayeredRoomRingResult:
    """Convenience: verify the declared digest against the bytes, then read the page's native drawings."""
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        return LayeredRoomRingResult(EvidenceResolutionStatus.ABSTAINED, (REASON_SOURCE_HASH,), (), (), 0, 0, 0, 0, 0, 0)
    import fitz

    document = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        drawings = document[page_index].get_drawings()
    finally:
        document.close()
    return build_layered_wall_doorway_room_rings(
        drawings, source_sha256=source_sha256, page_index=page_index,
        sliding_leaf_frame_closure=sliding_leaf_frame_closure,
    )


__all__ = [
    "KIND_STROKE",
    "KIND_SLIDING_LEAF",
    "KIND_CAVITY_SLIDER",
    "KIND_PANEL_LIFT",
    "KIND_SWING",
    "LAYERED_ROOM_RING_SCHEMA_VERSION",
    "LayeredDoorwayClosure",
    "LayeredRoomRingRecord",
    "LayeredRoomRingResult",
    "REASON_OPEN_EXTERIOR",
    "REASON_OPEN_GAP",
    "REASON_RING_CLOSED",
    "build_from_pdf_bytes",
    "build_layered_wall_doorway_room_rings",
]
