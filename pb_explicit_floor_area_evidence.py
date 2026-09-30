"""Declared drawing floor-area claims for PlanReader.

This module reads source drawing text only. It deliberately knows nothing about
benchmarks, projects, BOQs, expected quantities, or downstream score targets.

CRITICAL AUTHORITY BOUNDARY
---------------------------
A printed area statement is a declared source quantity claim. By itself it is
NOT proof of a physical footprint, polygon, length, width, slab boundary, room
identity, or finish extent.

The parser therefore only proves that:
* a page identifies itself as a floor-plan / floor-layout drawing;
* a value is explicitly labelled FLOOR AREA and carries square-metre units;
* the declaration is unambiguous on that page.

The resulting record is reconciliation/validation evidence until another,
entity-owning authority positively binds it to a proven physical zone.

Multiple pages may repeat the same declared value. Disagreeing declarations
remain unresolved at document-level; callers must retain the original per-page
claims rather than choosing one.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable, Optional, Tuple


DECLARED_FLOOR_AREA_EVIDENCE_ROLE = "declared_source_area_claim"
DECLARED_FLOOR_AREA_UNBOUND = "unbound"

_PLAN_CONTEXT_RE = re.compile(
    r"\b(?:floor\s+plan|floor\s+layout|ground\s+floor\s+plan|"
    r"design\s+scheme\s*\(\s*plan\s*\)|general\s+[^\n]{0,40}\s+floor\s+plan)\b",
    re.IGNORECASE,
)

# Keep the label-to-value window deliberately short. It is long enough for
# line-broken title-block formatting such as AREA in M2 / FLOOR AREA / - /
# 162.69M2 but short enough not to wander into unrelated schedule values.
_FLOOR_AREA_RE = re.compile(
    r"\bfloor\s+area\b[^\d]{0,48}"
    r"(?P<value>\d{1,6}(?:[.,]\d{1,3})?)\s*"
    r"(?P<unit>m\s*(?:2|²)|sq\.?\s*m|sqm)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ExplicitFloorAreaEvidence:
    """One declared overall floor-area claim from source text.

    The historical class name is retained for compatibility. evidence_role
    is intentionally not a physical measurement authority. binding remains
    unbound until a separate entity-owning authority proves scope.
    """

    area_m2: float
    source_pages: Tuple[int, ...]
    raw_evidence: Tuple[str, ...]
    evidence_role: str = DECLARED_FLOOR_AREA_EVIDENCE_ROLE
    binding: str = DECLARED_FLOOR_AREA_UNBOUND

    @property
    def authority(self) -> str:
        """Compatibility alias; returns a non-physical declared-evidence role."""
        return self.evidence_role


def _normalise_text(text: str) -> str:
    return " ".join(str(text or "").replace("\u00a0", " ").split())


def extract_explicit_floor_area_evidence(
    page_text: str,
    *,
    source_page: int,
) -> Optional[ExplicitFloorAreaEvidence]:
    """Extract one unambiguous declared floor-area claim from a plan page.

    Extraction does not bind the claim to any physical geometry or quantity.
    """

    normalized = _normalise_text(page_text)
    if not normalized or not _PLAN_CONTEXT_RE.search(normalized):
        return None

    matches = []
    for match in _FLOOR_AREA_RE.finditer(normalized):
        try:
            value = float(match.group("value").replace(",", "."))
        except ValueError:
            continue
        # Broad parser-noise bounds only; never project-specific tuning.
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
    )


def resolve_explicit_floor_area_evidence(
    evidence: Iterable[ExplicitFloorAreaEvidence],
) -> Optional[ExplicitFloorAreaEvidence]:
    """Reconcile repeated declarations only; never promote physical authority.

    Equal declarations may be combined for validation provenance. Any numerical
    disagreement fails closed at the aggregate reconciliation layer. Callers
    retain the original per-page records independently.
    """

    items = list(evidence)
    if not items:
        return None

    distinct = {round(item.area_m2, 3) for item in items}
    if len(distinct) != 1:
        return None

    pages = tuple(sorted({p for item in items for p in item.source_pages}))
    raw = tuple(dict.fromkeys(raw for item in items for raw in item.raw_evidence))
    return ExplicitFloorAreaEvidence(
        area_m2=next(iter(distinct)),
        source_pages=pages,
        raw_evidence=raw,
    )
