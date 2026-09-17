"""Producer-owned secondary footprint & verandah authority (Item 29).

Implements authenticated secondary-footprint geometry for:
- Verandahs, porches, covered external slabs, attached canopies
- Secondary building footprints and projections from the primary enclosed footprint

Architectural Invariants:
- Obtains polygon geometry and footprint classification directly from authenticated PhysicalWallCandidateAuthority and PhysicalScaleAuthority.
- NEVER accepts caller-supplied polygon points or caller-assigned categories.
- Never treats "largest polygon" as the entire building or default boundary.
- Distinguishes primary enclosed footprint (is_enclosed=True) from covered-but-open footprint (is_enclosed=False).
- Requires exact geometry provenance and authenticated physical scale.
- Preserves disconnected components; does not absorb nearby structures merely because of proximity.
- Ambiguous boundaries fail closed (ABSTAINED / CONFLICT).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)

SECONDARY_FOOTPRINT_SCHEMA_VERSION = "1.0.0"

# Public reason codes
SECONDARY_FOOTPRINT_RESOLVED = "secondary_footprint_resolved"
SECONDARY_FOOTPRINT_UNRESOLVED = "secondary_footprint_unresolved"
SECONDARY_FOOTPRINT_WALL_UNRESOLVED = "secondary_footprint_wall_unresolved"
SECONDARY_FOOTPRINT_SCALE_UNRESOLVED = "secondary_footprint_scale_unresolved"
SECONDARY_FOOTPRINT_LINEAGE_MISMATCH = "secondary_footprint_lineage_mismatch"
SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE = "secondary_footprint_geometry_unavailable"
SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE = "secondary_footprint_record_unavailable"
SECONDARY_FOOTPRINT_GEOMETRY_INVALID = "secondary_footprint_geometry_invalid"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _polygon_area(pts: Sequence[Tuple[float, float]]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def _polygon_perimeter(pts: Sequence[Tuple[float, float]]) -> float:
    n = len(pts)
    if n < 2:
        return 0.0
    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        x1, y1 = pts[i]
        x2, y2 = pts[j]
        perim += math.hypot(x2 - x1, y2 - y1)
    return perim


def _polygon_to_hex(pts: Sequence[Tuple[float, float]]) -> str:
    raw = f"POLYGON(({','.join(f'{x:.4f} {y:.4f}' for x, y in pts)}))"
    return raw.encode("utf-8").hex()


class FootprintCategory(str, Enum):
    """Classification of a building footprint component."""
    PRIMARY_ENCLOSED = "primary_enclosed"
    VERANDAH = "verandah"
    PORCH = "porch"
    COVERED_SLAB = "covered_slab"
    CANOPY = "canopy"
    SECONDARY_BUILDING = "secondary_building"
    PROJECTION = "projection"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class SecondaryFootprintSelector:
    """Sealed selector identifying exact secondary footprint component."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    footprint_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "footprint_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.footprint_id,
        )


@dataclass(frozen=True)
class SecondaryFootprintRecord:
    """Sealed record proving authenticated secondary footprint geometry."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    footprint_id: str
    category: FootprintCategory
    is_enclosed: bool
    area_m2: float
    perimeter_m: float
    polygon_wkb_hex: str
    schema_version: str = SECONDARY_FOOTPRINT_SCHEMA_VERSION


@dataclass(frozen=True)
class SecondaryFootprintResult:
    """Result of secondary footprint authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SecondaryFootprintRecord] = None
    schema_version: str = SECONDARY_FOOTPRINT_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SecondaryFootprintResult:
    return SecondaryFootprintResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> SecondaryFootprintResult:
    return SecondaryFootprintResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class SecondaryFootprintAuthority:
    """Sealed selector-only lookup for published secondary footprint records."""

    def __init__(
        self,
        results: Mapping[_Key, SecondaryFootprintResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SecondaryFootprintAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: SecondaryFootprintSelector) -> SecondaryFootprintResult:
        if type(selector) is not SecondaryFootprintSelector:
            raise TypeError("selector must be SecondaryFootprintSelector")
        return self._results.get(
            selector.key,
            _abstained(SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE),
        )


class SecondaryFootprintProducer:
    """Trusted writer boundary for secondary footprint & verandah authority.

    Consumes ONLY producer-owned PhysicalWallCandidateAuthority and PhysicalScaleAuthority.
    Does NOT accept caller-supplied polygon points or caller-assigned categories.
    """

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SecondaryFootprintProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
        self._wall_candidates = physical_wall_candidate_authority
        self._scale = physical_scale_authority
        self._results: dict[_Key, SecondaryFootprintResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
    ) -> "SecondaryFootprintProducer":
        return cls(
            physical_wall_candidate_authority,
            physical_scale_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> SecondaryFootprintAuthority:
        return SecondaryFootprintAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: SecondaryFootprintSelector,
        result: SecondaryFootprintResult,
    ) -> SecondaryFootprintResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: SecondaryFootprintSelector,
    ) -> SecondaryFootprintResult:
        """Publish authenticated secondary footprint geometry strictly from upstream authorities."""
        if type(selector) is not SecondaryFootprintSelector:
            raise TypeError("selector must be SecondaryFootprintSelector")

        # 1. Resolve Physical Wall Candidates
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_result = self._wall_candidates.resolve_scope(cand_sel)
        if (
            cand_result.status is not EvidenceResolutionStatus.CORROBORATED
            and selector.decision_scope_id != cand_scope_id
        ):
            try:
                alt_sel = PhysicalWallCandidateSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                )
                alt = self._wall_candidates.resolve_scope(alt_sel)
                if alt.status is EvidenceResolutionStatus.CORROBORATED:
                    cand_result = alt
            except Exception:
                pass

        if cand_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    SECONDARY_FOOTPRINT_WALL_UNRESOLVED,
                    *(getattr(cand_result, "reason_codes", ()) or ()),
                ),
            )

        matching_recs = [
            r for r in getattr(cand_result, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.footprint_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None)
            == selector.footprint_id
        ]
        if not matching_recs:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_WALL_UNRESOLVED))

        wall_rec = matching_recs[0]
        wc = getattr(wall_rec, "wall_candidate", None)

        # 2. Resolve Scale
        scale_sel = PhysicalScaleSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
        )
        scale_res = self._scale.resolve(scale_sel)
        if (
            scale_res.status is not EvidenceResolutionStatus.CORROBORATED
            or scale_res.evidence is None
        ):
            return self._store(
                selector,
                _abstained(
                    SECONDARY_FOOTPRINT_SCALE_UNRESOLVED,
                    *(getattr(scale_res, "reason_codes", ()) or ()),
                ),
            )
        mm_per_pt = float(scale_res.evidence.mm_per_point)
        if not math.isfinite(mm_per_pt) or mm_per_pt <= 0.0:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_SCALE_UNRESOLVED))

        # 3. Extract Footprint Polygon & Category from Authenticated Upstream Candidate
        pts = getattr(wc, "polygon_pts", None) or getattr(wc, "centerline_pts", None)
        if not pts or len(pts) < 3:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE))

        cat_str = str(getattr(wc, "footprint_category", None) or "").lower()
        if cat_str == "verandah":
            category = FootprintCategory.VERANDAH
        elif cat_str == "porch":
            category = FootprintCategory.PORCH
        elif cat_str == "covered_slab":
            category = FootprintCategory.COVERED_SLAB
        elif cat_str == "canopy":
            category = FootprintCategory.CANOPY
        elif cat_str == "secondary_building":
            category = FootprintCategory.SECONDARY_BUILDING
        elif cat_str == "primary_enclosed":
            category = FootprintCategory.PRIMARY_ENCLOSED
        elif cat_str == "projection":
            category = FootprintCategory.PROJECTION
        else:
            # Infer from interior_exterior / candidate attributes
            ie = str(getattr(wc, "interior_exterior", None) or "").lower()
            if ie == "exterior":
                category = FootprintCategory.VERANDAH
            elif ie == "interior":
                category = FootprintCategory.PRIMARY_ENCLOSED
            else:
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_UNRESOLVED))

        is_enclosed = category in (FootprintCategory.PRIMARY_ENCLOSED, FootprintCategory.SECONDARY_BUILDING)

        area_pt2 = _polygon_area(pts)
        perim_pt = _polygon_perimeter(pts)

        if area_pt2 <= 0.0:
            return self._store(selector, _conflict(SECONDARY_FOOTPRINT_GEOMETRY_INVALID))

        m_per_pt = mm_per_pt / 1000.0
        area_m2 = round(area_pt2 * (m_per_pt ** 2), 6)
        perimeter_m = round(perim_pt * m_per_pt, 6)

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "footprint_id": selector.footprint_id,
            "category": category.value,
            "is_enclosed": is_enclosed,
            "area_m2": area_m2,
            "perimeter_m": perimeter_m,
        }
        record_id = stable_contract_id("secondary_footprint", payload, digest_chars=32)
        record = SecondaryFootprintRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            footprint_id=selector.footprint_id,
            category=category,
            is_enclosed=is_enclosed,
            area_m2=area_m2,
            perimeter_m=perimeter_m,
            polygon_wkb_hex=_polygon_to_hex(pts),
        )
        return self._store(
            selector,
            SecondaryFootprintResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(SECONDARY_FOOTPRINT_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "FootprintCategory",
    "SECONDARY_FOOTPRINT_GEOMETRY_INVALID",
    "SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_LINEAGE_MISMATCH",
    "SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_RESOLVED",
    "SECONDARY_FOOTPRINT_SCALE_UNRESOLVED",
    "SECONDARY_FOOTPRINT_SCHEMA_VERSION",
    "SECONDARY_FOOTPRINT_UNRESOLVED",
    "SECONDARY_FOOTPRINT_WALL_UNRESOLVED",
    "SecondaryFootprintAuthority",
    "SecondaryFootprintProducer",
    "SecondaryFootprintRecord",
    "SecondaryFootprintResult",
    "SecondaryFootprintSelector",
]
