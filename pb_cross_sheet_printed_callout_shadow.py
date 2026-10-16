"""Conservative *shadow-only* ledger of printed cross-sheet callouts.

Sheet identity remains with the title-block reader pb_page_title_authority.
This module never infers identity from arbitrary page words and never
registers walls, rooms, doors, finishes, dimensions or quantities. Existing
live pb_cross_sheet_callout_evidence calls remain unchanged.

Records source-printed "1/A-201" and "2/S-0.01" and conservatively reunites
literal slash-separated pieces that native text extraction split on exactly
the same producer-reported PDF line. Competing calls remain competing.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Any, Sequence

from pb_cross_sheet_callout_evidence import CalloutReferenceEvidence
from pb_page_title_authority import normalise_sheet_number

# A literal callout must have a printed slash and a sheet-letter prefix.
# Preserve spelling/punctuation: A201 is NOT an alias for A-201.
_PRINTED = re.compile(
    r"^(?P<mark>\d{1,3})/(?P<sheet>[A-Z]{1,4}-?\d{1,4}(?:\.\d{1,3})?)$",
    re.ASCII,
)


@dataclass(frozen=True)
class _Word:
    x0: float
    y0: float
    x1: float
    y1: float
    value: str
    block: int
    line: int
    index: int


def _word(raw: Sequence[Any]) -> _Word | None:
    try:
        x0, y0, x1, y1 = (float(raw[n]) for n in range(4))
        if not all(math.isfinite(n) for n in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
            return None
        return _Word(x0, y0, x1, y1, str(raw[4]).strip().upper(),
                     int(raw[5]), int(raw[6]), int(raw[7]))
    except (TypeError, ValueError, IndexError, OverflowError):
        return None


def _candidate(value: str, bbox: tuple[float, float, float, float], page_num: int):
    match = _PRINTED.fullmatch(value)
    if match is None:
        return None
    return CalloutReferenceEvidence(
        mark=match.group("mark"),
        referenced_sheet_code=normalise_sheet_number(match.group("sheet")),
        callout_bbox=bbox,
        source_page=int(page_num),
    )


def _same_literal_line(parts: Sequence[_Word]) -> bool:
    """A transcription condition, never proximity-based target election."""
    first = parts[0]
    for before, after in zip(parts, parts[1:]):
        if (before.block, before.line) != (first.block, first.line):
            return False
        if (after.block, after.line) != (first.block, first.line):
            return False
        if after.index != before.index + 1 or after.x0 < before.x0:
            return False
        if after.x0 - before.x1 > max(1.0, 0.35 * max(before.y1-before.y0, after.y1-after.y0)):
            return False
    return True


def find_printed_callout_candidates_shadow(page: Any, *, page_num: int) -> list[CalloutReferenceEvidence]:
    """Enumerate literal native tokens, retaining all independent rivals.

    A single word is sufficient for the compact spelling. Split recovery
    requires the extractor's own same block, line and adjacent word indices.
    Source words are neither edited nor assigned to construction objects.
    """
    words = [word for raw in page.get_text("words") if (word := _word(raw)) is not None]
    grouped: dict[tuple[int, int], list[_Word]] = {}
    for word in words:
        grouped.setdefault((word.block, word.line), []).append(word)
    found: set[CalloutReferenceEvidence] = set()
    for group in grouped.values():
        group.sort(key=lambda w: (w.index, w.x0, w.y0, w.value))
        for i in range(len(group)):
            for count in (1, 2, 3):
                parts = group[i:i + count]
                if len(parts) != count or (count > 1 and not _same_literal_line(parts)):
                    continue
                value = "".join(w.value for w in parts)
                bbox = (min(w.x0 for w in parts), min(w.y0 for w in parts),
                        max(w.x1 for w in parts), max(w.y1 for w in parts))
                candidate = _candidate(value, bbox, page_num)
                if candidate is not None:
                    found.add(candidate)
    return sorted(found, key=lambda c: (c.source_page, c.callout_bbox,
                                       c.mark, c.referenced_sheet_code))


def candidates_for_resolved_sheet_shadow(
    candidates: Sequence[CalloutReferenceEvidence], *, sheet_number: str,
) -> list[CalloutReferenceEvidence]:
    """Compare only to a caller-supplied *already title-field-resolved* code.

    The caller is responsible for title-block evidence and ambiguous OCR.
    A match here is a candidate, NEVER physical-object registration.
    """
    target = str(sheet_number or "").strip().upper()
    if not target or not re.fullmatch(r"[A-Z]{1,4}-?\d{1,4}(?:\.\d{1,3})?", target):
        return []
    target = normalise_sheet_number(target)
    return [item for item in candidates if item.referenced_sheet_code == target]


__all__ = ["find_printed_callout_candidates_shadow", "candidates_for_resolved_sheet_shadow"]
