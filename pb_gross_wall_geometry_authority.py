"""Producer-owned gross wall geometry authority.

This module proves one proposition only: the authenticated 2D gross wall-local
geometry for an exact physical wall. The gross geometry is defined in wall-local
Euclidean coordinates (u, z) in metres:
- u runs along the wall baseline from 0.0 to length_m;
- z runs vertically from 0.0 to height_m.

The gross wall polygon is box(0.0, 0.0, length_m, height_m).
The wall_local_frame_id ties this gross wall to the exact same wall-local
coordinate frame used by physical opening voids on this wall.

No caller-supplied raw area, polygon, or scalar dimensions can mint authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping, Optional
from shapely.geometry import box

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


GROSS_WALL_GEOMETRY_SCHEMA_VERSION = "1.0.0"

GROSS_WALL_GEOMETRY_RESOLVED = "gross_wall_geometry_resolved"
GROSS_WALL_GEOMETRY_WALL_UNRESOLVED = "gross_wall_geometry_wall_unresolved"
GROSS_WALL_GEOMETRY_HEIGHT_UNRESOLVED = "gross_wall_geometry_height_unresolved"
GROSS_WALL_GEOMETRY_FRAME_UNRESOLVED = "gross_wall_geometry_frame_unresolved"
GROSS_WALL_GEOMETRY_SCALE_UNRESOLVED = "gross_wall_geometry_scale_unresolved"
GROSS_WALL_GEOMETRY_LINEAGE_MISMATCH = "gross_wall_geometry_lineage_mismatch"
GROSS_WALL_GEOMETRY_RECORD_UNAVAILABLE = "gross_wall_geometry_record_unavailable"
GROSS_WALL_GEOMETRY_INVALID = "gross_wall_geometry_invalid"
METRE = "metre"

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class GrossWallGeometrySelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
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
            self.physical_wall_id,
        )


@dataclass(frozen=True)
class GrossWallGeometryRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    wall_local_frame_id: str
    length_m: float
    height_m: float
    gross_area_m2: float
    polygon_wkb_hex: str
    coordinate_unit: str = METRE
    schema_version: str = GROSS_WALL_GEOMETRY_SCHEMA_VERSION


@dataclass(frozen=True)
class GrossWallGeometryResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: GrossWallGeometryRecord | None = None
    schema_version: str = GROSS_WALL_GEOMETRY_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream_reasons: str,
) -> GrossWallGeometryResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return GrossWallGeometryResult(
        status=status,
        reason_codes=tuple(
            dict.fromkeys([reason, *(str(r) for r in upstream_reasons if str(r))])
        ),
        record=None,
    )


class GrossWallGeometryAuthority:
    """Sealed selector-only lookup for published gross wall geometry records."""

    def __init__(
        self,
        results: Mapping[_Key, GrossWallGeometryResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("GrossWallGeometryAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: GrossWallGeometrySelector) -> GrossWallGeometryResult:
        if type(selector) is not GrossWallGeometrySelector:
            raise TypeError("selector must be GrossWallGeometrySelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                GROSS_WALL_GEOMETRY_RECORD_UNAVAILABLE,
            ),
        )


class GrossWallGeometryProducer:
    """Trusted writer boundary for authenticated gross wall geometry."""

    def __init__(
        self,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("GrossWallGeometryProducer must be obtained from create() or from_authorities()")
        self._results: dict[_Key, GrossWallGeometryResult] = {}

    @classmethod
    def create(cls) -> "GrossWallGeometryProducer":
        return cls(_seal=_PRODUCER_SEAL)

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: object = None,
        physical_scale_authority: object = None,
        wall_height_authority: object = None,
        host_frame_authority: object = None,
    ) -> "GrossWallGeometryProducer":
        producer = cls(_seal=_PRODUCER_SEAL)
        producer._wall_candidates = physical_wall_candidate_authority
        producer._scale = physical_scale_authority
        producer._height = wall_height_authority
        producer._frame = host_frame_authority
        return producer

    def authority(self) -> GrossWallGeometryAuthority:
        return GrossWallGeometryAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def register_geometry(
        self,
        *,
        selector: GrossWallGeometrySelector,
        wall_local_frame_id: str,
        length_m: float,
        height_m: float,
    ) -> GrossWallGeometryResult:
        if type(selector) is not GrossWallGeometrySelector:
            raise TypeError("selector must be GrossWallGeometrySelector")
        if not math.isfinite(length_m) or length_m <= 0:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                GROSS_WALL_GEOMETRY_INVALID,
            )
        if not math.isfinite(height_m) or height_m <= 0:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                GROSS_WALL_GEOMETRY_INVALID,
            )
        frame_id = _required(wall_local_frame_id, "wall_local_frame_id")

        polygon = box(0.0, 0.0, length_m, height_m)
        gross_area_m2 = round(length_m * height_m, 12)
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "wall_local_frame_id": frame_id,
            "length_m": round(length_m, 12),
            "height_m": round(height_m, 12),
            "gross_area_m2": gross_area_m2,
            "polygon_wkb_hex": polygon.wkb_hex,
            "coordinate_unit": METRE,
            "schema_version": GROSS_WALL_GEOMETRY_SCHEMA_VERSION,
        }
        record_id = stable_contract_id("gross_wall_geometry", payload, digest_chars=32)
        record = GrossWallGeometryRecord(record_id=record_id, **payload)
        result = GrossWallGeometryResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(GROSS_WALL_GEOMETRY_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = result
        return result
