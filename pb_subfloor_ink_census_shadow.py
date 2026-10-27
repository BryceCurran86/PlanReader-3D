"""Default-off, read-only SUB-FLOOR ink census of a named page region, strictly SHADOW.

The producer's native extraction drops every stroked line item shorter than half a point (and the
producer's visibility authority rejects every segment that short, rectangle edges included), so no
producer-owned consumer ever sees them. On a CAD export those short items are not rare, and they include
exactly the kind of mark a glazing cell is closed with (the end ticks of a glass pair drawn one coordinate
quantum apart). This module answers one narrow question for a caller-named region of one page: which stroked
items does the producer's floor hide there, how do they relate to the producer-visible ink, and would they
change a glazing cell's anatomy?

It is a census, not a detector. It reports every hidden item with the producer's own addresses, widths and
colours; whether each sits on top of a producer-visible endpoint; whether a later opaque fill is proven to paint
over it; and whether the producer proves it is not clipped away. For a nominated strip it adds a purely geometric
diagnostic: would the hidden perpendicular items at a pane's two ends let the existing strip finder's closure
rule (two end ticks spanning the pane pair, inside a centred frame whose end stations are crossed over the full
depth) pass for a cell that has no such tick today? That is a statement about drawn geometry, never evidence of a
window, a host, a kind, a scale, a count or a quantity.

The verdict is ABSTAINED unless the hidden items exactly complete a missing tick pair of an otherwise present
pane pair, with no rival reading, no visible cell displaced, and nothing proven or possibly painted or clipped
over them, in which case it is a CANDIDATE. It never alters the producer, never feeds a consumer, never builds a
`PhysicalOpeningExistenceRecord`, and imports nothing from the issuer, the binders, the count producer or live
quantity code.

Known limits (see also STANDING_LIMITS): a later stroke can only be called harmless to a black mark when it is
itself opaque black and the document defines no blend mode; text, images, shadings, translucent or unproven paint
reaching a hidden item leave it unproven; optional-content visibility is not evaluated for the hidden items
themselves (a cover on an optional-content layer is never proven); hidden ticks are read only as perpendicular
pieces of a glazing cell, so a hidden parallel piece never extends a line.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections import defaultdict
from dataclasses import dataclass, fields
from typing import Callable, Iterable, Optional, Sequence

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,
    SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE,
    VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

SUBFLOOR_INK_CENSUS_SCHEMA_VERSION = "1.0.0"
SUBFLOOR_CENSUS_METHOD = "subfloor_ink_census_shadow"

# The producer's own floors. Both are the literal 0.5 in the producer's source; there is no named constant to
# import, so they are mirrored here and pinned by tests that probe the producer's behaviour and read its source.
#  * pb_vector_geometry_v130.extract_native_page: a line ('l') item shorter than this is skipped (`continue`).
#    Rectangle edges are NOT floored there: every edge of every rectangle is emitted.
#  * pb_source_visibility_authority._segment_geometry: any segment shorter than this is not a visible
#    observation, whatever it is (so short rectangle edges are hidden at this second floor).
PRODUCER_LINE_ITEM_FLOOR_PT = 0.5
PRODUCER_VISIBLE_SEGMENT_FLOOR_PT = 0.5
HIDDEN_BY_EXTRACTOR_LINE_FLOOR = "extractor_line_item_floor"
HIDDEN_BY_VISIBILITY_SEGMENT_FLOOR = "visibility_segment_floor"
ITEM_KIND_LINE = "line"
ITEM_KIND_RECT_EDGE = "rect_edge"

# paint-order states of a hidden item
PAINT_COVERED = "covered_by_later_opaque_fill"
PAINT_CLEAR = "no_later_paint_overlaps"
PAINT_UNPROVEN = "paint_order_unproven"
PAINT_NOT_APPLICABLE = "not_applicable"
PAINT_BASIS_COVER = "later_opaque_rect_fill_contains_stroke_footprint"
PAINT_BASIS_CLEAR = "no_later_paint_operation_reaches_stroke_footprint"
PAINT_BASIS_OVERLAP = "later_paint_reaches_stroke_footprint_without_proof_of_cover"
PAINT_BASIS_SEQUENCE_MISSING = "item_sequence_number_unavailable"
PAINT_BASIS_BUDGET = "paint_check_budget_exceeded"
PAINT_BASIS_CLIP_UNPROVEN = "item_clip_not_proven_to_contain_stroke_footprint"

# tick support classes of a cell
TICK_VISIBLE = "visible"
TICK_MIXED = "mixed"
TICK_SUB_FLOOR = "sub_floor"

# census-local reason codes (the shared ones are imported from the existing authority above)
CENSUS_DISABLED = "subfloor_ink_census_disabled"
NOMINATION_NOT_VISIBLE_ON_PAGE = "subfloor_nomination_not_visible_on_page"
SOURCE_ROLE_UNPROVEN = "subfloor_nominated_source_role_unproven"
NOMINATION_NOT_AXIS_ALIGNED = "subfloor_nomination_not_axis_aligned"
NOMINATION_AXIS_AMBIGUOUS = "subfloor_nomination_axis_ambiguous"
NOMINATION_HAS_NO_DEPTH = "subfloor_nomination_has_no_depth"
ITEM_BUDGET_EXCEEDED = "subfloor_item_budget_exceeded"
VISIBLE_INVENTORY_INCOMPLETE = "subfloor_visible_inventory_incomplete"
CLOSURE_NOT_EVALUATED_REGION_MODE = "subfloor_closure_not_evaluated_in_region_mode"
CENSUS_ONLY_NO_CELL_COMPLETION = "subfloor_census_only_no_cell_completion"
CLOSURE_AMBIGUOUS = "subfloor_cell_closure_ambiguous"
HIDDEN_TICKS_DISPLACE_VISIBLE_CELL = "subfloor_ticks_also_displace_a_visible_cell"
COMPLETION_COVERED_BY_LATER_FILL = "subfloor_completion_covered_by_later_fill"
COMPLETION_PAINT_ORDER_UNPROVEN = "subfloor_completion_paint_order_unproven"
SUB_FLOOR_TICKS_WOULD_CLOSE_CELL = "sub_floor_ticks_would_close_cell"
# standing capability limits, never evidence kinds
SUB_FLOOR_INK_ROLE_UNPROVEN = "sub_floor_ink_role_unproven"
SUB_FLOOR_INK_IS_NOT_A_WINDOW = "sub_floor_ink_is_not_an_opening_or_window"
STANDING_LIMITS = (SUB_FLOOR_INK_ROLE_UNPROVEN, SUB_FLOOR_INK_IS_NOT_A_WINDOW)

# Source coordinates sit on a lattice whose spacing is the caller's coordinate quantum; two coordinates closer
# than a quarter of it are the same coordinate. This is identity of drawn geometry, not a distance threshold.
_EQ_FRACTION_OF_QUANTUM = 0.25
# Work bounds. They stop a pathological request from being analysed; they decide nothing.
_MAX_SUB_FLOOR_ITEMS = 100_000
_MAX_PAINT_PAIR_CHECKS = 5_000_000
_MAX_CLOSURE_STROKES = 50_000
# The sibling strip finder reads only black ink as a glazing strip; mirrored so the diagnostic is about the same
# ink it would read (gray or RGB channels only; a four-channel colour is never read as black here).
_SIBLING_BLACK_MAX_CHANNEL = 0.1
# Numerical slack when checking that the page's paint log agrees with its drawing list (float32 conversions).
_PAINT_LOG_SLACK = 1e-3

_STATUSES = (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.ABSTAINED, EvidenceResolutionStatus.CONFLICT)
_GRANT_FLAGS = (
    "physical_opening_granted", "host_granted", "opening_kind_granted", "frame_granted", "scale_granted",
    "metric_granted", "count_granted", "quantity_granted", "wall_binding_granted",
    "commercial_projection_allowed", "customer_publication_granted", "takeoff_eligible",
    "deduction_authority", "existence_record_issued",
)

Box = tuple[float, float, float, float]


# --------------------------------------------------------------------------------------
# records handed to the pure core (the adapter builds them from the producer; tests build them by hand)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CensusOwnership:
    document_id: str
    revision_id: str
    snapshot_id: str
    source_sha256: str
    page_id: str


@dataclass(frozen=True)
class ViewportRef:
    view_id: str
    bbox: Box


@dataclass(frozen=True, slots=True)
class VisibleInk:
    """One producer-visible segment, as the producer's own authority resolves it, joined to its primitive."""

    observation_id: str
    geometry: Box
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    solid_opaque: bool
    role_verified: bool


@dataclass(frozen=True, slots=True)
class RawItem:
    """One line item or one rectangle edge of the immutable page, in the producer's own id space."""

    item_id: str                    # d{drawing}i{item}[e{edge}], the producer's primitive id
    drawing_index: int
    item_index: int
    edge_index: Optional[int]
    kind: str                       # ITEM_KIND_LINE | ITEM_KIND_RECT_EDGE
    geometry: Box
    stroked: bool                   # the producer's own stroke_present and width_present
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    stroke_opacity: Optional[float]
    solid: bool                     # no dash pattern
    sequence_number: Optional[int]  # the drawing's first paint-sequence number
    sequence_end: Optional[int]     # the last paint-sequence number its drawing occupies
    # The producer's own clip proof for the item's drawing (pb_vector_geometry_v130). Fail closed by default: a
    # hand-built record that does not say it is unclipped is not proven unclipped.
    clip_known: bool = False
    clip_present: bool = False
    clip_exact_rect: Optional[Box] = None   # the clip, when the producer proves it is exactly this rectangle


@dataclass(frozen=True, slots=True)
class PaintOp:
    """One paint operation of the page's own paint log (fills, strokes, text, images, shadings...)."""

    sequence_number: int
    kind: str
    bbox: Box
    drawing_index: Optional[int] = None
    # Set by the adapter ONLY for a fill that is proven opaque, unclipped (or exactly clipped), unblended and a
    # single axis-aligned rectangle: the rectangle it provably paints.
    opaque_cover: Optional[Box] = None
    # Exact reach of a stroke made only of lines/rectangles: (x1, y1, x2, y2, half_width). None means bbox only.
    stroke_segments: Optional[tuple[tuple[float, float, float, float, float], ...]] = None
    # Set by the adapter ONLY for a stroke that is opaque, black and drawn with no blend mode anywhere in the document:
    # painted over a black mark it leaves that mark black, so it cannot hide a black mark.
    black_opaque_stroke: bool = False

    def __post_init__(self) -> None:
        if type(self.black_opaque_stroke) is not bool or (self.black_opaque_stroke and self.kind != "stroke-path"):
            raise ValueError("only a stroke can be recorded as an opaque black stroke")
        if self.black_opaque_stroke and (self.opaque_cover is not None):
            raise ValueError("a stroke does not cover")


@dataclass(frozen=True)
class PaintLog:
    ops: tuple[PaintOp, ...]
    aligned: bool                   # drawing sequence numbers proven to index this log
    unproven_reason: str = ""


# --------------------------------------------------------------------------------------
# records the core returns
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class SubFloorItem:
    item_id: str
    drawing_index: int
    item_index: int
    edge_index: Optional[int]
    kind: str
    hidden_by: str
    geometry: Box
    length: float
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    stroke_opacity: Optional[float]
    solid: bool
    orientation: str                          # "H" | "V" | "oblique" | "point"
    strip_relation: Optional[str]             # "parallel" | "perpendicular" | "oblique" | "point" (nominated mode)
    touches_band_edge: Optional[str]          # "lo" | "hi" | "both" | None (nominated mode)
    endpoint_a_visible_ids: tuple[str, ...]   # producer-visible segments with an endpoint at this endpoint
    endpoint_b_visible_ids: tuple[str, ...]
    endpoints_coincide_visible: bool
    paint_order: str
    paint_basis: str
    covering_drawing_indices: tuple[int, ...]
    sequence_number: Optional[int]


@dataclass(frozen=True)
class SubFloorGroup:
    stroke_width: Optional[float]
    stroke_rgb: Optional[tuple[float, ...]]
    orientation: str
    length_bucket: float            # the exact length rounded to 0.01
    count: int
    line_items: int
    rect_edges: int
    endpoint_coincident: int


@dataclass(frozen=True)
class TickSupport:
    position: float
    support: str                              # TICK_VISIBLE | TICK_MIXED | TICK_SUB_FLOOR
    visible_ids: tuple[str, ...]
    sub_floor_item_ids: tuple[str, ...]


@dataclass(frozen=True)
class CellClosure:
    """One glazing cell as the strip finder reads it: two parallel pane lines, two perpendicular end ticks that each
    span exactly the pair, framed by two parallel lines with the pane centred and narrower than each rebate."""

    cell_id: str
    stroke_width: float
    stroke_rgbs: tuple[tuple[float, ...], ...]   # every distinct black of the width class (the finder groups by width)
    pane_lines: tuple[float, float]           # the two parallel lines (across coordinates, snapped to the lattice)
    frame_lines: tuple[float, float]          # the enclosing parallel lines (across coordinates)
    along: tuple[float, float]                # the two end ticks (along coordinates, snapped to the lattice)
    lo_tick: TickSupport
    hi_tick: TickSupport
    visible_closed: bool                      # the very same cell exists from visible ink alone
    inside_visible_cell: bool                 # a visible cell on the same pane lines already spans it
    would_close_cell: bool                    # GEOMETRIC diagnostic only
    completion_paint: str                     # "clear" | "covered" | "unproven" | PAINT_NOT_APPLICABLE


@dataclass(frozen=True)
class DisplacedVisibleCell:
    """A cell the visible ink closes today that stops being read as a cell once the hidden ticks are added (hidden
    ink nests a smaller cell in it, or its coordinates re-cluster the cell's own). Reported, never resolved."""

    stroke_width: float
    stroke_rgbs: tuple[tuple[float, ...], ...]
    pane_lines: tuple[float, float]
    along: tuple[float, float]
    hidden_item_ids_in_cell: tuple[str, ...]  # hidden perpendicular items on or inside the cell, within its pane pair


@dataclass(frozen=True)
class SubFloorInkCensus:
    ownership: Optional[CensusOwnership]
    viewport_id: Optional[str]
    mode: Optional[str]                       # "region" | "nominated"
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    standing_limits: tuple[str, ...]
    nomination_id: Optional[str]
    nominated_observation_ids: tuple[str, ...]
    region: Optional[Box]
    axis: Optional[str]
    along_extent: Optional[tuple[float, float]]
    band_extent: Optional[tuple[float, float]]
    extractor_line_floor_pt: float
    visibility_segment_floor_pt: float
    sub_floor_items: tuple[SubFloorItem, ...]
    unstroked_sub_floor_count: int
    visible_in_region_count: int
    groups: tuple[SubFloorGroup, ...]
    band_edge_item_ids: tuple[str, ...]
    cells: tuple[CellClosure, ...]
    displaced_visible_cells: tuple[DisplacedVisibleCell, ...]
    would_close_cell: Optional[bool]          # None when closure was not evaluated
    visible_inventory_complete: bool
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
    schema_version: str = SUBFLOOR_INK_CENSUS_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if self.shadow_only is not True:
            raise ValueError("a sub-floor ink census cannot leave shadow mode")
        for name in _GRANT_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError(f"a sub-floor ink census cannot grant {name}")
        if self.status not in _STATUSES:
            raise ValueError("a sub-floor ink census is CANDIDATE, ABSTAINED or CONFLICT only")
        if any(atom.status not in _STATUSES for atom in self.evidence_atoms):
            raise ValueError("evidence atoms are CANDIDATE, ABSTAINED or CONFLICT only")
        if self.status is EvidenceResolutionStatus.CANDIDATE:
            completed = [c for c in self.cells if c.would_close_cell]
            if not (completed and all(c.completion_paint == "clear" for c in completed)
                    and self.would_close_cell is True and self.visible_inventory_complete is True
                    and not self.displaced_visible_cells
                    and self.reason_codes == (SUB_FLOOR_TICKS_WOULD_CLOSE_CELL,)):
                raise ValueError("a CANDIDATE needs a geometrically completed cell whose hidden ticks are proven "
                                 "not painted over and that displaces no visible cell")
        if not set(_GRANT_FLAGS) <= {f.name for f in fields(self)}:
            raise ValueError("grant flag set is out of date")


# --------------------------------------------------------------------------------------
# pure geometry
# --------------------------------------------------------------------------------------


def _bbox(g: Sequence[float]) -> Box:
    return (min(g[0], g[2]), min(g[1], g[3]), max(g[0], g[2]), max(g[1], g[3]))


def _expand(b: Box, margin: float) -> Box:
    return (b[0] - margin, b[1] - margin, b[2] + margin, b[3] + margin)


def _boxes_meet(a: Box, b: Box, slack: float = 0.0) -> bool:
    return not (a[2] < b[0] - slack or a[0] > b[2] + slack or a[3] < b[1] - slack or a[1] > b[3] + slack)


def _contains(outer: Box, inner: Box) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and inner[2] <= outer[2] and inner[3] <= outer[3]


def _length(g: Sequence[float]) -> float:
    return math.hypot(g[2] - g[0], g[3] - g[1])


def _orientation(g: Sequence[float], eq: float) -> str:
    dx, dy = abs(g[2] - g[0]), abs(g[3] - g[1])
    if dx <= eq and dy <= eq:
        return "point"
    if dy <= eq:
        return "H"
    if dx <= eq:
        return "V"
    return "oblique"


def _relation(orientation: str, axis: str) -> str:
    if orientation in ("H", "V"):
        return "parallel" if orientation == axis else "perpendicular"
    return orientation


def _along_across(g: Sequence[float], axis: str) -> tuple[tuple[float, float], tuple[float, float]]:
    x = (min(g[0], g[2]), max(g[0], g[2]))
    y = (min(g[1], g[3]), max(g[1], g[3]))
    return (x, y) if axis == "H" else (y, x)


def _segment_meets_box(x1: float, y1: float, x2: float, y2: float, box: Box) -> bool:
    """Does the closed segment meet the closed box (Liang-Barsky)?"""
    t0, t1 = 0.0, 1.0
    dx, dy = x2 - x1, y2 - y1
    for p, q in ((-dx, x1 - box[0]), (dx, box[2] - x1), (-dy, y1 - box[1]), (dy, box[3] - y1)):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        r = q / p
        if p < 0.0:
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            if r < t0:
                return False
            t1 = min(t1, r)
    return True


def _snapper(values: Iterable[float], eq: float) -> Callable[[float], float]:
    """Map values within the coordinate equality onto one representative (bounded-diameter clustering on the
    sorted distinct values: independent of input order and of where a translation puts the values)."""
    representative: dict[float, float] = {}
    start: Optional[float] = None
    for value in sorted(set(values)):
        if start is None or value - start > eq:
            start = value
        representative[value] = start  # type: ignore[assignment]
    return representative.__getitem__


def _is_black(rgb: Optional[Sequence[float]]) -> bool:
    return bool(rgb) and len(rgb) in (1, 3) and max(rgb) <= _SIBLING_BLACK_MAX_CHANNEL  # type: ignore[arg-type]


# --------------------------------------------------------------------------------------
# paint order
# --------------------------------------------------------------------------------------


def _clip_contains(item: RawItem, footprint: Box) -> bool:
    """Is the item proven not to be cut by a clip? Either the producer proves there is no clip at all, or it proves
    the clip is exactly one rectangle that contains the stroke footprint. Anything else (unknown, a curved or
    multi-part clip, a rectangle that cuts the footprint) is not proven."""
    if not item.clip_known:
        return False
    if not item.clip_present:
        return True
    return item.clip_exact_rect is not None and _contains(item.clip_exact_rect, footprint)


def _paint_state(item: RawItem, near: Sequence[PaintOp], log: PaintLog):
    """Is the hidden item provably painted over, provably not, or neither?

    Footprint = the item's box grown by half its stroke width on every side (it bounds butt, square and round
    caps). A LATER op (higher paint sequence) that provably paints a rectangle containing the footprint covers the
    item. A later op that reaches the footprint without such a proof leaves the order unproven. An item the
    producer cannot prove unclipped is unproven too. Only when nothing painted later reaches the footprint, and
    nothing may have cut the item away, is it reported as not overlapped."""
    if not log.aligned:
        return PAINT_UNPROVEN, log.unproven_reason or "paint_log_not_aligned_with_drawing_sequence", ()
    if item.sequence_end is None or item.stroke_width is None:
        return PAINT_UNPROVEN, PAINT_BASIS_SEQUENCE_MISSING, ()
    footprint = _expand(_bbox(item.geometry), item.stroke_width / 2.0)
    item_black = item.solid and item.stroke_opacity == 1.0 and _is_black(item.stroke_rgb)
    covering: set[int] = set()
    reaching = False
    for op in near:
        if op.sequence_number <= item.sequence_end or not _boxes_meet(op.bbox, footprint):
            continue
        if op.opaque_cover is not None and _contains(op.opaque_cover, footprint):
            if op.drawing_index is not None:
                covering.add(op.drawing_index)
            continue
        if op.black_opaque_stroke and item_black:
            continue
        if op.stroke_segments is not None and not any(
                _segment_meets_box(s[0], s[1], s[2], s[3], _expand(footprint, s[4])) for s in op.stroke_segments):
            continue
        reaching = True
    if covering:
        return PAINT_COVERED, PAINT_BASIS_COVER, tuple(sorted(covering))
    if reaching:
        return PAINT_UNPROVEN, PAINT_BASIS_OVERLAP, ()
    if not _clip_contains(item, footprint):
        return PAINT_UNPROVEN, PAINT_BASIS_CLIP_UNPROVEN, ()
    return PAINT_CLEAR, PAINT_BASIS_CLEAR, ()


# --------------------------------------------------------------------------------------
# pane-cell closure (the same rule the strip finder applies, re-stated over visible plus hidden ticks)
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Stroke:
    offset: float
    lo: float
    hi: float
    ident: str
    sub: bool


@dataclass(frozen=True)
class _Cover:
    spans: tuple[tuple[float, float], ...]
    eq: float

    def covers(self, lo: float, hi: float) -> bool:
        return any(a - self.eq <= lo and hi <= b + self.eq for a, b in self.spans)


def _covers_by_offset(strokes: Sequence[_Stroke], eq: float) -> dict[float, _Cover]:
    """The union of collinear pieces at each offset (invariant to splitting a line into pieces)."""
    grouped: dict[float, list[_Stroke]] = defaultdict(list)
    for s in strokes:
        grouped[s.offset].append(s)
    covers: dict[float, _Cover] = {}
    for offset, items in grouped.items():
        merged: list[list[float]] = []
        for s in sorted(items, key=lambda s: (s.lo, s.hi, s.ident)):
            if merged and s.lo <= merged[-1][1] + eq:
                merged[-1][1] = max(merged[-1][1], s.hi)
            else:
                merged.append([s.lo, s.hi])
        covers[offset] = _Cover(tuple((a, b) for a, b in merged), eq)
    return covers


def _pane_boxes(par: Sequence[_Stroke], perp: Sequence[_Stroke], eq: float) -> list[tuple[float, float, float, float]]:
    """Closed thin boxes (a, b, p, q): two parallel lines p < q and two perpendicular end ticks at a < b that each
    span exactly the pair. An end tick is a stroke, or the collinear union of strokes, spanning the pair."""
    lines = _covers_by_offset(par, eq)
    ranges: dict[tuple[float, float], set[float]] = defaultdict(set)
    for s in perp:
        if s.hi - s.lo > eq:
            ranges[(s.lo, s.hi)].add(s.offset)
    for offset, cover in _covers_by_offset(perp, eq).items():
        for lo, hi in cover.spans:
            if hi - lo > eq:
                ranges[(lo, hi)].add(offset)
    boxes: list[tuple[float, float, float, float]] = []
    for (p, q) in sorted(ranges):
        positions = sorted(ranges[(p, q)])
        for a, b in zip(positions, positions[1:]):
            if b - a <= q - p:            # a pane is longer than it is thick
                continue
            lp, lq = lines.get(p), lines.get(q)
            if lp is None or lq is None or not (lp.covers(a, b) and lq.covers(a, b)):
                continue
            boxes.append((a, b, p, q))
    return boxes


def _innermost(boxes: Sequence[tuple[float, float, float, float]], eq: float):
    """A pane is the INNERMOST thin box: the frame outline around it is also a closed box."""
    return [x for x in boxes
            if not any(y is not x and x[0] - eq <= y[0] and y[1] <= x[1] + eq and x[2] + eq < y[2] and y[3] < x[3] - eq
                       for y in boxes)]


def _frame_of(box, par_cover: dict[float, _Cover], perp_cover: dict[float, _Cover], eq: float):
    """The strip finder's glazing anatomy around a thin box, or None.

    The enclosing frame lines are the nearest parallel lines on either side that cover the pane. That is the finder's
    definition of the enclosing frame, restated so that this diagnostic and the finder cannot disagree; it can only
    remove a box from consideration, never choose between rival boxes (rivals are reported, see CLOSURE_AMBIGUOUS).
    The pane must be shorter in depth than the frame is long, narrower than each rebate, centred in the frame, and
    both end ticks' stations must be crossed by a stroke (or collinear union) spanning the whole frame depth."""
    a, b, p, q = box
    below = [o for o in par_cover if o < p - eq and par_cover[o].covers(a, b)]
    above = [o for o in par_cover if o > q + eq and par_cover[o].covers(a, b)]
    if not below or not above:
        return None
    o0, o1 = max(below), min(above)
    if o1 - o0 >= b - a:
        return None
    inner, side0, side1 = q - p, p - o0, o1 - q
    if not (inner < side0 - eq and inner < side1 - eq):
        return None
    if abs(side0 - side1) > 2.0 * eq:
        return None
    ca, cb = perp_cover.get(a), perp_cover.get(b)
    if ca is None or cb is None or not (ca.covers(o0, o1) and cb.covers(o0, o1)):
        return None
    return (o0, o1)


def _in_strip(box, along: tuple[float, float], band: tuple[float, float], eq: float) -> bool:
    a, b, p, q = box
    return along[0] - eq <= a and b <= along[1] + eq and band[0] - eq <= p and q <= band[1] + eq


def _same_box(x, y, eq: float) -> bool:
    return all(abs(u - v) <= eq for u, v in zip(x, y))


def _snap_view(par_raw: Sequence[tuple], perp_raw: Sequence[tuple], eq: float):
    """Snap one view of a width class (parallel strokes plus the perpendicular strokes this view contains) onto the
    lattice. The visible-only view and the visible-plus-hidden view are snapped separately, so adding hidden ink can
    never shift how the visible ink alone is read."""
    snap_along = _snapper([v for _, lo, hi, _, _ in par_raw for v in (lo, hi)] + [o for o, _, _, _, _ in perp_raw], eq)
    snap_across = _snapper([o for o, _, _, _, _ in par_raw] + [v for _, lo, hi, _, _ in perp_raw for v in (lo, hi)], eq)
    par = [_Stroke(snap_across(o), snap_along(lo), snap_along(hi), ident, sub) for o, lo, hi, ident, sub in par_raw]
    perp = [_Stroke(snap_along(o), snap_across(lo), snap_across(hi), ident, sub) for o, lo, hi, ident, sub in perp_raw]
    return par, perp


def _panes(par: Sequence[_Stroke], perp: Sequence[_Stroke], along, band, eq: float):
    """(box, frame) of every pane the finder would read inside the strip from exactly these strokes."""
    par_cover, perp_cover = _covers_by_offset(par, eq), _covers_by_offset(perp, eq)
    out = []
    for box in _innermost(_pane_boxes(par, perp, eq), eq):
        if not _in_strip(box, along, band, eq):
            continue
        frame = _frame_of(box, par_cover, perp_cover, eq)
        if frame is not None:
            out.append((box, frame))
    return sorted(out)


def _tick_support(position: float, p: float, q: float, perp_vis: Sequence[_Stroke], perp_sub: Sequence[_Stroke],
                  visible_cover: dict[float, _Cover], eq: float) -> TickSupport:
    """What stands at one end of a pane: only pieces lying within the pane pair can be part of its end tick (a
    longer frame tick at the same station is not a piece of it)."""
    def pieces(strokes):
        return tuple(sorted({s.ident for s in strokes
                             if abs(s.offset - position) <= eq and s.lo >= p - eq and s.hi <= q + eq}))
    visible_ids, sub_ids = pieces(perp_vis), pieces(perp_sub)
    # visible ink alone completes the tick when one stroke, or the collinear union of strokes, spans the pair
    complete = (any(abs(s.offset - position) <= eq and abs(s.lo - p) <= eq and abs(s.hi - q) <= eq for s in perp_vis)
                or any(abs(off - position) <= eq and any(abs(lo - p) <= eq and abs(hi - q) <= eq for lo, hi in cover.spans)
                       for off, cover in visible_cover.items()))
    support = TICK_VISIBLE if complete else (TICK_MIXED if visible_ids else TICK_SUB_FLOOR)
    return TickSupport(position=position, support=support, visible_ids=visible_ids, sub_floor_item_ids=sub_ids)


def _closure(*, axis: str, along: tuple[float, float], band: tuple[float, float], visible: Sequence[VisibleInk],
             sub_items: Sequence[RawItem], paint_of: dict, eq: float, root: tuple):
    """Pane cells over visible ink plus hidden perpendicular ink, per exact stroke width of black ink.

    The rule is the strip finder's: a pane is the innermost closed thin box of two parallel lines and two
    perpendicular end ticks that each span exactly that pair, inside a centred frame whose two end stations are
    crossed over the full frame depth. Hidden items only ever enter as perpendicular pieces (ticks); parallel hidden
    pieces are reported by the census but never extend a line here."""
    # entries are (offset, lo, hi, ident, hidden): offset across the stroke, [lo, hi] along it
    classes: dict[float, dict] = defaultdict(lambda: {"par": [], "perp_vis": [], "perp_sub": [], "rgb": set()})
    for v in visible:
        if not (v.role_verified and v.solid_opaque and v.stroke_width is not None and v.stroke_rgb is not None
                and _is_black(v.stroke_rgb) and v.stroke_width > 0.0):
            continue
        orient = _orientation(v.geometry, eq)
        if orient not in ("H", "V"):
            continue
        (a0, a1), (c0, c1) = _along_across(v.geometry, axis)
        group = classes[float(v.stroke_width)]
        group["rgb"].add(tuple(v.stroke_rgb))
        if _relation(orient, axis) == "parallel":
            group["par"].append(((c0 + c1) / 2.0, a0, a1, v.observation_id, False))
        else:
            group["perp_vis"].append(((a0 + a1) / 2.0, c0, c1, v.observation_id, False))
    for it in sub_items:
        if not (it.stroked and it.solid and it.stroke_opacity == 1.0 and it.stroke_width is not None
                and it.stroke_rgb is not None and _is_black(it.stroke_rgb) and it.stroke_width > 0.0):
            continue
        orient = _orientation(it.geometry, eq)
        if orient not in ("H", "V") or _relation(orient, axis) != "perpendicular":
            continue
        (a0, a1), (c0, c1) = _along_across(it.geometry, axis)
        group = classes[float(it.stroke_width)]
        group["rgb"].add(tuple(it.stroke_rgb))
        group["perp_sub"].append(((a0 + a1) / 2.0, c0, c1, it.item_id, True))

    cells: list[CellClosure] = []
    displaced: list[DisplacedVisibleCell] = []
    n_strokes = 0
    for key in sorted(classes):
        group = classes[key]
        n_strokes += len(group["par"]) + len(group["perp_vis"]) + len(group["perp_sub"])
        if n_strokes > _MAX_CLOSURE_STROKES:
            return None
        rgbs = tuple(sorted(group["rgb"]))
        par_v, perp_v = _snap_view(group["par"], group["perp_vis"], eq)
        panes_vis = _panes(par_v, perp_v, along, band, eq)
        if group["perp_sub"]:
            par_a, perp_a = _snap_view(group["par"], group["perp_vis"] + group["perp_sub"], eq)
            panes_all = _panes(par_a, perp_a, along, band, eq)
        else:
            par_a, perp_a, panes_all = par_v, perp_v, panes_vis
        perp_vis_s = [s for s in perp_a if not s.sub]
        perp_sub_s = [s for s in perp_a if s.sub]
        visible_cover = _covers_by_offset(perp_vis_s, eq)
        for box, frame in panes_all:
            a, b, p, q = box
            lo_tick = _tick_support(a, p, q, perp_vis_s, perp_sub_s, visible_cover, eq)
            hi_tick = _tick_support(b, p, q, perp_vis_s, perp_sub_s, visible_cover, eq)
            visible_closed = any(_same_box(box, v, eq) for v, _ in panes_vis)
            inside_visible = any(abs(v[2] - p) <= eq and abs(v[3] - q) <= eq and v[0] <= a + eq and b <= v[1] + eq
                                 for v, _ in panes_vis)
            would = not inside_visible
            if not would:
                completion = PAINT_NOT_APPLICABLE
            else:
                # only the hidden pieces of the ticks that visible ink does not complete are needed
                needed = [i for t in (lo_tick, hi_tick) if t.support != TICK_VISIBLE for i in t.sub_floor_item_ids]
                states = [paint_of[i][0] for i in needed if i in paint_of]
                if not states or len(states) != len(needed):
                    completion = "unproven"
                elif PAINT_COVERED in states:
                    completion = "covered"
                elif PAINT_UNPROVEN in states:
                    completion = "unproven"
                else:
                    completion = "clear"
            cells.append(CellClosure(
                cell_id=stable_contract_id("shadow_subfloor_cell", {
                    "root": root, "class": key, "lines": (p, q), "along": (a, b)}),
                stroke_width=key, stroke_rgbs=rgbs, pane_lines=(p, q), frame_lines=frame, along=(a, b),
                lo_tick=lo_tick, hi_tick=hi_tick, visible_closed=visible_closed, inside_visible_cell=inside_visible,
                would_close_cell=would, completion_paint=completion))
        if not group["perp_sub"]:
            continue
        for v, _ in panes_vis:
            if any(_same_box(v, w, eq) for w, _ in panes_all):
                continue
            a, b, p, q = v
            inside = sorted({s.ident for s in perp_sub_s if a - eq <= s.offset <= b + eq
                             and s.lo >= p - eq and s.hi <= q + eq})
            displaced.append(DisplacedVisibleCell(stroke_width=key, stroke_rgbs=rgbs, pane_lines=(p, q), along=(a, b),
                                                  hidden_item_ids_in_cell=tuple(inside)))
    return tuple(cells), tuple(displaced)


# --------------------------------------------------------------------------------------
# the core
# --------------------------------------------------------------------------------------


def _floor_for(kind: str) -> tuple[float, str]:
    if kind == ITEM_KIND_LINE:
        return PRODUCER_LINE_ITEM_FLOOR_PT, HIDDEN_BY_EXTRACTOR_LINE_FLOOR
    if kind == ITEM_KIND_RECT_EDGE:
        return PRODUCER_VISIBLE_SEGMENT_FLOOR_PT, HIDDEN_BY_VISIBILITY_SEGMENT_FLOOR
    raise ValueError(f"unknown raw item kind {kind!r}")


def census_sub_floor_ink(
    *, ownership: CensusOwnership, floor_plan_viewports: Sequence[ViewportRef], region_bbox: Optional[Sequence[float]],
    nominated_ids: Optional[Sequence[str]], visible: Sequence[VisibleInk], items: Sequence[RawItem],
    paint: PaintLog, coordinate_quantum_pt: float, visible_inventory_complete: bool = True,
) -> SubFloorInkCensus:
    """Pure core over records the adapter has already re-derived from the producer.

    Exactly one of `region_bbox` (an explicit box in native page coordinates) and `nominated_ids` (visible
    observation ids of one strip; the region is their box grown on every side by the strip's own depth) names the
    region. `floor_plan_viewports` are the page's RESOLVED floor-plan viewports; the named box must lie inside
    exactly one of them or there is no census."""
    if not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0
            and math.isfinite(coordinate_quantum_pt)):
        raise ValueError("a positive finite coordinate quantum is required")
    if (region_bbox is None) == (nominated_ids is None):
        raise ValueError("name the region by exactly one of an explicit box or nominated visible observation ids")
    if type(visible_inventory_complete) is not bool:
        raise ValueError("visible inventory completeness must be an explicit boolean")
    eq = float(coordinate_quantum_pt) * _EQ_FRACTION_OF_QUANTUM
    root = (ownership.document_id, ownership.revision_id, ownership.snapshot_id, ownership.source_sha256,
            ownership.page_id)
    mode = "region" if nominated_ids is None else "nominated"
    nominated = tuple(sorted(nominated_ids)) if nominated_ids is not None else ()
    by_id = {v.observation_id: v for v in visible}
    inventory_ok = visible_inventory_complete       # narrowed below once the region's own ink is known

    def done(status, reason_codes, *, viewport=None, region=None, axis=None, along=None, band=None,
             sub_items=(), unstroked=0, visible_count=0, groups=(), band_edge_ids=(), cells=(), displaced=(),
             would_close=None):
        viewport_id = viewport.view_id if viewport is not None else None
        nomination_id = (stable_contract_id("shadow_subfloor_nomination", {"root": root, "ids": nominated})
                         if mode == "nominated" else None)
        digest = hashlib.sha256("\n".join(sorted(i.item_id for i in sub_items)).encode("utf-8")).hexdigest()
        record_id = stable_contract_id("shadow_subfloor_ink_census", {
            "root": root, "mode": mode, "viewport": viewport_id, "ids": nominated, "region": region,
            "status": status.value, "reasons": tuple(reason_codes), "items": digest, "unstroked": unstroked,
            "cells": tuple(sorted(c.cell_id for c in cells)), "inventory": inventory_ok})
        atom = EvidenceAtom(
            evidence_id=stable_contract_id("shadow_subfloor_ink_census_atom", {"record": record_id}),
            document_id=ownership.document_id, page_id=ownership.page_id, kind=KIND_UNKNOWN,
            method=SUBFLOOR_CENSUS_METHOD, viewport_id=viewport_id, bbox=region, status=status,
            reason_codes=tuple(reason_codes),
            metadata={
                "revision_id": ownership.revision_id, "source_sha256": ownership.source_sha256,
                "snapshot_id": ownership.snapshot_id, "polarity": POLARITY_UNKNOWN, "mode": mode,
                "source_observation_ids": nominated, "sub_floor_item_count": len(sub_items),
                "unstroked_sub_floor_count": unstroked, "would_close_cell": would_close,
                **{flag: False for flag in _GRANT_FLAGS}})
        return SubFloorInkCensus(
            ownership=ownership, viewport_id=viewport_id, mode=mode, status=status, reason_codes=tuple(reason_codes),
            standing_limits=STANDING_LIMITS, nomination_id=nomination_id, nominated_observation_ids=nominated,
            region=region, axis=axis, along_extent=along, band_extent=band,
            extractor_line_floor_pt=PRODUCER_LINE_ITEM_FLOOR_PT,
            visibility_segment_floor_pt=PRODUCER_VISIBLE_SEGMENT_FLOOR_PT, sub_floor_items=tuple(sub_items),
            unstroked_sub_floor_count=unstroked, visible_in_region_count=visible_count, groups=tuple(groups),
            band_edge_item_ids=tuple(band_edge_ids), cells=tuple(cells), displaced_visible_cells=tuple(displaced),
            would_close_cell=would_close, visible_inventory_complete=inventory_ok,
            evidence_atoms=(atom,), record_id=record_id)

    ABSTAIN = EvidenceResolutionStatus.ABSTAINED
    axis: Optional[str] = None
    along = band = None
    if mode == "region":
        try:
            named = tuple(float(v) for v in region_bbox)  # type: ignore[union-attr]
        except (TypeError, ValueError) as exc:
            raise ValueError("an explicit region is four finite numbers") from exc
        if len(named) != 4 or not all(math.isfinite(v) for v in named) or named[0] >= named[2] or named[1] >= named[3]:
            raise ValueError("an explicit region is four finite numbers with x0 < x1 and y0 < y1")
        region = named
    else:
        if (not nominated or len(set(nominated)) != len(nominated) or any(i not in by_id for i in nominated)):
            return done(ABSTAIN, (NOMINATION_NOT_VISIBLE_ON_PAGE,))
        roles = [by_id[i] for i in nominated]
        if any(not r.role_verified or r.stroke_width is None for r in roles):
            return done(ABSTAIN, (SOURCE_ROLE_UNPROVEN, SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE))
        if any(_orientation(r.geometry, eq) not in ("H", "V") for r in roles):
            return done(ABSTAIN, (NOMINATION_NOT_AXIS_ALIGNED,))
        xs = [v for r in roles for v in (r.geometry[0], r.geometry[2])]
        ys = [v for r in roles for v in (r.geometry[1], r.geometry[3])]
        named = (min(xs), min(ys), max(xs), max(ys))
        w, h = named[2] - named[0], named[3] - named[1]
        if abs(w - h) <= eq:
            return done(ABSTAIN, (NOMINATION_AXIS_AMBIGUOUS,))
        axis = "H" if w > h else "V"
        along = (named[0], named[2]) if axis == "H" else (named[1], named[3])
        band = (named[1], named[3]) if axis == "H" else (named[0], named[2])
        depth = band[1] - band[0]          # the strip's own depth, a measured quantity
        if depth <= eq:
            return done(ABSTAIN, (NOMINATION_HAS_NO_DEPTH,), axis=axis, along=along, band=band)
        region = _expand(named, depth)

    holders = [v for v in floor_plan_viewports if _contains(v.bbox, named)]
    if len(holders) != 1:
        return done(ABSTAIN, (OPENING_CANDIDATE_VIEWPORT_SCOPE_UNRESOLVED,), axis=axis, along=along, band=band)
    viewport = holders[0]

    # --- the hidden items of the region ------------------------------------------------------------
    in_region = [it for it in items if _boxes_meet(_bbox(it.geometry), region, eq)]
    hidden: list[tuple[RawItem, float, str]] = []
    unstroked = 0
    for it in in_region:
        if not all(math.isfinite(v) for v in it.geometry):
            raise ValueError("raw item geometry must be finite")
        floor, hidden_by = _floor_for(it.kind)
        length = _length(it.geometry)
        if length >= floor:
            continue
        if not it.stroked:
            unstroked += 1
            continue
        hidden.append((it, length, hidden_by))
    if len(hidden) > _MAX_SUB_FLOOR_ITEMS:
        return done(ABSTAIN, (ITEM_BUDGET_EXCEEDED,), viewport=viewport, region=region, axis=axis, along=along,
                    band=band)
    hidden.sort(key=lambda t: (t[0].drawing_index, t[0].item_index,
                               -1 if t[0].edge_index is None else t[0].edge_index, t[0].item_id))

    # --- producer-visible ink in the region: endpoint coincidence ------------------------------------
    visible_here = [v for v in visible if _boxes_meet(_bbox(v.geometry), region, eq)]
    # a visible segment of the region whose primitive join is not proven is a rival the closure cannot see
    inventory_ok = visible_inventory_complete and all(v.role_verified for v in visible_here)
    cell_size = max(eq, 1e-9)
    grid: dict[tuple[int, int], list[tuple[float, float, str]]] = defaultdict(list)
    for v in visible_here:
        for x, y in ((v.geometry[0], v.geometry[1]), (v.geometry[2], v.geometry[3])):
            grid[(math.floor(x / cell_size), math.floor(y / cell_size))].append((x, y, v.observation_id))

    def visible_at(x: float, y: float) -> tuple[str, ...]:
        cx, cy = math.floor(x / cell_size), math.floor(y / cell_size)
        found = {ident for dx in (-1, 0, 1) for dy in (-1, 0, 1) for px, py, ident in grid.get((cx + dx, cy + dy), ())
                 if abs(px - x) <= eq and abs(py - y) <= eq}
        return tuple(sorted(found))

    # --- paint order ------------------------------------------------------------------------------------
    max_half = max((it.stroke_width or 0.0) / 2.0 for it, _, _ in hidden) if hidden else 0.0
    hull = _expand(region, max_half + eq)
    near = [op for op in paint.ops if _boxes_meet(op.bbox, hull)] if hidden else []
    over_budget = len(hidden) * len(near) > _MAX_PAINT_PAIR_CHECKS
    paint_of: dict[str, tuple[str, str, tuple[int, ...]]] = {}
    for it, _, _ in hidden:
        paint_of[it.item_id] = ((PAINT_UNPROVEN, PAINT_BASIS_BUDGET, ()) if over_budget
                                else _paint_state(it, near, paint))

    # --- per-item records -----------------------------------------------------------------------------
    records: list[SubFloorItem] = []
    band_edge_ids: list[str] = []
    for it, length, hidden_by in hidden:
        g = it.geometry
        orientation = _orientation(g, eq)
        edge_touch = None
        if axis is not None and along is not None and band is not None:
            ends = [((g[0], g[1])), ((g[2], g[3]))]
            lo_touch = hi_touch = False
            for x, y in ends:
                al, ac = (x, y) if axis == "H" else (y, x)
                if along[0] - eq <= al <= along[1] + eq:
                    lo_touch = lo_touch or abs(ac - band[0]) <= eq
                    hi_touch = hi_touch or abs(ac - band[1]) <= eq
            edge_touch = "both" if (lo_touch and hi_touch) else ("lo" if lo_touch else ("hi" if hi_touch else None))
            if edge_touch is not None:
                band_edge_ids.append(it.item_id)
        a_ids, b_ids = visible_at(g[0], g[1]), visible_at(g[2], g[3])
        state, basis, covering = paint_of[it.item_id]
        records.append(SubFloorItem(
            item_id=it.item_id, drawing_index=it.drawing_index, item_index=it.item_index, edge_index=it.edge_index,
            kind=it.kind, hidden_by=hidden_by, geometry=tuple(g), length=length, stroke_width=it.stroke_width,
            stroke_rgb=it.stroke_rgb, stroke_opacity=it.stroke_opacity, solid=it.solid, orientation=orientation,
            strip_relation=_relation(orientation, axis) if axis is not None else None, touches_band_edge=edge_touch,
            endpoint_a_visible_ids=a_ids, endpoint_b_visible_ids=b_ids,
            endpoints_coincide_visible=bool(a_ids or b_ids), paint_order=state, paint_basis=basis,
            covering_drawing_indices=covering, sequence_number=it.sequence_number))

    buckets: dict[tuple, list[SubFloorItem]] = defaultdict(list)
    for r in records:
        buckets[(r.stroke_width, r.stroke_rgb, r.orientation, round(r.length, 2))].append(r)
    groups = [SubFloorGroup(
        stroke_width=k[0], stroke_rgb=k[1], orientation=k[2], length_bucket=k[3], count=len(v),
        line_items=sum(1 for r in v if r.kind == ITEM_KIND_LINE),
        rect_edges=sum(1 for r in v if r.kind == ITEM_KIND_RECT_EDGE),
        endpoint_coincident=sum(1 for r in v if r.endpoints_coincide_visible))
        for k, v in sorted(buckets.items(), key=lambda kv: (kv[0][0] is None, kv[0][0] or 0.0, kv[0][1] or (),
                                                            kv[0][2], kv[0][3]))]
    common = dict(viewport=viewport, region=region, axis=axis, along=along, band=band, sub_items=records,
                  unstroked=unstroked, visible_count=len(visible_here), groups=groups,
                  band_edge_ids=sorted(band_edge_ids))

    if mode == "region":
        reasons = (CLOSURE_NOT_EVALUATED_REGION_MODE,)
        if not inventory_ok:
            reasons += (VISIBLE_INVENTORY_INCOMPLETE,)
        return done(ABSTAIN, reasons, **common)

    closure = _closure(axis=axis, along=along, band=band, visible=visible_here, sub_items=[it for it, _, _ in hidden],
                       paint_of=paint_of, eq=eq, root=root)
    if closure is None:
        return done(ABSTAIN, (ITEM_BUDGET_EXCEEDED,), **common)
    cells, displaced = closure
    completed = [c for c in cells if c.would_close_cell]
    # a completed cell that another pane pair over the same stretch reads differently is an ambiguity, retained
    ambiguous = any(
        d is not c
        and (abs(d.pane_lines[0] - c.pane_lines[0]) > eq or abs(d.pane_lines[1] - c.pane_lines[1]) > eq)
        and min(c.along[1], d.along[1]) - max(c.along[0], d.along[0]) > eq
        for c in completed for d in cells)
    reasons: list[str] = []
    if not completed:
        reasons.append(CENSUS_ONLY_NO_CELL_COMPLETION)
    else:
        if ambiguous:
            reasons.append(CLOSURE_AMBIGUOUS)
        if any(c.completion_paint == "covered" for c in completed):
            reasons.append(COMPLETION_COVERED_BY_LATER_FILL)
        if any(c.completion_paint == "unproven" for c in completed):
            reasons.append(COMPLETION_PAINT_ORDER_UNPROVEN)
    if displaced:
        reasons.append(HIDDEN_TICKS_DISPLACE_VISIBLE_CELL)
    if not inventory_ok:
        reasons.append(VISIBLE_INVENTORY_INCOMPLETE)
    common.update(cells=cells, displaced=displaced, would_close=bool(completed))
    if completed and not reasons:
        return done(EvidenceResolutionStatus.CANDIDATE, (SUB_FLOOR_TICKS_WOULD_CLOSE_CELL,), **common)
    return done(ABSTAIN, tuple(reasons), **common)


# --------------------------------------------------------------------------------------
# producer adapter
# --------------------------------------------------------------------------------------

_SOLID_DASH = re.compile(r"\s*\[\s*\]\s*[-+]?(?:\d+(?:\.\d*)?|\.\d+)\s*")
_NON_PAINTING_KINDS = frozenset({"ignore-text"})
_BM_AFTER = re.compile(r"/BM\s*(?:/([A-Za-z0-9]+)|\[([^\]]*)\])")


def _line_points(item) -> Optional[tuple[float, float, float, float]]:
    """The producer's own point reading of a line item (attribute access, then indexing)."""
    p1, p2 = item[1], item[2]
    try:
        values = (float(p1.x), float(p1.y), float(p2.x), float(p2.y))
    except (AttributeError, TypeError, ValueError):
        try:
            values = (float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]))
        except (TypeError, ValueError, IndexError, KeyError):
            return None
    return values if all(math.isfinite(v) for v in values) else None


def _rect_corners(item) -> Optional[tuple[float, float, float, float]]:
    rect = item[1]
    try:
        values = tuple(map(float, (rect.x0, rect.y0, rect.x1, rect.y1)))
    except (AttributeError, TypeError, ValueError):
        return None
    return values if all(math.isfinite(v) for v in values) else None


def _enumerate_raw_items(drawings, clip_table):
    """Every line item and rectangle edge of the page in the producer's id space.

    Returns (items, required_ids, clip_by_path). `required_ids` is the id set the producer's extraction must
    contain, which pins the producer's floor on this very page (a line item is required exactly when it is not
    shorter than the floor; every rectangle edge is required). `clip_by_path` is the producer's own clip proof of
    every drawing, read through the producer's own clip association (pb_vector_geometry_v130)."""
    from pb_vector_geometry_v130 import _resolve_clip_proof_fields

    items: list[RawItem] = []
    required: set[str] = set()
    clip_by_path: dict[int, tuple] = {}
    for draw_index, drawing in enumerate(drawings):
        if not isinstance(drawing, dict):
            continue
        width, stroke = drawing.get("width"), drawing.get("color")
        stroked = "width" in drawing and width is not None and "color" in drawing and stroke is not None
        seqno = drawing.get("seqno")
        sequence = seqno if type(seqno) is int else None
        sequence_end = None if sequence is None else (sequence + 1 if drawing.get("type") == "fs" else sequence)
        opacity = drawing.get("stroke_opacity")
        solid = bool(_SOLID_DASH.fullmatch(str(drawing.get("dashes") or "")))
        rgb = tuple(float(c) for c in stroke) if stroke is not None else None
        stroke_width = float(width) if (stroked and type(width) in (int, float)) else None
        known, present, _scissor, shape_known, exact = _resolve_clip_proof_fields(
            clip_table=clip_table, seq_key=sequence)
        clip_by_path[draw_index] = (known, present, shape_known, tuple(exact) if exact is not None else None)
        common = dict(drawing_index=draw_index, stroked=bool(stroked and stroke_width is not None),
                      stroke_width=stroke_width, stroke_rgb=rgb,
                      stroke_opacity=float(opacity) if type(opacity) in (int, float) else None, solid=solid,
                      sequence_number=sequence, sequence_end=sequence_end, clip_known=bool(known),
                      clip_present=bool(present),
                      clip_exact_rect=tuple(exact) if (known and present and shape_known and exact is not None) else None)
        for item_index, item in enumerate(drawing.get("items", [])):
            if not item:
                continue
            kind = str(item[0])
            if kind == "l" and len(item) >= 3:
                points = _line_points(item)
                if points is None:
                    continue
                ident = f"d{draw_index}i{item_index}"
                if _length(points) >= PRODUCER_LINE_ITEM_FLOOR_PT:
                    required.add(ident)
                items.append(RawItem(item_id=ident, item_index=item_index, edge_index=None, kind=ITEM_KIND_LINE,
                                     geometry=points, **common))
            elif kind == "re" and len(item) >= 2:
                corners = _rect_corners(item)
                if corners is None:
                    continue
                x0, y0, x1, y1 = corners
                pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
                for edge in range(4):
                    a, b = pts[edge], pts[(edge + 1) % 4]
                    ident = f"d{draw_index}i{item_index}e{edge}"
                    required.add(ident)
                    items.append(RawItem(item_id=ident, item_index=item_index, edge_index=edge,
                                         kind=ITEM_KIND_RECT_EDGE, geometry=(a[0], a[1], b[0], b[1]), **common))
    return items, required, clip_by_path


def _axis_rectangle(items) -> Optional[Box]:
    """The rectangle a fill path is, when it is exactly one axis-aligned rectangle; otherwise None."""
    if len(items) == 1 and str(items[0][0]) == "re":
        corners = _rect_corners(items[0])
        if corners is None:
            return None
        return (min(corners[0], corners[2]), min(corners[1], corners[3]),
                max(corners[0], corners[2]), max(corners[1], corners[3]))
    if len(items) == 4 and all(str(i[0]) == "l" and len(i) >= 3 for i in items):
        pts = [_line_points(i) for i in items]
        if any(p is None for p in pts):
            return None
        for k in range(4):
            nxt = pts[(k + 1) % 4]
            if (pts[k][2], pts[k][3]) != (nxt[0], nxt[1]):
                return None
            if not (pts[k][0] == pts[k][2] or pts[k][1] == pts[k][3]):
                return None
        xs = {v for p in pts for v in (p[0], p[2])}
        ys = {v for p in pts for v in (p[1], p[3])}
        if len(xs) != 2 or len(ys) != 2:
            return None
        return (min(xs), min(ys), max(xs), max(ys))
    return None


def _blend_or_softmask_present(document) -> bool:
    """Is any blend mode other than Normal, or any soft mask, defined anywhere in the document?

    A cover claim needs painting to be plain source-over; this scans every object dictionary, so a positive (or an
    unreadable object, or an unparseable blend entry) only ever makes a cover claim unproven."""
    for xref in range(1, document.xref_length()):
        try:
            text = document.xref_object(xref, compressed=True)
        except (RuntimeError, ValueError):
            return True
        if "/BM" in text:
            found = False
            for m in _BM_AFTER.finditer(text):
                found = True
                names = [m.group(1)] if m.group(1) else re.findall(r"/([A-Za-z0-9]+)", m.group(2) or "")
                if any(n not in ("Normal", "Compatible") for n in names):
                    return True
            if not found:
                return True
        if "/SMask" in text and "/Image" not in text and not re.search(r"/SMask\s*/None", text):
            return True
    return False


def _build_paint_log(page, drawings, clip_by_path: dict, blend_unproven: bool) -> PaintLog:
    """The page's own paint log, with each drawing's sequence number proven to index it (else nothing is decided)."""
    try:
        log = list(page.get_bboxlog())
    except (RuntimeError, ValueError, AttributeError):
        return PaintLog((), False, "paint_log_unavailable")
    roles: dict[int, tuple[int, str]] = {}
    for k, drawing in enumerate(drawings):
        sequence, kind = drawing.get("seqno"), drawing.get("type")
        if type(sequence) is not int or sequence < 0 or kind not in ("s", "f", "fs"):
            return PaintLog((), False, "drawing_sequence_unavailable")
        wanted = [(sequence, "stroke-path" if kind == "s" else "fill-path")]
        if kind == "fs":
            wanted.append((sequence + 1, "stroke-path"))
        for index, wanted_kind in wanted:
            if index in roles or index >= len(log) or str(log[index][0]) != wanted_kind:
                return PaintLog((), False, "paint_log_not_aligned_with_drawing_sequence")
            logged = tuple(float(v) for v in log[index][1])
            r = drawing.get("rect")
            if r is None or len(logged) != 4 or not (
                    logged[0] <= r[0] + _PAINT_LOG_SLACK and logged[1] <= r[1] + _PAINT_LOG_SLACK
                    and logged[2] >= r[2] - _PAINT_LOG_SLACK and logged[3] >= r[3] - _PAINT_LOG_SLACK):
                return PaintLog((), False, "paint_log_not_aligned_with_drawing_sequence")
            roles[index] = (k, wanted_kind)
    ops: list[PaintOp] = []
    for index, entry in enumerate(log):
        kind = str(entry[0])
        if kind in _NON_PAINTING_KINDS:
            continue
        bbox = tuple(float(v) for v in entry[1])
        if index not in roles:
            ops.append(PaintOp(index, kind, bbox))
            continue
        k, role = roles[index]
        drawing = drawings[k]
        cover = segments = None
        black = False
        if role == "fill-path":
            cover = _opaque_cover(drawing, clip_by_path.get(k), blend_unproven)
        else:
            segments = _stroke_reach(drawing)
            opacity = drawing.get("stroke_opacity")
            black = (not blend_unproven and _is_black(drawing.get("color")) and type(opacity) in (int, float)
                     and opacity == 1.0)
        ops.append(PaintOp(index, kind, bbox, k, cover, segments, black))
    return PaintLog(tuple(ops), True, "")


def _opaque_cover(drawing, clip, blend_unproven: bool) -> Optional[Box]:
    """The rectangle a fill provably paints with plain opaque source-over, else None.

    Not proven: any blend mode or soft mask in the document, a translucent or absent fill, a path that is not exactly
    one axis-aligned rectangle, a clip the producer cannot prove, and a drawing that carries optional content (a
    layer that may be switched off paints nothing)."""
    if blend_unproven or drawing.get("type") not in ("f", "fs"):
        return None
    if drawing.get("layer") or drawing.get("oc"):
        return None
    opacity = drawing.get("fill_opacity")
    if not drawing.get("fill") or type(opacity) not in (int, float) or opacity != 1.0:
        return None
    rect = _axis_rectangle(drawing.get("items") or ())
    if rect is None or clip is None:
        return None
    known, present, shape_known, exact = clip
    if not known:
        return None
    if present:
        if not shape_known or exact is None or len(exact) != 4:
            return None
        rect = (max(rect[0], exact[0]), max(rect[1], exact[1]), min(rect[2], exact[2]), min(rect[3], exact[3]))
        if rect[0] >= rect[2] or rect[1] >= rect[3]:
            return None
    return rect


def _stroke_reach(drawing):
    width = drawing.get("width")
    if type(width) not in (int, float):
        return None
    half = float(width) / 2.0
    out: list[tuple[float, float, float, float, float]] = []
    for item in drawing.get("items") or ():
        kind = str(item[0])
        if kind == "l" and len(item) >= 3:
            p = _line_points(item)
            if p is None:
                return None
            out.append((p[0], p[1], p[2], p[3], half))
        elif kind == "re" and len(item) >= 2:
            c = _rect_corners(item)
            if c is None:
                return None
            pts = [(c[0], c[1]), (c[2], c[1]), (c[2], c[3]), (c[0], c[3])]
            out.extend((pts[e][0], pts[e][1], pts[(e + 1) % 4][0], pts[(e + 1) % 4][1], half) for e in range(4))
        else:
            return None
    return tuple(out)


class SubFloorInkCensusShadow:
    """Read-only census bound to one `SourceVisibilityProducer`; default OFF.

    Every record is re-derived from the producer's own immutable bytes; the caller supplies only the revision, the
    page, the lattice quantum and a region (an explicit box or nominated visible observation ids). There is no
    channel for widths, colours, roles, paint order or provenance."""

    def __init__(self, source, *, enabled: bool = False):
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be a producer-owned SourceVisibilityProducer")
        if type(enabled) is not bool:
            raise ValueError("sub-floor ink census gate must be an explicit boolean")
        self._source = source
        self._enabled = enabled

    @staticmethod
    def _failure(*codes: str) -> SubFloorInkCensus:
        return SubFloorInkCensus(
            ownership=None, viewport_id=None, mode=None, status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=tuple(codes), standing_limits=STANDING_LIMITS, nomination_id=None,
            nominated_observation_ids=(), region=None, axis=None, along_extent=None, band_extent=None,
            extractor_line_floor_pt=PRODUCER_LINE_ITEM_FLOOR_PT,
            visibility_segment_floor_pt=PRODUCER_VISIBLE_SEGMENT_FLOOR_PT, sub_floor_items=(),
            unstroked_sub_floor_count=0, visible_in_region_count=0, groups=(), band_edge_item_ids=(), cells=(),
            displaced_visible_cells=(), would_close_cell=None, visible_inventory_complete=True, evidence_atoms=(),
            record_id=None)

    def census(self, *, revision_id: str, page_id: int, coordinate_quantum_pt: float,
               region_bbox: Optional[Sequence[float]] = None,
               nominated_observation_ids: Optional[Sequence[str]] = None) -> SubFloorInkCensus:
        if not self._enabled:
            return self._failure(CENSUS_DISABLED)
        if (type(revision_id) is not str or type(page_id) is not int
                or not (type(coordinate_quantum_pt) in (int, float) and coordinate_quantum_pt > 0
                        and math.isfinite(coordinate_quantum_pt))):
            raise ValueError("revision id, integer page id and a positive quantum required")
        if (region_bbox is None) == (nominated_observation_ids is None):
            raise ValueError("name the region by exactly one of region_bbox and nominated_observation_ids")
        nominated = None
        if nominated_observation_ids is not None:
            if isinstance(nominated_observation_ids, (str, bytes)):
                raise ValueError("nominated observation ids are non-empty strings")
            nominated = tuple(nominated_observation_ids)        # a one-shot iterable is read exactly once
            if any(type(i) is not str or not i for i in nominated):
                raise ValueError("nominated observation ids are non-empty strings")
        region = None
        if region_bbox is not None:
            if isinstance(region_bbox, (str, bytes)):
                raise ValueError("region_bbox is four finite numbers with x0 < x1 and y0 < y1")
            region = tuple(region_bbox)
            if (len(region) != 4 or any(type(v) not in (int, float) or not math.isfinite(v) for v in region)
                    or region[0] >= region[2] or region[1] >= region[3]):
                raise ValueError("region_bbox is four finite numbers with x0 < x1 and y0 < y1")
        import fitz

        from pb_source_observation_authority import ObservationSelector
        from pb_source_visibility_authority import VISIBLE_SOURCE_OBSERVATION_EXISTS
        from pb_vector_geometry_v130 import _clip_scissor_by_seqno, extract_native_page
        from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports

        source = self._source
        published = source.published_snapshot_for_revision(revision_id)
        if published is None:
            return self._failure(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        document_id = published.revision.document_id
        if (page_id not in tuple(int(v) for v in published.coverage.decoded_pages)
                or int(page_id) in tuple(int(v) for v in published.coverage.failed_pages)
                or source._producer.current_revision_id(document_id) != revision_id):
            return self._failure(VISIBLE_SOURCE_AUTHORITY_REQUIRED)
        source_bytes = source._producer._store.source_bytes_by_revision.get(revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != published.revision.source_sha256:
            return self._failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
        ownership = CensusOwnership(document_id, revision_id, published.snapshot.snapshot_id,
                                    published.revision.source_sha256, str(page_id))

        def selector(observation_id: str) -> ObservationSelector:
            return ObservationSelector(document_id, revision_id, ownership.source_sha256, ownership.snapshot_id,
                                       observation_id)

        # one pass over the immutable page: the producer's own primitives, the raw drawing list in the same index
        # space, the clip proof, the paint log, and the viewport census
        with fitz.open(stream=bytes(source_bytes), filetype="pdf") as document:
            page = document[page_id - 1]
            drawings = page.get_drawings() or []
            primitives = {s["id"]: s for s in extract_native_page(page)["segments"]}
            segmented = segment_page_viewports(page, page_number=page_id)
            raw_items, required_ids, clip_by_path = _enumerate_raw_items(drawings, _clip_scissor_by_seqno(page))
            if set(primitives) != required_ids:
                return self._failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
            paint = _build_paint_log(page, drawings, clip_by_path, _blend_or_softmask_present(document))

        # visible observations re-resolved by the producer's authority and joined to its own primitive
        visibility = source.authority()
        visible: list[VisibleInk] = []
        inventory_complete = True
        for observation_id in published.visible_observation_ids:
            result = visibility.resolve_visible(selector(observation_id))
            observation = result.observation
            if (result.status is not EvidenceResolutionStatus.CORROBORATED
                    or result.proposition != VISIBLE_SOURCE_OBSERVATION_EXISTS or observation is None):
                inventory_complete = False
                continue
            # a positive wrapper does not authenticate a foreign observation: immutable identity first
            if (observation.observation_id != observation_id or observation.document_id != document_id
                    or observation.revision_id != revision_id or observation.source_sha256 != ownership.source_sha256
                    or observation.snapshot_id != ownership.snapshot_id):
                return self._failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)
            if str(observation.page_id) != str(page_id):
                continue
            raw_geometry = observation.geometry
            if (type(raw_geometry) not in (tuple, list) or len(raw_geometry) != 4
                    or any(type(v) not in (int, float) for v in raw_geometry)):
                inventory_complete = False
                continue
            try:
                geometry = tuple(float(v) for v in raw_geometry)
            except OverflowError:
                inventory_complete = False
                continue
            if not all(math.isfinite(v) for v in geometry):
                inventory_complete = False
                continue
            if _length(geometry) < PRODUCER_VISIBLE_SEGMENT_FLOOR_PT:
                return self._failure(SNAPSHOT_OBSERVATION_INTEGRITY_FAILURE)      # the producer's floor moved
            primitive = primitives.get(str(observation.source_primitive_ref).removeprefix("visible:segment:"))
            joined = (primitive is not None
                      and geometry == (float(primitive["x1"]), float(primitive["y1"]),
                                       float(primitive["x2"]), float(primitive["y2"])))
            stroked = joined and bool(primitive.get("width_present")) and bool(primitive.get("stroke_present"))
            solid_opaque = False
            if joined:
                path_index = primitive.get("path_index")
                drawing = drawings[path_index] if (type(path_index) is int and 0 <= path_index < len(drawings)) else None
                if not isinstance(drawing, dict) or drawing.get("seqno") != primitive.get("sequence_number"):
                    joined = stroked = False
                elif stroked:
                    opacity = drawing.get("stroke_opacity")
                    solid_opaque = (bool(_SOLID_DASH.fullmatch(str(primitive.get("dashes", ""))))
                                    and type(opacity) in (int, float) and math.isfinite(opacity) and opacity == 1.0)
            visible.append(VisibleInk(
                observation_id=str(observation_id), geometry=geometry,
                stroke_width=float(primitive["width"]) if stroked else None,
                stroke_rgb=tuple(float(c) for c in primitive["stroke"]) if stroked else None,
                solid_opaque=solid_opaque, role_verified=bool(joined)))

        floor_plans = tuple(
            ViewportRef(str(v.view_id), tuple(float(c) for c in v.bounding_box)) for v in segmented
            if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box is not None
            and v.view_type == "floor_plan")
        return census_sub_floor_ink(
            ownership=ownership, floor_plan_viewports=floor_plans,
            region_bbox=tuple(float(v) for v in region) if region is not None else None,
            nominated_ids=nominated, visible=visible, items=raw_items, paint=paint,
            coordinate_quantum_pt=float(coordinate_quantum_pt), visible_inventory_complete=inventory_complete)


__all__ = [
    "CENSUS_DISABLED", "CellClosure", "CensusOwnership", "DisplacedVisibleCell", "HIDDEN_BY_EXTRACTOR_LINE_FLOOR",
    "HIDDEN_BY_VISIBILITY_SEGMENT_FLOOR", "PAINT_CLEAR", "PAINT_COVERED", "PAINT_UNPROVEN", "PRODUCER_LINE_ITEM_FLOOR_PT",
    "PRODUCER_VISIBLE_SEGMENT_FLOOR_PT", "PaintLog", "PaintOp", "RawItem", "SUBFLOOR_INK_CENSUS_SCHEMA_VERSION",
    "STANDING_LIMITS", "SUB_FLOOR_TICKS_WOULD_CLOSE_CELL", "SubFloorGroup", "SubFloorInkCensus",
    "SubFloorInkCensusShadow", "SubFloorItem", "TickSupport", "ViewportRef", "VisibleInk", "census_sub_floor_ink",
]
