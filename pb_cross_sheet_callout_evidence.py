"""Source-backed cross-sheet callout reference evidence (PlanReader Item 32).

Resolves a real drafting cross-reference from one sheet to another: a
detail/section callout of the conventional ``<mark>/<sheet code>`` form
(e.g. ``"1/A201"``) printed near a physical element on a source page, whose
referenced sheet code matches the target page's own uniquely-identified
sheet code.

This is the only positive correspondence signal this module recognizes.
Same mark string, same caller-selected id, or per-page existence are never
sufficient by themselves -- see ``pb_cross_sheet_registration_authority``.

Ambiguity fails closed: more than one distinct sheet-code token on a page,
or more than one callout referencing the target sheet near the element,
resolves to ``None`` rather than guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, List, Optional, Sequence, Tuple

from pb_page_title_authority import PageTitle, normalise_sheet_number, sheet_number_shape

_CALLOUT_RE = re.compile(r"^\s*(?P<mark>\d{1,3})\s*/\s*(?P<sheet>[A-Z]{1,4}\d{2,4})\s*$")
_SHEET_CODE_RE = re.compile(r"^\s*[A-Z]{1,4}\d{2,4}\s*$")

# Opt-in shadow *callout* tokens only: not an independent sheet-identity rule.
# Hyphenated numbers/decimals must also pass the existing title authority's
# shape predicate. Ordinary letters/numbers and prose are not callouts.
_SHADOW_SHEET_RE = re.compile(r"[A-Z]{1,4}(?:\d{2,4}|-\d{1,4}(?:\.\d{1,3})?)")
_SHADOW_CALLOUT_RE = re.compile(
    r"^\s*(?P<mark>\d{1,3})\s*/\s*(?P<sheet>[A-Z]{1,4}(?:\d{2,4}|-\d{1,4}(?:\.\d{1,3})?))\s*$",
    re.IGNORECASE,
)
_SHADOW_MARK_RE = re.compile(r"\d{1,3}")



@dataclass(frozen=True)
class CalloutReferenceEvidence:
    """One real, printed cross-reference callout found on a source page."""

    mark: str
    referenced_sheet_code: str
    callout_bbox: Tuple[float, float, float, float]
    source_page: int


def _word_bbox(word: Sequence[Any]) -> Tuple[float, float, float, float]:
    return (float(word[0]), float(word[1]), float(word[2]), float(word[3]))


def _bbox_center(bbox: Sequence[float]) -> Tuple[float, float]:
    return (float(bbox[0]) + float(bbox[2])) / 2.0, (float(bbox[1]) + float(bbox[3])) / 2.0


def _shadow_sheet_code(raw: str) -> Optional[str]:
    """Recognize narrowly shaped printed sheet references, not page identity."""
    code = normalise_sheet_number(str(raw or "")).upper()
    if not _SHADOW_SHEET_RE.fullmatch(code) or not sheet_number_shape(code):
        return None
    return code


def _adjacent_callout_words(mark_word: Sequence[Any], sheet_word: Sequence[Any]) -> bool:
    """Accept nearby consecutive printed words, including stacked bubble text.

    Mere text extraction order is not enough: the two word rectangles must
    also form a compact horizontal or vertical pair, not words across a page.
    """
    mx0, my0, mx1, my1 = _word_bbox(mark_word)
    sx0, sy0, sx1, sy1 = _word_bbox(sheet_word)
    mh, sh = max(my1 - my0, 0.5), max(sy1 - sy0, 0.5)
    mcx, mcy = _bbox_center((mx0, my0, mx1, my1))
    scx, scy = _bbox_center((sx0, sy0, sx1, sy1))
    same_line = (
        abs(mcy - scy) <= 0.6 * max(mh, sh)
        and -1 <= sx0 - mx1 <= 2 * max(mh, sh)
    )
    stacked = (
        -1 <= sy0 - my1 <= 2 * max(mh, sh)
        and abs(mcx - scx) <= 0.5 * max(mx1 - mx0, sx1 - sx0) + 2
    )
    return bool(same_line or stacked)


def _combined_bbox(words: Sequence[Sequence[Any]]) -> Tuple[float, float, float, float]:
    rects = [_word_bbox(word) for word in words]
    return (
        min(box[0] for box in rects),
        min(box[1] for box in rects),
        max(box[2] for box in rects),
        max(box[3] for box in rects),
    )


def find_callout_references(
    page: Any, *, page_num: int, shadow_extended: bool = False
) -> List[CalloutReferenceEvidence]:
    """Find printed mark/sheet callouts.

    The default is the original exact single-token reader. Optional wider
    token forms are SHADOW ONLY; no production registration enables them.
    This reader never proves a target sheet's identity or an element match.
    """
    words = list(page.get_text("words"))
    out: List[CalloutReferenceEvidence] = []
    seen: set[tuple[str, str, Tuple[float, float, float, float]]] = set()

    def append(mark: str, sheet: str, members: Sequence[Sequence[Any]]) -> None:
        bbox = _combined_bbox(members)
        key = (mark, sheet, bbox)
        if key not in seen:
            seen.add(key)
            out.append(CalloutReferenceEvidence(mark, sheet, bbox, page_num))

    for word in words:
        text = str(word[4]).strip()
        match = _CALLOUT_RE.match(text)
        if match is not None:
            append(match.group("mark"), match.group("sheet").upper(), (word,))
        elif shadow_extended:
            match = _SHADOW_CALLOUT_RE.fullmatch(text)
            if match:
                code = _shadow_sheet_code(match.group("sheet"))
                if code is not None:
                    append(match.group("mark"), code, (word,))

    if not shadow_extended:
        return out

    # A split callout is at most [mark, sheet] or [mark, slash, sheet].
    # Adjacent words must be spatially compact, not just consecutive in a
    # page-wide OCR/text read. Do not infer a slash when text explicitly has
    # a different separator.
    for i, word in enumerate(words):
        mark = str(word[4]).strip()
        if not _SHADOW_MARK_RE.fullmatch(mark):
            continue
        if i + 1 >= len(words):
            continue
        nxt = words[i + 1]
        nxt_text = str(nxt[4]).strip()
        if nxt_text == "/":
            if i + 2 >= len(words):
                continue
            sheet_word = words[i + 2]
            if not (
                _adjacent_callout_words(word, nxt)
                and _adjacent_callout_words(nxt, sheet_word)
            ):
                continue
            members = (word, nxt, sheet_word)
        else:
            sheet_word = nxt
            members = (word, sheet_word)
        code = _shadow_sheet_code(str(sheet_word[4]).strip())
        if code is None or not _adjacent_callout_words(word, sheet_word) and len(members) == 2:
            continue
        append(mark, code, members)
    return out


def _bound_sheet_code(title: PageTitle) -> Optional[str]:
    """Only consume a title reader's accepted, field-bound sheet value."""
    if type(title) is not PageTitle or not title.sheet_number or not title.sheet_number_source:
        return None
    if title.sheet_number_source.startswith(("ambiguous:", "not accepted:")):
        return None
    return _shadow_sheet_code(title.sheet_number)


def find_unique_bound_target_page(
    page_titles: Sequence[PageTitle], referenced_sheet_code: str
) -> Optional[int]:
    """Shadow lookup from the existing title authority's document results.

    A stray free-text token cannot identify a sheet. No page, or multiple
    pages carrying the same bound sheet number, must remain unresolved.
    """
    code = _shadow_sheet_code(referenced_sheet_code)
    if code is None:
        return None
    matches = [
        title.page_no for title in page_titles
        if _bound_sheet_code(title) == code
    ]
    return matches[0] if len(matches) == 1 else None


def find_unique_page_sheet_code(page: Any, *, bound_title: Optional[PageTitle] = None) -> Optional[str]:
    """Return this page's sheet code when unambiguous.

    Default legacy behavior remains unchanged for production consumers.
    The opt-in bound_title path uses only the existing title-block reader's
    accepted page-local result, never a printed reference elsewhere on page.
    An absent/untrusted/mismatched binding abstains without text fallback.
    """
    if bound_title is not None:
        if type(bound_title) is not PageTitle or getattr(page, "number", None) != bound_title.page_no - 1:
            return None
        return _bound_sheet_code(bound_title)
    found: set[str] = set()
    for word in page.get_text("words"):
        text = str(word[4]).strip().upper().rstrip(".,:;")
        if _SHEET_CODE_RE.match(text):
            found.add(text)
    if len(found) != 1:
        return None
    return next(iter(found))


def find_callout_near_geometry(
    page: Any,
    *,
    page_num: int,
    geometry_bbox: Tuple[float, float, float, float],
    proximity_pt: float,
    shadow_extended: bool = False,
) -> Optional[CalloutReferenceEvidence]:
    """Return the one callout near geometry, or abstain if zero/ambiguous."""
    geom_center = _bbox_center(geometry_bbox)
    candidates = [
        callout
        for callout in find_callout_references(page, page_num=page_num, shadow_extended=shadow_extended)
        if math.hypot(
            _bbox_center(callout.callout_bbox)[0] - geom_center[0],
            _bbox_center(callout.callout_bbox)[1] - geom_center[1],
        )
        <= proximity_pt
    ]
    if len(candidates) != 1:
        return None
    return candidates[0]


def mark_appears_near_geometry(
    page: Any,
    *,
    mark: str,
    geometry_bbox: Tuple[float, float, float, float],
    proximity_pt: float,
) -> bool:
    """Return whether a standalone text token equal to ``mark`` is printed
    near ``geometry_bbox`` on this page -- the real target-side half of a
    detail/section callout bubble, proving THIS specific target element
    (not merely the sheet) is the one the source callout refers to.
    """
    wanted = str(mark or "").strip()
    if not wanted:
        return False
    geom_center = _bbox_center(geometry_bbox)
    for word in page.get_text("words"):
        text = str(word[4]).strip().rstrip(".,:;")
        if text != wanted:
            continue
        word_bbox = _word_bbox(word)
        if math.hypot(
            _bbox_center(word_bbox)[0] - geom_center[0],
            _bbox_center(word_bbox)[1] - geom_center[1],
        ) <= proximity_pt:
            return True
    return False


__all__ = [
    "CalloutReferenceEvidence",
    "find_callout_near_geometry",
    "find_callout_references",
    "find_unique_page_sheet_code",
    "find_unique_bound_target_page",
    "mark_appears_near_geometry",
]
