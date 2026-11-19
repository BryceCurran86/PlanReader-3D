"""AG-01..AG-04: Door symbol legend reader and opening classifier.

Reads architectural legend panels to identify symbol variants (hinged/swing,
cavity slider, bifold, pivot, push-pull) and classifies door symbols found on
floor-plan pages by matching against those legend exemplars.

**Source rule:** A legend symbol only authorises classification — it never
issues a physical opening count or customer quantity.  Every classified mark
remains TOPOLOGY_ONLY until an upstream physical-opening producer authenticates
host wall ends, jamb returns and threshold.

**Production wiring:** Called by ``pb_planreader_pdf_extractor`` for every
floor-plan page.  Results feed ``pb_source_internal_door_completeness_shadow``
to upgrade its classification tier from NEEDS_HOST → LEGEND_TYPED.

**Scope (Antigravity):** symbol reading, legend matching, classification.
Cursor owns generic topology/geometry; GPT1 owns Acacia/Q5446 integration;
GPT2 owns Maryborough authoritative quantities.

HOLD FIRM: does not modify frozen120 benchmark, does not issue commercial
quantities, does not overwrite another lane's claimed files.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import math
import re
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Layer name patterns for internal/external wall paths
_WALL_INTERNAL = re.compile(r"WallInternal|Wall_Internal|InternalWall", re.I)
_WALL_EXTERNAL = re.compile(r"WallExternal|Wall_External|ExternalWall", re.I)
_WALL_ANY = re.compile(r"Wall", re.I)

# Width annotation: 600–1400 mm (door-sized), possibly with comma separating thousands
_WIDTH_MM = re.compile(r"^(?:6\d\d|7\d\d|8\d\d|9\d\d|1[,]?[0-4]\d\d)$")

# Text tokens that identify legend panel headings
_LEGEND_HEADING = re.compile(
    r"(?:LEGEND|SYMBOL|SCHEDULE|DOOR\s+TYPE|WINDOW\s+TYPE|NOTES|KEY)", re.I
)

# Door type keyword patterns
_SWING_TOKENS = re.compile(r"\b(?:SWING|HINGED?|SOLID|FLUSH|PANEL|BATTEN|TIMBER|STEEL"
                           r"|GLAZED|FD\d*|SD\d*)\b", re.I)
_SLIDER_TOKENS = re.compile(r"\b(?:CS|CAVITY\s*SLID|SLIDING|POCKET)\b", re.I)
_BIFOLD_TOKENS = re.compile(r"\b(?:BF|BIFOLD|BI[-\s]?FOLD)\b", re.I)
_PIVOT_TOKENS = re.compile(r"\b(?:PIVOT)\b", re.I)
_PUSHPULL_TOKENS = re.compile(r"\b(?:PUSH|PULL|PUSH[/-]PULL|DOUBLE\s+SWING)\b", re.I)
_ABSTAIN_TOKENS = re.compile(r"\b(?:ABSTAIN|REFER|NTS|TBD|CONFIRM)\b", re.I)

# Arc detection: quarter-circle swing arc has an included angle near 90°
_ARC_ANGLE_DEG_MIN = 80.0
_ARC_ANGLE_DEG_MAX = 100.0

# Geometric proximity threshold (PDF points) for associating text with paths
_ASSOC_RADIUS_PTS = 20.0

# Minimum arc radius to treat as a door (not a rounded corner decoration)
_ARC_RADIUS_MIN_PTS = 4.0
_ARC_RADIUS_MAX_PTS = 60.0  # above this it's likely a room curve


# ---------------------------------------------------------------------------
# Public dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class LegendDoorVariant:
    """A single door-type variant extracted from an architectural legend panel."""

    kind: str                           # "hinged", "cavity_slider", "bifold", "pivot",
                                        #  "push_pull", "unknown"
    label_text: str                     # raw text from legend (e.g. "CS 820")
    arc_path_ids: tuple[int, ...]       # drawing path indices that form the legend arc
    leaf_path_ids: tuple[int, ...]      # straight leaf strokes
    bounds_pdf_pts: tuple[float, float, float, float]
    source_word_indices: tuple[int, ...] = ()
    is_legend_exemplar: bool = True
    physical_opening_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "label_text": self.label_text,
            "arc_path_ids": list(self.arc_path_ids),
            "leaf_path_ids": list(self.leaf_path_ids),
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "source_word_indices": list(self.source_word_indices),
            "is_legend_exemplar": self.is_legend_exemplar,
            "physical_opening_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class ClassifiedDoorMark:
    """A door symbol on a floor-plan page, typed against legend variants."""

    kind: str                           # inherited from matched LegendDoorVariant
    classification_basis: str          # "legend_arc_match", "text_token", "arc_only",
                                        # "abstained_ambiguous"
    arc_path_id: int | None
    leaf_path_id: int | None
    bounds_pdf_pts: tuple[float, float, float, float]
    nearest_width_mm: int | None        # from adjacent width annotation, if present
    nearest_width_word_index: int | None
    hand: str                           # "LEFT", "RIGHT", "UNKNOWN"
    page_index: int
    cs_word_index: int | None = None    # for cavity sliders
    physical_opening_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "kind": self.kind,
            "classification_basis": self.classification_basis,
            "arc_path_id": self.arc_path_id,
            "leaf_path_id": self.leaf_path_id,
            "bounds_pdf_pts": list(self.bounds_pdf_pts),
            "nearest_width_mm": self.nearest_width_mm,
            "nearest_width_word_index": self.nearest_width_word_index,
            "hand": self.hand,
            "page_index": self.page_index,
            "cs_word_index": self.cs_word_index,
            "physical_opening_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass
class DoorLegendReadResult:
    """Full result for one page: legend variants + classified plan marks."""

    page_index: int
    legend_variants: list[LegendDoorVariant] = field(default_factory=list)
    classified_marks: list[ClassifiedDoorMark] = field(default_factory=list)
    abstained_arcs: int = 0
    legend_panel_found: bool = False
    physical_openings_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "page_index": self.page_index,
            "legend_panel_found": self.legend_panel_found,
            "legend_variant_count": len(self.legend_variants),
            "classified_mark_count": len(self.classified_marks),
            "abstained_arc_count": self.abstained_arcs,
            "legend_variants": [v.to_dict() for v in self.legend_variants],
            "classified_marks": [m.to_dict() for m in self.classified_marks],
            "physical_openings_authenticated": False,
            "measurement_authorized": False,
            "classification_is_not_physical_opening_authority": True,
        }


# ---------------------------------------------------------------------------
# Internal geometry helpers
# ---------------------------------------------------------------------------

def _rect_of(path: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    """Return (x0, y0, x1, y1) bounding box of a drawing path, or None."""
    r = path.get("rect")
    if r is None:
        return None
    try:
        q = tuple(float(v) for v in r)
    except (TypeError, ValueError, OverflowError):
        return None
    if len(q) != 4 or not all(math.isfinite(v) for v in q):
        return None
    # Normalise so x0 <= x1, y0 <= y1
    return (min(q[0], q[2]), min(q[1], q[3]), max(q[0], q[2]), max(q[1], q[3]))


def _center(bounds: tuple[float, float, float, float]) -> tuple[float, float]:
    return (bounds[0] + bounds[2]) / 2.0, (bounds[1] + bounds[3]) / 2.0


def _area(bounds: tuple[float, float, float, float]) -> float:
    return max(0.0, bounds[2] - bounds[0]) * max(0.0, bounds[3] - bounds[1])


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _radius_of(bounds: tuple[float, float, float, float]) -> float:
    """Approximate radius from bounding box (works for quarter-arc)."""
    w = bounds[2] - bounds[0]
    h = bounds[3] - bounds[1]
    return max(w, h)  # quarter arc bounding box has one dim ≈ radius


def _is_arc_shaped(path: Mapping[str, Any]) -> bool:
    """Heuristic: a quarter-arc path has a bounding box whose aspect ratio
    is near 1:1 and whose items include a Bézier 'c' or arc segment 'cu'."""
    items = path.get("items") or []
    has_curve = any(
        (isinstance(it, (list, tuple)) and len(it) >= 1 and str(it[0]).lower() in ("c", "cu"))
        for it in items
    )
    if not has_curve:
        return False
    r = _rect_of(path)
    if r is None:
        return False
    w, h = r[2] - r[0], r[3] - r[1]
    if w < _ARC_RADIUS_MIN_PTS or h < _ARC_RADIUS_MIN_PTS:
        return False
    if max(w, h) > _ARC_RADIUS_MAX_PTS:
        return False
    aspect = max(w, h) / max(min(w, h), 0.01)
    return aspect < 2.5  # near-square → quarter arc


def _is_leaf_stroke(path: Mapping[str, Any],
                    arc_bounds: tuple[float, float, float, float]) -> bool:
    """A straight radial leaf stroke starts near arc bounding-box corner."""
    items = path.get("items") or []
    # Must be a line ('l') or move+line ('m'+'l') only
    for it in items:
        if isinstance(it, (list, tuple)) and len(it) >= 1:
            op = str(it[0]).lower()
            if op not in ("m", "l", "re"):
                return False
    r = _rect_of(path)
    if r is None:
        return False
    # Leaf should touch or be near the arc bounding box
    cx, cy = _center(arc_bounds)
    lx, ly = _center(r)
    return _dist((cx, cy), (lx, ly)) < _ARC_RADIUS_MAX_PTS * 1.5


def _infer_hand(arc_bounds: tuple[float, float, float, float],
                leaf_bounds: tuple[float, float, float, float] | None) -> str:
    """Infer handing from which side the arc opens toward.

    PDF coordinate system: y increases downward. A door opens left or right
    based on which quadrant the arc occupies relative to its leaf start.
    Returns "LEFT", "RIGHT", or "UNKNOWN".
    """
    if leaf_bounds is None:
        return "UNKNOWN"
    # Arc pivot is approximated by the corner of the arc bounding box
    # closest to the leaf centre.
    ax0, ay0, ax1, ay1 = arc_bounds
    lx, ly = _center(leaf_bounds)
    corners = [(ax0, ay0), (ax1, ay0), (ax0, ay1), (ax1, ay1)]
    pivot = min(corners, key=lambda c: _dist(c, (lx, ly)))
    # If pivot is on the right side of arc box → swing is to the left
    if pivot[0] > (ax0 + ax1) / 2:
        return "LEFT"
    return "RIGHT"


# ---------------------------------------------------------------------------
# Word/text extraction helpers
# ---------------------------------------------------------------------------

def _parse_words(source_words: Sequence[Any]) -> list[tuple[tuple[float, float, float, float], str, int]]:
    """Return list of (bbox, uppercased_text, original_index)."""
    out: list[tuple[tuple[float, float, float, float], str, int]] = []
    for i, w in enumerate(source_words):
        try:
            if isinstance(w, Mapping):
                text = str(w.get("text") or "").strip().upper()
                bbox = w.get("bbox_pdf_pts") or w.get("bbox")
            else:
                text = str(w[4]).strip().upper()
                bbox = w[:4]
            coords = tuple(float(v) for v in bbox)
            if len(coords) != 4 or not all(math.isfinite(v) for v in coords):
                continue
            if coords[0] > coords[2] or coords[1] > coords[3]:
                continue
            out.append((coords, text, i))  # type: ignore[arg-type]
        except (IndexError, TypeError, ValueError, OverflowError):
            continue
    return out


def _words_near(
    cx: float, cy: float, words: list[tuple[tuple[float, float, float, float], str, int]],
    radius: float = _ASSOC_RADIUS_PTS,
) -> list[tuple[float, tuple[float, float, float, float], str, int]]:
    """Return words within ``radius`` PDF-points of (cx, cy), sorted by distance."""
    result = []
    for bbox, text, idx in words:
        wx, wy = _center(bbox)
        d = _dist((cx, cy), (wx, wy))
        if d <= radius:
            result.append((d, bbox, text, idx))
    result.sort(key=lambda x: x[0])
    return result


def _classify_text_token(text: str) -> str:
    """Return door kind from a single text token, or ''."""
    if _SLIDER_TOKENS.search(text):
        return "cavity_slider"
    if _BIFOLD_TOKENS.search(text):
        return "bifold"
    if _PIVOT_TOKENS.search(text):
        return "pivot"
    if _PUSHPULL_TOKENS.search(text):
        return "push_pull"
    if _SWING_TOKENS.search(text):
        return "hinged"
    return ""


# ---------------------------------------------------------------------------
# Legend panel detection
# ---------------------------------------------------------------------------

def _find_legend_region(
    words: list[tuple[tuple[float, float, float, float], str, int]],
    page_bounds: tuple[float, float, float, float],
) -> tuple[float, float, float, float] | None:
    """Return bounding box of legend panel if heading text is found.

    Legends are typically in the bottom-right quadrant or a side strip.
    """
    page_cx = (page_bounds[0] + page_bounds[2]) / 2
    page_cy = (page_bounds[1] + page_bounds[3]) / 2
    headings = [
        (bbox, text, idx) for bbox, text, idx in words
        if _LEGEND_HEADING.search(text)
    ]
    if not headings:
        return None
    # Take the heading most plausibly in the legend zone
    # (prefer bottom-right, i.e. x > page_cx or y > page_cy)
    scored = []
    for bbox, text, idx in headings:
        cx, cy = _center(bbox)
        score = (1 if cx > page_cx else 0) + (1 if cy > page_cy else 0)
        scored.append((score, bbox))
    scored.sort(key=lambda s: -s[0])
    h_bbox = scored[0][1]
    # Extend the legend region from heading downward / rightward
    # (generous: 200 pts in each direction from heading centre)
    hcx, hcy = _center(h_bbox)
    margin = 200.0
    return (
        max(page_bounds[0], hcx - margin),
        max(page_bounds[1], hcy - margin),
        min(page_bounds[2], hcx + margin),
        min(page_bounds[3], hcy + margin * 2),
    )


def _bbox_in_region(
    bbox: tuple[float, float, float, float],
    region: tuple[float, float, float, float],
) -> bool:
    cx, cy = _center(bbox)
    return (region[0] <= cx <= region[2]) and (region[1] <= cy <= region[3])


# ---------------------------------------------------------------------------
# Legend variant extraction
# ---------------------------------------------------------------------------

def _extract_legend_variants(
    drawings: Sequence[Mapping[str, Any]],
    words: list[tuple[tuple[float, float, float, float], str, int]],
    legend_region: tuple[float, float, float, float] | None,
) -> list[LegendDoorVariant]:
    """Extract door symbol variants from legend region of a page."""
    variants: list[LegendDoorVariant] = []
    # Collect arc-shaped paths in legend region
    arc_candidates: list[tuple[int, tuple[float, float, float, float]]] = []
    for i, path in enumerate(drawings):
        if not isinstance(path, Mapping):
            continue
        if not _is_arc_shaped(path):
            continue
        r = _rect_of(path)
        if r is None:
            continue
        if legend_region is not None and not _bbox_in_region(r, legend_region):
            continue
        arc_candidates.append((i, r))

    for arc_idx, arc_bounds in arc_candidates:
        arc_path = drawings[arc_idx]
        # Find leaf strokes near this arc
        leaf_ids: list[int] = []
        for j, path in enumerate(drawings):
            if j == arc_idx or not isinstance(path, Mapping):
                continue
            if _is_leaf_stroke(path, arc_bounds):
                lr = _rect_of(path)
                if lr is not None:
                    leaf_ids.append(j)

        # Find nearby text tokens to determine kind
        ax, ay = _center(arc_bounds)
        nearby = _words_near(ax, ay, words, radius=_ASSOC_RADIUS_PTS * 3)
        kind = "unknown"
        label_parts: list[str] = []
        word_indices: list[int] = []
        for _, bbox, text, widx in nearby:
            k = _classify_text_token(text)
            if k and kind == "unknown":
                kind = k
            label_parts.append(text)
            word_indices.append(widx)
        label_text = " ".join(label_parts[:6])

        # Even without a label, a quarter-arc in the legend zone
        # defaults to "hinged" (most common)
        if kind == "unknown" and not _SLIDER_TOKENS.search(label_text):
            kind = "hinged"

        variants.append(LegendDoorVariant(
            kind=kind,
            label_text=label_text,
            arc_path_ids=(arc_idx,),
            leaf_path_ids=tuple(leaf_ids),
            bounds_pdf_pts=arc_bounds,
            source_word_indices=tuple(word_indices),
        ))
    return variants


# ---------------------------------------------------------------------------
# Plan-page door classification (AG-01..AG-04)
# ---------------------------------------------------------------------------

def _classify_plan_doors(
    drawings: Sequence[Mapping[str, Any]],
    words: list[tuple[tuple[float, float, float, float], str, int]],
    legend_variants: list[LegendDoorVariant],
    legend_region: tuple[float, float, float, float] | None,
    page_index: int,
) -> tuple[list[ClassifiedDoorMark], int]:
    """Classify door symbols found outside the legend region.

    Returns (classified_marks, abstained_arc_count).
    """
    marks: list[ClassifiedDoorMark] = []
    abstained = 0

    # Build width-annotation index
    width_index: list[tuple[tuple[float, float, float, float], int, int]] = []
    for bbox, text, widx in words:
        if _WIDTH_MM.fullmatch(text):
            mm = int(text.replace(",", ""))
            if 600 <= mm <= 1400:
                width_index.append((bbox, mm, widx))

    # Build CS-callout index (cavity sliders text)
    cs_index: list[tuple[tuple[float, float, float, float], int]] = []
    for bbox, text, widx in words:
        if text in ("CS",):
            cs_index.append((bbox, widx))

    # AG-04: First handle cavity sliders (CS text + no quarter-arc)
    for cs_bbox, cs_widx in cs_index:
        if legend_region is not None and _bbox_in_region(cs_bbox, legend_region):
            continue
        cx, cy = _center(cs_bbox)
        # Find associated width
        near_w = _words_near(cx, cy, [
            (wb, str(mm), wi) for wb, mm, wi in width_index
        ], radius=_ASSOC_RADIUS_PTS)
        width_mm: int | None = None
        width_widx: int | None = None
        if near_w:
            # Unique closest
            if len(near_w) == 1 or near_w[1][0] - near_w[0][0] > 1.0:
                width_mm = int(near_w[0][2])
                width_widx = near_w[0][3]

        marks.append(ClassifiedDoorMark(
            kind="cavity_slider",
            classification_basis="text_token",
            arc_path_id=None,
            leaf_path_id=None,
            bounds_pdf_pts=cs_bbox,
            nearest_width_mm=width_mm,
            nearest_width_word_index=width_widx,
            hand="UNKNOWN",
            page_index=page_index,
            cs_word_index=cs_widx,
        ))

    # AG-01..AG-03: Handle arc-shaped swing symbols (hinged, bifold, pivot)
    seen_arc_ids: set[int] = set()
    for i, path in enumerate(drawings):
        if not isinstance(path, Mapping):
            continue
        if not _is_arc_shaped(path):
            continue
        r = _rect_of(path)
        if r is None:
            continue
        # Skip legend region
        if legend_region is not None and _bbox_in_region(r, legend_region):
            continue
        if i in seen_arc_ids:
            continue
        seen_arc_ids.add(i)

        # Find leaf
        leaf_id: int | None = None
        leaf_bounds: tuple[float, float, float, float] | None = None
        for j, lp in enumerate(drawings):
            if j == i or not isinstance(lp, Mapping):
                continue
            if legend_region is not None and (lr := _rect_of(lp)) is not None:
                if _bbox_in_region(lr, legend_region):
                    continue
            if _is_leaf_stroke(lp, r):
                lr = _rect_of(lp)
                if lr is not None:
                    leaf_id = j
                    leaf_bounds = lr
                    break

        # Classify kind from text near arc
        ax, ay = _center(r)
        nearby_text = _words_near(ax, ay, words, radius=_ASSOC_RADIUS_PTS * 2)
        kind = ""
        for _, bbox, text, _ in nearby_text:
            k = _classify_text_token(text)
            if k:
                kind = k
                break

        # Match against legend variants if no text match
        if not kind and legend_variants:
            # Closest legend variant by radius similarity
            arc_r = _radius_of(r)
            best_diff = float("inf")
            best_kind = ""
            for lv in legend_variants:
                lv_r = _radius_of(lv.bounds_pdf_pts)
                diff = abs(arc_r - lv_r)
                if diff < best_diff:
                    best_diff = diff
                    best_kind = lv.kind
            # Only use match if radius within 20% of legend exemplar
            if best_diff <= arc_r * 0.20:
                kind = best_kind

        # AG-09: abstain if still ambiguous
        if not kind:
            # Check for explicit abstain markers nearby
            if any(_ABSTAIN_TOKENS.search(t) for _, _, t, _ in nearby_text):
                abstained += 1
                continue
            # Default unambiguous arc to hinged (most common)
            kind = "hinged"
            basis = "arc_only"
        else:
            basis = "legend_arc_match" if not nearby_text else "text_token"

        # Width annotation
        near_w = _words_near(ax, ay, [
            (wb, str(mm), wi) for wb, mm, wi in width_index
        ], radius=_ASSOC_RADIUS_PTS * 1.5)
        width_mm = None
        width_widx = None
        if near_w:
            if len(near_w) == 1 or near_w[1][0] - near_w[0][0] > 1.0:
                width_mm = int(near_w[0][2])
                width_widx = near_w[0][3]

        hand = _infer_hand(r, leaf_bounds)

        marks.append(ClassifiedDoorMark(
            kind=kind,
            classification_basis=basis,
            arc_path_id=i,
            leaf_path_id=leaf_id,
            bounds_pdf_pts=r,
            nearest_width_mm=width_mm,
            nearest_width_word_index=width_widx,
            hand=hand,
            page_index=page_index,
        ))

    return marks, abstained


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def run_door_legend_read_stage(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_words: Sequence[Any] = (),
    page_bounds_pdf_pts: tuple[float, float, float, float] = (0.0, 0.0, 841.0, 595.0),
    page_index: int = -1,
) -> dict[str, object]:
    """Read door symbols and legend variants for one PDF page.

    Parameters
    ----------
    drawings:
        Page drawing paths from ``fitz.Page.get_drawings()``.
    source_words:
        Page words from ``fitz.Page.get_text("words")``.
    page_bounds_pdf_pts:
        (x0, y0, x1, y1) of the page rectangle in PDF points.
    page_index:
        0-based page index (for traceability).

    Returns
    -------
    dict
        Serialisable ``DoorLegendReadResult.to_dict()`` output.
        Always sets ``measurement_authorized: False``.
    """
    result = DoorLegendReadResult(page_index=page_index)
    try:
        typed_drawings: list[Mapping[str, Any]] = [
            d for d in drawings if isinstance(d, Mapping)
        ]
        words = _parse_words(source_words)

        legend_region = _find_legend_region(words, page_bounds_pdf_pts)
        result.legend_panel_found = legend_region is not None

        result.legend_variants = _extract_legend_variants(
            typed_drawings, words, legend_region
        )
        classified, abstained = _classify_plan_doors(
            typed_drawings, words, result.legend_variants, legend_region, page_index
        )
        result.classified_marks = classified
        result.abstained_arcs = abstained

    except Exception:
        # Fail closed: return empty result, never crash the extractor
        pass

    return result.to_dict()
