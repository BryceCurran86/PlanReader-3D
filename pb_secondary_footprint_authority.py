"""Producer-owned secondary footprint & verandah authority (Item 29).

Implements authenticated secondary-footprint geometry for:
- Verandahs, porches, covered external slabs, attached canopies
- Secondary building footprints and projections from the primary enclosed footprint

Architectural Invariants:
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

from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)

SECONDARY_FOOTPRINT_SCHEMA_VERSION = "1.0.0"

# Public reason codes
SECONDARY_FOOTPRINT_RESOLVED = "secondary_footprint_resolved"
SECONDARY_FOOTPRINT_UNRESOLVED = "secondary_footprint_unresolved"
SECONDARY_FOOTPRINT_SCALE_UNRESOLVED = "secondary_footprint_scale_unresolved"
SECONDARY_FOOTPRINT_LINEAGE_MISMATCH = "secondary_footprint_lineage_mismatch"
SECONDARY_FOOTPRINT_LARGEST_POLYGON_REJECTED = "secondary_footprint_largest_polygon_rule_rejected"
SECONDARY_FOOTPRINT_PROXIMITY_ABSORPTION_REJECTED = "secondary_footprint_proximity_absorption_rejected"
SECONDARY_FOOTPRINT_CALLER_CATEGORY_REJECTED = "secondary_footprint_caller_category_rejected"
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
class SecondaryFootprintEvidence:
    """Authenticated spatial/geometry observation of a secondary structure."""
    evidence_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    category: FootprintCategory
    polygon_points_pt: Tuple[Tuple[float, float], ...]  # [(x, y), ...] in points
    kind: str           # e.g. "plan_verandah_outline", "porch_slab_boundary"
    confidence: float

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "source_sha256",
            "revision_id",
            "snapshot_id",
            "page_id",
            "viewport_id",
            "kind",
        ):
            _required(getattr(self, name), name)
        if not isinstance(self.category, FootprintCategory):
            raise TypeError("category must be FootprintCategory")
        if len(self.polygon_points_pt) < 3:
            raise ValueError("polygon_points_pt must contain at least 3 points")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")


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
    """Trusted writer boundary for secondary footprint & verandah authority."""

    def __init__(
        self,
        physical_scale_authority: PhysicalScaleAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SecondaryFootprintProducer must be obtained via from_authorities()")
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
        self._scale = physical_scale_authority
        self._results: dict[_Key, SecondaryFootprintResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_scale_authority: PhysicalScaleAuthority,
    ) -> "SecondaryFootprintProducer":
        return cls(physical_scale_authority, _seal=_PRODUCER_SEAL)

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
        observations: Sequence[SecondaryFootprintEvidence],
    ) -> SecondaryFootprintResult:
        """Publish authenticated secondary footprint geometry for selector."""
        if type(selector) is not SecondaryFootprintSelector:
            raise TypeError("selector must be SecondaryFootprintSelector")

        # 1. Resolve Scale
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

        # 2. Filter Observations
        obs = list(observations or [])
        if not obs:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_UNRESOLVED))

        forbidden_kinds = {
            "largest_polygon_rule",
            "proximity_absorption",
            "caller_category",
            "assumed_footprint",
        }
        valid_obs: list[SecondaryFootprintEvidence] = []
        stale_count = 0
        forbidden_largest = False
        forbidden_proximity = False

        for ob in obs:
            if not isinstance(ob, SecondaryFootprintEvidence):
                continue
            if ob.kind == "largest_polygon_rule":
                forbidden_largest = True
                continue
            if ob.kind == "proximity_absorption":
                forbidden_proximity = True
                continue
            if ob.kind in forbidden_kinds:
                continue

            # Lineage match
            if (
                ob.source_sha256 != selector.source_sha256
                or ob.revision_id != selector.revision_id
                or ob.snapshot_id != selector.snapshot_id
                or ob.page_id != selector.page_id
            ):
                stale_count += 1
                continue
            valid_obs.append(ob)

        if forbidden_largest and not valid_obs:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_LARGEST_POLYGON_REJECTED))
        if forbidden_proximity and not valid_obs:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_PROXIMITY_ABSORPTION_REJECTED))
        if stale_count and not valid_obs:
            return self._store(selector, _conflict(SECONDARY_FOOTPRINT_LINEAGE_MISMATCH))
        if not valid_obs:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_UNRESOLVED))

        # Check for category agreement
        categories = {ob.category for ob in valid_obs}
        if FootprintCategory.UNRESOLVED in categories:
            categories.remove(FootprintCategory.UNRESOLVED)
        if len(categories) == 0:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_UNRESOLVED))
        if len(categories) > 1:
            return self._store(selector, _conflict(SECONDARY_FOOTPRINT_UNRESOLVED, "conflicting_categories"))

        category = next(iter(categories))
        is_enclosed = category in (FootprintCategory.PRIMARY_ENCLOSED, FootprintCategory.SECONDARY_BUILDING)

        # 3. Compute Metric Geometry from Polygon Points
        first_ob = valid_obs[0]
        pts = first_ob.polygon_points_pt
        area_pt2 = _polygon_area(pts)
        perim_pt = _polygon_perimeter(pts)

        if area_pt2 <= 0.0:
            return self._store(selector, _conflict(SECONDARY_FOOTPRINT_GEOMETRY_INVALID))

        # Convert points to metres: 1 pt * mm_per_pt = mm / 1000 = m
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
    "SECONDARY_FOOTPRINT_CALLER_CATEGORY_REJECTED",
    "SECONDARY_FOOTPRINT_GEOMETRY_INVALID",
    "SECONDARY_FOOTPRINT_LARGEST_POLYGON_REJECTED",
    "SECONDARY_FOOTPRINT_LINEAGE_MISMATCH",
    "SECONDARY_FOOTPRINT_PROXIMITY_ABSORPTION_REJECTED",
    "SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_RESOLVED",
    "SECONDARY_FOOTPRINT_SCALE_UNRESOLVED",
    "SECONDARY_FOOTPRINT_SCHEMA_VERSION",
    "SECONDARY_FOOTPRINT_UNRESOLVED",
    "SecondaryFootprintAuthority",
    "SecondaryFootprintEvidence",
    "SecondaryFootprintProducer",
    "SecondaryFootprintRecord",
    "SecondaryFootprintResult",
    "SecondaryFootprintSelector",
]
