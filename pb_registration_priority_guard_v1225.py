"""v1.2.25 priority guard for architectural sheet headings.

The title-block detector is primary.  This guard strengthens the text-only fallback
used during early indexing: a standalone sheet heading (e.g. PARTITION PLAN) beats
multiple lines that merely say REFER/SEE ELEVATION or SECTION.
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

import pb_page_registration_v1225 as registration

_VERSION = "1.2.25"
_REFERENCE_WORDS = ("refer ", "refer to", "see ", "referenced", "detail ", "matchline", "keynote")
_HEADING_RULES = (
    ("Reflected Ceiling Plan", ("reflected ceiling plan", "reflected ceiling", "rcp")),
    ("Finishes Schedule", ("finish schedule", "finishes schedule", "finishing schedule", "material schedule", "colour schedule", "color schedule", "paint schedule")),
    ("Door / Window Schedule", ("door schedule", "window schedule", "door and window schedule")),
    ("Floor Plan", ("partition plan", "floor plan", "unit plan", "apartment plan", "general arrangement", "ga plan", "tenancy plan")),
    ("Roof Plan", ("roof plan",)),
    ("Elevation", ("external elevations", "external elevation", "building elevations", "building elevation", "north elevation", "south elevation", "east elevation", "west elevation")),
    ("Section", ("building sections", "building section", "wall sections", "wall section", "cross section")),
    ("Render / Artist's Impression", ("artist's impression", "artists impression", "artist impression", "3d render", "perspective")),
)
_BASE_WEIGHTED_PAGE_TYPE = registration.weighted_page_type


def _norm_line(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip().lower()


def _is_reference_line(line: str) -> bool:
    low = _norm_line(line)
    if any(low.startswith(token) for token in _REFERENCE_WORDS):
        return True
    return any(token in low[:24] for token in ("refer to ", "see drawing", "see elevation", "see section"))


def _line_heading_types(line: str) -> List[Tuple[str, str]]:
    """Heading types on one line. A shorter phrase inside a longer one does not count."""
    matched: List[Tuple[str, str]] = []
    for page_type, phrases in _HEADING_RULES:
        for phrase in phrases:
            if phrase == "rcp":
                present = re.search(r"\brcp\b", line) is not None
            else:
                present = phrase in line
            if present:
                matched.append((page_type, phrase))
    return [
        (page_type, phrase)
        for page_type, phrase in matched
        if not any(phrase != other and phrase in other for _page_type, other in matched)
    ]


def strong_heading_type(text: Any) -> Tuple[str, str]:
    """Return a sheet type only when every concise heading line agrees.

    Two different heading types abstain. Reading order is not a winner.
    """
    found: List[Tuple[str, str]] = []
    for raw in str(text or "").splitlines():
        line = str(raw).strip()
        low = _norm_line(line)
        if not low or len(low) > 120 or _is_reference_line(low):
            continue
        types = {page_type for page_type, _phrase in _line_heading_types(low)}
        if len(types) > 1:
            return "", ""
        if len(types) == 1:
            found.append((next(iter(types)), line))
    names = {page_type for page_type, _line in found}
    if len(names) != 1:
        return "", ""
    page_type = next(iter(names))
    heading = next(line for found_type, line in found if found_type == page_type)
    return page_type, heading


def weighted_page_type(full_text: Any, file_name: Any = "", title_block: Any = ""):
    base_type, confidence, evidence = _BASE_WEIGHTED_PAGE_TYPE(full_text, file_name, title_block)
    # A title block that names two sheet types has already abstained. Do not
    # replace that with the first heading found in the page body.
    if evidence == "competing title block headings":
        return base_type, confidence, evidence
    # Native title-block evidence remains strongest and already receives a large
    # score in the base classifier. Only improve the fallback when the concise
    # headings agree.
    title_type, title_line = strong_heading_type(title_block)
    if title_type:
        return title_type, max(int(confidence), 94), f"title block heading: {title_line}"
    if evidence == "competing page headings":
        return base_type, confidence, evidence
    heading_type, heading_line = strong_heading_type(full_text)
    if heading_type:
        return heading_type, max(int(confidence) if heading_type == base_type else 0, 84), f"page heading: {heading_line}"
    return base_type, confidence, evidence


def classify_page(text: str, file_name: str, page_no: int):
    page_type, _confidence, _evidence = weighted_page_type(text, file_name, "")
    return page_type, f"Page {int(page_no)}"


def apply(app: Any) -> None:
    if getattr(app, "_pb_registration_priority_guard_v1225_applied", False):
        return
    app._pb_registration_priority_guard_v1225_applied = True
    registration._pb_v1225_base_weighted_page_type = _BASE_WEIGHTED_PAGE_TYPE
    registration.weighted_page_type = weighted_page_type
    registration.classify_page = classify_page
    app.classify_page = classify_page
