"""PlanReader v1.7.1 — Door/window schedule table parsing.

Parses tab-separated rows (from _word_rows() or equivalent) to extract
schedule entries: type mark, width, height, description, count.

Safety rules:
  - Schedule rows describe opening TYPES, not physical wall instances.
  - A schedule entry MUST NOT create a new OpeningEvidence record by
    itself — it can only enrich an existing geometric instance.
  - Enrichment requires a matching non-empty type_mark on both the
    schedule entry and the existing evidence.
  - Width + height + basis + dimension_confidence + dimension_source
    are one atomic bundle (inherited from B0 safety contract).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_opening_evidence_v170 import (
    DIMENSION_BASIS_UNKNOWN,
    DIMENSION_BASIS_ROUGH_OPENING,
    DEDUCTION_REVIEW,
    NON_INSTANCE_SOURCES,
    OpeningEvidence,
    enriches_by_type,
    merge_opening_evidence,
)

VERSION = "1.7.1"

# ---------------------------------------------------------------------------
# Schedule entry — one row from a door/window schedule table
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScheduleEntry:
    """One row from a door/window schedule table.

    Represents an opening TYPE (D01, W01), not a physical instance.
    The same type mark can appear many times on the plan.
    """
    type_mark: str              # "D01", "W01"
    width_mm: Optional[int] = None
    height_mm: Optional[int] = None
    description: str = ""
    count: int = 1
    # True only when a schedule count/quantity cell was explicitly present
    # and parsed.  The historical default count=1 is retained for backwards
    # compatibility but must never be treated as independent commercial
    # quantity evidence when this flag is False.
    count_explicit: bool = False
    page_no: int = 0
    bbox: Tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    parse_source: str = ""      # "header_dims", "header_separate", "heuristic"
    dimension_basis: str = ""    # "rough_opening", "frame", "leaf", "clear_opening", ""
    basis_source: str = ""       # provenance for dimension_basis (heading text)


# ---------------------------------------------------------------------------
# Internal constants
# ---------------------------------------------------------------------------
_HEADER_MARK_KEYWORDS = frozenset({
    "mark", "marks", "type", "code", "no", "num", "number",
    "door", "window", "tag", "ref", "label", "item",
    "d#", "w#",  # LAGO schedule column headers
})

_HEADER_WIDTH_KEYWORDS = frozenset({
    "width", "wide", "wdth",
})

_HEADER_HEIGHT_KEYWORDS = frozenset({
    "height", "ht", "hgt", "high",
})

_HEADER_DIMS_KEYWORDS = frozenset({
    "size", "dims", "dim", "dimensions", "w×h", "w*x", "w x h",
    "width×height", "width*height", "width x height",
    "w/h", "w×h", "wxh",
})

_HEADER_COUNT_KEYWORDS = frozenset({
    "qty", "quantity", "count", "nos", "no.", "number",
})

_HEADER_DESC_KEYWORDS = frozenset({
    "description", "desc", "notes", "note", "detail", "remarks",
    "type_desc", "material", "finish", "spec",
})

# ---------------------------------------------------------------------------
# Dimension basis inference from schedule heading text
# ---------------------------------------------------------------------------
# Only explicit heading labels can establish basis.  Generic "Width/Height"
# must remain unknown — knowing dimensions is not the same as knowing
# they represent the wall void.

_RO_HEADING_KEYWORDS = re.compile(
    r"\b(rough\s*opening|ro\s*size|ro\s*wdth|ro\s*ht|structural\s*opening"
    r"|rough\s*opening\s*(width|height|wdth|ht|hgt)"
    r"|r\.?o\.?\s*(width|height|wdth|ht|hgt))\b",
    re.IGNORECASE,
)
_FRAME_HEADING_KEYWORDS = re.compile(
    r"\b(frame\s*(size|width|height|wdth|ht|hgt)|fr\s*size)\b",
    re.IGNORECASE,
)
_LEAF_HEADING_KEYWORDS = re.compile(
    r"\b(leaf\s*(size|width|height|wdth|ht|hgt))\b",
    re.IGNORECASE,
)
_CLEAR_HEADING_KEYWORDS = re.compile(
    r"\b(clear\s*(opening|size|width|height|wdth|ht|hgt))\b",
    re.IGNORECASE,
)


def _infer_column_basis(heading_text: str) -> Tuple[str, str]:
    """Infer dimension basis from a single column heading.

    Returns (dimension_basis, basis_source) where:
      - dimension_basis is "rough_opening", "frame", "leaf",
        "clear_opening", or "" (unknown).
      - basis_source is the matched heading text for provenance.

    Only explicit heading labels establish basis.  Generic headings like
    "Width", "Height", "Size" return ("", "") because the parser cannot
    determine what physical measurement those dimensions represent.
    """
    text = heading_text.lower().strip()
    if _RO_HEADING_KEYWORDS.search(text):
        m = _RO_HEADING_KEYWORDS.search(text)
        return "rough_opening", m.group(0) if m else text
    if _FRAME_HEADING_KEYWORDS.search(text):
        m = _FRAME_HEADING_KEYWORDS.search(text)
        return "frame", m.group(0) if m else text
    if _LEAF_HEADING_KEYWORDS.search(text):
        m = _LEAF_HEADING_KEYWORDS.search(text)
        return "leaf", m.group(0) if m else text
    if _CLEAR_HEADING_KEYWORDS.search(text):
        m = _CLEAR_HEADING_KEYWORDS.search(text)
        return "clear_opening", m.group(0) if m else text
    return "", ""


def _resolve_dimension_basis(
    width_basis: str, width_source: str,
    height_basis: str, height_source: str,
    dims_basis: str, dims_source: str,
) -> Tuple[str, str]:
    """Resolve the final dimension basis from individual column bases.

    Rules:
      - A combined Size/dims column with explicit basis → use that basis.
        (Both values originate from one explicitly based field.)
      - Both width and height present AND agree on basis → use it.
      - Any other case (one missing, one generic, disagree) → unknown.
        Generic "Width" does not become a rough-opening width merely
        because the height column says "Rough Opening Height".

    The atomic measurement-bundle contract requires ALL dimensions in
    the bundle to share the same explicit basis.
    """
    if dims_basis:
        return dims_basis, dims_source
    if width_basis and height_basis:
        if width_basis == height_basis:
            return width_basis, width_source
        return "", ""
    return "", ""

# Structural opening-mark validation.  Roman numerals are deliberately
# excluded: accepting an "I" prefix must never make I/II/III look like doors.
_OPENING_MARK_RE = re.compile(
    r"^(?:[EI]?[DW]|WD|DW)\d{1,4}$",
    re.IGNORECASE,
)
_MARK_SEARCH_RE = re.compile(
    r"\b((?:[EI]?[DW]|WD|DW)\d{1,4})\b",
    re.IGNORECASE,
)


def _is_opening_mark(mark: str) -> bool:
    return bool(mark and _OPENING_MARK_RE.fullmatch(mark.strip()))


# Patterns for compound dimension extraction (from full row text)
_DIMENSION_PATTERNS_X = [
    re.compile(r"(\d{1,5})\s*[×xX]\s*(\d{1,5})"),
    re.compile(r"(\d{1,5})\s*[-–—]\s*(\d{1,5})"),
    re.compile(r"(\d{1,5})\s*[bhBH]\s*(\d{1,5})"),
]
_DIMENSION_PATTERNS_SLASH = [
    re.compile(r"(\d{1,5})\s*/\s*(\d{1,5})"),
]

_SINGLE_NUM_RE = re.compile(r"\b(\d{2,5})\b")
_MM_RE = re.compile(r"(\d{2,5})\s*mm", re.IGNORECASE)
_M_RE = re.compile(r"(\d{1,3}(?:\.\d{1,3})?)\s*m\b", re.IGNORECASE)

_RATING_KEYWORDS = re.compile(
    r"\b(frl|fire|rating|acoustic|stc|rw|db|hr|sound|insul)\b",
    re.IGNORECASE,
)

# Non-authoritative deferral / manufacturer-exclusion wording inside a
# schedule dimension cell. In strict two-level schedule mode, a dimension
# cell containing any of these phrases must abstain (None) even if a stray
# reference number appears in the same cell.
_SCHEDULE_DIM_EXCLUSION_RE = re.compile(
    r"(?:\bas\s+per\s+(?:manufacturer|mfr\.?|supplier|contractor|shop|spec\w*)\b"
    r"|\bby\s+(?:others|manufacturer|mfr\.?|contractor|tenant|lessee|owner|builder|client|specialist)\b"
    r"|\b(?:verify|measure|confirm|check)\s+on\s+site\b|\bsite\s+measure\b"
    r"|\bnot\s+in\s+contract\b"
    r"|\b(?:n\.?\s*/\s*a|t\.?b\.?c\.?|t\.?b\.?a\.?|n\.?i\.?c\.?|varies|refer|existing|approx\.?|nominal|nom\.?)\b"
    r"|\bsee\s+)",
    re.IGNORECASE,
)

_STRICT_SINGLE_DIM_CELL_RE = re.compile(
    r"^\s*(?:(\d{1,5}(?:,\d{3})?)\s*(?:mm)?|(\d{1,3}(?:\.\d{1,3})?)\s*m)\s*$",
    re.IGNORECASE,
)

_STRICT_COMBINED_DIM_CELL_RE = re.compile(
    r"^\s*(?:(\d{1,5}(?:,\d{3})?)\s*(?:mm)?|(\d{1,3}(?:\.\d{1,3})?)\s*m)"
    r"\s*[×xX/\-–—]\s*"
    r"(?:(\d{1,5}(?:,\d{3})?)\s*(?:mm)?|(\d{1,3}(?:\.\d{1,3})?)\s*m)\s*$",
    re.IGNORECASE,
)

_MARK_PARTS_RE = re.compile(r"^([EI]?[DW]|WD|DW)(\d{1,4})$", re.IGNORECASE)
_MARK_RANGE_SPLIT_RE = re.compile(r"\s*(?:[-–—]|\bto\b)\s*", re.IGNORECASE)
_MARK_LIST_SPLIT_RE = re.compile(r"\s*(?:[,/&+\n]|\band\b)\s*", re.IGNORECASE)
_MAX_GROUPED_MARK_RANGE = 50

_STRICT_MARK_COL_RE = re.compile(
    r"^(?:door|window|opening)(?:\s*[/&]\s*(?:door|window))?\s+(?:no\.?|number|mark|code|type|ref|id)$",
    re.IGNORECASE,
)
_STRICT_MARK_CHILD_TOKENS = frozenset({
    "no", "no.", "number", "mark", "code", "type", "ref", "id",
})
_STRICT_WIDTH_CHILD_RE = re.compile(
    r"^(?:width|wide|wdth)(?:\s*(?:\(\s*mm?\s*\)|\[\s*mm?\s*\]|mm?))?$",
    re.IGNORECASE,
)
_STRICT_HEIGHT_CHILD_RE = re.compile(
    r"^(?:height|ht|hgt)(?:\s*(?:\(\s*mm?\s*\)|\[\s*mm?\s*\]|mm?))?$",
    re.IGNORECASE,
)
_STRICT_UNIT_ONLY_RE = re.compile(
    r"^(?:\(\s*mm?\s*\)|\[\s*mm?\s*\]|mm?)$",
    re.IGNORECASE,
)
_STRICT_GROUP_PARENT_RE = re.compile(
    r"^(door\s+leaf|window\s+leaf|door\s+frame|window\s+frame|"
    r"rough\s+opening|structural\s+opening|clear\s+opening)"
    r"(?:\s+(?:size|dims?|dimensions?))?"
    r"(?:\s*(?:\(\s*mm?\s*\)|\[\s*mm?\s*\]|mm?))?$",
    re.IGNORECASE,
)
_STRICT_GROUP_BASIS_BY_PHRASE = {
    "door leaf": "leaf",
    "window leaf": "leaf",
    "door frame": "frame",
    "window frame": "frame",
    "rough opening": "rough_opening",
    "structural opening": "rough_opening",
    "clear opening": "clear_opening",
}


def _normalize_cell_label(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _strict_group_parent_basis(label: str) -> str:
    clean = _normalize_cell_label(label)
    if not clean:
        return ""
    match = _STRICT_GROUP_PARENT_RE.fullmatch(clean)
    if not match:
        return ""
    phrase = " ".join(match.group(1).lower().split())
    return _STRICT_GROUP_BASIS_BY_PHRASE.get(phrase, "")


def _is_strict_mark_column_label(parent_label: str, child_label: str = "") -> bool:
    p = _normalize_cell_label(parent_label)
    c = _normalize_cell_label(child_label)
    if p and _STRICT_MARK_COL_RE.fullmatch(p):
        return True
    if not p and c and _STRICT_MARK_COL_RE.fullmatch(c):
        return True
    if p in ("door", "window") and c in _STRICT_MARK_CHILD_TOKENS:
        return True
    return False


def _is_strict_width_child_label(label: str) -> bool:
    return bool(_STRICT_WIDTH_CHILD_RE.fullmatch(_normalize_cell_label(label)))


def _is_strict_height_child_label(label: str) -> bool:
    return bool(_STRICT_HEIGHT_CHILD_RE.fullmatch(_normalize_cell_label(label)))


def _is_strict_unit_only_label(label: str) -> bool:
    return bool(_STRICT_UNIT_ONLY_RE.fullmatch(_normalize_cell_label(label)))


def _canonical_opening_mark_key(mark: str) -> Optional[Tuple[str, int]]:
    """Canonical (prefix, integer_number) identity so D1 and D01 cannot silently compete."""
    match = _MARK_PARTS_RE.fullmatch(mark.strip())
    if not match:
        return None
    return (match.group(1).upper(), int(match.group(2)))


def _parse_strict_schedule_dimension_cell(text: str) -> Optional[int]:
    """Parse one explicit dimension cell for strict opt-in schedule parsing.

    Rejects manufacturer/contractor exclusions, deferral wording, and prose
    containing embedded numbers. Returns None on blank or non-authoritative
    cells rather than guessing or applying generic frame/leaf adjustments.
    """
    if not text or not text.strip():
        return None
    t = text.strip()
    if _SCHEDULE_DIM_EXCLUSION_RE.search(t):
        return None
    match = _STRICT_SINGLE_DIM_CELL_RE.fullmatch(t)
    if not match:
        return None
    return parse_single_dimension(t)


def _parse_strict_schedule_dims_cell(text: str) -> Tuple[Optional[int], Optional[int]]:
    """Parse one strictly formatted combined WxH dimension cell (no prose rescue)."""
    if not text or not text.strip():
        return None, None
    t = text.strip()
    if _SCHEDULE_DIM_EXCLUSION_RE.search(t) or _has_rating_keywords(t):
        return None, None
    match = _STRICT_COMBINED_DIM_CELL_RE.fullmatch(t)
    if not match:
        return None, None
    w_mm_raw, w_m_raw, h_mm_raw, h_m_raw = match.groups()
    try:
        w = int(w_mm_raw.replace(",", "")) if w_mm_raw is not None else round(float(w_m_raw) * 1000)
        h = int(h_mm_raw.replace(",", "")) if h_mm_raw is not None else round(float(h_m_raw) * 1000)
    except (ValueError, TypeError):
        return None, None
    if not _is_plausible_dimension(w, h):
        return None, None
    return w, h


def _parse_strict_schedule_marks(raw: str) -> Optional[Tuple[str, ...]]:
    """Parse one strict schedule mark cell into single or grouped opening marks.

    Returns:
      - None when the cell is empty or plain non-mark text (row skipped);
      - () when the cell attempts a grouped/range mark expression that is
        malformed, reversed, mixed-prefix, mixed-padding, oversized, or
        canonically self-duplicating (caller must fail closed on the schedule);
      - Tuple[str, ...] of uppercase opening marks in printed order otherwise.
    """
    raw_str = str(raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not raw_str:
        return None
    # Collapse line breaks inside wrapped ranges (e.g. "D01 -\nD03") or next to
    # list separators (e.g. "D01,\nD02"), while preserving bare newline-separated
    # multi-line mark cells (e.g. "D01\nD02").
    lines = [" ".join(line.split()) for line in raw_str.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return None
    text = "\n".join(lines)
    text = re.sub(r"([-–—]|\bto\b)\s*\n\s*", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\n\s*([-–—]|\bto\b)", r" \1", text, flags=re.IGNORECASE)
    text = re.sub(r"([,/&+]|\band\b)\s*\n\s*", r"\1 ", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*\n\s*([,/&+]|\band\b)", r" \1", text, flags=re.IGNORECASE)
    if not text:
        return None
    if _is_opening_mark(text):
        return (text.upper(),)
    if not _MARK_SEARCH_RE.search(text):
        return None
    chunks = [chunk.strip() for chunk in _MARK_LIST_SPLIT_RE.split(text)]
    if any(not chunk for chunk in chunks):
        non_empty = [c for c in chunks if c]
        if non_empty and any(_MARK_SEARCH_RE.search(c) for c in non_empty):
            return ()
        return None
    expanded: List[str] = []
    seen_canonical: set[Tuple[str, int]] = set()
    saw_group_syntax = len(chunks) > 1
    for chunk in chunks:
        if _is_opening_mark(chunk):
            mark = chunk.upper()
            key = _canonical_opening_mark_key(mark)
            if key is None or key in seen_canonical:
                return ()
            seen_canonical.add(key)
            expanded.append(mark)
            continue
        range_parts = _MARK_RANGE_SPLIT_RE.split(chunk)
        if len(range_parts) >= 2:
            # Any hyphen/dash/to expression containing an opening mark is an
            # attempted range and MUST fail closed if malformed (e.g. D01-X03,
            # D01-99, D1-D03, D06-D04, D01-D02-D03).
            if len(range_parts) != 2 or not all(_is_opening_mark(p) for p in range_parts):
                if any(_is_opening_mark(p) or _MARK_SEARCH_RE.search(p) for p in range_parts):
                    return ()
                if saw_group_syntax:
                    return ()
                return None
            saw_group_syntax = True
            start_m = _MARK_PARTS_RE.fullmatch(range_parts[0].strip())
            end_m = _MARK_PARTS_RE.fullmatch(range_parts[1].strip())
            if not start_m or not end_m:
                return ()
            p_start, n_start_raw = start_m.group(1).upper(), start_m.group(2)
            p_end, n_end_raw = end_m.group(1).upper(), end_m.group(2)
            if p_start != p_end:
                return ()
            n_start, n_end = int(n_start_raw), int(n_end_raw)
            if n_end <= n_start or (n_end - n_start) > _MAX_GROUPED_MARK_RANGE:
                return ()
            # Reject both forward and reverse mixed zero-padding (e.g. D04-D006, D01-D3, D1-D03).
            if (n_start_raw.startswith("0") or n_end_raw.startswith("0")) and len(n_start_raw) != len(n_end_raw):
                return ()
            pad_width = len(n_start_raw) if n_start_raw.startswith("0") else 0
            for num in range(n_start, n_end + 1):
                token = f"{p_start}{num:0{pad_width}d}" if pad_width else f"{p_start}{num}"
                key = (p_start, num)
                if key in seen_canonical:
                    return ()
                seen_canonical.add(key)
                expanded.append(token)
            continue
        if saw_group_syntax:
            return ()
        return None
    return tuple(expanded) if expanded else None

_MIN_PLAUSIBLE_MM = 200
_MAX_PLAUSIBLE_MM = 6000


def _is_plausible_dimension(w: Optional[int], h: Optional[int]) -> bool:
    if w is None and h is None:
        return False
    if w is not None and (w < _MIN_PLAUSIBLE_MM or w > _MAX_PLAUSIBLE_MM):
        return False
    if h is not None and (h < _MIN_PLAUSIBLE_MM or h > _MAX_PLAUSIBLE_MM):
        return False
    return True


def _has_rating_keywords(text: str) -> bool:
    return bool(_RATING_KEYWORDS.search(text))


def parse_single_dimension(text: str) -> Optional[int]:
    """Return one plausible length. Two different lengths abstain."""
    if not text or not text.strip():
        return None
    t = text.strip()
    values: List[int] = []
    for match in _MM_RE.finditer(t):
        values.append(int(match.group(1)))
    if not values:
        for match in _M_RE.finditer(t):
            values.append(round(float(match.group(1)) * 1000))
    if not values:
        try:
            values.append(int(float(t.replace(",", "").strip())))
        except (ValueError, TypeError):
            return None
    plausible: List[int] = []
    for value in values:
        if _is_plausible_dimension(value, None) and value not in plausible:
            plausible.append(value)
    if len(plausible) == 1:
        return plausible[0]
    return None


def _plausible_pairs(patterns: Sequence[re.Pattern[str]], text: str) -> List[Tuple[int, int]]:
    found: List[Tuple[int, int]] = []
    for pattern in patterns:
        for match in pattern.finditer(text):
            pair = (int(match.group(1)), int(match.group(2)))
            if _is_plausible_dimension(*pair) and pair not in found:
                found.append(pair)
    return found


def parse_dimension(text: str, allow_slash: bool = True) -> Tuple[Optional[int], Optional[int]]:
    """Return one width and height.

    Two different explicit pairs abstain. A fire-rating slash does not replace
    one ``x`` pair. More than two loose lengths abstain instead of keeping the
    first two.
    """
    if not text or not text.strip():
        return None, None
    t = text.strip()
    pairs = _plausible_pairs(_DIMENSION_PATTERNS_X, t)
    if len(pairs) > 1:
        return None, None
    if len(pairs) == 1:
        return pairs[0]
    if allow_slash:
        pairs = _plausible_pairs(_DIMENSION_PATTERNS_SLASH, t)
        if len(pairs) > 1:
            return None, None
        if len(pairs) == 1:
            return pairs[0]

    def _loose(raw_values: List[int]) -> Tuple[Optional[int], Optional[int], bool]:
        if len(raw_values) > 2:
            return None, None, True
        if len(raw_values) == 2 and _is_plausible_dimension(*raw_values):
            return raw_values[0], raw_values[1], True
        if len(raw_values) == 1:
            return raw_values[0], None, True
        return None, None, False

    mm_values: List[int] = []
    for raw in _MM_RE.findall(t):
        value = int(raw)
        if _MIN_PLAUSIBLE_MM <= value <= _MAX_PLAUSIBLE_MM and value not in mm_values:
            mm_values.append(value)
    width, height, handled = _loose(mm_values)
    if handled:
        return width, height
    metre_values: List[int] = []
    for raw in _M_RE.findall(t):
        value = round(float(raw) * 1000)
        if _MIN_PLAUSIBLE_MM <= value <= _MAX_PLAUSIBLE_MM and value not in metre_values:
            metre_values.append(value)
    width, height, handled = _loose(metre_values)
    if handled:
        return width, height
    raw_numbers: List[int] = []
    distinct_numbers: List[int] = []
    for raw in _SINGLE_NUM_RE.findall(t):
        value = int(raw)
        if _MIN_PLAUSIBLE_MM <= value <= _MAX_PLAUSIBLE_MM:
            raw_numbers.append(value)
            if value not in distinct_numbers:
                distinct_numbers.append(value)
    if len(distinct_numbers) > 2:
        return None, None
    if len(raw_numbers) >= 2:
        if (allow_slash or "/" not in t) and _is_plausible_dimension(raw_numbers[0], raw_numbers[1]):
            return raw_numbers[0], raw_numbers[1]
        return None, None
    if len(raw_numbers) == 1:
        return raw_numbers[0], None
    return None, None


def extract_mark(text: str) -> str:
    """Extract one door/window mark. Two different marks abstain."""
    if not text:
        return ""
    marks = {
        match.group(1).upper()
        for match in _MARK_SEARCH_RE.finditer(str(text).upper())
        if _is_opening_mark(match.group(1).upper())
    }
    if len(marks) != 1:
        return ""
    return next(iter(marks))


def detect_header(words: Sequence[str]) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {}
    hits: Dict[str, List[Tuple[int, str, str]]] = {
        "mark": [],
        "dims": [],
        "width": [],
        "height": [],
        "count": [],
        "desc": [],
    }

    for i, w in enumerate(words):
        w_clean = w.strip().lower()
        if not w_clean:
            continue
        col_basis, col_source = _infer_column_basis(w)
        # In the explicit DOOR / TYPE and WINDOW / TYPE schema, TYPE is
        # the filling description (e.g. HINGED), beside the opening mark.
        # It is not a second competing mark column. Other repeated mark
        # headings remain ambiguous and are retained below.
        if (w_clean == "type" and i > 0
                and words[i - 1].strip().lower() in {"door", "window"}):
            hits["desc"].append((i, "", ""))
            continue
        if w_clean in _HEADER_MARK_KEYWORDS:
            hits["mark"].append((i, "", ""))
            continue
        if (
            w_clean in _HEADER_DIMS_KEYWORDS
            or any(kw in w_clean for kw in _HEADER_DIMS_KEYWORDS)
        ):
            hits["dims"].append((i, col_basis, col_source))
            continue
        if (
            w_clean in _HEADER_WIDTH_KEYWORDS
            or any(kw in w_clean for kw in _HEADER_WIDTH_KEYWORDS)
        ):
            hits["width"].append((i, col_basis, col_source))
            continue
        if (
            "sill" not in w_clean
            and (
                w_clean in _HEADER_HEIGHT_KEYWORDS
                or any(kw in w_clean for kw in _HEADER_HEIGHT_KEYWORDS)
            )
        ):
            hits["height"].append((i, col_basis, col_source))
            continue
        if w_clean in _HEADER_COUNT_KEYWORDS:
            hits["count"].append((i, "", ""))
            continue
        if w_clean in _HEADER_DESC_KEYWORDS:
            hits["desc"].append((i, "", ""))
            continue

    width_basis = ""
    width_basis_source = ""
    height_basis = ""
    height_basis_source = ""
    dims_basis = ""
    dims_basis_source = ""
    for role, columns in hits.items():
        if len(columns) != 1:
            continue
        index, basis, source = columns[0]
        mapping[role] = index
        if role == "width":
            width_basis, width_basis_source = basis, source
        elif role == "height":
            height_basis, height_basis_source = basis, source
        elif role == "dims":
            dims_basis, dims_basis_source = basis, source

    basis, basis_source = _resolve_dimension_basis(
        width_basis, width_basis_source,
        height_basis, height_basis_source,
        dims_basis, dims_basis_source,
    )
    mapping["dimension_basis"] = basis
    mapping["basis_source"] = basis_source
    return mapping


def _is_header_row(words: Sequence[str]) -> bool:
    mapping = detect_header(words)
    return "mark" in mapping or "dims" in mapping


def _explicit_two_level_schedule_header(cells: Sequence[str]) -> Dict[str, Any]:
    """Default-off schedule header candidate: require a complete typed schema.

    A notes heading such as DOOR | NOTES must never become the table header.
    Composite labels (DOOR NO / WINDOW MARK) describe a mark *column*, not
    an independently proven instance. Dimension basis rules remain unchanged.
    """
    normalised: List[str] = []
    for cell in cells:
        label = " ".join(str(cell or "").strip().split())
        if _STRICT_MARK_COL_RE.fullmatch(label):
            label = "Mark"
        normalised.append(label)
    mapping = detect_header(normalised)
    if "mark" not in mapping:
        return {}
    separate = "width" in mapping and "height" in mapping
    combined = "dims" in mapping
    # Both column layouts simultaneously would require a second dimension
    # basis/ownership decision and cannot be selected by header precedence.
    if separate == combined:
        return {}
    return mapping


def _explicit_nested_schedule_header(
    parent_cells: Sequence[str], child_cells: Sequence[str],
) -> Dict[str, Any]:
    """Combine two *column-aligned*, explicitly labelled dimension headings.

    This opt-in B2 reader never guesses which child belongs to a spanning
    group. An unaligned header or ambiguous leaf/frame ownership abstains.
    Source word identity, metric unit and physical opening still require
    their independent authorities.
    """
    if len(parent_cells) != len(child_cells) or len(parent_cells) < 3:
        return {}
    expanded: List[str] = []
    dimension_groups: Dict[str, List[Tuple[int, str]]] = {
        "width": [], "height": [],
    }
    for i, (parent, child) in enumerate(zip(parent_cells, child_cells)):
        p = _normalize_cell_label(parent)
        c = _normalize_cell_label(child)
        basis = _strict_group_parent_basis(p)
        if basis and _is_strict_width_child_label(c):
            dimension_groups["width"].append((i, basis))
            expanded.append(f"{basis.replace('_', ' ')} width")
        elif basis and _is_strict_height_child_label(c):
            dimension_groups["height"].append((i, basis))
            expanded.append(f"{basis.replace('_', ' ')} height")
        elif basis and c:
            # A child cell under a dimension group that explicitly names a
            # conflicting basis (e.g. "frame width" under "door leaf") must
            # abstain rather than silently dropping the conflict.
            child_basis, _ = _infer_column_basis(c)
            if child_basis and child_basis != basis:
                return {}
            expanded.append(parent.strip() or child.strip())
        elif _is_strict_mark_column_label(p, c):
            expanded.append("Mark")
        else:
            # Never borrow a dimension from an unrelated parent group.
            expanded.append(" ".join(str(parent or "").strip().split())
                            or " ".join(str(child or "").strip().split()))

    widths, heights = dimension_groups["width"], dimension_groups["height"]
    if len(widths) != 1 or len(heights) != 1:
        return {}
    if widths[0][1] != heights[0][1]:
        return {}
    mapping = _explicit_two_level_schedule_header(expanded)
    if (
        mapping.get("width") != widths[0][0]
        or mapping.get("height") != heights[0][0]
        or mapping.get("dimension_basis") != widths[0][1]
    ):
        return {}
    return mapping


def _extract_row_word_phrases(
    row: Mapping[str, Any],
) -> Optional[List[Tuple[float, float, str]]]:
    """Group one row's word boxes into horizontal cell phrases without crossing gaps.

    Returns None when the row carries no usable word geometry (plain text row),
    or raises ValueError on corrupt/non-finite/inverted word boxes.
    """
    raw_words = row.get("words")
    if not isinstance(raw_words, (list, tuple)) or not raw_words:
        return None
    usable: List[Tuple[float, float, float, float, str]] = []
    heights: List[float] = []
    for word in raw_words:
        if not isinstance(word, (list, tuple)) or len(word) < 5:
            raise ValueError("malformed_row_word")
        try:
            x0, y0, x1, y1 = (float(word[0]), float(word[1]), float(word[2]), float(word[3]))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("non_numeric_row_word") from exc
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            raise ValueError("non_finite_row_word")
        if x1 < x0 or y1 < y0:
            raise ValueError("inverted_row_word_bbox")
        text = str(word[4]).strip()
        if not text:
            continue
        usable.append((x0, y0, x1, y1, text))
        heights.append(max(1.0, y1 - y0))
    if not usable:
        return []
    usable.sort(key=lambda item: (item[0], item[1]))
    heights.sort()
    typical_h = heights[len(heights) // 2]
    gap_threshold = max(18.0, typical_h * 2.6)
    phrases: List[Tuple[float, float, str]] = []
    cur_x0, cur_x1, cur_parts = usable[0][0], usable[0][2], [usable[0][4]]
    for x0, _y0, x1, _y1, text in usable[1:]:
        if x0 - cur_x1 > gap_threshold:
            phrases.append((cur_x0, cur_x1, " ".join(cur_parts)))
            cur_x0, cur_x1, cur_parts = x0, x1, [text]
        else:
            cur_x1 = max(cur_x1, x1)
            cur_parts.append(text)
    phrases.append((cur_x0, cur_x1, " ".join(cur_parts)))
    return phrases


def _align_two_header_rows_by_x(
    parent_phrases: Sequence[Tuple[float, float, str]],
    child_phrases: Sequence[Tuple[float, float, str]],
    unit_phrases: Sequence[Tuple[float, float, str]] = (),
) -> Optional[Tuple[List[Tuple[float, float]], List[str], List[str], bool]]:
    """Build strictly disjoint X-columns for a 2- or 3-row borderless header.

    Returns ``(col_intervals, parent_labels, child_labels, had_ambiguous_group)``.
    Returns ``None`` when the block is not a valid disjoint header.
    """
    if not parent_phrases or not child_phrases:
        return None
    child_cols: List[List[Any]] = [
        [cx0, cx1, "", ctext, False] for cx0, cx1, ctext in child_phrases
    ]
    standalone_cols: List[List[Any]] = []
    saw_group_parent = False
    saw_dim_child = any(
        _is_strict_width_child_label(ctext) or _is_strict_height_child_label(ctext)
        for _, _, ctext in child_phrases
    )

    for px0, px1, ptext in parent_phrases:
        basis = _strict_group_parent_basis(ptext)
        if basis:
            saw_group_parent = True
        touched = [
            j for j, col in enumerate(child_cols)
            if min(px1, col[1]) - max(px0, col[0]) > -1.0
        ]
        if len(touched) == 0:
            # Standalone parent header above a blank child cell (e.g. DOOR NO. or NOTES).
            standalone_cols.append([px0, px1, ptext, "", True])
        elif len(touched) == 1:
            col = child_cols[touched[0]]
            if col[4]:
                return ([], [], [], True)
            col[0] = min(col[0], px0)
            col[1] = max(col[1], px1)
            col[2] = ptext
            col[4] = True
        else:
            # Spanning parent phrase across multiple child columns: ONLY allowed
            # for an explicit typed dimension group over contiguous child columns
            # with no competing parent claim.
            if not basis:
                return ([], [], [], saw_group_parent and saw_dim_child)
            if touched != list(range(touched[0], touched[-1] + 1)):
                return ([], [], [], True)
            for j in touched:
                if child_cols[j][4]:
                    return ([], [], [], True)
                child_cols[j][2] = ptext
                child_cols[j][4] = True

    all_cols = sorted(child_cols + standalone_cols, key=lambda col: col[0])
    # Require strictly disjoint column X-intervals (zero cross-column overlap).
    for idx in range(len(all_cols) - 1):
        if all_cols[idx][1] >= all_cols[idx + 1][0] - 1.0:
            return ([], [], [], saw_group_parent and saw_dim_child)

    if unit_phrases:
        for ux0, ux1, utext in unit_phrases:
            if not _is_strict_unit_only_label(utext):
                return None
            hits = [
                j for j, col in enumerate(all_cols)
                if min(ux1, col[1]) - max(ux0, col[0]) > -1.0
            ]
            if len(hits) != 1:
                return ([], [], [], True)
            j = hits[0]
            all_cols[j][0] = min(all_cols[j][0], ux0)
            all_cols[j][1] = max(all_cols[j][1], ux1)
            all_cols[j][3] = f"{all_cols[j][3]} {utext}".strip()
        for idx in range(len(all_cols) - 1):
            if all_cols[idx][1] >= all_cols[idx + 1][0] - 1.0:
                return ([], [], [], True)

    intervals = [(float(col[0]), float(col[1])) for col in all_cols]
    parent_labels = [str(col[2]) for col in all_cols]
    child_labels = [str(col[3]) for col in all_cols]
    return (intervals, parent_labels, child_labels, False)


def _assign_phrases_to_columns(
    phrases: Sequence[Tuple[float, float, str]],
    col_intervals: Sequence[Tuple[float, float]],
) -> Optional[List[str]]:
    """Assign a row's phrases to proved disjoint columns without crossing ownership.

    Returns None when any phrase physically overlaps two column intervals or
    straddles the midpoint boundary between two adjacent columns.
    """
    n_cols = len(col_intervals)
    buckets: List[List[str]] = [[] for _ in range(n_cols)]
    midpoints = [
        (col_intervals[i][1] + col_intervals[i + 1][0]) / 2.0
        for i in range(n_cols - 1)
    ]
    for px0, px1, text in phrases:
        core_hits = [
            i for i, (cx0, cx1) in enumerate(col_intervals)
            if min(px1, cx1) - max(px0, cx0) > 0.0
        ]
        if len(core_hits) > 1:
            return None
        if len(core_hits) == 1:
            target = core_hits[0]
            # Stay strictly clear of neighboring columns' core X-intervals so
            # text can never bleed across column ownership boundaries.
            if target > 0 and px0 < col_intervals[target - 1][1] + 2.0:
                return None
            if target + 1 < n_cols and px1 > col_intervals[target + 1][0] - 2.0:
                return None
            buckets[target].append(text)
            continue
        # No core overlap: assign ONLY if the phrase stays strictly inside one
        # midpoint-bounded column band without straddling any boundary.
        assigned = -1
        for i in range(n_cols):
            lo = -math.inf if i == 0 else midpoints[i - 1]
            hi = math.inf if i + 1 == n_cols else midpoints[i]
            if px0 >= lo and px1 <= hi:
                assigned = i
                break
        if assigned < 0:
            return None
        buckets[assigned].append(text)
    return [" ".join(parts).strip() for parts in buckets]


def _parse_geometry_column_owned_schedule_rows(
    rows: Sequence[Dict[str, Any]],
    page_no: int,
) -> Optional[List[ScheduleEntry]]:
    """Strict borderless multi-line/spanning schedule parser using word X-intervals.

    Returns:
      - None when rows have no word geometry or no geometry-proven header exists;
      - [] when a header exists but column ownership, header uniqueness, marks,
        or word coordinates fail closed;
      - List[ScheduleEntry] on clean column-owned extraction.
    """
    row_phrases: List[List[Tuple[float, float, str]]] = []
    has_geometry = False
    for row in rows:
        try:
            phrases = _extract_row_word_phrases(row)
        except ValueError:
            return []
        if phrases is None:
            return None
        has_geometry = True
        row_phrases.append(phrases)
    if not has_geometry or len(row_phrases) < 2:
        return None

    candidates: List[Tuple[int, List[Tuple[float, float]], Dict[str, Any], set[int]]] = []
    consumed: set[int] = set()
    for idx in range(len(row_phrases) - 1):
        if idx in consumed:
            continue
        # Try 3-row header with pure unit continuation row (idx, idx+1, idx+2) first.
        matched_3 = False
        if (
            idx + 2 < len(row_phrases)
            and row_phrases[idx + 2]
            and all(_is_strict_unit_only_label(t) for _, _, t in row_phrases[idx + 2])
        ):
            aligned3 = _align_two_header_rows_by_x(
                row_phrases[idx], row_phrases[idx + 1], row_phrases[idx + 2],
            )
            if aligned3 is not None:
                intervals, p_labels, c_labels, ambiguous = aligned3
                if ambiguous:
                    return []
                mapping = _explicit_nested_schedule_header(p_labels, c_labels)
                if mapping:
                    candidates.append((idx + 2, intervals, mapping, {idx, idx + 1, idx + 2}))
                    consumed.update((idx, idx + 1, idx + 2))
                    matched_3 = True
        if matched_3:
            continue

        aligned2 = _align_two_header_rows_by_x(row_phrases[idx], row_phrases[idx + 1])
        if aligned2 is not None:
            intervals, p_labels, c_labels, ambiguous = aligned2
            if ambiguous:
                return []
            mapping = _explicit_nested_schedule_header(p_labels, c_labels)
            if mapping:
                candidates.append((idx + 1, intervals, mapping, {idx, idx + 1}))
                consumed.update((idx, idx + 1))
                continue
            # Also try 3-row stacked parent header: (row[idx] + row[idx+1]) over row[idx+2]
            # when row[idx] + row[idx+1] stack strictly column-by-column.
            if idx + 2 < len(row_phrases) and row_phrases[idx + 2]:
                # Only stack parent rows that contain no opening marks or numeric dims.
                has_data_token = any(
                    _MARK_SEARCH_RE.search(t) or _parse_strict_schedule_dimension_cell(t) is not None
                    for _, _, t in row_phrases[idx + 1]
                )
                if not has_data_token:
                    stacked_parent = _align_two_header_rows_by_x(row_phrases[idx], row_phrases[idx + 1])
                    if stacked_parent is not None and not stacked_parent[3]:
                        sp_intervals, sp_top, sp_bot, _ = stacked_parent
                        combined_parent_phrases = [
                            (x0, x1, f"{top} {bot}".strip())
                            for (x0, x1), top, bot in zip(sp_intervals, sp_top, sp_bot)
                            if f"{top} {bot}".strip()
                        ]
                        aligned_3p = _align_two_header_rows_by_x(
                            combined_parent_phrases, row_phrases[idx + 2],
                        )
                        if aligned_3p is not None:
                            intervals3, p3, c3, amb3 = aligned_3p
                            if amb3:
                                return []
                            mapping3 = _explicit_nested_schedule_header(p3, c3)
                            if mapping3:
                                # Ensure top row actually contributed to mark or dim group
                                # so a title banner above a 2-row header is never absorbed.
                                m_col = mapping3["mark"]
                                w_col = mapping3["width"]
                                h_col = mapping3["height"]
                                top_only = _align_two_header_rows_by_x(
                                    row_phrases[idx + 1], row_phrases[idx + 2],
                                )
                                child_alone = (
                                    _explicit_nested_schedule_header(top_only[1], top_only[2])
                                    if top_only is not None and not top_only[3] else {}
                                )
                                if not child_alone and (
                                    any(
                                        min(px1, intervals3[col][1]) - max(px0, intervals3[col][0]) > -1.0
                                        for px0, px1, _ in row_phrases[idx]
                                        for col in (m_col, w_col, h_col)
                                    )
                                ):
                                    candidates.append((idx + 2, intervals3, mapping3, {idx, idx + 1, idx + 2}))
                                    consumed.update((idx, idx + 1, idx + 2))
                                    continue

            # Ambiguous group header with unprovable alignment must fail closed.
            if (
                any(_strict_group_parent_basis(t) for _, _, t in row_phrases[idx])
                and any(
                    _is_strict_width_child_label(t) or _is_strict_height_child_label(t)
                    for _, _, t in row_phrases[idx + 1]
                )
            ):
                return []

    # Also detect strict single-row headers with disjoint column intervals so
    # blank-column continuation lines (e.g. wrapped NOTES rows) never shift left
    # into the mark or dimension columns on borderless upright/rotated sheets.
    for idx, phrases in enumerate(row_phrases):
        if idx in consumed or len(phrases) < 2:
            continue
        if any(phrases[i][1] >= phrases[i + 1][0] - 1.0 for i in range(len(phrases) - 1)):
            continue
        labels = [text for _, _, text in phrases]
        mapping = _explicit_two_level_schedule_header(labels)
        if mapping:
            intervals = [(float(px0), float(px1)) for px0, px1, _ in phrases]
            candidates.append((idx, intervals, mapping, {idx}))
            consumed.add(idx)

    if not candidates:
        return None
    fields = ("mark", "dims", "width", "height", "count", "desc",
              "dimension_basis", "basis_source")
    signatures = {
        tuple(mapping.get(field) for field in fields)
        for _, _, mapping, _ in candidates
    }
    if len(signatures) != 1:
        return []
    header_end_idx, col_intervals, col_map, _ = min(candidates, key=lambda c: c[0])
    all_header_rows = set().union(*(c[3] for c in candidates))

    entries: List[ScheduleEntry] = []
    strict_marks_seen: set[Tuple[str, int]] = set()
    for row_idx in range(header_end_idx + 1, len(rows)):
        if row_idx in all_header_rows:
            continue
        phrases = row_phrases[row_idx]
        if not phrases:
            continue
        cells = _assign_phrases_to_columns(phrases, col_intervals)
        if cells is None:
            return []
        if "mark" not in col_map or col_map["mark"] >= len(cells):
            continue
        parsed_marks = _parse_strict_schedule_marks(cells[col_map["mark"]])
        if parsed_marks is None:
            continue
        if not parsed_marks:
            return []
        for mk in parsed_marks:
            canon_key = _canonical_opening_mark_key(mk)
            if canon_key is None or canon_key in strict_marks_seen:
                return []
            strict_marks_seen.add(canon_key)

        width_mm: Optional[int] = None
        height_mm: Optional[int] = None
        parse_source = "header_separate"
        if "dims" in col_map and col_map["dims"] < len(cells):
            width_mm, height_mm = _parse_strict_schedule_dims_cell(cells[col_map["dims"]])
            parse_source = "header_dims"
        elif "width" in col_map and "height" in col_map:
            w_idx, h_idx = col_map["width"], col_map["height"]
            if w_idx < len(cells):
                width_mm = _parse_strict_schedule_dimension_cell(cells[w_idx])
            if h_idx < len(cells):
                height_mm = _parse_strict_schedule_dimension_cell(cells[h_idx])
            parse_source = "header_separate"
        if width_mm is not None or height_mm is not None:
            if not _is_plausible_dimension(width_mm, height_mm):
                width_mm, height_mm = None, None
                parse_source = ""
        count = 1
        count_explicit = False
        if len(parsed_marks) == 1 and "count" in col_map and col_map["count"] < len(cells):
            try:
                raw_count = cells[col_map["count"]].lower().replace("x", "").strip()
                parsed_count = int(raw_count)
                if parsed_count >= 1:
                    count = parsed_count
                    count_explicit = True
            except (ValueError, TypeError):
                count = 1
                count_explicit = False
        desc = cells[col_map["desc"]].strip() if "desc" in col_map and col_map["desc"] < len(cells) else ""
        bbox = rows[row_idx].get("bbox", (0, 0, 0, 0))
        for mark in parsed_marks:
            entries.append(ScheduleEntry(
                type_mark=mark,
                width_mm=width_mm,
                height_mm=height_mm,
                description=desc,
                count=count,
                count_explicit=count_explicit,
                page_no=page_no,
                bbox=tuple(bbox) if len(bbox) >= 4 else (0, 0, 0, 0),
                parse_source=parse_source,
                dimension_basis=col_map.get("dimension_basis", ""),
                basis_source=col_map.get("basis_source", ""),
            ))
    return entries


def parse_schedule_rows(
    rows: Sequence[Dict[str, Any]],
    page_no: int = 0,
    *,
    two_level_header: bool = False,
) -> List[ScheduleEntry]:
    if type(two_level_header) is not bool:
        raise TypeError("two_level_header must be a bool")
    if not rows:
        return []

    if two_level_header:
        geom_entries = _parse_geometry_column_owned_schedule_rows(rows, page_no)
        if geom_entries is not None:
            return geom_entries

    entries: List[ScheduleEntry] = []
    col_map: Dict[str, int] = {}
    header_idx = -1
    header_rows: set[int] = set()

    if two_level_header:
        # An explicit two-row group may qualify its WIDTH/HEIGHT subcolumns.
        # Consume both header rows so the generic second row cannot erase an
        # authenticated LEAF/FRAME basis. Competing complete headers abstain.
        candidates: List[Tuple[int, Dict[str, Any]]] = []
        consumed: set[int] = set()
        for idx in range(len(rows) - 1):
            parent = [v.strip() for v in rows[idx].get("text", "").split("\t")]
            child = [v.strip() for v in rows[idx + 1].get("text", "").split("\t")]
            mapping = _explicit_nested_schedule_header(parent, child)
            if mapping:
                candidates.append((idx + 1, mapping))
                consumed.update((idx, idx + 1))
            elif (
                any(_strict_group_parent_basis(p) for p in parent)
                and any(
                    _is_strict_width_child_label(c) or _is_strict_height_child_label(c)
                    for c in child
                )
            ):
                # A grouped dimension header with unprovable alignment cannot
                # be reinterpreted as an unrelated generic child header.
                return []
        for idx, row in enumerate(rows):
            if idx in consumed:
                continue
            cells = [v.strip() for v in row.get("text", "").split("\t")]
            mapping = _explicit_two_level_schedule_header(cells)
            if mapping:
                candidates.append((idx, mapping))
                consumed.add(idx)
        if not candidates:
            return []
        fields = ("mark", "dims", "width", "height", "count", "desc",
                  "dimension_basis", "basis_source")
        signatures = {
            tuple(mapping.get(field) for field in fields)
            for _, mapping in candidates
        }
        if len(signatures) != 1:
            return []
        header_idx, col_map = min(candidates, key=lambda pair: pair[0])
        header_rows = consumed
    else:
        # Historical production path is byte-for-byte behaviourally unchanged.
        for idx, row in enumerate(rows):
            text = row.get("text", "")
            cells = [v.strip() for v in text.split("\t")]
            if _is_header_row(cells):
                col_map = detect_header(cells)
                header_idx = idx
                break

    if header_idx < 0:
        return _parse_rows_without_header(rows, page_no)

    strict_marks_seen: set[Tuple[str, int]] = set()
    for row_idx, row in enumerate(rows[header_idx + 1:], header_idx + 1):
        if two_level_header and row_idx in header_rows:
            continue
        text = row.get("text", "")
        bbox = row.get("bbox", (0, 0, 0, 0))
        cells = [c.strip() for c in text.split("\t")]
        if not any(cells):
            continue

        row_marks: List[str] = []
        if two_level_header:
            if "mark" not in col_map or col_map["mark"] >= len(cells):
                continue
            parsed_marks = _parse_strict_schedule_marks(cells[col_map["mark"]])
            if parsed_marks is None:
                continue
            if not parsed_marks:
                return []
            for mk in parsed_marks:
                canon_key = _canonical_opening_mark_key(mk)
                if canon_key is None or canon_key in strict_marks_seen:
                    return []
                strict_marks_seen.add(canon_key)
            row_marks = list(parsed_marks)
        else:
            mark = ""
            if "mark" in col_map and col_map["mark"] < len(cells):
                mark = extract_mark(cells[col_map["mark"]])
            # The strict opt-in table reader may not rescue a mark from a notes
            # column or from a row with a missing/wrong mark-cell address.
            if not mark:
                mark = extract_mark(text)
            if not _is_opening_mark(mark):
                continue
            row_marks = [mark]

        width_mm: Optional[int] = None
        height_mm: Optional[int] = None
        parse_source = "heuristic"

        if "dims" in col_map and col_map["dims"] < len(cells):
            if two_level_header:
                width_mm, height_mm = _parse_strict_schedule_dims_cell(cells[col_map["dims"]])
            else:
                width_mm, height_mm = parse_dimension(cells[col_map["dims"]])
            parse_source = "header_dims"
        elif "width" in col_map and "height" in col_map:
            w_idx = col_map["width"]
            h_idx = col_map["height"]
            dim_parser = (
                _parse_strict_schedule_dimension_cell
                if two_level_header else parse_single_dimension
            )
            if w_idx < len(cells):
                width_mm = dim_parser(cells[w_idx])
            if h_idx < len(cells):
                height_mm = dim_parser(cells[h_idx])
            parse_source = "header_separate"
        else:
            has_rating = _has_rating_keywords(text)
            width_mm, height_mm = parse_dimension(text, allow_slash=not has_rating)
            if _is_plausible_dimension(width_mm, height_mm):
                parse_source = "heuristic"
            else:
                width_mm, height_mm = None, None
                parse_source = ""

        if width_mm is not None or height_mm is not None:
            if not _is_plausible_dimension(width_mm, height_mm):
                width_mm, height_mm = None, None
                parse_source = ""

        count = 1
        count_explicit = False
        if len(row_marks) == 1 and "count" in col_map and col_map["count"] < len(cells):
            try:
                raw_count = cells[col_map["count"]].lower().replace("x", "").strip()
                parsed_count = int(raw_count)
                if parsed_count >= 1:
                    count = parsed_count
                    count_explicit = True
            except (ValueError, TypeError):
                count = 1
                count_explicit = False

        desc = ""
        if "desc" in col_map and col_map["desc"] < len(cells):
            desc = cells[col_map["desc"]].strip()

        for mark in row_marks:
            entries.append(ScheduleEntry(
                type_mark=mark,
                width_mm=width_mm,
                height_mm=height_mm,
                description=desc,
                count=count,
                count_explicit=count_explicit,
                page_no=page_no,
                bbox=tuple(bbox) if len(bbox) >= 4 else (0, 0, 0, 0),
                parse_source=parse_source,
                dimension_basis=col_map.get("dimension_basis", ""),
                basis_source=col_map.get("basis_source", ""),
            ))

    return entries


def _parse_rows_without_header(
    rows: Sequence[Dict[str, Any]],
    page_no: int,
) -> List[ScheduleEntry]:
    entries: List[ScheduleEntry] = []
    for row in rows:
        text = row.get("text", "")
        bbox = row.get("bbox", (0, 0, 0, 0))
        mark = extract_mark(text)
        if not _is_opening_mark(mark):
            continue
        has_rating = _has_rating_keywords(text)
        width_mm, height_mm = parse_dimension(text, allow_slash=not has_rating)
        if not _is_plausible_dimension(width_mm, height_mm):
            continue
        entries.append(ScheduleEntry(
            type_mark=mark,
            width_mm=width_mm,
            height_mm=height_mm,
            page_no=page_no,
            bbox=tuple(bbox) if len(bbox) >= 4 else (0, 0, 0, 0),
            parse_source="heuristic",
        ))
    return entries



def _grid_nested_header_match(
    parent: Sequence[Any],
    child: Sequence[Any],
) -> Tuple[Optional[Tuple[int, int, int, str]], bool]:
    """Match a strict 2-row native-grid header without crossing parent spans.

    Returns ``(match_or_none, had_conflict)`` where ``match_or_none`` is
    ``(mark_col, width_col, height_col, basis)``. A spanning parent group at
    column ``start`` terminates immediately at the first column ``c > start``
    carrying a distinct non-empty parent heading so an unrelated neighbor group
    (e.g. VISION PANEL, HARDWARE, NOTES) can never be borrowed.
    """
    if not (
        isinstance(parent, (list, tuple))
        and isinstance(child, (list, tuple))
        and len(parent) == len(child)
        and 3 <= len(parent) <= 100
    ):
        return None, False

    p_labels = [_normalize_cell_label(v) for v in parent]
    c_labels = [_normalize_cell_label(v) for v in child]

    marks = [
        col for col in range(len(p_labels))
        if _is_strict_mark_column_label(p_labels[col], c_labels[col])
    ]
    if len(marks) != 1:
        return None, False

    # Build strictly bounded contiguous parent-group spans. Any distinct
    # non-empty parent cell ends the preceding span immediately.
    group_spans: List[Tuple[int, int, str]] = []
    col = 0
    n_cols = len(p_labels)
    while col < n_cols:
        basis = _strict_group_parent_basis(p_labels[col])
        if not basis:
            col += 1
            continue
        start_label = p_labels[col]
        end = col + 1
        while end < n_cols and (p_labels[end] == "" or p_labels[end] == start_label):
            end += 1
        group_spans.append((col, end, basis))
        col = end

    matches: List[Tuple[int, int, int, str]] = []
    for start, end, basis in group_spans:
        # Reject conflicting basis wording inside child columns of this span.
        for c_idx in range(start, end):
            if c_labels[c_idx]:
                child_basis, _ = _infer_column_basis(c_labels[c_idx])
                if child_basis and child_basis != basis:
                    return None, True
        widths = [
            c_idx for c_idx in range(start, end)
            if _is_strict_width_child_label(c_labels[c_idx])
        ]
        heights = [
            c_idx for c_idx in range(start, end)
            if _is_strict_height_child_label(c_labels[c_idx])
        ]
        if len(widths) == len(heights) == 1:
            matches.append((marks[0], widths[0], heights[0], basis))
    if not matches:
        return None, False
    if len(matches) != 1:
        return None, True
    return matches[0], False


def _combine_grid_rows_by_column(
    top: Sequence[Any], bottom: Sequence[Any],
) -> List[str]:
    return [
        f"{_normalize_cell_label(a)} {_normalize_cell_label(b)}".strip()
        for a, b in zip(top, bottom)
    ]


def _explicit_grid_nested_schedule_entries(
    pdf_page: Any,
    page_no: int,
) -> Optional[List[ScheduleEntry]]:
    """Read native printed table-grid ownership, opt-in and noncommercial.

    A group header such as DOOR LEAF may span multiple child columns, bounded
    strictly by the next distinct non-empty parent cell. Supports single-row
    wrapped headers, two-row nested headers (including vertical split mark
    headers and unit-tagged child cells), and three-row wrapped nested headers.
    No opening instance, row-count quantity, rough wall aperture or customer
    seal is created. None means no qualifying grid; [] means competing/invalid.
    """
    try:
        detector = getattr(pdf_page, "find_tables", None)
        if not callable(detector):
            return None
        tables = tuple(detector(strategy="lines_strict").tables)
    except (AttributeError, ValueError, TypeError, RuntimeError):
        return None
    if len(tables) > 100:
        return []

    # Each found tuple: (grid, data_start_idx, mark_col, width_col, height_col, dims_col, basis, basis_source, parse_source)
    found: List[Tuple[List[Sequence[Any]], int, int, Optional[int], Optional[int], Optional[int], str, str, str]] = []
    header_count = 0

    for table in tables:
        try:
            grid = list(table.extract())
        except (AttributeError, ValueError, TypeError, RuntimeError):
            continue
        if len(grid) < 2 or len(grid) > 5000:
            continue

        matched_rows_in_table: set[int] = set()
        # Pass 1: 2-row and 3-row nested headers (parent + child).
        for idx in range(len(grid) - 1):
            if idx in matched_rows_in_table:
                continue
            parent, child = grid[idx], grid[idx + 1]
            if not (
                isinstance(parent, (list, tuple))
                and isinstance(child, (list, tuple))
                and len(parent) == len(child)
                and 3 <= len(parent) <= 100
            ):
                continue

            match, conflict = _grid_nested_header_match(parent, child)
            if conflict:
                return []
            if match is not None:
                data_start = idx + 2
                # Consume an immediately following pure-unit row (e.g. [None, "(mm)", "(mm)"]).
                if (
                    data_start < len(grid)
                    and isinstance(grid[data_start], (list, tuple))
                    and len(grid[data_start]) == len(parent)
                ):
                    unit_row = [_normalize_cell_label(v) for v in grid[data_start]]
                    non_empty_units = [u for u in unit_row if u]
                    if non_empty_units and all(_is_strict_unit_only_label(u) for u in non_empty_units):
                        matched_rows_in_table.add(data_start)
                        data_start += 1
                if data_start >= len(grid):
                    continue
                mark_col, width_col, height_col, basis = match
                header_count += 1
                matched_rows_in_table.update((idx, idx + 1))
                found.append((
                    grid, data_start, mark_col, width_col, height_col, None,
                    basis, f"grid:{basis}", "source_grid_nested_header",
                ))
                continue

            # Try 3-row stacked parent header: (grid[idx] + grid[idx+1]) over grid[idx+2],
            # strictly column-by-column without crossing columns and without absorbing
            # an unrelated banner row above an already-valid 2-row header.
            if (
                idx + 3 <= len(grid)
                and isinstance(grid[idx + 2], (list, tuple))
                and len(grid[idx + 2]) == len(parent)
            ):
                # Do not swallow a valid 2-row header at (idx+1, idx+2).
                sub_match, sub_conflict = _grid_nested_header_match(grid[idx + 1], grid[idx + 2])
                if sub_match is None and not sub_conflict:
                    mid_labels = [_normalize_cell_label(v) for v in grid[idx + 1]]
                    has_data_in_mid = any(
                        _MARK_SEARCH_RE.search(lbl) or _parse_strict_schedule_dimension_cell(lbl) is not None
                        for lbl in mid_labels if lbl
                    )
                    top_labels = [_normalize_cell_label(v) for v in parent]
                    if not has_data_in_mid and any(top_labels) and any(mid_labels):
                        combined_parent = _combine_grid_rows_by_column(parent, grid[idx + 1])
                        match3, conflict3 = _grid_nested_header_match(combined_parent, grid[idx + 2])
                        if conflict3:
                            return []
                        if match3 is not None:
                            mark_col, width_col, height_col, basis = match3
                            # Verify top row actually contributed to the mark or group column.
                            if any(
                                top_labels[c] for c in (mark_col, width_col, height_col)
                                if c < len(top_labels)
                            ):
                                header_count += 1
                                matched_rows_in_table.update((idx, idx + 1, idx + 2))
                                found.append((
                                    grid, idx + 3, mark_col, width_col, height_col, None,
                                    basis, f"grid:{basis}", "source_grid_nested_header",
                                ))
                                continue

            # Try 3-row stacked child+unit header: grid[idx] over (grid[idx+1] + grid[idx+2])
            # ONLY when grid[idx+2] is purely unit tokens.
            if (
                idx + 3 <= len(grid)
                and isinstance(grid[idx + 2], (list, tuple))
                and len(grid[idx + 2]) == len(parent)
            ):
                unit_labels = [_normalize_cell_label(v) for v in grid[idx + 2]]
                non_empty_units = [u for u in unit_labels if u]
                if non_empty_units and all(_is_strict_unit_only_label(u) for u in non_empty_units):
                    combined_child = _combine_grid_rows_by_column(child, grid[idx + 2])
                    match3u, conflict3u = _grid_nested_header_match(parent, combined_child)
                    if conflict3u:
                        return []
                    if match3u is not None:
                        mark_col, width_col, height_col, basis = match3u
                        header_count += 1
                        matched_rows_in_table.update((idx, idx + 1, idx + 2))
                        found.append((
                            grid, idx + 3, mark_col, width_col, height_col, None,
                            basis, f"grid:{basis}", "source_grid_nested_header",
                        ))
                        continue

        # Pass 2: Strict 1-row wrapped native-grid header (only for tables/rows
        # that had no 2-row/3-row nested header match).
        if not matched_rows_in_table:
            for idx, row_cells in enumerate(grid[:-1]):
                if not isinstance(row_cells, (list, tuple)) or not (2 <= len(row_cells) <= 100):
                    continue
                norm_cells = [" ".join(str(v or "").strip().split()) for v in row_cells]
                mapping = _explicit_two_level_schedule_header(norm_cells)
                if not mapping:
                    continue
                header_count += 1
                matched_rows_in_table.add(idx)
                basis = mapping.get("dimension_basis", "")
                basis_src = mapping.get("basis_source", "") or (f"grid:{basis}" if basis else "")
                found.append((
                    grid,
                    idx + 1,
                    mapping["mark"],
                    mapping.get("width"),
                    mapping.get("height"),
                    mapping.get("dims"),
                    basis,
                    basis_src,
                    "source_grid_nested_header",
                ))

    if header_count == 0:
        return None
    if len(found) != 1:
        return []
    (
        grid, data_start, mark_col, width_col, height_col, dims_col,
        basis, basis_source, parse_source,
    ) = found[0]
    required_cols = [c for c in (mark_col, width_col, height_col, dims_col) if c is not None]
    max_col = max(required_cols)

    entries: List[ScheduleEntry] = []
    marks_seen: set[Tuple[str, int]] = set()
    for cells in grid[data_start:]:
        if not (isinstance(cells, (tuple, list)) and max_col < len(cells)):
            return []
        parsed_marks = _parse_strict_schedule_marks(str(cells[mark_col] or ""))
        if parsed_marks is None:
            continue
        if not parsed_marks:
            return []
        if dims_col is not None:
            width, height = _parse_strict_schedule_dims_cell(str(cells[dims_col] or ""))
        else:
            width = _parse_strict_schedule_dimension_cell(str(cells[width_col] or "")) if width_col is not None else None
            height = _parse_strict_schedule_dimension_cell(str(cells[height_col] or "")) if height_col is not None else None
        for mark in parsed_marks:
            canon_key = _canonical_opening_mark_key(mark)
            if canon_key is None or canon_key in marks_seen:
                # Duplicate or canonically colliding typed schedule rows (e.g. D1 vs D01)
                # must fail closed rather than silently overwriting competing rows.
                return []
            marks_seen.add(canon_key)
            entries.append(ScheduleEntry(
                type_mark=mark,
                width_mm=width,
                height_mm=height,
                page_no=page_no,
                parse_source=parse_source,
                dimension_basis=basis,
                basis_source=basis_source,
            ))
    return entries


def _normalized_page_rotation(pdf_page: Any) -> Optional[int]:
    """Normalize PDF /Rotate to 0, 90, 180, or 270; fail closed (None) on invalid values."""
    raw = getattr(pdf_page, "rotation", 0)
    if raw is None:
        return 0
    if isinstance(raw, bool):
        return None
    if isinstance(raw, int):
        deg = raw
    elif isinstance(raw, float) and math.isfinite(raw) and raw.is_integer():
        deg = int(raw)
    else:
        return None
    if deg % 90 != 0:
        return None
    return deg % 360


def _validated_rotation_matrix(
    pdf_page: Any, rotation: int,
) -> Optional[Tuple[float, float, float, float, float, float]]:
    """Validate that pdf_page.rotation_matrix is a proper orthogonal 90/180/270 transform."""
    if rotation not in (90, 180, 270):
        return None
    try:
        matrix = pdf_page.rotation_matrix
        a, b, c, d, e, f = (
            float(matrix.a), float(matrix.b), float(matrix.c),
            float(matrix.d), float(matrix.e), float(matrix.f),
        )
    except (AttributeError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(v) for v in (a, b, c, d, e, f)):
        return None
    det = a * d - b * c
    if det <= 1e-12:
        # Reject singular or reflected (negative-determinant) frames.
        return None
    scale = max(1.0, abs(a), abs(b), abs(c), abs(d))
    tol = 1e-5 * scale
    if rotation == 90:
        if not (abs(a) <= tol and abs(d) <= tol and b > 0.0 and c < 0.0 and abs(b + c) <= tol):
            return None
    elif rotation == 180:
        if not (abs(b) <= tol and abs(c) <= tol and a < 0.0 and d < 0.0 and abs(a - d) <= tol):
            return None
    elif rotation == 270:
        if not (abs(a) <= tol and abs(d) <= tol and b < 0.0 and c > 0.0 and abs(b + c) <= tol):
            return None
    return (a, b, c, d, e, f)


def _rotated_display_words(pdf_page: Any) -> List[tuple]:
    """Explicit opt-in: page-native PyMuPDF word boxes to visible row space.

    Supports all three PDF page rotations (90, 180, 270 degrees, including
    modulo-360 normalized equivalents). Invalid coordinate frames or inverted
    word boxes fail closed. No transformation of stored source word IDs, wall
    coordinates, physical opening hosts or authority decisions.
    """
    rotation = _normalized_page_rotation(pdf_page)
    if rotation not in (90, 180, 270):
        return []
    validated = _validated_rotation_matrix(pdf_page, rotation)
    if validated is None:
        return []
    a, b, c, d, e, f = validated
    try:
        source_words = list(pdf_page.get_text("words") or [])
    except (AttributeError, TypeError, ValueError, OverflowError):
        return []
    transformed = []
    for word in source_words:
        if not isinstance(word, (list, tuple)) or len(word) < 5:
            return []
        try:
            x0, y0, x1, y1 = [float(v) for v in word[:4]]
        except (TypeError, ValueError, OverflowError):
            return []
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            return []
        if x1 < x0 or y1 < y0:
            return []
        corners = (
            (a * x + c * y + e, b * x + d * y + f)
            for x in (x0, x1) for y in (y0, y1)
        )
        points = tuple(corners)
        if not all(math.isfinite(v) for xy in points for v in xy):
            return []
        xs, ys = zip(*points)
        transformed.append((min(xs), min(ys), max(xs), max(ys), *word[4:]))
    return transformed


def parse_schedule_page(
    pdf_page: Any,
    page_no: int = 0,
    *,
    two_level_header: bool = False,
) -> List[ScheduleEntry]:
    if type(two_level_header) is not bool:
        raise TypeError("two_level_header must be a bool")
    if two_level_header:
        rotation = _normalized_page_rotation(pdf_page)
        if rotation is None:
            return []
        if rotation in (90, 180, 270) and _validated_rotation_matrix(pdf_page, rotation) is None:
            return []
        gridded = _explicit_grid_nested_schedule_entries(pdf_page, page_no)
        if gridded is not None:
            return gridded
        if rotation in (90, 180, 270):
            # The existing _word_rows groups NATIVE y; displayed landscape rows
            # can run across native x on /Rotate 90/180/270. Only the opted-in
            # strict reader uses transformed display rows, never the live default.
            words = _rotated_display_words(pdf_page)
            if not words:
                return []
            rows = _basic_word_rows(words)
        else:
            try:
                from pb_plan_read_engine_v1228 import _word_rows
                rows = _word_rows(pdf_page)
            except ImportError:
                try:
                    words = list(pdf_page.get_text("words") or [])
                except Exception:
                    return []
                rows = _basic_word_rows(words)
    else:
        try:
            from pb_plan_read_engine_v1228 import _word_rows
            rows = _word_rows(pdf_page)
        except ImportError:
            try:
                words = list(pdf_page.get_text("words") or [])
            except Exception:
                return []
            rows = _basic_word_rows(words)
    return parse_schedule_rows(
        rows, page_no=page_no, two_level_header=two_level_header,
    )


def _basic_word_rows(words: list) -> List[Dict[str, Any]]:
    if not words:
        return []
    usable = []
    for word in words:
        if not isinstance(word, (list, tuple)) or len(word) < 5:
            continue
        try:
            x0, y0, x1, y1 = map(float, word[:4])
        except Exception:
            continue
        if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
            continue
        if x1 < x0 or y1 < y0:
            continue
        text = str(word[4]).strip()
        if text:
            usable.append((x0, y0, x1, y1, text))
    if not usable:
        return []

    usable.sort(key=lambda item: ((item[1] + item[3]) / 2.0, item[0]))
    rows: List[List[tuple]] = []
    row_cy: List[float] = []
    tolerance = 5.0
    for item in usable:
        cy = (item[1] + item[3]) / 2.0
        best = -1
        best_d = 1e9
        for idx in range(len(rows)):
            d = abs(cy - row_cy[idx])
            if d <= tolerance and d < best_d:
                best, best_d = idx, d
        if best < 0:
            rows.append([item])
            row_cy.append(cy)
        else:
            rows[best].append(item)
            row_cy[best] = sum((p[1] + p[3]) / 2.0 for p in rows[best]) / len(rows[best])

    output = []
    for row in rows:
        row.sort(key=lambda item: item[0])
        pieces = []
        prev_x1 = None
        for x0, y0, x1, y1, text in row:
            if prev_x1 is not None:
                gap = x0 - prev_x1
                pieces.append("\t" if gap > 18.0 else " ")
            pieces.append(text)
            prev_x1 = x1
        output.append({
            "text": "".join(pieces).strip(),
            "bbox": [min(r[0] for r in row), min(r[1] for r in row),
                     max(r[2] for r in row), max(r[3] for r in row)],
            "words": row,
        })
    output.sort(key=lambda item: (item["bbox"][1], item["bbox"][0]))
    return output


def enrich_opening_evidence(
    instances: List[OpeningEvidence],
    schedule_entries: List[ScheduleEntry],
) -> List[OpeningEvidence]:
    if not instances or not schedule_entries:
        return list(instances)

    schedule_by_mark: Dict[str, List[ScheduleEntry]] = {}
    for entry in schedule_entries:
        if entry.type_mark:
            schedule_by_mark.setdefault(entry.type_mark, []).append(entry)

    _PROVENANCE_RANK = {"header_separate": 3, "header_dims": 2, "heuristic": 1, "": 0}
    mark_authority: Dict[str, Optional[ScheduleEntry]] = {}
    mark_conflicts: Dict[str, List[ScheduleEntry]] = {}
    for mark, entries_list in schedule_by_mark.items():
        if len(entries_list) == 1:
            mark_authority[mark] = entries_list[0]
        else:
            dims_set = set()
            for e in entries_list:
                dims_set.add((e.width_mm, e.height_mm, e.dimension_basis))
            if len(dims_set) == 1:
                best = max(entries_list,
                           key=lambda e: _PROVENANCE_RANK.get(e.parse_source, 0))
                mark_authority[mark] = best
            else:
                mark_authority[mark] = None
                mark_conflicts[mark] = entries_list

    enriched = []
    for inst in instances:
        mark = inst.type_mark
        if mark and mark in mark_authority:
            sched = mark_authority[mark]
            if sched is None:
                alternatives = mark_conflicts.get(mark, [])
                conflicting_obs = {
                    "source": "schedule_parse",
                    "width_m": None,
                    "height_m": None,
                    "dimension_basis": DIMENSION_BASIS_UNKNOWN,
                    "dimension_confidence": 0.0,
                    "type_mark": mark,
                    "page_no": None,
                    "accepted": False,
                    "status": "ambiguous",
                    "alternatives": [
                        {
                            "width_mm": e.width_mm,
                            "height_mm": e.height_mm,
                            "page_no": e.page_no,
                            "parse_source": e.parse_source,
                            "dimension_basis": e.dimension_basis,
                            "basis_source": e.basis_source,
                        }
                        for e in alternatives
                    ],
                }
                inst.source_observations = list(inst.source_observations) + [conflicting_obs]
                enriched.append(inst)
                continue
            if sched.parse_source == "header_separate":
                dim_conf = 0.8
            elif sched.parse_source == "header_dims":
                dim_conf = 0.75
            elif sched.parse_source == "heuristic":
                dim_conf = 0.5
            else:
                dim_conf = 0.5
            sched_basis = sched.dimension_basis or DIMENSION_BASIS_UNKNOWN
            sched_ev = OpeningEvidence(
                type_mark=mark,
                width_m=(sched.width_mm / 1000.0) if sched.width_mm else None,
                height_m=(sched.height_mm / 1000.0) if sched.height_mm else None,
                dimension_basis=sched_basis,
                dimension_source="schedule_parse",
                dimension_confidence=dim_conf,
                extraction_method="schedule_parse",
                page_no=sched.page_no,
            )
            sched_obs = {
                "source": "schedule_parse",
                "width_m": sched_ev.width_m,
                "height_m": sched_ev.height_m,
                "dimension_basis": sched_ev.dimension_basis,
                "dimension_confidence": sched_ev.dimension_confidence,
                "type_mark": mark,
                "page_no": sched_ev.page_no,
                "accepted": False,
            }
            merged = merge_opening_evidence(inst, sched_ev)
            if merged.dimension_source == "schedule_parse":
                sched_obs["accepted"] = True
            merged.source_observations = list(inst.source_observations) + [sched_obs]
            enriched.append(merged)
        else:
            enriched.append(inst)

    return enriched
