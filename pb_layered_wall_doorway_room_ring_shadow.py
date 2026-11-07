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
REASON_SOURCE_HASH = "source_sha256_mismatch"

KIND_SWING = "swing_doorway"
KIND_STROKE = "source_stroke_closure"

_RECORD_SEAL = object()


def _xy(point: Any) -> tuple[float, float]:
    return float(point.x), float(point.y)


def _is_black(color: Any) -> bool:
    return (
        isinstance(color, (tuple, list))
        and len(color) == 3
        and all(type(v) in (int, float) and math.isfinite(v) and 0.0 <= v <= _BLACK_MAX for v in color)
    )


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


def _wall_rows(drawings: Sequence[Mapping[str, Any]]) -> Iterable[tuple[int, Mapping[str, Any]]]:
    for index, row in enumerate(drawings):
        if is_explicit_wall_layer_name(str(row.get("layer") or "")):
            yield index, row


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


def _collect_strips(drawings: Sequence[Mapping[str, Any]]) -> tuple[list[_Strip], list[Polygon]]:
    """Filled opaque-black wall-layer paths. Near-rectangular ones (rectangles and mitred strips whose
    outline fills at least 85% of its bounding box) are strips for run/gap analysis; every other
    filled shape is kept as a plain barrier polygon and counted, never dropped."""
    strips: list[_Strip] = []
    other: list[Polygon] = []
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
                other.append(polygon)
    return _attach_caps(strips), other


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
                current[index] = _Strip(strip.path_index, strip.x0, strip.y0, strip.x1, strip.y1, strip.polygon, forced)
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
        paths = [group[0].path_index]
        for strip in group[1:]:
            s_lo, s_hi = strip.span()
            if s_lo <= hi + NOISE_PT:
                hi = max(hi, s_hi)
                paths.append(strip.path_index)
            else:
                out.append((band, lo, hi, tuple(sorted(set(paths)))))
                lo, hi, paths = s_lo, s_hi, [strip.path_index]
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
                touching = tuple(sorted(s.path_index for s in strips if s.polygon.buffer(NOISE_PT).intersects(rect)))
                same_band = [r for r in _runs(strips, horizontal) if _close(r[0][0], band[0], 0.02) and _close(r[0][1], band[1], 0.02)]
                collinear = any(_close(r[2], a) for r in same_band) and any(_close(r[1], b) for r in same_band)
                found[key] = _Gap(horizontal, band, a, b, touching, (), collinear)
    return list(found.values())


def _swing_arcs(drawings: Sequence[Mapping[str, Any]]) -> tuple[list[dict], int]:
    arcs: list[dict] = []
    rejected = 0
    leaves: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    for index, row in _wall_rows(drawings):
        if row.get("fill") is not None:
            continue
        items = list(row.get("items", ()))
        if len(items) == 1 and items[0][0] == "l":
            leaves.append((index, _xy(items[0][1]), _xy(items[0][2])))
    for index, row in _wall_rows(drawings):
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


def _stroke_closed(drawings: Sequence[Mapping[str, Any]], gap: _Gap) -> Optional[int]:
    """Index of an unfilled wall-layer stroke parallel to the gap and spanning it end to end.

    The stroke may sit on a face line or on the wall's own lining line just outside the band
    (never farther than one wall thickness): CAD exports draw glazing and lining on either.
    """
    thickness = gap.band[1] - gap.band[0]
    for index, row in _wall_rows(drawings):
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
            if near_band and _close(lo, gap.lo) and _close(hi, gap.hi):
                return index
    return None


def _closed_union(polygons: Iterable[Polygon]) -> Any:
    merged = unary_union([p.buffer(_CLOSING_PT, join_style=2) for p in polygons])
    return merged.buffer(-_CLOSING_PT, join_style=2)


def _polygon_parts(geom: Any) -> list[Polygon]:
    if geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "Polygon"]


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


def build_layered_wall_doorway_room_rings(
    drawings: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
    page_index: int,
) -> LayeredRoomRingResult:
    """Rings enclosed by wall ink plus source-attested doorway closures. Never mutates ``drawings``."""
    if type(source_sha256) is not str or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("source_sha256 must be a 64-char lowercase hex digest")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must be a non-negative int")
    strips, other_fills = _collect_strips(drawings)
    unsupported = len(other_fills)
    if not strips:
        return LayeredRoomRingResult(EvidenceResolutionStatus.ABSTAINED, (REASON_NO_WALL_INK,), (), (), 0, 0, 0, unsupported, 0, 0)
    polygons = [s.polygon for s in strips] + list(other_fills)
    union = _closed_union(polygons)
    domain = union.envelope.buffer(1.0, join_style=2)
    gaps = _gaps(strips, union, domain)
    arcs, _rejected_arcs = _swing_arcs(drawings)
    swing_by_gap, unplaced, ambiguous = _place_swings(arcs, gaps)

    closures: list[LayeredDoorwayClosure] = []
    unresolved: list[_Gap] = []
    closure_rects: list[tuple[str, Polygon]] = []
    for gap_index, gap in enumerate(gaps):
        swing = swing_by_gap.get(gap_index)
        stroke = None if swing is not None else _stroke_closed(drawings, gap)
        if swing is None and stroke is None:
            unresolved.append(gap)
            continue
        kind = KIND_SWING if swing is not None else KIND_STROKE
        native = (swing["arc"], swing["leaf"]) if swing is not None else (stroke,)
        closure_id = stable_contract_id(
            "layered_doorway_closure",
            {
                "source_sha256": source_sha256,
                "page_index": page_index,
                "kind": kind,
                "horizontal": gap.horizontal,
                "band": [round(v, 3) for v in gap.band],
                "gap": [round(gap.lo, 3), round(gap.hi, 3)],
                "native": list(native),
            },
            digest_chars=24,
        )
        closures.append(LayeredDoorwayClosure(
            closure_id=closure_id, kind=kind, horizontal=gap.horizontal,
            band=gap.band, gap_interval=(gap.lo, gap.hi), native_path_indices=tuple(native),
            wall_path_indices=tuple(sorted(set(gap.left_path_indices) | set(gap.right_path_indices))),
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
        base = tuple((round(x, 4), round(y, 4)) for x, y in list(part.exterior.coords)[:-1])
        coords = _split_at_closures(base, [(c.horizontal, c.band, c.gap_interval[0], c.gap_interval[1]) for c in closures])
        closure_edges = 0
        wall_edges = 0
        bounding_closures: set[str] = set()
        for a, b in zip(coords, coords[1:] + coords[:1]):
            mid = ((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            owner = next((cid for cid, rect in closure_rects if rect.buffer(NOISE_PT).contains(Point(mid))), None)
            if owner is not None:
                closure_edges += 1
                bounding_closures.add(owner)
            else:
                wall_edges += 1
        wall_paths = tuple(sorted({s.path_index for s in strips if part.buffer(NOISE_PT * 2).intersects(s.polygon)}))
        status = EvidenceResolutionStatus.ABSTAINED if reasons else EvidenceResolutionStatus.CANDIDATE
        if not reasons:
            reasons.append(REASON_RING_CLOSED)
        minx, miny, maxx, maxy = part.bounds
        record_id = stable_contract_id(
            "layered_wall_doorway_room_ring",
            {"source_sha256": source_sha256, "page_index": page_index, "polygon": coords,
             "closures": sorted(bounding_closures), "reasons": reasons},
            digest_chars=32,
        )
        rings.append(LayeredRoomRingRecord(
            record_id=record_id, source_sha256=source_sha256, page_index=page_index,
            polygon_pdf_pts=coords, hole_count=len(part.interiors), area_pt2=round(part.area, 4),
            bbox_pdf_pts=(round(minx, 4), round(miny, 4), round(maxx, 4), round(maxy, 4)),
            wall_edge_count=wall_edges, closure_edge_count=closure_edges,
            bounding_closure_ids=tuple(sorted(bounding_closures)), bounding_wall_path_indices=wall_paths,
            status=status, reason_codes=tuple(reasons), _seal=_RECORD_SEAL,
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


def build_from_pdf_bytes(source_bytes: bytes, *, source_sha256: str, page_index: int) -> LayeredRoomRingResult:
    """Convenience: verify the declared digest against the bytes, then read the page's native drawings."""
    if hashlib.sha256(source_bytes).hexdigest() != source_sha256:
        return LayeredRoomRingResult(EvidenceResolutionStatus.ABSTAINED, (REASON_SOURCE_HASH,), (), (), 0, 0, 0, 0, 0, 0)
    import fitz

    document = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        drawings = document[page_index].get_drawings()
    finally:
        document.close()
    return build_layered_wall_doorway_room_rings(drawings, source_sha256=source_sha256, page_index=page_index)


__all__ = [
    "KIND_STROKE",
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
