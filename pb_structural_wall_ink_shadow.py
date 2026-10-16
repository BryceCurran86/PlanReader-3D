"""Shadow-only structural-ink evidence for native vector wall linework.

Why this exists. The wall chain keeps every drawn primitive as a candidate and, by design, treats stroke weight,
colour, layer and fill as description only (``pb_physical_wall_source_metadata_shadow``). On a plan whose walls are
drawn heavier than everything else, nothing then separates structural geometry from finish, joinery, fixture,
annotation and lettering geometry, so every relaxation behind that gate raises ownership of non-wall candidates.
This module computes TYPED, RELATIONAL evidence for that gate and nothing else.

What it does. From native stroke/fill segments of one page it reports, per source primitive id, one of

* ``WALL_NETWORK_INK_CANDIDATE``: darkest-present ink that either sits in a parallel-face pair (two faces a plausible
  wall thickness apart that overlap along a long run) inside a connected paired-face network of building scale, or is
  the heaviest ink class whose own strokes form a connected network of building scale (walls drawn as one heavy
  line each);
* ``NOT_WALL_INK``: only for definite negatives (a sheet-frame ring, a ruled ring, a dashed/patterned stroke, a run of at
  least three glyph-sized paths on one baseline: outlined lettering, dimension ticks). A ruled ring is a pure ring in its
  own ink class (nearly all of its length on its own bounding box) around at least four parallel full-span rule lines: a
  schedule, legend or title-block table, or a grille symbol. A building ring has partitions of its own class touching it, so
  it is not a pure ring;
* ``UNPROVEN``: everything else, retained, with the reason it could not be proven.

What it deliberately does not do. It does not use a numeric stroke-weight threshold, a colour list, a layer name, a
project name, a page number or any expected quantity. "Darkest present ink" is an ordinal rank on the page's own
strokes. It does not filter, merge, snap or re-key anything, it does not raise any authority, it is not called by a
live path, and ``UNPROVEN`` primitives are never dropped. Fixtures and joinery that touch a wall network are NOT
separated from it here: that remains an open gate. The per-class table lets a reviewer see which ink class each
network member belongs to.

Bounded work: input above ``MAX_STRUCTURAL_INK_SEGMENTS`` eligible segments is returned entirely ``UNPROVEN`` with
``structural_ink_scope_too_large``; the 20,000-segment wall-topology cap of the live wall authority is untouched.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import math
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

STRUCTURAL_WALL_INK_SCHEMA_VERSION = "1.0.0"

WALL_NETWORK_INK_CANDIDATE = "wall_network_ink_candidate"
NOT_WALL_INK = "not_wall_ink"
UNPROVEN = "unproven"

REASON_PAIRED_FACE_NETWORK = "paired_face_network_of_building_scale"
REASON_SHEET_FRAME_RING = "sheet_frame_ring"
REASON_DASHED_OR_PATTERNED = "dashed_or_patterned_stroke"
REASON_OUTLINED_GLYPH_RUN = "repeated_small_path_run"
REASON_NO_PARTNER = "no_parallel_face_partner"
REASON_SMALL_ISLAND = "paired_island_below_network_extent"
REASON_LIGHTER_INK = "lighter_than_darkest_present_ink"
REASON_BELOW_MIN_LENGTH = "below_minimum_run_length"
REASON_FILL_NOT_STRIP = "filled_primitive_not_a_strip"
REASON_NO_GRAPHIC_STATE = "stroke_or_fill_state_unavailable"
REASON_SCOPE_TOO_LARGE = "structural_ink_scope_too_large"

# Geometry-of-drawing constants (page points). Each is a relation to the drawing itself, never to an expected value.
MIN_RUN_LENGTH_PT = 2.0             # shorter primitives cannot be a face run
MAX_FACE_GAP_PT = 8.0               # face-to-face search bound; thicker drawn walls stay UNPROVEN (reported)
MIN_FACE_ASPECT = 8.0               # paired run length must be at least this many wall thicknesses
MIN_FACE_OFFSET_PT = 0.3            # below this the two lines are one line, not two faces
COLLINEAR_OFFSET_TOL_PT = 0.3       # same line for run merging
RUN_JOIN_GAP_PT = 0.6               # contiguous collinear pieces of one face
ANGLE_TOL_RAD = math.radians(1.0)
CONTACT_SLACK_PT = 0.6              # strokes touch when closer than half their widths plus this
NETWORK_MIN_MAJOR_FRACTION = 0.15   # building-scale network: major bbox side vs the page's shorter side
NETWORK_MIN_MINOR_FRACTION = 0.10   # ... and it must be areal, not a single string (a title-block strip is not)
GLYPH_MAX_EXTENT_FRACTION = 0.02    # one glyph path is at most this fraction of the page's shorter side
GLYPH_MIN_RUN = 3                   # a text line has at least this many glyph-sized paths on a baseline
GLYPH_BASELINE_TOL_FRACTION = 0.2   # baseline alignment tolerance relative to glyph height
GLYPH_MAX_GAP_FACTOR = 2.5          # neighbouring glyphs of one line are at most this many glyph heights apart
MAX_OPENING_GAP_FACTOR = 12.0       # a wall face may continue across a collinear gap up to this many wall thicknesses
MAX_WALL_BODY_GAP_FACTOR = 80.0     # a wider gap needs the partner face interrupted over the same interval
GAP_PARTNER_MATCH_TOL_PT = 1.0
MAX_GAP_CANDIDATES_FOR_PARTNER_MATCH = 5000
OPENING_GAP_COLLINEAR_TOL_PT = 0.5
REASON_CONTINUED_ACROSS_GAP = "network_continued_across_collinear_gap"
REASON_HEAVIEST_SINGLE_STROKE_NETWORK = "heaviest_areal_single_stroke_network"
REASON_RULED_RING = "ruled_ring_table_or_grille"
REASON_GLYPH_RUN_ATTACHED = "glyph_sized_run_attached_to_wall_network"
TABLE_MIN_ROWS = 4                  # a pure ring around at least this many full-span parallel lines is a table, not a building
TABLE_ROW_SPAN_FRACTION = 0.9       # a row line spans at least this share of the ring's side
TABLE_ROW_MIN_SEPARATION_PT = 1.0   # row lines closer than this are one line (a double rule)
TABLE_RING_FRACTION = 0.9           # share of the ring component's length that runs along its own box sides (stricter than a frame)
STRIP_MAX_SEGMENTS = 5              # a filled wall strip is a rectangle-like path
STRIP_MIN_ASPECT = 4.0
STRIP_MIN_LENGTH_PT = 6.0
FRAME_RING_FRACTION = 0.8           # share of a frame component's length lying on its own bbox boundary
FRAME_RING_TOL_PT = 1.5
FRAME_SHEET_FRACTION = 0.9          # a component this close to the whole sheet in both dimensions is the sheet frame
FRAME_RING_MINOR_FRACTION = 0.7     # a ring-shaped component spanning the sheet length and most of its height
MAX_STRUCTURAL_INK_SEGMENTS = 120_000
_GRID_CELL_PT = 40.0
_CONTACT_CELL_PT = 6.0


@dataclass(frozen=True)
class StructuralInkDecision:
    source_primitive_id: str
    classification: str
    reason_codes: Tuple[str, ...]
    ink_class: Optional[Tuple[Any, ...]]
    network_id: Optional[int]


@dataclass(frozen=True)
class OpeningGapCandidate:
    """Two facing ends of one wall face line, equal thickness, a plausible opening apart.

    Evidence of an interruption in the wall body, not an opening: the kind, host, frame and size of whatever
    occupies the gap are not proven here. ``end_a``/``end_b`` are the facing face ends; the primitive ids
    are the source primitives that own those ends.
    """

    end_a: Tuple[float, float]
    end_b: Tuple[float, float]
    gap_length_pt: float
    thickness_pt: float
    source_primitive_id_a: str
    source_primitive_id_b: str


@dataclass(frozen=True)
class GlyphSizedRun:
    """A run of at least three glyph-sized paths on one baseline: outlined lettering, numerals or dimension ticks.

    This is the source-native ink and ancestry of such a run (box, baseline, path and primitive ids), not its text:
    reading it needs a separately approved source-positive reader or a human hint. ``touches_wall_network`` is True when
    some piece of the run touches a building-scale wall network (a door frame, a post), so a reviewer can tell lettering
    apart from jambs.
    """

    bbox: Tuple[float, float, float, float]
    path_count: int
    segment_count: int
    baseline_y_pt: float
    glyph_height_pt: float
    touches_wall_network: bool
    source_primitive_ids: Tuple[str, ...]


@dataclass(frozen=True)
class InkClassRow:
    ink_class: Tuple[Any, ...]
    segment_count: int
    total_length_pt: float
    candidate_segment_count: int


@dataclass(frozen=True)
class StructuralWallInkReport:
    decisions: Tuple[StructuralInkDecision, ...]
    class_table: Tuple[InkClassRow, ...]
    network_count: int
    darkest_ink_color: Optional[Tuple[float, ...]]
    reason_codes: Tuple[str, ...]
    opening_gaps: Tuple[OpeningGapCandidate, ...] = ()
    glyph_runs: Tuple[GlyphSizedRun, ...] = ()
    schema_version: str = STRUCTURAL_WALL_INK_SCHEMA_VERSION
    shadow_only: bool = True
    live_effect: bool = False
    wall_authority_granted: bool = False

    def classification_of(self, source_primitive_id: str) -> Optional[str]:
        for decision in self.decisions:
            if decision.source_primitive_id == source_primitive_id:
                return decision.classification
        return None

    def ids_with(self, classification: str) -> Tuple[str, ...]:
        return tuple(d.source_primitive_id for d in self.decisions if d.classification == classification)


def _num(value: Any) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _color(value: Any) -> Optional[Tuple[float, ...]]:
    if not isinstance(value, (list, tuple)) or not value:
        return None
    out = []
    for channel in value:
        number = _num(channel)
        if number is None:
            return None
        out.append(round(number, 3))
    return tuple(out)


def _luminance(color: Tuple[float, ...]) -> float:
    return sum(color) / len(color)


def _solid(dashes: Any) -> bool:
    if dashes is None:
        return True
    if isinstance(dashes, str):
        return dashes.strip() in ("", "[] 0", "[]", "[] 0.0")
    if isinstance(dashes, (list, tuple)):
        return not dashes
    return False


def _endpoints(segment: Mapping[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    values = tuple(_num(segment.get(k)) for k in ("x1", "y1", "x2", "y2"))
    if any(v is None for v in values):
        return None
    return values  # type: ignore[return-value]


def _length(p: Tuple[float, float, float, float]) -> float:
    return math.hypot(p[2] - p[0], p[3] - p[1])


def _angle(p: Tuple[float, float, float, float]) -> float:
    return math.atan2(p[3] - p[1], p[2] - p[0]) % math.pi


def _point_segment_distance(px: float, py: float, q: Tuple[float, float, float, float]) -> float:
    dx, dy = q[2] - q[0], q[3] - q[1]
    length2 = dx * dx + dy * dy
    if length2 == 0.0:
        return math.hypot(px - q[0], py - q[1])
    t = max(0.0, min(1.0, ((px - q[0]) * dx + (py - q[1]) * dy) / length2))
    return math.hypot(px - (q[0] + t * dx), py - (q[1] + t * dy))


def _segment_distance(a: Tuple[float, float, float, float], b: Tuple[float, float, float, float]) -> float:
    def cross(ax: float, ay: float, bx: float, by: float) -> float:
        return ax * by - ay * bx

    d1 = cross(a[2] - a[0], a[3] - a[1], b[0] - a[0], b[1] - a[1])
    d2 = cross(a[2] - a[0], a[3] - a[1], b[2] - a[0], b[3] - a[1])
    d3 = cross(b[2] - b[0], b[3] - b[1], a[0] - b[0], a[1] - b[1])
    d4 = cross(b[2] - b[0], b[3] - b[1], a[2] - b[0], a[3] - b[1])
    if d1 * d2 < 0 and d3 * d4 < 0:
        return 0.0
    return min(
        _point_segment_distance(a[0], a[1], b), _point_segment_distance(a[2], a[3], b),
        _point_segment_distance(b[0], b[1], a), _point_segment_distance(b[2], b[3], a),
    )


class _UnionFind:
    def __init__(self, items: Iterable[int]):
        self.parent = {i: i for i in items}

    def find(self, item: int) -> int:
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            # deterministic: the smaller index becomes the root
            self.parent[max(ra, rb)] = min(ra, rb)


@dataclass
class _Run:
    """Contiguous collinear primitives of one ink class (one drawn face)."""

    members: List[int]
    p: Tuple[float, float, float, float]
    width: float
    ink_class: Tuple[Any, ...]


def _contact_union(runs: Sequence["_Run"], members: Sequence[int]) -> "_UnionFind":
    uf = _UnionFind(members)
    cells: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for r in members:
        x0, x1 = sorted((runs[r].p[0], runs[r].p[2]))
        y0, y1 = sorted((runs[r].p[1], runs[r].p[3]))
        for gx in range(int(x0 // _CONTACT_CELL_PT) - 1, int(x1 // _CONTACT_CELL_PT) + 2):
            for gy in range(int(y0 // _CONTACT_CELL_PT) - 1, int(y1 // _CONTACT_CELL_PT) + 2):
                cells[(gx, gy)].append(r)
    checked: set = set()
    for cell in sorted(cells):
        group = cells[cell]
        for ia in range(len(group)):
            for ib in range(ia + 1, len(group)):
                a, b = group[ia], group[ib]
                if (a, b) in checked or uf.find(a) == uf.find(b):
                    continue
                checked.add((a, b))
                tol = (runs[a].width + runs[b].width) / 2 + CONTACT_SLACK_PT
                if _segment_distance(runs[a].p, runs[b].p) <= tol:
                    uf.union(a, b)
    return uf


def classify_structural_wall_ink(
    segments: Sequence[Mapping[str, Any]],
    *,
    page_width: float,
    page_height: float,
) -> StructuralWallInkReport:
    """Classify native segments; see the module docstring. Pure, deterministic, input-order invariant."""
    page_min = min(float(page_width), float(page_height))
    page_max = max(float(page_width), float(page_height))
    if not (math.isfinite(page_min) and page_min > 0):
        raise ValueError("page extent must be positive and finite")

    # Stable identity: segments are processed in sorted source-id order, never in input order.
    keyed: List[Tuple[str, Mapping[str, Any]]] = []
    for position, segment in enumerate(segments):
        ident = str(segment.get("id") if segment.get("id") not in (None, "") else f"anon:{position}")
        keyed.append((ident, segment))
    keyed.sort(key=lambda item: item[0])
    ids = [k for k, _ in keyed]
    if len(set(ids)) != len(ids):
        raise ValueError("source primitive ids must be unique")
    segs = [s for _, s in keyed]
    n = len(segs)

    reasons: Dict[int, List[str]] = defaultdict(list)
    label: Dict[int, str] = {}
    net_of: Dict[int, int] = {}
    cls_of: Dict[int, Tuple[Any, ...]] = {}

    def set_label(i: int, classification: str, reason: str) -> None:
        # NOT_WALL_INK is never overwritten by a weaker label; positive labels never silently replace a negative.
        if label.get(i) == NOT_WALL_INK:
            return
        label[i] = classification
        reasons[i].append(reason)

    pts: Dict[int, Tuple[float, float, float, float]] = {}
    for i, s in enumerate(segs):
        p = _endpoints(s)
        if p is not None:
            pts[i] = p

    # ---- path structure (strip fills, glyph-sized paths) -------------------------------------------------------
    paths: Dict[Any, List[int]] = defaultdict(list)
    for i, s in enumerate(segs):
        if i in pts and s.get("path_index") is not None:
            paths[s.get("path_index")].append(i)

    def path_extent(members: Sequence[int]) -> Tuple[float, float, float, float]:
        xs = [v for m in members for v in (pts[m][0], pts[m][2])]
        ys = [v for m in members for v in (pts[m][1], pts[m][3])]
        return min(xs), min(ys), max(xs), max(ys)

    # ---- ink colour rank: the darkest stroke or fill present on the page ----------------------------------------
    strokes: Dict[int, Tuple[float, ...]] = {}
    fills: Dict[int, Tuple[float, ...]] = {}
    for i, s in enumerate(segs):
        if i not in pts:
            continue
        c = _color(s.get("stroke")) if s.get("stroke_present", s.get("stroke") is not None) else None
        if c is not None:
            strokes[i] = c
        f = _color(s.get("fill")) if s.get("fill_present", s.get("fill") is not None) else None
        if f is not None:
            fills[i] = f
    luminances = [_luminance(c) for c in list(strokes.values()) + list(fills.values())]
    darkest = min(luminances) if luminances else None
    darkest_colors = {c for c in list(strokes.values()) + list(fills.values())
                      if darkest is not None and abs(_luminance(c) - darkest) < 1e-6}
    darkest_color = min(darkest_colors) if darkest_colors else None

    # ---- eligibility ---------------------------------------------------------------------------------------------
    eligible: List[int] = []
    strip_paths: Dict[Any, bool] = {}
    for i, s in enumerate(segs):
        if i not in pts:
            set_label(i, UNPROVEN, REASON_NO_GRAPHIC_STATE)
            continue
        if i in strokes:
            cls_of[i] = ("stroke", round(_num(s.get("width")) or 0.0, 3), strokes[i], "solid" if _solid(s.get("dashes")) else "patterned")
            if not _solid(s.get("dashes")):
                set_label(i, NOT_WALL_INK, REASON_DASHED_OR_PATTERNED)
                continue
            if strokes[i] not in darkest_colors:
                set_label(i, UNPROVEN, REASON_LIGHTER_INK)
                continue
            if _length(pts[i]) <= 0.0:
                set_label(i, UNPROVEN, REASON_BELOW_MIN_LENGTH)
                continue
            if (_num(s.get("width")) or 0.0) <= 0.0:
                set_label(i, UNPROVEN, REASON_NO_GRAPHIC_STATE)
                continue
            eligible.append(i)
        elif i in fills:
            cls_of[i] = ("fill", fills[i])
            if fills[i] not in darkest_colors:
                set_label(i, UNPROVEN, REASON_LIGHTER_INK)
                continue
            key = s.get("path_index")
            if key not in strip_paths:
                members = paths.get(key, [])
                if members and len(members) <= STRIP_MAX_SEGMENTS:
                    x0, y0, x1, y1 = path_extent(members)
                    w, h = x1 - x0, y1 - y0
                    strip_paths[key] = (max(w, h) >= STRIP_MIN_LENGTH_PT
                                        and max(w, h) >= STRIP_MIN_ASPECT * max(min(w, h), 0.5))
                else:
                    strip_paths[key] = False
            if not strip_paths[key]:
                set_label(i, UNPROVEN, REASON_FILL_NOT_STRIP)
                continue
            if _length(pts[i]) <= 0.0:
                set_label(i, UNPROVEN, REASON_BELOW_MIN_LENGTH)
                continue
            eligible.append(i)
        else:
            set_label(i, UNPROVEN, REASON_NO_GRAPHIC_STATE)

    if len(eligible) > MAX_STRUCTURAL_INK_SEGMENTS:
        decisions = tuple(StructuralInkDecision(ids[i], UNPROVEN, (REASON_SCOPE_TOO_LARGE,), cls_of.get(i), None)
                          for i in range(n))
        return StructuralWallInkReport(decisions, (), 0, darkest_color, (REASON_SCOPE_TOO_LARGE,))

    # ---- outlined-glyph runs (definite negative): glyph-sized paths in baseline-aligned runs ----------------------
    glyph_max = GLYPH_MAX_EXTENT_FRACTION * page_min
    small: List[Tuple[Any, float, float, float, float]] = []
    for key, members in paths.items():
        if not members:
            continue
        x0, y0, x1, y1 = path_extent(members)
        if max(x1 - x0, y1 - y0) <= glyph_max and any(m in strokes or m in fills for m in members):
            if all(((m in strokes and strokes[m] in darkest_colors) or (m in fills and fills[m] in darkest_colors))
                   for m in members if m in pts):
                small.append((key, x0, y0, x1, y1))
    small.sort(key=lambda r: (r[4], r[1], repr(r[0])))   # by baseline (bottom edge), then x
    glyph_keys: set = set()
    run_groups: List[List[int]] = []
    if small:
        guf = _UnionFind(range(len(small)))
        tol_max = GLYPH_BASELINE_TOL_FRACTION * max(glyph_max, 1.0)
        for a in range(len(small)):
            _, ax0, ay0, ax1, ay1 = small[a]
            for b in range(a + 1, len(small)):
                _, bx0, by0, bx1, by1 = small[b]
                if by1 - ay1 > tol_max:
                    break
                height = max(ay1 - ay0, by1 - by0, 1.0)
                if abs(by1 - ay1) > GLYPH_BASELINE_TOL_FRACTION * height:
                    continue
                gap = max(bx0 - ax1, ax0 - bx1)
                if gap <= GLYPH_MAX_GAP_FACTOR * height:
                    guf.union(a, b)
        groups: Dict[int, List[int]] = defaultdict(list)
        for a in range(len(small)):
            groups[guf.find(a)].append(a)
        for members in groups.values():
            if len(members) >= GLYPH_MIN_RUN:
                run_groups.append(sorted(members))
                for a in members:
                    glyph_keys.add(small[a][0])
    # Glyph-sized runs are withheld from the network search, but they are judged AFTER it: a run that touches a
    # building-scale wall network (door jambs, posts, returns) is kept as UNPROVEN, never rejected.
    eligible_before_glyphs = set(eligible)
    glyph_members: Dict[Any, List[int]] = {}
    for key in sorted(glyph_keys, key=repr):
        glyph_members[key] = [m for m in paths[key] if m in eligible_before_glyphs or label.get(m) in (None, UNPROVEN)]
    deferred_glyph = {m for members in glyph_members.values() for m in members}
    eligible = [i for i in eligible if i not in deferred_glyph]

    # ---- runs: merge contiguous collinear pieces of one ink class --------------------------------------------------
    by_class: Dict[Tuple[Any, ...], List[int]] = defaultdict(list)
    for i in eligible:
        by_class[cls_of[i]].append(i)
    runs: List[_Run] = []
    for klass in sorted(by_class, key=repr):
        members = sorted(by_class[klass])
        buckets: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for i in members:
            a = _angle(pts[i])
            ux, uy = math.cos(a), math.sin(a)
            off = -pts[i][0] * uy + pts[i][1] * ux
            buckets[(int(round(a / ANGLE_TOL_RAD)), int(round(off / COLLINEAR_OFFSET_TOL_PT)))].append(i)
        for key in sorted(buckets):
            group = buckets[key]
            a = _angle(pts[group[0]])
            ux, uy = math.cos(a), math.sin(a)

            def span(i: int) -> Tuple[float, float]:
                t1 = pts[i][0] * ux + pts[i][1] * uy
                t2 = pts[i][2] * ux + pts[i][3] * uy
                return (min(t1, t2), max(t1, t2))

            order = sorted(group, key=lambda i: (span(i)[0], span(i)[1], i))
            current: List[int] = [order[0]]
            reach = span(order[0])[1]
            for i in order[1:]:
                lo, hi = span(i)
                if lo <= reach + RUN_JOIN_GAP_PT:
                    current.append(i)
                    reach = max(reach, hi)
                else:
                    runs.append(_make_run(current, pts, segs, klass, ux, uy))
                    current, reach = [i], hi
            runs.append(_make_run(current, pts, segs, klass, ux, uy))

    kept_runs: List[_Run] = []
    for run in runs:
        if _length(run.p) < MIN_RUN_LENGTH_PT:
            for m in run.members:
                set_label(m, UNPROVEN, REASON_BELOW_MIN_LENGTH)
        else:
            kept_runs.append(run)
    runs = kept_runs

    # ---- pairing: two faces a plausible wall thickness apart with a long overlap ------------------------------------
    # Every run is registered in all cells its box (padded by the face-gap search bound) covers and queries all cells
    # its own box covers, so two overlapping faces find each other from either side, however long either one is.
    grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for r, run in enumerate(runs):
        bx0, bx1 = sorted((run.p[0], run.p[2]))
        by0, by1 = sorted((run.p[1], run.p[3]))
        for gx in range(int((bx0 - MAX_FACE_GAP_PT) // _GRID_CELL_PT), int((bx1 + MAX_FACE_GAP_PT) // _GRID_CELL_PT) + 1):
            for gy in range(int((by0 - MAX_FACE_GAP_PT) // _GRID_CELL_PT), int((by1 + MAX_FACE_GAP_PT) // _GRID_CELL_PT) + 1):
                grid[(gx, gy)].append(r)
    paired: set = set()
    thickness: Dict[int, float] = {}
    for r, run in enumerate(runs):
        run_len = _length(run.p)
        a = _angle(run.p)
        ux, uy = math.cos(a), math.sin(a)
        nx, ny = -uy, ux
        cx, cy = (run.p[0] + run.p[2]) / 2, (run.p[1] + run.p[3]) / 2
        found = False
        best_off = None
        qx0, qx1 = sorted((run.p[0], run.p[2]))
        qy0, qy1 = sorted((run.p[1], run.p[3]))
        seen_q: set = set()
        for gx in range(int(qx0 // _GRID_CELL_PT), int(qx1 // _GRID_CELL_PT) + 1):
            for gy in range(int(qy0 // _GRID_CELL_PT), int(qy1 // _GRID_CELL_PT) + 1):
                for q in grid.get((gx, gy), ()):
                    if q == r or q in seen_q:
                        continue
                    seen_q.add(q)
                    other = runs[q]
                    d = abs(_angle(other.p) - a)
                    if min(d, math.pi - d) > ANGLE_TOL_RAD:
                        continue
                    ox, oy = (other.p[0] + other.p[2]) / 2, (other.p[1] + other.p[3]) / 2
                    off = abs((ox - cx) * nx + (oy - cy) * ny)
                    if off < MIN_FACE_OFFSET_PT or off > MAX_FACE_GAP_PT:
                        continue
                    s1 = sorted(((run.p[0] - cx) * ux + (run.p[1] - cy) * uy, (run.p[2] - cx) * ux + (run.p[3] - cy) * uy))
                    s2 = sorted(((other.p[0] - cx) * ux + (other.p[1] - cy) * uy, (other.p[2] - cx) * ux + (other.p[3] - cy) * uy))
                    overlap = min(s1[1], s2[1]) - max(s1[0], s2[0])
                    if overlap >= 0.5 * min(run_len, _length(other.p)) and overlap >= MIN_FACE_ASPECT * off:
                        if best_off is None or off < best_off:
                            best_off = off
                        found = True
        if found:
            paired.add(r)
            thickness[r] = best_off

    # ---- contact components among paired runs -----------------------------------------------------------------------
    paired_list = sorted(paired)
    uf = _UnionFind(paired_list)
    cgrid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for r in paired_list:
        x0, x1 = sorted((runs[r].p[0], runs[r].p[2]))
        y0, y1 = sorted((runs[r].p[1], runs[r].p[3]))
        for gx in range(int(x0 // _CONTACT_CELL_PT) - 1, int(x1 // _CONTACT_CELL_PT) + 2):
            for gy in range(int(y0 // _CONTACT_CELL_PT) - 1, int(y1 // _CONTACT_CELL_PT) + 2):
                cgrid[(gx, gy)].append(r)
    checked: set = set()
    for cell in sorted(cgrid):
        members = cgrid[cell]
        for ia in range(len(members)):
            for ib in range(ia + 1, len(members)):
                a, b = members[ia], members[ib]
                key = (a, b)
                if key in checked or uf.find(a) == uf.find(b):
                    continue
                checked.add(key)
                tol = (runs[a].width + runs[b].width) / 2 + CONTACT_SLACK_PT
                if _segment_distance(runs[a].p, runs[b].p) <= tol:
                    uf.union(a, b)
    # Collinear continuation across an opening-sized gap: same face line, same thickness, facing ends. Openings
    # carry door leaves, swing arcs and window lines, so a drawn symbol inside the gap is not a reason to refuse.
    face_ends: List[Tuple[int, float, float, float, float]] = []
    for r in paired_list:
        p = runs[r].p
        a = _angle(p)
        ux, uy = math.cos(a), math.sin(a)
        if (p[2] - p[0]) * ux + (p[3] - p[1]) * uy < 0:
            ux, uy = -ux, -uy
        face_ends.append((r, p[2], p[3], ux, uy))      # end at (x2, y2), outward = +u
        face_ends.append((r, p[0], p[1], -ux, -uy))    # end at (x1, y1), outward = -u
    end_grid: Dict[Tuple[int, int], List[int]] = defaultdict(list)
    for k, (r, ex, ey, _, _) in enumerate(face_ends):
        end_grid[(int(ex // _GRID_CELL_PT), int(ey // _GRID_CELL_PT))].append(k)
    bridged: set = set()
    gap_pairs: Dict[Tuple[int, int], Tuple[int, int, float, float]] = {}
    for k, (r, ex, ey, ux, uy) in enumerate(face_ends):
        max_gap = MAX_WALL_BODY_GAP_FACTOR * thickness[r]
        reach = int(max_gap // _GRID_CELL_PT) + 1
        for gx in range(int(ex // _GRID_CELL_PT) - reach, int(ex // _GRID_CELL_PT) + reach + 1):
            for gy in range(int(ey // _GRID_CELL_PT) - reach, int(ey // _GRID_CELL_PT) + reach + 1):
                for k2 in end_grid.get((gx, gy), ()):
                    if k2 <= k:
                        continue
                    r2, fx, fy, vx, vy = face_ends[k2]
                    if r2 == r:
                        continue
                    if abs(ux * vx + uy * vy + 1.0) > 0.02:
                        continue
                    if abs(thickness[r2] - thickness[r]) > MIN_FACE_OFFSET_PT:
                        continue
                    dx, dy = fx - ex, fy - ey
                    gap = dx * ux + dy * uy
                    if gap <= CONTACT_SLACK_PT or gap > max_gap:
                        continue
                    if abs(dx * -uy + dy * ux) > OPENING_GAP_COLLINEAR_TOL_PT:
                        continue
                    gap_pairs[(k, k2)] = (r, r2, gap, thickness[r])
    # Short gaps are accepted on one face. A wider gap is accepted only when the partner face of the same wall is
    # interrupted over the same interval: either its own gap ends line up with this one (to a point tolerance), or its
    # line is free of solid wall runs over the interval and has a face on each side of it (a jamb symbol or an end cap
    # can overhang a face end, so alignment to a point is not required).
    def _partner_gap_exists(key: Tuple[int, int]) -> bool:
        r, r2, gap, thick = gap_pairs[key]
        _, ex, ey, ux, uy = face_ends[key[0]]
        _, fx, fy, _, _ = face_ends[key[1]]
        nx, ny = -uy, ux
        for sign in (1.0, -1.0):
            tx, ty = sign * thick * nx, sign * thick * ny
            for other, (_, _, _, _) in gap_pairs.items():
                if other == key:
                    continue
                _, ox, oy, _, _ = face_ends[other[0]]
                _, px, py, _, _ = face_ends[other[1]]
                for (ax, ay, bx, by) in ((ox, oy, px, py), (px, py, ox, oy)):
                    if (math.hypot(ax - (ex + tx), ay - (ey + ty)) <= GAP_PARTNER_MATCH_TOL_PT
                            and math.hypot(bx - (fx + tx), by - (fy + ty)) <= GAP_PARTNER_MATCH_TOL_PT):
                        return True
        return False

    run_dirs: List[Tuple[float, float, float, float, float, float]] = []
    for other in runs:
        oa = _angle(other.p)
        run_dirs.append((math.cos(oa), math.sin(oa), other.p[0], other.p[1], other.p[2], other.p[3]))

    def _partner_line_interrupted(key: Tuple[int, int]) -> bool:
        """The partner face line (one reading of the wall thickness to either side) carries no solid wall run over the gap
        interval and has a face ending on each side of it. A jamb symbol may overhang a face end, so ends are matched
        within the face-gap bound and the interval is shortened by it instead of by a point tolerance."""
        r, r2, gap, thick = gap_pairs[key]
        _, ex, ey, ux, uy = face_ends[key[0]]
        nx, ny = -uy, ux
        tol = max(MIN_FACE_OFFSET_PT, 0.25 * thick)
        shrink = min(MAX_FACE_GAP_PT, 0.25 * gap)
        lo, hi = shrink, gap - shrink
        for sign in (1.0, -1.0):
            target = sign * thick
            left = right = blocked = False
            for q in range(len(runs)):
                if q == r or q == r2:
                    continue
                oux, ouy, ax, ay, bx, by = run_dirs[q]
                if abs(oux * ux + ouy * uy) < math.cos(ANGLE_TOL_RAD):
                    continue
                o1 = (ax - ex) * nx + (ay - ey) * ny
                o2 = (bx - ex) * nx + (by - ey) * ny
                if abs(o1 - target) > tol or abs(o2 - target) > tol:
                    continue
                t1 = (ax - ex) * ux + (ay - ey) * uy
                t2 = (bx - ex) * ux + (by - ey) * uy
                a, b = (t1, t2) if t1 <= t2 else (t2, t1)
                if min(b, hi) - max(a, lo) > 0.0:
                    blocked = True
                    break
                if a < lo and b >= -MAX_FACE_GAP_PT:
                    left = True
                if b > hi and a <= gap + MAX_FACE_GAP_PT:
                    right = True
            if not blocked and left and right:
                return True
        return False

    valid_gap_pairs: Dict[Tuple[int, int], Tuple[int, int, float, float]] = {}
    can_match = len(gap_pairs) <= MAX_GAP_CANDIDATES_FOR_PARTNER_MATCH
    for key in sorted(gap_pairs):
        r, r2, gap, thick = gap_pairs[key]
        if gap <= MAX_OPENING_GAP_FACTOR * thick or (
                can_match and (_partner_gap_exists(key) or _partner_line_interrupted(key))):
            valid_gap_pairs[key] = gap_pairs[key]
    gap_pairs = valid_gap_pairs
    for key in sorted(gap_pairs):
        r, r2, gap, thick = gap_pairs[key]
        if uf.find(r2) != uf.find(r):
            uf.union(r, r2)
            bridged.add(r)
            bridged.add(r2)

    def owner_of_end(r: int, ex: float, ey: float) -> str:
        best, best_d = None, None
        for m in runs[r].members:
            q = pts[m]
            for px, py in ((q[0], q[1]), (q[2], q[3])):
                d = math.hypot(px - ex, py - ey)
                if best_d is None or d < best_d or (d == best_d and ids[m] < ids[best]):
                    best, best_d = m, d
        return ids[best]

    gaps_found = []
    for (k, k2), (r, r2, gap, thick) in sorted(gap_pairs.items()):
        _, ex, ey, _, _ = face_ends[k]
        _, fx, fy, _, _ = face_ends[k2]
        gaps_found.append(OpeningGapCandidate(
            end_a=(round(ex, 4), round(ey, 4)), end_b=(round(fx, 4), round(fy, 4)),
            gap_length_pt=round(gap, 4), thickness_pt=round(thick, 4),
            source_primitive_id_a=owner_of_end(r, ex, ey), source_primitive_id_b=owner_of_end(r2, fx, fy)))
    gaps_found.sort(key=lambda g: (g.end_a, g.end_b))

    components: Dict[int, List[int]] = defaultdict(list)
    for r in paired_list:
        components[uf.find(r)].append(r)

    def comp_bbox(rs: Sequence[int]) -> Tuple[float, float, float, float]:
        xs = [v for r in rs for v in (runs[r].p[0], runs[r].p[2])]
        ys = [v for r in rs for v in (runs[r].p[1], runs[r].p[3])]
        return min(xs), min(ys), max(xs), max(ys)

    ordered = sorted(components.values(), key=lambda rs: (-sum(_length(runs[r].p) for r in rs), min(rs)))
    boxes = [comp_bbox(rs) for rs in ordered]

    def ring_like(rs: Sequence[int], box: Tuple[float, float, float, float]) -> bool:
        total = sum(_length(runs[r].p) for r in rs)
        if total <= 0:
            return False
        on_edge = 0.0
        for r in rs:
            p = runs[r].p
            horiz = abs(p[1] - p[3]) <= FRAME_RING_TOL_PT and (abs(p[1] - box[1]) <= FRAME_RING_TOL_PT or abs(p[1] - box[3]) <= FRAME_RING_TOL_PT)
            vert = abs(p[0] - p[2]) <= FRAME_RING_TOL_PT and (abs(p[0] - box[0]) <= FRAME_RING_TOL_PT or abs(p[0] - box[2]) <= FRAME_RING_TOL_PT)
            if horiz or vert:
                on_edge += _length(p)
        return on_edge / total >= FRAME_RING_FRACTION

    def table_grid_runs(rs: Sequence[int], box: Tuple[float, float, float, float]) -> List[int]:
        """Interior full-span parallel lines when the component is a pure ring around rule lines (a table or a grille).

        Pure ring: nearly all of the component's length runs along the sides of its own bounding box, within one face-gap bound
        of them (a frame drawn as a single stroke or as a pair of faces). Rows: at least ``TABLE_MIN_ROWS`` parallel lines inside
        the box, each spanning at least ``TABLE_ROW_SPAN_FRACTION`` of the box side, closer than ``TABLE_ROW_MIN_SEPARATION_PT``
        counted once (a double rule). Two full-span lines a wall thickness apart (within the face-gap bound but not a double rule)
        are the two faces of a partition: such a ring is a building, never a table. When the rows hold in one direction, the
        full-span lines of the other direction (column rules) belong too."""
        bx0, by0, bx1, by1 = box
        total = sum(_length(runs[r].p) for r in rs)
        if total <= 0:
            return []
        band = MAX_FACE_GAP_PT
        on_side = 0.0
        for r in rs:
            p = runs[r].p
            horiz = abs(p[1] - p[3]) <= FRAME_RING_TOL_PT and (abs(p[1] - by0) <= band or abs(p[1] - by1) <= band)
            vert = abs(p[0] - p[2]) <= FRAME_RING_TOL_PT and (abs(p[0] - bx0) <= band or abs(p[0] - bx1) <= band)
            if horiz or vert:
                on_side += _length(p)
        if on_side / total < TABLE_RING_FRACTION:
            return []
        own = set(rs)
        tol = FRAME_RING_TOL_PT
        rows: Dict[str, List[Tuple[float, int]]] = {"across": [], "down": []}
        for q, run in enumerate(runs):
            if q in own:
                continue
            p = run.p
            x_lo, x_hi = sorted((p[0], p[2]))
            y_lo, y_hi = sorted((p[1], p[3]))
            if x_lo < bx0 - tol or x_hi > bx1 + tol or y_lo < by0 - tol or y_hi > by1 + tol:
                continue
            if abs(p[1] - p[3]) <= tol and x_hi - x_lo >= TABLE_ROW_SPAN_FRACTION * (bx1 - bx0) and by0 + band < y_lo < by1 - band:
                rows["across"].append((p[1], q))
            elif abs(p[0] - p[2]) <= tol and y_hi - y_lo >= TABLE_ROW_SPAN_FRACTION * (by1 - by0) and bx0 + band < x_lo < bx1 - band:
                rows["down"].append((p[0], q))

        def distinct(lines: Sequence[Tuple[float, int]]) -> Tuple[int, bool]:
            """Rule lines counted once per double rule, and whether two of them stand a wall thickness apart."""
            count, last, wall_like = 0, None, False
            for offset in sorted(o for o, _ in lines):
                if last is None or offset - last >= TABLE_ROW_MIN_SEPARATION_PT:
                    count += 1
                    wall_like = wall_like or (last is not None and offset - last <= MAX_FACE_GAP_PT)
                last = offset
            return count, wall_like

        across, down = distinct(rows["across"]), distinct(rows["down"])
        if across[1] or down[1] or max(across[0], down[0]) < TABLE_MIN_ROWS:
            return []                  # a pair of full-span faces a wall thickness apart inside the ring is a wall, not a rule
        return sorted(q for lines in rows.values() for _, q in lines)

    def mark_table(rs: Sequence[int], grid: Sequence[int]) -> None:
        for r in list(rs) + list(grid):
            for m in runs[r].members:
                set_label(m, NOT_WALL_INK, REASON_RULED_RING)

    frame_idx: set = set()
    for k, rs in enumerate(ordered):
        bx0, by0, bx1, by1 = boxes[k]
        w, h = bx1 - bx0, by1 - by0
        sheet_scale = (max(w, h) >= FRAME_SHEET_FRACTION * page_max and min(w, h) >= FRAME_SHEET_FRACTION * page_min)
        ring_scale = (ring_like(rs, boxes[k]) and max(w, h) >= FRAME_SHEET_FRACTION * page_max
                      and min(w, h) >= FRAME_RING_MINOR_FRACTION * page_min)
        if sheet_scale or ring_scale:
            frame_idx.add(k)

    network_id = 0
    for k, rs in enumerate(ordered):
        member_ids = sorted(m for r in rs for m in runs[r].members)
        x0, y0, x1, y1 = boxes[k]
        major, minor = max(x1 - x0, y1 - y0), min(x1 - x0, y1 - y0)
        grid = [] if k in frame_idx else table_grid_runs(rs, boxes[k])
        if k in frame_idx:
            for m in member_ids:
                set_label(m, NOT_WALL_INK, REASON_SHEET_FRAME_RING)
        elif grid:
            mark_table(rs, grid)
        elif major >= NETWORK_MIN_MAJOR_FRACTION * page_min and minor >= NETWORK_MIN_MINOR_FRACTION * page_min:
            network_id += 1
            for r in rs:
                for m in runs[r].members:
                    set_label(m, WALL_NETWORK_INK_CANDIDATE, REASON_PAIRED_FACE_NETWORK)
                    if r in bridged:
                        reasons[m].append(REASON_CONTINUED_ACROSS_GAP)
                    net_of[m] = network_id
        else:
            for m in member_ids:
                set_label(m, UNPROVEN, REASON_SMALL_ISLAND)

    eligible_set = set(eligible)
    # A drawn wall piece is one small path (long faces plus end caps). End caps and any other short member follow the
    # long face that was proven, so a cap is never counted as a separate network.
    for key, members in paths.items():
        if len(members) > STRIP_MAX_SEGMENTS:
            continue
        positive = [m for m in members if label.get(m) == WALL_NETWORK_INK_CANDIDATE]
        if not positive:
            continue
        nid = net_of[positive[0]]
        for m in members:
            follows = (label.get(m) is None and m in eligible_set) or (
                label.get(m) == UNPROVEN and (REASON_NO_PARTNER in reasons[m] or REASON_BELOW_MIN_LENGTH in reasons[m]))
            if follows:
                label[m] = WALL_NETWORK_INK_CANDIDATE
                reasons[m] = [REASON_PAIRED_FACE_NETWORK]
                net_of[m] = nid

    # Walls drawn as ONE heavy line each: the heaviest dark stroke class whose own strokes form a building-scale
    # network. Ordinal on this page's own widths; frame-scale components are never candidates.
    stroke_classes: Dict[Tuple[Any, ...], List[int]] = defaultdict(list)
    for r, run in enumerate(runs):
        if run.ink_class[0] == "stroke":
            stroke_classes[run.ink_class].append(r)
    qualifying: List[Tuple[float, Tuple[Any, ...], List[List[int]]]] = []
    for klass in sorted(stroke_classes, key=repr):
        members = stroke_classes[klass]
        suf = _contact_union(runs, members)
        comps: Dict[int, List[int]] = defaultdict(list)
        for r in members:
            comps[suf.find(r)].append(r)
        areal = []
        for rs in comps.values():
            bx0, by0, bx1, by1 = comp_bbox(rs)
            w, h = bx1 - bx0, by1 - by0
            if (max(w, h) >= FRAME_SHEET_FRACTION * page_max and min(w, h) >= FRAME_SHEET_FRACTION * page_min) or (
                    ring_like(rs, (bx0, by0, bx1, by1)) and max(w, h) >= FRAME_SHEET_FRACTION * page_max
                    and min(w, h) >= FRAME_RING_MINOR_FRACTION * page_min):
                for r in rs:
                    for m in runs[r].members:
                        if label.get(m) in (None, UNPROVEN):
                            label[m] = NOT_WALL_INK
                            reasons[m] = [REASON_SHEET_FRAME_RING]
                continue
            grid = table_grid_runs(rs, (bx0, by0, bx1, by1))
            if grid:
                mark_table(rs, grid)
                continue
            if max(w, h) >= NETWORK_MIN_MAJOR_FRACTION * page_min and min(w, h) >= NETWORK_MIN_MINOR_FRACTION * page_min:
                areal.append(sorted(rs))
        if areal:
            qualifying.append((klass[1], klass, areal))
    if qualifying:
        qualifying.sort(key=lambda q: (-q[0], repr(q[1])))
        _, _, areal_components = qualifying[0]
        for rs in areal_components:
            fresh = [m for r in rs for m in runs[r].members if label.get(m) in (None, UNPROVEN)]
            if not fresh:
                continue
            network_id += 1
            for m in fresh:
                reasons[m] = [x for x in reasons[m] if x not in (REASON_NO_PARTNER, REASON_SMALL_ISLAND)]
                label[m] = WALL_NETWORK_INK_CANDIDATE
                reasons[m].append(REASON_HEAVIEST_SINGLE_STROKE_NETWORK)
                net_of[m] = network_id

    for i in eligible:
        if i not in label:
            set_label(i, UNPROVEN, REASON_NO_PARTNER)
    # ---- judge the deferred glyph-sized runs now that the networks are known ------------------------------------------
    if glyph_members:
        cand_cells: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for r, run in enumerate(runs):
            if not any(label.get(m) == WALL_NETWORK_INK_CANDIDATE for m in run.members):
                continue
            x0, x1 = sorted((run.p[0], run.p[2]))
            y0, y1 = sorted((run.p[1], run.p[3]))
            for gx in range(int(x0 // _CONTACT_CELL_PT) - 1, int(x1 // _CONTACT_CELL_PT) + 2):
                for gy in range(int(y0 // _CONTACT_CELL_PT) - 1, int(y1 // _CONTACT_CELL_PT) + 2):
                    cand_cells[(gx, gy)].append(r)

        def touches_network(m: int) -> bool:
            p = pts[m]
            x0, x1 = sorted((p[0], p[2]))
            y0, y1 = sorted((p[1], p[3]))
            width = (_num(segs[m].get("width")) or 0.0) if m in strokes else 0.0
            seen: set = set()
            for gx in range(int(x0 // _CONTACT_CELL_PT) - 1, int(x1 // _CONTACT_CELL_PT) + 2):
                for gy in range(int(y0 // _CONTACT_CELL_PT) - 1, int(y1 // _CONTACT_CELL_PT) + 2):
                    for r in cand_cells.get((gx, gy), ()):
                        if r in seen:
                            continue
                        seen.add(r)
                        if _segment_distance(p, runs[r].p) <= (width + runs[r].width) / 2 + CONTACT_SLACK_PT:
                            return True
            return False

        # Glyph-sized pieces that touch each other form one cluster (a door frame is several small touching pieces);
        # a cluster that reaches the wall network anywhere is attached as a whole.
        glyph_list = sorted(m for m in deferred_glyph if m in pts)
        guf = _UnionFind(glyph_list)
        gcells: Dict[Tuple[int, int], List[int]] = defaultdict(list)
        for m in glyph_list:
            x0, x1 = sorted((pts[m][0], pts[m][2]))
            y0, y1 = sorted((pts[m][1], pts[m][3]))
            for gx in range(int(x0 // _CONTACT_CELL_PT) - 1, int(x1 // _CONTACT_CELL_PT) + 2):
                for gy in range(int(y0 // _CONTACT_CELL_PT) - 1, int(y1 // _CONTACT_CELL_PT) + 2):
                    gcells[(gx, gy)].append(m)
        for cell in sorted(gcells):
            group = gcells[cell]
            for ia in range(len(group)):
                for ib in range(ia + 1, len(group)):
                    a, b = group[ia], group[ib]
                    if guf.find(a) == guf.find(b):
                        continue
                    wa = (_num(segs[a].get("width")) or 0.0) if a in strokes else 0.0
                    wb = (_num(segs[b].get("width")) or 0.0) if b in strokes else 0.0
                    if _segment_distance(pts[a], pts[b]) <= (wa + wb) / 2 + CONTACT_SLACK_PT:
                        guf.union(a, b)
        attached_roots = {guf.find(m) for m in glyph_list if touches_network(m)}
        for key, members in glyph_members.items():
            for m in members:
                if m in pts and guf.find(m) in attached_roots:
                    set_label(m, UNPROVEN, REASON_GLYPH_RUN_ATTACHED)
                else:
                    set_label(m, NOT_WALL_INK, REASON_OUTLINED_GLYPH_RUN)

    glyph_runs_found: List[GlyphSizedRun] = []
    for members in run_groups:
        boxes = [small[a] for a in members]
        member_segments = sorted({m for a in members for m in paths[small[a][0]]})
        heights = sorted(b[4] - b[2] for b in boxes)
        bottoms = sorted(b[4] for b in boxes)
        glyph_runs_found.append(GlyphSizedRun(
            bbox=(round(min(b[1] for b in boxes), 4), round(min(b[2] for b in boxes), 4),
                  round(max(b[3] for b in boxes), 4), round(max(b[4] for b in boxes), 4)),
            path_count=len(members), segment_count=len(member_segments),
            baseline_y_pt=round(bottoms[len(bottoms) // 2], 4), glyph_height_pt=round(heights[len(heights) // 2], 4),
            touches_wall_network=any(REASON_GLYPH_RUN_ATTACHED in reasons[m] for m in member_segments),
            source_primitive_ids=tuple(sorted(ids[m] for m in member_segments)),
        ))
    glyph_runs_found.sort(key=lambda g: (g.bbox[1], g.bbox[0], g.source_primitive_ids[:1]))

    decisions = tuple(
        StructuralInkDecision(ids[i], label.get(i, UNPROVEN), tuple(sorted(set(reasons[i]))) or (REASON_NO_GRAPHIC_STATE,),
                              cls_of.get(i), net_of.get(i))
        for i in range(n)
    )
    table: Dict[Tuple[Any, ...], List[float]] = defaultdict(lambda: [0, 0.0, 0])
    for i in range(n):
        if i in cls_of and i in pts:
            row = table[cls_of[i]]
            row[0] += 1
            row[1] += _length(pts[i])
            if label.get(i) == WALL_NETWORK_INK_CANDIDATE:
                row[2] += 1
    class_table = tuple(
        InkClassRow(k, int(v[0]), round(v[1], 3), int(v[2])) for k, v in sorted(table.items(), key=lambda kv: (-kv[1][1], repr(kv[0])))
    )
    return StructuralWallInkReport(decisions, class_table, network_id, darkest_color, (), tuple(gaps_found),
                                   tuple(glyph_runs_found))


def _make_run(members: List[int], pts: Mapping[int, Tuple[float, float, float, float]],
              segs: Sequence[Mapping[str, Any]], klass: Tuple[Any, ...], ux: float, uy: float) -> _Run:
    ts = []
    for i in members:
        p = pts[i]
        ts.append((p[0] * ux + p[1] * uy, p[0], p[1]))
        ts.append((p[2] * ux + p[3] * uy, p[2], p[3]))
    ts.sort()
    lo, hi = ts[0], ts[-1]
    width = (_num(segs[members[0]].get("width")) or 0.0) if klass[0] == "stroke" else 0.0
    return _Run(list(members), (lo[1], lo[2], hi[1], hi[2]), width, klass)
