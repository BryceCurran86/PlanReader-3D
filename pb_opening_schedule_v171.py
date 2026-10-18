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

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

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


def parse_schedule_rows(
    rows: Sequence[Dict[str, Any]],
    page_no: int = 0,
) -> List[ScheduleEntry]:
    if not rows:
        return []

    entries: List[ScheduleEntry] = []
    col_map: Dict[str, int] = {}
    header_idx = -1

    for idx, row in enumerate(rows):
        text = row.get("text", "")
        cells = [c.strip() for c in text.split("\t")]
        if _is_header_row(cells):
            col_map = detect_header(cells)
            header_idx = idx
            break

    if header_idx < 0:
        return _parse_rows_without_header(rows, page_no)

    for row in rows[header_idx + 1:]:
        text = row.get("text", "")
        bbox = row.get("bbox", (0, 0, 0, 0))
        cells = [c.strip() for c in text.split("\t")]
        if not any(cells):
            continue

        mark = ""
        if "mark" in col_map and col_map["mark"] < len(cells):
            mark = extract_mark(cells[col_map["mark"]])
        if not mark:
            mark = extract_mark(text)
        if not _is_opening_mark(mark):
            continue

        width_mm: Optional[int] = None
        height_mm: Optional[int] = None
        parse_source = "heuristic"

        if "dims" in col_map and col_map["dims"] < len(cells):
            width_mm, height_mm = parse_dimension(cells[col_map["dims"]])
            parse_source = "header_dims"
        elif "width" in col_map and "height" in col_map:
            w_idx = col_map["width"]
            h_idx = col_map["height"]
            if w_idx < len(cells):
                width_mm = parse_single_dimension(cells[w_idx])
            if h_idx < len(cells):
                height_mm = parse_single_dimension(cells[h_idx])
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
        if "count" in col_map and col_map["count"] < len(cells):
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


def parse_schedule_page(
    pdf_page: Any,
    page_no: int = 0,
) -> List[ScheduleEntry]:
    try:
        from pb_plan_read_engine_v1228 import _word_rows
        rows = _word_rows(pdf_page)
    except ImportError:
        try:
            words = list(pdf_page.get_text("words") or [])
        except Exception:
            return []
        rows = _basic_word_rows(words)
    return parse_schedule_rows(rows, page_no=page_no)


def _basic_word_rows(words: list) -> List[Dict[str, Any]]:
    if not words:
        return []
    usable = []
    for word in words:
        if len(word) < 5:
            continue
        try:
            x0, y0, x1, y1 = map(float, word[:4])
        except Exception:
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
