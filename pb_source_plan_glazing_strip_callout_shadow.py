"""Source-owned plan callout -> glazing strip correspondence, strictly SHADOW.

Question answered: for a window tag printed on a plan page inside a closed callout
ring (no leader to the window), which glazing strip on that same page is a
source-corroborated candidate for it, and which rivals remain?

Nothing here is authority. The receipt grants no physical opening, host, opening
kind, frame, scale, metric, count, quantity or customer output; every grant flag is
False and enforced at construction. The module is a pure function over records the
existing producers already own (visible ink, trusted native words, elevation
type-frame records); `audit_plan_callout_to_glazing_strip_from_source` is the only
place that touches a `SourceVisibilityProducer`, and it re-opens nothing except the
producer's own revision bytes for facts the producer does not expose (page rotation,
stroke width and colour of the producer's own primitives).

How a correspondence is earned, all tri-state (passed / failed / not_evaluated; any
condition that is not `passed` forbids CANDIDATE):

* the strip inventory is page wide and independent of every callout;
* the elevation panel count must equal the strip's panel count, and at least two
  window types must agree on one common plan/elevation ratio within a tolerance built
  only from the drawing's own coordinate and dimension-print quanta. No scale leaves
  this module and no absolute mm-per-point is computed from it; the agreement is a
  dimensionless cross-window consistency check;
* location is a necessary filter that can only remove a candidate (the six ring
  vertices must lie within the strip's along-extent and on one side of its band); it
  never selects, ranks or breaks a tie;
* exclusivity runs over every callout ring found on the page, not over the tags a
  caller asked about; any second claimant retains everything as CONFLICT.

Single-panel strips are fingerprint-unmeasurable here (the count carries no
information and the length test alone is not discriminating), so they abstain.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, fields, replace
from typing import Callable, Iterable, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_tag_normalization import normalize_opening_tag

PLAN_CALLOUT_STRIP_SHADOW_SCHEMA_VERSION = "2.3.0"
PRODUCER_INPUT_PROVENANCE = "source_visibility_producer"
WHOLE_PAGE_UNSEGMENTED = "whole_page_unsegmented"

PASSED = "passed"
FAILED = "failed"
NOT_EVALUATED = "not_evaluated"

CONDITION_NAMES = (
    "tag_unique_on_plan_page",
    "callout_ring_unique",
    "callout_in_one_resolved_plan_viewport",
    "elevation_type_record_unique",
    "elevation_width_resolved",
    "panel_count_measurable",
    "count_matching_strip_exists",
    "scale_consistent_strip_unique",
    "one_common_ratio_group",
    "fingerprint_exclusive_across_tags",
    "callout_beside_fingerprint_strip",
    "no_other_callout_claims_strip",
    "strip_in_callout_viewport",
)

# Source coordinates sit on a lattice whose spacing is the scope's coordinate quantum; two
# coordinates closer than a quarter of it are the same coordinate (lattice sites are at least one
# quantum apart). This is identity of drawn geometry, not a distance threshold.
_EQ_FRACTION_OF_QUANTUM = 0.25
# Work bounds. They stop a pathological page from being analysed; they decide nothing.
_MAX_INK = 200_000
_MAX_RING_EDGES = 250
# Path expansions allowed while looking for one callout ring; past it the word abstains.
_MAX_RING_PATH_EXPANSIONS = 100_000
_MAX_SCALE_PAIRS = 5_000
# A post between two panels of one strip is narrower than the strip's own frame depth.
_MAX_CHAIN_GAP_DEPTHS = 1.0
# Largest relative disagreement between a record's aspect ratio and its bounding box for the
# record's axes to be read as native x/y (or swapped); anything unclear abstains.
_AXIS_ASPECT_FIT = 0.05


# --------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SourceOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    input_provenance: str


@dataclass(frozen=True)
class PlanInkSegment:
    """One visible, stroked source segment of the plan page (native page coordinates)."""

    ink_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    black: bool


@dataclass(frozen=True)
class PlanTextObservation:
    """A trusted native word of the plan page (the caller proves the trust)."""

    observation_id: str
    text: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class PlanViewportRef:
    view_id: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class ElevationTypeObservation:
    """What the elevation page says about one type mark, with its provenance resolved."""

    type_mark: str
    record_id: str
    display_width_mm: Optional[float]
    panel_count: int
    panel_observation_ids: tuple[str, ...] = ()
    unresolved_reason: str = ""
    outside_frame_mark_count: int = 0


@dataclass(frozen=True)
class PlanCalloutStripScope:
    ownership: SourceOwnership
    plan_page_id: str
    elevation_page_id: str
    callout_mark_pattern: str
    coordinate_quantum_pt: float
    dimension_quantum_mm: float
    plan_viewports: tuple[PlanViewportRef, ...] = ()
    elevation_viewport_id: Optional[str] = None
    untrusted_plan_words: tuple[PlanTextObservation, ...] = ()
    plan_viewport_basis: str = "caller_supplied"

    def __post_init__(self) -> None:
        if not (math.isfinite(self.coordinate_quantum_pt) and self.coordinate_quantum_pt > 0.0
                and math.isfinite(self.dimension_quantum_mm) and self.dimension_quantum_mm > 0.0):
            raise ValueError("coordinate and dimension quanta must be positive finite numbers")
        re.compile(self.callout_mark_pattern)


@dataclass(frozen=True)
class GlazingStrip:
    strip_id: str
    axis: str
    band: tuple[float, float]
    frame_depth: float
    along: tuple[float, float]
    frame_along: tuple[float, float]
    panel_count: int
    panel_lengths: tuple[float, ...]
    inner_post_widths: tuple[float, ...]
    end_post_widths: tuple[Optional[float], Optional[float]]
    extent_complete: bool
    stroke_width: float
    plan_viewport_id: Optional[str]
    ink_ids: tuple[str, ...]


@dataclass(frozen=True)
class CalloutRing:
    status: EvidenceResolutionStatus
    tag_observation_id: str
    tag_mark: str
    reason_codes: tuple[str, ...] = ()
    polygon: tuple[tuple[float, float], ...] = ()
    ink_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CalloutCorrespondence:
    tag_mark: str
    tag_observation_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    conditions: tuple[tuple[str, str], ...]
    strip_id: Optional[str]
    ring: CalloutRing
    plan_viewport_id: Optional[str]
    count_matching_strip_ids: tuple[str, ...]
    scale_consistent_strip_ids: tuple[str, ...]
    position_strip_ids: tuple[str, ...]
    rival_strip_ids: tuple[str, ...]
    rival_callout_ids: tuple[str, ...]
    numbers: tuple[tuple[str, float], ...]
    record_id: str

    def __post_init__(self) -> None:
        if (tuple(name for name, _ in self.conditions) != CONDITION_NAMES
                or any(state not in (PASSED, FAILED, NOT_EVALUATED) for _, state in self.conditions)):
            raise ValueError("a correspondence carries exactly the complete, ordered, unique condition set")
        if self.status is EvidenceResolutionStatus.CANDIDATE:
            if self.strip_id is None or any(state != PASSED for _, state in self.conditions):
                raise ValueError("a CANDIDATE needs a strip and every condition passed")


_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted",
    "scale_granted", "metric_granted", "count_granted", "quantity_granted",
    "door_leaf_granted", "wall_binding_granted", "commercial_projection_allowed",
    "customer_publication_granted",
)


@dataclass(frozen=True)
class PlanCalloutStripShadow:
    ownership: SourceOwnership
    plan_page_id: str
    elevation_page_id: str
    elevation_viewport_id: Optional[str]
    strips: tuple[GlazingStrip, ...]
    correspondences: tuple[CalloutCorrespondence, ...]
    page_reason_codes: tuple[str, ...]
    untrusted_plan_word_count: int
    shadow_only: bool = True
    text_trust_verified_by_this_module: bool = False
    physical_opening_granted: bool = False
    host_granted: bool = False
    opening_kind_granted: bool = False
    frame_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    door_leaf_granted: bool = False
    wall_binding_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    schema_version: str = PLAN_CALLOUT_STRIP_SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True or self.text_trust_verified_by_this_module is not False:
            raise ValueError("shadow receipt cannot leave shadow mode or claim to verify text trust")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"shadow receipt cannot grant {name}")
        known = {f.name for f in fields(self)}
        if not set(_GRANT_FLAGS) <= known:
            raise ValueError("grant flag set is out of date")


# --------------------------------------------------------------------------------------
# ink: exact-width classes on a snapped coordinate grid
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Stroke:
    axis: str            # "H" or "V"
    offset: float        # coordinate across the line
    lo: float            # along-axis start
    hi: float            # along-axis end
    ink_id: str


def _snapper(values: Iterable[float], eq: float) -> Callable[[float], float]:
    """Map values that sit within one source quantum of a neighbour onto one representative.

    Chain clustering on the sorted distinct values: independent of input order and of
    where a translation puts the values relative to any fixed rounding boundary."""
    representative: dict[float, float] = {}
    start: Optional[float] = None
    previous: Optional[float] = None
    for value in sorted(set(values)):
        if previous is None or value - previous > eq:
            start = value
        representative[value] = start  # type: ignore[assignment]
        previous = value
    return representative.__getitem__


def _axis_aligned(ink: Sequence[PlanInkSegment], eq: float) -> dict[float, list[_Stroke]]:
    """Black axis-aligned strokes grouped by their own exact stroke width."""
    raw: dict[float, list[tuple[str, float, float, float, str]]] = defaultdict(list)
    for s in ink:
        if not s.black or not all(math.isfinite(v) for v in (s.x0, s.y0, s.x1, s.y1, s.width)):
            continue
        key = round(float(s.width), 3)
        if abs(s.y0 - s.y1) <= eq and abs(s.x0 - s.x1) > eq:
            raw[key].append(("H", (s.y0 + s.y1) / 2.0, min(s.x0, s.x1), max(s.x0, s.x1), s.ink_id))
        elif abs(s.x0 - s.x1) <= eq and abs(s.y0 - s.y1) > eq:
            raw[key].append(("V", (s.x0 + s.x1) / 2.0, min(s.y0, s.y1), max(s.y0, s.y1), s.ink_id))
    by_width: dict[float, list[_Stroke]] = {}
    for key, items in raw.items():
        sx = _snapper([v for a, o, lo, hi, _ in items for v in ((o,) if a == "V" else (lo, hi))], eq)
        sy = _snapper([v for a, o, lo, hi, _ in items for v in ((o,) if a == "H" else (lo, hi))], eq)
        by_width[key] = [
            _Stroke(a, (sy if a == "H" else sx)(o), (sx if a == "H" else sy)(lo),
                    (sx if a == "H" else sy)(hi), ink_id)
            for a, o, lo, hi, ink_id in items
        ]
    return by_width


@dataclass(frozen=True)
class _Cover:
    """Union of collinear stroke pieces at one offset (invariant to splitting and double ink)."""

    spans: tuple[tuple[float, float], ...]
    pieces: tuple[tuple[float, float, str], ...]
    eq: float

    def covers(self, lo: float, hi: float) -> bool:
        return any(a - self.eq <= lo and hi <= b + self.eq for a, b in self.spans)

    def ink_in(self, lo: float, hi: float) -> set[str]:
        return {q for a, b, q in self.pieces if b >= lo - self.eq and a <= hi + self.eq}


def _covers_by_offset(strokes: Sequence[_Stroke], axis: str, eq: float) -> dict[float, _Cover]:
    pieces: dict[float, list[tuple[float, float, str]]] = defaultdict(list)
    for s in strokes:
        if s.axis == axis:
            pieces[s.offset].append((s.lo, s.hi, s.ink_id))
    covers: dict[float, _Cover] = {}
    for offset, items in pieces.items():
        items.sort()
        merged: list[list[float]] = []
        for lo, hi, _ in items:
            if merged and lo <= merged[-1][1] + eq:
                merged[-1][1] = max(merged[-1][1], hi)
            else:
                merged.append([lo, hi])
        covers[offset] = _Cover(tuple((a, b) for a, b in merged), tuple(items), eq)
    return covers


def _pane_boxes(strokes: Sequence[_Stroke], axis: str, eq: float, lines: dict[float, _Cover]) -> list[dict]:
    """Thin closed boxes (glass panes): two parallel lines and two perpendicular end ticks.

    An end tick is a stroke, or the collinear union of strokes, spanning exactly the pair of
    parallel lines; both views are used so a tick exported in pieces is still one tick."""
    other = "V" if axis == "H" else "H"
    ranges: dict[tuple[float, float], set[float]] = defaultdict(set)
    for s in strokes:
        if s.axis == other and s.hi - s.lo > eq:
            ranges[(s.lo, s.hi)].add(s.offset)
    for offset, cover in _covers_by_offset(strokes, other, eq).items():
        for lo, hi in cover.spans:
            if hi - lo > eq:
                ranges[(lo, hi)].add(offset)
    boxes: list[dict] = []
    for (p, q), offsets in ranges.items():
        along_positions = sorted(offsets)
        for a, b in zip(along_positions, along_positions[1:]):
            if b - a <= q - p:        # a pane is longer than it is thick
                continue
            lp, lq = lines.get(p), lines.get(q)
            if lp is None or lq is None or not (lp.covers(a, b) and lq.covers(a, b)):
                continue
            boxes.append({"a": a, "b": b, "p": p, "q": q})
    # a pane is the INNERMOST thin box: the frame outline drawn around it is also a closed box
    return [
        x for x in boxes
        if not any(y is not x and x["a"] - eq <= y["a"] and y["b"] <= x["b"] + eq
                   and x["p"] + eq < y["p"] and y["q"] < x["q"] - eq for y in boxes)
    ]


def _q(value: float) -> float:
    return round(value, 2)


def _glazing_strips(strokes: Sequence[_Stroke], width: float, ownership: SourceOwnership,
                    plan_page_id: str, eq: float) -> list[GlazingStrip]:
    strips: list[GlazingStrip] = []
    for axis in ("H", "V"):
        other = "V" if axis == "H" else "H"
        lines = _covers_by_offset(strokes, axis, eq)
        crosses = _covers_by_offset(strokes, other, eq)
        offsets = sorted(lines)
        panels: list[dict] = []
        for box in _pane_boxes(strokes, axis, eq, lines):
            a, b, p, q = box["a"], box["b"], box["p"], box["q"]
            below = [o for o in offsets if o < p - eq and lines[o].covers(a, b)]
            above = [o for o in offsets if o > q + eq and lines[o].covers(a, b)]
            if not below or not above:
                continue
            o0, o1 = max(below), min(above)
            if o1 - o0 >= b - a:     # the frame is deeper than the panel is long: not a window panel
                continue
            inner, side0, side1 = q - p, p - o0, o1 - q
            if not (inner < side0 - eq and inner < side1 - eq):     # the glass pair is narrower than each rebate
                continue
            if abs(side0 - side1) > 2.0 * eq:                       # and sits centred in the frame
                continue
            ca, cb = crosses.get(a), crosses.get(b)                 # the cell is closed across its full depth
            if ca is None or cb is None or not (ca.covers(o0, o1) and cb.covers(o0, o1)):
                continue
            panels.append({"a": a, "b": b, "p": p, "q": q, "o0": o0, "o1": o1})
        groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
        for panel in panels:
            groups[(panel["o0"], panel["o1"])].append(panel)
        for (o0, o1), members in groups.items():
            members.sort(key=lambda m: (m["a"], m["b"]))
            depth = o1 - o0
            runs: list[list[dict]] = []
            for m in members:
                if runs and -eq <= m["a"] - runs[-1][-1]["b"] <= depth * _MAX_CHAIN_GAP_DEPTHS:
                    runs[-1].append(m)
                else:
                    runs.append([m])
            for run in runs:
                lo, hi = run[0]["a"], run[-1]["b"]
                inner = tuple(_q(y["a"] - x["b"]) for x, y in zip(run, run[1:]))
                ends: list[Optional[float]] = []
                for side in ("lo", "hi"):
                    found = None
                    for off in (o0, o1):
                        for a_, b_, _id in lines[off].pieces:
                            piece = b_ - a_
                            if not (eq < piece <= depth):
                                continue
                            if side == "lo" and abs(b_ - lo) <= eq:
                                found = _q(piece)
                            if side == "hi" and abs(a_ - hi) <= eq:
                                found = _q(piece)
                    ends.append(found)
                ink: set[str] = set()
                for m in run:
                    for off in (o0, m["p"], m["q"], o1):
                        ink |= lines[off].ink_in(m["a"], m["b"])
                for s in strokes:
                    if s.axis == other and lo - eq <= s.offset <= hi + eq and s.lo >= o0 - eq and s.hi <= o1 + eq:
                        ink.add(s.ink_id)
                frame_lo = lo - (ends[0] or 0.0)
                frame_hi = hi + (ends[1] or 0.0)
                ink_ids = tuple(sorted(ink))
                strip_id = stable_contract_id("shadow_strip", {
                    "ownership": (ownership.document_id, ownership.revision_id,
                                  ownership.snapshot_id, ownership.source_sha256),
                    "page": plan_page_id, "width": width, "axis": axis,
                    "band": (_q(o0), _q(o1)), "along": (_q(lo), _q(hi)),
                    "panels": len(run), "ink": ink_ids,
                }, digest_chars=24)
                strips.append(GlazingStrip(
                    strip_id=strip_id, axis=axis, band=(_q(o0), _q(o1)), frame_depth=_q(depth),
                    along=(_q(lo), _q(hi)), frame_along=(_q(frame_lo), _q(frame_hi)),
                    panel_count=len(run), panel_lengths=tuple(_q(m["b"] - m["a"]) for m in run),
                    inner_post_widths=inner, end_post_widths=(ends[0], ends[1]),
                    extent_complete=ends[0] is not None and ends[1] is not None,
                    stroke_width=width, plan_viewport_id=None, ink_ids=ink_ids,
                ))
    return strips


# --------------------------------------------------------------------------------------
# callout ring
# --------------------------------------------------------------------------------------


def _cross(a, b, c) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _strictly_inside(point, polygon) -> bool:
    signs = [_cross(polygon[i], polygon[(i + 1) % len(polygon)], point) for i in range(len(polygon))]
    return all(v > 1e-6 for v in signs) or all(v < -1e-6 for v in signs)


def _between(a, b, p, eq: float) -> bool:
    return (min(a[0], b[0]) - eq <= p[0] <= max(a[0], b[0]) + eq
            and min(a[1], b[1]) - eq <= p[1] <= max(a[1], b[1]) + eq)


def _off_line(a, b, p) -> float:
    """Perpendicular distance of p from the line through a and b."""
    length = math.hypot(b[0] - a[0], b[1] - a[1])
    return abs(_cross(a, b, p)) / length if length > 0.0 else math.hypot(p[0] - a[0], p[1] - a[1])


def _convex(polygon) -> bool:
    n = len(polygon)
    signs = [_cross(polygon[i], polygon[(i + 1) % n], polygon[(i + 2) % n]) for i in range(n)]
    return all(v > 1e-6 for v in signs) or all(v < -1e-6 for v in signs)


def _black_lines(ink: Sequence[PlanInkSegment]) -> list[tuple[str, tuple[float, float], tuple[float, float]]]:
    return [(s.ink_id, (s.x0, s.y0), (s.x1, s.y1)) for s in ink
            if s.black and all(math.isfinite(v) for v in (s.x0, s.y0, s.x1, s.y1))]


def _ring_for_word(word: PlanTextObservation, lines, eq: float) -> CalloutRing:
    """Exactly one closed convex six-edge black ink ring around the word, or abstain."""
    x0, y0, x1, y1 = word.bbox
    span = max(x1 - x0, y1 - y0)
    margin = 1.5 * span
    bounds = (x0 - margin, y0 - margin, x1 + margin, y1 + margin)
    local = [(ink_id, a, b) for ink_id, a, b in lines
             if bounds[0] <= a[0] <= bounds[2] and bounds[0] <= b[0] <= bounds[2]
             and bounds[1] <= a[1] <= bounds[3] and bounds[1] <= b[1] <= bounds[3]]
    sx = _snapper([v for _, a, b in local for v in (a[0], b[0])], eq)
    sy = _snapper([v for _, a, b in local for v in (a[1], b[1])], eq)
    edges: dict[tuple, set[str]] = defaultdict(set)
    for ink_id, a, b in local:
        pa, pb = (sx(a[0]), sy(a[1])), (sx(b[0]), sy(b[1]))
        if pa != pb:
            edges[tuple(sorted((pa, pb)))].add(ink_id)
    base = dict(tag_observation_id=word.observation_id, tag_mark=word.text)
    if len(edges) > _MAX_RING_EDGES:
        return CalloutRing(status=EvidenceResolutionStatus.ABSTAINED,
                           reason_codes=("callout_local_ink_unbounded",), **base)
    neighbours: dict[tuple, set[tuple]] = defaultdict(set)
    for a, b in edges:
        neighbours[a].add(b)
        neighbours[b].add(a)
    # an edge exported in two collinear pieces is still one edge: contract straight degree-2 vertices
    changed = True
    while changed:
        changed = False
        for vertex in sorted(neighbours):
            around = sorted(neighbours[vertex])
            if len(around) == 2 and _off_line(around[0], around[1], vertex) <= eq:
                neighbours[around[0]].discard(vertex)
                neighbours[around[1]].discard(vertex)
                neighbours[around[0]].add(around[1])
                neighbours[around[1]].add(around[0])
                del neighbours[vertex]
                changed = True
                break
    # a vertex with fewer than two neighbours cannot lie on a cycle
    pruned = True
    while pruned:
        pruned = False
        for vertex in sorted(neighbours):
            if len(neighbours[vertex]) < 2:
                for other in neighbours[vertex]:
                    neighbours[other].discard(vertex)
                del neighbours[vertex]
                pruned = True
                break
    cycles: dict[tuple, tuple] = {}
    centre = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
    expansions = 0
    for start in sorted(neighbours):
        stack = [(start, (start,))]
        while stack:
            expansions += 1
            if expansions > _MAX_RING_PATH_EXPANSIONS:
                return CalloutRing(status=EvidenceResolutionStatus.ABSTAINED,
                                   reason_codes=("callout_ring_search_budget_exceeded",), **base)
            node, path = stack.pop()
            if len(path) == 6:
                if start in neighbours[node] and _convex(path):
                    # the word's font box is not its ink, so containment is decided on its centre alone
                    if _strictly_inside(centre, path):
                        cycles[tuple(sorted(path))] = path
                continue
            for nxt in sorted(neighbours[node]):
                if nxt not in path and nxt >= start:
                    stack.append((nxt, path + (nxt,)))
    if not cycles:
        return CalloutRing(status=EvidenceResolutionStatus.ABSTAINED,
                           reason_codes=("callout_ring_not_found",), **base)
    if len(cycles) != 1:
        return CalloutRing(status=EvidenceResolutionStatus.CONFLICT,
                           reason_codes=("callout_ring_not_unique",), **base)
    polygon = next(iter(cycles.values()))
    owners_all: set[str] = set()
    for raw_edge, owners in edges.items():
        for i in range(6):
            a_, b_ = polygon[i], polygon[(i + 1) % 6]
            if (_off_line(a_, b_, raw_edge[0]) <= eq and _off_line(a_, b_, raw_edge[1]) <= eq
                    and _between(a_, b_, raw_edge[0], eq) and _between(a_, b_, raw_edge[1], eq)):
                owners_all |= owners
    return CalloutRing(status=EvidenceResolutionStatus.CANDIDATE, polygon=tuple(polygon),
                       ink_ids=tuple(sorted(owners_all)), **base)


# --------------------------------------------------------------------------------------
# correspondence
# --------------------------------------------------------------------------------------


def _tag_key(text: str) -> Optional[str]:
    """The repository's own opening-tag normalisation (W01 and W1 are one type mark)."""
    normalized = normalize_opening_tag(text)
    return None if normalized is None else normalized.tag


def _contains(box, inner) -> bool:
    return box[0] <= inner[0] and box[1] <= inner[1] and inner[2] <= box[2] and inner[3] <= box[3]


def _ring_box(ring: CalloutRing) -> tuple[float, float, float, float]:
    xs = [p[0] for p in ring.polygon]
    ys = [p[1] for p in ring.polygon]
    return (min(xs), min(ys), max(xs), max(ys))


def _strip_box(strip: GlazingStrip) -> tuple[float, float, float, float]:
    lo, hi = strip.frame_along
    o0, o1 = strip.band
    return (lo, o0, hi, o1) if strip.axis == "H" else (o0, lo, o1, hi)


def _viewport_of(box, viewports: Sequence[PlanViewportRef]) -> Optional[str]:
    matches = [v.view_id for v in viewports if _contains(v.bbox, box)]
    return matches[0] if len(matches) == 1 else None


def _position(ring: CalloutRing, strip: GlazingStrip, eq: float) -> tuple[bool, float]:
    """Necessary location conditions only: all six vertices within the strip's along-extent
    and on one side of its band. The gap is reported as data, never as a pass/fail."""
    along = [p[0] for p in ring.polygon] if strip.axis == "H" else [p[1] for p in ring.polygon]
    normal = [p[1] for p in ring.polygon] if strip.axis == "H" else [p[0] for p in ring.polygon]
    flo, fhi = strip.frame_along
    o0, o1 = strip.band
    inside = all(flo - eq <= v <= fhi + eq for v in along)
    beyond = all(v >= o1 - eq for v in normal)
    before = all(v <= o0 + eq for v in normal)
    if before:
        gap = o0 - max(normal)
    elif beyond:
        gap = min(normal) - o1
    else:
        gap = 0.0
    return bool(inside and (beyond or before)), float(gap)


_INCONCLUSIVE_RING = {"callout_ring_search_budget_exceeded", "callout_ring_not_unique", "callout_local_ink_unbounded"}


def _word_claims(word: PlanTextObservation, strip: GlazingStrip, eq: float) -> bool:
    """Location filter on a word's centre alone, for a ring that could not be decided: beside the
    strip's along-extent and not over its band."""
    cx, cy = (word.bbox[0] + word.bbox[2]) / 2.0, (word.bbox[1] + word.bbox[3]) / 2.0
    along, normal = (cx, cy) if strip.axis == "H" else (cy, cx)
    flo, fhi = strip.frame_along
    o0, o1 = strip.band
    return bool(flo - eq <= along <= fhi + eq and not (o0 - eq <= normal <= o1 + eq))


@dataclass(frozen=True)
class _TypeFact:
    key: str
    mm: float
    panels: int


def _scale_support(facts: Sequence[_TypeFact], strips: Sequence[GlazingStrip], q_pt: float, q_mm: float):
    """Cross-window consistency of the plan/elevation length ratio.

    A pair (type, strip) is supported when a pair of another type on another strip has the
    same ratio of printed width to drawn extent within the sum of the two pairs' own quantum
    tolerances (two plan endpoints plus the dimension print step). The ratios are computed for
    this test only; none is exported, published or granted."""
    pairs = []
    for fact in facts:
        for strip in strips:
            if strip.panel_count != fact.panels or not strip.extent_complete:
                continue
            extent = strip.frame_along[1] - strip.frame_along[0]
            if extent <= 0.0:
                continue
            pairs.append((fact.key, strip.strip_id, fact.mm / extent, 2.0 * q_pt / extent + q_mm / fact.mm))
    if len(pairs) > _MAX_SCALE_PAIRS:
        return None
    supporters: dict[tuple[str, str], list[float]] = defaultdict(list)
    for key, sid, ratio, tol in pairs:
        for key2, sid2, ratio2, tol2 in pairs:
            if key2 == key or sid2 == sid:
                continue
            difference = abs(ratio - ratio2) / max(ratio, ratio2)
            if difference <= tol + tol2:
                supporters[(key, sid)].append(difference)
    return supporters, {(key, sid): (ratio, tol) for key, sid, ratio, tol in pairs}


def _ratio_groups(chosen: dict[str, tuple[float, float]]) -> dict[str, str]:
    """Is there ONE shared ratio behind every chosen pair?

    Chosen pairs (one per type) are linked when their ratios agree within their own tolerances.
    A component of two or more is a group and must be a clique; two groups, a non-clique group,
    or a pair with no partner cannot claim one shared ratio. States: ok / competing / unshared."""
    keys = sorted(chosen)

    def agree(a: str, b: str) -> bool:
        (ra, ta), (rb, tb) = chosen[a], chosen[b]
        return abs(ra - rb) / max(ra, rb) <= ta + tb

    parent = {k: k for k in keys}

    def find(k: str) -> str:
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if agree(a, b):
                parent[find(a)] = find(b)
    components: dict[str, list[str]] = defaultdict(list)
    for k in keys:
        components[find(k)].append(k)
    groups = [members for members in components.values() if len(members) >= 2]
    state: dict[str, str] = {}
    for members in components.values():
        if len(members) < 2:
            state[members[0]] = "unshared"
            continue
        is_clique = all(agree(a, b) for i, a in enumerate(members) for b in members[i + 1:])
        for k in members:
            state[k] = "ok" if (is_clique and len(groups) == 1) else "competing"
    return state


def audit_plan_callout_to_glazing_strip_shadow(
    scope: PlanCalloutStripScope, *, ink: Sequence[PlanInkSegment],
    words: Sequence[PlanTextObservation], elevation_types: Sequence[ElevationTypeObservation],
) -> PlanCalloutStripShadow:
    """Pure core over already-extracted, producer-owned records."""
    if type(scope) is not PlanCalloutStripScope:
        raise TypeError("plan callout strip scope required")
    ownership = scope.ownership
    eq = scope.coordinate_quantum_pt * _EQ_FRACTION_OF_QUANTUM
    pattern = re.compile(scope.callout_mark_pattern)
    callouts = sorted((w for w in words if pattern.fullmatch(w.text)),
                      key=lambda w: (w.text, w.observation_id))
    page_reasons: list[str] = []
    strips: list[GlazingStrip] = []
    lines: list = []
    if len(ink) > _MAX_INK:
        page_reasons.append("stroke_budget_exceeded")
    else:
        for width, strokes in sorted(_axis_aligned(ink, eq).items()):
            strips.extend(_glazing_strips(strokes, width, ownership, scope.plan_page_id, eq))
        lines = _black_lines(ink)
    strips = [replace(s, plan_viewport_id=_viewport_of(_strip_box(s), scope.plan_viewports)) for s in strips]
    strips.sort(key=lambda s: (s.axis, s.band, s.along, s.panel_count, s.strip_id))
    by_id = {s.strip_id: s for s in strips}
    # rings are inventoried around native words only: a ring whose tag is not a native word is not seen
    page_reasons.append("callout_rings_without_native_words_not_inventoried")
    if scope.plan_viewport_basis == WHOLE_PAGE_UNSEGMENTED:
        page_reasons.append("plan_viewport_whole_page_unsegmented")

    # uniqueness of a type mark is a fact about ALL trusted native words of the page (W01 and W1 are one
    # key); the report pattern only selects what is reported
    key_count = Counter(k for k in (_tag_key(w.text) for w in words) if k is not None)
    for w in callouts:
        if _tag_key(w.text) is None:
            key_count[None] += 1
    rings = {w.observation_id: (None if "stroke_budget_exceeded" in page_reasons else _ring_for_word(w, lines, eq))
             for w in callouts}
    types_by_key: dict[str, list[ElevationTypeObservation]] = defaultdict(list)
    for t in elevation_types:
        key = _tag_key(t.type_mark)
        if key is not None:
            types_by_key[key].append(t)
    plan_keys = {k for k in (_tag_key(w.text) for w in callouts) if k is not None}

    facts: list[_TypeFact] = []
    for key in sorted(plan_keys):
        group = types_by_key.get(key, [])
        if (len(group) == 1 and key_count[key] == 1 and group[0].display_width_mm is not None
                and math.isfinite(group[0].display_width_mm) and group[0].display_width_mm > 0.0
                and group[0].panel_count >= 2):
            facts.append(_TypeFact(key, float(group[0].display_width_mm), int(group[0].panel_count)))
    scale = _scale_support(facts, strips, scope.coordinate_quantum_pt, scope.dimension_quantum_mm)
    if scale is None:
        page_reasons.append("scale_pair_budget_exceeded")
        supporters, pair_info = {}, {}
    else:
        supporters, pair_info = scale
    supported: dict[str, set[str]] = defaultdict(set)
    for (key, sid), _diffs in supporters.items():
        supported[key].add(sid)
    ratio_state = _ratio_groups({key: pair_info[(key, next(iter(sids)))] for key, sids in supported.items()
                                 if len(sids) == 1})

    # The target pattern only selects what is REPORTED. Every native word that could label an opening
    # (the repository's own tag syntax, trusted or not) is a possible claimant, and a ring that cannot be
    # decided stays a claimant by its word's position instead of disappearing.
    budget_spent = "stroke_budget_exceeded" in page_reasons
    reported_ids = {w.observation_id for w in callouts}
    claim_words = sorted((w for w in words if w.observation_id in reported_ids or _tag_key(w.text) is not None),
                         key=lambda w: (w.text, w.observation_id))
    all_rings = dict(rings)
    for w in claim_words:
        if w.observation_id not in all_rings:
            all_rings[w.observation_id] = None if budget_spent else _ring_for_word(w, lines, eq)
    position: dict[tuple[str, str], tuple[bool, float]] = {}
    claimants: dict[str, list[str]] = defaultdict(list)
    uncertain: dict[str, list[tuple[str, str]]] = defaultdict(list)

    def note_claims(word: PlanTextObservation, ring: Optional[CalloutRing], reason: str, label: str) -> None:
        if ring is None:
            return
        for strip in strips:
            if ring.status is EvidenceResolutionStatus.CANDIDATE:
                ok, gap = _position(ring, strip, eq)
                if label == "":
                    position[(word.observation_id, strip.strip_id)] = (ok, gap)
                    if ok:
                        claimants[strip.strip_id].append(word.observation_id)
                elif ok:
                    uncertain[strip.strip_id].append((reason, label + word.observation_id))
            elif set(ring.reason_codes) & _INCONCLUSIVE_RING and _word_claims(word, strip, eq):
                uncertain[strip.strip_id].append(("strip_has_unresolved_ring_claimant", "unresolved:" + word.observation_id))

    for w in claim_words:
        note_claims(w, all_rings.get(w.observation_id), "", "")
    # an untrusted native word inside a ring beside a strip may be a second callout: its label is unknown
    if not budget_spent:
        for w in sorted(scope.untrusted_plan_words, key=lambda w: w.observation_id):
            note_claims(w, _ring_for_word(w, lines, eq), "strip_has_claimant_with_untrusted_label", "untrusted:")
    fingerprint_owners: dict[str, set[str]] = defaultdict(set)
    for key, sids in supported.items():
        for sid in sids:
            fingerprint_owners[sid].add(key)

    correspondences: list[CalloutCorrespondence] = []
    for word in callouts:
        correspondences.append(_decide(
            word, scope, rings.get(word.observation_id), key_count, types_by_key, facts, strips, by_id,
            supported, supporters, fingerprint_owners, position, claimants, uncertain, ratio_state, page_reasons))
    correspondences.sort(key=lambda c: (c.tag_mark, c.tag_observation_id))
    return PlanCalloutStripShadow(
        ownership=ownership, plan_page_id=scope.plan_page_id, elevation_page_id=scope.elevation_page_id,
        elevation_viewport_id=scope.elevation_viewport_id, strips=tuple(strips),
        correspondences=tuple(correspondences), page_reason_codes=tuple(page_reasons),
        untrusted_plan_word_count=len(scope.untrusted_plan_words))


def _decide(word, scope, ring, key_count, types_by_key, facts, strips, by_id, supported, supporters,
            fingerprint_owners, position, claimants, uncertain, ratio_state, page_reasons) -> CalloutCorrespondence:
    oid = word.observation_id
    key = _tag_key(word.text)
    states: dict[str, str] = {}
    numbers: dict[str, float] = {}
    count_matching: list[str] = []
    scale_consistent: list[str] = []
    position_ids: list[str] = []
    rival_callouts: list[str] = []
    chosen: Optional[str] = None
    viewport: Optional[str] = None

    def finish(status: EvidenceResolutionStatus, reasons: Sequence[str]) -> CalloutCorrespondence:
        conditions = tuple((name, states.get(name, NOT_EVALUATED)) for name in CONDITION_NAMES)
        selected = chosen if status is EvidenceResolutionStatus.CANDIDATE else None
        rivals = sorted((set(count_matching) | set(position_ids) | set(scale_consistent)
                         | ({chosen} if chosen else set())) - ({selected} if selected else set()))
        callout_rivals = tuple(sorted(set(rival_callouts)))
        record_id = stable_contract_id("shadow_plan_callout_strip_correspondence", {
            "ownership": (scope.ownership.document_id, scope.ownership.revision_id,
                          scope.ownership.snapshot_id, scope.ownership.source_sha256),
            "page": scope.plan_page_id, "tag": oid, "mark": word.text, "status": status.value,
            "strip": selected, "rivals": tuple(rivals), "callouts": callout_rivals,
            "conditions": conditions, "reasons": tuple(reasons),
        }, digest_chars=24)
        ring_view = ring or CalloutRing(status=EvidenceResolutionStatus.ABSTAINED, tag_observation_id=oid,
                                        tag_mark=word.text, reason_codes=("callout_ring_not_evaluated",))
        return CalloutCorrespondence(
            tag_mark=word.text, tag_observation_id=oid, status=status, reason_codes=tuple(reasons),
            conditions=conditions, strip_id=selected,
            ring=ring_view, plan_viewport_id=viewport, count_matching_strip_ids=tuple(sorted(count_matching)),
            scale_consistent_strip_ids=tuple(sorted(scale_consistent)),
            position_strip_ids=tuple(sorted(position_ids)), rival_strip_ids=tuple(rivals),
            rival_callout_ids=callout_rivals, numbers=tuple(sorted(numbers.items())), record_id=record_id)

    ABSTAIN, CONFLICT = EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT

    if "stroke_budget_exceeded" in page_reasons:
        return finish(ABSTAIN, ("stroke_budget_exceeded",))
    # 1 the tag is one explicit, unique opening mark on the plan page
    if key is None or key_count[key] != 1:
        states["tag_unique_on_plan_page"] = FAILED
        return finish(ABSTAIN, ("tag_not_unique_on_plan_page",))
    states["tag_unique_on_plan_page"] = PASSED
    # 2 its callout ring
    if ring is None or ring.status is not EvidenceResolutionStatus.CANDIDATE:
        states["callout_ring_unique"] = FAILED
        return finish(ring.status if ring is not None else ABSTAIN,
                      ring.reason_codes if ring is not None else ("callout_ring_not_found",))
    states["callout_ring_unique"] = PASSED
    box = _ring_box(ring)
    viewport = _viewport_of(box, scope.plan_viewports)
    # position of this callout against every strip, as data (kept even when the viewport is not resolved)
    position_ids.extend(s.strip_id for s in strips if position.get((oid, s.strip_id), (False, 0.0))[0])
    if scope.plan_viewport_basis == WHOLE_PAGE_UNSEGMENTED:
        # the whole page admitted for want of any segmentation is a caveat about the page, not a RESOLVED viewport
        states["callout_in_one_resolved_plan_viewport"] = FAILED
        return finish(ABSTAIN, ("plan_viewport_not_resolved",))
    if viewport is None:
        states["callout_in_one_resolved_plan_viewport"] = FAILED
        return finish(ABSTAIN, ("callout_outside_resolved_plan_viewport",))
    states["callout_in_one_resolved_plan_viewport"] = PASSED
    # 3 the elevation type
    group = types_by_key.get(key, [])
    if len(group) != 1:
        states["elevation_type_record_unique"] = FAILED
        return finish(CONFLICT if group else ABSTAIN,
                      ("elevation_type_record_ambiguous",) if group else ("elevation_type_record_missing",))
    states["elevation_type_record_unique"] = PASSED
    kind = group[0]
    if kind.display_width_mm is None or not math.isfinite(kind.display_width_mm) or kind.display_width_mm <= 0.0:
        states["elevation_width_resolved"] = FAILED
        return finish(ABSTAIN, (kind.unresolved_reason or "elevation_width_unresolved",))
    states["elevation_width_resolved"] = PASSED
    numbers["panel_count"] = float(kind.panel_count)
    if kind.panel_count < 2:
        states["panel_count_measurable"] = FAILED
        return finish(ABSTAIN, ("single_panel_fingerprint_unmeasurable",) if kind.panel_count == 1
                      else ("elevation_panel_count_unavailable",))
    states["panel_count_measurable"] = PASSED
    # 4 strips whose panel count matches, page wide
    count_matching = [s.strip_id for s in strips if s.panel_count == kind.panel_count]
    numbers["count_matching_strips"] = float(len(count_matching))
    numbers["count_matching_strips_without_complete_extent"] = float(
        sum(1 for s in strips if s.panel_count == kind.panel_count and not s.extent_complete))
    if not count_matching:
        states["count_matching_strip_exists"] = FAILED
        return finish(ABSTAIN, ("no_count_matching_strip",))
    states["count_matching_strip_exists"] = PASSED
    # 5 cross-window ratio consistency
    scale_consistent = sorted(supported.get(key, ()))
    numbers["scale_eligible_tags"] = float(len(facts))
    numbers["scale_consistent_strips"] = float(len(scale_consistent))
    if not scale_consistent:
        states["scale_consistent_strip_unique"] = FAILED
        return finish(ABSTAIN, ("fewer_than_two_scale_eligible_tags",) if len(facts) < 2
                      else ("no_scale_consistent_strip",))
    if len(scale_consistent) > 1:
        states["scale_consistent_strip_unique"] = FAILED
        return finish(CONFLICT, ("several_scale_consistent_strips",))
    states["scale_consistent_strip_unique"] = PASSED
    chosen = scale_consistent[0]
    shared = ratio_state.get(key, "unshared")
    if shared != "ok":
        states["one_common_ratio_group"] = FAILED
        return finish(CONFLICT if shared == "competing" else ABSTAIN,
                      ("competing_ratio_groups",) if shared == "competing" else ("ratio_group_unshared",))
    states["one_common_ratio_group"] = PASSED
    strip = by_id[chosen]
    numbers["strip_extent_pt"] = float(strip.frame_along[1] - strip.frame_along[0])
    diffs = supporters.get((key, chosen), [])
    numbers["scale_supporting_pairs"] = float(len(diffs))
    numbers["relative_ratio_disagreement_max"] = float(max(diffs)) if diffs else 0.0
    # 6 no other tag's fingerprint lands on the same strip
    others = sorted(fingerprint_owners.get(chosen, set()) - {key})
    if others:
        states["fingerprint_exclusive_across_tags"] = FAILED
        return finish(CONFLICT, ("fingerprint_strip_claimed_by_several_tags",))
    states["fingerprint_exclusive_across_tags"] = PASSED
    # 7 location is necessary only
    ok, gap = position.get((oid, chosen), (False, 0.0))
    numbers["callout_normal_gap_pt"] = gap
    if not ok:
        states["callout_beside_fingerprint_strip"] = FAILED
        return finish(ABSTAIN, ("callout_not_at_fingerprint_strip",))
    states["callout_beside_fingerprint_strip"] = PASSED
    # 8 no other callout ring (of any kind) satisfies the same location conditions
    trusted_rivals = [c for c in claimants.get(chosen, []) if c != oid]
    uncertain_rivals = [(reason, ident) for reason, ident in uncertain.get(chosen, [])
                        if ident != "unresolved:" + oid]
    rival_callouts.extend(trusted_rivals + [ident for _, ident in uncertain_rivals])
    numbers["other_callout_claimants"] = float(len(trusted_rivals))
    numbers["unresolved_or_unverified_claimants"] = float(len(uncertain_rivals))
    if trusted_rivals:
        states["no_other_callout_claims_strip"] = FAILED
        return finish(CONFLICT, ("strip_has_other_callout_claimants",))
    if uncertain_rivals:
        states["no_other_callout_claims_strip"] = FAILED
        reasons_here = {reason for reason, _ in uncertain_rivals}
        return finish(ABSTAIN, ("strip_has_unresolved_ring_claimant",)
                      if "strip_has_unresolved_ring_claimant" in reasons_here
                      else ("strip_has_claimant_with_untrusted_label",))
    states["no_other_callout_claims_strip"] = PASSED
    # 9 the strip lies in the same resolved viewport as the callout
    if strip.plan_viewport_id != viewport:
        states["strip_in_callout_viewport"] = FAILED
        return finish(ABSTAIN, ("strip_outside_callout_viewport",))
    states["strip_in_callout_viewport"] = PASSED
    reasons = ["source_correspondence_candidate_not_authority"]
    if scope.elevation_viewport_id is None:
        reasons.append("elevation_viewport_unproven")
    if kind.outside_frame_mark_count:
        reasons.append("elevation_mark_also_printed_outside_type_frame")
    return finish(EvidenceResolutionStatus.CANDIDATE, reasons)


# --------------------------------------------------------------------------------------
# producer adapter: the only place that reads a SourceVisibilityProducer
# --------------------------------------------------------------------------------------


def display_horizontal_width_mm(
    rotation: int, bbox: Sequence[float], axis_x_mm: float, axis_y_mm: float,
) -> tuple[Optional[float], str]:
    """The record's width along the page's DISPLAY-horizontal direction, or why it is unknown.

    The elevation record labels its two axes by native x and native y and carries no
    rotation; on a /Rotate 90 or 270 page the display-horizontal direction is native y.
    The axis labelling is checked against the frame bounding box and abstains if both or
    neither reading fits."""
    if rotation not in (0, 90, 180, 270):
        return None, "page_rotation_unavailable"
    bx, by = float(bbox[2]) - float(bbox[0]), float(bbox[3]) - float(bbox[1])
    if not (bx > 0.0 and by > 0.0 and axis_x_mm > 0.0 and axis_y_mm > 0.0):
        return None, "elevation_frame_degenerate"
    aspect = bx / by

    def fits(expected: float) -> bool:
        return abs(aspect - expected) / expected <= _AXIS_ASPECT_FIT

    native = fits(axis_x_mm / axis_y_mm)
    swapped = fits(axis_y_mm / axis_x_mm)
    if native == swapped:
        return None, "frame_axis_ambiguous" if native else "frame_axis_unverified"
    native_x_mm, native_y_mm = (axis_x_mm, axis_y_mm) if native else (axis_y_mm, axis_x_mm)
    return (native_x_mm if rotation in (0, 180) else native_y_mm), ""


def audit_plan_callout_to_glazing_strip_from_source(
    source, *, revision_id: str, plan_page_id: int, elevation_page_id: int,
    callout_mark_pattern: str, panel_token: str, coordinate_quantum_pt: float,
    dimension_quantum_mm: float,
) -> PlanCalloutStripShadow:
    """Run the shadow on a published revision of a `SourceVisibilityProducer`."""
    import fitz

    from pb_opening_elevation_frame_area_authority import (
        OpeningElevationFrameAreaProducer,
        OpeningElevationFrameAreaRecord,
        OpeningElevationFrameAreaSelector,
    )
    from pb_pdf_text_integrity_authority import TRUSTED_PDF_TEXT
    from pb_source_observation_authority import ObservationSelector
    from pb_source_visibility_authority import (
        VISIBLE_SOURCE_OBSERVATION_EXISTS,
        SourceVisibilityProducer,
    )
    from pb_vector_geometry_v130 import extract_native_page
    from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports

    if type(source) is not SourceVisibilityProducer:
        raise TypeError("source must be a producer-owned SourceVisibilityProducer")
    if type(plan_page_id) is not int or type(elevation_page_id) is not int:
        raise TypeError("page ids must be integers")
    published = source.published_snapshot_for_revision(revision_id)
    if published is None:
        raise ValueError("source revision unavailable")
    decoded = tuple(int(v) for v in published.coverage.decoded_pages)
    if (plan_page_id not in decoded or elevation_page_id not in decoded
            or source._producer.current_revision_id(published.revision.document_id) != revision_id):
        raise ValueError("source pages unavailable for the current revision")
    source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
    if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
        raise ValueError("producer source bytes failed their SHA check")
    ownership = SourceOwnership(
        document_id=published.revision.document_id, revision_id=revision_id,
        snapshot_id=published.snapshot.snapshot_id, source_sha256=published.revision.source_sha256,
        input_provenance=PRODUCER_INPUT_PROVENANCE)

    def selector(observation_id: str) -> ObservationSelector:
        return ObservationSelector(
            document_id=ownership.document_id, revision_id=revision_id,
            source_sha256=ownership.source_sha256, snapshot_id=ownership.snapshot_id,
            observation_id=observation_id)

    # trusted words, through the producer's own text-integrity authority
    text_authority = source.text_integrity_authority()
    plan_words: list[PlanTextObservation] = []
    elevation_words: list[PlanTextObservation] = []
    untrusted_plan: list[PlanTextObservation] = []
    for observation_id in published.text_observation_ids:
        result = text_authority.resolve_text(selector(observation_id))
        receipt = result.receipt
        if receipt is None or str(receipt.page_id) not in (str(plan_page_id), str(elevation_page_id)):
            continue
        if (result.status is EvidenceResolutionStatus.CORROBORATED and result.proposition == TRUSTED_PDF_TEXT
                and result.trusted_text is not None and len(receipt.geometry) >= 4):
            word = PlanTextObservation(
                str(observation_id), str(result.trusted_text), tuple(float(v) for v in receipt.geometry[:4]))
            (plan_words if str(receipt.page_id) == str(plan_page_id) else elevation_words).append(word)
        elif str(receipt.page_id) == str(plan_page_id) and len(receipt.geometry) >= 4:
            # only the box is used: an untrusted word's text is never an identity
            untrusted_plan.append(PlanTextObservation(
                str(observation_id), str(getattr(receipt, "raw_text", "") or ""),
                tuple(float(v) for v in receipt.geometry[:4])))

    with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
        plan_page = document[plan_page_id - 1]
        elevation_page = document[elevation_page_id - 1]
        elevation_rotation = int(elevation_page.rotation)
        segments = {s["id"]: s for s in extract_native_page(plan_page)["segments"]}
        segmented = segment_page_viewports(plan_page, page_number=plan_page_id)
        viewports = tuple(
            PlanViewportRef(str(v.view_id), tuple(float(c) for c in v.bounding_box))
            for v in segmented
            if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box is not None)
        viewport_basis = "segmented_resolved"
        # the same convention as the physical-scale producer: a page the segmentation found no usable
        # view on is admitted whole; a page with usable views is confined to its RESOLVED ones
        if not any(v.status in {ViewportSegmentationStatus.RESOLVED.value, ViewportSegmentationStatus.DERIVED.value}
                   and v.bounding_box is not None for v in segmented):
            viewports = (PlanViewportRef(f"page_{plan_page_id}", tuple(float(c) for c in plan_page.mediabox)),)
            viewport_basis = WHOLE_PAGE_UNSEGMENTED

    # visible ink, with stroke attributes joined from the producer's own primitive of the same id
    visibility = source.authority()
    ink: list[PlanInkSegment] = []
    for observation_id in published.visible_observation_ids:
        result = visibility.resolve_visible(selector(observation_id))
        observation = result.observation
        if (result.status is not EvidenceResolutionStatus.CORROBORATED
                or result.proposition != VISIBLE_SOURCE_OBSERVATION_EXISTS or observation is None
                or str(observation.page_id) != str(plan_page_id) or len(observation.geometry) != 4):
            continue
        primitive = segments.get(str(observation.source_primitive_ref).removeprefix("visible:segment:"))
        if primitive is None or tuple(float(v) for v in observation.geometry) != (
                float(primitive["x1"]), float(primitive["y1"]), float(primitive["x2"]), float(primitive["y2"])):
            continue
        stroke = primitive.get("stroke")
        width = primitive.get("width")
        if not primitive.get("stroke_present") or not primitive.get("width_present") or width is None:
            continue
        x0, y0, x1, y1 = (float(v) for v in observation.geometry)
        ink.append(PlanInkSegment(str(observation_id), x0, y0, x1, y1, float(width),
                                  bool(stroke) and max(stroke) <= 0.1))

    # elevation type records, one resolve per plan mark; display width from the page rotation
    pattern = re.compile(callout_mark_pattern)
    marks = sorted({w.text for w in plan_words if pattern.fullmatch(w.text)})
    producer = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source)
    authority = producer.authority()
    types: list[ElevationTypeObservation] = []
    for mark in marks:
        result = authority.resolve(OpeningElevationFrameAreaSelector(
            ownership.document_id, revision_id, ownership.source_sha256, ownership.snapshot_id, mark))
        record = result.record
        if record is None or type(record) is not OpeningElevationFrameAreaRecord:
            continue
        if str(record.page_id) != str(elevation_page_id) or result.status is not EvidenceResolutionStatus.CORROBORATED:
            continue
        x0, y0, x1, y1 = record.frame_bbox
        panels = [w for w in elevation_words if w.text == panel_token
                  and x0 <= (w.bbox[0] + w.bbox[2]) / 2.0 <= x1 and y0 <= (w.bbox[1] + w.bbox[3]) / 2.0 <= y1]
        width_mm, reason = display_horizontal_width_mm(
            elevation_rotation, record.frame_bbox, float(record.axis_x_mm), float(record.axis_y_mm))
        # the same mark printed elsewhere on the elevation page (a title, a stray tag) is carried as a caveat
        mark_key = _tag_key(str(record.type_mark))
        outside = sum(
            1 for w in elevation_words
            if mark_key is not None and _tag_key(w.text) == mark_key
            and not (x0 <= (w.bbox[0] + w.bbox[2]) / 2.0 <= x1 and y0 <= (w.bbox[1] + w.bbox[3]) / 2.0 <= y1))
        types.append(ElevationTypeObservation(
            type_mark=str(record.type_mark), record_id=str(record.record_id), display_width_mm=width_mm,
            panel_count=len(panels), panel_observation_ids=tuple(sorted(w.observation_id for w in panels)),
            unresolved_reason=reason, outside_frame_mark_count=outside))

    scope = PlanCalloutStripScope(
        ownership=ownership, plan_page_id=str(plan_page_id), elevation_page_id=str(elevation_page_id),
        callout_mark_pattern=callout_mark_pattern, coordinate_quantum_pt=coordinate_quantum_pt,
        dimension_quantum_mm=dimension_quantum_mm, plan_viewports=viewports, elevation_viewport_id=None,
        untrusted_plan_words=tuple(untrusted_plan), plan_viewport_basis=viewport_basis)
    return audit_plan_callout_to_glazing_strip_shadow(scope, ink=ink, words=plan_words, elevation_types=types)


__all__ = [
    "CONDITION_NAMES", "CalloutCorrespondence", "CalloutRing", "ElevationTypeObservation", "FAILED",
    "GlazingStrip", "NOT_EVALUATED", "PASSED", "PLAN_CALLOUT_STRIP_SHADOW_SCHEMA_VERSION",
    "PRODUCER_INPUT_PROVENANCE", "WHOLE_PAGE_UNSEGMENTED", "PlanCalloutStripScope", "PlanCalloutStripShadow", "PlanInkSegment",
    "PlanTextObservation", "PlanViewportRef", "SourceOwnership",
    "audit_plan_callout_to_glazing_strip_from_source", "audit_plan_callout_to_glazing_strip_shadow",
    "display_horizontal_width_mm",
]
