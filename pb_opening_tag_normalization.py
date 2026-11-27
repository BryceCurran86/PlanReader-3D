"""Generic opening tag normalization and explicit-tag parsing.

This module normalizes only identities that are explicitly documented in drawing
text or schedule cells. It deliberately does *not* infer W/D identities from
opening dimensions, expected quantities, benchmark IDs, project names, or BOQ
content. When multiple generic detectors agree on one identity, downstream
schedule reconciliation preserves the most complete evidence (count plus figured
dimensions) rather than allowing a higher-confidence count-only observation to
strip geometry.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

_UNICODE_DASH_TRANSLATION = str.maketrans({
    "\u2010": "-",  # hyphen
    "\u2011": "-",  # non-breaking hyphen
    "\u2012": "-",  # figure dash
    "\u2013": "-",  # en dash
    "\u2014": "-",  # em dash
    "\u2212": "-",  # minus sign
    "\u00a0": " ",  # nbsp
    "\u2009": " ",  # thin space
    "\u202f": " ",  # narrow nbsp
    "\u200b": "",   # zero-width space
    "\ufeff": "",   # BOM
})


def _normalize_unicode_tag_text(text: str) -> str:
    return unicodedata.normalize("NFKC", text).translate(_UNICODE_DASH_TRANSLATION)


@dataclass(frozen=True)
class NormalizedOpeningTag:
    tag: str
    trade_type: str
    raw_text: str


# Explicit documented identities accepted generically. Examples:
# W7, W-07, W 07, WINDOW 07, WIN-07, D12, D-12, DOOR 12, DR-12.
# A second numeric segment (for example D8-03-200 reinforcement notation)
# disqualifies the token instead of allowing the leading D8 to masquerade as
# a door identity.
_TAG_RE = re.compile(
    r"(?<![A-Za-z0-9])"
    r"(?P<prefix>WINDOW|WIN|W|DOOR|DR|D)"
    r"\s*[-_]?\s*"
    r"(?P<number>\d{1,3})"
    r"(?![A-Za-z0-9])"
    r"(?!\s*[-_]\s*\d)",
    re.IGNORECASE,
)


def normalize_opening_tag(text: str) -> Optional[NormalizedOpeningTag]:
    """Normalize one explicit window/door identity from *text*.

    Returns ``None`` when no explicit opening identity is present. Dimension
    strings alone never create a tag.
    """
    if not text:
        return None
    normalized_text = _normalize_unicode_tag_text(text)
    found: list[tuple[str, str, str]] = []
    for match in _TAG_RE.finditer(normalized_text):
        prefix = match.group("prefix").upper()
        number = int(match.group("number"))
        if number <= 0:
            continue
        if prefix in {"W", "WIN", "WINDOW"}:
            canonical, trade = f"W{number}", "windows"
        else:
            canonical, trade = f"D{number}", "doors"
        item = (canonical, trade, match.group(0))
        if item[:2] not in {(row[0], row[1]) for row in found}:
            found.append(item)
    if len(found) != 1:
        return None
    canonical, trade, raw = found[0]
    return NormalizedOpeningTag(tag=canonical, trade_type=trade, raw_text=raw)


def find_explicit_opening_tags(text: str) -> list[NormalizedOpeningTag]:
    """Return explicit documented opening identities in textual order."""
    if not text:
        return []
    normalized_text = _normalize_unicode_tag_text(text)
    out: list[NormalizedOpeningTag] = []
    for m in _TAG_RE.finditer(normalized_text):
        norm = normalize_opening_tag(m.group(0))
        if norm is not None:
            out.append(norm)
    return out


def opening_trade_from_tag(text: str) -> Optional[str]:
    norm = normalize_opening_tag(text)
    return norm.trade_type if norm else None


# Keep normalization evidence-only; geometry is never an identity source.
