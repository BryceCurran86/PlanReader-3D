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

_CALLOUT_RE = re.compile(r"^\s*(?P<mark>\d{1,3})\s*/\s*(?P<sheet>[A-Z]{1,4}\d{2,4})\s*$")
_SHEET_CODE_RE = re.compile(r"^\s*[A-Z]{1,4}\d{2,4}\s*$")


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


def find_callout_references(page: Any, *, page_num: int) -> List[CalloutReferenceEvidence]:
    """Find every ``<mark>/<sheet code>`` callout token printed on this page."""
    out: List[CalloutReferenceEvidence] = []
    for word in page.get_text("words"):
        text = str(word[4]).strip()
        match = _CALLOUT_RE.match(text)
        if match is None:
            continue
        out.append(
            CalloutReferenceEvidence(
                mark=match.group("mark"),
                referenced_sheet_code=match.group("sheet").upper(),
                callout_bbox=_word_bbox(word),
                source_page=page_num,
            )
        )
    return out


def find_unique_page_sheet_code(page: Any) -> Optional[str]:
    """Return this page's own sheet code (e.g. ``"A201"``) if unambiguous.

    Fails closed (returns ``None``) when zero or more than one distinct
    sheet-code-shaped token is printed on the page -- a page whose own
    identity is ambiguous cannot be a registration target.
    """
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
) -> Optional[CalloutReferenceEvidence]:
    """Return the one callout near ``geometry_bbox``, or ``None`` if zero/ambiguous."""
    geom_center = _bbox_center(geometry_bbox)
    candidates = [
        callout
        for callout in find_callout_references(page, page_num=page_num)
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
    "mark_appears_near_geometry",
]
