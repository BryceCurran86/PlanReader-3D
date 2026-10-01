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

OCR (the drawing OCR evidence layer) only reads drawings whose native text
cannot answer, and only where a title block can be: text pages are never read.
The regions, most targeted first, are

1. an empty drawing-title or sheet-number field of a demonstrated title block
   where an image lies over the value (a value pasted in as a picture);
2. the title-block region that sibling sheets of the same size demonstrate in
   native text (siblings say where to look, never what the text is);
3. the raster images in the bottom and right title-block bands of a raster
   sheet or a drawing-sized sheet;
4. the whole bottom and right edge bands of a heavily vector-drawn sheet
   (title blocks drawn as vector lettering);
5. the whole sheet, only when it has no text layer at all.

Reading stops once a field label binds a title or sheet number, or once the
title block shows both fields empty; a field whose value lies just outside a
region read is read next. OCR text is trusted only where a field label binds
it, as for native text, and only once a second read of the value alone, at
another resolution, agrees. An OCR heading is never a title, OCR text never
joins or re-sizes native text, and a sibling's field position only ever
supplies native text. OCR results are cached per file, page, region and
resolution.
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


def _label_words(text: str) -> int:
    """How many words of ``text`` the field label itself uses ('PROJECT TITLE ...' -> 2)."""
    key = _label_key(text)
    for _field, _strength, pattern in _LABEL_RULES:
        match = pattern.match(key)
        if match:
            return len(match.group(0).split())
    return 0


def split_label_runs(cell: Cell) -> List[Cell]:
    """Split a cell that runs several field labels together, such as the OCR line
    'DRAWING NUMBER REVISION', so each value binds to its own label.

    A cut is made only after the whole leading label phrase ('PROJECT TITLE'
    stays one label) and before a later field label, and a drawing title's own
    words are never cut ('... NOTES AND REVISIONS' stays whole). Positions are
    shared out in proportion to the characters.
    """
    words = list(re.finditer(r"\S+", cell.text))
    for index in range(max(1, _label_words(cell.text)), len(words)):
        cut = words[index].start()
        rest = cell.text[cut:]
        if not _starts_field(rest):
            continue
        head = parse_label(replace(cell, text=cell.text[:cut]))
        if head is None or (head.field == "title" and head.remainder):
            return [cell]
        at = cell.x0 + (cell.x1 - cell.x0) * cut / max(1, len(cell.text))
        return [replace(cell, text=_clean(cell.text[:cut]), x1=at - 0.5)] + split_label_runs(replace(cell, text=_clean(rest), x0=at))
    return [cell]


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
    label_strength: str = ""          # for a label-bound value: the strength of the field label that bound it

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
    sheet_number_boxes: List[Box] = field(default_factory=list)          # where each value is (relative)
    title_block: Optional[Box] = None                      # page points
    layout: Tuple[Tuple[str, int, int], ...] = ()          # (field, x%, y%) of title-block labels
    learned: Dict[str, Box] = field(default_factory=dict)  # relative value boxes of bound title / sheet number
    block_cells: List[Tuple[str, Box]] = field(default_factory=list)     # unlabelled title-block text (relative)
    texts: Tuple[str, ...] = ()                            # normalised free candidate texts
    empty_title_field: bool = False
    recovery: Optional["_Recovery"] = field(default=None, repr=False, compare=False)  # regions to read with OCR
    ocr: Dict[str, Any] = field(default_factory=dict)      # what OCR read, where and why


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
    ocr: Dict[str, Any] = field(default_factory=dict)

    def meta(self) -> Dict[str, Any]:
        out = {
            "title": self.title, "title_confidence": self.confidence, "title_source": self.source,
            "title_region": self.region, "title_reason": self.reason, "sheet_number": self.sheet_number,
            "sheet_number_source": self.sheet_number_source, "title_text_source": self.text_source,
            "title_authority": AUTHORITY, "title_candidates": self.candidates[:6],
        }
        if self.ocr:
            out["title_ocr"] = self.ocr
        return out


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
    """Rows of text directly below a label inside its column, up to the next field label.

    A value starts at the label's left edge, or is centred under it (centred title blocks).
    """
    left = label.x0 - 1.5 * label.size
    top = label.y1 - 0.35 * label.height
    stop_y = min((other.y0 for other in stops if other is not label and other.y0 > top
                  and other.x0 < right_limit and other.x1 > left), default=math.inf)

    def aligned(c: Cell) -> bool:
        return left <= c.x0 or abs(c.xc - label.xc) <= 0.1 * max(c.x1 - c.x0, label.x1 - label.x0) + label.size

    below = sorted((c for c in cells if c is not label and c not in stops and c.y0 >= top
                    and aligned(c) and c.x0 < right_limit and c.y0 < stop_y - 0.2 * c.height),
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
        # a wider gap is the next piece of text, not more of this value. OCR line
        # heights vary with ascenders and descenders, so read sizes are rougher.
        low, high = (0.6, 1.67) if cell.source == "ocr" or any(c.source == "ocr" for c in last) else (0.9, 1.1)
        if (len(rows) >= max_rows or cell.y0 - max(c.y1 for c in last) > max(size, cell.height)
                or not low <= cell.size / max(size, 0.1) <= high):
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


_OCR_NOTE = ", read with OCR"


def _ocr_note(label: Label, parts: Sequence[Cell]) -> str:
    """Marks a bound value whose label or text was read with OCR."""
    return _OCR_NOTE if parts and (label.cell.source == "ocr" or any(part.source == "ocr" for part in parts)) else ""


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
            if abs(other.size - last.size) > 0.1 * last.size or other.source != last.source:
                continue  # another type size, or OCR text that must not join a native heading
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
                analysis.sheet_numbers.append((normalise_sheet_number(value), how + _ocr_note(label, parts)))
                analysis.sheet_number_boxes.append(_rel(_union(parts), width, height))
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
        how += _ocr_note(label, parts)
        if label.field == "drawing" and value and sheet_number_shape(value):
            analysis.sheet_numbers.append((normalise_sheet_number(value), how))
            analysis.sheet_number_boxes.append(_rel(_union(parts), width, height))
            continue
        region = "title block" if _inside(label.cell, analysis.title_block) else _region_name(_box(label.cell), width, height)
        if not value:
            analysis.empty_title_field = analysis.empty_title_field or label.strength == "title_explicit"
            analysis.candidates.append(Candidate("", "label", 0.0, region, f"'{label.cell.text}' field has no value",
                                                 _rel(_box(label.cell), width, height), "empty field"))
            continue
        score = _TITLE_STRENGTH[label.strength] * title_shape(value, bound=True)[0] + (4.0 if region == "title block" else 0.0)
        if how.endswith(_OCR_NOTE):
            score -= 6.0  # a label binds it, but the letters themselves are read, not extracted
        box = _rel(_union(parts), width, height)
        analysis.candidates.append(Candidate(value, "label", score, region, f"value of '{label.cell.text}' ({how})", box,
                                             label_strength=label.strength))
        analysis.learned.setdefault("title", box)
        claimed.update(id(part) for part in parts)

    free = [cell for cell in cells if id(cell) not in claimed]
    if analysis.title_block is not None:
        # Text found by position alone (a sibling's field position) must be extracted text, never read text.
        analysis.block_cells = [(cell.text, _rel(_box(cell), width, height)) for cell in free
                                if _inside(cell, analysis.title_block) and cell.source != "ocr"]

    # Headings: inside the title block, or one dominant heading on a drawing sheet.
    blocks = _heading_blocks(free)
    # Body text size comes from the native text when there is any: OCR line heights
    # are rough and must not make a native heading look dominant.
    sizes = ([cell.size for cell in cells if len(cell.text) >= 3 and cell.source != "ocr"]
             or [cell.size for cell in cells if len(cell.text) >= 3])
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
# Page entry point (native text, then a plan for targeted OCR)
# ---------------------------------------------------------------------------

_OCR_CACHE: "OrderedDict[tuple, List[Cell]]" = OrderedDict()
_OCR_LOCK = threading.Lock()
_OCR_CACHE_SIZE = 256
_OCR_AVAILABLE: Optional[bool] = None
_OCR_STATS = {"calls": 0, "cache_hits": 0, "pixels": 0}
_REGION_DPI = 300                 # title-block regions and fields are small: read them finely
_REGION_MAX_PIXELS = 8_000_000
_BAND_IMAGE_DPI = 200             # an image under a whole title-block band
_BAND_IMAGE_MAX_PIXELS = 6_000_000
_CHECK_DPI = 400                  # a value read with OCR is read again, alone, at this resolution
_CHECK_MAX_PIXELS = 2_000_000


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


def ocr_stats() -> Dict[str, int]:
    """OCR engine calls, cache hits and pixels rendered since the last reset (for measurement)."""
    with _OCR_LOCK:
        return dict(_OCR_STATS)


def reset_ocr_stats() -> None:
    with _OCR_LOCK:
        for key in _OCR_STATS:
            _OCR_STATS[key] = 0


def _page_identity(pdf_page: Any) -> Optional[tuple]:
    try:
        name = str(pdf_page.parent.name or "")
        if not name or not os.path.isfile(name):
            return None
        stat = os.stat(name)
        return (os.path.abspath(name), stat.st_size, stat.st_mtime_ns, int(pdf_page.number))
    except Exception:
        return None


def _dpi_for(area: float, cap: float, max_pixels: float) -> int:
    return int(max(72, min(cap, math.sqrt(max_pixels / max(1.0, area)) * 72)))


def ocr_cells(pdf_page: Any, engine: Any = None, clip: Optional[Box] = None, dpi: Optional[int] = None) -> List[Cell]:
    """OCR lines of a page region (visual page points), read through the drawing OCR evidence layer.

    Results are cached per file (path, size, mtime), page, region and
    resolution, so a region is only OCR'd once per process however often the
    page is re-registered. An injected engine is never cached.
    """
    width, height = _visual_size(pdf_page)
    area_w = (clip[2] - clip[0]) if clip else width
    area_h = (clip[3] - clip[1]) if clip else height
    if dpi is None:
        dpi = _dpi_for(area_w * area_h, 150, _OCR_MAX_PIXELS)
    identity = _page_identity(pdf_page)
    key = None if identity is None or engine is not None else identity + (tuple(round(v, 1) for v in clip) if clip else None, int(dpi))
    if key is not None:
        with _OCR_LOCK:
            cached = _OCR_CACHE.get(key)
            if cached is not None:
                _OCR_CACHE.move_to_end(key)
                _OCR_STATS["cache_hits"] += 1
                return list(cached)
    if engine is None:
        from pb_drawing_ocr_evidence_layer import DrawingOCREngine

        engine = DrawingOCREngine()
    clip_rect = None
    if clip is not None:
        import fitz

        clip_rect = fitz.Rect(*clip)  # PyMuPDF clips in the page's visual (rotated) coordinates
    with _OCR_LOCK:
        _OCR_STATS["calls"] += 1
        _OCR_STATS["pixels"] += int(area_w * dpi / 72.0) * int(area_h * dpi / 72.0)
    try:
        lines = engine.recognize_page_rect(pdf_page, clip_rect, dpi=int(dpi)) or []
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
    # OCR returns words or short runs; assemble them into cells exactly like native
    # spans, and separate field labels that one OCR line runs together.
    cells = [piece for cell in cells_from_spans(spans, source="ocr") for piece in split_label_runs(cell)]
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


# Geometry of boxes in page points.

def _area(box: Box) -> float:
    return max(0.0, box[2] - box[0]) * max(0.0, box[3] - box[1])


def _intersect(a: Box, b: Box) -> Box:
    return (max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3]))


def _bounds(boxes: Sequence[Box]) -> Box:
    return (min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes))


def _cover(boxes: Sequence[Box], region: Box, steps: int = 64) -> float:
    """Share of ``region`` covered by the union of ``boxes`` (sampled on a grid; exact enough to gate on)."""
    x0, y0, x1, y1 = region
    if x1 <= x0 or y1 <= y0:
        return 0.0
    rows = [bytearray(steps) for _ in range(steps)]
    sx, sy = steps / (x1 - x0), steps / (y1 - y0)
    for box in boxes:
        c0, c1 = max(0, int(round((box[0] - x0) * sx))), min(steps, int(round((box[2] - x0) * sx)))
        r0, r1 = max(0, int(round((box[1] - y0) * sy))), min(steps, int(round((box[3] - y0) * sy)))
        if c1 > c0:
            for row in rows[r0:r1]:
                row[c0:c1] = b"\x01" * (c1 - c0)
    return sum(row.count(1) for row in rows) / float(steps * steps)


def _bands(width: float, height: float) -> Tuple[Box, Box]:
    """Where title blocks are drawn when nothing says otherwise: the bottom and right edge bands.

    They overlap in the corner, so a corner title block is never cut in two.
    """
    return (0.0, 0.8 * height, width, height), (0.8 * width, 0.0, width, height)


@dataclass(frozen=True)
class _Image:
    box: Box        # visual page points
    dpi: float      # resolution the image was placed at


def _page_images(pdf_page: Any, width: float, height: float) -> List[_Image]:
    """Placed raster images of a page (scans, raster sheets, pasted title blocks), largest first.

    Specks (under 0.05 % of the page: bullets, stamps, hatch tiles) never hold
    a title block and are ignored.
    """
    try:
        infos = pdf_page.get_image_info()
    except Exception:
        return []
    import fitz

    matrix = pdf_page.rotation_matrix if int(getattr(pdf_page, "rotation", 0) or 0) else None
    page_box = fitz.Rect(0.0, 0.0, width, height)
    out: List[_Image] = []
    for info in infos:
        bbox = list(info.get("bbox") or [])[:4]
        if len(bbox) < 4 or not _finite(bbox):
            continue
        rect = fitz.Rect(bbox)
        if matrix is not None:
            rect = rect * matrix
        pixels = max(int(info.get("width") or 0), int(info.get("height") or 0))
        dpi = pixels / (max(rect.width, rect.height) / 72.0) if pixels and not rect.is_empty else 0.0
        rect = rect & page_box
        if rect.is_empty or rect.width * rect.height < 0.0005 * width * height:
            continue
        out.append(_Image((rect.x0, rect.y0, rect.x1, rect.y1), dpi))
    out.sort(key=lambda image: -_area(image.box))
    return out[:128]


def _panel(image: _Image, width: float, height: float) -> bool:
    """An image big enough to be a title block; logos, stamps and seals are smaller."""
    box = image.box
    return _area(box) >= 0.002 * width * height and min(box[2] - box[0], box[3] - box[1]) >= 36.0


def _sheet_image(image: _Image, width: float, height: float) -> bool:
    """A raster sheet or one strip of a tiled raster sheet, as opposed to a pasted panel."""
    box = image.box
    return _area(box) >= 0.25 * width * height or box[2] - box[0] >= 0.9 * width or box[3] - box[1] >= 0.9 * height


def _image_dpi(clip: Box, images: Sequence[_Image], cap: float, max_pixels: float) -> int:
    """Read an image region at its own resolution (never below 150 dpi, never above ``cap``)."""
    native = max((image.dpi for image in images if _area(_intersect(image.box, clip)) > 0), default=0.0)
    return _dpi_for(_area(clip), min(cap, max(150.0, native)) if native else cap, max_pixels)


@dataclass
class _Recovery:
    """Why and where a page whose native text cannot answer may be read with OCR."""

    page: Any                      # the PyMuPDF page, valid while its document is open
    identity: Optional[tuple]      # (path, size, mtime, index) to re-open the page once its document is closed
    engine: Any
    cells: List[Cell]              # native text cells
    words: int
    images: List[_Image]
    cover: float = 0.0             # share of the page under raster images
    sparse: bool = False           # (almost) no native text on a page that draws something
    raster: bool = False           # a raster sheet, or an image in a title-block band of a drawing-sized sheet
    vector: bool = False           # a heavily vector-drawn sheet (lettering may be drawn, not text)
    field_clips: List[Box] = field(default_factory=list)   # empty title-block fields over an image


def _value_zone(label: Cell, stops: Sequence[Cell], width: float, height: float) -> Box:
    """Where a field label's value is written: right of it on its row and below it in its column."""
    right = min([s.x0 for s in stops if s is not label and s.x0 >= label.x1 - 2.0
                 and abs(s.yc - label.yc) <= 0.6 * max(s.height, label.height)]
                + [min(width, label.x1 + max(14.0 * label.size, 0.18 * width))])
    left = max(0.0, label.x0 - 1.5 * label.size)
    below = min((s.y0 for s in stops if s is not label and s.y0 > label.y1 - 0.35 * label.height
                 and s.x0 < right and s.x1 > left), default=math.inf)
    bottom = min(below, label.y1 + max(8.0 * label.size, 0.08 * height), height)
    return left, max(0.0, label.y0 - 0.3 * label.height), right, bottom


def _bound(analysis: PageAnalysis) -> Tuple[bool, bool]:
    """Whether a page's field labels bind a drawing title, and a sheet number."""
    return any(c.kind == "label" and c.score > 0 for c in analysis.candidates), bool(analysis.sheet_numbers)


def _empty_field_zones(cells: Sequence[Cell], analysis: PageAnalysis, width: float, height: float) -> List[Box]:
    """Value areas of a demonstrated title block's drawing-title and sheet-number labels that bind nothing."""
    if analysis.title_block is None:
        return []
    has_title, has_number = _bound(analysis)
    labels = [label for label in (parse_label(cell) for cell in cells) if label is not None]
    stops = [label.cell for label in labels]
    return [_value_zone(label.cell, stops, width, height) for label in labels
            if ((label.field == "title" and not has_title) or (label.field == "sheet_number" and not has_number))
            and not label.remainder and _inside(label.cell, analysis.title_block)]


def _merge(boxes: Sequence[Box]) -> List[Box]:
    merged: List[Box] = []
    for box in sorted(boxes):
        if merged and _area(_intersect(merged[-1], box)) > 0:
            merged[-1] = _bounds([merged[-1], box])
        else:
            merged.append(box)
    return merged


def _field_clips(cells: Sequence[Cell], native: PageAnalysis, images: Sequence[_Image], width: float, height: float) -> List[Box]:
    """Where a demonstrated title block's drawing-title or sheet-number field has no text but an image.

    The value may be pasted in as a picture. Only the empty field's value area
    under an image is read, so logos and stamps elsewhere in the block are not.
    """
    clips = []
    for zone in _empty_field_zones(cells, native, width, height):
        under = [image.box for image in images if _area(_intersect(image.box, zone)) >= 0.2 * min(_area(zone), _area(image.box))]
        if under:
            clips.append(_intersect(zone, _bounds(under)))
    return _merge(clips)[:3]


def _recovery_plan(pdf_page: Any, native: PageAnalysis, cells: Sequence[Cell], width: float, height: float,
                   engine: Any) -> Optional[_Recovery]:
    """Decide whether a page may be read with OCR, from facts that need no rendering.

    Text pages (bills, specifications, forms) never qualify. A page with title
    evidence qualifies only when a drawing-title or sheet-number field of its
    title block is empty and an image lies where the value is written.
    """
    words = sum(len(cell.text.split()) for cell in cells)
    base = {"page": pdf_page, "identity": _page_identity(pdf_page), "engine": engine, "cells": list(cells), "words": words}
    if _has_title_evidence(native):
        if native.title_block is None or (any(c.kind == "label" and c.score > 0 for c in native.candidates) and native.sheet_numbers):
            return None
        images = _page_images(pdf_page, width, height)
        clips = _field_clips(cells, native, images, width, height) if images else []
        return _Recovery(**base, images=images, field_clips=clips) if clips else None
    images = _page_images(pdf_page, width, height)
    cover = _cover([image.box for image in images], (0.0, 0.0, width, height))
    sparse = words < _OCR_MIN_WORDS
    drawing_sized = width * height >= _DRAWING_SHEET_AREA
    in_band = any(_panel(image, width, height) and _area(_intersect(image.box, band)) > 0
                  for image in images for band in _bands(width, height))
    raster = cover >= 0.25 or (drawing_sized and in_band)
    vector = False
    if sparse:
        if cover < 0.05 and _vector_paths(pdf_page) < 50:
            return None  # a blank page
    else:
        paths = _vector_paths(pdf_page)
        vector = paths >= 1000 or (drawing_sized and paths >= 400)
    if not (sparse or raster or vector):
        return None
    return _Recovery(**base, images=images, cover=cover, sparse=sparse, raster=raster, vector=vector)


def analyse_page(pdf_page: Any, page_no: int, *, spans: Optional[Sequence[Dict[str, Any]]] = None,
                 ocr_engine: Any = None, allow_ocr: bool = True) -> PageAnalysis:
    """Native evidence of one PyMuPDF page. ``spans`` reuses text already extracted from the page.

    No OCR runs here. When the native text cannot answer and the page is a
    drawing (no text layer, a raster sheet, a raster title block or a heavily
    vector-drawn sheet), the analysis carries a recovery plan, and
    ``resolve_document`` reads the planned regions once the document's other
    sheets have shown where its title blocks are. Text pages are never OCR'd.
    """
    width, height = _visual_size(pdf_page)
    cells = cells_from_spans(spans if spans is not None else page_spans(pdf_page))
    native = analyse_cells(cells, width, height, page_no, "native")
    if allow_ocr and (ocr_engine is not None or ocr_available()):
        native.recovery = _recovery_plan(pdf_page, native, cells, width, height, ocr_engine)
    return native


# ---------------------------------------------------------------------------
# OCR recovery (targeted regions, cross-sheet)
# ---------------------------------------------------------------------------


def _same_size(a: Tuple[float, float], b: Tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) <= 0.02 * a[0] and abs(a[1] - b[1]) <= 0.02 * a[1]


def _learned_regions(pages: Sequence[PageAnalysis]) -> List[Tuple[Tuple[float, float], Box, int]]:
    """Title-block regions that native text demonstrates, per sheet size: ((width, height), relative box, sheets).

    Sibling sheets only say where to look; the text read there is the page's
    own, and it still has to be bound by the page's own field labels. Linear in
    the number of sheets: boxes are grouped by size and by position cell.
    """
    groups: List[Tuple[Tuple[float, float], List[Box]]] = []
    for page in pages:
        if page.title_block is None or page.source != "native" or page.width <= 0 or page.height <= 0:
            continue
        size = (page.width, page.height)
        box = _rel(page.title_block, page.width, page.height)
        for group_size, boxes in groups:
            if _same_size(group_size, size):
                boxes.append(box)
                break
        else:
            groups.append((size, [box]))
    out = []
    for size, boxes in groups:
        keys = [tuple(round(v * 20) for v in box) for box in boxes]  # 5 % position cells
        counts = Counter(keys)
        best = max(counts.values())
        winners = [key for key, count in counts.items() if count == best]
        members = [box for box, key in zip(boxes, keys)
                   if any(max(abs(a - b) for a, b in zip(key, winner)) <= 1 for winner in winners)]
        pad = 0.015
        region = _bounds(members)
        region = (max(0.0, region[0] - pad), max(0.0, region[1] - pad), min(1.0, region[2] + pad), min(1.0, region[3] + pad))
        if _area(region) <= 0.35:  # a region that vague says nothing about where the block is
            out.append((size, region, len(members)))
    return out


def _live_page(plan: _Recovery, opened: Dict[str, Any]) -> Any:
    """The plan's page, re-opened from its file if its document has since been closed."""
    page = plan.page
    try:
        if page is not None and page.parent is not None and not page.parent.is_closed:
            page.rect  # noqa: B018 - raises once the document is gone
            return page
    except Exception:
        pass
    if plan.identity is None:
        return None
    path, size, mtime, index = plan.identity
    try:
        stat = os.stat(path)
        if (stat.st_size, stat.st_mtime_ns) != (size, mtime):
            return None  # the file changed after it was analysed: nothing read now belongs to that analysis
        doc = opened.get(path)
        if doc is None:
            import fitz

            doc = opened[path] = fitz.open(path)
        return doc.load_page(index)
    except Exception:
        return None


_SIBLING_REGION = "title-block region of sibling sheets"


def _extensions(clip: Box, labels: Sequence[Cell], width: float, height: float) -> List[Box]:
    """Strips beyond the edges of a region read that the title-block labels read in it crowd against."""
    if not labels:
        return []
    x0, y0, x1, y1 = clip
    near_x, near_y, grow_x, grow_y = 0.015 * width, 0.015 * height, 0.6 * (x1 - x0), 0.6 * (y1 - y0)
    out: List[Box] = []
    if max(c.y1 for c in labels) >= y1 - near_y and y1 < height - 1:
        out.append((x0, y1, x1, min(height, y1 + grow_y)))
    if min(c.y0 for c in labels) <= y0 + near_y and y0 > 1:
        out.append((x0, max(0.0, y0 - grow_y), x1, y0))
    if max(c.x1 for c in labels) >= x1 - near_x and x1 < width - 1:
        out.append((x1, y0, min(width, x1 + grow_x), y1))
    if min(c.x0 for c in labels) <= x0 + near_x and x0 > 1:
        out.append((max(0.0, x0 - grow_x), y0, x0, y1))
    return out


def _recovery_steps(plan: _Recovery, width: float, height: float,
                    region: Optional[Box]) -> List[Tuple[str, List[Tuple[Box, Optional[int]]]]]:
    """Regions to read, most targeted first: (strategy, [(region, dpi)]). A dpi of None is the page default."""
    if plan.field_clips:
        return [("empty title-block field over an image",
                 [(clip, _image_dpi(clip, plan.images, _REGION_DPI, _REGION_MAX_PIXELS)) for clip in plan.field_clips])]
    steps: List[Tuple[str, List[Tuple[Box, Optional[int]]]]] = []
    if region is not None:
        box = (region[0] * width, region[1] * height, region[2] * width, region[3] * height)
        if plan.raster and not (plan.vector or plan.sparse):
            under = [image for image in plan.images if _area(_intersect(image.box, box)) > 0]
            if under and _cover([image.box for image in under], box) >= 0.3:
                clip = _intersect(box, _bounds([image.box for image in under]))
                steps.append((_SIBLING_REGION, [(clip, _image_dpi(clip, under, _REGION_DPI, _REGION_MAX_PIXELS))]))
        else:
            steps.append((_SIBLING_REGION, [(box, _dpi_for(_area(box), _REGION_DPI, _REGION_MAX_PIXELS))]))
    if plan.raster and not plan.sparse:  # a sheet without text is read whole below
        clips = []
        bands = _bands(width, height)
        # A pasted panel in a band is read whole; a raster sheet (or its tiles) only inside the bands.
        def tile(image: _Image) -> bool:
            return _sheet_image(image, width, height) or (plan.cover >= 0.25 and _area(image.box) >= 0.05 * width * height)

        panels = [image for image in plan.images if not tile(image) and _panel(image, width, height)
                  and any(_area(_intersect(image.box, band)) > 0 for band in bands)]
        for image in panels[:4]:
            clips.append((image.box, _image_dpi(image.box, [image], _REGION_DPI, _REGION_MAX_PIXELS)))
        for band in bands:
            tiles = [image for image in plan.images if tile(image) and _area(_intersect(image.box, band)) > 0]
            if tiles:
                clip = _intersect(band, _bounds([image.box for image in tiles]))
                clips.append((clip, _image_dpi(clip, tiles, _BAND_IMAGE_DPI, _BAND_IMAGE_MAX_PIXELS)))
        if clips:
            steps.append(("image in the title-block band", clips))
    if plan.vector:
        steps.append(("title-block edge band", [(band, None) for band in _bands(width, height)]))
    if plan.sparse:
        steps.append(("whole sheet (no text layer)", [((0.0, 0.0, width, height), None)]))
    return steps


def _new_cells(read: Sequence[Cell], known: Sequence[Cell]) -> List[Cell]:
    """OCR cells not already present: text that exists natively, or was read in an earlier region, wins."""
    def clash(cell: Cell, other: Cell) -> bool:
        return (other.x0 - 1 <= cell.xc <= other.x1 + 1 and other.y0 - 1 <= cell.yc <= other.y1 + 1) or \
               (cell.x0 <= other.xc <= cell.x1 and cell.y0 <= other.yc <= cell.y1)

    return [cell for cell in read if not any(clash(cell, other) for other in known)]


def _compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(text or "").upper())


def _edits_within(value: str, text: str) -> int:
    """Fewest edits turning ``value`` into some stretch of ``text`` (approximate substring match)."""
    previous = [0] * (len(text) + 1)
    for i, char in enumerate(value, 1):
        current = [i] + [0] * len(text)
        for j, other in enumerate(text, 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (char != other))
        previous = current
    return min(previous)


def _read_again(pdf_page: Any, engine: Any, box: Box, text: str, width: float, height: float,
                *, code: bool) -> Tuple[bool, str]:
    """Read one value's own box again at another resolution: (the reads agree, second read).

    A code (sheet number) must be read again exactly, as whole words. Words (a
    title) may differ by a stray mark, one edit per 12 letters: ruling lines round
    a field read as marks.
    """
    x0, y0, x1, y1 = box[0] * width, box[1] * height, box[2] * width, box[3] * height
    # A margin round the value: OCR detection garbles text that touches the edge of its image.
    pad = max(6.0, 0.5 * min(y1 - y0, 14.0))
    clip = (max(0.0, x0 - pad), max(0.0, y0 - pad), min(width, x1 + pad), min(height, y1 + pad))
    cells = ocr_cells(pdf_page, engine, clip, dpi=_dpi_for(_area(clip), _CHECK_DPI, _CHECK_MAX_PIXELS))
    second = _clean(" ".join(c.text for c in _reading_order(cells)))  # the engine only sees the clip
    value = _compact(text)
    if not value:
        return False, second
    if code:  # the whole code, as whole words of the second read: "A-201" is not read again in "A-2011"
        words = re.split(r"[\s:;]+", second)  # a colon or semicolon is never part of a sheet number
        return any(_compact(" ".join(words[i:j])) == value for i in range(len(words)) for j in range(i + 1, len(words) + 1)), second
    return _edits_within(value, _compact(second)) <= max(1, len(value) // 12), second


def _reading_order(cells: Sequence[Cell]) -> List[Cell]:
    """Cells line by line from the top, each line left to right."""
    lines: List[List[Cell]] = []
    for cell in sorted(cells, key=lambda c: c.yc):
        if lines and abs(cell.yc - median(c.yc for c in lines[-1])) <= 0.5 * max(cell.height, max(c.height for c in lines[-1])):
            lines[-1].append(cell)
        else:
            lines.append([cell])
    return [cell for line in lines for cell in sorted(line, key=lambda c: c.x0)]


def _corroborate(pdf_page: Any, engine: Any, analysis: PageAnalysis, info: Dict[str, Any]) -> None:
    """Accept a value that only OCR supplies once a second, independent read of it agrees.

    Every drawing title or sheet number bound from OCR text is read again on its
    own, at another resolution. Small or poor lettering reads differently from
    one read to the next; a value whose reads disagree is not accepted. Two reads
    that make the same mistake still agree, so this narrows OCR error; it cannot
    remove it.
    """
    checks = []
    for candidate in analysis.candidates:
        if candidate.kind == "label" and candidate.score > 0 and _OCR_NOTE in candidate.reason:
            agree, second = _read_again(pdf_page, engine, candidate.box, candidate.text, analysis.width, analysis.height, code=False)
            checks.append({"field": "title", "value": candidate.text, "second_read": second, "agree": agree})
            if not agree:
                candidate.score, candidate.rejected = 0.0, "a second OCR read of it disagrees"
    numbers, boxes = [], []
    for (value, how), box in zip(analysis.sheet_numbers, analysis.sheet_number_boxes):
        if how.endswith(_OCR_NOTE):
            agree, second = _read_again(pdf_page, engine, box, value, analysis.width, analysis.height, code=True)
            checks.append({"field": "sheet_number", "value": value, "second_read": second, "agree": agree})
            if not agree:
                continue
        numbers.append((value, how))
        boxes.append(box)
    analysis.sheet_numbers, analysis.sheet_number_boxes = numbers, boxes
    if checks:
        info["checks"] = checks


def _recover_page(page: PageAnalysis, region: Optional[Box], opened: Dict[str, Any]) -> PageAnalysis:
    """Read a page's planned regions in order until its title-block fields bind a title or sheet number.

    When a read shows a title block whose drawing-title or sheet-number value
    lies outside what was read, that field's value area is read next. Reading
    stops once a title or sheet number is bound, or once the title block shows
    both fields and they are empty.
    """
    plan = page.recovery
    width, height = page.width, page.height
    info: Dict[str, Any] = {"native_words": plan.words, "raster_cover": round(plan.cover, 2),
                            "images": [[round(v, 3) for v in _rel(image.box, width, height)] for image in plan.images[:4]],
                            "reads": []}
    if region is not None:
        info["sibling_region"] = [round(v, 3) for v in region]
    pdf_page = _live_page(plan, opened)
    if pdf_page is None:
        info["result"] = "the document could not be re-read"
        return replace(page, recovery=None, ocr=info)
    whole = (0.0, 0.0, width, height)
    steps = _recovery_steps(plan, width, height, region)
    read: List[Box] = []
    found: List[Cell] = []
    best: Optional[Tuple[PageAnalysis, str]] = None
    region_clip: Optional[Box] = None
    followed = extended = False
    index = 0
    while index < len(steps):
        strategy, clips = steps[index]
        index += 1
        fresh = False
        for clip, dpi in clips:
            if _area(clip) <= 0 or (read and _cover(read, clip) >= 0.7):
                continue  # already read (a sibling region inside a band, a band inside the whole sheet)
            lines = ocr_cells(pdf_page, plan.engine, None if clip == whole else clip, dpi=dpi)
            if strategy == _SIBLING_REGION:
                region_clip = clip
            read.append(clip)
            info["reads"].append({"strategy": strategy, "region": [round(v, 3) for v in _rel(clip, width, height)],
                                  "dpi": dpi, "lines": len(lines)})
            found.extend(_new_cells(lines, plan.cells + found))
            fresh = True
        if not fresh or not found:
            continue
        combined = analyse_cells(plan.cells + found, width, height, page.page_no, "native+ocr" if plan.cells else "ocr")
        title, number = _bound(combined)
        if plan.field_clips:
            had_title, had_number = _bound(page)
            if (title and not had_title) or (number and not had_number):
                best = (combined, strategy)
            continue
        if combined.title_block is None and not (title or number):
            continue  # OCR showed no title-block structure of its own
        best = (combined, strategy)
        if title and number:
            break
        seen = {item[0] for item in combined.layout}
        if not extended and region_clip is not None and combined.title_block is not None and                 ((not title and "title" not in seen) or (not number and "sheet_number" not in seen)):
            # A sibling with another layout: the block runs past the region read, and a field was not seen.
            extended = True
            labels = [label.cell for label in (parse_label(cell) for cell in plan.cells + found)
                      if label is not None and _inside(label.cell, combined.title_block)]
            grow = [box for box in _extensions(region_clip, labels, width, height) if _cover(read, box) < 0.7]
            if grow:
                steps.insert(index, ("title block continued past the region read",
                                     [(box, _dpi_for(_area(box), _REGION_DPI, _REGION_MAX_PIXELS)) for box in grow]))
                continue
        if not followed and combined.title_block is not None:
            followed = True
            zones = [zone for zone in _merge(_empty_field_zones(plan.cells + found, combined, width, height)) if _cover(read, zone) < 0.7]
            if zones:
                steps.insert(index, ("value area of a title-block field read with OCR",
                                     [(zone, _dpi_for(_area(zone), _REGION_DPI, _REGION_MAX_PIXELS)) for zone in zones[:3]]))
                continue
        if title or number or (followed and {"title", "sheet_number"} <= {item[0] for item in combined.layout}):
            break
    if best is not None:
        combined, strategy = best
        _corroborate(pdf_page, plan.engine, combined, info)
        title, number = _bound(combined)
        info["strategy"] = strategy
        info["result"] = ("title-block evidence read with OCR" if title or number else
                          "title block read with OCR; no drawing title or sheet number is bound to its fields")
        combined.ocr = info
        return combined
    if plan.sparse and found:
        # A sheet without a text layer is its OCR text, even when that text holds no title evidence.
        combined = analyse_cells(plan.cells + found, width, height, page.page_no, "native+ocr" if plan.cells else "ocr")
        info["result"] = "no title-block evidence in the text read"
        combined.ocr = info
        return combined
    info["result"] = "no title-block evidence in the regions read" if info["reads"] else "no region to read"
    return replace(page, recovery=None, ocr=info)


def _recover_document(pages: Sequence[PageAnalysis]) -> List[PageAnalysis]:
    """Read the planned OCR regions of the pages that need them, using regions their siblings demonstrate."""
    todo = [index for index, page in enumerate(pages) if page.recovery is not None]
    if not todo:
        return list(pages)
    regions = _learned_regions(pages)
    out = list(pages)
    opened: Dict[str, Any] = {}
    try:
        for index in todo:
            page = pages[index]
            region = next((box for size, box, _count in regions if _same_size(size, (page.width, page.height))), None)
            try:
                out[index] = _recover_page(page, region, opened)
            except Exception:
                out[index] = replace(page, recovery=None, ocr={"result": "OCR recovery failed"})
    finally:
        for doc in opened.values():
            try:
                doc.close()
            except Exception:
                pass
    return out


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
    """Choose each page's title and sheet number using the evidence of all pages of its document.

    Pages that carry an OCR recovery plan are read first, at the title-block
    region their sibling sheets demonstrate when there is one.
    """
    pages = _recover_document(pages)
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
            if page.ocr.get("reads"):
                reason += f"; OCR read {len(page.ocr['reads'])} region(s): {page.ocr.get('result', '')}"
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
            elif any(check["field"] == "sheet_number" and not check["agree"] for check in page.ocr.get("checks", [])):
                sheet_source = "not accepted: a second OCR read of the sheet number disagrees"
        results.append(PageTitle(
            page_no=page.page_no, title=title, confidence=confidence, source=source, region=region, reason=reason,
            sheet_number=sheet_number, sheet_number_source=sheet_source, text_source=page.source,
            candidates=[c.as_dict() for c in sorted(candidates, key=lambda c: -c.score)], ocr=page.ocr,
        ))
    return results


def resolve_page(pdf_page: Any, page_no: int = 1, **kwargs: Any) -> PageTitle:
    return resolve_document([analyse_page(pdf_page, page_no, **kwargs)])[0]


def display_title(meta: Dict[str, Any], page_no: int, page_label: str = "") -> str:
    """What to show for a page: its title, else its sheet number, else a neutral page identifier."""
    if meta.get("title_authority"):
        return str(meta.get("title") or meta.get("sheet_number") or f"Page {int(page_no)}")
    return str(meta.get("title") or page_label or f"Page {int(page_no)}")
