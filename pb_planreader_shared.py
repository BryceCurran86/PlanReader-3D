"""Shared utilities for PB PlanReader.

Consolidates duplicated logic across the codebase: scale-ratio parsing,
dimension extraction, and page classification.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Scale-ratio parsing (was duplicated in 4 files)
# ---------------------------------------------------------------------------
SCALE_RE = re.compile(r"(?<!\d)1\s*:\s*(\d{2,4})(?!\d)", re.IGNORECASE)


def _scale_denominators(text: str) -> set[int]:
    return {int(match.group(1)) for match in SCALE_RE.finditer(str(text or ""))}


def extract_scale_ratio(text: str) -> Optional[int]:
    """Return one scale denominator. Two different denominators abstain."""
    found = _scale_denominators(text)
    if len(found) != 1:
        return None
    return next(iter(found))


# ---------------------------------------------------------------------------
# Dimension extraction (consolidated from auto_geometry + plan_read_engine)
# ---------------------------------------------------------------------------
DIM_RE = re.compile(
    r"(?<![:\d])(?P<num>\d{2,5}(?:\.\d{1,3})?)\s*(?P<unit>mm|m)?(?!\s*[:\d])",
    re.IGNORECASE,
)


def dimension_value_m(raw: str) -> Optional[float]:
    """Parse a dimension string (e.g. '3600', '3.6m', '1200mm') into metres.

    Returns None if the value is outside a reasonable architectural range.
    """
    compact = re.sub(r"\s+", "", str(raw or "")).lower()
    try:
        if compact.endswith("mm"):
            value = float(compact[:-2]) / 1000.0
            return value if 0.05 <= value <= 200.0 else None
        if compact.endswith("m") and not compact.endswith("mm"):
            value = float(compact[:-1])
            return value if 0.05 <= value <= 200.0 else None
        # Bare numbers in millimetres (e.g. 3600, 1200)
        m = DIM_RE.fullmatch(compact)
        if m:
            value = float(m.group("num"))
            unit = str(m.group("unit") or "").lower()
            if unit == "mm" or (not unit and value >= 100):
                value /= 1000.0
            elif unit == "m":
                pass
            else:
                return None
            return value if 0.05 <= value <= 200.0 else None
    except (ValueError, TypeError):
        pass
    return None


# ---------------------------------------------------------------------------
# Page classification keywords (consolidated from 6 files)
# ---------------------------------------------------------------------------
_FLOOR_PLAN_KW = [
    "floor plan", "site plan", "ground floor", "first floor",
    "second floor", "roof plan", "basement plan",
    "upper floor", "lower floor",
]
_ELEVATION_KW = [
    "elevation", "external elevation", "internal elevation",
    "north elevation", "south elevation", "east elevation", "west elevation",
    "facade", "front elevation", "rear elevation", "side elevation",
]
_SECTION_KW = [
    "section", "cross section", "longitudinal section",
    "transverse section", "building section", "wall section",
]
_SCHEDULE_KW = [
    "schedule", "door schedule", "window schedule",
    "finishing schedule", "material schedule", "brick schedule",
    "specification", "colour schedule", "paint schedule",
]
_TITLE_KW = [
    "drawing register", "drawing index", "drawing schedule",
    "sheet index", "title sheet", "project information",
    "general notes", "location plan", "key plan", "site layout",
]
CEILING_KW = [
    "reflected ceiling plan", "rcp", "ceiling plan",
    "ceiling layout", "suspended ceiling",
]

# Drawing number pattern (consolidated from 3 files)
DRAWING_NUMBER_RE = re.compile(
    r"\b([A-Z]{1,3}\d{2,4}(?:[-/.][A-Z0-9]+)?)\b",
)


def _keyword_hit(text: str, keyword: str) -> bool:
    """Match a keyword as its own words, not as part of a longer word."""
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


def _reference_line(line: str) -> bool:
    return line.startswith(("refer ", "see ", "matchline ", "keynote "))


def _type_score(text: str, keywords: list[str]) -> int:
    """Count heading hits without letting a shorter phrase inflate a longer one."""
    hits = [keyword for keyword in keywords if _keyword_hit(text, keyword)]
    return sum(
        1
        for keyword in hits
        if not any(keyword != other and keyword in other for other in hits)
    )


def classify_page(text: str) -> str:
    """Classify a page from its own text.

    A tied top score abstains. The bare word ``title`` is not a sheet type.
    A keyword inside another word is not a hit, and a reference line does not vote.
    """
    kept: list[str] = []
    for raw in (text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip().lower()
        if line and not _reference_line(line):
            kept.append(line)
    body = "\n".join(kept)

    scores = {
        "Floor Plan": _type_score(body, _FLOOR_PLAN_KW),
        "Elevation": _type_score(body, _ELEVATION_KW),
        "Section": _type_score(body, _SECTION_KW),
        "Schedule": _type_score(body, _SCHEDULE_KW),
        "Title / Drawing Register": _type_score(body, _TITLE_KW),
        "Reflected Ceiling Plan": _type_score(body, CEILING_KW),
    }

    best_score = max(scores.values())
    if best_score <= 0:
        return "Other"
    winners = [name for name, score in scores.items() if score == best_score]
    if len(winners) != 1:
        return "Other"
    return winners[0]


def detect_scale_from_text(text: str) -> Optional[Dict[str, Any]]:
    """Find one scale ratio. Two different denominators abstain."""
    matches = list(SCALE_RE.finditer(str(text or "")))
    denominators = {int(match.group(1)) for match in matches}
    if len(denominators) != 1:
        return None
    ratio = next(iter(denominators))
    confidence = "high" if ratio in (50, 100, 200, 500, 1000) else "medium"
    return {
        "ratio": ratio,
        "denominator": ratio,
        "text": matches[0].group(0),
        "confidence": confidence,
    }


def detect_drawing_number(text: str) -> Optional[str]:
    """Return one drawing number. Two different numbers abstain."""
    found: Dict[str, str] = {}
    for match in DRAWING_NUMBER_RE.finditer(str(text or "")):
        token = match.group(1)
        found.setdefault(token.upper(), token)
    if len(found) != 1:
        return None
    return next(iter(found.values()))
