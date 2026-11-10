"""Shadow-only diagnostic: a printed width that lies INSIDE a door's swing drawing belongs to that door.

Owner rule (2026-11-10): "if the measurement is inside the door swinging drawing then it is for the door".

This core turns that rule into an independent, geometry-only CHECK of which printed figure belongs to a plan opening.
It never reads the figure's value, never replaces the opening label authority and never writes a width, a kind, a host
or a quantity: the result is a ``CANDIDATE`` binding with receipts that a reviewer can compare with the label
authority's own choice.

Rules
-----
* A swing is a quarter-circle arc whose bounding box is square (``SQUARE_TOL``). Its HINGE is the bounding-box corner
  that is one radius from both arc ends AND from the arc's midpoint (the opposite corner is one radius from the ends but
  not from the midpoint) and that lies within the opening's OWN wall thickness of one opening end.
* An opening whose wall thickness is not smaller than its length is not a measured door opening and abstains (a thickness
  that large would accept any arc).
* The leaf length (the radius) must match the opening length within that same wall thickness (a leaf is shorter than the
  clear opening by at most its frame reveal, which cannot exceed the wall depth). A double-leaf door (two half-radius
  arcs), a sliding door, a garage door and a window-corner fillet therefore have NO hinged swing here and abstain.
* A figure is INSIDE a swing only when all four corners of its box lie inside the arc's square and within one radius of
  the hinge. A figure with some corners inside is a boundary straddler and makes the binding ambiguous.
* Exactly one hinged swing per opening, exactly one figure-like word inside it, no straddler, and that figure inside no
  other hinged swing; anything else abstains with a named reason. Several opening records that share one swing share its
  figure (they are one physical door drawn once).
* Only the figure's geometry is used. Its numeric value, the opening's measured width and any benchmark value never
  decide the binding.
* Pure, deterministic, order-invariant, no input mutation, default off (``enabled`` must be a strict bool). Nothing in
  production imports this module.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"
SQUARE_TOL = 0.05          # arc bounding box square within this fraction of its side
HINGE_CORNER_TOL = 0.05    # a corner is one radius from both arc ends within this fraction of the radius
BOX_TOL_PT = 0.01          # containment slack for coordinates that coincide on an edge

FIGURE_RE = re.compile(r"^\d{1,2},?\d{3}$|^\d{3}$")

SWING_BINDING_CANDIDATE = "door_swing_figure_binding_candidate_shadow"
NO_HINGED_SWING = "no_swing_hinged_at_this_opening_with_leaf_length_equal_to_its_length"
MULTIPLE_HINGED_SWINGS = "more_than_one_distinct_swing_hinged_at_this_opening"
NO_FIGURE_IN_SWING = "no_figure_word_inside_the_swing"
MULTIPLE_FIGURES_IN_SWING = "more_than_one_figure_word_inside_the_swing"
FIGURE_STRADDLES_SWING = "figure_word_straddles_the_swing_boundary"
FIGURE_IN_MULTIPLE_SWINGS = "figure_word_inside_more_than_one_hinged_swing"
IMPLAUSIBLE_OPENING = "opening_wall_thickness_not_less_than_its_length"
INVALID_INPUT = "door_swing_binding_input_invalid"
GATE_PROMOTION = "authority_promotion_review_required_label_authority_untouched"

TEXT_CORROBORATED = "corroborated"
TEXT_RAW = "raw_unverified"


@dataclass(frozen=True)
class SwingArc:
    """A quarter-circle arc: its end points and the point halfway along it (page points).

    The midpoint is what says WHICH corner of the arc's square is the centre: the arc bulges away from its centre, so its
    midpoint is one radius from the hinge and only 0.41 radius from the opposite corner.
    """

    arc_id: str
    sx: float
    sy: float
    ex: float
    ey: float
    mx: float
    my: float
    receipt_ids: tuple[str, ...] = ()

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return (min(self.sx, self.ex), min(self.sy, self.ey), max(self.sx, self.ex), max(self.sy, self.ey))


@dataclass(frozen=True)
class OpeningEnds:
    opening_id: str
    ax: float
    ay: float
    bx: float
    by: float
    thickness: float
    receipt_ids: tuple[str, ...] = ()

    @property
    def length(self) -> float:
        return math.hypot(self.bx - self.ax, self.by - self.ay)


@dataclass(frozen=True)
class FigureWord:
    word_id: str
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    text_trust: str = ""
    receipt_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SwingFigureBinding:
    opening_id: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    figure_word_id: Optional[str] = None
    figure_text: Optional[str] = None
    printed_figure_value: Optional[float] = None
    swing_arc_id: Optional[str] = None
    hinge: Optional[tuple[float, float]] = None
    text_trust: str = ""
    source_observation_ids: tuple[str, ...] = ()
    result_id: Optional[str] = None
    schema_version: str = SCHEMA_VERSION

    @property
    def is_candidate(self) -> bool:
        return self.status is EvidenceResolutionStatus.CANDIDATE


def _finite(*values) -> bool:
    return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in values)


def _result(opening_id, status, reasons, **kw) -> SwingFigureBinding:
    payload = {
        "schema_version": SCHEMA_VERSION, "opening": opening_id, "status": status.value, "reasons": tuple(reasons),
        "figure": kw.get("figure_word_id"), "swing": kw.get("swing_arc_id"), "hinge": kw.get("hinge"),
        "trust": kw.get("text_trust", ""), "receipts": tuple(kw.get("source_observation_ids", ())),
    }
    return SwingFigureBinding(opening_id=opening_id, status=status, reason_codes=tuple(reasons),
                              result_id=stable_contract_id("door_swing_figure_binding_shadow", payload, digest_chars=32), **kw)


def hinge_corners(arc: SwingArc) -> tuple[tuple[float, float], ...]:
    """The bounding-box corner one radius from both arc ends AND from its midpoint (the centre); empty if not a quarter arc."""
    x0, y0, x1, y1 = arc.bbox
    w, h = x1 - x0, y1 - y0
    side = max(w, h)
    if side <= 0 or abs(w - h) > SQUARE_TOL * side:
        return ()
    out = []
    for cx, cy in ((x0, y0), (x1, y0), (x0, y1), (x1, y1)):
        if (abs(math.hypot(cx - arc.sx, cy - arc.sy) - side) <= HINGE_CORNER_TOL * side
                and abs(math.hypot(cx - arc.ex, cy - arc.ey) - side) <= HINGE_CORNER_TOL * side
                and abs(math.hypot(cx - arc.mx, cy - arc.my) - side) <= HINGE_CORNER_TOL * side):
            out.append((cx, cy))
    return tuple(out)


def _radius(arc: SwingArc) -> float:
    x0, y0, x1, y1 = arc.bbox
    return max(x1 - x0, y1 - y0)


def _corner_state(arc: SwingArc, hinge, figure: FigureWord) -> str:
    """``inside`` (all four corners in the quarter disc), ``partial`` (some) or ``outside``."""
    x0, y0, x1, y1 = arc.bbox
    r = _radius(arc)
    inside = 0
    for px, py in ((figure.x0, figure.y0), (figure.x1, figure.y0), (figure.x0, figure.y1), (figure.x1, figure.y1)):
        if (x0 - BOX_TOL_PT <= px <= x1 + BOX_TOL_PT and y0 - BOX_TOL_PT <= py <= y1 + BOX_TOL_PT
                and math.hypot(px - hinge[0], py - hinge[1]) <= r + BOX_TOL_PT):
            inside += 1
    return "inside" if inside == 4 else ("partial" if inside else "outside")


def _valid(openings, arcs, figures) -> bool:
    for o in openings:
        if not o.opening_id or not _finite(o.ax, o.ay, o.bx, o.by, o.thickness) or o.thickness <= 0 or o.length <= 0:
            return False
    for a in arcs:
        if not a.arc_id or not _finite(a.sx, a.sy, a.ex, a.ey, a.mx, a.my):
            return False
    for f in figures:
        if not f.word_id or not isinstance(f.text, str) or not _finite(f.x0, f.y0, f.x1, f.y1) or f.x1 < f.x0 or f.y1 < f.y0:
            return False
    return (len({o.opening_id for o in openings}) == len(openings) and len({a.arc_id for a in arcs}) == len(arcs)
            and len({f.word_id for f in figures}) == len(figures))


SIGNATURE_PT = 0.1         # arcs whose hinge, radius and midpoint agree to this are one swing painted more than once


def _signature(arc: SwingArc, hinge) -> tuple:
    q = SIGNATURE_PT
    return (round(hinge[0] / q), round(hinge[1] / q), round(_radius(arc) / q), round(arc.mx / q), round(arc.my / q))


def _hinged(opening: OpeningEnds, arcs: Sequence[SwingArc]):
    """(arc, hinge) pairs hinged at this opening with a leaf as long as the opening, within the wall thickness."""
    found = []
    for arc in arcs:
        for hinge in hinge_corners(arc):
            d_end = min(math.hypot(hinge[0] - opening.ax, hinge[1] - opening.ay),
                        math.hypot(hinge[0] - opening.bx, hinge[1] - opening.by))
            if d_end <= opening.thickness and abs(_radius(arc) - opening.length) <= opening.thickness:
                found.append((arc, hinge))
    return found


def bind_figures_to_swings(
    openings: Sequence[OpeningEnds],
    arcs: Sequence[SwingArc],
    figures: Sequence[FigureWord],
    *,
    enabled: bool = False,
) -> tuple[SwingFigureBinding, ...]:
    """One binding per opening (sorted by opening id). Empty unless ``enabled`` is exactly ``True``."""
    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a strict bool")
    if not enabled:
        return ()
    ordered = sorted(openings, key=lambda o: o.opening_id)
    if not _valid(openings, arcs, figures):
        return tuple(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (INVALID_INPUT,)) for o in ordered)
    figs = sorted((f for f in figures if FIGURE_RE.match(f.text.strip())), key=lambda f: f.word_id)
    hinged_by_opening = {o.opening_id: _hinged(o, arcs) for o in ordered}
    # every distinct hinged swing (one entry per arc and hinge), used to test that a figure is in only one swing
    all_swings = {}
    for pairs in hinged_by_opening.values():
        for arc, hinge in pairs:
            all_swings.setdefault(_signature(arc, hinge), (arc, hinge))
    out = []
    for o in ordered:
        if o.thickness >= o.length:            # the wall thickness is the tolerance: it must be smaller than the leaf it measures
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (IMPLAUSIBLE_OPENING,)))
            continue
        pairs = hinged_by_opening[o.opening_id]
        distinct = {_signature(arc, hinge) for arc, hinge in pairs}
        if not distinct:
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (NO_HINGED_SWING,)))
            continue
        if len(distinct) > 1:
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (MULTIPLE_HINGED_SWINGS,)))
            continue
        arc, hinge = sorted(pairs, key=lambda p: (p[1], p[0].arc_id))[0]
        painted = [a for a, h in pairs if _signature(a, h) == _signature(arc, hinge)]     # the same swing painted more than once
        states = [(f, _corner_state(arc, hinge, f)) for f in figs]
        inside = [f for f, s in states if s == "inside"]
        partial = [f for f, s in states if s == "partial"]
        if len(inside) > 1:
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (MULTIPLE_FIGURES_IN_SWING,), swing_arc_id=arc.arc_id))
            continue
        if partial:
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (FIGURE_STRADDLES_SWING,), swing_arc_id=arc.arc_id))
            continue
        if not inside:
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (NO_FIGURE_IN_SWING,), swing_arc_id=arc.arc_id))
            continue
        figure = inside[0]
        holders = {key for key, (a, h) in all_swings.items() if _corner_state(a, h, figure) == "inside"}
        if len(holders) > 1:
            out.append(_result(o.opening_id, EvidenceResolutionStatus.ABSTAINED, (FIGURE_IN_MULTIPLE_SWINGS,), swing_arc_id=arc.arc_id))
            continue
        receipts = tuple(sorted(set(figure.receipt_ids) | {r for a in painted for r in a.receipt_ids} | set(o.receipt_ids)))
        trust = (TEXT_CORROBORATED if figure.text_trust == TEXT_CORROBORATED
                 else TEXT_RAW if figure.text_trust == TEXT_RAW else "")
        out.append(_result(
            o.opening_id, EvidenceResolutionStatus.CANDIDATE, (SWING_BINDING_CANDIDATE,), figure_word_id=figure.word_id,
            figure_text=figure.text.strip(), printed_figure_value=float(figure.text.strip().replace(",", "")),
            swing_arc_id=min(a.arc_id for a in painted), hinge=hinge, text_trust=trust, source_observation_ids=receipts))
    return tuple(out)


__all__ = [
    "FIGURE_IN_MULTIPLE_SWINGS", "FIGURE_STRADDLES_SWING", "FigureWord", "GATE_PROMOTION", "IMPLAUSIBLE_OPENING", "INVALID_INPUT",
    "MULTIPLE_FIGURES_IN_SWING", "MULTIPLE_HINGED_SWINGS", "NO_FIGURE_IN_SWING", "NO_HINGED_SWING", "OpeningEnds",
    "SWING_BINDING_CANDIDATE", "SwingArc", "SwingFigureBinding", "bind_figures_to_swings", "hinge_corners",
]
