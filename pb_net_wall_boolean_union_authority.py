"""Producer-owned Net-wall Boolean Union authority foundation.

Item 17. The geometry helpers are production-capable today. The positive authority
publication route remains structurally unavailable until Items 11-15 provide the
sealed physical-opening-void, opening-deduction and applicable-opening universe
authorities required by the contract.

Nothing in this module may treat caller polygons, caller areas, caller opening IDs,
caller completeness booleans, nearest/first choices or legacy scalar arithmetic as
authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import importlib
import math
from types import MappingProxyType
from typing import Iterable, Mapping

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

NET_WALL_BOOLEAN_UNION_SCHEMA_VERSION = "1.0.0"
NET_WALL_BOOLEAN_UNION_RESOLVED = "net_wall_boolean_union_resolved"
NET_WALL_BOOLEAN_UNION_UPSTREAM_UNAVAILABLE = "net_wall_boolean_union_upstream_authorities_unavailable"
NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE = "net_wall_boolean_union_record_unavailable"
NET_WALL_BOOLEAN_UNION_INVALID_GEOMETRY = "net_wall_boolean_union_invalid_geometry"

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _valid_geometry(geometry: BaseGeometry) -> bool:
    if not isinstance(geometry, BaseGeometry) or geometry.is_empty or not geometry.is_valid:
        return False
    bounds = tuple(float(v) for v in geometry.bounds)
    return bool(bounds) and all(math.isfinite(v) for v in bounds)


def union_wall_local_void_polygons(void_polygons: Iterable[BaseGeometry]) -> BaseGeometry:
    """Return exact geometric union of already-authenticated wall-local voids.

    This helper performs geometry only. It does not establish opening identity,
    host binding, applicability, completeness or deduction permission.
    """
    items = tuple(void_polygons)
    for geometry in items:
        if not _valid_geometry(geometry):
            raise ValueError(NET_WALL_BOOLEAN_UNION_INVALID_GEOMETRY)
    merged = unary_union(items)
    if not merged.is_empty and not merged.is_valid:
        raise ValueError(NET_WALL_BOOLEAN_UNION_INVALID_GEOMETRY)
    return merged


def subtract_void_union_from_wall_polygon(
    gross_wall_polygon: BaseGeometry,
    void_polygons: Iterable[BaseGeometry],
) -> BaseGeometry:
    """Subtract the union of authenticated wall-local voids from gross geometry."""
    if not _valid_geometry(gross_wall_polygon):
        raise ValueError(NET_WALL_BOOLEAN_UNION_INVALID_GEOMETRY)
    void_union = union_wall_local_void_polygons(void_polygons)
    result = gross_wall_polygon.difference(void_union)
    if result.is_empty:
        return result
    if not result.is_valid:
        raise ValueError(NET_WALL_BOOLEAN_UNION_INVALID_GEOMETRY)
    return result


@dataclass(frozen=True)
class NetWallBooleanUnionSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    trade_scope_id: str

    def __post_init__(self) -> None:
        for field in (
            "document_id", "revision_id", "source_sha256", "snapshot_id",
            "page_id", "decision_scope_id", "physical_wall_id", "trade_scope_id",
        ):
            _required(getattr(self, field), field)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.physical_wall_id,
            self.trade_scope_id,
        )


@dataclass(frozen=True)
class NetWallBooleanUnionEvidence:
    selector: NetWallBooleanUnionSelector
    record_id: str
    gross_wall_record_id: str
    opening_deduction_record_ids: tuple[str, ...]
    physical_void_record_ids: tuple[str, ...]
    gross_area_m2: float
    void_union_area_m2: float
    net_area_m2: float
    net_geometry_wkb_hex: str
    schema_version: str = NET_WALL_BOOLEAN_UNION_SCHEMA_VERSION


@dataclass(frozen=True)
class NetWallBooleanUnionResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: NetWallBooleanUnionEvidence | None = None
    schema_version: str = NET_WALL_BOOLEAN_UNION_SCHEMA_VERSION


def _blocked(*reasons: str) -> NetWallBooleanUnionResult:
    return NetWallBooleanUnionResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys(reason for reason in reasons if reason))
        or (NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE,),
    )


class NetWallBooleanUnionAuthority:
    """Sealed selector-only read boundary."""

    def __init__(self, results: Mapping[_Key, NetWallBooleanUnionResult], *, _seal: object = None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("NetWallBooleanUnionAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: NetWallBooleanUnionSelector) -> NetWallBooleanUnionResult:
        if type(selector) is not NetWallBooleanUnionSelector:
            raise TypeError("selector must be NetWallBooleanUnionSelector")
        return self._results.get(selector.key) or _blocked(NET_WALL_BOOLEAN_UNION_RECORD_UNAVAILABLE)


class NetWallBooleanUnionProducer:
    """Trusted writer boundary; positive construction is locked to real upstream classes."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise ValueError("NetWallBooleanUnionProducer is sealed")
        self._results: dict[_Key, NetWallBooleanUnionResult] = {}

    @classmethod
    def from_authorities(
        cls,
        physical_void_authority: object,
        opening_deduction_authority: object,
        opening_universe_authority: object,
        gross_wall_authority: object,
    ) -> "NetWallBooleanUnionProducer":
        """Construct only when the exact reviewed upstream authority classes exist.

        Items 11-15 are not merged yet. Until then this method deliberately fails
        closed rather than accepting lookalike caller objects or raw geometry.
        """
        required = (
            ("pb_physical_opening_void_authority", "PhysicalOpeningVoidAuthority", physical_void_authority),
            ("pb_opening_deduction_authority", "OpeningDeductionAuthority", opening_deduction_authority),
            ("pb_opening_universe_completeness_authority", "OpeningUniverseCompletenessAuthority", opening_universe_authority),
            ("pb_wall_gross_area_quantity", "GrossWallAreaAuthority", gross_wall_authority),
        )
        for module_name, class_name, instance in required:
            try:
                module = importlib.import_module(module_name)
                expected = getattr(module, class_name)
            except (ImportError, AttributeError) as exc:
                raise RuntimeError(NET_WALL_BOOLEAN_UNION_UPSTREAM_UNAVAILABLE) from exc
            if type(instance) is not expected:
                raise TypeError(f"{class_name} instance required")
        return cls(_seal=_PRODUCER_SEAL)

    def authority(self) -> NetWallBooleanUnionAuthority:
        return NetWallBooleanUnionAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def publish_scope(self, selector: NetWallBooleanUnionSelector) -> NetWallBooleanUnionResult:
        """Fail closed until reviewed upstream adapters are implemented.

        The positive body is intentionally not guessed here. When Items 11-15 land,
        this method must independently resolve their sealed records and then use the
        geometry helpers above. No caller-supplied polygon/list/completeness seam will
        be added to this signature.
        """
        if type(selector) is not NetWallBooleanUnionSelector:
            raise TypeError("selector must be NetWallBooleanUnionSelector")
        result = _blocked(NET_WALL_BOOLEAN_UNION_UPSTREAM_UNAVAILABLE)
        self._results[selector.key] = result
        return result


def deterministic_net_wall_record_id(
    selector: NetWallBooleanUnionSelector,
    *,
    gross_wall_record_id: str,
    opening_deduction_record_ids: tuple[str, ...],
    physical_void_record_ids: tuple[str, ...],
) -> str:
    """Addressing helper only; deterministic IDs never establish authority."""
    return stable_contract_id(
        "net_wall_boolean_union",
        {
            "selector": selector.key,
            "gross_wall_record_id": _required(gross_wall_record_id, "gross_wall_record_id"),
            "opening_deduction_record_ids": tuple(sorted(opening_deduction_record_ids)),
            "physical_void_record_ids": tuple(sorted(physical_void_record_ids)),
            "schema_version": NET_WALL_BOOLEAN_UNION_SCHEMA_VERSION,
        },
    )
