"""Shadow check: is a raster footprint candidate drawn in the same pen as the walls it encloses?

Why this exists. The raster stage of ``pb_external_footprint_first_trace`` closes dark ink into one outer contour.
A thin site, roof or dimension frame that encloses several separate buildings closes just as well as a real
wall outline, so the raster alone cannot tell them apart. This module compares the long axis-aligned edges of a
near-rectangular candidate with the page's own native vector ink. It never creates geometry, scale, walls,
areas or authority: a verdict is evidence for a reviewer and for the default-off veto in the first trace.

The signature of a false frame is relative: its edges are drawn in a much lighter pen than the wall linework
inside it. So the reference is taken from the candidate's OWN interior, never from a page-wide statistic or an
absolute width (a count- or percentile-based cutoff moves with every swarm of short hatch ticks):

* a "long edge" is a candidate edge of at least ``LONG_EDGE_SHARE`` of the candidate's shorter side;
* the interior wall pen is the heaviest pen (stroke width, or filled-strip thickness) whose interior linework,
  excluding the edge bands, adds up to at least ``REFERENCE_RUN_SHARE`` of the shorter side;
* an edge is backed when ink at least ``1 / BOLD_RATIO`` as heavy as that pen covers ``MIN_EDGE_COVERAGE`` of its
  length, within the repository's 2.5 pt snap plus half the ink's own thickness (a thick wall's outer face is
  half a thickness from its centre line). ``BOLD_RATIO`` is two pen steps of the usual line-weight series;
* "dark" and "green" use the same predicate as the raster ink mask, so anything the raster saw as ink can be
  seen here.

Only a positive conflict is UNSUPPORTED: an edge covered by native ink, all of it much lighter than the interior
wall pen. Missing, unreadable, ambiguous or oversized native evidence is UNVERIFIABLE, and complex contours are
NOT_APPLICABLE: neither is promoted to a veto. Nothing here is measurement authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Mapping, Sequence

STATUS_SUPPORTED = "NATIVE_EDGE_SUPPORTED"
STATUS_UNSUPPORTED = "NATIVE_EDGE_UNSUPPORTED"
STATUS_NOT_APPLICABLE = "NATIVE_EDGE_NOT_APPLICABLE"
STATUS_UNVERIFIABLE = "NATIVE_EDGE_UNVERIFIABLE"

REASON_SUPPORTED = "every_long_edge_drawn_in_the_interior_wall_pen"
REASON_UNSUPPORTED = "long_edge_drawn_only_in_a_much_lighter_pen_than_the_interior_walls"
REASON_COMPLEX = "contour_has_more_than_eight_vertices"
REASON_FEW_EDGES = "fewer_than_four_long_axis_aligned_edges"
REASON_NO_INK = "no_dark_axis_aligned_native_ink"
REASON_NO_REFERENCE = "no_interior_wall_pen_reference"
REASON_EDGE_UNKNOWN = "long_edge_without_native_ink"
REASON_AMBIGUOUS = "long_edge_covered_only_by_unreadable_dark_fill"
REASON_OVER_CAP = "native_primitive_count_exceeds_20000_cap"
REASON_BAD_POLYGON = "candidate_polygon_invalid"

NATIVE_PRIMITIVE_CAP = 20_000  # the repository's owner limit, unchanged
SNAP_TOL_PT = 2.5  # the repository's snap, used as the position tolerance base
MAX_CANDIDATE_VERTICES = 8
LONG_EDGE_SHARE = 0.18
MIN_SEGMENT_SHARE = 0.02
MIN_EDGE_COVERAGE = 0.25
REFERENCE_RUN_SHARE = 1.0
BOLD_RATIO = 2.0
PEN_CLASS_BIN = 1.1  # pens within 10 percent are one class
AXIS_SLOPE = 0.002  # a native segment is axis-aligned when |minor| <= AXIS_SLOPE * |major|
STRIP_ASPECT = 4.0  # a dark filled rectangle at least this elongated is read as a wall strip
MAX_ITEMS_PER_ROW = 512
_FLOAT_EPS = 1e-7


@dataclass(frozen=True)
class EdgeSupport:
    orientation: str
    position: float
    start: float
    end: float
    backed_cover: float
    any_ink_cover: float
    unreadable_fill_cover: float

    def to_dict(self) -> dict[str, object]:
        return {
            "orientation": self.orientation,
            "position": self.position,
            "start": self.start,
            "end": self.end,
            "backed_cover": round(self.backed_cover, 4),
            "any_ink_cover": round(self.any_ink_cover, 4),
            "unreadable_fill_cover": round(self.unreadable_fill_cover, 4),
        }


@dataclass(frozen=True)
class FootprintNativeEdgeSupport:
    status: str
    reason: str
    edges: tuple[EdgeSupport, ...] = ()
    reference_thickness: float | None = None
    rows_examined: int = 0
    commercial_publishable: bool = False
    measurement_authorized: bool = False
    deduction_authority: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "edges": [e.to_dict() for e in self.edges],
            "reference_thickness": self.reference_thickness,
            "rows_examined": self.rows_examined,
            "commercial_publishable": False,
            "measurement_authorized": False,
            "deduction_authority": False,
        }


def _finite(*values: object) -> bool:
    return all(type(v) in (int, float) and math.isfinite(v) for v in values)


def _xy(point: object) -> tuple[float, float] | None:
    try:
        if hasattr(point, "x"):
            xy = (float(point.x), float(point.y))  # type: ignore[attr-defined]
        else:
            xy = (float(point[0]), float(point[1]))  # type: ignore[index]
    except (TypeError, ValueError, AttributeError, IndexError):
        return None
    return xy if all(math.isfinite(v) for v in xy) else None


def _rect(value: object) -> tuple[float, float, float, float] | None:
    try:
        if hasattr(value, "x0"):
            r = (float(value.x0), float(value.y0), float(value.x1), float(value.y1))  # type: ignore[attr-defined]
        else:
            r = tuple(float(v) for v in value)  # type: ignore[union-attr]
            if len(r) != 4:
                return None
    except (TypeError, ValueError, AttributeError):
        return None
    if not all(math.isfinite(v) for v in r):
        return None
    return (min(r[0], r[2]), min(r[1], r[3]), max(r[0], r[2]), max(r[1], r[3]))


def _is_raster_ink(color: object) -> bool:
    """Same predicate as the raster ink mask: dark (gray < 125/255) and not the green exclusion art."""
    if not isinstance(color, (list, tuple)) or len(color) != 3 or not _finite(*color):
        return False
    r, g, b = (float(v) * 255.0 for v in color)
    if not all(0.0 <= v <= 255.0 for v in (r, g, b)):
        return False
    if g > r * 1.25 and g > b * 1.08 and g > 40:
        return False
    return 0.299 * r + 0.587 * g + 0.114 * b < 125


def _axis_segment(p: object, q: object, min_length: float) -> tuple[str, float, float, float] | None:
    a, b = _xy(p), _xy(q)
    if a is None or b is None:
        return None
    dx, dy = b[0] - a[0], b[1] - a[1]
    if abs(dx) >= min_length and abs(dy) <= AXIS_SLOPE * abs(dx):
        return ("h", (a[1] + b[1]) / 2.0, min(a[0], b[0]), max(a[0], b[0]))
    if abs(dy) >= min_length and abs(dx) <= AXIS_SLOPE * abs(dy):
        return ("v", (a[0] + b[0]) / 2.0, min(a[1], b[1]), max(a[1], b[1]))
    return None


def _item_edges(item: object) -> Iterable[tuple[object, object]]:
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return ()
    kind = item[0]
    if kind == "l" and len(item) >= 3:
        return ((item[1], item[2]),)
    if kind == "re":
        r = _rect(item[1])
        if r is None:
            return ()
        c = ((r[0], r[1]), (r[2], r[1]), (r[2], r[3]), (r[0], r[3]))
        return tuple((c[i], c[(i + 1) % 4]) for i in range(4))
    if kind == "qu":
        quad = item[1]
        try:
            c = (quad.ul, quad.ur, quad.lr, quad.ll)
        except AttributeError:
            return ()
        return tuple((c[i], c[(i + 1) % 4]) for i in range(4))
    return ()


def _long_edges(points: Sequence[tuple[float, float]]) -> tuple[list[tuple[str, float, float, float]], float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    short_side = min(max(xs) - min(xs), max(ys) - min(ys))
    floor = LONG_EDGE_SHARE * short_side
    edges: list[tuple[str, float, float, float]] = []
    for a, b in zip(points, (*points[1:], points[0])):
        if abs(a[1] - b[1]) <= SNAP_TOL_PT and abs(a[0] - b[0]) >= floor:
            edges.append(("h", (a[1] + b[1]) / 2.0, min(a[0], b[0]), max(a[0], b[0])))
        elif abs(a[0] - b[0]) <= SNAP_TOL_PT and abs(a[1] - b[1]) >= floor:
            edges.append(("v", (a[0] + b[0]) / 2.0, min(a[1], b[1]), max(a[1], b[1])))
    return edges, short_side


def _inside(points: Sequence[tuple[float, float]], x: float, y: float) -> bool:
    inside, j = False, len(points) - 1
    for i, (xi, yi) in enumerate(points):
        xj, yj = points[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _covered(spans: list[tuple[float, float]], start: float, end: float) -> float:
    covered, last = 0.0, start
    for lo, hi in sorted(spans):
        if hi > last:
            covered += hi - max(last, lo)
            last = hi
    return covered / (end - start) if end > start else 0.0


def _interior_wall_pen(
    points: Sequence[tuple[float, float]],
    edges: Sequence[tuple[str, float, float, float]],
    inks: Sequence[tuple[str, float, float, float, float]],
    short_side: float,
) -> float | None:
    """Heaviest pen whose linework inside the candidate (edge bands excluded) adds up to a wall run."""
    classes: dict[int, list[float]] = {}  # pen class -> [heaviest thickness, total length]
    for orientation, at, lo, hi, thickness in inks:
        if any(
            orientation == eo and abs(at - eat) <= SNAP_TOL_PT + thickness / 2.0 and min(hi, eend) > max(lo, estart)
            for eo, eat, estart, eend in edges
        ):
            continue
        mx, my = ((lo + hi) / 2.0, at) if orientation == "h" else (at, (lo + hi) / 2.0)
        if not _inside(points, mx, my):
            continue
        key = round(math.log(thickness) / math.log(PEN_CLASS_BIN))
        entry = classes.setdefault(key, [thickness, 0.0])
        entry[0] = max(entry[0], thickness)
        entry[1] += hi - lo
    heavy = [entry[0] for entry in classes.values() if entry[1] >= REFERENCE_RUN_SHARE * short_side]
    return max(heavy) if heavy else None


def assess_footprint_native_edge_support(
    polygon_pdf_pts: Sequence[Sequence[float]],
    rows: Sequence[Mapping[str, object]],
) -> FootprintNativeEdgeSupport:
    """Compare a raster footprint candidate's long edges with the page's native dark ink.

    ``rows`` are the page's native drawing rows (PyMuPDF ``get_drawings`` shape: ``type``, ``color``,
    ``fill``, ``width``, ``items``, ``rect``). The rows are only read.
    """
    points: list[tuple[float, float]] = []
    for p in polygon_pdf_pts:
        xy = _xy(p)
        if xy is None:
            return FootprintNativeEdgeSupport(STATUS_UNVERIFIABLE, REASON_BAD_POLYGON)
        points.append(xy)
    if len(points) < 4 or len(set(points)) < 4:
        return FootprintNativeEdgeSupport(STATUS_UNVERIFIABLE, REASON_BAD_POLYGON)
    if len(points) > MAX_CANDIDATE_VERTICES:
        return FootprintNativeEdgeSupport(STATUS_NOT_APPLICABLE, REASON_COMPLEX)
    edges, short_side = _long_edges(points)
    if not short_side > 0 or len(edges) < 4:
        return FootprintNativeEdgeSupport(STATUS_NOT_APPLICABLE, REASON_FEW_EDGES)
    row_list = rows if isinstance(rows, (list, tuple)) else tuple(rows)
    if len(row_list) > NATIVE_PRIMITIVE_CAP:
        return FootprintNativeEdgeSupport(STATUS_UNVERIFIABLE, REASON_OVER_CAP, rows_examined=len(row_list))

    min_length = MIN_SEGMENT_SHARE * short_side
    # (orientation, position, start, end, thickness)
    inks: list[tuple[str, float, float, float, float]] = []
    blobs: list[tuple[float, float, float, float]] = []  # dark fills that are not readable as strips
    for row in row_list:
        if not isinstance(row, Mapping):
            continue
        row_type = row.get("type")
        if row_type in ("s", "fs"):
            width, items = row.get("width"), row.get("items", ())
            if (
                _is_raster_ink(row.get("color")) and _finite(width) and width > 0
                and isinstance(items, (list, tuple)) and len(items) <= MAX_ITEMS_PER_ROW
            ):
                for item in items:
                    for p, q in _item_edges(item):
                        seg = _axis_segment(p, q, min_length)
                        if seg is not None:
                            inks.append((*seg, float(width)))
        if row_type in ("f", "fs") and _is_raster_ink(row.get("fill")):
            rect = _rect(row.get("rect"))
            if rect is None:
                continue
            w, h = rect[2] - rect[0], rect[3] - rect[1]
            if w <= 0 or h <= 0 or max(w, h) < min_length:
                continue
            if max(w, h) >= STRIP_ASPECT * min(w, h):
                if w >= h:
                    inks.append(("h", (rect[1] + rect[3]) / 2.0, rect[0], rect[2], h))
                else:
                    inks.append(("v", (rect[0] + rect[2]) / 2.0, rect[1], rect[3], w))
            else:
                blobs.append(rect)
    if not inks:
        return FootprintNativeEdgeSupport(STATUS_UNVERIFIABLE, REASON_NO_INK, rows_examined=len(row_list))
    reference = _interior_wall_pen(points, edges, inks, short_side)
    if reference is None:
        return FootprintNativeEdgeSupport(STATUS_UNVERIFIABLE, REASON_NO_REFERENCE, rows_examined=len(row_list))

    threshold = reference / BOLD_RATIO
    supports: list[EdgeSupport] = []
    for orientation, at, start, end in edges:
        backed_spans: list[tuple[float, float]] = []
        any_spans: list[tuple[float, float]] = []
        for direction, source_at, a, b, thickness in inks:
            if direction != orientation or abs(source_at - at) > SNAP_TOL_PT + thickness / 2.0:
                continue
            lo, hi = max(start, a), min(end, b)
            if hi <= lo:
                continue
            any_spans.append((lo, hi))
            if thickness + _FLOAT_EPS >= threshold:
                backed_spans.append((lo, hi))
        blob_spans: list[tuple[float, float]] = []
        for x0, y0, x1, y1 in blobs:
            a, b, lo_perp, hi_perp = (x0, x1, y0, y1) if orientation == "h" else (y0, y1, x0, x1)
            if lo_perp - SNAP_TOL_PT <= at <= hi_perp + SNAP_TOL_PT:
                lo, hi = max(start, a), min(end, b)
                if hi > lo:
                    blob_spans.append((lo, hi))
        supports.append(EdgeSupport(
            orientation, round(at, 3), round(start, 3), round(end, 3),
            _covered(backed_spans, start, end), _covered(any_spans, start, end),
            _covered(blob_spans, start, end),
        ))

    def verdict(status: str, reason: str) -> FootprintNativeEdgeSupport:
        return FootprintNativeEdgeSupport(status, reason, tuple(supports), reference, len(row_list))

    unbacked = [s for s in supports if s.backed_cover < MIN_EDGE_COVERAGE]
    if not unbacked:
        return verdict(STATUS_SUPPORTED, REASON_SUPPORTED)
    if any(s.any_ink_cover >= MIN_EDGE_COVERAGE and s.unreadable_fill_cover < MIN_EDGE_COVERAGE for s in unbacked):
        return verdict(STATUS_UNSUPPORTED, REASON_UNSUPPORTED)
    if any(s.unreadable_fill_cover >= MIN_EDGE_COVERAGE for s in unbacked):
        return verdict(STATUS_UNVERIFIABLE, REASON_AMBIGUOUS)
    return verdict(STATUS_UNVERIFIABLE, REASON_EDGE_UNKNOWN)
