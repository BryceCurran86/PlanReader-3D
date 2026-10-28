"""Default-off, read-only glazing ANATOMY variant inventory, strictly SHADOW.

Question answered, page wide and independent of any callout: for every candidate glazing cell in the
black, continuous, axis-aligned ink of one plan page, which of eight ordered gates does it pass and which
is the FIRST gate it fails?

The merged plan-callout glazing-strip shadow inventories only cells that satisfy gates 1..6 below. This
module re-derives the same snapped-stroke representation (the stroke, snapping and cover logic below is an
adaptation of the helpers in `pb_source_plan_glazing_strip_callout_shadow`, copied rather than imported so
that this module reaches no other shadow) and exposes the gate-by-gate evaluation instead of a filter, so a
reviewer can see which cells that inventory misses and which gate stops them.

Gates, in a fixed order, each `passed` / `failed` / `not_evaluated` (every gate after the first failure is
`not_evaluated`):

  g1_pair_closed_by_end_ticks        two parallel pane lines, both covering the cell, closed by two end ticks
                                     that each span exactly the pair; the cell is longer than the pair is
                                     thick; and it is the INNERMOST thin closed box (a box that encloses
                                     another thin closed box is a container, counted but not a candidate)
  g2_enclosing_frame_lines_exist     a parallel line covering the cell exists on each side of the pair
  g3_frame_deeper_than_cell_is_long  PASSES when the nearest enclosing lines are closer together than the
                                     cell is long (o1 - o0 < b - a); the name keeps the failure wording
  g4_pair_narrower_than_each_rebate  the pair gap is narrower than each rebate
  g5_pair_centred                    the two rebates are equal within two coordinate equalities
  g6_cell_closed_across_full_depth   cross strokes at both cell ends cover the full frame depth
  g7_chains_with_neighbour           chaining is the merged rule (same frame offsets, gap from -eq up to the
                                     frame depth). A cell with no neighbour is a one-panel strip and passes. The
                                     gate fails when the chain is not well formed: two accepted cells with the
                                     same frame offsets overlap, or more than one such cell could be a cell's
                                     predecessor or successor (the merged rule would silently take the later one)
  g8_end_posts_both_present          the chained strip has an end post at both of its ends

A cell is `in_merged_inventory` when it passes g1..g6. Accepted cells are chained exactly as the merged
module chains them into strips. g7 and g8 never remove a cell from that set; they annotate it.

Standing limits that a reader must not lose:

* The frame lines are the merged rule's NEAREST parallel lines that cover the cell. That is the merged module's
  definition (and the acceptance equality depends on it), not a tie-break, but a farther covering line is a
  plausible rival frame; the next one on each side is kept in `CellCandidate.frame_rivals` and never used.
  Likewise an end post width is the merged rule's last matching stroke piece; every distinct matching width is
  kept in `AnatomyStrip.end_post_alternatives`.
* A gate after the first failure is `not_evaluated`, so "near miss" (first failed gate is g6 or g8) knows only
  that gate: for g6 it cannot say that g7 and g8 would have passed. A g8 near miss passes g1..g6 and is IN the
  merged inventory; only a g6 near miss is a cell that inventory misses.
* Ink is black when every stroke channel is at most 0.1 and the stroke is not fully transparent (the merged
  adapter's convention), continuous when its dash array is solid, and grouped by its own exact stroke width.
* The adapter re-resolves every published visible observation through the producer's own authority, exactly as
  the merged adapter does. That call fills the producer store's `verified_resolution_cache` memo (the same memo any
  consumer fills); nothing else of the producer is touched, and no opening authority is built or called.

A candidate needs at least one end tick spanning exactly two parallel lines that both cover the tick. Pairs
of lines with no such tick are not enumerated (stated as a standing limit). A candidate whose second tick is
missing is a half-open cell: it fails g1 and nothing later is evaluated.

Inventory mode: each accepted strip reports the id of the one RESOLVED floor-plan viewport that contains
it (or None), but this module never abstains on a missing, ambiguous or non-containing viewport.

Verdict: CANDIDATE when at least one cell is accepted, else ABSTAINED. Published ink the producer could not
verify, or a disagreement with the in-module copy of the merged rule, also ABSTAINS (the lists stay attached as
data about the verified ink only). Work bounds on the ink count and the candidate count abstain with typed reasons.

It decides nothing about windows: it grants no physical opening, host, kind, frame, scale, metric, count,
quantity or customer output, it never produces a `PhysicalOpeningExistenceRecord`, it never calls the
physical-opening authority, and it imports nothing from the live issuer, the schedule binder, the host
binder, the opening count producer or any live quantity code. Verdicts are CANDIDATE or ABSTAINED only.
"""
from __future__ import annotations

import hashlib
import math
import re
from bisect import bisect_left, bisect_right
from collections import defaultdict
from dataclasses import dataclass, fields
from typing import Callable, Iterable, Optional, Sequence

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
    VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

GLAZING_ANATOMY_INVENTORY_SCHEMA_VERSION = "1.0.0"
INVENTORY_METHOD = "glazing_anatomy_inventory_shadow"

PASSED = "passed"
FAILED = "failed"
NOT_EVALUATED = "not_evaluated"
_STATES = (PASSED, FAILED, NOT_EVALUATED)

GATE_NAMES = (
    "g1_pair_closed_by_end_ticks",
    "g2_enclosing_frame_lines_exist",
    "g3_frame_deeper_than_cell_is_long",
    "g4_pair_narrower_than_each_rebate",
    "g5_pair_centred",
    "g6_cell_closed_across_full_depth",
    "g7_chains_with_neighbour",
    "g8_end_posts_both_present",
)
MERGED_RULE_GATE_COUNT = 6
NEAR_MISS_GATES = ("g6_cell_closed_across_full_depth", "g8_end_posts_both_present")
ALL_GATES_PASSED = "all_gates_passed"
GATE_DESCRIPTIONS = {
    GATE_NAMES[0]: "two parallel lines covering the cell, closed by two end ticks spanning exactly the pair, "
                   "cell longer than the pair is thick, innermost thin closed box",
    GATE_NAMES[1]: "a covering parallel line exists on each side of the pair",
    GATE_NAMES[2]: "PASSES when o1 - o0 < b - a (the frame is not deeper than the cell is long)",
    GATE_NAMES[3]: "pair gap narrower than each rebate",
    GATE_NAMES[4]: "rebates equal within two coordinate equalities",
    GATE_NAMES[5]: "cross strokes at both cell ends cover the full frame depth",
    GATE_NAMES[6]: "no overlapping accepted cell with the same frame offsets (chaining as the merged rule)",
    GATE_NAMES[7]: "the chained strip has an end post at both ends",
}

CLOSURE_BOTH = "both_end_ticks"
CLOSURE_LO_MISSING = "lo_end_tick_missing"
CLOSURE_HI_MISSING = "hi_end_tick_missing"
_CLOSURES = (CLOSURE_BOTH, CLOSURE_LO_MISSING, CLOSURE_HI_MISSING)

# assessment-local reason codes
INVENTORY_DISABLED = "glazing_anatomy_inventory_disabled"
INK_BUDGET_EXCEEDED = "glazing_anatomy_ink_budget_exceeded"
CANDIDATE_BUDGET_EXCEEDED = "glazing_anatomy_candidate_budget_exceeded"
ACCEPTED_CELLS_PRESENT = "glazing_anatomy_accepted_cells_present"
NO_ACCEPTED_CELL = "glazing_anatomy_no_accepted_cell"
SELF_CHECK_DISAGREES = "glazing_anatomy_self_check_disagrees_with_merged_rule_copy"
INK_UNVERIFIED = "glazing_anatomy_visible_ink_not_verified_against_primitive"
# cell-level details of a failed g7
OVERLAP_DETAIL = "overlaps_accepted_cell_with_the_same_frame_offsets"
AMBIGUOUS_NEIGHBOUR_DETAIL = "more_than_one_same_frame_neighbour_within_the_frame_depth"
# the only new strings besides the reason codes: standing capability limits, never atom kinds
INVENTORY_NOT_WINDOW_EXISTENCE = "glazing_anatomy_inventory_is_not_window_existence"
PAIRS_WITHOUT_ANY_END_TICK_NOT_ENUMERATED = "glazing_anatomy_pairs_without_any_end_tick_not_enumerated"
VIEWPORT_REPORTED_NOT_GATING = "glazing_anatomy_viewport_reported_not_gating"
FRAME_IS_NEAREST_COVERING_LINE_RIVALS_REPORTED = "glazing_anatomy_frame_is_nearest_covering_line_rivals_reported"
NEAR_MISS_KNOWS_ONLY_THE_FIRST_FAILED_GATE = "glazing_anatomy_near_miss_knows_only_the_first_failed_gate"
STANDING_LIMITS = (INVENTORY_NOT_WINDOW_EXISTENCE, PAIRS_WITHOUT_ANY_END_TICK_NOT_ENUMERATED,
                   VIEWPORT_REPORTED_NOT_GATING, FRAME_IS_NEAREST_COVERING_LINE_RIVALS_REPORTED,
                   NEAR_MISS_KNOWS_ONLY_THE_FIRST_FAILED_GATE)

# Source coordinates sit on a lattice whose spacing is the page's coordinate quantum; two coordinates closer
# than a quarter of it are the same coordinate. This is identity of drawn geometry, not a distance threshold.
_EQ_FRACTION_OF_QUANTUM = 0.25
# Work bounds. They stop a pathological page from being analysed; they decide nothing.
_MAX_INK = 200_000
_MAX_CANDIDATES = 100_000
# The in-module copy of the merged pane-box rule is quadratic; it is run only below this many closed boxes.
_SELF_CHECK_MAX_BOXES = 2_000
# A post between two panels of one strip is narrower than the strip's own frame depth.
_MAX_CHAIN_GAP_DEPTHS = 1.0

_STATUSES = (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED)

_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted", "scale_granted",
    "metric_granted", "count_granted", "quantity_granted", "wall_binding_granted",
    "commercial_projection_allowed", "customer_publication_granted", "takeoff_eligible",
    "deduction_authority", "existence_record_issued",
)


# --------------------------------------------------------------------------------------
# records
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class AnatomyOwnership:
    """Who owns the page this inventory describes; the adapter derives it from the producer, never from a caller."""

    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str

    def __post_init__(self) -> None:
        values = (self.document_id, self.revision_id, self.snapshot_id, self.source_sha256, self.page_id)
        if any(type(v) is not str or not v for v in values):
            raise ValueError("ownership needs non-empty document, revision, snapshot, source hash and page ids")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source_sha256):
            raise ValueError("the source hash must be a SHA-256 hex digest")


@dataclass(frozen=True)
class InkSegment:
    """One visible, stroked source segment of the page (native page coordinates)."""

    ink_id: str
    x0: float
    y0: float
    x1: float
    y1: float
    width: float
    black: bool
    continuous_opaque: bool = True

    def __post_init__(self) -> None:
        if type(self.black) is not bool or type(self.continuous_opaque) is not bool:
            raise ValueError("ink colour and positive stroke coverage require explicit bools")


@dataclass(frozen=True)
class ViewportRef:
    view_id: str
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class CellCandidate:
    ownership: AnatomyOwnership
    candidate_id: str
    axis: str                                           # direction of the pane pair's lines: "H" | "V"
    stroke_width: float
    pair: tuple[float, float]                           # across offsets (p, q) of the two parallel lines
    along: tuple[float, float]                          # (a, b) along the lines
    closure: str
    gates: tuple[tuple[str, str], ...]
    first_failed_gate: Optional[str]
    detail: tuple[str, ...]
    frame_offsets: Optional[tuple[float, float]]        # (o0, o1) once g2 passed: the NEAREST covering lines
    frame_rivals: Optional[tuple[Optional[float], Optional[float]]]   # next covering line beyond (o0, o1), kept as data
    rebates: Optional[tuple[float, float]]              # (side0, side1) once g2 passed
    cross_closed: Optional[tuple[bool, bool]]           # (lo, hi) cell-end cross strokes, once g5 passed
    end_post_widths: Optional[tuple[Optional[float], Optional[float]]]
    chain_panel_count: Optional[int]
    strip_id: Optional[str]
    in_merged_inventory: bool                           # passes g1..g6
    near_miss: bool                                     # first failed gate is g6 or g8
    ink_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.closure not in _CLOSURES:
            raise ValueError("unknown closure")
        if tuple(name for name, _ in self.gates) != GATE_NAMES or any(s not in _STATES for _, s in self.gates):
            raise ValueError("a cell carries exactly the complete, ordered gate set")
        states = [s for _, s in self.gates]
        failed = [i for i, s in enumerate(states) if s == FAILED]
        if len(failed) > 1:
            raise ValueError("at most one gate can be the first failure")
        if failed:
            index = failed[0]
            if (any(s != PASSED for s in states[:index]) or any(s != NOT_EVALUATED for s in states[index + 1:])):
                raise ValueError("gates after the first failure are not evaluated")
            expected = GATE_NAMES[index]
        else:
            if any(s != PASSED for s in states):
                raise ValueError("a cell with no failed gate passed every gate")
            expected = None
        if self.first_failed_gate != expected:
            raise ValueError("first failed gate disagrees with the gate states")
        if self.in_merged_inventory != all(s == PASSED for s in states[:MERGED_RULE_GATE_COUNT]):
            raise ValueError("merged-inventory membership is gates 1..6 passed")
        if self.near_miss != (self.first_failed_gate in NEAR_MISS_GATES):
            raise ValueError("near miss means the first failed gate is g6 or g8")


@dataclass(frozen=True)
class AnatomyStrip:
    ownership: AnatomyOwnership
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
    end_post_alternatives: tuple[tuple[float, ...], tuple[float, ...]]   # every distinct matching piece per end
    extent_complete: bool
    stroke_width: float
    viewport_id: Optional[str]                          # reported, never gating
    ink_ids: tuple[str, ...]
    cell_ids: tuple[str, ...]
    full_anatomy: bool                                  # every cell passes g1..g8
    merged_rule_copy_agrees: Optional[bool]             # None: the quadratic self check was not run

    def __post_init__(self) -> None:
        if self.panel_count != len(self.panel_lengths) or self.panel_count != len(self.cell_ids):
            raise ValueError("a strip carries one length and one cell per panel")
        if any((end is None) != (not alternatives)
               for end, alternatives in zip(self.end_post_widths, self.end_post_alternatives)):
            raise ValueError("an end post width is present exactly when an end post piece was found")


@dataclass(frozen=True)
class WidthClassSummary:
    stroke_width: float
    ink_count: int
    candidate_count: int
    container_box_count: int
    short_pair_count: int
    accepted_cell_count: int
    strip_count: int
    first_failed_gate_histogram: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class GlazingAnatomyInventory:
    ownership: Optional[AnatomyOwnership]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    coordinate_quantum_pt: Optional[float]
    ink_count: int
    unverified_ink_count: int
    width_classes: tuple[WidthClassSummary, ...]
    candidates: tuple[CellCandidate, ...]
    strips: tuple[AnatomyStrip, ...]
    near_misses: tuple[CellCandidate, ...]
    first_failed_gate_histogram: tuple[tuple[str, int], ...]
    container_box_count: int
    short_pair_count: int
    evidence_atoms: tuple[EvidenceAtom, ...]
    record_id: Optional[str]
    shadow_only: bool = True
    physical_opening_granted: bool = False
    host_granted: bool = False
    opening_kind_granted: bool = False
    frame_granted: bool = False
    scale_granted: bool = False
    metric_granted: bool = False
    count_granted: bool = False
    quantity_granted: bool = False
    wall_binding_granted: bool = False
    commercial_projection_allowed: bool = False
    customer_publication_granted: bool = False
    takeoff_eligible: bool = False
    deduction_authority: bool = False
    existence_record_issued: bool = False
    schema_version: str = GLAZING_ANATOMY_INVENTORY_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("a glazing anatomy inventory cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"a glazing anatomy inventory cannot grant {name}")
        if self.status not in _STATUSES:
            raise ValueError("a glazing anatomy inventory is CANDIDATE or ABSTAINED only")
        if any(atom.status not in _STATUSES for atom in self.evidence_atoms):
            raise ValueError("evidence atoms are CANDIDATE or ABSTAINED only")
        if self.status is EvidenceResolutionStatus.CANDIDATE:
            if (not self.strips or any(s.merged_rule_copy_agrees is False for s in self.strips)
                    or self.unverified_ink_count or {SELF_CHECK_DISAGREES, INK_UNVERIFIED} & set(self.reason_codes)):
                raise ValueError("a CANDIDATE needs an accepted strip, verified ink and no self-check disagreement")
        if any(record.ownership != self.ownership for record in (*self.candidates, *self.strips)):
            raise ValueError("every record carries the ownership of the inventory that holds it")
        if self.near_misses != tuple(c for c in self.candidates if c.near_miss):
            raise ValueError("near misses are exactly the candidates whose first failed gate is g6 or g8")
        if sum(count for _, count in self.first_failed_gate_histogram) != len(self.candidates):
            raise ValueError("the histogram counts every candidate once")
        if not set(_GRANT_FLAGS) <= {f.name for f in fields(self)}:
            raise ValueError("grant flag set is out of date")


# --------------------------------------------------------------------------------------
# ink: exact-width classes on a snapped coordinate grid
# (adapted from the merged plan-callout glazing-strip shadow; copied, not imported)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Stroke:
    axis: str            # "H" or "V"
    offset: float        # coordinate across the line
    lo: float            # along-axis start
    hi: float            # along-axis end
    ink_id: str


def _snapper(values: Iterable[float], eq: float) -> Callable[[float], float]:
    """Map values within the coordinate equality onto a representative (order independent)."""
    representative: dict[float, float] = {}
    start: Optional[float] = None
    for value in sorted(set(values)):
        if start is None or value - start > eq:
            start = value
        representative[value] = start  # type: ignore[assignment]
    return representative.__getitem__


def _axis_aligned(ink: Sequence[InkSegment], eq: float) -> dict[float, list[_Stroke]]:
    """Black, continuous, axis-aligned strokes grouped by their own exact stroke width."""
    raw: dict[float, list[tuple[str, float, float, float, str]]] = defaultdict(list)
    for s in ink:
        if (not s.black or not s.continuous_opaque or s.width <= 0.
                or not all(math.isfinite(v) for v in (s.x0, s.y0, s.x1, s.y1, s.width))):
            continue
        key = float(s.width)
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


class _Cover:
    """Union of collinear stroke pieces at one offset (invariant to splitting and double ink)."""

    __slots__ = ("spans", "pieces", "eq", "_los")

    def __init__(self, spans, pieces, eq):
        self.spans = spans
        self.pieces = pieces
        self.eq = eq
        self._los = [lo for lo, _ in spans]

    def covers(self, lo: float, hi: float) -> bool:
        # spans are disjoint and sorted: only the last span starting at or before lo can cover [lo, hi]
        i = bisect_right(self._los, lo + self.eq) - 1
        return i >= 0 and hi <= self.spans[i][1] + self.eq

    def ink_in(self, lo: float, hi: float) -> set[str]:
        return {q for a, b, q in self.pieces if b >= lo - self.eq and a <= hi + self.eq}

    def contained_ink(self, lo: float, hi: float) -> set[str]:
        return {q for a, b, q in self.pieces if a >= lo - self.eq and b <= hi + self.eq}


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


# --------------------------------------------------------------------------------------
# candidate enumeration
# --------------------------------------------------------------------------------------


def _tick_ranges(strokes: Sequence[_Stroke], other: str, crosses: dict[float, _Cover],
                 eq: float) -> dict[tuple[float, float], set[float]]:
    """An end tick is a stroke, or the collinear union of strokes, perpendicular to the pane lines.

    Keyed by the exact (low, high) across-extent it spans; the value is every along-position holding one."""
    ranges: dict[tuple[float, float], set[float]] = defaultdict(set)
    for s in strokes:
        if s.axis == other and s.hi - s.lo > eq:
            ranges[(s.lo, s.hi)].add(s.offset)
    for offset, cover in crosses.items():
        for lo, hi in cover.spans:
            if hi - lo > eq:
                ranges[(lo, hi)].add(offset)
    return ranges


def _lanes(lp: _Cover, lq: _Cover, eq: float) -> list[tuple[float, float]]:
    """Maximal along-intervals covered by both lines of a pair."""
    out: list[tuple[float, float]] = []
    i = j = 0
    a_spans, b_spans = lp.spans, lq.spans
    while i < len(a_spans) and j < len(b_spans):
        lo = max(a_spans[i][0], b_spans[j][0])
        hi = min(a_spans[i][1], b_spans[j][1])
        if hi - lo > eq:
            out.append((lo, hi))
        if a_spans[i][1] < b_spans[j][1]:
            i += 1
        else:
            j += 1
    return out


def _enumerate_pairs(lines: dict[float, _Cover], ranges: dict[tuple[float, float], set[float]], eq: float):
    """Closed thin boxes, half-open cells (one end tick missing) and the count of too-short tick pairs."""
    closed: list[dict] = []
    openers: list[dict] = []
    short = 0
    for (p, q) in sorted(ranges):
        lp, lq = lines.get(p), lines.get(q)
        if lp is None or lq is None:
            continue
        thick = q - p
        positions = sorted(ranges[(p, q)])
        for a, b in zip(positions, positions[1:]):
            if not (lp.covers(a, b) and lq.covers(a, b)):
                continue
            if b - a <= thick:                    # a pane is longer than it is thick
                short += 1
                continue
            closed.append({"a": a, "b": b, "p": p, "q": q})
        for lo, hi in _lanes(lp, lq, eq):
            inside = [t for t in positions if lo - eq <= t <= hi + eq]
            if not inside:
                continue
            if inside[0] - lo > thick:
                openers.append({"a": lo, "b": inside[0], "p": p, "q": q, "lane": (lo, hi),
                                "closure": CLOSURE_LO_MISSING})
            if hi - inside[-1] > thick:
                openers.append({"a": inside[-1], "b": hi, "p": p, "q": q, "lane": (lo, hi),
                                "closure": CLOSURE_HI_MISSING})
    return closed, openers, short


def _sorted_boxes(boxes: Sequence[dict]):
    order = sorted(boxes, key=lambda x: (x["a"], x["b"], x["p"], x["q"]))
    return order, [x["a"] for x in order]


def _split_innermost(boxes: Sequence[dict], eq: float):
    """A pane is the INNERMOST thin box: the frame outline drawn around it is also a closed box."""
    order, starts = _sorted_boxes(boxes)
    inner: list[dict] = []
    outer: list[dict] = []
    for x in order:
        i = bisect_left(starts, x["a"] - eq)
        j = bisect_right(starts, x["b"] + eq)
        contains = any(y is not x and y["b"] <= x["b"] + eq and x["p"] + eq < y["p"] and y["q"] < x["q"] - eq
                       for y in order[i:j])
        (outer if contains else inner).append(x)
    return inner, outer


def _lane_encloses_a_box(opener: dict, order: Sequence[dict], starts: Sequence[float], eq: float) -> bool:
    """Is the lane of a half-open cell the frame lane of a thin closed box? (Then it is a frame, not a pane.)"""
    lo, hi = opener["lane"]
    i = bisect_left(starts, lo - eq)
    j = bisect_right(starts, hi + eq)
    return any(y["b"] <= hi + eq and opener["p"] + eq < y["p"] and y["q"] < opener["q"] - eq
               for y in order[i:j])


def _nearest_below(offsets: Sequence[float], lines: dict[float, _Cover], p: float, a: float, b: float,
                   eq: float) -> Optional[float]:
    """The frame line of the merged rule: the nearest parallel line below the pair that covers the cell."""
    for k in range(bisect_left(offsets, p - eq) - 1, -1, -1):
        if lines[offsets[k]].covers(a, b):
            return offsets[k]
    return None


def _nearest_above(offsets: Sequence[float], lines: dict[float, _Cover], q: float, a: float, b: float,
                   eq: float) -> Optional[float]:
    for k in range(bisect_right(offsets, q + eq), len(offsets)):
        if lines[offsets[k]].covers(a, b):
            return offsets[k]
    return None


def _farther_rival(offsets: Sequence[float], lines: dict[float, _Cover], chosen: float, a: float, b: float,
                   eq: float, *, below: bool) -> Optional[float]:
    """The next covering line beyond the chosen frame line, kept as data: choosing the nearest covering line is
    the merged module's definition of the frame, but a farther covering line is a plausible rival frame and is
    retained, never used."""
    if below:
        for k in range(bisect_left(offsets, chosen - eq) - 1, -1, -1):
            if lines[offsets[k]].covers(a, b):
                return offsets[k]
        return None
    for k in range(bisect_right(offsets, chosen + eq), len(offsets)):
        if lines[offsets[k]].covers(a, b):
            return offsets[k]
    return None


def _distinct(values: Iterable[float], eq: float) -> tuple[float, ...]:
    """Distinct values under the coordinate equality (bounded-diameter clusters on the sorted values)."""
    out: list[float] = []
    for value in sorted(values):
        if not out or value - out[-1] > eq:
            out.append(value)
    return tuple(out)


# --------------------------------------------------------------------------------------
# gate evaluation
# --------------------------------------------------------------------------------------


def _new_cell(axis: str, width: float, box: dict, closure: str) -> dict:
    return {"axis": axis, "width": width, "p": box["p"], "q": box["q"], "a": box["a"], "b": box["b"],
            "closure": closure, "fail": None, "detail": [], "frame": None, "rivals": None, "rebates": None,
            "cross_closed": None, "ends": None, "chain_count": None, "strip_key": None, "ink": ()}


def _cell_ink(cell: dict, lines: dict[float, _Cover], crosses: dict[float, _Cover], eq: float) -> tuple[str, ...]:
    a, b, p, q = cell["a"], cell["b"], cell["p"], cell["q"]
    ink = set(lines[p].ink_in(a, b)) | set(lines[q].ink_in(a, b))
    for position in (a, b):
        cover = crosses.get(position)
        if cover is not None:
            ink |= cover.contained_ink(p, q)
    return tuple(sorted(ink))


def _evaluate_box(cell: dict, offsets: Sequence[float], lines: dict[float, _Cover],
                  crosses: dict[float, _Cover], eq: float) -> None:
    """Gates 2..6 for one innermost closed box; sets `fail` to the index of the first failed gate."""
    a, b, p, q = cell["a"], cell["b"], cell["p"], cell["q"]
    o0 = _nearest_below(offsets, lines, p, a, b, eq)
    o1 = _nearest_above(offsets, lines, q, a, b, eq)
    if o0 is None or o1 is None:
        cell["fail"] = 1
        cell["detail"] = (["no_enclosing_line_below"] if o0 is None else []) + \
                         (["no_enclosing_line_above"] if o1 is None else [])
        return
    cell["frame"] = (o0, o1)
    cell["rivals"] = (_farther_rival(offsets, lines, o0, a, b, eq, below=True),
                      _farther_rival(offsets, lines, o1, a, b, eq, below=False))
    inner, side0, side1 = q - p, p - o0, o1 - q
    cell["rebates"] = (side0, side1)
    if not (o1 - o0 < b - a):
        cell["fail"] = 2
        cell["detail"] = ["frame_not_shallower_than_cell_is_long"]
        return
    if not (inner < side0 - eq and inner < side1 - eq):
        cell["fail"] = 3
        cell["detail"] = ["pair_not_narrower_than_each_rebate"]
        return
    if abs(side0 - side1) > 2.0 * eq:
        cell["fail"] = 4
        cell["detail"] = ["pair_not_centred"]
        return
    ca, cb = crosses.get(a), crosses.get(b)
    closed_lo = ca is not None and ca.covers(o0, o1)
    closed_hi = cb is not None and cb.covers(o0, o1)
    cell["cross_closed"] = (closed_lo, closed_hi)
    if not (closed_lo and closed_hi):
        cell["fail"] = 5
        cell["detail"] = (["lo_cell_end_not_closed_across_depth"] if not closed_lo else []) + \
                         (["hi_cell_end_not_closed_across_depth"] if not closed_hi else [])


def _chain(members: list[dict], depth: float, eq: float) -> list[list[dict]]:
    runs: list[list[dict]] = []
    for m in members:
        if runs and -eq <= m["a"] - runs[-1][-1]["b"] <= depth * _MAX_CHAIN_GAP_DEPTHS:
            runs[-1].append(m)
        else:
            runs.append([m])
    return runs


def _chain_conflicts(members: Sequence[dict], depth: float, eq: float) -> dict[int, list[str]]:
    """Accepted cells whose place in a chain is not well formed, by member index.

    The chain itself is built exactly as the merged module builds it: in position order, a cell joins the run it
    follows. That resolves an ambiguity silently, so the ambiguity is reported here and fails g7: a cell overlaps
    another accepted cell with the same frame offsets, or more than one such cell could be its predecessor or its
    successor within the frame depth. Both cells of an overlap and every cell with a rival neighbour are flagged."""
    limit = depth * _MAX_CHAIN_GAP_DEPTHS
    overlapped: set[int] = set()
    predecessors: dict[int, int] = defaultdict(int)
    successors: dict[int, int] = defaultdict(int)
    for i, x in enumerate(members):
        for j in range(i + 1, len(members)):
            y = members[j]
            gap = y["a"] - x["b"]
            if gap > limit:          # members are in position order: no later cell can be within the depth either
                break
            if gap >= -eq:
                successors[i] += 1
                predecessors[j] += 1
            elif min(x["b"], y["b"]) - y["a"] > eq:
                overlapped.add(i)
                overlapped.add(j)
    flagged: dict[int, list[str]] = {}
    for index in range(len(members)):
        reasons = []
        if index in overlapped:
            reasons.append(OVERLAP_DETAIL)
        if predecessors[index] > 1 or successors[index] > 1:
            reasons.append(AMBIGUOUS_NEIGHBOUR_DETAIL)
        if reasons:
            flagged[index] = reasons
    return flagged


def _build_strips(cells: list[dict], lines: dict[float, _Cover], strokes: Sequence[_Stroke], axis: str,
                  width: float, eq: float) -> list[dict]:
    """Chain the cells that pass g1..g6 exactly as the merged module does; set g7 / g8 on each cell."""
    other = "V" if axis == "H" else "H"
    cross_sorted = sorted((s for s in strokes if s.axis == other), key=lambda s: (s.offset, s.lo, s.hi, s.ink_id))
    cross_offsets = [s.offset for s in cross_sorted]
    groups: dict[tuple[float, float], list[dict]] = defaultdict(list)
    for cell in cells:
        if cell["fail"] is None:
            groups[cell["frame"]].append(cell)
    strips: list[dict] = []
    for (o0, o1) in sorted(groups):
        members = sorted(groups[(o0, o1)], key=lambda m: (m["a"], m["b"], m["p"], m["q"]))
        depth = o1 - o0
        conflicts = _chain_conflicts(members, depth, eq)
        for index, m in enumerate(members):
            m["conflict"] = conflicts.get(index, [])
        for run in _chain(members, depth, eq):
            lo, hi = run[0]["a"], run[-1]["b"]
            inner_posts = tuple(y["a"] - x["b"] for x, y in zip(run, run[1:]))
            ends: list[Optional[float]] = []
            alternatives: list[tuple[float, ...]] = []
            for side in ("lo", "hi"):
                matches: list[float] = []
                for off in (o0, o1):
                    for a_, b_, _id in lines[off].pieces:
                        piece = b_ - a_
                        if not (eq < piece <= depth):
                            continue
                        if (side == "lo" and abs(b_ - lo) <= eq) or (side == "hi" and abs(a_ - hi) <= eq):
                            matches.append(piece)
                # the merged rule reports the last matching piece; every distinct width is kept beside it
                ends.append(matches[-1] if matches else None)
                alternatives.append(_distinct(matches, eq))
            ink: set[str] = set()
            for m in run:
                for off in (o0, m["p"], m["q"], o1):
                    ink |= lines[off].ink_in(m["a"], m["b"])
            first, last = bisect_left(cross_offsets, lo - eq), bisect_right(cross_offsets, hi + eq)
            for s in cross_sorted[first:last]:
                if s.lo >= o0 - eq and s.hi <= o1 + eq:
                    ink.add(s.ink_id)
            strip = {"axis": axis, "width": width, "band": (o0, o1), "depth": depth, "along": (lo, hi),
                     "frame_along": (lo - (ends[0] or 0.0), hi + (ends[1] or 0.0)), "run": run,
                     "panel_lengths": tuple(m["b"] - m["a"] for m in run), "inner_posts": inner_posts,
                     "ends": (ends[0], ends[1]), "alternatives": (alternatives[0], alternatives[1]),
                     "extent_complete": ends[0] is not None and ends[1] is not None,
                     "ink": tuple(sorted(ink))}
            strips.append(strip)
            for m in run:
                m["chain_count"] = len(run)
                m["ends"] = strip["ends"]
                m["strip_key"] = len(strips) - 1
                if m["conflict"]:
                    m["fail"] = 6
                    m["detail"] = list(m["conflict"])
                elif not strip["extent_complete"]:
                    m["fail"] = 7
                    missing_ends = (["lo_end_post_missing"] if ends[0] is None else [],
                                    ["hi_end_post_missing"] if ends[1] is None else [])
                    m["detail"] = missing_ends[0] + missing_ends[1]
    return strips


def _reference_panels(strokes: Sequence[_Stroke], axis: str, eq: float, lines: dict[float, _Cover]):
    """In-module copy of the merged module's pane-box rule and per-box filters, for a consistency check.

    Adapted from `_pane_boxes` and the first half of `_glazing_strips` of the merged plan-callout shadow, in
    the merged module's own form. Returns the set of (a, b, p, q, o0, o1) it accepts, or None when the page is
    too large for its quadratic innermost test."""
    other = "V" if axis == "H" else "H"
    crosses = _covers_by_offset(strokes, other, eq)
    ranges: dict[tuple[float, float], set[float]] = defaultdict(set)
    for s in strokes:
        if s.axis == other and s.hi - s.lo > eq:
            ranges[(s.lo, s.hi)].add(s.offset)
    for offset, cover in crosses.items():
        for lo, hi in cover.spans:
            if hi - lo > eq:
                ranges[(lo, hi)].add(offset)
    boxes: list[dict] = []
    for (p, q), offsets_ in ranges.items():
        along_positions = sorted(offsets_)
        for a, b in zip(along_positions, along_positions[1:]):
            if b - a <= q - p:
                continue
            lp, lq = lines.get(p), lines.get(q)
            if lp is None or lq is None or not (lp.covers(a, b) and lq.covers(a, b)):
                continue
            boxes.append({"a": a, "b": b, "p": p, "q": q})
    if len(boxes) > _SELF_CHECK_MAX_BOXES:
        return None
    boxes = [x for x in boxes
             if not any(y is not x and x["a"] - eq <= y["a"] and y["b"] <= x["b"] + eq
                        and x["p"] + eq < y["p"] and y["q"] < x["q"] - eq for y in boxes)]
    offsets = sorted(lines)
    accepted: set[tuple] = set()
    for box in boxes:
        a, b, p, q = box["a"], box["b"], box["p"], box["q"]
        below = [o for o in offsets if o < p - eq and lines[o].covers(a, b)]
        above = [o for o in offsets if o > q + eq and lines[o].covers(a, b)]
        if not below or not above:
            continue
        o0, o1 = max(below), min(above)
        if o1 - o0 >= b - a:
            continue
        inner, side0, side1 = q - p, p - o0, o1 - q
        if not (inner < side0 - eq and inner < side1 - eq):
            continue
        if abs(side0 - side1) > 2.0 * eq:
            continue
        ca, cb = crosses.get(a), crosses.get(b)
        if ca is None or cb is None or not (ca.covers(o0, o1) and cb.covers(o0, o1)):
            continue
        accepted.add((a, b, p, q, o0, o1))
    return accepted


# --------------------------------------------------------------------------------------
# pure core
# --------------------------------------------------------------------------------------


def _gate_states(fail: Optional[int]) -> tuple[tuple[str, str], ...]:
    out = []
    for index, name in enumerate(GATE_NAMES):
        if fail is None or index < fail:
            out.append((name, PASSED))
        elif index == fail:
            out.append((name, FAILED))
        else:
            out.append((name, NOT_EVALUATED))
    return tuple(out)


def _histogram(candidates: Iterable[CellCandidate]) -> tuple[tuple[str, int], ...]:
    counts = {name: 0 for name in (*GATE_NAMES, ALL_GATES_PASSED)}
    for c in candidates:
        counts[c.first_failed_gate or ALL_GATES_PASSED] += 1
    return tuple(counts.items())


def _viewport_of(box: tuple[float, float, float, float], viewports: Sequence[ViewportRef]) -> Optional[str]:
    holders = [v.view_id for v in viewports
               if v.bbox[0] <= box[0] and v.bbox[1] <= box[1] and box[2] <= v.bbox[2] and box[3] <= v.bbox[3]]
    return holders[0] if len(holders) == 1 else None


def _empty(status: EvidenceResolutionStatus, reasons: Sequence[str], *, ownership: Optional[AnatomyOwnership] = None,
           quantum: Optional[float] = None, ink_count: int = 0, unverified: int = 0) -> GlazingAnatomyInventory:
    return GlazingAnatomyInventory(
        ownership=ownership, status=status, reason_codes=tuple(reasons), standing_limits=STANDING_LIMITS,
        coordinate_quantum_pt=quantum, ink_count=ink_count, unverified_ink_count=unverified, width_classes=(),
        candidates=(), strips=(), near_misses=(), first_failed_gate_histogram=_histogram(()),
        container_box_count=0, short_pair_count=0, evidence_atoms=(), record_id=None)


def inventory_glazing_anatomy(
    *, ownership: AnatomyOwnership, ink: Sequence[InkSegment], viewports: Sequence[ViewportRef],
    coordinate_quantum_pt: float, unverified_ink_count: int = 0,
) -> GlazingAnatomyInventory:
    """Pure core over records the adapter has already re-derived from the producer.

    `viewports` are the RESOLVED floor-plan viewports of the page; they are only reported, never gating."""
    if not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0.0
            and math.isfinite(coordinate_quantum_pt)):
        raise ValueError("a positive finite coordinate quantum is required")
    ABSTAIN, CANDIDATE = EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CANDIDATE
    quantum = float(coordinate_quantum_pt)
    eq = quantum * _EQ_FRACTION_OF_QUANTUM
    if len(ink) > _MAX_INK:
        return _empty(ABSTAIN, (INK_BUDGET_EXCEEDED,), ownership=ownership, quantum=quantum, ink_count=len(ink),
                      unverified=unverified_ink_count)
    root = (ownership.document_id, ownership.revision_id, ownership.snapshot_id, ownership.source_sha256,
            ownership.page_id)
    classes = _axis_aligned(ink, eq)

    # 1. enumerate, with the work bound enforced before anything is evaluated
    plans: list[dict] = []
    total = 0
    for width in sorted(classes):
        strokes = classes[width]
        for axis in ("H", "V"):
            other = "V" if axis == "H" else "H"
            lines = _covers_by_offset(strokes, axis, eq)
            crosses = _covers_by_offset(strokes, other, eq)
            ranges = _tick_ranges(strokes, other, crosses, eq)
            closed, openers, short = _enumerate_pairs(lines, ranges, eq)
            # the work bound is enforced on everything enumerated, before the quadratic innermost test runs
            if total + len(closed) + len(openers) > _MAX_CANDIDATES:
                return _empty(ABSTAIN, (CANDIDATE_BUDGET_EXCEEDED,), ownership=ownership, quantum=quantum,
                              ink_count=len(ink), unverified=unverified_ink_count)
            inner, outer = _split_innermost(closed, eq)
            order, starts = _sorted_boxes(closed)
            openers = [o for o in openers if not _lane_encloses_a_box(o, order, starts, eq)]
            total += len(inner) + len(openers)
            plans.append({"width": width, "axis": axis, "strokes": strokes, "lines": lines, "crosses": crosses,
                          "inner": inner, "outer": outer, "openers": openers, "short": short})

    # 2. evaluate the gates; chain the accepted cells; check them against the in-module copy of the merged rule
    built: list[dict] = []
    reference_disagrees = False
    for plan in plans:
        width, axis, lines, crosses = plan["width"], plan["axis"], plan["lines"], plan["crosses"]
        offsets = sorted(lines)
        cells: list[dict] = []
        for box in plan["inner"]:
            cell = _new_cell(axis, width, box, CLOSURE_BOTH)
            _evaluate_box(cell, offsets, lines, crosses, eq)
            cells.append(cell)
        for opener in plan["openers"]:
            cell = _new_cell(axis, width, opener, opener["closure"])
            cell["fail"] = 0
            cell["detail"] = [opener["closure"]]
            cells.append(cell)
        for cell in cells:
            cell["ink"] = _cell_ink(cell, lines, crosses, eq)
        accepted_keys = {(c["a"], c["b"], c["p"], c["q"], *c["frame"]) for c in cells
                         if c["fail"] is None}
        strips = _build_strips(cells, lines, plan["strokes"], axis, width, eq)
        reference = _reference_panels(plan["strokes"], axis, eq, lines)
        plan["reference_ok"] = None if reference is None else (reference == accepted_keys)
        reference_disagrees = reference_disagrees or plan["reference_ok"] is False
        plan["cells"], plan["strips"] = cells, strips
        built.append(plan)

    # 3. freeze
    cell_records: list[CellCandidate] = []
    strip_records: list[AnatomyStrip] = []
    summaries: list[WidthClassSummary] = []
    containers = shorts = 0
    for plan in built:
        width, axis = plan["width"], plan["axis"]
        cell_ids: dict[int, str] = {}
        for index, cell in enumerate(plan["cells"]):
            cell_ids[id(cell)] = stable_contract_id("shadow_glazing_anatomy_cell", {
                "root": root, "width": width, "axis": axis, "pair": (cell["p"], cell["q"]),
                "along": (cell["a"], cell["b"]), "closure": cell["closure"]}, digest_chars=24)
        strip_ids: dict[int, str] = {}
        for index, strip in enumerate(plan["strips"]):
            strip["viewport"] = None
            o0, o1 = strip["band"]
            f0, f1 = strip["frame_along"]
            box = (f0, o0, f1, o1) if axis == "H" else (o0, f0, o1, f1)
            strip["viewport"] = _viewport_of(box, viewports)
            strip_ids[index] = stable_contract_id("shadow_glazing_anatomy_strip", {
                "root": root, "width": width, "axis": axis, "band": strip["band"], "along": strip["along"],
                "panels": len(strip["run"]), "ink": strip["ink"]}, digest_chars=24)
        for cell in plan["cells"]:
            fail = cell["fail"]
            gates = _gate_states(fail)
            first = None if fail is None else GATE_NAMES[fail]
            cell_records.append(CellCandidate(
                ownership=ownership, candidate_id=cell_ids[id(cell)], axis=axis, stroke_width=width,
                pair=(cell["p"], cell["q"]), along=(cell["a"], cell["b"]), closure=cell["closure"], gates=gates,
                first_failed_gate=first, detail=tuple(cell["detail"]), frame_offsets=cell["frame"],
                frame_rivals=cell["rivals"], rebates=cell["rebates"],
                cross_closed=cell["cross_closed"], end_post_widths=cell["ends"],
                chain_panel_count=cell["chain_count"],
                strip_id=None if cell["strip_key"] is None else strip_ids[cell["strip_key"]],
                in_merged_inventory=all(s == PASSED for _, s in gates[:MERGED_RULE_GATE_COUNT]),
                near_miss=first in NEAR_MISS_GATES, ink_ids=cell["ink"]))
        for index, strip in enumerate(plan["strips"]):
            run = strip["run"]
            strip_records.append(AnatomyStrip(
                ownership=ownership, strip_id=strip_ids[index], axis=axis, band=strip["band"],
                frame_depth=strip["depth"], along=strip["along"], frame_along=strip["frame_along"],
                panel_count=len(run),
                panel_lengths=strip["panel_lengths"], inner_post_widths=strip["inner_posts"],
                end_post_widths=strip["ends"], end_post_alternatives=strip["alternatives"],
                extent_complete=strip["extent_complete"], stroke_width=width,
                viewport_id=strip["viewport"], ink_ids=strip["ink"],
                cell_ids=tuple(cell_ids[id(m)] for m in run),
                full_anatomy=all(m["fail"] is None for m in run),
                merged_rule_copy_agrees=plan["reference_ok"]))
        containers += len(plan["outer"])
        shorts += plan["short"]

    candidates = tuple(sorted(cell_records, key=lambda c: (c.stroke_width, c.axis, c.pair, c.along, c.closure)))
    strips_out = tuple(sorted(strip_records, key=lambda s: (s.stroke_width, s.axis, s.band, s.along,
                                                             s.panel_count, s.strip_id)))
    for width in sorted(classes):
        mine = [p for p in built if p["width"] == width]
        class_candidates = [c for c in candidates if c.stroke_width == width]
        summaries.append(WidthClassSummary(
            stroke_width=width, ink_count=len(classes[width]), candidate_count=len(class_candidates),
            container_box_count=sum(len(p["outer"]) for p in mine), short_pair_count=sum(p["short"] for p in mine),
            accepted_cell_count=sum(1 for c in class_candidates if c.in_merged_inventory),
            strip_count=sum(1 for s in strips_out if s.stroke_width == width),
            first_failed_gate_histogram=_histogram(class_candidates)))
    near = tuple(c for c in candidates if c.near_miss)
    histogram = _histogram(candidates)

    # Unknown evidence abstains: an inventory over ink the producer could not verify, or one that disagrees with
    # the in-module copy of the merged rule, is not a census. Its lists stay attached as data about the verified ink.
    reasons: list[str] = []
    if reference_disagrees:
        reasons.append(SELF_CHECK_DISAGREES)
    if unverified_ink_count:
        reasons.append(INK_UNVERIFIED)
    if reasons:
        status = ABSTAIN
    elif strips_out:
        status, reasons = CANDIDATE, [ACCEPTED_CELLS_PRESENT]
    else:
        status, reasons = ABSTAIN, [NO_ACCEPTED_CELL]
    record_id = stable_contract_id("shadow_glazing_anatomy_inventory", {
        "root": root, "status": status.value, "reasons": tuple(reasons), "quantum": quantum,
        "cells": tuple((c.candidate_id, c.first_failed_gate, c.detail, c.frame_rivals) for c in candidates),
        "strips": tuple((s.strip_id, s.end_post_alternatives, s.viewport_id) for s in strips_out)}, digest_chars=24)
    boxes = [((s.frame_along[0], s.band[0], s.frame_along[1], s.band[1]) if s.axis == "H"
              else (s.band[0], s.frame_along[0], s.band[1], s.frame_along[1])) for s in strips_out]
    union = (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes),
             max(b[3] for b in boxes)) if boxes else None
    atom = EvidenceAtom(
        evidence_id=stable_contract_id("shadow_glazing_anatomy_atom", {"record": record_id}),
        document_id=ownership.document_id, page_id=ownership.page_id, kind=KIND_UNKNOWN, method=INVENTORY_METHOD,
        viewport_id=None, bbox=union, status=status, reason_codes=tuple(reasons),
        metadata={
            "revision_id": ownership.revision_id, "source_sha256": ownership.source_sha256,
            "snapshot_id": ownership.snapshot_id, "polarity": POLARITY_UNKNOWN,
            "candidate_count": len(candidates), "strip_count": len(strips_out), "near_miss_count": len(near),
            "first_failed_gate_histogram": dict(histogram),
            **{flag: False for flag in _GRANT_FLAGS}})
    return GlazingAnatomyInventory(
        ownership=ownership, status=status, reason_codes=tuple(reasons), standing_limits=STANDING_LIMITS,
        coordinate_quantum_pt=quantum, ink_count=len(ink), unverified_ink_count=unverified_ink_count,
        width_classes=tuple(summaries), candidates=candidates, strips=strips_out, near_misses=near,
        first_failed_gate_histogram=histogram, container_box_count=containers, short_pair_count=shorts,
        evidence_atoms=(atom,), record_id=record_id)


# --------------------------------------------------------------------------------------
# producer adapter
# --------------------------------------------------------------------------------------


class GlazingAnatomyInventoryShadow:
    """Read-only glazing anatomy inventory bound to one `SourceVisibilityProducer`; default OFF."""

    def __init__(self, source, *, enabled: bool = False):
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        if type(enabled) is not bool:
            raise ValueError("glazing anatomy inventory gate must be an explicit boolean")
        self._source = source
        self._enabled = enabled

    def inventory(self, *, revision_id: str, page_id: int, coordinate_quantum_pt: float) -> GlazingAnatomyInventory:
        """The gate-by-gate inventory of one page of a published, current revision.

        The page is addressed only by revision id and 1-based page id; the producer supplies the ink, the
        ownership, the stroke attributes and the viewports. There is no channel for nominations, widths, roles,
        tags or provenance. A disabled shadow returns a typed abstention without touching the producer."""
        if not self._enabled:
            return _empty(EvidenceResolutionStatus.ABSTAINED, (INVENTORY_DISABLED,))
        if (type(revision_id) is not str or type(page_id) is not int or isinstance(page_id, bool)
                or not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0
                        and math.isfinite(coordinate_quantum_pt))):
            raise ValueError("revision id, integer page id and a positive quantum required")
        import fitz

        from pb_source_observation_authority import ObservationSelector
        from pb_source_visibility_authority import VISIBLE_SOURCE_OBSERVATION_EXISTS
        from pb_vector_geometry_v130 import extract_native_page
        from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports

        ABSTAIN = EvidenceResolutionStatus.ABSTAINED
        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return _empty(ABSTAIN, (VISIBLE_SOURCE_AUTHORITY_REQUIRED,))
        document_id = published.revision.document_id
        if (page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or int(page_id) in tuple(int(v) for v in published.coverage.failed_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return _empty(ABSTAIN, (VISIBLE_SOURCE_AUTHORITY_REQUIRED,))
        source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return _empty(ABSTAIN, (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,))
        ownership = AnatomyOwnership(document_id, revision_id, published.snapshot.snapshot_id,
                                     published.revision.source_sha256, str(page_id))

        def selector(observation_id: str) -> ObservationSelector:
            return ObservationSelector(document_id, revision_id, ownership.source_sha256, ownership.snapshot_id,
                                       observation_id)

        # one pass over the page: the producer's own primitives, native drawings and viewport segmentation
        with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
            page = document[page_id - 1]
            primitives = {s["id"]: s for s in extract_native_page(page)["segments"]}
            native_drawings = page.get_drawings()
            segmented = segment_page_viewports(page, page_number=page_id)

        # visible ink: re-resolved by the producer, joined to its own primitive of the same id
        visibility = source.authority()
        ink: list[InkSegment] = []
        unverified = 0
        published_ids: set[str] = set()
        for observation_id in published.visible_observation_ids:
            if observation_id in published_ids:      # a repeated published id is an integrity negative, never merged
                return _empty(ABSTAIN, (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,))
            published_ids.add(observation_id)
            result = visibility.resolve_visible(selector(observation_id))
            observation = result.observation
            if (result.status is not EvidenceResolutionStatus.CORROBORATED
                    or result.proposition != VISIBLE_SOURCE_OBSERVATION_EXISTS or observation is None):
                if observation is None or str(observation.page_id) == str(page_id):
                    unverified += 1
                continue
            # a positive wrapper is not authority to substitute a foreign observation: immutable identity first
            if (observation.observation_id != observation_id or observation.document_id != document_id
                    or observation.revision_id != revision_id or observation.source_sha256 != ownership.source_sha256
                    or observation.snapshot_id != ownership.snapshot_id):
                return _empty(ABSTAIN, (SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,))
            if str(observation.page_id) != str(page_id):
                continue
            try:
                geometry = tuple(float(v) for v in observation.geometry)
            except (TypeError, ValueError, OverflowError):
                geometry = ()
            if len(geometry) != 4 or not all(math.isfinite(v) for v in geometry):
                unverified += 1
                continue
            primitive = primitives.get(str(observation.source_primitive_ref).removeprefix("visible:segment:"))
            if primitive is None or geometry != (float(primitive["x1"]), float(primitive["y1"]),
                                                 float(primitive["x2"]), float(primitive["y2"])):
                unverified += 1
                continue
            stroke, width = primitive.get("stroke"), primitive.get("width")
            if not primitive.get("stroke_present") or not primitive.get("width_present") or width is None:
                continue                              # an unstroked primitive (a fill) is not line ink
            path_index = primitive.get("path_index")
            if type(path_index) is not int or not (0 <= path_index < len(native_drawings)):
                unverified += 1
                continue
            drawing = native_drawings[path_index]
            if drawing.get("seqno") != primitive.get("sequence_number"):
                unverified += 1
                continue
            opacity = drawing.get("stroke_opacity")
            solid = bool(re.fullmatch(r"\s*\[\s*\]\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*",
                                      str(primitive.get("dashes", ""))))
            opaque = type(opacity) in (int, float) and math.isfinite(opacity) and opacity == 1.
            # "black" is the merged adapter's convention (every stroke channel at most 0.1, not fully transparent)
            black = bool(stroke) and max(stroke) <= 0.1 and opacity != 0.
            ink.append(InkSegment(str(observation_id), geometry[0], geometry[1], geometry[2], geometry[3],
                                  float(width), black, continuous_opaque=bool(solid and opaque)))

        floor_plans = tuple(
            ViewportRef(str(v.view_id), tuple(float(c) for c in v.bounding_box)) for v in segmented
            if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box is not None
            and v.view_type == "floor_plan")
        return inventory_glazing_anatomy(
            ownership=ownership, ink=ink, viewports=floor_plans, coordinate_quantum_pt=float(coordinate_quantum_pt),
            unverified_ink_count=unverified)


__all__ = [
    "ACCEPTED_CELLS_PRESENT", "ALL_GATES_PASSED", "AnatomyOwnership", "AnatomyStrip", "CANDIDATE_BUDGET_EXCEEDED",
    "CLOSURE_BOTH", "CLOSURE_HI_MISSING", "CLOSURE_LO_MISSING", "CellCandidate", "FAILED", "GATE_DESCRIPTIONS",
    "GATE_NAMES", "GLAZING_ANATOMY_INVENTORY_SCHEMA_VERSION", "GlazingAnatomyInventory",
    "GlazingAnatomyInventoryShadow", "INK_BUDGET_EXCEEDED", "INK_UNVERIFIED", "INVENTORY_DISABLED",
    "InkSegment", "NEAR_MISS_GATES", "NOT_EVALUATED", "NO_ACCEPTED_CELL", "PASSED", "SELF_CHECK_DISAGREES",
    "STANDING_LIMITS", "ViewportRef", "WidthClassSummary", "inventory_glazing_anatomy",
]
