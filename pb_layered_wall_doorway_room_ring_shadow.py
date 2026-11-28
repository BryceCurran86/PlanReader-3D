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
from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import math
from typing import Any, Iterable, Optional, Sequence

from shapely.geometry import LineString, Point, Polygon, box
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name

LAYERED_ROOM_RING_SCHEMA_VERSION = "1.0.0"

NOISE_PT = 0.05  # representation noise only; NOT the 2.5 pt production snap
_CLOSING_PT = 0.03  # hairline closing between exactly shared strip edges
_BLACK_MAX = 0.04
# Black source-line pair geometry, ported from Cursor's evidence-bound
# candidate tracer. It cannot publish a wall/room quantity on its own.
_STROKE_PAIR_THICK_MIN = 1.2
_STROKE_PAIR_THICK_MAX = 8.0
_STROKE_PAIR_MIN_SPAN = 8.0
_STROKE_PAIR_FACE_PT = 0.35
_STROKE_PAIR_CLUSTER_PT = 0.8
_DARK_FILL_THICK_MAX = 14.0
# PDF-point candidate heuristic only. Not a physical wall identity or scale rule.
_WALL_END_SUPPORT_SPAN = 80.0
_WALL_END_CLOSER_SPAN = 20.0
# Thin CAD exterior faces (often dashed ~3.5 pt gaps) merge into topology bands.
# Never a wall-body join snap or measurement authority.
_CAD_DASH_GAP_PT = 4.0
_MERGED_FACE_MIN_SPAN = 40.0
_MERGED_FACE_WIDTH_MIN = 0.2
_MERGED_FACE_WIDTH_MAX = 6.0

_ARC_CIRCULARITY = 0.002  # relative; a cubic Bezier quarter circle deviates by about 0.0003

REASON_RING_CLOSED = "layered_wall_ring_closed_by_source_ink"
REASON_OPEN_GAP = "open_wall_gap_unresolved"
REASON_OPEN_EXTERIOR = "open_to_exterior"
REASON_NO_WALL_INK = "no_wall_layer_strips"
REASON_UNOWNED_EDGE = "ring_edge_without_source_owner"
REASON_SOURCE_HASH = "source_sha256_mismatch"
REASON_UNLABELLED_SOURCE_PRIMITIVE_CAP = (
    "unlabelled_dark_wall_page_exceeds_20000_primitive_cap_needs_bounded_viewport"
)

KIND_SWING = "swing_doorway"
KIND_STROKE = "source_stroke_closure"
KIND_SLIDING_LEAF = "sliding_leaf_frame_closure"

_RECORD_SEAL = object()


def _xy(point: Any) -> tuple[float, float]:
    return float(point.x), float(point.y)


def _is_black(color: Any) -> bool:
    return (
        isinstance(color, (tuple, list))
        and len(color) == 3
        and all(type(v) in (int, float) and math.isfinite(v) and 0.0 <= v <= _BLACK_MAX for v in color)
    )


def _visible_source_stroke_paint(row: Mapping[str, Any]) -> bool:
    """Finite positive stroke opacity only. Bool, NaN, zero and junk stay unresolved.

    Missing paint defaults to opaque CAD (1.0), matching fill_opacity on dark
    bars. An explicit False/True is not a PDF float and cannot close a room.
    """
    opacity = row.get("stroke_opacity", 1.0)
    if type(opacity) is bool or type(opacity) not in (int, float):
        return False
    return math.isfinite(opacity) and opacity > 0.0


def _clip_allows_point(row: Mapping[str, Any], x: float, y: float) -> bool:
    """Fail closed when an active scissor is unknown or excludes the stroke."""
    scissor = row.get("scissor")
    if scissor is None:
        return True
    try:
        if hasattr(scissor, "x0"):
            x0, y0, x1, y1 = (
                float(scissor.x0), float(scissor.y0),
                float(scissor.x1), float(scissor.y1),
            )
        else:
            x0, y0, x1, y1 = (float(value) for value in scissor)
    except (TypeError, ValueError, AttributeError):
        return False
    if not all(math.isfinite(value) for value in (x0, y0, x1, y1)):
        return False
    lo_x, hi_x = (x0, x1) if x0 <= x1 else (x1, x0)
    lo_y, hi_y = (y0, y1) if y0 <= y1 else (y1, y0)
    return lo_x - NOISE_PT <= x <= hi_x + NOISE_PT and lo_y - NOISE_PT <= y <= hi_y + NOISE_PT


def _later_opaque_fill_covers(
    drawings: Sequence[Mapping[str, Any] | None],
    index: int,
    x: float,
    y: float,
) -> bool:
    """A later opaque fill that covers the stroke hides it. Paint order is source order."""
    for later in range(index + 1, len(drawings)):
        row = drawings[later]
        if not isinstance(row, Mapping) or row.get("fill") is None or not _opaque(row):
            continue
        x0, y0, x1, y1 = _row_bounds(row)
        if x0 - 1e-6 <= x <= x1 + 1e-6 and y0 - 1e-6 <= y <= y1 + 1e-6:
            return True
    return False


def _owner_excluded_green_ink(color: Any) -> bool:
    """Owner: green aisle/equipment/cold-room details are NOT wall geometry.

    This filter belongs ONLY to native wall/room tracing; cold-room
    finishes, room labels, and original PDF layers remain available to
    their separate source authorities. R/G/B paint channels are PDF-native
    normalized floats, not colours interpreted from a raster image.
    """
    return (
        isinstance(color, (tuple, list))
        and len(color) == 3
        and all(
            type(component) in (int, float)
            and math.isfinite(component)
            and 0 <= component <= 1
            for component in color
        )
        and color[1] >= 0.16
        and color[1] > 1.25 * color[0]
        and color[1] > 1.08 * color[2]
    )


def _is_dark_neutral_paint(color: Any) -> bool:
    """Near-black / dark gray CAD paint (≤0.25), not mid-gray glazing evidence."""
    return (
        isinstance(color, (tuple, list))
        and len(color) == 3
        and all(
            type(v) in (int, float) and math.isfinite(v) and 0.0 <= v <= 0.25
            for v in color
        )
        and max(color) - min(color) <= 0.03
    )


def _is_source_wall_support_row(row: Mapping[str, Any]) -> bool:
    """Named wall layer with dark paint, black stroke, or near-black fill — not mid-gray."""
    fill, stroke = row.get("fill"), row.get("color")
    if _owner_excluded_green_ink(fill) or _owner_excluded_green_ink(stroke):
        return False
    # Unfilled mid-gray / pale strokes stay doorway/glazing evidence only even
    # when the CAD layer name says Wall*; they must not mint wall strips or
    # alone authorize a bounded footprint primitive count.
    if (
        fill is None
        and stroke is not None
        and not _is_black(stroke)
        and not _is_dark_neutral_paint(stroke)
    ):
        return False
    return bool(
        is_explicit_wall_layer_name(str(row.get("layer") or ""))
        or (fill is None and _is_black(stroke) and _visible_source_stroke_paint(row))
        or _is_dark_neutral_paint(fill)
    )


_ROLE_GREEN = "green"
_ROLE_WALL_SUPPORT = "wall_support"
_ROLE_OPAQUE_FILL = "opaque_fill"
_ROLE_EVIDENCE = "evidence"
_ROLE_BLANK = "blank"
# The rows the structural wall hypothesis is built from. Evidence strokes are not in this set.
_STRUCTURAL_ROLES = frozenset({_ROLE_WALL_SUPPORT, _ROLE_OPAQUE_FILL})


def _source_wall_ink_role(row: Any) -> str:
    """The one decision of how a source row is used by the wall-ink selector.

    ``green``: owner-excluded aisle/equipment ink (blanked). ``wall_support``: named wall layer,
    black stroke or near-black fill. ``opaque_fill``: any other opaque fill, kept only because it
    can hide a stroke. ``evidence``: an unfilled, visible, non-green stroke that is not wall
    support: doorway/glazing evidence for the closure searches, never a wall strip. ``blank``:
    everything else (including a row that is not a mapping).
    """
    if not isinstance(row, Mapping):
        return _ROLE_BLANK
    fill, stroke = row.get("fill"), row.get("color")
    if _owner_excluded_green_ink(fill) or _owner_excluded_green_ink(stroke):
        return _ROLE_GREEN
    if _is_source_wall_support_row(row):
        return _ROLE_WALL_SUPPORT
    if row.get("fill") is not None and _opaque(row):
        return _ROLE_OPAQUE_FILL
    if fill is None and row.get("items") and _visible_source_stroke_paint(row):
        return _ROLE_EVIDENCE
    return _ROLE_BLANK


def structural_native_primitive_count(drawings: Sequence[Any]) -> int:
    """Native primitives (line/curve/rect operations, not PDF path containers) on the STRUCTURAL rows.

    Structural means ``wall_support`` and ``opaque_fill`` rows: the set the 20,000-primitive cap of
    the dark-painted layered ring counted until ``_source_wall_ink_candidate_drawings`` began
    retaining doorway/glazing evidence strokes. Evidence strokes and green ink are not counted.
    The classification is idempotent over the selector, so the count is the same on the original
    rows and on the selector's output. This is a bound on work, not an authority.
    """
    total = 0
    for row in drawings:
        if _source_wall_ink_role(row) in _STRUCTURAL_ROLES:
            total += len(row.get("items", ()))
    return total


def _source_wall_ink_candidate_drawings(
    drawings: Sequence[Mapping[str, Any]],
) -> tuple[tuple[Mapping[str, Any], ...], int, int]:
    """Select wall-relevant source ink, keeping EVERY original path index.

    Non-black strokes (except separately authenticated wall-layer ink)
    are not proof of a wall. In particular green plan overlay artwork
    never enters room planarization. This is NOT a source deletion: the
    output contains empty inert rows in exactly the same indices so
    source-owned native path numbers cannot be silently reindexed.

    Unfilled non-green strokes are retained as doorway/glazing *evidence*
    only (``_stroke_closed``, jamb caps). Strip collectors still require
    black/dark/named wall paint and do not promote mid-gray lining to a wall.
    """
    blank: Mapping[str, Any] = {
        "layer": "", "fill": None, "color": None, "items": (),
    }
    kept: list[Mapping[str, Any]] = []
    supported = 0
    green_excluded = 0
    for row in drawings:
        role = _source_wall_ink_role(row)
        if role == _ROLE_GREEN:
            kept.append(blank)
            green_excluded += 1
        elif role == _ROLE_BLANK:
            kept.append(blank)
        else:
            if role == _ROLE_WALL_SUPPORT:
                supported += 1
            # Later opaque fills are kept so they can hide a stroke (not a wall);
            # glazing/lining CAD strokes (often mid-gray) close host wall gaps.
            kept.append(row)
    return tuple(kept), supported, green_excluded


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
    path_indices: tuple[int, ...] = ()  # paired source strokes retain BOTH original native paths

    def native_path_indices(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.path_indices or (self.path_index,))))

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
    # Original PDF black segmented arcs + radial leaves, NOT sealed
    # openings, hosted frames or customer wall geometry.
    source_segmented_swing_witnesses: tuple[Mapping[str, Any], ...] = ()
    source_owned_doorway_chords: tuple[Mapping[str, Any], ...] = ()
    # Candidate-only original-path witnesses for each unclosed collinear wall
    # interruption. No hosts, closures, lengths, room quantities or FIRM.
    unresolved_gap_witnesses: tuple[Mapping[str, Any], ...] = ()
    unresolved_gap_witness_count: int = 0
    # Topology-only free-space planarization audit. Never room quantity authority.
    free_space_part_count: int = 0
    free_space_exterior_touching_count: int = 0
    free_space_enclosed_part_count: int = 0
    free_space_max_enclosed_area_pt2: float = 0.0
    merged_collinear_dark_face_strip_count: int = 0
    # Topology-only size tiers for candidate rings (not room quantity authority).
    ring_area_tier_lt_100_count: int = 0
    ring_area_tier_100_to_1000_count: int = 0
    ring_area_tier_ge_1000_count: int = 0
    drafting_pocket_sliver_count: int = 0


def _wall_rows(drawings: Sequence[Mapping[str, Any]]) -> Iterable[tuple[int, Mapping[str, Any]]]:
    for index, row in enumerate(drawings):
        if is_explicit_wall_layer_name(str(row.get("layer") or "")):
            yield index, row


def _source_rows(
    drawings: Sequence[Mapping[str, Any] | None], *, all_ink: bool = False,
) -> Iterable[tuple[int, Mapping[str, Any]]]:
    """Named wall-layer rows, or every remaining source-visible candidate path."""
    if all_ink:
        for index, row in enumerate(drawings):
            if isinstance(row, Mapping) and row.get("items"):
                yield index, row
        return
    yield from _wall_rows(drawings)


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


def _orthogonal_wall_fill_strips(index: int, polygon: Polygon) -> list[_Strip]:
    """Axis-aligned rectangular bars covering an orthogonal notched wall fill.

    CAD wall pockets fail the 85% strip test, so they never enter run hashing.
    Vertex-grid cells that lie inside the fill and have wall thickness become
    traced bars. The notch itself is empty, so no doorway is invented. Topology
    still uses the exact fill polygon as a barrier; these bars are length-only.
    """
    pts = list(polygon.exterior.coords)
    if len(pts) < 5:
        return []
    for start, end in zip(pts, pts[1:]):
        if abs(start[0] - end[0]) > NOISE_PT and abs(start[1] - end[1]) > NOISE_PT:
            return []
    xs = sorted({round(float(x), 4) for x, _y in pts})
    ys = sorted({round(float(y), 4) for _x, y in pts})
    if len(xs) < 2 or len(ys) < 2:
        return []
    grown = polygon.buffer(NOISE_PT, join_style=2)
    bars: list[_Strip] = []
    for x0, x1 in zip(xs, xs[1:]):
        for y0, y1 in zip(ys, ys[1:]):
            width, height = x1 - x0, y1 - y0
            if width <= NOISE_PT or height <= NOISE_PT:
                continue
            thick, span = min(width, height), max(width, height)
            if not (_STROKE_PAIR_THICK_MIN <= thick <= _DARK_FILL_THICK_MAX and span >= 8.0):
                continue
            cell = box(x0, y0, x1, y1)
            if not grown.contains(cell.centroid):
                continue
            if cell.difference(grown).area > 0.1 * cell.area:
                continue
            bars.append(_Strip(index, x0, y0, x1, y1, cell))
    return bars


def _collect_dark_painted_source_wall_strips(
    drawings: Sequence[Mapping[str, Any]],
) -> list[_Strip]:
    """Extract actual native dark-filled narrow bars, NOT white PDF masks.

    Some original plans paint structural wall faces as a dark grey fill on
    unnamed layers rather than opaque BLACK explicit wall-layer ink.
    This is a source-native extra wall hypothesis, default OFF. It is never
    a physical finished-face authority or a measurement on its own.
    Each bar keeps its exact original PDF drawing path index and endpoints.
    """
    candidates: list[_Strip] = []
    for path_index, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        color = row.get("fill")
        if not (
            isinstance(color, (tuple, list))
            and len(color) == 3
            and all(
                type(v) in (float, int) and math.isfinite(v)
                and 0 <= v <= 0.25 for v in color
            )
            and max(color) - min(color) <= 0.03
        ):
            continue
        # Named black wall polygons already enter through _collect_strips.
        # Anonymous black bars need the same source-paint route as grey bars.
        if _is_black(color) and is_explicit_wall_layer_name(str(row.get("layer") or "")):
            continue
        if row.get("color") is not None:
            continue
        try:
            fill_opacity = float(row.get("fill_opacity", 1))
        except (ValueError, TypeError):
            continue
        if not math.isfinite(fill_opacity) or fill_opacity < 0.995:
            continue
        for item in row.get("items", ()):
            bounds = _rect_of_item(item)
            if bounds is None:
                continue
            x0, y0, x1, y1 = bounds
            if not all(math.isfinite(v) for v in bounds):
                continue
            width, height = x1 - x0, y1 - y0
            if width <= 0 or height <= 0:
                continue
            thickness = min(width, height)
            span = max(width, height)
            if not (1.2 <= thickness <= _DARK_FILL_THICK_MAX and span >= 8.0):
                continue
            # An independent long dark source fill is a wall hypothesis.
            # A square dark cabinet / label mask / furniture is not a wall.
            if span / thickness < 4.0:
                continue
            candidates.append(
                _Strip(path_index, x0, y0, x1, y1, box(*bounds))
            )
    return _attach_caps(candidates)


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
        if not _visible_source_stroke_paint(row):
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
            if not _clip_allows_point(row, mid.x, mid.y):
                continue
            if _later_opaque_fill_covers(drawings, index, mid.x, mid.y):
                continue
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


# Black source stroke-pair evidence adapted from PR #4284's Cursor
# experimental wall-pair tracer into the ORIGINAL PlanReader source path.
# No Next runtime import, new customer issuer or frozen-score modification.
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
        if not _visible_source_stroke_paint(row):
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

def _collect_source_heavy_stroke_strips(
    drawings: Sequence[Mapping[str, Any] | None],
) -> list[_Strip]:
    """Opaque black heavy native line paint as topology-only wall-band candidates.

    Some CAD sheets paint a wall as one 1.2–6 pt source stroke instead of a
    fill or a paired face. Axis-aligned, long, source-black, opaque strokes
    become candidate bands with their original path index. Hairline drafting
    ink, green, faint, short, and diagonal strokes are not walls. This does
    not mint a physical wall, close a gap, or issue area.
    """
    found: list[_Strip] = []
    seen: set[tuple[int, float, float, float, float]] = set()
    for index, row in enumerate(drawings):
        if row is None or row.get("fill") is not None:
            continue
        if not _is_black(row.get("color")):
            continue
        opacity = row.get("stroke_opacity", 1.0)
        if type(opacity) is bool or type(opacity) not in (int, float):
            continue
        if not math.isfinite(opacity) or opacity < 0.95:
            continue
        width = row.get("width", 0)
        if type(width) is bool or type(width) not in (int, float):
            continue
        width_f = float(width)
        if not math.isfinite(width_f) or width_f > 6.0 or width_f < 0.45:
            continue
        for item in row.get("items") or ():
            if not item or item[0] != "l" or len(item) < 3:
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if not all(math.isfinite(v) for v in (ax, ay, bx, by)):
                continue
            if abs(ay - by) < 0.08 and abs(ax - bx) >= 12.0:
                span = abs(ax - bx)
                x0, x1 = sorted((ax, bx))
                mid_y = (ay + by) / 2.0
                # Medium-width (0.45–1.2) only for long structural faces.
                if width_f < 1.2 and span < _WALL_END_SUPPORT_SPAN:
                    continue
                half = max(width_f, _STROKE_PAIR_THICK_MIN) / 2.0
                y0, y1 = mid_y - half, mid_y + half
            elif abs(ax - bx) < 0.08 and abs(ay - by) >= 12.0:
                span = abs(ay - by)
                y0, y1 = sorted((ay, by))
                mid_x = (ax + bx) / 2.0
                if width_f < 1.2 and span < _WALL_END_SUPPORT_SPAN:
                    continue
                half = max(width_f, _STROKE_PAIR_THICK_MIN) / 2.0
                x0, x1 = mid_x - half, mid_x + half
            else:
                continue
            key = (index, round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4))
            if key in seen:
                continue
            seen.add(key)
            found.append(_Strip(index, x0, y0, x1, y1, box(x0, y0, x1, y1)))
    return found


def _dark_face_stroke_rgb(color: Any) -> bool:
    """Dark CAD stroke paint for merged-face topology only (not mid-gray guides)."""
    if not isinstance(color, (tuple, list)) or len(color) != 3:
        return False
    if any(type(v) is bool or type(v) not in (int, float) for v in color):
        return False
    values = tuple(float(v) for v in color)
    return all(math.isfinite(v) and 0.0 <= v <= 0.4 for v in values)


def _collect_merged_collinear_dark_face_strips(
    drawings: Sequence[Mapping[str, Any] | None],
) -> list[_Strip]:
    """Merge collinear thin/dashed dark CAD faces into topology-only wall bands.

    Some exterior walls are drawn as one dashed or thin dark face (Acacia west
    ~0.5 pt dashes with ~3.5 pt gaps) rather than a fill or a 1.2 pt heavy stroke.
    Collinear dashes along one face become one candidate band after CAD-dash gap
    merge. A single short drafting mark is not a wall. This never authenticates
    a physical wall, closes a doorway, or issues area.
    """
    raw: list[tuple[int, bool, float, float, float, float]] = []
    for index, row in enumerate(drawings):
        if row is None or row.get("fill") is not None:
            continue
        if not _dark_face_stroke_rgb(row.get("color")):
            continue
        if not _visible_source_stroke_paint(row):
            continue
        width = row.get("width", 0)
        if type(width) is bool or type(width) not in (int, float):
            continue
        width_f = float(width)
        if not math.isfinite(width_f):
            continue
        if not (_MERGED_FACE_WIDTH_MIN <= width_f <= _MERGED_FACE_WIDTH_MAX):
            continue
        for item in row.get("items") or ():
            if not item or item[0] != "l" or len(item) < 3:
                continue
            (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
            if not all(math.isfinite(v) for v in (ax, ay, bx, by)):
                continue
            if _close(ay, by, 1e-3) and abs(bx - ax) > NOISE_PT:
                lo, hi = sorted((ax, bx))
                raw.append((index, True, (ay + by) / 2.0, lo, hi, width_f))
            elif _close(ax, bx, 1e-3) and abs(by - ay) > NOISE_PT:
                lo, hi = sorted((ay, by))
                raw.append((index, False, (ax + bx) / 2.0, lo, hi, width_f))
    found: list[_Strip] = []
    seen: set[tuple[float, float, float, float]] = set()
    for horiz in (True, False):
        members = [item for item in raw if item[1] is horiz]
        members.sort(key=lambda item: (item[2], item[3], item[4]))
        buckets: list[list[tuple[int, bool, float, float, float, float]]] = []
        for stroke in members:
            if buckets and abs(stroke[2] - buckets[-1][0][2]) <= NOISE_PT:
                buckets[-1].append(stroke)
            else:
                buckets.append([stroke])
        for bucket in buckets:
            ordered = sorted(bucket, key=lambda item: (item[3], item[4]))
            run = [ordered[0]]
            lo, hi = ordered[0][3], ordered[0][4]
            for stroke in ordered[1:]:
                if stroke[3] <= hi + _CAD_DASH_GAP_PT:
                    run.append(stroke)
                    hi = max(hi, stroke[4])
                    continue
                _emit_merged_face_strip(found, seen, run, lo, hi, horiz)
                run = [stroke]
                lo, hi = stroke[3], stroke[4]
            _emit_merged_face_strip(found, seen, run, lo, hi, horiz)
    return found


def _emit_merged_face_strip(
    found: list[_Strip],
    seen: set[tuple[float, float, float, float]],
    run: Sequence[tuple[int, bool, float, float, float, float]],
    lo: float,
    hi: float,
    horiz: bool,
) -> None:
    span = hi - lo
    if span < _MERGED_FACE_MIN_SPAN:
        return
    ids = tuple(sorted({item[0] for item in run}))
    # Require ≥2 original path indices so a lone wall-end closer stroke cannot
    # mint a face band and bypass wall_end_stroke_closures. Dashed exterior
    # faces (Acacia west) naturally supply many collinear dash paths.
    if len(ids) < 2:
        return
    perp = sum(item[2] for item in run) / len(run)
    width = max(item[5] for item in run)
    half = max(width, _STROKE_PAIR_THICK_MIN) / 2.0
    if horiz:
        x0, x1, y0, y1 = lo, hi, perp - half, perp + half
    else:
        x0, x1, y0, y1 = perp - half, perp + half, lo, hi
    key = (round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
    if key in seen:
        return
    seen.add(key)
    found.append(
        _Strip(
            ids[0], x0, y0, x1, y1, box(x0, y0, x1, y1),
            path_indices=ids,
        )
    )


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
                    strip.path_index, strip.x0, strip.y0, strip.x1, strip.y1,
                    strip.polygon, forced, strip.native_path_indices(),
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


def _unique_collinear_run_end_paths(
    same_band_runs: Sequence[tuple],
    lo: float,
    hi: float,
) -> tuple[tuple[int, ...], tuple[int, ...], bool]:
    """Unique-or-abstain collinear owners of a gap's two run ends.

    A collinear interruption is the free interval between two runs of one
    band. Left is the unique run that ends at ``lo``; right is the unique run
    that starts at ``hi``. Two 0.02-close rival bands, or a missing end,
    leave both sides empty so callers keep the unsided touching inventory
    and do not invent a host. This does not close the gap.
    """
    left_runs = [run for run in same_band_runs if _close(run[2], lo)]
    right_runs = [run for run in same_band_runs if _close(run[1], hi)]
    if len(left_runs) != 1 or len(right_runs) != 1:
        return (), (), False
    return (
        tuple(sorted(left_runs[0][3])),
        tuple(sorted(right_runs[0][3])),
        True,
    )


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
        # Immutable run inventory for this orientation. Rebuilding it per
        # doorway was quadratic on original CAD sheets. Same grouped runs
        # for candidate and collinearity checks; never infer a closure.
        orientation_runs = _runs(strips, horizontal)
        band_components: dict[tuple[float, float], list[Polygon]] = {}
        band_runs: dict[tuple[float, float], list[tuple]] = {}
        for run in orientation_runs:
            band_runs.setdefault(run[0], []).append(run)
        for band, lo, hi, _paths in orientation_runs:
            components = band_components.get(band)
            if components is None:
                band_rect = box(minx, band[0], maxx, band[1]) if horizontal else box(band[0], miny, band[1], maxy)
                components = _polygon_parts(band_rect.difference(union))
                band_components[band] = components
            for component in components:
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
                touching = tuple(sorted({index for s in strips if s.polygon.buffer(NOISE_PT).intersects(rect) for index in s.native_path_indices()}))
                same_band = [
                    run for source_band, runs in band_runs.items()
                    if _close(source_band[0], band[0], 0.02) and _close(source_band[1], band[1], 0.02)
                    for run in runs
                ]
                collinear = any(_close(r[2], a) for r in same_band) and any(_close(r[1], b) for r in same_band)
                left_paths, right_paths, _unique_ends = _unique_collinear_run_end_paths(
                    same_band, a, b,
                )
                if not _unique_ends:
                    # Unsided touching inventory is adjacent-path evidence only.
                    # It is not left/right host ownership.
                    left_paths, right_paths = touching, ()
                found[key] = _Gap(horizontal, band, a, b, left_paths, right_paths, collinear)
    return list(found.values())


def _swing_source_rows(drawings, *, unlabelled_source_ink=False):
    """Keep legacy wall layers; optionally admit source-black anonymous strokes.

    This selects door-symbol evidence, not wall barriers or white frame boxes.
    Existing arc/leaf geometry, ambiguity and wall-gap checks still apply.
    """
    owned = dict(_wall_rows(drawings))
    if unlabelled_source_ink:
        for index, row in enumerate(drawings):
            if index in owned or not isinstance(row, Mapping):
                continue
            opacity = row.get("stroke_opacity", 1.0)
            if (
                row.get("fill") is None and _is_black(row.get("color"))
                and type(opacity) in (int, float) and math.isfinite(opacity)
                and opacity >= 0.995
            ):
                owned[index] = row
    return tuple(sorted(owned.items()))


def _swing_arcs(drawings: Sequence[Mapping[str, Any]], *, unlabelled_source_ink: bool = False) -> tuple[list[dict], int]:
    source_rows = _swing_source_rows(drawings, unlabelled_source_ink=unlabelled_source_ink)
    arcs: list[dict] = []
    rejected = 0
    leaves: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    for index, row in source_rows:
        if row.get("fill") is not None:
            continue
        items = list(row.get("items", ()))
        if len(items) == 1 and items[0][0] == "l":
            leaves.append((index, _xy(items[0][1]), _xy(items[0][2])))
    for index, row in source_rows:
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
        arcs.append({
            "arc": index,
            "leaf": leaf_index,
            "centre": centre,
            "open_tip": open_tip,
            "closed_tip": closed_tip,
            "radius": radius,
        })
    return arcs, rejected


def _gaps_containing_swing(arc: Mapping[str, Any], gaps: Sequence[_Gap]) -> list[int]:
    """Run-gap indices whose band contains this closed leaf. Empty when the swing is off the wall."""
    centre, tip = arc["centre"], arc["closed_tip"]
    candidates: list[int] = []
    for gap_index, gap in enumerate(gaps):
        thickness = gap.band[1] - gap.band[0]
        if gap.horizontal:
            on_line = _close(centre[1], tip[1], NOISE_PT) and gap.band[0] - thickness <= centre[1] <= gap.band[1] + thickness
            seg = sorted((centre[0], tip[0]))
        else:
            on_line = _close(centre[0], tip[0], NOISE_PT) and gap.band[0] - thickness <= centre[0] <= gap.band[1] + thickness
            seg = sorted((centre[1], tip[1]))
        if arc.get("source_segmented_polyline"):
            # A visible door swing cannot turn a 52pt doorway into
            # a 1200pt fabricated wall or arbitrary closing chord.
            # BOTH original painted wall ends must bound the chord
            # at the real source door leaf's CLOSED position.
            if not (
                _close(seg[0], gap.lo, 0.18)
                and _close(seg[1], gap.hi, 0.18)
            ):
                continue
        if on_line and gap.lo - NOISE_PT <= seg[0] and seg[1] <= gap.hi + NOISE_PT:
            candidates.append(gap_index)
    opening = [
        index for index in candidates
        if 10.0 <= (gaps[index].hi - gaps[index].lo) <= 140.0
        and (gaps[index].band[1] - gaps[index].band[0]) >= _STROKE_PAIR_THICK_MIN
    ]
    return opening if opening else []


def _place_swings(arcs: Sequence[dict], gaps: Sequence[_Gap]) -> tuple[dict[int, dict], int, int]:
    """Map gap index -> swing; count swings with no gap and swings with several."""
    placed: dict[int, list[dict]] = {}
    unplaced = 0
    ambiguous = 0
    for arc in arcs:
        candidates = _gaps_containing_swing(arc, gaps)
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


def _lining_face_wall_strips(
    drawings: Sequence[Mapping[str, Any]],
    gaps: Sequence[_Gap],
    *,
    all_ink: bool = False,
) -> tuple[list[_Strip], list[_Gap]]:
    """A spanning stroke on a lining-thin band is that wall's finished face, not a doorway.

    CAD often paints only lining caps at the ends of a cavity wall and draws the long inner
    face as an unfilled stroke. The interval between those caps is the wall. Treating the
    stroke as a doorway chord would hide the wall from hashed length matching.
    Framed openings on the same page are left as gaps so they can still close as doorways.
    """
    found: list[_Strip] = []
    consumed: list[_Gap] = []
    for gap in gaps:
        if (gap.band[1] - gap.band[0]) >= _STROKE_PAIR_THICK_MIN:
            continue
        if _frame_pair_closed(drawings, gap) is not None:
            continue
        native = _stroke_closed(drawings, gap, all_ink=all_ink)
        if native is None:
            continue
        x0, y0, x1, y1 = (
            (gap.lo, gap.band[0], gap.hi, gap.band[1]) if gap.horizontal
            else (gap.band[0], gap.lo, gap.band[1], gap.hi)
        )
        found.append(_Strip(
            native[0], x0, y0, x1, y1, box(x0, y0, x1, y1),
            forced="h" if gap.horizontal else "v",
            path_indices=native,
        ))
        consumed.append(gap)
    return found, consumed


def _stroke_closed(
    drawings: Sequence[Mapping[str, Any]], gap: _Gap, *, all_ink: bool = False,
) -> Optional[tuple[int, ...]]:
    """Native path index of one unfilled wall-layer stroke parallel to the gap and spanning it end to end.

    The stroke may sit on a face line or on the wall's own lining line just outside the band (never
    farther than one wall thickness): CAD exports draw glazing and lining on either.
    Face identity (0.35 pt) applies only to opening-sized interruptions.
    """
    thickness = gap.band[1] - gap.band[0]
    span = gap.hi - gap.lo
    end_tol = _STROKE_PAIR_FACE_PT if 10.0 <= span <= 140.0 else NOISE_PT
    for index, row in _source_rows(drawings, all_ink=all_ink):
        if row.get("fill") is not None:
            continue
        if not _visible_source_stroke_paint(row):
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
            if near_band and _close(lo, gap.lo, end_tol) and _close(hi, gap.hi, end_tol):
                return (index,)
    return None


def _jamb_cap_closed(
    drawings: Sequence[Mapping[str, Any] | None], gap: _Gap, *, all_ink: bool = False,
    wall_depth: Optional[tuple[float, float]] = None,
) -> Optional[tuple[int, ...]]:
    """Unique perpendicular caps at both opening-sized gap ends spanning the wall band.

    Competing caps abstain. Hall-length interruptions are not closed this way.
    Representation noise / face identity only; never the 2.5 pt production snap.

    Inset CAD jambs (door returns within one wall thickness of the run end) are
    accepted when they still cover the host band. Continuous jamb walls that
    continue past the host are allowed up to ``_WALL_END_SUPPORT_SPAN``.
    Colinear split jamb strokes at one station may union to cover the band.

    ``wall_depth`` (default None: the reading above) is the strict reading: a cap
    stroke must be wall ink and must end within this depth across the wall
    (``_STROKE_PAIR_CLUSTER_PT``), so a line running past the wall is no wall end.
    """
    thickness = gap.band[1] - gap.band[0]
    span = gap.hi - gap.lo
    if thickness <= NOISE_PT or not (10.0 <= span <= 140.0):
        return None
    station_tol = max(_STROKE_PAIR_FACE_PT, thickness)
    max_cap_extent = max(_WALL_END_SUPPORT_SPAN, thickness + 2.0 * _STROKE_PAIR_FACE_PT)

    def caps(station: float) -> Optional[tuple[float, set[tuple[int, int]]]]:
        # ((native path, primitive), along_lo, along_hi, perp_station)
        pieces: list[tuple[tuple[int, int], float, float, float]] = []
        for index, row in _source_rows(drawings, all_ink=all_ink):
            if row.get("fill") is not None or not _visible_source_stroke_paint(row):
                continue
            if wall_depth is not None and _source_wall_ink_role(row) != _ROLE_WALL_SUPPORT:
                continue
            for item_index, item in enumerate(row.get("items", ())):
                if item[0] != "l":
                    continue
                (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
                if gap.horizontal:
                    if not _close(ax, bx, _STROKE_PAIR_FACE_PT):
                        continue
                    perp = (ax + bx) / 2.0
                    if abs(perp - station) > station_tol:
                        continue
                    lo, hi = sorted((ay, by))
                else:
                    if not _close(ay, by, _STROKE_PAIR_FACE_PT):
                        continue
                    perp = (ay + by) / 2.0
                    if abs(perp - station) > station_tol:
                        continue
                    lo, hi = sorted((ax, bx))
                if wall_depth is None:
                    if (hi - lo) > max_cap_extent:
                        continue
                elif lo < wall_depth[0] - _STROKE_PAIR_CLUSTER_PT or hi > wall_depth[1] + _STROKE_PAIR_CLUSTER_PT:
                    continue
                # Keep pieces that overlap the host band; union may finish coverage.
                if hi < gap.band[0] - _STROKE_PAIR_FACE_PT or lo > gap.band[1] + _STROKE_PAIR_FACE_PT:
                    continue
                pieces.append(((index, item_index), lo, hi, perp))
        if not pieces:
            return None
        # Inset jambs and face-end returns can both sit inside station_tol.
        # Cluster by perpendicular station first so a through-jamb is not
        # merged with unrelated face returns at the run end.
        pieces.sort(key=lambda item: (item[3], item[1], item[2], item[0]))
        station_groups: list[list[tuple[tuple[int, int], float, float]]] = []
        group_perp: list[float] = []
        for index, lo, hi, perp in pieces:
            if group_perp and abs(perp - group_perp[-1]) <= _STROKE_PAIR_CLUSTER_PT:
                station_groups[-1].append((index, lo, hi))
            else:
                group_perp.append(perp)
                station_groups.append([(index, lo, hi)])

        # CAD often splits one jamb into two colinear strokes with a small
        # track/hardware notch inside the host band. Merge within one station
        # cluster so the union can still cover the wall thickness.
        merge_tol = _STROKE_PAIR_CLUSTER_PT * 2.0
        covering: list[tuple[float, set[tuple[int, int]]]] = []
        for group_index, group in enumerate(station_groups):
            group = sorted(group, key=lambda item: (item[1], item[2], item[0]))
            components: list[tuple[float, float, set[tuple[int, int]]]] = []
            for index, lo, hi in group:
                if components and lo <= components[-1][1] + merge_tol:
                    prev_lo, prev_hi, prev_used = components[-1]
                    components[-1] = (prev_lo, max(prev_hi, hi), prev_used | {index})
                else:
                    components.append((lo, hi, {index}))
            for lo, hi, used in components:
                if (
                    lo - _STROKE_PAIR_FACE_PT <= gap.band[0]
                    and hi + _STROKE_PAIR_FACE_PT >= gap.band[1]
                    and 1 <= len({path_index for path_index, _ in used}) <= 2
                ):
                    covering.append((group_perp[group_index], used))
        if not covering:
            return None
        # Prefer the covering cluster nearest the geometric gap end. A second
        # through-jamb only a face away (common CAD double-line) abstains when
        # equally near; an inset return farther away loses to the end station.
        covering.sort(key=lambda item: (abs(item[0] - station), sorted(item[1])))
        best_perp, best_used = covering[0]
        if len(covering) > 1:
            second_perp, _second_used = covering[1]
            if abs(abs(second_perp - station) - abs(best_perp - station)) <= _STROKE_PAIR_FACE_PT:
                return None
        return best_perp, best_used

    low, high = caps(gap.lo), caps(gap.hi)
    if low is None or high is None:
        return None
    low_station, low_used = low
    high_station, high_used = high
    # Distinct physical jamb primitives, even when a CAD exporter batches
    # both into one native path. Never reuse a primitive or station.
    if high_station - low_station <= _STROKE_PAIR_CLUSTER_PT or low_used & high_used:
        return None
    return tuple(sorted({path_index for path_index, _ in low_used | high_used}))


def _swing_leaf_span(arc: Mapping[str, Any]) -> Optional[tuple[bool, float, float, float]]:
    """(horizontal, lo, hi, perp) of a closed door leaf, else None when it is not axis-aligned."""
    centre, tip = arc["centre"], arc["closed_tip"]
    dx, dy = abs(centre[0] - tip[0]), abs(centre[1] - tip[1])
    horizontal = dy <= NOISE_PT and dx > 1.0
    vertical = dx <= NOISE_PT and dy > 1.0
    if horizontal == vertical:
        return None
    if horizontal:
        lo, hi = sorted((centre[0], tip[0]))
        perp = (centre[1] + tip[1]) / 2.0
    else:
        lo, hi = sorted((centre[1], tip[1]))
        perp = (centre[0] + tip[0]) / 2.0
    if hi - lo < 10.0 or hi - lo > 140.0:
        return None
    return horizontal, lo, hi, perp


def _gap_from_swing_leaf(arc: Mapping[str, Any], union: Any, known: Sequence[_Gap]) -> Optional[_Gap]:
    """Doorway chord of an unplaced swing whose closed leaf sits between wall ink at both jambs.

    CAD often draws the host wall as a notched fill that is not a rectangular strip, so run-gap
    matching never sees the interruption. The swing still names the opening: the chord is the
    closed leaf only, never a hall-length gap. Wall ink overlapping the leaf abstains (too-wide
    or off-wall). Topology only; not a hosted opening or wall length.
    """
    span = _swing_leaf_span(arc)
    if span is None:
        return None
    horizontal, lo, hi, perp = span
    along_depth = _DARK_FILL_THICK_MAX
    perp_window = _STROKE_PAIR_THICK_MAX
    bands: list[tuple[float, float]] = []
    inner_faces: list[float] = []
    for station, outward in ((lo, -1.0), (hi, 1.0)):
        if horizontal:
            a, b = (station - along_depth, station) if outward < 0 else (station, station + along_depth)
            slab = box(a, perp - perp_window, b, perp + perp_window)
        else:
            a, b = (station - along_depth, station) if outward < 0 else (station, station + along_depth)
            slab = box(perp - perp_window, a, perp + perp_window, b)
        inter = union.intersection(slab)
        if inter.is_empty or inter.area <= NOISE_PT:
            return None
        leaf_pt = Point(station, perp) if horizontal else Point(perp, station)
        parts = [
            part for part in _polygon_parts(inter)
            if part.area > NOISE_PT
        ]
        if not parts:
            return None
        parts.sort(key=lambda part: part.distance(leaf_pt))
        nearest = parts[0]
        bx0, by0, bx1, by1 = nearest.bounds
        band = (by0, by1) if horizontal else (bx0, bx1)
        if band[1] - band[0] <= NOISE_PT:
            return None
        bands.append(band)
        along0, along1 = (bx0, bx1) if horizontal else (by0, by1)
        inner_faces.append(along1 if outward < 0 else along0)
    overlap_lo, overlap_hi = max(bands[0][0], bands[1][0]), min(bands[0][1], bands[1][1])
    if overlap_hi - overlap_lo > NOISE_PT:
        band = (overlap_lo, overlap_hi)
    elif min(bands[0][1], bands[1][1]) + _STROKE_PAIR_FACE_PT >= max(bands[0][0], bands[1][0]):
        # Corner door: one jamb is the continuing wall, the other is the
        # abutting return. They touch; their union is the host band.
        band = (min(bands[0][0], bands[1][0]), max(bands[0][1], bands[1][1]))
    else:
        return None
    slack = band[1] - band[0]
    if not (band[0] - slack <= perp <= band[1] + slack):
        return None
    chord_lo = min(lo, inner_faces[0])
    chord_hi = max(hi, inner_faces[1])
    if chord_hi - chord_lo < 10.0 or chord_hi - chord_lo > 140.0:
        return None
    lo, hi = chord_lo, chord_hi
    door = box(lo, band[0], hi, band[1]) if horizontal else box(band[0], lo, band[1], hi)
    door_area = door.area
    if door_area <= NOISE_PT:
        return None
    if door.intersection(union).area > max(NOISE_PT * 2.0 * slack, 0.25 * door_area):
        return None
    mid = (lo + hi) / 2.0
    probes = (
        (Point(mid, band[0] - 2 * NOISE_PT), Point(mid, band[1] + 2 * NOISE_PT)) if horizontal
        else (Point(band[0] - 2 * NOISE_PT, mid), Point(band[1] + 2 * NOISE_PT, mid))
    )
    if any(union.contains(probe) for probe in probes):
        return None
    if any(
        gap.horizontal == horizontal
        and _close(gap.band[0], band[0], 0.5) and _close(gap.band[1], band[1], 0.5)
        and _close(gap.lo, lo, 0.5) and _close(gap.hi, hi, 0.5)
        for gap in known
    ):
        return None
    return _Gap(horizontal, band, lo, hi, (), (), True)


def _frame_pair_closed(
    drawings: Sequence[Mapping[str, Any]], gap: _Gap,
) -> Optional[tuple[int, ...]]:
    """Unique white wall-layer frame box at each end of an opening-sized interruption.

    Cavity sliders and framed doors are drawn that way: the frames name the opening even
    when only one leaf sits in the pocket. Hall-length interruptions are not closed.
    """
    span = gap.hi - gap.lo
    if not (10.0 <= span <= 140.0):
        return None
    thickness = gap.band[1] - gap.band[0]
    end_tol = _STROKE_PAIR_FACE_PT
    low: list[int] = []
    high: list[int] = []
    for x0, y0, x1, y1, index in _white_frame_boxes(drawings):
        lo, hi = (x0, x1) if gap.horizontal else (y0, y1)
        p0, p1 = (y0, y1) if gap.horizontal else (x0, x1)
        if p1 < gap.band[0] - thickness or p0 > gap.band[1] + thickness:
            continue
        if _close(hi, gap.lo, end_tol) or _close(lo, gap.lo, end_tol):
            low.append(index)
        if _close(lo, gap.hi, end_tol) or _close(hi, gap.hi, end_tol):
            high.append(index)
    low, high = list(dict.fromkeys(low)), list(dict.fromkeys(high))
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


def _jamb_pair_gaps(
    drawings: Sequence[Mapping[str, Any]], union: Any, known: Sequence[_Gap],
) -> list[tuple[_Gap, tuple[int, ...]]]:
    """Opening-sized interruptions between adjacent white jamb boxes on one wall face.

    CAD draws cavity-slider and window jambs as mixed-width boxes; a long white bar in
    the opening is glazing or a leaf, not a jamb. Run-gaps never see a notched host, so
    the interruption is the interval between two adjacent short jambs that share a face
    line, with wall ink at both outward ends and no black ink between. The host band is
    the overlap of those end inks, or their union when the bands touch. A leaf or lining
    sliver in the opening is not wall (same 25% cap as a swing-leaf chord). Not FIRM.
    """
    boxes = _white_frame_boxes(drawings)
    found: list[tuple[_Gap, tuple[int, ...]]] = []
    seen: set[tuple[bool, float, float]] = set()
    for horizontal in (True, False):
        jambs: list[tuple[float, float, float, float, int]] = []
        for x0, y0, x1, y1, index in boxes:
            lo, hi = (x0, x1) if horizontal else (y0, y1)
            p0, p1 = (y0, y1) if horizontal else (x0, x1)
            if hi - lo >= 10.0 or p1 - p0 <= NOISE_PT:
                continue
            jambs.append((lo, hi, p0, p1, index))
        faces: dict[int, list[tuple[float, float, float, float, int]]] = {}
        for lo, hi, p0, p1, index in jambs:
            for face in (p0, p1):
                faces.setdefault(round(face / 0.02), []).append((lo, hi, p0, p1, index))
        for members in faces.values():
            unique = list(dict.fromkeys(members))
            unique.sort(key=lambda item: (item[0], item[1]))
            for (lo1, hi1, a0, a1, i1), (lo2, hi2, b0, b1, i2) in zip(unique, unique[1:]):
                if i1 == i2 or lo2 - hi1 <= NOISE_PT:
                    continue
                span = lo2 - hi1
                if not (_STROKE_PAIR_THICK_MIN <= span <= 140.0):
                    continue
                bands: list[tuple[float, float]] = []
                for edge, direction, p0, p1 in ((lo1, -1.0, a0, a1), (hi2, 1.0, b0, b1)):
                    a, b = (edge - _STROKE_PAIR_THICK_MAX, edge) if direction < 0 else (edge, edge + _STROKE_PAIR_THICK_MAX)
                    slab = box(a, p0, b, p1) if horizontal else box(p0, a, p1, b)
                    inter = union.intersection(slab)
                    if inter.is_empty or inter.area <= NOISE_PT:
                        bands = []
                        break
                    leaf_pt = Point(edge, (p0 + p1) / 2.0) if horizontal else Point((p0 + p1) / 2.0, edge)
                    parts = [part for part in _polygon_parts(inter) if part.area > NOISE_PT]
                    if not parts:
                        bands = []
                        break
                    parts.sort(key=lambda part: part.distance(leaf_pt))
                    bx0, by0, bx1, by1 = parts[0].bounds
                    bands.append((by0, by1) if horizontal else (bx0, bx1))
                if len(bands) != 2:
                    continue
                overlap_lo = max(bands[0][0], bands[1][0])
                overlap_hi = min(bands[0][1], bands[1][1])
                if overlap_hi - overlap_lo >= _STROKE_PAIR_THICK_MIN:
                    band = (overlap_lo, overlap_hi)
                elif min(bands[0][1], bands[1][1]) + _STROKE_PAIR_FACE_PT >= max(bands[0][0], bands[1][0]):
                    band = (min(bands[0][0], bands[1][0]), max(bands[0][1], bands[1][1]))
                else:
                    continue
                if band[1] - band[0] < _STROKE_PAIR_THICK_MIN:
                    continue
                key = (horizontal, round(lo1, 2), round(hi2, 2))
                if key in seen:
                    continue
                gap = _Gap(horizontal, band, lo1, hi2, (), (), True)
                rect = gap.rect()
                door_area = rect.area
                if door_area <= NOISE_PT:
                    continue
                if rect.intersection(union).area > max(
                    NOISE_PT * 2.0 * (band[1] - band[0]), 0.25 * door_area,
                ):
                    continue
                mid = (lo1 + hi2) / 2.0
                probes = (
                    (Point(mid, band[0] - 2 * NOISE_PT), Point(mid, band[1] + 2 * NOISE_PT)) if horizontal
                    else (Point(band[0] - 2 * NOISE_PT, mid), Point(band[1] + 2 * NOISE_PT, mid))
                )
                if any(union.contains(probe) for probe in probes):
                    continue
                if any(
                    g.horizontal == horizontal
                    and _close(g.band[0], band[0], 0.5) and _close(g.band[1], band[1], 0.5)
                    and _close(g.lo, lo1, 0.5) and _close(g.hi, hi2, 0.5)
                    for g in (*known, *(item[0] for item in found))
                ):
                    continue
                seen.add(key)
                found.append((gap, tuple(sorted({i1, i2}))))
            for lo, hi, p0, p1, index in unique:
                for station, outward in ((lo, -1.0), (hi, 1.0)):
                    a, b = (
                        (station - 10.0, station) if outward < 0 else (station, station + 10.0)
                    )
                    slab = box(a, p0, b, p1) if horizontal else box(p0, a, p1, b)
                    inter = union.intersection(slab)
                    if inter.is_empty or inter.area <= NOISE_PT:
                        continue
                    leaf_pt = Point(station, (p0 + p1) / 2.0) if horizontal else Point((p0 + p1) / 2.0, station)
                    parts = [part for part in _polygon_parts(inter) if part.area > NOISE_PT]
                    if not parts:
                        continue
                    parts.sort(key=lambda part: part.distance(leaf_pt))
                    bx0, by0, bx1, by1 = parts[0].bounds
                    along0, along1 = (bx0, bx1) if horizontal else (by0, by1)
                    inner = along1 if outward < 0 else along0
                    span = abs(inner - station)
                    if not (_STROKE_PAIR_FACE_PT <= span < 10.0):
                        continue
                    wall_band = (by0, by1) if horizontal else (bx0, bx1)
                    overlap_lo = max(p0, wall_band[0])
                    overlap_hi = min(p1, wall_band[1])
                    if overlap_hi - overlap_lo >= _STROKE_PAIR_THICK_MIN:
                        band = (overlap_lo, overlap_hi)
                    elif min(p1, wall_band[1]) + _STROKE_PAIR_FACE_PT >= max(p0, wall_band[0]):
                        band = (min(p0, wall_band[0]), max(p1, wall_band[1]))
                    else:
                        continue
                    if band[1] - band[0] < _STROKE_PAIR_THICK_MIN:
                        continue
                    lo_g, hi_g = (inner, station) if inner < station else (station, inner)
                    key = (horizontal, round(lo_g, 2), round(hi_g, 2))
                    if key in seen:
                        continue
                    gap = _Gap(horizontal, band, lo_g, hi_g, (), (), True)
                    rect = gap.rect()
                    door_area = rect.area
                    if door_area <= NOISE_PT:
                        continue
                    if rect.intersection(union).area > max(
                        NOISE_PT * 2.0 * (band[1] - band[0]), 0.25 * door_area,
                    ):
                        continue
                    mid = (lo_g + hi_g) / 2.0
                    probes = (
                        (Point(mid, band[0] - 2 * NOISE_PT), Point(mid, band[1] + 2 * NOISE_PT)) if horizontal
                        else (Point(band[0] - 2 * NOISE_PT, mid), Point(band[1] + 2 * NOISE_PT, mid))
                    )
                    if any(union.contains(probe) for probe in probes):
                        continue
                    if any(
                        g.horizontal == horizontal
                        and _close(g.band[0], band[0], 0.5) and _close(g.band[1], band[1], 0.5)
                        and _close(g.lo, lo_g, 0.5) and _close(g.hi, hi_g, 0.5)
                        for g in (*known, *(item[0] for item in found))
                    ):
                        continue
                    seen.add(key)
                    found.append((gap, (index,)))
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


def _unresolved_collinear_gap_breaches_outer_ring(part: Polygon, gap: _Gap) -> bool:
    """Only veto THIS room when both source wall-gap ends meet its exterior.

    A far-away collinear wall or an incomplete internal partition can share a
    band with this ring. Mere intersection, or one endpoint on the exterior,
    is not an opening in this enclosing perimeter. Topology-only; not a
    physical wall, opening, area or commercial room.
    """
    if not gap.collinear:
        return False
    if gap.horizontal:
        first = LineString(((gap.lo, gap.band[0]), (gap.lo, gap.band[1])))
        last = LineString(((gap.hi, gap.band[0]), (gap.hi, gap.band[1])))
    else:
        first = LineString(((gap.band[0], gap.lo), (gap.band[1], gap.lo)))
        last = LineString(((gap.band[0], gap.hi), (gap.band[1], gap.hi)))
    outer = part.exterior
    return outer.distance(first) <= NOISE_PT and outer.distance(last) <= NOISE_PT



def _source_unresolved_gap_witnesses(
    unresolved: Sequence[_Gap], *, limit: int = 64,
) -> tuple[tuple[Mapping[str, Any], ...], int]:
    """Report exact existing wall-run endpoints; never invent an opening or wall.

    Source native path indices are original page indices, including when the
    drawing list was bounded by the footprint diagnostic with inert placeholders.
    Left/right owners are recorded only when each collinear run end is unique.
    An unsided touching inventory is adjacent-path evidence, not a host.
    Sampling is presentation-only: all such gaps stay unclosed, regardless of
    whether their receipt makes the bounded diagnostic list.
    """
    unique: dict[tuple[Any, ...], Mapping[str, Any]] = {}
    for gap in unresolved:
        if not gap.collinear or not (gap.left_path_indices or gap.right_path_indices):
            continue
        if gap.hi <= gap.lo:
            continue
        geometry = (
            bool(gap.horizontal),
            round(float(gap.band[0]), 4),
            round(float(gap.band[1]), 4),
            round(float(gap.lo), 4),
            round(float(gap.hi), 4),
        )
        left = tuple(sorted(set(int(i) for i in gap.left_path_indices)))
        right = tuple(sorted(set(int(i) for i in gap.right_path_indices)))
        partitioned = bool(left) and bool(right)
        adjacent_paths = tuple(sorted(set(left) | set(right)))
        key = (*geometry, adjacent_paths)
        if key in unique:
            continue
        unique[key] = {
            "horizontal": geometry[0],
            "band_pdf_pts": (geometry[1], geometry[2]),
            "gap_interval_pdf_pts": (geometry[3], geometry[4]),
            "adjacent_wall_native_path_indices": adjacent_paths,
            "left_wall_native_path_indices": left if partitioned else (),
            "right_wall_native_path_indices": right if partitioned else (),
            "source_path_side_partition_proven": partitioned,
            "topology_only": True,
            "physical_wall_authenticated": False,
            "opening_authenticated": False,
            "can_issue_area": False,
            "reason_code": "unresolved_source_collinear_wall_gap",
        }
    ordered = tuple(unique[key] for key in sorted(unique))
    return ordered[:limit], len(ordered)


def _without_door_owned_paths(
    drawings: Sequence[Any], witnesses: Sequence[Mapping[str, Any]],
) -> Sequence[Any]:
    """The rows with every native path a segmented swing witness OWNS made inert: same indices, same length.

    A witness (a quarter-turn chain of black single-line strokes and its one radial leaf) is door symbol ink,
    not wall ink. The leaf is collinear with the hinge-side jamb line, so the line-based wall-strip collectors
    (merged collinear dark face, stroke pair, wall-end closure, heavy stroke) read it as a thin wall face that
    reaches into the doorway and shortens the raw wall gap the chord proposer needs (``4285e133a``). Only the
    collectors' view changes: the door detection, the proposer and every other consumer keep reading the full
    rows. With no witness the input itself is returned, so a page without a segmented swing is untouched.
    """
    owned = {int(index) for witness in witnesses for index in witness["native_source_path_indices"]}
    if not owned:
        return drawings
    inert: Mapping[str, Any] = {"layer": "", "fill": None, "color": None, "items": ()}
    return [inert if index in owned else row for index, row in enumerate(drawings)]


# The source doorway-chord proposer's own representation tolerances, reused to read the door's own jamb.
_JAMB_CHORD_AXIS_PT = 0.12
_JAMB_FACE_PT = 0.18
_JAMB_FACE_MIN_RUN_PT = 1.0
# A wall thicker than the 8 pt paper-space window (an enlarged view) must be stated by a cap spanning it, and is at
# most one part in this many of the door's own width. A proportion guard against furniture, not a fitted value.
_JAMB_THICK_WALL_DOOR_RATIO = 3.0


def _jamb_return_extent(
    end: float, direction: float, chord: float, width: float,
    faces: Sequence[tuple[float, float, float, int]], crosses: Sequence[tuple[float, float, float, int]],
) -> Optional[tuple[float, tuple[float, float], tuple[int, ...]]]:
    """(far end, wall band, source path ids) of the wall that starts at one chord end, or None when it is not unique."""

    def starts(lo: float, hi: float) -> bool:  # begins at the chord end and runs away from the door
        near, far = (hi, lo) if direction < 0 else (lo, hi)
        return abs(near - end) <= _JAMB_FACE_PT and direction * (far - end) > _JAMB_FACE_MIN_RUN_PT

    frame = [direction * ((lo if direction < 0 else hi) - end) for perp, lo, hi, _index in faces
             if abs(perp - chord) <= _JAMB_FACE_PT and starts(lo, hi)]  # how far the first chord-face strokes run
    if not frame:
        return None

    def capped(low: float, high: float) -> bool:  # one cross stroke from face to face, within the door frame
        return any(abs(lo - low) <= _JAMB_FACE_PT and abs(hi - high) <= _JAMB_FACE_PT
                   and -_JAMB_FACE_PT <= direction * (pos - end) <= max(frame) + _JAMB_FACE_PT
                   for pos, lo, hi, _index in crosses)

    seconds: list[float] = []
    for perp in sorted(p for p, lo, hi, _index in faces if abs(p - chord) >= _STROKE_PAIR_THICK_MIN and starts(lo, hi)):
        thickness = abs(perp - chord)
        if thickness > _STROKE_PAIR_THICK_MAX and not (
            thickness <= width / _JAMB_THICK_WALL_DOOR_RATIO and capped(min(perp, chord), max(perp, chord))
        ):
            continue
        if not seconds or perp - seconds[-1] > _JAMB_FACE_PT:
            seconds.append(perp)
    candidates = []
    for perp in seconds:
        low, high = min(perp, chord), max(perp, chord)
        jamb = [index for pos, lo, hi, index in crosses
                if abs(pos - end) <= _JAMB_FACE_PT and lo >= low - _JAMB_FACE_PT and hi <= high + _JAMB_FACE_PT
                and (abs(lo - low) <= _JAMB_FACE_PT or abs(hi - high) <= _JAMB_FACE_PT)]
        if jamb:
            candidates.append((perp, jamb))
    if len(candidates) != 1:
        return None
    other, jamb = candidates[0]

    def reach(face: float) -> tuple[float, list[tuple[float, int]]]:
        """How far this face runs from the chord end without a break, and the (position, path id) lines read."""
        spans = sorted(((lo, hi, index, perp) for perp, lo, hi, index in faces if abs(perp - face) <= _JAMB_FACE_PT),
                       key=lambda span: (-span[1], span[0]) if direction < 0 else (span[0], -span[1]))
        edge, used = end, []
        for lo, hi, index, perp in spans:
            near, far = (hi, lo) if direction < 0 else (lo, hi)
            if direction * (near - edge) <= _JAMB_FACE_PT and direction * (far - edge) > 0:
                edge = far
                used.append((perp, index))
        return edge, used

    chord_far, chord_lines = reach(chord)
    other_far, other_lines = reach(other)
    far_end = end + direction * min(direction * (chord_far - end), direction * (other_far - end))
    positions = [perp for perp, _index in chord_lines + other_lines]  # the band is where the drawn faces are
    ids = {index for _perp, index in chord_lines + other_lines} | set(jamb)
    return far_end, (min(positions), max(positions)), tuple(sorted(ids))


def _collect_door_jamb_return_strips(
    drawings: Sequence[Any], witnesses: Sequence[Mapping[str, Any]], strips: Sequence[_Strip],
) -> list[_Strip]:
    """Short wall pieces bound to a segmented source swing's own jamb (opt-in ``door_jamb_returns``).

    The long-wall collectors need 40 pt (merged faces) or exactly one partner face line (stroke pairs), so the short wall
    left between a door and the next wall is often never collected, and the doorway then has no wall gap to close. The
    door says where that wall starts. At each end of a witness's closed chord one strip is made only when all hold:

    * the chord is axis-aligned;
    * black visible face lines start at that end and run away from the door: one on the chord line, and exactly one other
      1.2 to 8 pt from it that has a black cross stroke at the end between the two (zero or several candidates abstain).
      A thicker wall, as on an enlarged view, counts only when one cross stroke spans the two faces within the frame and
      the wall is at most a third of the door's width;
    * both faces run on without a break; the piece ends where the shorter one stops;
    * a strip already collected in the other direction touches that far end, within the face-cluster tolerance;
    * the piece is shorter than the merged-face minimum (longer walls stay with the existing collectors).

    Every witness's own arc and leaf are door symbol ink and are never read. Topology-only candidate ink: it
    authenticates no wall, closes no doorway by itself and issues no quantity.
    """
    if not witnesses:
        return []
    owned = {int(index) for witness in witnesses for index in witness.get("native_source_path_indices", ())}
    lines: list[tuple[int, tuple[float, float], tuple[float, float]]] = []
    for index, row in enumerate(drawings):
        if index in owned or not isinstance(row, Mapping) or row.get("fill") is not None:
            continue
        if not _is_black(row.get("color")) or not _visible_source_stroke_paint(row):
            continue
        for item in row.get("items") or ():
            if item and item[0] == "l":
                a, b = _xy(item[1]), _xy(item[2])
                if all(math.isfinite(v) for v in (*a, *b)):
                    lines.append((index, a, b))
    found: list[_Strip] = []
    seen: set[tuple[bool, float, float, float, float]] = set()
    for witness in witnesses:
        hinge, tip = witness["source_hinge_point_pdf_pts"], witness["source_closed_leaf_tip_pdf_pts"]
        dx, dy = abs(hinge[0] - tip[0]), abs(hinge[1] - tip[1])
        horizontal = dy <= _JAMB_CHORD_AXIS_PT and dx > _JAMB_FACE_MIN_RUN_PT
        if horizontal == (dx <= _JAMB_CHORD_AXIS_PT and dy > _JAMB_FACE_MIN_RUN_PT):
            continue
        axis, across = (0, 1) if horizontal else (1, 0)
        chord = (hinge[across] + tip[across]) / 2.0
        faces: list[tuple[float, float, float, int]] = []    # (perpendicular position, along lo, along hi, path id)
        crosses: list[tuple[float, float, float, int]] = []  # (along position, perpendicular lo, perpendicular hi, path id)
        for index, a, b in lines:
            if abs(a[across] - b[across]) < _JAMB_CHORD_AXIS_PT and abs(a[axis] - b[axis]) > NOISE_PT:
                faces.append(((a[across] + b[across]) / 2.0, min(a[axis], b[axis]), max(a[axis], b[axis]), index))
            elif abs(a[axis] - b[axis]) < _JAMB_CHORD_AXIS_PT and abs(a[across] - b[across]) > NOISE_PT:
                crosses.append(((a[axis] + b[axis]) / 2.0, min(a[across], b[across]), max(a[across], b[across]), index))
        low_end, high_end = sorted((hinge[axis], tip[axis]))
        for end, direction in ((low_end, -1.0), (high_end, 1.0)):
            extent = _jamb_return_extent(end, direction, chord, high_end - low_end, faces, crosses)
            if extent is None:
                continue
            far_end, band, ids = extent
            if not NOISE_PT < direction * (far_end - end) < _MERGED_FACE_MIN_SPAN:
                continue
            far_edge = (
                LineString([(far_end, band[0]), (far_end, band[1])]) if horizontal
                else LineString([(band[0], far_end), (band[1], far_end)])
            )
            if not any((strip.vertical if horizontal else strip.horizontal)
                       and strip.polygon.distance(far_edge) <= _STROKE_PAIR_CLUSTER_PT for strip in strips):
                continue
            lo, hi = sorted((far_end, end))
            x0, y0, x1, y1 = (lo, band[0], hi, band[1]) if horizontal else (band[0], lo, band[1], hi)
            key = (horizontal, round(x0, 2), round(y0, 2), round(x1, 2), round(y1, 2))
            if key in seen:
                continue
            seen.add(key)
            found.append(_Strip(
                ids[0], x0, y0, x1, y1, box(x0, y0, x1, y1), forced="h" if horizontal else "v", path_indices=ids,
            ))
    return found


def _wall_end_depth(gap: _Gap, gaps: Sequence[_Gap], swing_gaps: Iterable[int]) -> tuple[float, float]:
    """The wall's depth for a strict jamb cap: this band, widened to a far face line of the same doorway.

    A far line counts only where a door swing is already placed, in a parallel interruption lying inside this
    one (``_STROKE_PAIR_FACE_PT``). The depth stays at most one part in ``_JAMB_THICK_WALL_DOOR_RATIO`` of this
    interruption's width, else it is the band alone. Every such line is used; none is chosen as nearest.
    """
    low, high = gap.band
    limit = (gap.hi - gap.lo) / _JAMB_THICK_WALL_DOOR_RATIO
    for index in swing_gaps:
        far = gaps[index]
        if far.horizontal != gap.horizontal:
            continue
        if far.lo < gap.lo - _STROKE_PAIR_FACE_PT or far.hi > gap.hi + _STROKE_PAIR_FACE_PT:
            continue
        near_edge, far_edge = min(gap.band[0], far.band[0]), max(gap.band[1], far.band[1])
        if far_edge - near_edge <= limit:
            low, high = min(low, near_edge), max(high, far_edge)
    if high - low > limit:  # far lines on both sides that together are too deep (or a band already deeper)
        return gap.band
    return low, high


def build_layered_wall_doorway_room_rings(
    drawings: Sequence[Mapping[str, Any]],
    *,
    source_sha256: str,
    page_index: int,
    sliding_leaf_frame_closure: bool = False,
    dark_painted_wall_source: bool = False,
    door_jamb_returns: bool = False,
    jamb_caps_must_be_wall_ends: bool = False,
    wall_end_stroke_closures: bool = False,
    source_heavy_stroke_wall_bands: bool = False,
) -> LayeredRoomRingResult:
    """Rings enclosed by wall ink plus source-attested doorway closures. Never mutates ``drawings``.

    ``sliding_leaf_frame_closure`` (default False, its own control) additionally closes an interruption
    that carries a frame box at each end and exactly two overlapping sliding leaves between them.
    ``door_jamb_returns`` (default False, dark-painted only) is one paired change: it keeps a
    segmented swing's own strokes out of the line-based wall strips (``_without_door_owned_paths``)
    and adds the short wall pieces bound to that swing's jamb (``_collect_door_jamb_return_strips``),
    as topology-only candidate ink.
    ``jamb_caps_must_be_wall_ends`` (default False, dark-painted only) makes the jamb-cap closure
    strict: only wall ink that ends at the wall faces may cap an interruption (``_wall_end_depth``).
    ``wall_end_stroke_closures`` (default False) adds a single black stroke only when both of
    its native endpoints already meet major structural strips. The stroke is not extended.
    That flag is a PDF-point candidate heuristic, not physical wall identity.
    ``source_heavy_stroke_wall_bands`` (default False) admits one opaque 1.2–6 pt
    black axis-aligned stroke as a topology-only wall band, and also a long
    (≥80 pt) medium-width (0.45–1.2) black face. It is not a pair, not a raster
    hull, and not a billed wall.
    """
    if type(sliding_leaf_frame_closure) is not bool:
        raise ValueError("sliding_leaf_frame_closure must be an explicit boolean")
    if type(dark_painted_wall_source) is not bool:
        raise ValueError("dark_painted_wall_source must be an explicit boolean")
    if type(wall_end_stroke_closures) is not bool:
        raise ValueError("wall_end_stroke_closures must be an explicit boolean")
    if type(source_heavy_stroke_wall_bands) is not bool:
        raise ValueError("source_heavy_stroke_wall_bands must be an explicit boolean")
    if wall_end_stroke_closures and not dark_painted_wall_source:
        raise ValueError("wall_end_stroke_closures requires dark_painted_wall_source")
    if type(door_jamb_returns) is not bool:
        raise ValueError("door_jamb_returns must be an explicit boolean")
    if door_jamb_returns and not dark_painted_wall_source:
        raise ValueError("door_jamb_returns requires dark_painted_wall_source")
    if type(jamb_caps_must_be_wall_ends) is not bool:
        raise ValueError("jamb_caps_must_be_wall_ends must be an explicit boolean")
    if jamb_caps_must_be_wall_ends and not dark_painted_wall_source:
        raise ValueError("jamb_caps_must_be_wall_ends requires dark_painted_wall_source")
    if type(source_sha256) is not str or len(source_sha256) != 64 or any(c not in "0123456789abcdef" for c in source_sha256):
        raise ValueError("source_sha256 must be a 64-char lowercase hex digest")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index must be a non-negative int")
    # Keep original indexed source paths, but only allow actual black/dark
    # wall-candidate source paint to enter this opt-in topology path.
    # On Maryborough p7 the owner-green exclusion reduces 109k PDF paths
    # substantially and black/dark source ink is beneath the 20k cap.
    if dark_painted_wall_source:
        drawings, source_candidates, _green_excluded = (
            _source_wall_ink_candidate_drawings(drawings)
        )
        # The frozen limit counts native PRIMITIVES, not PDF path
        # containers; a path may own multiple line/arc/rect operations.
        # It bounds the STRUCTURAL wall hypothesis (wall-support rows and the
        # opaque fills that can hide them), as it did before the selector began
        # retaining doorway/glazing evidence strokes. Those evidence rows stay
        # in ``drawings`` with their original indices, never mint a wall strip
        # and are not counted here (see ``structural_native_primitive_count``).
        selected_native_primitives = structural_native_primitive_count(drawings)
        if selected_native_primitives > 20_000:
            return LayeredRoomRingResult(
                EvidenceResolutionStatus.ABSTAINED,
                (REASON_UNLABELLED_SOURCE_PRIMITIVE_CAP,),
                (), (), 0, 0, 0, 0, 0, 0,
            )
    strips, other_fills = _collect_strips(drawings)
    merged_face_strips: list[_Strip] = []
    segmented_witnesses: tuple[Mapping[str, Any], ...] = ()
    wall_ink = drawings
    if dark_painted_wall_source:
        from pb_source_segmented_door_swing_shadow import (
            collect_source_black_segmented_door_swings,
        )
        # Find the source door swings once, here.
        segmented_witnesses = collect_source_black_segmented_door_swings(drawings)
        # With the jamb returns on, a swing's own strokes are door symbol ink, not wall ink: the line-based
        # wall-strip collectors get rows in which its native paths are inert (same indices). One paired change:
        # alone it loses doorways whose jamb reached the wall minimum only together with the open leaf.
        if door_jamb_returns:
            wall_ink = _without_door_owned_paths(drawings, segmented_witnesses)
        # Owner: black paired-line walls, dark filled wall strips and true
        # named wall ink are the structural wall hypothesis sources.
        # Unqualified green aisle/equipment/cold-room graphics are excluded
        # before this stage, with original path indices still intact.
        merged_face_strips = _collect_merged_collinear_dark_face_strips(wall_ink)
        strips = (
            strips
            + _collect_dark_painted_source_wall_strips(drawings)
            + _collect_stroke_pair_strips(wall_ink)
            + merged_face_strips
        )
        if wall_end_stroke_closures:
            strips = strips + _collect_wall_end_closing_strips(wall_ink, strips)
    if source_heavy_stroke_wall_bands:
        strips = strips + _collect_source_heavy_stroke_strips(wall_ink)
    if door_jamb_returns:
        strips = strips + _collect_door_jamb_return_strips(drawings, segmented_witnesses, strips)
    unsupported = len(other_fills)
    if not strips:
        return LayeredRoomRingResult(EvidenceResolutionStatus.ABSTAINED, (REASON_NO_WALL_INK,), (), (), 0, 0, 0, unsupported, 0, 0)
    polygons = [s.polygon for s in strips] + [polygon for _index, polygon in other_fills]
    union = _closed_union(polygons)
    domain = union.envelope.buffer(1.0, join_style=2)
    gaps = _gaps(strips, union, domain)
    if sliding_leaf_frame_closure or dark_painted_wall_source:
        gaps = gaps + _frame_anchored_gaps(drawings, union, gaps)
    face_strips, consumed_faces = _lining_face_wall_strips(
        drawings, gaps, all_ink=dark_painted_wall_source,
    )
    if face_strips:
        strips = strips + face_strips
        polygons = [s.polygon for s in strips] + [polygon for _index, polygon in other_fills]
        union = _closed_union(polygons)
        domain = union.envelope.buffer(1.0, join_style=2)
        consumed_ids = {id(gap) for gap in consumed_faces}
        gaps = [gap for gap in gaps if id(gap) not in consumed_ids]
    arcs, _rejected_arcs = _swing_arcs(
        drawings, unlabelled_source_ink=dark_painted_wall_source,
    )
    sourced_doorway_chords: tuple[Mapping[str, Any], ...] = ()
    if dark_painted_wall_source:
        from pb_source_segmented_door_swing_shadow import (
            propose_source_owned_doorway_chords,
        )
        # ``segmented_witnesses`` were found once, above, on these same rows.
        # One shared wall-end and jamb rule for EVERY segmented source
        # swing. Never close the whole oversized original _Gap.
        sourced_doorway_chords = propose_source_owned_doorway_chords(
            drawings, segmented_witnesses, gaps,
        )
        gaps.extend(
            _Gap(
                chord["horizontal"],
                chord["wall_band_pdf_pts"],
                chord["door_interval_pdf_pts"][0],
                chord["door_interval_pdf_pts"][1],
                chord["left_source_wall_path_indices"],
                chord["right_source_wall_path_indices"],
                True,
            )
            for chord in sourced_doorway_chords
        )
        arcs.extend({
            "arc": witness["arc_native_path_indices"][0],
            "arc_source_ids": witness["arc_native_path_indices"],
            "leaf": witness["leaf_native_path_index"],
            "centre": witness["source_hinge_point_pdf_pts"],
            "closed_tip": witness["source_closed_leaf_tip_pdf_pts"],
            "radius": witness["radius_pdf_pts"],
            "source_segmented_polyline": True,
        } for witness in segmented_witnesses)
    swing_by_gap, unplaced, ambiguous = _place_swings(arcs, gaps)
    run_gaps = list(gaps)
    placed_arc_ids = {id(arc) for arc in swing_by_gap.values()}
    unplaced = 0
    for arc in arcs:
        if id(arc) in placed_arc_ids:
            continue
        if _gaps_containing_swing(arc, run_gaps):
            continue
        leaf_gap = _gap_from_swing_leaf(arc, union, gaps)
        if leaf_gap is None:
            unplaced += 1
            continue
        swing_by_gap[len(gaps)] = arc
        gaps.append(leaf_gap)
        placed_arc_ids.add(id(arc))

    jamb_by_id: dict[int, tuple[int, ...]] = {}
    if dark_painted_wall_source:
        for gap, native in _jamb_pair_gaps(drawings, union, gaps):
            jamb_by_id[id(gap)] = native
            gaps.append(gap)

    closures: list[LayeredDoorwayClosure] = []
    closed_gaps: list[_Gap] = []
    unresolved: list[_Gap] = []
    closure_rects: list[tuple[str, Polygon]] = []
    sliding_by_gap: dict[int, tuple[int, ...]] = {}
    if sliding_leaf_frame_closure:
        for gap_index, gap in enumerate(gaps):
            evidence = _sliding_leaf_evidence(drawings, gap)
            if evidence is not None:
                sliding_by_gap[gap_index] = evidence
        # one native stroke or box may evidence only ONE interruption; a shared one is a one-to-many span
        uses = Counter(index for evidence in sliding_by_gap.values() for index in evidence)
        sliding_by_gap = {g: e for g, e in sliding_by_gap.items() if all(uses[i] == 1 for i in e)}

    def _append_closure(gap: _Gap, kind: str, native: tuple[int, ...]) -> None:
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
        closed_gaps.append(gap)
        # Frame cracks beside a sourced opening are thinner than a wall and are
        # not rooms. Pad only the planarization barrier, never the evidenced interval.
        pad = _STROKE_PAIR_THICK_MIN
        if gap.horizontal:
            barrier_rect = box(gap.lo - pad, gap.band[0], gap.hi + pad, gap.band[1])
        else:
            barrier_rect = box(gap.band[0], gap.lo - pad, gap.band[1], gap.hi + pad)
        closure_rects.append((closure_id, barrier_rect))

    for gap_index, gap in enumerate(gaps):
        swing = swing_by_gap.get(gap_index)
        host_wall = (gap.band[1] - gap.band[0]) >= _STROKE_PAIR_THICK_MIN
        stroke = None
        if swing is None and host_wall:
            stroke = _stroke_closed(
                drawings, gap, all_ink=dark_painted_wall_source,
            )
        if stroke is None and swing is None and host_wall and dark_painted_wall_source:
            stroke = _jamb_cap_closed(
                drawings, gap, all_ink=True,
                wall_depth=_wall_end_depth(gap, gaps, swing_by_gap) if jamb_caps_must_be_wall_ends else None,
            )
        if (
            stroke is None and swing is None and host_wall
            and dark_painted_wall_source and not sliding_leaf_frame_closure
        ):
            stroke = _frame_pair_closed(drawings, gap)
        if stroke is None and swing is None and host_wall:
            stroke = jamb_by_id.get(id(gap))
        sliding = sliding_by_gap.get(gap_index)
        if sliding is not None and (swing is not None or stroke is not None):
            unresolved.append(gap)  # competing doorway evidence in one interruption: neither is chosen
            continue
        if swing is None and stroke is None and sliding is None:
            unresolved.append(gap)
            continue
        if swing is not None:
            kind, native = KIND_SWING, tuple(sorted({
                *swing.get("arc_source_ids", (swing["arc"],)),
                swing["leaf"],
            }))
        elif stroke is not None:
            kind, native = KIND_STROKE, tuple(stroke)
        else:
            kind, native = KIND_SLIDING_LEAF, tuple(sliding)
        _append_closure(gap, kind, native)

    # A thick wall has two collinear faces. Closing one face of an opening
    # (jamb/stroke) also resolves the parallel unfinished face of the same
    # span; leave competing / differently spanned gaps unresolved.
    seed_faces = tuple(zip(tuple(closed_gaps), tuple(closures)))
    still_unresolved: list[_Gap] = []
    for gap in unresolved:
        sibling_native: tuple[int, ...] | None = None
        sibling_kind = KIND_STROKE
        for closed, closure in seed_faces:
            if not gap.collinear or closed.horizontal != gap.horizontal:
                continue
            if not (
                _close(closed.lo, gap.lo, _STROKE_PAIR_FACE_PT)
                and _close(closed.hi, gap.hi, _STROKE_PAIR_FACE_PT)
            ):
                continue
            overlap = (
                min(closed.band[1], gap.band[1]) - max(closed.band[0], gap.band[0])
            )
            if overlap < _STROKE_PAIR_THICK_MIN - _STROKE_PAIR_FACE_PT:
                continue
            sibling_native = tuple(closure.native_path_indices)
            sibling_kind = closure.kind
            break
        if sibling_native is None:
            still_unresolved.append(gap)
            continue
        _append_closure(gap, sibling_kind, sibling_native)
    unresolved = still_unresolved

    barrier = _closed_union([*polygons, *(rect for _cid, rect in closure_rects)])
    free = domain.difference(barrier)
    rings: list[LayeredRoomRingRecord] = []
    thicknesses = sorted(min(s.x1 - s.x0, s.y1 - s.y0) for s in strips)
    median_thickness = thicknesses[len(thicknesses) // 2]
    sliver_count = 0
    free_space_part_count = 0
    free_space_exterior_touching_count = 0
    free_space_enclosed_part_count = 0
    free_space_max_enclosed_area_pt2 = 0.0
    drafting_pocket_sliver_count = 0
    for part in _polygon_parts(free):
        if part.area <= NOISE_PT * NOISE_PT:
            continue
        free_space_part_count += 1
        # Full median-thickness inset: wall-cavity drafting pockets (~3×3 pt)
        # are not rooms. Half-thickness previously left tiny false rings.
        if part.buffer(-median_thickness, join_style=2).is_empty:
            sliver_count += 1
            drafting_pocket_sliver_count += 1
            continue
        minx, miny, maxx, maxy = part.bounds
        width, height = maxx - minx, maxy - miny
        # Both extents inside a few wall thicknesses → cavity, not a room.
        if (
            width < 6.0 * median_thickness
            and height < 6.0 * median_thickness
        ):
            sliver_count += 1
            drafting_pocket_sliver_count += 1
            continue
        reasons: list[str] = []
        touches_domain = part.boundary.intersects(domain.boundary.buffer(NOISE_PT))
        if touches_domain:
            free_space_exterior_touching_count += 1
            continue  # the exterior region: not a room
        free_space_enclosed_part_count += 1
        free_space_max_enclosed_area_pt2 = max(
            free_space_max_enclosed_area_pt2, float(part.area),
        )
        # Only a collinear interruption whose BOTH ends sit on this ring's
        # outer face may invalidate it. Aligned walls outside the room, or
        # disconnected partitions inside it, are not openings in THIS perimeter.
        adjacent_open = any(
            _unresolved_collinear_gap_breaches_outer_ring(part, gap)
            for gap in unresolved
        )
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
            owners = tuple(sorted(
                [f"layered_wall_strip:{index}" for s in strips if s.polygon.distance(mid) <= NOISE_PT * 2 for index in s.native_path_indices()]
                + [f"layered_wall_fill:{index}" for index, polygon in other_fills if polygon.distance(mid) <= NOISE_PT * 2]
            ))
            if owners:
                wall_edges += 1
                edge_owners.append(owners)
                continue
            owner = next((cid for cid, rect in closure_rects if rect.buffer(NOISE_PT).contains(mid)), None)
            if owner is not None:
                closure_edges += 1
                bounding_closures.add(owner)
                edge_owners.append((f"layered_doorway_closure:{owner}",))
                continue
            unowned_edges += 1
            edge_owners.append(())
        if unowned_edges:
            reasons.append(REASON_UNOWNED_EDGE)
        wall_paths = tuple(sorted({index for s in strips if part.buffer(NOISE_PT * 2).intersects(s.polygon) for index in s.native_path_indices()}))
        status = EvidenceResolutionStatus.ABSTAINED if reasons else EvidenceResolutionStatus.CANDIDATE
        if not reasons:
            reasons.append(REASON_RING_CLOSED)
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
    gap_witnesses, gap_witness_count = _source_unresolved_gap_witnesses(unresolved)
    tier_lt_100 = sum(1 for r in rings if r.area_pt2 < 100.0)
    tier_mid = sum(1 for r in rings if 100.0 <= r.area_pt2 < 1000.0)
    tier_ge_1000 = sum(1 for r in rings if r.area_pt2 >= 1000.0)
    return LayeredRoomRingResult(
        status=EvidenceResolutionStatus.CANDIDATE if candidate else EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(REASON_RING_CLOSED,) if candidate else (REASON_OPEN_EXTERIOR,),
        rings=tuple(rings), closures=tuple(closures), wall_strip_count=len(strips),
        wall_gap_count=len(gaps), unresolved_gap_count=len([g for g in unresolved if g.collinear]),
        non_strip_wall_fill_count=unsupported, unplaced_swing_count=unplaced, ambiguous_swing_count=ambiguous,
        sliver_region_count=sliver_count,
        source_segmented_swing_witnesses=segmented_witnesses,
        source_owned_doorway_chords=sourced_doorway_chords,
        unresolved_gap_witnesses=gap_witnesses,
        unresolved_gap_witness_count=gap_witness_count,
        free_space_part_count=free_space_part_count,
        free_space_exterior_touching_count=free_space_exterior_touching_count,
        free_space_enclosed_part_count=free_space_enclosed_part_count,
        free_space_max_enclosed_area_pt2=round(free_space_max_enclosed_area_pt2, 4),
        merged_collinear_dark_face_strip_count=len(merged_face_strips),
        ring_area_tier_lt_100_count=tier_lt_100,
        ring_area_tier_100_to_1000_count=tier_mid,
        ring_area_tier_ge_1000_count=tier_ge_1000,
        drafting_pocket_sliver_count=drafting_pocket_sliver_count,
    )


def build_from_pdf_bytes(
    source_bytes: bytes, *,     source_sha256: str, page_index: int, sliding_leaf_frame_closure: bool = False,
    dark_painted_wall_source: bool = False,
    door_jamb_returns: bool = False,
    jamb_caps_must_be_wall_ends: bool = False,
    wall_end_stroke_closures: bool = False,
    source_heavy_stroke_wall_bands: bool = False,
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
        dark_painted_wall_source=dark_painted_wall_source,
        door_jamb_returns=door_jamb_returns,
        jamb_caps_must_be_wall_ends=jamb_caps_must_be_wall_ends,
        wall_end_stroke_closures=wall_end_stroke_closures,
        source_heavy_stroke_wall_bands=source_heavy_stroke_wall_bands,
    )


__all__ = [
    "KIND_STROKE",
    "KIND_SLIDING_LEAF",
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
