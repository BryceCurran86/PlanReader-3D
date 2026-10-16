"""Declared drawing floor-area claims for PlanReader.

This module reads only drawing text. It deliberately knows nothing about
benchmarks, projects, BOQs, expected quantities, or downstream score targets.

A printed ``FLOOR AREA`` annotation is a declared source quantity claim. By
itself it is NOT physical geometry authority and is NOT a bound floor/slab
quantity authority. The claim may be retained for reconciliation, validation,
and discrepancy reporting until a separate producer-owned binding proves that
it belongs to a specific physical entity.

The parser remains intentionally narrow and fail-closed:

* the page must identify itself as a floor-plan / floor-layout drawing;
* the value must be explicitly labelled ``FLOOR AREA`` and carry square-metre
  units (``m2``, ``m²``, ``sqm`` or ``sq m``);
* multiple materially different floor-area annotations on one page are
  ambiguous and yield no resolved page claim;
* multiple pages may corroborate the same declared value, but disagreeing
  pages make the document-level claim unresolved.

Room-area labels, drawing scales, unlabelled numbers, schedules and BOQ text do
not satisfy this contract. This module never chooses length/width, manufactures
a footprint, or promotes a declared aggregate into physical take-off authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional, Tuple


DECLARED_FLOOR_AREA_AUTHORITY = "declared_floor_area_reconciliation_only"
DECLARED_FLOOR_AREA_BINDING = "unbound"

_PLAN_CONTEXT_RE = re.compile(
    r"\b(?:floor\s+plan|floor\s+layout|ground\s+floor\s+plan|"
    r"design\s+scheme\s*\(\s*plan\s*\)|general\s+[^\n]{0,40}\s+floor\s+plan)\b",
    re.IGNORECASE,
)

# Keep the label-to-value window deliberately short. It is long enough for
# line-broken title-block formatting such as ``AREA in M2 / FLOOR AREA / - /
# 162.69M2`` but short enough not to wander into unrelated schedule values.
_FLOOR_AREA_RE = re.compile(
    r"\bfloor\s+area\b[^\d]{0,48}"
    r"(?P<value>\d{1,6}(?:[.,]\d{1,3})?)\s*"
    r"(?P<unit>m\s*(?:2|²)|sq\.?\s*m|sqm)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExplicitFloorAreaEvidence:
    """Resolved declared overall floor-area claim from one or more pages.

    The class name is retained for compatibility with existing callers. Its
    authority and binding fields intentionally make the new boundary explicit:
    this record is reconciliation evidence only until another authority binds a
    scoped explicit area to a proven physical entity.
    """

    area_m2: float
    source_pages: Tuple[int, ...]
    raw_evidence: Tuple[str, ...]
    authority: str = DECLARED_FLOOR_AREA_AUTHORITY
    binding: str = DECLARED_FLOOR_AREA_BINDING
    source_sha256: Optional[str] = None
    revision_id: Optional[str] = None


def _normalise_text(text: str) -> str:
    return " ".join(str(text or "").replace("\u00a0", " ").split())


def extract_explicit_floor_area_evidence(
    page_text: str,
    *,
    source_page: int,
    source_sha256: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> Optional[ExplicitFloorAreaEvidence]:
    """Extract one unambiguous declared floor-area claim from a plan page."""

    normalized = _normalise_text(page_text)
    if not normalized or not _PLAN_CONTEXT_RE.search(normalized):
        return None

    matches = []
    for match in _FLOOR_AREA_RE.finditer(normalized):
        try:
            value = float(match.group("value").replace(",", "."))
        except ValueError:
            continue
        # Only reject physically impossible / parser-noise values. These are
        # broad domain sanity bounds, not project-specific tuning constants.
        if not (0.1 <= value <= 1_000_000.0):
            continue
        matches.append((round(value, 3), match.group(0).strip()))

    if not matches:
        return None

    distinct = {value for value, _raw in matches}
    if len(distinct) != 1:
        return None

    area = next(iter(distinct))
    raw = tuple(dict.fromkeys(raw_text for _value, raw_text in matches))
    return ExplicitFloorAreaEvidence(
        area_m2=area,
        source_pages=(int(source_page),),
        raw_evidence=raw,
        source_sha256=source_sha256,
        revision_id=revision_id,
    )


def resolve_explicit_floor_area_evidence(
    evidence: Iterable[ExplicitFloorAreaEvidence],
) -> Optional[ExplicitFloorAreaEvidence]:
    """Resolve corroborating declared claims; disagreement fails closed.

    Resolution here means only that the source repeats the same declared
    quantity. It does not bind the claim to geometry or promote quantity
    authority.
    """

    items = list(evidence)
    if not items:
        return None

    distinct = {round(item.area_m2, 3) for item in items}
    if len(distinct) != 1:
        return None

    source_hashes = {item.source_sha256 for item in items if item.source_sha256}
    revisions = {item.revision_id for item in items if item.revision_id}
    if len(source_hashes) > 1 or len(revisions) > 1:
        return None

    pages = tuple(sorted({p for item in items for p in item.source_pages}))
    raw = tuple(dict.fromkeys(raw for item in items for raw in item.raw_evidence))
    return ExplicitFloorAreaEvidence(
        area_m2=next(iter(distinct)),
        source_pages=pages,
        raw_evidence=raw,
        source_sha256=next(iter(source_hashes)) if source_hashes else None,
        revision_id=next(iter(revisions)) if revisions else None,
    )


# Component rows are not the same claim as an aggregate "TOTAL FLOOR AREA".
# This narrow parser is reconciliation *input* only, never a source-authenticated
# physical floor measurement and never QuantityEvidence.
_COMPONENT_AREA_LABEL_RE = re.compile(
    r"^(?P<label>[A-Za-z][A-Za-z0-9&/()+. -]{0,79}?)\s+AREA\s*:\s*(?P<inline>.*)$",
    re.IGNORECASE,
)
_COMPONENT_AREA_VALUE_RE = re.compile(
    r"^(?P<value>\d{1,6}(?:\\.\d{1,3})?)\s*"
    r"(?P<unit>m(?:2|²)|sq\\.?\s*m|sqm)$",
    re.IGNORECASE,
)
_COMPONENT_AGGREGATE_PREFIXES = ("TOTAL", "SUBTOTAL", "GRAND TOTAL")


@dataclass(frozen=True)
class DeclaredComponentFloorAreaEvidence:
    """One printed, unbound area row from a caller-isolated text block.

    The source text is NOT presumed glyph-, clip- or paint-authenticated.
    A complete original source identity and geometric physical binding must
    be independently issued before any commercial quantity can exist.
    """

    label: str
    area_m2: float
    source_page: int
    source_block_id: str
    raw_evidence: str
    authority: str = DECLARED_FLOOR_AREA_AUTHORITY
    binding: str = DECLARED_FLOOR_AREA_BINDING
    source_sha256: Optional[str] = None
    revision_id: Optional[str] = None


def extract_declared_component_floor_areas(
    source_block_text: str,
    *,
    source_page: int,
    source_block_id: str,
    source_sha256: Optional[str] = None,
    revision_id: Optional[str] = None,
) -> Tuple[DeclaredComponentFloorAreaEvidence, ...]:
    """Read independent printed component-area rows without inventing m².

    The caller supplies one exact source-native text block (not a flattened
    multi-page text dump). Each area label is paired with a value on its SAME
    text line or the immediately next nonblank line, never the closest match
    across unrelated blocks. Duplicated labels are withheld even when their
    numbers agree: the original physical owners could still be distinct.

    This is intentionally unbound evidence only. It does not change the
    existing aggregate floor-area parser or issue FIRM QuantityEvidence.
    """
    if type(source_page) is not int or source_page <= 0:
        raise ValueError("source_page must be an exact positive page number")
    if (
        type(source_block_id) is not str
        or not source_block_id
        or source_block_id != source_block_id.strip()
    ):
        raise ValueError("source_block_id must be a typed original block address")
    if source_sha256 is not None and (
        type(source_sha256) is not str
        or len(source_sha256) != 64
        or any(char not in "0123456789abcdefABCDEF" for char in source_sha256)
    ):
        raise ValueError("source_sha256 must be a 64-hex source address")
    if revision_id is not None and (
        type(revision_id) is not str or not revision_id
        or revision_id != revision_id.strip()
    ):
        raise ValueError("revision_id must be an exact source revision")
    if type(source_block_text) is not str:
        raise TypeError("source_block_text must be one original text block")

    # Blank native PDF line breaks between labels and values are allowed;
    # another substantive text row terminates the pending value window.
    lines = tuple(line.strip() for line in source_block_text.splitlines()
                  if line.strip())
    candidates: list[DeclaredComponentFloorAreaEvidence] = []
    for index, raw_line in enumerate(lines):
        label_match = _COMPONENT_AREA_LABEL_RE.fullmatch(raw_line)
        if label_match is None:
            continue
        label = " ".join(label_match.group("label").split())
        if not label or label.upper().startswith(_COMPONENT_AGGREGATE_PREFIXES):
            continue
        inline = label_match.group("inline").strip()
        if inline:
            candidate_line = inline
        elif index + 1 < len(lines):
            candidate_line = lines[index + 1]
        else:
            continue
        value_match = _COMPONENT_AREA_VALUE_RE.fullmatch(candidate_line)
        if value_match is None:
            continue
        try:
            value = float(value_match.group("value"))
        except (ValueError, OverflowError):
            continue
        if not (0.0 < value <= 1_000_000.0):
            continue
        candidates.append(
            DeclaredComponentFloorAreaEvidence(
                label=label,
                area_m2=value,
                source_page=source_page,
                source_block_id=source_block_id,
                raw_evidence=raw_line + (" " + candidate_line if not inline else ""),
                source_sha256=source_sha256,
                revision_id=revision_id,
            )
        )

    counts: dict[str, int] = {}
    for row in candidates:
        key = " ".join(row.label.casefold().split())
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        row for row in candidates
        if counts[" ".join(row.label.casefold().split())] == 1
    )
