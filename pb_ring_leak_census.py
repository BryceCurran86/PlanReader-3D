"""Read-only census of why wall rings do not close: the ink class of every unclosed raw wall gap, overlap groups of raw gaps, and
how many rings closing a chosen set of gaps would add.

Why this exists. Both ring builders (``pb_next_wall_ring_preview`` for the canonical preview and ``pb_layered_wall_doorway_room_ring_shadow``,
the one the room-face scope consumes) report ``unresolved_gap_count``, but that count covers collinear gaps only, says nothing about
whether a gap touches a ring, and never mentions the open ends that meet a perpendicular wall. A room whose perimeter leaks leaves no
trace in the result: no ring, no reason code, no gap list. This module reads what a builder produced (a ``BuilderCapture``, built by
``tools/diag_ring_leak_census.py`` from throwaway spies) and answers, from source ink geometry only:

* what is inside each unclosed gap (a ``classify_unclosed_gap_ink`` class and a length bucket);
* how many rings each closing set would add ("unblocking power"), recomputed from the builder's own barrier polygons and ring rule, with
  replication checks that must hold before any such figure is reported;
* which raw gaps are one aperture seen more than once (``aperture_groups``).

Nothing here is a wall, an opening, a closure, a host, a room, a quantity or a score. It changes no ring, closure, gate or builder; every
closing set is a measurement (the "every raw gap" figure is an upper bound and never a rule), and output carries counts, lengths and
offsets only, never coordinates, words or names.

The ink classes and the aperture overlap rule are DESCRIPTIVE: they feed no closure, strip or ring. The 10 pt and 140 pt buckets are the
builders' own face-identity band (``_stroke_closed``), pinned by a contract test, not tuned.
"""
from __future__ import annotations

import math
from collections import Counter
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Optional

from shapely.geometry import box

SCHEMA_VERSION = "1.0.0"

# The builders' own opening-sized band: ``_stroke_closed`` accepts face identity within 0.35 pt only for 10 pt <= span <= 140 pt.
OPENING_FLOOR_PT = 10.0
OPENING_CEILING_PT = 140.0
# Descriptive census cuts (no closure, strip or ring reads them).
SPAN_FRACTION = 0.6
AXIS_TOLERANCE_PT = 0.12
END_INSET_PT = 0.5
WITNESS_MIN_ALONG_PT = 1.0
OVERLAP_EPSILON_PT = 1e-6
# A single closure "encloses new space" when the total enclosed area grows by more than this (pt squared); otherwise it only splits.
NEW_SPACE_AREA_EPSILON_PT2 = 1e-6

CLASS_COMPETING_OWNERS = "competing_owners"
CLASS_DOOR_WITNESS = "source_door_witness_in_gap"
CLASS_ARC_UNPLACED = "native_arc_swing_not_placed"
CLASS_PARALLEL_MANY = "parallel_strokes_2plus"
CLASS_PARTIAL_STROKE = "one_partial_spanning_stroke"
CLASS_PERPENDICULAR = "perpendicular_strokes"
CLASS_OTHER_INK = "other_ink_only"
CLASS_EMPTY = "empty"
CLASSES = (
    CLASS_COMPETING_OWNERS, CLASS_DOOR_WITNESS, CLASS_ARC_UNPLACED, CLASS_PARALLEL_MANY, CLASS_PARTIAL_STROKE,
    CLASS_PERPENDICULAR, CLASS_OTHER_INK, CLASS_EMPTY,
)
BUCKET_SHORT = "lt10"
BUCKET_OPENING = "10to140"
BUCKET_LONG = "gt140"

EFFECT_NEW_SPACE = "encloses_new_space"
EFFECT_SPLIT = "splits_an_enclosed_ring"
EFFECT_REMOVES = "removes_a_ring"
EFFECT_NONE = "adds_no_ring"

BUILDER_PREVIEW_FORK = "preview_fork"
BUILDER_LAYERED = "layered"
# The reason code both builders put on a ring that an unresolved collinear gap holds open (pinned against both modules by a test).
REASON_OPEN_GAP = "open_wall_gap_unresolved"


class CensusInputError(ValueError):
    """A gap, capture or row is malformed; the census refuses instead of guessing."""


# ------------------------------------------------------------------------------------------------ gaps and rows

@dataclass(frozen=True)
class PlainGap:
    """One raw wall gap, as plain numbers: an interruption of a wall band between ``lo`` and ``hi`` along the band."""
    horizontal: bool
    band: tuple[float, float]
    lo: float
    hi: float
    collinear: bool
    left_path_indices: tuple[int, ...] = ()
    right_path_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        values = (*self.band, self.lo, self.hi)
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values):
            raise CensusInputError("gap numbers must be finite")
        if not self.hi > self.lo:
            raise CensusInputError("gap hi must be greater than lo")
        if not self.band[1] > self.band[0]:
            raise CensusInputError("gap band must be ordered and non-empty")
        if type(self.horizontal) is not bool or type(self.collinear) is not bool:
            raise CensusInputError("horizontal and collinear must be explicit booleans")

    @property
    def length(self) -> float:
        return self.hi - self.lo

    @property
    def thickness(self) -> float:
        return self.band[1] - self.band[0]

    def rect(self):
        if self.horizontal:
            return box(self.lo, self.band[0], self.hi, self.band[1])
        return box(self.band[0], self.lo, self.band[1], self.hi)


def plain_gap(gap: Any) -> PlainGap:
    """Copy any builder ``_Gap`` (or look-alike) into a ``PlainGap``."""
    return PlainGap(
        horizontal=bool(gap.horizontal), band=(float(gap.band[0]), float(gap.band[1])), lo=float(gap.lo), hi=float(gap.hi),
        collinear=bool(gap.collinear), left_path_indices=tuple(int(i) for i in gap.left_path_indices),
        right_path_indices=tuple(int(i) for i in gap.right_path_indices),
    )


def length_bucket(length: float) -> str:
    """``lt10`` (under the builders' opening floor), ``10to140`` (opening sized) or ``gt140``."""
    if length < OPENING_FLOOR_PT:
        return BUCKET_SHORT
    if length <= OPENING_CEILING_PT:
        return BUCKET_OPENING
    return BUCKET_LONG


def _xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x") and hasattr(point, "y"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def item_bbox(item: Sequence[Any]) -> Optional[tuple[float, float, float, float]]:
    """Bounding box of one native drawing item, mirroring the builders: lines and curves by their points, ``re`` by its rectangle,
    ``qu`` only when it is an axis-aligned rectangle; anything else has none."""
    kind = item[0] if item else None
    if kind == "l" and len(item) >= 3:
        (ax, ay), (bx, by) = _xy(item[1]), _xy(item[2])
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)
    if kind == "re" and len(item) >= 2:
        r = item[1]
        if hasattr(r, "x0"):
            return float(r.x0), float(r.y0), float(r.x1), float(r.y1)
        return float(r[0]), float(r[1]), float(r[2]), float(r[3])
    if kind == "qu" and len(item) >= 2:
        q = item[1]
        pts = [_xy(q.ul), _xy(q.ur), _xy(q.lr), _xy(q.ll)]
        xs = sorted({round(p[0], 6) for p in pts})
        ys = sorted({round(p[1], 6) for p in pts})
        if len(xs) != 2 or len(ys) != 2:
            return None
        return xs[0], ys[0], xs[1], ys[1]
    if kind == "c" and len(item) >= 5:
        pts = [_xy(item[i]) for i in range(1, 5)]
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        return min(xs), min(ys), max(xs), max(ys)
    return None


def _overlaps(b: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
    ox = min(b[2], inner[2]) - max(b[0], inner[0])
    oy = min(b[3], inner[3]) - max(b[1], inner[1])
    return ox >= -OVERLAP_EPSILON_PT and oy >= -OVERLAP_EPSILON_PT and (ox > OVERLAP_EPSILON_PT or oy > OVERLAP_EPSILON_PT)


class InkIndex:
    """Every drawing item of the page rows, read once: row index, kind, bounding box and, for lines, both endpoints.

    ``rows`` are the indexed rows a builder read (inert ``None``/empty placeholders are skipped; indices are preserved). The rows are
    never mutated."""
    __slots__ = ("_rows",)

    def __init__(self, rows: Sequence[Any]) -> None:
        built: list[tuple[int, bool, tuple[tuple[Any, tuple[float, float, float, float], Any], ...]]] = []
        for row_index, row in enumerate(rows):
            if not isinstance(row, Mapping):
                continue
            filled = row.get("fill") is not None
            entries = []
            for item in row.get("items") or ():
                bbox = item_bbox(item)
                if bbox is None:
                    continue
                kind = item[0]
                ends = (_xy(item[1]), _xy(item[2])) if kind == "l" else None
                entries.append((kind, bbox, ends))
            if entries:
                built.append((row_index, filled, tuple(entries)))
        self._rows = tuple(built)

    def profile(self, gap: PlainGap, own_rows: frozenset[int] = frozenset()) -> tuple[dict[str, int], list[tuple[float, float]]]:
        """Counts of drawing ROWS that put ink inside the gap rectangle (inflated by one wall thickness across, shrunk by 0.5 pt at the
        ends), excluding ``own_rows`` (the strips that bound the gap): ``curve``, ``parallel`` (a stroke parallel to the gap spanning
        at least 60 percent of it), ``perpendicular``, ``fill`` and ``other``; and the along-extents of the parallel strokes."""
        length, thickness = gap.length, gap.thickness
        if gap.horizontal:
            inner = (gap.lo + END_INSET_PT, gap.band[0] - thickness, gap.hi - END_INSET_PT, gap.band[1] + thickness)
        else:
            inner = (gap.band[0] - thickness, gap.lo + END_INSET_PT, gap.band[1] + thickness, gap.hi - END_INSET_PT)
        counts = {"curve": 0, "parallel": 0, "perpendicular": 0, "fill": 0, "other": 0}
        spans: list[tuple[float, float]] = []
        for row_index, filled, entries in self._rows:
            if row_index in own_rows:
                continue
            hits: set[str] = set()
            row_spans: list[tuple[float, float]] = []
            for kind, bbox, ends in entries:
                if not _overlaps(bbox, inner):
                    continue
                if kind == "c":
                    hits.add("curve")
                elif kind == "l":
                    (ax, ay), (bx, by) = ends
                    along = abs(ax - bx) if gap.horizontal else abs(ay - by)
                    across = abs(ay - by) if gap.horizontal else abs(ax - bx)
                    if across <= AXIS_TOLERANCE_PT and along >= SPAN_FRACTION * length:
                        hits.add("parallel")
                        row_spans.append(tuple(sorted((ax, bx) if gap.horizontal else (ay, by))))  # type: ignore[arg-type]
                    elif along <= AXIS_TOLERANCE_PT and across >= 0.5 * thickness:
                        hits.add("perpendicular")
                    else:
                        hits.add("other")
                else:
                    hits.add("other")  # a rectangle or quad; a filled row is folded into "fill" below
            if filled and hits:
                hits = {"fill"}
            for name in hits:
                counts[name] += 1
            if "parallel" in hits:
                spans.extend(row_spans)
        return counts, spans


def classify_unclosed_gap_ink(
    rows: Sequence[Any] | InkIndex, gap: PlainGap, *, owners: Sequence[str] = (), door_witnesses: int = 0, native_arcs: int = 0,
) -> dict[str, Any]:
    """What is inside one unclosed gap, from source ink geometry only.

    The class is decided in this order: ``competing_owners`` (two or more of the builder's own closure evidence functions fire, so
    neither is chosen), ``source_door_witness_in_gap`` (a segmented source door swing lies in the gap), ``native_arc_swing_not_placed``
    (a native arc swing lies in an unclosed gap), ``parallel_strokes_2plus`` (two or more strokes parallel to the gap each spanning at
    least 60 percent of it), ``one_partial_spanning_stroke`` (exactly one), ``perpendicular_strokes`` (no such parallel stroke and at
    least one stroke across the band; other ink may also be present), ``other_ink_only`` (arcs, fills or oblique lines), ``empty``.
    A class is a description, never a basis for closing the gap."""
    if not isinstance(gap, PlainGap):
        raise CensusInputError("gap must be a PlainGap")
    index = rows if isinstance(rows, InkIndex) else InkIndex(rows)
    own = frozenset(gap.left_path_indices) | frozenset(gap.right_path_indices)
    counts, spans = index.profile(gap, own)
    owners = tuple(owners)
    if len(owners) > 1:
        klass = CLASS_COMPETING_OWNERS
    elif door_witnesses:
        klass = CLASS_DOOR_WITNESS
    elif native_arcs:
        klass = CLASS_ARC_UNPLACED
    elif counts["parallel"] >= 2:
        klass = CLASS_PARALLEL_MANY
    elif counts["parallel"]:
        klass = CLASS_PARTIAL_STROKE
    elif counts["perpendicular"]:
        klass = CLASS_PERPENDICULAR
    elif counts["curve"] or counts["fill"] or counts["other"]:
        klass = CLASS_OTHER_INK
    else:
        klass = CLASS_EMPTY
    best_end_miss: Optional[tuple[float, float]] = None
    if spans:
        lo, hi = max(spans, key=lambda s: (s[1] - s[0], -s[0]))
        best_end_miss = (round(lo - gap.lo, 4), round(gap.hi - hi, 4))  # positive: the stroke stops short of that end
    return {
        "class": klass,
        "bucket": length_bucket(gap.length),
        "length_pt": round(gap.length, 4),
        "thickness_pt": round(gap.thickness, 4),
        "ink_rows": counts,
        "owners": list(owners),
        "door_witnesses": int(door_witnesses),
        "native_arcs": int(native_arcs),
        "best_parallel_end_miss_pt": None if best_end_miss is None else list(best_end_miss),
    }


# ------------------------------------------------------------------------------------------------ door evidence in a gap

def _segment_in_gap(a: Sequence[float], b: Sequence[float], gap: PlainGap, *, perp_from_mean: bool) -> bool:
    axis = 0 if gap.horizontal else 1
    perp = (a[1 - axis] + b[1 - axis]) / 2 if perp_from_mean else a[1 - axis]
    lo, hi = sorted((a[axis], b[axis]))
    thickness = gap.thickness
    return gap.band[0] - thickness <= perp <= gap.band[1] + thickness and gap.lo - 0.05 <= lo and hi <= gap.hi + 0.05


def arc_in_gap(arc: Mapping[str, Any], gap: PlainGap) -> bool:
    """A native arc swing whose centre and closed tip lie on the gap's line (within 0.05 pt) and inside its interval."""
    centre, tip = arc["centre"], arc["closed_tip"]
    axis = 0 if gap.horizontal else 1
    if abs(centre[1 - axis] - tip[1 - axis]) > 0.05:
        return False
    return _segment_in_gap(centre, tip, gap, perp_from_mean=False)


def witness_in_gap(witness: Mapping[str, Any], gap: PlainGap) -> bool:
    """A segmented source door swing (hinge point to closed leaf tip) on the gap's line (within 0.12 pt) and inside its interval."""
    a, b = witness["centre"], witness["closed_tip"]
    axis = 0 if gap.horizontal else 1
    if abs(a[1 - axis] - b[1 - axis]) > AXIS_TOLERANCE_PT or abs(a[axis] - b[axis]) <= WITNESS_MIN_ALONG_PT:
        return False
    return _segment_in_gap(a, b, gap, perp_from_mean=True)


# ------------------------------------------------------------------------------------------------ apertures

def gaps_overlap(a: PlainGap, b: PlainGap) -> bool:
    """Two raw gaps on one line whose band AND interval both overlap by more than zero are one aperture seen twice."""
    if a.horizontal != b.horizontal:
        return False
    if min(a.band[1], b.band[1]) - max(a.band[0], b.band[0]) <= 0:
        return False
    return min(a.hi, b.hi) - max(a.lo, b.lo) > 0


def aperture_groups(gaps: Sequence[PlainGap]) -> tuple[tuple[int, ...], ...]:
    """Overlap components of the raw gaps: each group's indices ascending, the groups ordered by their first index. Order-independent
    in content (the same gaps in any order give the same groups of the same gaps)."""
    parent = list(range(len(gaps)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(gaps)):
        for j in range(i + 1, len(gaps)):
            if gaps_overlap(gaps[i], gaps[j]):
                root_i, root_j = find(i), find(j)
                if root_i != root_j:
                    parent[max(root_i, root_j)] = min(root_i, root_j)
    groups: dict[int, list[int]] = {}
    for i in range(len(gaps)):
        groups.setdefault(find(i), []).append(i)
    return tuple(tuple(members) for _root, members in sorted(groups.items()))


# ------------------------------------------------------------------------------------------------ rings and the capture

@dataclass(frozen=True)
class RingRule:
    """How a builder turns a free part of the page into a ring (the census's model of it; the replication check guards it).

    A part is dropped when it is noise, when insetting it by ``sliver_inset_factor`` median strip thicknesses leaves nothing (a
    sliver), when both its bounding-box extents are under ``min_extent_factor`` thicknesses (a wall cavity; ``None`` = no such
    test), or when it touches the domain boundary (the exterior)."""
    sliver_inset_factor: float
    min_extent_factor: Optional[float] = None


PREVIEW_RING_RULE = RingRule(sliver_inset_factor=0.5, min_extent_factor=None)
LAYERED_RING_RULE = RingRule(sliver_inset_factor=1.0, min_extent_factor=6.0)


@dataclass(frozen=True)
class BuilderRing:
    status: str
    reason_codes: tuple[str, ...]
    polygon: Any  # shapely Polygon in page points


@dataclass(frozen=True)
class ArcInfo:
    """Native arc swing outcomes: what the finder returned and rejected, what the builder's own placement reported, and per arc how
    many raw gaps are candidates for it (none, one or several)."""
    found: int
    rejected_by_finder: int
    builder_unplaced: int
    builder_ambiguous: int
    candidate_gap_indices: tuple[tuple[int, ...], ...]


@dataclass(frozen=True)
class BuilderCapture:
    """Everything the census needs from one builder run. Built by ``tools/diag_ring_leak_census.py``; hand-built in tests.

    ``barrier`` is the builder's own finished barrier and ``barrier_inputs`` the polygons it united (strips, fills and its closing
    rectangles): a what-if that closes more gaps re-runs ``closed_union`` on exactly those polygons plus the extra rectangles, the way the
    builder would have if those gaps had closed. Without ``barrier_inputs`` the finished barrier is re-closed with the rectangles."""
    builder: str
    status: str
    reason_codes: tuple[str, ...]
    rows: Sequence[Any]
    gaps: Sequence[PlainGap]
    closed: Sequence[bool]
    barrier: Any
    domain: Any
    median_thickness: float
    ring_rule: RingRule
    noise_pt: float
    closure_rect: Callable[[PlainGap], Any]
    closed_union: Callable[[Iterable[Any]], Any]
    polygon_parts: Callable[[Any], list]
    ring_touch: Callable[[Any, int], bool]
    builder_strip_count: int
    builder_gap_count: int
    builder_closure_count: int
    builder_unresolved_collinear: int
    builder_rings: Sequence[BuilderRing]
    owner_evidence: Optional[Callable[[int], tuple[str, ...]]] = None
    native_arcs: Sequence[Mapping[str, Any]] = ()
    door_witnesses: Sequence[Mapping[str, Any]] = ()
    arc_info: Optional[ArcInfo] = None
    barrier_inputs: Sequence[Any] = ()

    def __post_init__(self) -> None:
        if len(self.gaps) != len(self.closed):
            raise CensusInputError("closed must have one flag per gap")
        if not all(isinstance(g, PlainGap) for g in self.gaps):
            raise CensusInputError("gaps must be PlainGap records")


def ring_parts(capture: BuilderCapture, extra: Sequence[Any] = ()) -> list[Any]:
    """The free-space parts that are rings once ``extra`` rectangles are added to the builder's barrier, by the builder's own ring rule."""
    if not extra:
        geometry = capture.barrier
    elif capture.barrier_inputs:
        geometry = capture.closed_union([*capture.barrier_inputs, *extra])
    else:
        geometry = capture.closed_union([capture.barrier, *extra])
    free = capture.domain.difference(geometry)
    exterior = capture.domain.boundary.buffer(capture.noise_pt)
    rule, median = capture.ring_rule, capture.median_thickness
    parts = []
    for part in capture.polygon_parts(free):
        if part.area <= capture.noise_pt * capture.noise_pt:
            continue
        if part.buffer(-rule.sliver_inset_factor * median, join_style=2).is_empty:
            continue
        if rule.min_extent_factor is not None:
            minx, miny, maxx, maxy = part.bounds
            if (maxx - minx) < rule.min_extent_factor * median and (maxy - miny) < rule.min_extent_factor * median:
                continue
        if part.boundary.intersects(exterior):
            continue
        parts.append(part)
    return parts


def count_rings(capture: BuilderCapture, extra: Sequence[Any] = ()) -> int:
    """How many rings there are once ``extra`` rectangles are added to the builder's barrier (see ``ring_parts``)."""
    return len(ring_parts(capture, extra))


def single_closure_effect(ring_gain: int, area_gain: float) -> str:
    """What closing one more gap does: it adds a ring that ENCLOSES NEW SPACE (the space was open to the exterior before), adds a ring by
    SPLITTING an enclosed ring (the closing rectangle covers part of it, so the enclosed area does not grow), removes one, or adds none."""
    if ring_gain > 0:
        return EFFECT_NEW_SPACE if area_gain > NEW_SPACE_AREA_EPSILON_PT2 else EFFECT_SPLIT
    return EFFECT_REMOVES if ring_gain < 0 else EFFECT_NONE


def _ring_label(ring: BuilderRing) -> str:
    return f"{ring.status}|{'+'.join(ring.reason_codes)}"


def _tally(counter: Counter) -> dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _collinear_label(gap: PlainGap) -> str:
    return "collinear" if gap.collinear else "non_collinear"


def _arc_section(capture: BuilderCapture) -> Optional[dict[str, Any]]:
    info = capture.arc_info
    if info is None:
        return None
    per_arc: Counter = Counter()
    shape: Counter = Counter()
    kinds: Counter = Counter()
    for candidates in info.candidate_gap_indices:
        if not candidates:
            per_arc["no_candidate_gap"] += 1
        elif len(candidates) == 1:
            per_arc["one_candidate_gap"] += 1
        else:
            per_arc["several_candidate_gaps"] += 1
            kinds["+".join(sorted(_collinear_label(capture.gaps[i]) for i in candidates))] += 1
            pairs = [(a, b) for k, a in enumerate(candidates) for b in candidates[k + 1:]]
            overlap = all(gaps_overlap(capture.gaps[a], capture.gaps[b]) for a, b in pairs)
            shape["all_pairs_overlap_one_aperture" if overlap else "different_apertures"] += 1
    return {
        "found": info.found, "rejected_by_finder": info.rejected_by_finder,
        "builder_unplaced": info.builder_unplaced, "builder_ambiguous": info.builder_ambiguous,
        "per_arc_candidate_gaps": _tally(per_arc), "several_candidate_kinds": _tally(kinds), "several_candidate_shape": _tally(shape),
    }


def census_report(capture: BuilderCapture, *, per_gap: bool = False, unblocking: bool = True) -> dict[str, Any]:
    """The counts-only census of one builder run (see the module docstring). ``per_gap`` adds one record per unclosed gap (indices into
    the builder's gap list, lengths and counts, no coordinates). ``unblocking=False`` skips the ring recomputations."""
    gaps = capture.gaps
    closed = [bool(flag) for flag in capture.closed]
    index = InkIndex(capture.rows)
    unclosed = [i for i in range(len(gaps)) if not closed[i]]
    unresolved_collinear = [i for i in unclosed if gaps[i].collinear]

    records: dict[int, dict[str, Any]] = {}
    for i in unclosed:
        gap = gaps[i]
        owners = capture.owner_evidence(i) if capture.owner_evidence is not None else ()
        records[i] = classify_unclosed_gap_ink(
            index, gap, owners=owners,
            door_witnesses=sum(1 for w in capture.door_witnesses if witness_in_gap(w, gap)),
            native_arcs=sum(1 for a in capture.native_arcs if arc_in_gap(a, gap)),
        )

    rings_by_label = Counter(_ring_label(r) for r in capture.builder_rings)
    touched = {i: [k for k, ring in enumerate(capture.builder_rings) if capture.ring_touch(ring.polygon, i)] for i in unclosed}
    open_gap_rings = [k for k, ring in enumerate(capture.builder_rings) if ring.status == "abstained" and REASON_OPEN_GAP in ring.reason_codes]
    held_open = []
    for k in open_gap_rings:
        leaking = [i for i in unclosed if k in touched[i]]
        held_open.append({"leaking_gaps": len(leaking), "classes": sorted({records[i]["class"] for i in leaking})})
    held_open.sort(key=lambda h: (h["leaking_gaps"], h["classes"]))

    rings_recomputed = count_rings(capture)
    replication = {
        "unresolved_collinear": {"census": len(unresolved_collinear), "builder": capture.builder_unresolved_collinear,
                                 "match": len(unresolved_collinear) == capture.builder_unresolved_collinear},
        "closed": {"census": sum(closed), "builder": capture.builder_closure_count, "match": sum(closed) == capture.builder_closure_count},
        "rings": {"recomputed": rings_recomputed, "builder": len(capture.builder_rings), "match": rings_recomputed == len(capture.builder_rings)},
    }
    replication["exact"] = all(replication[k]["match"] for k in ("unresolved_collinear", "closed", "rings"))

    by_class = Counter(records[i]["class"] for i in unclosed)
    unclosed_section = {
        "count": len(unclosed), "collinear": len(unresolved_collinear), "non_collinear": len(unclosed) - len(unresolved_collinear),
        "by_orientation_and_class": _tally(Counter(f"{_collinear_label(gaps[i])}|{records[i]['class']}" for i in unclosed)),
        "by_class": _tally(by_class),
        "by_class_and_bucket": _tally(Counter(f"{records[i]['class']}|{records[i]['bucket']}" for i in unclosed)),
        "unresolved_collinear_by_class": _tally(Counter(records[i]["class"] for i in unresolved_collinear)),
        "unresolved_collinear_by_bucket": _tally(Counter(records[i]["bucket"] for i in unresolved_collinear)),
        "owner_sets": _tally(Counter("+".join(records[i]["owners"]) or "none" for i in unclosed)),
        "touching_no_ring": sum(1 for i in unclosed if not touched[i]),
        "touching_an_abstained_ring": sum(1 for i in unclosed if any(capture.builder_rings[k].status == "abstained" for k in touched[i])),
        "held_open_rings": held_open,
    }

    groups = aperture_groups(gaps)
    group_of = {i: g for g, members in enumerate(groups) for i in members}
    multi = [m for m in groups if len(m) > 1]
    group_has_closed = [any(closed[i] for i in members) for members in groups]

    single_gain: dict[int, int] = {}
    single_effect: dict[int, str] = {}
    unblock: Optional[dict[str, Any]] = None
    if unblocking and replication["rings"]["match"]:
        rect = {i: capture.closure_rect(gaps[i]) for i in unclosed}
        class_sets: dict[str, list[int]] = {}
        for i in unclosed:
            class_sets.setdefault(records[i]["class"], []).append(i)
        now_area = sum(part.area for part in ring_parts(capture))
        for i in unclosed:
            parts = ring_parts(capture, [rect[i]])
            single_gain[i] = len(parts) - rings_recomputed
            single_effect[i] = single_closure_effect(single_gain[i], sum(part.area for part in parts) - now_area)
        adders = [i for i in unclosed if single_gain[i] > 0]
        unblock = {
            "rings_now": len(capture.builder_rings),
            "rings_recomputed": rings_recomputed,
            "if_all_unresolved_collinear_closed": count_rings(capture, [rect[i] for i in unresolved_collinear]) if unresolved_collinear else rings_recomputed,
            "if_all_opening_sized_unresolved_closed": count_rings(capture, [rect[i] for i in unclosed if records[i]["bucket"] == BUCKET_OPENING]),
            "if_every_unclosed_raw_gap_closed_UPPER_BOUND_NOT_A_RULE": count_rings(capture, [rect[i] for i in unclosed]) if unclosed else rings_recomputed,
            "if_all_unclosed_of_one_class_closed": {k: count_rings(capture, [rect[i] for i in members]) for k, members in sorted(class_sets.items())},
            "single_closure": {
                "gaps_adding_a_ring": len(adders),
                "adding_by_orientation_and_class": _tally(Counter(f"{_collinear_label(gaps[i])}|{records[i]['class']}" for i in adders)),
                "adding_by_bucket": _tally(Counter(records[i]["bucket"] for i in adders)),
                "adding_by_effect": _tally(Counter(single_effect[i] for i in adders)),
                "adding_by_orientation_and_effect": _tally(Counter(f"{_collinear_label(gaps[i])}|{single_effect[i]}" for i in adders)),
                "adding_with_door_evidence": sum(1 for i in adders if records[i]["door_witnesses"] or records[i]["native_arcs"]),
                "gaps_removing_a_ring": sum(1 for i in unclosed if single_gain[i] < 0),
            },
        }
    adders_all = [i for i, gain in single_gain.items() if gain > 0]
    new_space = [i for i in adders_all if single_effect[i] == EFFECT_NEW_SPACE]
    apertures = {
        "raw_gaps": len(gaps), "groups": len(groups), "groups_with_two_or_more_gaps": len(multi),
        "gaps_in_such_groups": sum(len(m) for m in multi), "largest_group": max((len(m) for m in groups), default=0),
        "groups_with_a_closed_gap": sum(1 for flag in group_has_closed if flag),
        "unclosed_gaps_sharing_a_group_with_a_closed_gap": sum(1 for i in unclosed if group_has_closed[group_of[i]]),
        "unresolved_collinear_sharing_a_group_with_a_closed_gap": sum(1 for i in unresolved_collinear if group_has_closed[group_of[i]]),
        "ring_adding_gaps": len(adders_all) if unblock is not None else None,
        "ring_adding_distinct_groups": len({group_of[i] for i in adders_all}) if unblock is not None else None,
        "ring_adding_gaps_in_multi_gap_groups": sum(1 for i in adders_all if len(groups[group_of[i]]) > 1) if unblock is not None else None,
        "new_space_gaps": len(new_space) if unblock is not None else None,
        "new_space_distinct_groups": len({group_of[i] for i in new_space}) if unblock is not None else None,
    }

    partial = sorted(
        (records[i]["best_parallel_end_miss_pt"][0], records[i]["best_parallel_end_miss_pt"][1], records[i]["length_pt"])
        for i in unclosed if records[i]["class"] == CLASS_PARTIAL_STROKE and records[i]["best_parallel_end_miss_pt"] is not None
    )
    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "builder": capture.builder,
        "builder_status": capture.status,
        "builder_reason_codes": list(capture.reason_codes),
        "counts": {
            "strips": capture.builder_strip_count, "raw_gaps": len(gaps), "raw_gaps_builder": capture.builder_gap_count,
            "raw_gaps_collinear": sum(1 for g in gaps if g.collinear), "raw_gaps_non_collinear": sum(1 for g in gaps if not g.collinear),
            "closed": sum(closed), "rings": len(capture.builder_rings), "rings_by_status_and_reason": _tally(rings_by_label),
        },
        "replication": replication,
        "unclosed_gaps": unclosed_section,
        "unblocking_power": unblock,
        "unblocking_power_withheld": None if unblock is not None or not unblocking else "ring_count_replication_not_exact",
        "apertures": apertures,
        "native_arcs": _arc_section(capture),
        "partial_stroke_end_misses_pt": [{"miss_lo": m[0], "miss_hi": m[1], "gap_length": m[2]} for m in partial],
        "descriptive_cuts": {"span_fraction": SPAN_FRACTION, "axis_tolerance_pt": AXIS_TOLERANCE_PT, "end_inset_pt": END_INSET_PT,
                             "bucket_floor_pt": OPENING_FLOOR_PT, "bucket_ceiling_pt": OPENING_CEILING_PT},
    }
    if per_gap:
        report["gap_records"] = [
            {
                "index": i, "orientation": "horizontal" if gaps[i].horizontal else "vertical", "collinear": gaps[i].collinear,
                **{k: records[i][k] for k in ("class", "bucket", "length_pt", "thickness_pt", "owners", "door_witnesses", "native_arcs", "ink_rows")},
                "rings_touched": len(touched[i]),
                "single_closure_ring_gain": single_gain.get(i),
                "single_closure_effect": single_effect.get(i),
                "aperture_group_size": len(groups[group_of[i]]),
            }
            for i in unclosed
        ]
    return report


__all__ = [
    "BUCKET_LONG", "BUCKET_OPENING", "BUCKET_SHORT", "BUILDER_LAYERED", "BUILDER_PREVIEW_FORK", "CLASSES", "REASON_OPEN_GAP", "ArcInfo",
    "BuilderCapture", "BuilderRing", "CensusInputError", "EFFECT_NEW_SPACE", "EFFECT_NONE", "EFFECT_REMOVES", "EFFECT_SPLIT", "InkIndex", "LAYERED_RING_RULE", "PREVIEW_RING_RULE", "PlainGap", "RingRule",
    "SCHEMA_VERSION", "aperture_groups", "arc_in_gap", "census_report", "classify_unclosed_gap_ink", "count_rings", "gaps_overlap",
    "item_bbox", "length_bucket", "plain_gap", "ring_parts", "single_closure_effect", "witness_in_gap",
]
