"""Generic page / drawing-title authority.

Reads a sheet's drawing title and sheet number from positive structural
evidence, and fails closed when that evidence is missing.

Title evidence, strongest first:

1. A title-block field label bound to its value. The labels are "DRAWING
   TITLE", "DRG. TITLE", "DWG TITLE", "SHEET TITLE", "TITLE OF DRAWING", a
   bare "TITLE" (never "PROJECT TITLE" and the like), a bare "DRAWING:" whose
   value is a title and, inside a title block, "DESCRIPTION". The value is the
   rest of the label's own cell, the cell to its right on the same row, or the
   lines directly below it inside the label's column, stopping at the next
   field label.
2. A title-shaped line with drawing-title vocabulary inside a demonstrated
   title block: a cluster of drawing title-block field labels (scale, drawn,
   checked, revision, drawing number, ...). Values of other fields (project,
   client, consultants, dates, numbers) never compete.
3. One typographically dominant sheet heading with drawing-title vocabulary,
   such as a large schedule heading, on a drawing sheet. Several headings of
   similar size are view captions, not a sheet title.

Across the sheets of one document, the title position learned on one sheet is
reused on sheets with the same title-block layout, and text repeated on most
sheets (practice names, project names, standard notes) cannot become a title
unless a title label binds it.

Rejection is structural, never a list of phrases: sentences, list items and
the headings of note blocks, amounts, dates, page furniture, contact details,
company names and field labels.

The sheet number is only ever a value bound to a sheet-number label ("DRAWING
NO", "DWG NO", "SHEET NO", ...), directly or at the position learned from a
sibling sheet; no other code on the sheet is promoted to a sheet number.

A page without native text is read with the drawing OCR evidence layer; so are
the edge bands of a drawing-sized sheet whose native text has no title
evidence (title blocks drawn as vector lettering). OCR results are cached per
file, page and region.
"""
from __future__ import annotations

import math
import os
import re
import threading
from collections import Counter, OrderedDict
from dataclasses import dataclass, field, replace
from statistics import median
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

AUTHORITY = "page_title_authority/1"

# Minimum score per kind of evidence before a title is accepted.
_MIN_SCORE = {"label": 60.0, "layout": 60.0, "title_block_heading": 55.0, "sheet_heading": 55.0}
_OCR_MIN_WORDS = 5                # fewer native words than this: read the page with OCR
_OCR_MAX_PIXELS = 12_000_000
_DRAWING_SHEET_AREA = 0.9 * 842.0 * 1191.0   # A3 and larger sheets are drawing-sized


# ---------------------------------------------------------------------------
# Text cells
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Cell:
    """A contiguous run of text on one visual row, in page points."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    size: float
    bold: bool = False
    source: str = "native"

    @property
    def xc(self) -> float:
        return (self.x0 + self.x1) / 2.0

    @property
    def yc(self) -> float:
        return (self.y0 + self.y1) / 2.0

    @property
    def height(self) -> float:
        return max(0.5, self.y1 - self.y0)


_Item = Tuple[float, float, float, float, float, bool, str]


def _clean(value: Any) -> str:
    text = str(value or "").replace(" ", " ").replace("�", " ")
    return re.sub(r"\s+", " ", text).strip()


def _finite(values: Sequence[Any]) -> bool:
    try:
        return all(math.isfinite(float(v)) for v in values)
    except (TypeError, ValueError):
        return False


def _x_overlap(a: _Item, b: _Item) -> float:
    return min(a[2], b[2]) - max(a[0], b[0])


def _fits_row(item: _Item, row: Sequence[_Item]) -> bool:
    """Text that overlaps another fragment horizontally is on a different (stacked) row."""
    return not any(_x_overlap(item, part) > 0.3 * min(item[2] - item[0], part[2] - part[0]) for part in row if part is not item)


def _row_centre(row: Sequence[_Item]) -> float:
    return sum((part[1] + part[3]) / 2.0 for part in row) / len(row)


def cells_from_spans(spans: Iterable[Dict[str, Any]], source: str = "native") -> List[Cell]:
    """Group text spans ({text, bbox, size, font, flags}) into row cells.

    Fragments join the nearest visual row (by vertical centre) that they do
    not overlap; a row splits into separate cells at column-sized gaps, and
    fragments with almost no gap join without a space, so a word broken
    across spans reads as one word.
    """
    items: List[_Item] = []
    seen = set()
    for span in spans or []:
        text = _clean(span.get("text"))
        bbox = list(span.get("bbox") or [])[:4]
        if not text or len(bbox) < 4 or not _finite(bbox):
            continue
        x0, y0, x1, y1 = (float(v) for v in bbox)
        if x1 <= x0 or y1 <= y0:
            continue
        key = (text, round(x0, 1), round(y0, 1))
        if key in seen:  # the same text drawn twice at one position
            continue
        seen.add(key)
        size = float(span.get("size") or 0.0) or (y1 - y0)
        font = str(span.get("font") or "")
        bold = bool(int(span.get("flags") or 0) & 16) or bool(re.search(r"bold|black|heavy|demi", font, re.I))
        items.append((x0, y0, x1, y1, max(0.5, size), bold, text))
    items.sort(key=lambda item: ((item[1] + item[3]) / 2.0, item[0]))

    rows: List[List[_Item]] = []
    for item in items:
        yc = (item[1] + item[3]) / 2.0
        options = [row for row in rows[-12:]
                   if abs(yc - _row_centre(row)) <= 0.45 * max(item[4], median(part[4] for part in row)) and _fits_row(item, row)]
        if options:
            min(options, key=lambda row: abs(yc - _row_centre(row))).append(item)
        else:
            rows.append([item])
    # One refinement pass: a fragment placed before its true row existed moves
    # to the row whose centre is clearly nearer. Rows are created top to bottom,
    # so only neighbouring rows (the placement window) can be that close.
    for index, row in enumerate(rows):
        for item in list(row):
            if len(row) == 1:
                break
            yc = (item[1] + item[3]) / 2.0
            here = abs(yc - _row_centre(row))
            for other in rows[max(0, index - 12): index + 13]:
                if other is row or not other:
                    continue
                there = abs(yc - _row_centre(other))
                if there >= 0.8 * here or there > 0.45 * max(item[4], median(part[4] for part in other)):
                    continue
                if _fits_row(item, other):
                    row.remove(item)
                    other.append(item)
                    break

    cells: List[Cell] = []
    for row in rows:
        if not row:
            continue
        row.sort(key=lambda item: item[0])
        group = [row[0]]
        for item in row[1:]:
            previous = group[-1]
            gap = item[0] - previous[2]
            size = max(previous[4], item[4])
            # A column-sized gap always splits; a smaller one splits where the
            # next fragment starts another field (tightly packed title blocks).
            if gap > max(2.5 * size, 6.0) or (gap > max(0.8 * size, 3.0) and _starts_field(item[6])):
                cells.append(_make_cell(group, source))
                group = [item]
            else:
                group.append(item)
        cells.append(_make_cell(group, source))
    return [cell for cell in cells if cell.text]


def _starts_field(text: str) -> bool:
    label = parse_label(Cell(text, 0.0, 0.0, 1.0, 1.0, 1.0))
    return label is not None and (label.field in _BLOCK_FIELDS or label.field == "description")


def _make_cell(group: Sequence[_Item], source: str) -> Cell:
    pieces: List[str] = []
    for index, item in enumerate(group):
        if index and item[0] - group[index - 1][2] >= 0.2 * max(item[4], group[index - 1][4]):
            pieces.append(" ")
        pieces.append(item[6])
    bold_chars = sum(len(item[6]) for item in group if item[5])
    return Cell(
        text=_clean("".join(pieces)),
        x0=min(item[0] for item in group), y0=min(item[1] for item in group),
        x1=max(item[2] for item in group), y1=max(item[3] for item in group),
        size=max(item[4] for item in group),
        bold=bold_chars * 2 >= sum(len(item[6]) for item in group),
        source=source,
    )


def page_spans(pdf_page: Any) -> List[Dict[str, Any]]:
    """Horizontal text spans of a PyMuPDF page, in the page's visual orientation."""
    try:
        payload = pdf_page.get_text("dict") or {}
    except Exception:
        return []
    return spans_from_text_dict(payload, pdf_page)


def spans_from_text_dict(payload: Dict[str, Any], pdf_page: Any = None) -> List[Dict[str, Any]]:
    matrix = pdf_page.rotation_matrix if pdf_page is not None and int(getattr(pdf_page, "rotation", 0) or 0) else None
    out: List[Dict[str, Any]] = []
    for block in payload.get("blocks") or []:
        if int(block.get("type", 0) or 0) != 0:
            continue
        for line in block.get("lines") or []:
            dx, dy = (list(line.get("dir") or (1.0, 0.0)) + [0.0, 0.0])[:2]
            if matrix is not None:
                dx, dy = dx * matrix.a + dy * matrix.c, dx * matrix.b + dy * matrix.d
            if abs(dy) > 0.2 * max(abs(dx), 1e-9):
                continue  # vertical text is never a sheet title here
            for span in line.get("spans") or []:
                bbox = span.get("bbox")
                if matrix is not None and bbox is not None:
                    import fitz  # PyMuPDF is present whenever a page object is

                    bbox = tuple(fitz.Rect(bbox) * matrix)
                out.append({"text": span.get("text"), "bbox": bbox, "size": span.get("size"),
                            "font": span.get("font"), "flags": span.get("flags")})
    return out


def page_cells(pdf_page: Any) -> List[Cell]:
    return cells_from_spans(page_spans(pdf_page))


def _visual_size(pdf_page: Any) -> Tuple[float, float]:
    rect = pdf_page.rect  # PyMuPDF reports the rotated (visual) page rectangle
    return float(rect.width), float(rect.height)


# ---------------------------------------------------------------------------
# Field labels
# ---------------------------------------------------------------------------

_NUMBER_WORD = r"(?:NO|NOS|NUMBER|NUM|NBR|#|REF|REFERENCE)"
_LABEL_RULES: Tuple[Tuple[str, str, "re.Pattern[str]"], ...] = tuple(
    (name, strength, re.compile(pattern)) for name, strength, pattern in (
        # (field, strength, pattern) in priority order: number labels before their bare words.
        ("sheet_number", "sheet_number", rf"^(?:DRAWING|DRG|DWG|SHEET)\s*{_NUMBER_WORD}\b"),
        ("other_number", "other_number", rf"^(?:PROJECT|JOB|CONTRACT|FILE|REGISTRATION|APPOINTMENT|TENDER|ORDER|ACCOUNT|PLOT|PARCEL|LR|CLIENT|REVISION|REV|ISSUE)\s*{_NUMBER_WORD}\b"),
        ("title", "title_explicit", r"^(?:DRAWING|DRG|DWG|SHEET)\s*(?:TITLE|NAME)\b"),
        ("title", "title_explicit", r"^TITLE\s+OF\s+(?:THE\s+)?(?:DRAWING|SHEET)\b"),
        ("title", "title_bare", r"^TITLE\b"),
        ("drawing", "drawing", r"^(?:DRAWING|DRG|DWG)$"),
        ("description", "description", r"^DESCRIPTION\b"),
        ("project", "project", r"^(?:PROJECT|JOB|CONTRACT|SCHEME|DEVELOPMENT)(?:\s+(?:TITLE|NAME|DESCRIPTION|DETAILS))?\b"),
        ("client", "client", r"^(?:CLIENT|EMPLOYER|OWNER|DEVELOPER|PROPRIETOR|USER)(?:\s+(?:NAME|DETAILS))?\b"),
        ("site", "site", r"^(?:SITE|LOCATION|ADDRESS)(?:\s+(?:ADDRESS|NAME))?\b"),
        ("party", "party", r"^(?:ARCHITECTS?|ENGINEERS?|CONSULTANTS?|QUANTITY\s+SURVEYORS?|SURVEYORS?|CONTRACTORS?|PLANNERS?)\b"),
        ("party", "party", r"^(?:STRUCTURAL|CIVIL|SERVICES|MECHANICAL|ELECTRICAL|M\s*&\s*E|MEP|PLUMBING|FIRE)(?:\s*&\s*\w+)?\s+(?:ENGINEERS?|CONSULTANTS?)\b"),
        ("party", "party", r"^(?:CHIEF|PRINCIPAL|PROJECT|COUNTY|SENIOR|AG|ACTING)\s+[A-Z() &]*(?:ENGINEER|ARCHITECT|MANAGER|CO-?ORDINATOR|SURVEYOR|OFFICER)S?\b"),
        ("party", "party", r"^(?:PREPARED|SUBMITTED|ISSUED)\s+(?:BY|FOR|TO)\b"),
        ("drawn", "drawn", r"^DRAWN(?:\s+BY)?\b"),
        ("designed", "designed", r"^DESIGNED(?:\s+BY)?\b"),
        ("checked", "checked", r"^CHECKED(?:\s+BY)?\b"),
        ("approved", "approved", r"^(?:APPROVED|AUTHORI[SZ]ED|VERIFIED|CERTIFIED|REVIEWED)(?:\s+BY)?\b"),
        ("date", "date", r"^(?:DATE|PLOT\s+DATE|ISSUE\s+DATE)\b"),
        ("scale", "scale", r"^SCALES?\b"),
        ("revision", "revision", r"^(?:REV|REVISIONS?|AMENDMENTS?)\b"),
        ("status", "status", r"^(?:STATUS|DRAWING\s+STATUS|ISSUE\s+STATUS|PURPOSE\s+OF\s+ISSUE|STAGE)\b"),
        ("signature", "signature", r"^(?:SIGNATURE|SIGNED|SIGN|STAMP|SEAL)\b"),
        ("ref", "ref", r"^(?:REF|REFERENCE|CAD\s+FILE|CAD\s+REF|FILE)\b"),
        ("size", "size", r"^(?:PAPER\s+SIZE|SHEET\s+SIZE)\b"),
        ("copyright", "copyright", r"^COPYRIGHT\b"),
    )
)
# Fields only drawing title blocks carry (not tender forms or letters).
_DRAWING_FIELDS = {"sheet_number", "title", "scale", "drawn", "designed", "checked", "approved", "revision"}
# Labels that make up title blocks. Table headers such as DESCRIPTION,
# LOCATION or SIZE also head schedules, so they never define the region.
_BLOCK_FIELDS = {"sheet_number", "other_number", "title", "drawing", "project", "client", "party", "drawn", "designed",
                 "checked", "approved", "date", "scale", "revision", "status", "signature", "ref"}
_TITLE_STRENGTH = {"title_explicit": 96.0, "title_bare": 86.0, "drawing": 80.0, "description": 70.0}


def _split_joins(text: str) -> str:
    """Separate words run together by OCR or extraction ('TitleFOUNDATION' -> 'Title FOUNDATION')."""
    return re.sub(r"(?<=[a-z])(?=[A-Z]{2})", " ", str(text or ""))


def _label_key(text: str) -> str:
    """Upper-case form used to recognise labels: 'Drg.  Title :' -> 'DRG TITLE'."""
    value = _split_joins(text).upper()
    value = re.sub(r"\bN\s*[O°º0]\b\.?", "NO", value)  # "N o", "N°", "Nº"
    value = re.sub(r"[.:]", " ", value)
    value = re.sub(r"\s+", " ", value).strip(" -_")
    # "Drawing N" whose superscript "o" was set apart is "Drawing No".
    return re.sub(r"^((?:DRAWING|DRG|DWG|SHEET) )N$", r"\1NO", value)


@dataclass(frozen=True)
class Label:
    cell: Cell
    field: str
    strength: str
    remainder: str     # value text inside the label's own cell, if any


_LEADERS = re.compile(r"[\s._\-/]*")


def _remainder(raw: str, label_words: int) -> str:
    """Text of the cell after its first ``label_words`` label words ("N o" counts as one)."""
    tokens = list(re.finditer(r"[A-Za-z0-9#°º&]+", raw))
    index, consumed = 0, 0
    while index < len(tokens) and consumed < label_words:
        if tokens[index].group(0).upper() == "N" and index + 1 < len(tokens) and tokens[index + 1].group(0).upper() in {"O", "0"}:
            index += 1
        consumed += 1
        index += 1
    if index == 0 or index >= len(tokens) + 1:
        return ""
    return raw[tokens[index - 1].end():]


def parse_label(cell: Cell) -> Optional[Label]:
    key = _label_key(cell.text)
    if not key or len(key) > 90:
        return None
    for field_name, strength, pattern in _LABEL_RULES:
        match = pattern.match(key)
        if not match:
            continue
        rest = _remainder(_split_joins(cell.text), len(match.group(0).split()))
        separated = bool(re.match(r"^\s*(?::|-\s|–|—|\.{2,}|_{2,})", rest))
        value = rest.strip(" .:-_–—")
        if _LEADERS.fullmatch(value):
            value = ""
        if value and not separated:
            if strength == "title_bare":
                return None  # "Title of the person signing", "Title/position": a bare TITLE stands alone
            if field_name not in ("title", "sheet_number"):
                if field_name == "drawing" or has_title_vocabulary(value) or len(value.split()) > 2:
                    return None  # "SITE PLAN" is a title and "Scale bar shown..." a sentence, not labels
                value = ""       # "PROJECT TITLE", "CLIENT NAME": the rest of the label itself
        if field_name == "drawing" and not (separated or cell.text.rstrip().endswith(":")):
            return None  # a lone word "DRAWING" (a wrapped note, a heading) is not a label
        return Label(cell=cell, field=field_name, strength=strength, remainder=_clean(value))
    return None


def is_label_like(text: str) -> bool:
    value = _clean(text)
    label = parse_label(Cell(value, 0.0, 0.0, 1.0, 1.0, 1.0))
    if label is not None and not label.remainder:
        return True
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z .&/()-]{0,28}:", value)) and len(value.split()) <= 4


# ---------------------------------------------------------------------------
# Text shape
# ---------------------------------------------------------------------------

_STOPWORDS = {
    "the", "to", "be", "of", "and", "shall", "all", "is", "are", "with", "in", "for", "as", "by", "on", "unless",
    "otherwise", "must", "should", "will", "not", "any", "or", "at", "this", "that", "from", "where", "which", "it",
    "its", "their", "than", "have", "has", "been", "such", "into", "these", "those", "may", "if",
}
_TITLE_VOCAB = re.compile(
    r"\b(?:plans?|elevations?|sections?|schedules?|details?|detailing|layouts?|notes|legends?|index|"
    r"register|cover\s+sheet|perspectives?|views?|renders?|renderings?|isometrics?|axonometrics?|diagrams?|"
    r"schematics?|symbols|setting[- ]out|site|roof(?:ing)?|floors?|ceilings?|reflected|foundations?|footings?|"
    r"framing|reinforcement|structural|electrical|lighting|power|plumbing|drainage|sanitary|mechanical|hvac|"
    r"services|landscape|landscaping|external\s+works|demolition|finish(?:es|ing)?|doors?|windows?|joinery|"
    r"stairs?|staircases?|general\s+arrangement|blocks?|typical|arrangement|assembly|profiles?)\b",
    re.I,
)
_DATE_RE = re.compile(
    r"\b(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*\.?,?\s*\d{2,4}|"
    r"\d{1,2}\s*(?:ST|ND|RD|TH)?\s*(?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*,?\s*\d{2,4})\b",
    re.I,
)
_PAGE_FURNITURE_RE = re.compile(r"^(?:page\s*\d+(?:\s*of\s*\d+)?|\d+\s*\|\s*p\s*a\s*g\s*e|p\s*a\s*g\s*e\s*\d*|\d+\s*/\s*\d+)$", re.I)
_CONTACT_RE = re.compile(r"(?:\bP\.?\s*O\.?\s*BOX\b|\bTEL\b|\bFAX\b|\bE-?MAIL\b|@|\bwww\.|\.co\.|\.com\b|\+\d{3})", re.I)
_ORGANISATION_RE = re.compile(
    r"\b(?:LTD|LIMITED|LLP|INC|PLC|ASSOCIATES|CONSULTANTS|CONSULTING|ENGINEERS|ARCHITECTS|PLANNERS|"
    r"SURVEYORS|DESIGNERS|PARTNERS|&\s*CO|COMPANY)\b\.?",
    re.I,
)
_LIST_ITEM_RE = re.compile(r"^(?:\(?\d{1,3}[.)]|\(?[a-z][.)]|[•·\-–*])\s+\S")
_SCALE_RE = re.compile(r"(?<!\d)1\s*:\s*\d{1,5}(?!\d)|\bN\.?\s*T\.?\s*S\.?\b|\bNOT\s+TO\s+SCALE\b", re.I)
_AMOUNT_RE = re.compile(r"^(?:KSHS?\.?|KES|USD|\$|£|€)?[\d,]+(?:\.\d+)?(?:/-)?$", re.I)


def title_shape(text: str, *, bound: bool) -> Tuple[float, str]:
    """(score 0-1, reason). A score of 0 means the text cannot be a drawing title.

    ``bound`` values come from an explicit title label, so ordinary casing and
    a little more length are allowed; free text must look like a heading.
    """
    value = _clean(text)
    letters = sum(ch.isalpha() for ch in value)
    alnum = sum(ch.isalnum() for ch in value)
    words = re.findall(r"[A-Za-z][A-Za-z'’&/-]*|\d[\d,./:-]*", value)
    if letters < 3:
        return 0.0, "too few letters"
    if len(value) > (120 if bound else 80) or len(words) > (16 if bound else 11):
        return 0.0, "too long for a title"
    if letters < 0.5 * alnum:
        return 0.0, "mostly digits"
    if _AMOUNT_RE.match(value.replace(" ", "")) or (_DATE_RE.search(value) and letters <= 14):
        return 0.0, "a date or amount"
    if _PAGE_FURNITURE_RE.match(value):
        return 0.0, "page furniture"
    if _CONTACT_RE.search(value):
        return 0.0, "contact details"
    if _LIST_ITEM_RE.match(value) and len(words) >= 3:
        return 0.0, "a list item"
    if _SCALE_RE.fullmatch(value):
        return 0.0, "a scale"
    if is_label_like(value):
        return 0.0, "a field label"
    lowered = [w for w in words if w[:1].islower()]
    stops = sum(1 for w in words if w.lower() in _STOPWORDS)
    if bound:
        if len(words) >= 8 and stops >= 3:
            return 0.0, "a sentence"
        return 1.0, "title-shaped"
    if len(words) >= 5 and (len(lowered) * 2 >= len(words) or stops >= 2):
        return 0.0, "a sentence"
    if value.endswith(".") and len(words) >= 4:
        return 0.0, "a sentence"
    if stops >= 3:
        return 0.0, "a sentence"
    if _ORGANISATION_RE.search(value):
        return 0.0, "a company name"
    upper_ratio = sum(ch.isupper() for ch in value) / max(1, letters)
    return 0.7 + 0.3 * min(1.0, upper_ratio * 1.2), "heading-shaped"


def has_title_vocabulary(text: str) -> bool:
    return bool(_TITLE_VOCAB.search(text or ""))


def sheet_number_shape(text: str) -> bool:
    value = _clean(text)
    if not value or len(value) > 32 or len(value.split()) > 5:
        return False
    if not re.search(r"\d", value) or ":" in value or _CONTACT_RE.search(value):
        return False
    if _DATE_RE.search(value) or _SCALE_RE.search(value) or ("," in value and _AMOUNT_RE.match(value.replace(" ", ""))):
        return False
    letters = sum(ch.isalpha() for ch in value)
    if letters > 18 or (len(value.split()) >= 3 and letters > 10):
        return False  # words, not a code
    return not is_label_like(value)


def normalise_sheet_number(text: str) -> str:
    value = _clean(text).strip(" .:-_")
    return re.sub(r"\s*([-/])\s*", r"\1", value)


# ---------------------------------------------------------------------------
# Page analysis
# ---------------------------------------------------------------------------

Box = Tuple[float, float, float, float]


@dataclass
class Candidate:
    text: str
    kind: str                 # label / layout / title_block_heading / sheet_heading / heading
    score: float
    region: str
    reason: str
    box: Box = (0.0, 0.0, 0.0, 0.0)   # relative to the page (0-1)
    rejected: str = ""
    lines: Tuple[str, ...] = ()       # the text lines a heading was merged from

    def as_dict(self) -> Dict[str, Any]:
        out = {"text": self.text, "kind": self.kind, "score": round(self.score, 1), "region": self.region, "reason": self.reason}
        if self.rejected:
            out["rejected"] = self.rejected
        return out


@dataclass
class PageAnalysis:
    page_no: int
    width: float
    height: float
    source: str                                            # native / native+ocr / ocr / none
    candidates: List[Candidate] = field(default_factory=list)
    sheet_numbers: List[Tuple[str, str]] = field(default_factory=list)   # (value, how)
    title_block: Optional[Box] = None                      # page points
    layout: Tuple[Tuple[str, int, int], ...] = ()          # (field, x%, y%) of title-block labels
    learned: Dict[str, Box] = field(default_factory=dict)  # relative value boxes of bound title / sheet number
    block_cells: List[Tuple[str, Box]] = field(default_factory=list)     # unlabelled title-block text (relative)
    texts: Tuple[str, ...] = ()                            # normalised free candidate texts
    empty_title_field: bool = False


@dataclass
class PageTitle:
    page_no: int
    title: str
    confidence: int
    source: str
    region: str
    reason: str
    sheet_number: str
    sheet_number_source: str
    text_source: str
    candidates: List[Dict[str, Any]]

    def meta(self) -> Dict[str, Any]:
        return {
            "title": self.title, "title_confidence": self.confidence, "title_source": self.source,
            "title_region": self.region, "title_reason": self.reason, "sheet_number": self.sheet_number,
            "sheet_number_source": self.sheet_number_source, "title_text_source": self.text_source,
            "title_authority": AUTHORITY, "title_candidates": self.candidates[:6],
        }


def _norm_text(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", " ", str(text or "").upper()).strip()


def _box(cell: Cell) -> Box:
    return (cell.x0, cell.y0, cell.x1, cell.y1)


def _rel(box: Box, width: float, height: float) -> Box:
    return (box[0] / width, box[1] / height, box[2] / width, box[3] / height)


def _union(parts: Sequence[Cell]) -> Box:
    return (min(p.x0 for p in parts), min(p.y0 for p in parts), max(p.x1 for p in parts), max(p.y1 for p in parts))


def _region_name(box: Box, width: float, height: float) -> str:
    xc = (box[0] + box[2]) / 2.0 / max(width, 1.0)
    yc = (box[1] + box[3]) / 2.0 / max(height, 1.0)
    vertical = "top" if yc < 0.33 else ("bottom" if yc > 0.67 else "middle")
    horizontal = "left" if xc < 0.33 else ("right" if xc > 0.67 else "centre")
    return f"{vertical}-{horizontal}"


def _inside(cell: Cell, box: Optional[Box]) -> bool:
    return box is not None and box[0] <= cell.xc <= box[2] and box[1] <= cell.yc <= box[3]


def _box_gap(a: Cell, b: Cell) -> float:
    dx = max(0.0, max(a.x0, b.x0) - min(a.x1, b.x1))
    dy = max(0.0, max(a.y0, b.y0) - min(a.y1, b.y1))
    return math.hypot(dx, dy)


def _collect_below(label: Cell, cells: Sequence[Cell], stops: Sequence[Cell], height: float,
                   right_limit: float, max_rows: int) -> List[Cell]:
    """Rows of text directly below a label inside its column, up to the next field label."""
    left = label.x0 - 1.5 * label.size
    top = label.y1 - 0.35 * label.height
    stop_y = min((other.y0 for other in stops if other is not label and other.y0 > top
                  and other.x0 < right_limit and other.x1 > left), default=math.inf)
    below = sorted((c for c in cells if c is not label and c not in stops and c.y0 >= top
                    and left <= c.x0 < right_limit and c.y0 < stop_y - 0.2 * c.height),
                   key=lambda c: (c.yc, c.x0))
    first_limit = label.y1 + max(3.5 * label.size, 0.045 * height)
    rows: List[List[Cell]] = []
    for cell in below:
        if not rows:
            if cell.y0 > first_limit:
                break
            rows.append([cell])
            continue
        last = rows[-1]
        if abs(cell.yc - sum(c.yc for c in last) / len(last)) <= 0.6 * cell.height:
            last.append(cell)
            continue
        size = median(c.size for c in last)
        # A value continues only in the same type at line spacing; a new size or
        # a wider gap is the next piece of text, not more of this value.
        if (len(rows) >= max_rows or cell.y0 - max(c.y1 for c in last) > max(size, cell.height)
                or not 0.9 <= cell.size / max(size, 0.1) <= 1.1):
            break
        rows.append([cell])
    return [cell for row in rows for cell in sorted(row, key=lambda c: c.x0)]


def _bind(label: Label, cells: Sequence[Cell], stops: Sequence[Cell], width: float, height: float,
          valid: Callable[[str], bool], max_rows: int, single: bool = False) -> Tuple[str, str, List[Cell]]:
    """A field label's value: its own cell, then right of it on the row, then below it in its column.

    ``single`` values (sheet numbers) are one cell: the first below the label.
    """
    cell = label.cell
    if label.remainder and valid(label.remainder):
        return label.remainder, "same cell", [cell]
    mates = sorted((c for c in cells if c is not cell and abs(c.yc - cell.yc) <= 0.6 * max(c.height, cell.height)
                    and c.x0 >= cell.x1 - 2.0), key=lambda c: c.x0)
    right_limit = width
    if mates:
        first = mates[0]
        if first in stops:
            right_limit = first.x0
        elif first.x0 - cell.x1 <= max(14.0 * cell.size, 0.18 * width) and valid(first.text):
            return first.text, "right of label", [first]
        # the next label to the right on this row closes the label's column
        right_limit = min([m.x0 for m in mates if m in stops] or [width])
    rows = _collect_below(cell, cells, stops, height, right_limit, max_rows)
    if rows:
        if single:
            first = min(rows, key=lambda c: (c.y0 > rows[0].y1, abs(c.x0 - cell.x0)))
            return (first.text, "below label", [first]) if valid(first.text) else ("", "", [])
        text = _clean(" ".join(c.text for c in rows))
        if valid(text):
            return text, "below label", rows
        if valid(rows[0].text):
            return rows[0].text, "below label", [rows[0]]
    return "", "", []


def _cluster(labels: Sequence[Label], width: float, height: float) -> List[List[Label]]:
    link = 0.08 * max(width, height)
    clusters: List[List[Label]] = []
    for label in sorted(labels, key=lambda item: (item.cell.y0, item.cell.x0)):
        joined = [cluster for cluster in clusters if any(_box_gap(label.cell, other.cell) <= link for other in cluster)]
        merged = [label]
        for cluster in joined:
            merged.extend(cluster)
            clusters.remove(cluster)
        clusters.append(merged)
    return clusters


def _block_heading(cell: Cell, cells: Sequence[Cell]) -> bool:
    """A heading directly followed by sentences or list items heads a text block (notes, clauses)."""
    below = [c for c in cells if c is not cell and cell.y1 - 0.2 * cell.height <= c.y0 <= cell.y1 + 3.0 * cell.height
             and c.x0 < cell.x1 + 4 * cell.size and c.x1 > cell.x0 - 4 * cell.size]
    body = sum(1 for c in below if _LIST_ITEM_RE.match(c.text) or title_shape(c.text, bound=False)[1] == "a sentence")
    return body >= 1 and len(below) >= 2


def _heading_blocks(cells: Sequence[Cell]) -> List[Tuple[Cell, Tuple[str, ...]]]:
    """Merge the stacked lines of one heading (same size, aligned, tight spacing); keep its lines."""
    ordered = sorted(cells, key=lambda c: (c.y0, c.x0))
    used = set()
    blocks: List[Tuple[Cell, Tuple[str, ...]]] = []
    for index, cell in enumerate(ordered):
        if index in used:
            continue
        parts = [cell]
        used.add(index)
        for other_index in range(index + 1, len(ordered)):
            if other_index in used:
                continue
            other, last = ordered[other_index], parts[-1]
            if other.y0 > last.y1 + 2 * last.size:
                break
            if other.y0 - last.y1 > 0.6 * last.size or other.y0 < last.y1 - 0.3 * last.height:
                continue
            if abs(other.size - last.size) > 0.1 * last.size:
                continue
            overlap = min(other.x1, last.x1) - max(other.x0, last.x0)
            if overlap < 0.4 * min(other.x1 - other.x0, last.x1 - last.x0):
                continue
            parts.append(other)
            used.add(other_index)
        if len(parts) == 1:
            blocks.append((cell, (cell.text,)))
        else:
            x0, y0, x1, y1 = _union(parts)
            blocks.append((Cell(_clean(" ".join(p.text for p in parts)), x0, y0, x1, y1, max(p.size for p in parts),
                                all(p.bold for p in parts), cell.source), tuple(p.text for p in parts)))
    return blocks


def analyse_cells(cells: Sequence[Cell], width: float, height: float, page_no: int, source: str = "native") -> PageAnalysis:
    """Title and sheet-number evidence of one page, before cross-sheet resolution."""
    analysis = PageAnalysis(page_no=int(page_no), width=float(width), height=float(height), source=source if cells else "none")
    if not cells or width <= 0 or height <= 0:
        return analysis
    labels = [label for label in (parse_label(cell) for cell in cells) if label is not None]
    stops = [label.cell for label in labels]

    # A demonstrated title block: a cluster of drawing title-block field labels.
    best: Optional[List[Label]] = None
    for cluster in _cluster([label for label in labels if label.field in _BLOCK_FIELDS], width, height):
        fields = {label.field for label in cluster}
        if len(fields) >= 3 and len(fields & _DRAWING_FIELDS) >= 2:
            if best is None or len(fields) > len({label.field for label in best}):
                best = cluster
    if best is not None:
        margin = 0.012 * max(width, height)
        box = _union([label.cell for label in best])
        drop = max(0.02 * height, 3.0 * median(label.cell.size for label in best))
        analysis.title_block = (max(0.0, box[0] - margin), max(0.0, box[1] - margin),
                                min(width, box[2] + margin), min(height, box[3] + drop))
        analysis.layout = tuple(sorted({(label.field, round(label.cell.x0 / width * 100), round(label.cell.y0 / height * 100))
                                        for label in best}))

    # Values of every field. Titles become candidates; all other values are
    # claimed, so a project, client, consultant, date or number never competes.
    claimed = set()
    for label in labels:
        claimed.add(id(label.cell))
        if label.field in ("title", "description", "drawing"):
            continue
        if label.field == "sheet_number":
            value, how, parts = _bind(label, cells, stops, width, height, sheet_number_shape, 1, single=True)
            if value:
                analysis.sheet_numbers.append((normalise_sheet_number(value), how))
                analysis.learned.setdefault("sheet_number", _rel(_union(parts), width, height))
        else:
            value, how, parts = _bind(label, cells, stops, width, height, lambda text: bool(_clean(text)), 3)
        claimed.update(id(part) for part in parts)

    drawing_sheet = analysis.title_block is not None or width * height >= _DRAWING_SHEET_AREA
    for label in labels:
        if label.field not in ("title", "description", "drawing"):
            continue
        if label.field == "description" and not _inside(label.cell, analysis.title_block):
            continue  # schedule columns are headed "DESCRIPTION" too
        if label.strength in ("title_bare", "drawing") and not drawing_sheet:
            continue  # a bare TITLE or DRAWING field on a form or letter is not a sheet title
        value, how, parts = _bind(label, cells, stops, width, height, lambda text: title_shape(text, bound=True)[0] > 0, 5)
        if label.field == "drawing" and value and sheet_number_shape(value):
            analysis.sheet_numbers.append((normalise_sheet_number(value), how))
            continue
        region = "title block" if _inside(label.cell, analysis.title_block) else _region_name(_box(label.cell), width, height)
        if not value:
            analysis.empty_title_field = analysis.empty_title_field or label.strength == "title_explicit"
            analysis.candidates.append(Candidate("", "label", 0.0, region, f"'{label.cell.text}' field has no value",
                                                 _rel(_box(label.cell), width, height), "empty field"))
            continue
        score = _TITLE_STRENGTH[label.strength] * title_shape(value, bound=True)[0] + (4.0 if region == "title block" else 0.0)
        box = _rel(_union(parts), width, height)
        analysis.candidates.append(Candidate(value, "label", score, region, f"value of '{label.cell.text}' ({how})", box))
        analysis.learned.setdefault("title", box)
        claimed.update(id(part) for part in parts)

    free = [cell for cell in cells if id(cell) not in claimed]
    if analysis.title_block is not None:
        analysis.block_cells = [(cell.text, _rel(_box(cell), width, height)) for cell in free if _inside(cell, analysis.title_block)]

    # Headings: inside the title block, or one dominant heading on a drawing sheet.
    blocks = _heading_blocks(free)
    sizes = [cell.size for cell in cells if len(cell.text) >= 3]
    body = median(sizes) if sizes else 0.0
    shaped = [(block, lines, title_shape(block.text, bound=False)[0]) for block, lines in blocks]
    headings = [(block, lines, shape) for block, lines, shape in shaped if shape > 0 and has_title_vocabulary(block.text)]
    for block, lines, shape in headings:
        if block.source == "ocr":
            continue  # OCR text is trusted only where a field label binds it
        in_block = _inside(block, analysis.title_block)
        region = "title block" if in_block else _region_name(_box(block), width, height)
        box = _rel(_box(block), width, height)
        if _block_heading(block, cells):
            analysis.candidates.append(Candidate(block.text, "heading", 0.0, region, "heads a block of notes or clauses", box,
                                                 "text-block heading", lines))
            continue
        if in_block:
            larger = sum(1 for other, _l, _s in headings if _inside(other, analysis.title_block) and other.size > 1.05 * block.size)
            score = 58.0 + 6.0 * shape - 3.0 * larger + (3.0 if block.bold else 0.0)
            analysis.candidates.append(Candidate(block.text, "title_block_heading", score, region,
                                                 "drawing-title vocabulary inside the title block", box, "", lines))
            continue
        if not drawing_sheet or body <= 0 or block.size < 1.4 * body:
            continue
        peers = [other for other, _l, _s in headings if other is not block and not _inside(other, analysis.title_block)
                 and other.size >= 0.8 * block.size and _norm_text(other.text) != _norm_text(block.text)]
        if peers:
            analysis.candidates.append(Candidate(block.text, "sheet_heading", 0.0, region,
                                                 f"one of {len(peers) + 1} similar view captions", box, "view caption", lines))
            continue
        score = 52.0 + 6.0 * shape + min(6.0, 2.0 * (block.size / body - 1.4)) + (2.0 if block.bold else 0.0)
        analysis.candidates.append(Candidate(block.text, "sheet_heading", score, region,
                                             f"the only dominant heading ({block.size:.0f} pt, body text {body:.0f} pt)", box, "", lines))
    analysis.texts = tuple(sorted({_norm_text(text) for c in analysis.candidates if c.kind != "label"
                                   for text in (c.text, *c.lines) if text}))
    return analysis


# ---------------------------------------------------------------------------
# Page entry point (native text, OCR fallback)
# ---------------------------------------------------------------------------

_OCR_CACHE: "OrderedDict[tuple, List[Cell]]" = OrderedDict()
_OCR_LOCK = threading.Lock()
_OCR_CACHE_SIZE = 256
_OCR_AVAILABLE: Optional[bool] = None


def ocr_available() -> bool:
    """Whether the drawing OCR evidence layer has a backend on this host (checked once)."""
    global _OCR_AVAILABLE
    if _OCR_AVAILABLE is None:
        available = False
        try:
            from pb_portable_raster_ocr_authority import RapidOCRBackend

            available = bool(RapidOCRBackend().is_available())
        except Exception:
            pass
        if not available:
            try:
                import pb_drawing_ocr_evidence_layer as layer

                available = bool(getattr(layer, "_HAS_WINOCR", False))
            except Exception:
                pass
        if not available:
            try:
                import pytesseract

                pytesseract.get_tesseract_version()
                available = True
            except Exception:
                pass
        _OCR_AVAILABLE = available
    return _OCR_AVAILABLE


def _page_identity(pdf_page: Any) -> Optional[tuple]:
    try:
        name = str(pdf_page.parent.name or "")
        if not name or not os.path.isfile(name):
            return None
        stat = os.stat(name)
        return (os.path.abspath(name), stat.st_size, stat.st_mtime_ns, int(pdf_page.number))
    except Exception:
        return None


def ocr_cells(pdf_page: Any, engine: Any = None, clip: Optional[Box] = None) -> List[Cell]:
    """OCR lines of a page region, read through the drawing OCR evidence layer.

    Results are cached per file (path, size, mtime), page and region, so a
    page is only OCR'd once per process however often it is re-registered.
    An injected engine is never cached.
    """
    width, height = _visual_size(pdf_page)
    identity = _page_identity(pdf_page)
    key = None if identity is None or engine is not None else identity + (tuple(round(v, 1) for v in clip) if clip else None,)
    if key is not None:
        with _OCR_LOCK:
            cached = _OCR_CACHE.get(key)
            if cached is not None:
                _OCR_CACHE.move_to_end(key)
                return list(cached)
    if engine is None:
        from pb_drawing_ocr_evidence_layer import DrawingOCREngine

        engine = DrawingOCREngine()
    area_w = (clip[2] - clip[0]) if clip else width
    area_h = (clip[3] - clip[1]) if clip else height
    dpi = int(max(72, min(150, math.sqrt(_OCR_MAX_PIXELS / max(1.0, area_w * area_h)) * 72)))
    clip_rect = None
    if clip is not None:
        import fitz

        clip_rect = fitz.Rect(*clip)
    try:
        lines = engine.recognize_page_rect(pdf_page, clip_rect, dpi=dpi) or []
    except Exception:
        lines = []
    spans: List[Dict[str, Any]] = []
    for line in lines:
        text = _clean(line.get("text"))
        bbox = list(line.get("bounding_box") or [])[:4]
        # The evidence layer scales line confidence by image quality, and a mostly
        # white title-block band scores low; values are still checked structurally.
        if not text or len(bbox) < 4 or not _finite(bbox) or float(line.get("confidence") or 0.0) < 0.3:
            continue
        x0, y0, x1, y1 = (float(v) for v in bbox)
        if x1 > x0 and y1 > y0:
            spans.append({"text": text, "bbox": (x0, y0, x1, y1), "size": 0.8 * (y1 - y0)})
    # OCR returns words or short runs; assemble them into cells exactly like native spans.
    cells = cells_from_spans(spans, source="ocr")
    if key is not None:
        with _OCR_LOCK:
            _OCR_CACHE[key] = list(cells)
            while len(_OCR_CACHE) > _OCR_CACHE_SIZE:
                _OCR_CACHE.popitem(last=False)
    return cells


def _has_title_evidence(analysis: PageAnalysis) -> bool:
    return analysis.title_block is not None or any(c.score > 0 for c in analysis.candidates)


def _vector_paths(pdf_page: Any) -> int:
    """How many vector paths a page draws: drawings carry hundreds, text pages a handful."""
    try:
        return len(pdf_page.get_cdrawings())
    except Exception:
        try:
            return len(pdf_page.get_drawings())
        except Exception:
            return 0


def _drawing_like(pdf_page: Any, width: float, height: float) -> bool:
    """A drawing sheet: a drawing-sized vector drawing or scan, or any heavily vector-drawn page.

    Bills and specifications (text pages, ruled tables) draw a few hundred
    paths at most, so they are never OCR'd for a title.
    """
    paths = _vector_paths(pdf_page)
    if paths >= 1000:
        return True
    return width * height >= _DRAWING_SHEET_AREA and (paths >= 400 or _image_cover(pdf_page) >= 0.25)


def _image_cover(pdf_page: Any) -> float:
    """Share of the page covered by its largest image (scanned or rasterised drawings)."""
    try:
        area = max(1.0, float(pdf_page.rect.width) * float(pdf_page.rect.height))
        best = 0.0
        for image in pdf_page.get_images(full=True):
            for rect in pdf_page.get_image_rects(image[0]):
                best = max(best, float(rect.width) * float(rect.height) / area)
        return best
    except Exception:
        return 0.0


def analyse_page(pdf_page: Any, page_no: int, *, spans: Optional[Sequence[Dict[str, Any]]] = None,
                 ocr_engine: Any = None, allow_ocr: bool = True) -> PageAnalysis:
    """Evidence of one PyMuPDF page. ``spans`` reuses text already extracted from the page.

    OCR is only used where native text cannot answer, and only on drawings: a
    page with (almost) no native text that draws something is OCR'd whole, and
    a drawing-sized vector drawing whose native text carries no title evidence
    has its edge bands (where title blocks are drawn) OCR'd and read together
    with the native text. Text pages (bills, specifications, forms) are never
    OCR'd.
    """
    width, height = _visual_size(pdf_page)
    cells = cells_from_spans(spans if spans is not None else page_spans(pdf_page))
    native = analyse_cells(cells, width, height, page_no, "native")
    if not allow_ocr or (ocr_engine is None and not ocr_available()):
        return native
    words = sum(len(cell.text.split()) for cell in cells)
    if words < _OCR_MIN_WORDS:
        if _image_cover(pdf_page) < 0.05 and _vector_paths(pdf_page) < 50:
            return native  # a blank page
        ocr = ocr_cells(pdf_page, ocr_engine)
        return analyse_cells(ocr, width, height, page_no, "ocr") if ocr else native
    if not _has_title_evidence(native) and int(getattr(pdf_page, "rotation", 0) or 0) == 0 and _drawing_like(pdf_page, width, height):
        bands = [(0.0, 0.8 * height, width, height), (0.8 * width, 0.0, width, 0.8 * height)]
        extra: List[Cell] = []
        for band in bands:
            extra.extend(cell for cell in ocr_cells(pdf_page, ocr_engine, band)
                         if not any(_box_gap(cell, other) == 0.0 and _norm_text(cell.text) == _norm_text(other.text) for other in cells))
        if extra:
            combined = analyse_cells(list(cells) + extra, width, height, page_no, "native+ocr")
            if _has_title_evidence(combined):
                return combined
    return native


# ---------------------------------------------------------------------------
# Cross-sheet resolution
# ---------------------------------------------------------------------------


def _same_layout(a: PageAnalysis, b: PageAnalysis) -> bool:
    if not a.layout or not b.layout:
        return False
    if abs(a.width - b.width) > 0.02 * a.width or abs(a.height - b.height) > 0.02 * a.height:
        return False
    matches = sum(1 for item in a.layout
                  if any(item[0] == other[0] and abs(item[1] - other[1]) <= 2 and abs(item[2] - other[2]) <= 2 for other in b.layout))
    return matches >= 3


def _text_at(page: PageAnalysis, box: Box) -> str:
    """Unlabelled title-block text whose centre lies in a (relative) box learned from a sibling sheet."""
    pad_x, pad_y = 0.01, 0.006
    hits = [(b[1], b[0], text) for text, b in page.block_cells
            if box[0] - pad_x <= (b[0] + b[2]) / 2.0 <= box[2] + pad_x and box[1] - pad_y <= (b[1] + b[3]) / 2.0 <= box[3] + pad_y]
    return _clean(" ".join(text for _y, _x, text in sorted(hits)))


def _learned_from(page: PageAnalysis, learners: Sequence[PageAnalysis], key: str) -> Tuple[str, int]:
    """Text at the position a sibling sheet with the same title block binds ``key``."""
    if not page.layout:
        return "", 0
    for sibling in learners:
        if sibling is page or key not in sibling.learned or not _same_layout(page, sibling):
            continue
        text = _text_at(page, sibling.learned[key])
        if text:
            return text, sibling.page_no
    return "", 0


def resolve_document(pages: Sequence[PageAnalysis]) -> List[PageTitle]:
    """Choose each page's title and sheet number using the evidence of all pages of its document."""
    block_pages = [page for page in pages if page.title_block is not None]
    repeated = set()
    if len(block_pages) >= 3:
        counts = Counter(text for page in block_pages for text in set(page.texts))
        threshold = max(3, math.ceil(0.6 * len(block_pages)))
        repeated = {text for text, count in counts.items() if count >= threshold}

    # Only sheets that bound a label can teach its position: O(pages x learners), not O(pages^2).
    learners = [page for page in pages if page.learned and page.layout]
    results: List[PageTitle] = []
    for page in pages:
        candidates = [replace(c) for c in page.candidates]
        for candidate in candidates:
            if candidate.kind == "label" or candidate.score <= 0:
                continue
            if _norm_text(candidate.text) in repeated:
                candidate.score, candidate.rejected = 0.0, "repeated on most sheets of this document"
                continue
            kept = [line for line in candidate.lines if _norm_text(line) not in repeated]
            if candidate.lines and len(kept) < len(candidate.lines):
                # A heading merged with a line that every sheet carries keeps only its own lines.
                text = _clean(" ".join(kept))
                if text and title_shape(text, bound=False)[0] > 0 and has_title_vocabulary(text):
                    candidate.text, candidate.lines = text, tuple(kept)
                    candidate.reason += "; line repeated on most sheets dropped"
                else:
                    candidate.score, candidate.rejected = 0.0, "repeated on most sheets of this document"
        if not any(c.kind == "label" and c.score > 0 for c in candidates) and not page.empty_title_field:
            text, sibling = _learned_from(page, learners, "title")
            if text and title_shape(text, bound=True)[0] > 0:
                candidates.append(Candidate(text, "layout", 74.0, "title block",
                                            f"title position of p{sibling} (same title block layout)"))
        live = sorted((c for c in candidates if c.score >= _MIN_SCORE.get(c.kind, math.inf)), key=lambda c: -c.score)
        title, confidence, source, region, reason = "", 0, "", "", ""
        if live:
            top = live[0]
            rivals = [c for c in live[1:] if c.kind == top.kind and top.score - c.score < 3.0
                      and _norm_text(c.text) != _norm_text(top.text)]
            if rivals:
                reason = f"ambiguous: '{top.text}' and '{rivals[0].text}' carry equal evidence"
            else:
                title, confidence, source, region, reason = top.text, int(round(min(99.0, top.score))), top.kind, top.region, top.reason
        if not title and not reason:
            if page.source == "none":
                reason = "no native or OCR text on this page"
            elif page.empty_title_field:
                reason = "the title block's drawing-title field is empty"
            elif page.title_block is None:
                reason = "no title block and no dominant sheet heading"
            else:
                reason = "no title-shaped value in the title block"
        values = sorted({value for value, _how in page.sheet_numbers if value})
        sheet_number, sheet_source = "", ""
        if len(values) == 1:
            sheet_number = values[0]
            sheet_source = next(how for value, how in page.sheet_numbers if value == sheet_number)
        elif len(values) > 1:
            sheet_source = "ambiguous: " + ", ".join(values)
        else:
            text, sibling = _learned_from(page, learners, "sheet_number")
            if text and sheet_number_shape(text):
                sheet_number, sheet_source = normalise_sheet_number(text), f"sheet-number position of p{sibling}"
        results.append(PageTitle(
            page_no=page.page_no, title=title, confidence=confidence, source=source, region=region, reason=reason,
            sheet_number=sheet_number, sheet_number_source=sheet_source, text_source=page.source,
            candidates=[c.as_dict() for c in sorted(candidates, key=lambda c: -c.score)],
        ))
    return results


def resolve_page(pdf_page: Any, page_no: int = 1, **kwargs: Any) -> PageTitle:
    return resolve_document([analyse_page(pdf_page, page_no, **kwargs)])[0]


def display_title(meta: Dict[str, Any], page_no: int, page_label: str = "") -> str:
    """What to show for a page: its title, else its sheet number, else a neutral page identifier."""
    if meta.get("title_authority"):
        return str(meta.get("title") or meta.get("sheet_number") or f"Page {int(page_no)}")
    return str(meta.get("title") or page_label or f"Page {int(page_no)}")
