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
import math
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
    # An unbound overall-area claim cannot borrow another declaration's
    # source SHA, revision or page if one input has no original receipt.
    # All unscoped legacy declarations may still reconcile with one another.
    def valid_area_m2(value: object) -> bool:
        if type(value) not in (int, float):
            return False
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            return False
        return math.isfinite(numeric) and numeric > 0.0

    if any(
        type(item) is not ExplicitFloorAreaEvidence
        or item.authority != DECLARED_FLOOR_AREA_AUTHORITY
        or item.binding != DECLARED_FLOOR_AREA_BINDING
        or not valid_area_m2(item.area_m2)
        or type(item.source_pages) not in (tuple, list)
        or not item.source_pages
        or any(type(p) is not int or p <= 0 for p in item.source_pages)
        or type(item.raw_evidence) not in (tuple, list)
        or any(type(text) is not str or not text for text in item.raw_evidence)
        or (item.source_sha256 is not None and (
            type(item.source_sha256) is not str
            or re.fullmatch(r"[0-9a-f]{64}", item.source_sha256) is None
        ))
        or (item.revision_id is not None and (
            type(item.revision_id) is not str
            or not item.revision_id
            or item.revision_id != item.revision_id.strip()
        ))
        for item in items
    ):
        return None
    for key in ("source_sha256", "revision_id"):
        values = [getattr(item, key) for item in items]
        if any(value is None for value in values) and any(
            value is not None for value in values
        ):
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
