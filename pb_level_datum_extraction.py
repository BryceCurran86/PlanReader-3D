"""pb_level_datum_extraction.py — Roof/Floor Level Datum Parsing (Phase F.14).

Sections and elevations conventionally annotate vertical datums directly on
the drawing: a roof/ceiling/beam level and a floor/ground level, each given
as a signed value relative to a shared reference (e.g. "Roof Level +3,325",
"Ground floor +175"). Together, two such datums are a real figured
measurement of wall/room height — genuine drawing evidence, not a
convenience assumption.

This module only recognizes that annotation pattern (a level-type label
immediately followed by a signed numeric value) and turns it into
pb_dimension_graph_constraint_engine.LevelMarker records, which
resolve_wall_height() (F.13, already merged) turns into a resolved height —
or leaves unresolved when the evidence does not constrain it. Nothing here
invents a value: a page with no level annotation yields no markers, and no
default height is ever substituted.

Deliberately label-then-value only, never value-then-label: a value that
merely precedes a level label somewhere later in flat reading order is not
reliably the value *for* that label — real drawings pack unrelated
dimension strings and level annotations onto the same line, and a
value-then-label scan was found (against real project PDFs) to attribute
an unrelated nearby dimension chain value to the label purely because it
happened to sit right before it in text order. Every genuine occurrence
observed in real drawings so far is label-then-value; requiring that
direction only trades recall for correctness deliberately.

Number format follows the same convention already used throughout this
extractor's other dimension parsing (pb_dimension_graph_constraint_engine.
parse_dimension_tokens_from_text, GenericPlanReaderExtractor's own
parsed_dims_m): a comma is a thousands separator on a millimetre value
(e.g. "3,325" = 3325mm), never a decimal point. A level value additionally
carries an explicit sign relative to the datum (e.g. "+3,325", "-150"). A
level string that does not match this convention (a bare decimal like
"+3.325") is deliberately not recognized here rather than guessed at.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

from pb_dimension_graph_constraint_engine import LevelMarker

# marker_type -> the label phrase(s) that identify that datum. Kept as
# separate keywords (not lumped into one "roof-like"/"floor-like" pattern)
# so the resulting LevelMarker.marker_type reflects which label was
# actually printed on the drawing, not a guess.
_LEVEL_LABELS: Dict[str, Tuple[str, ...]] = {
    "roof": (r"roof\s*level",),
    "ceiling": (r"ceiling\s*level",),
    "beam": (r"beam\s*level",),
    "floor": (r"floor\s*level",),
    # "ground floor" is excluded when followed by "plan" -- "GROUND FLOOR
    # PLAN" is a view title (like "ROOF PLAN"), not a level datum.
    "ground": (r"ground\s*level", r"ground\s*floor(?:\s*level)?(?!\s*plan\b)"),
}

# The sign is mandatory, not optional (F.23A): a level datum is always
# stated relative to a reference in this drafting convention -- every
# genuine occurrence found in real drawings so far carries an explicit
# "+"/"-". A bare, unsigned number is far more likely to be unrelated
# noise sitting next to the label by coincidence -- found against a real
# false positive: "Roof Level 9'-6\" above datum" (imperial feet-inches
# notation) matched the bare "9" as if it were a signed level value.
# The trailing negative lookahead rejects a decimal-point value (e.g.
# "+3.325") outright rather than silently mis-parsing its leading digits
# (e.g. capturing just "+3") -- a format this module does not recognize
# must yield no marker, never a wrong one.
_LEVEL_VALUE = r"([+\-]\d{1,3}(?:,\d{3})?)(?!\d)(?!\.\d)"

# Reverse CAD annotations on some drawings use ungrouped four-digit
# millimetre values (for example "+3000 ROOF LEVEL"). Keep this broader
# spelling local to the reverse-only parser so the established label-first
# grammar and its false-positive boundary remain unchanged.
_REVERSE_LEVEL_VALUE = r"([+\-](?:\d{1,4}|\d{1,3},\d{3}))(?!\d)(?!\.\d)"


def _parse_level_value_m(raw: str) -> float:
    """Convert a signed, comma-grouped millimetre level string to metres."""
    stripped = raw.strip()
    sign = -1.0 if stripped.startswith("-") else 1.0
    digits = stripped.lstrip("+-").replace(",", "")
    return sign * float(digits) / 1000.0


def find_level_markers(
    page_text: str,
    *,
    source_page: int,
    view_id: str = "",
) -> List[LevelMarker]:
    """Parse roof/ceiling/beam/floor/ground level datum annotations
    ("Roof Level +3,325", "Ground floor +175") from one page's text.
    Returns one LevelMarker per match; a page with no such annotation
    returns an empty list."""
    norm = re.sub(r"\s+", " ", page_text)
    markers: List[LevelMarker] = []
    seq = 0

    # Some CAD/PDF exports print a signed datum before its label, and may
    # split one annotation across two adjacent text lines, e.g.
    # "+3000 ROOF" / "LEVEL". Accept this reverse convention only when
    # the complete one-line or adjacent-two-line candidate FULL-MATCHES one
    # signed value plus one recognized level label. For a wrapped pair the
    # first line must already contain the signed value plus at least the first
    # label token; this prevents an unrelated standalone dimension on the
    # previous line from being attached to a following level label.
    raw_lines = [
        re.sub(r"\s+", " ", raw_line).strip()
        for raw_line in page_text.splitlines()
        if re.sub(r"\s+", " ", raw_line).strip()
    ]
    reverse_candidates: List[str] = []
    for index, line in enumerate(raw_lines):
        reverse_candidates.append(line)
        if (
            index + 1 < len(raw_lines)
            and re.match(r"^[+\-](?:\d{1,4}|\d{1,3},\d{3})\s+[A-Za-z]", line)
        ):
            reverse_candidates.append(f"{line} {raw_lines[index + 1]}")

    seen_reverse: set[Tuple[str, float, str]] = set()
    for candidate in reverse_candidates:
        for marker_type, label_patterns in _LEVEL_LABELS.items():
            for label_pat in label_patterns:
                reverse = re.fullmatch(
                    rf"{_REVERSE_LEVEL_VALUE}\s*:?\s*{label_pat}",
                    candidate,
                    re.I,
                )
                if reverse is None:
                    continue
                level_m = _parse_level_value_m(reverse.group(1))
                dedupe_key = (marker_type, level_m, candidate.casefold())
                if dedupe_key in seen_reverse:
                    continue
                seen_reverse.add(dedupe_key)
                markers.append(LevelMarker(
                    marker_id=f"level_p{source_page}_{marker_type}_{seq}",
                    level_m=level_m,
                    raw_text=candidate,
                    marker_type=marker_type,
                    view_id=view_id,
                    source_page=source_page,
                    scope_id=None,
                ))
                seq += 1

    for marker_type, label_patterns in _LEVEL_LABELS.items():
        for label_pat in label_patterns:
            # Only ":" is an optional label/value separator -- "-" is not,
            # since it would otherwise be ambiguously consumed as that
            # separator instead of as a negative value's sign.
            for m in re.finditer(rf"{label_pat}\s*:?\s*{_LEVEL_VALUE}", norm, re.I):
                markers.append(LevelMarker(
                    marker_id=f"level_p{source_page}_{marker_type}_{seq}",
                    level_m=_parse_level_value_m(m.group(1)),
                    raw_text=m.group(0).strip(),
                    marker_type=marker_type,
                    view_id=view_id,
                    source_page=source_page,
                    scope_id=None,
                ))
                seq += 1

    return markers
