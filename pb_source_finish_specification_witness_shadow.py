"""Generic finish-specification, wall-extent, and elevation-material source witnesses (A20/A22/A23).

Shadow-only, producer-neutral evidence extraction with zero job-specific rules:
- A20: Explicit lining/finish thickness witnesses (e.g., ``10mm PLASTERBOARD``,
  ``13mm GYPROCK``, ``12mm CERAMIC TILE``, ``6mm FIBRE CEMENT``).
- A22: Explicit wall-finish height extent & wet-area partial/full-height
  treatment (e.g., ``FULL HEIGHT TILES``, ``TILES TO 1200mm``, ``DADO TO 1.2M``,
  ``SPLASHBACK TO 600mm``, ``WATERPROOF TO 1800mm``).
- A23: Explicit external/elevation material witnesses strictly scoped to
  elevation/external views and matching document revision/SHA.

All extractors fail closed (ABSTAINED / CONFLICT) on conflicting values,
cross-revision mismatches, or wrong-view scope, and never grant commercial
quantity authority (``commercial_authority_granted = False``).
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus

SCHEMA_VERSION = "1.0.0"

_UNICODE_CLEAN = str.maketrans({
    "\u2010": "-",
    "\u2011": "-",
    "\u2012": "-",
    "\u2013": "-",
    "\u2014": "-",
    "\u2212": "-",
    "\u00a0": " ",
    "\u2009": " ",
    "\u202f": " ",
    "\u200b": "",
    "\ufeff": "",
})
_THOUSANDS_RE = re.compile(r"(?<!\d)(\d{1,2}),(\d{3})(?!\d)")

_THICKNESS_RE = re.compile(
    r"\b(?P<mm>\d{1,2}(?:\.\d)?)\s*mm\s+"
    r"(?P<material>plasterboard|gyprock|villaboard|fibre\s+cement|fc\s+sheet|"
    r"ceramic\s+tile(?:s)?|porcelain\s+tile(?:s)?|tile(?:s)?|render|cement\s+render|"
    r"plywood|mdf|timber\s+lining|acoustic\s+panel|compressed\s+fc)\b",
    re.IGNORECASE,
)

_FULL_HEIGHT_RE = re.compile(
    r"\b(?:full\s*[-]?\s*height\s+(?:tile(?:s|d|ing)?|wall\s+tile(?:s)?|splashback|lining|waterproof(?:ing)?)|"
    r"(?:tile(?:s|d|ing)?|wall\s+tile(?:s)?)\s+to\s+(?:ceiling|underside\s+of\s+ceiling|full\s+height))\b",
    re.IGNORECASE,
)
_PARTIAL_HEIGHT_MM_RE = re.compile(
    r"\b(?:tile(?:s|d|ing)?|dado|splashback|waterproof(?:ing)?|skirting\s+tile(?:s)?|wall\s+lining)\s+"
    r"(?:to|up\s+to|@)\s*(?P<mm>\d{3,4})\s*mm\b",
    re.IGNORECASE,
)
_PARTIAL_HEIGHT_M_RE = re.compile(
    r"\b(?:tile(?:s|d|ing)?|dado|splashback|waterproof(?:ing)?|wall\s+lining)\s+"
    r"(?:to|up\s+to|@)\s*(?P<m>\d(?:\.\d{1,3})?)\s*m\b",
    re.IGNORECASE,
)

_EXTERNAL_MATERIAL_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("face_brick", re.compile(r"\bface\s+brick(?:work)?\b", re.IGNORECASE)),
    ("bagged_painted_brick", re.compile(r"\bbagged\s*(?:&|and)\s*painted\s+brick(?:work)?\b", re.IGNORECASE)),
    ("rendered_masonry", re.compile(r"\b(?:cement\s+)?rendered\s+(?:brick(?:work)?|block(?:work)?|masonry)\b", re.IGNORECASE)),
    ("metal_cladding", re.compile(r"\b(?:colorbond|metal|corrugated|standing\s+seam)\s+(?:wall\s+)?cladding\b", re.IGNORECASE)),
    ("fibre_cement_cladding", re.compile(r"\b(?:fibre\s+cement|fc|james\s+hardie|scyon|linea)\s+(?:wall\s+)?(?:cladding|weatherboard|sheet(?:ing)?)\b", re.IGNORECASE)),
    ("timber_weatherboard", re.compile(r"\b(?:timber\s+)?weatherboard(?:s)?\b", re.IGNORECASE)),
    ("aluminium_cladding", re.compile(r"\balumin(?:i)?um\s+(?:composite\s+)?cladding\b", re.IGNORECASE)),
)


def _norm(text: str) -> str:
    cleaned = unicodedata.normalize("NFKC", str(text or "")).translate(_UNICODE_CLEAN)
    cleaned = _THOUSANDS_RE.sub(r"\1\2", cleaned)
    return " ".join(cleaned.strip().split())


@dataclass(frozen=True)
class FinishThicknessWitness:
    status: EvidenceResolutionStatus
    thickness_mm: Optional[float]
    material_label: Optional[str]
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False
    issuer_wiring_owned_by: str = "MAX"


@dataclass(frozen=True)
class WallFinishExtentWitness:
    status: EvidenceResolutionStatus
    extent_mode: Optional[str]  # "full_height" | "partial_height" | None
    extent_height_mm: Optional[int]
    wet_area_indicated: bool
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False
    issuer_wiring_owned_by: str = "MAX"


@dataclass(frozen=True)
class ExternalElevationMaterialWitness:
    status: EvidenceResolutionStatus
    document_id: str
    revision_id: str
    source_sha256: str
    view_type: str
    materials: tuple[str, ...]
    reason_codes: tuple[str, ...]
    commercial_authority_granted: bool = False
    issuer_wiring_owned_by: str = "MAX"


def extract_finish_thickness_witness(text: str) -> FinishThicknessWitness:
    """Extract one explicit lining/finish thickness witness (A20); abstain on conflicts."""
    norm = _norm(text)
    if not norm:
        return FinishThicknessWitness(
            EvidenceResolutionStatus.ABSTAINED, None, None, ("empty_finish_thickness_text",)
        )
    hits: list[tuple[float, str]] = []
    for match in _THICKNESS_RE.finditer(norm):
        val = float(match.group("mm"))
        if 1.0 <= val <= 50.0:
            hits.append((val, match.group("material").lower()))
    distinct_mm = sorted({h[0] for h in hits})
    if not distinct_mm:
        return FinishThicknessWitness(
            EvidenceResolutionStatus.ABSTAINED, None, None, ("no_explicit_finish_thickness",)
        )
    if len(distinct_mm) > 1:
        return FinishThicknessWitness(
            EvidenceResolutionStatus.CONFLICT, None, None, ("conflicting_finish_thickness_values",)
        )
    materials = sorted({h[1] for h in hits})
    if len(materials) > 1:
        return FinishThicknessWitness(
            EvidenceResolutionStatus.CONFLICT, None, None, ("conflicting_finish_thickness_materials",)
        )
    return FinishThicknessWitness(
        EvidenceResolutionStatus.CORROBORATED,
        distinct_mm[0],
        materials[0],
        ("explicit_finish_thickness_extracted",),
    )


def extract_wall_finish_extent_witness(text: str) -> WallFinishExtentWitness:
    """Extract explicit wall finish height extent & wet-area treatment (A22)."""
    norm = _norm(text)
    if not norm:
        return WallFinishExtentWitness(
            EvidenceResolutionStatus.ABSTAINED, None, None, False, ("empty_wall_finish_extent_text",)
        )
    wet_area = bool(
        re.search(r"\b(?:wet\s+area|waterproof(?:ing)?|shower|bath(?:room)?|ensuite|wc|laundry|splashback)\b", norm, re.IGNORECASE)
    )
    is_full = bool(_FULL_HEIGHT_RE.search(norm))
    partial_heights: set[int] = set()
    for match in _PARTIAL_HEIGHT_MM_RE.finditer(norm):
        val = int(match.group("mm"))
        if 100 <= val <= 3600:
            partial_heights.add(val)
    for match in _PARTIAL_HEIGHT_M_RE.finditer(norm):
        val = round(float(match.group("m")) * 1000.0)
        if 100 <= val <= 3600:
            partial_heights.add(val)

    if is_full and partial_heights:
        return WallFinishExtentWitness(
            EvidenceResolutionStatus.CONFLICT,
            None,
            None,
            wet_area,
            ("conflicting_full_and_partial_wall_finish_extent",),
        )
    if len(partial_heights) > 1:
        return WallFinishExtentWitness(
            EvidenceResolutionStatus.CONFLICT,
            None,
            None,
            wet_area,
            ("conflicting_partial_wall_finish_heights",),
        )
    if is_full:
        return WallFinishExtentWitness(
            EvidenceResolutionStatus.CORROBORATED,
            "full_height",
            None,
            wet_area,
            ("explicit_full_height_wall_finish",),
        )
    if len(partial_heights) == 1:
        return WallFinishExtentWitness(
            EvidenceResolutionStatus.CORROBORATED,
            "partial_height",
            next(iter(partial_heights)),
            wet_area,
            ("explicit_partial_height_wall_finish",),
        )
    return WallFinishExtentWitness(
        EvidenceResolutionStatus.ABSTAINED,
        None,
        None,
        wet_area,
        ("wall_finish_extent_unproven",),
    )


def extract_external_elevation_material_witness(
    *,
    text: str,
    view_type: str,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    expected_revision_id: Optional[str] = None,
) -> ExternalElevationMaterialWitness:
    """Extract elevation/external cladding material witnesses scoped to elevation views (A23)."""
    vt = str(view_type or "").strip().lower()
    if expected_revision_id is not None and str(revision_id).strip() != str(expected_revision_id).strip():
        return ExternalElevationMaterialWitness(
            EvidenceResolutionStatus.CONFLICT,
            document_id,
            revision_id,
            source_sha256,
            vt,
            (),
            ("cross_revision_elevation_material_rejected",),
        )
    if vt not in ("elevation", "section"):
        return ExternalElevationMaterialWitness(
            EvidenceResolutionStatus.ABSTAINED,
            document_id,
            revision_id,
            source_sha256,
            vt,
            (),
            ("non_elevation_view_scope_rejected",),
        )
    norm = _norm(text)
    found = tuple(
        name for name, pattern in _EXTERNAL_MATERIAL_PATTERNS if pattern.search(norm)
    )
    if not found:
        return ExternalElevationMaterialWitness(
            EvidenceResolutionStatus.ABSTAINED,
            document_id,
            revision_id,
            source_sha256,
            vt,
            (),
            ("no_explicit_external_material_callout",),
        )
    return ExternalElevationMaterialWitness(
        EvidenceResolutionStatus.CORROBORATED,
        document_id,
        revision_id,
        source_sha256,
        vt,
        found,
        ("explicit_elevation_external_material_extracted",),
    )


__all__ = [
    "ExternalElevationMaterialWitness",
    "FinishThicknessWitness",
    "SCHEMA_VERSION",
    "WallFinishExtentWitness",
    "extract_external_elevation_material_witness",
    "extract_finish_thickness_witness",
    "extract_wall_finish_extent_witness",
]
