"""Producer-Owned Source Structural Column and Isolated Pier Boundary Shadow Authority.

Workstream A Items 1 & 4:
Recovers isolated structural columns (circular, rectangular, steel universal columns)
and standalone masonry piers, preventing them from being merged into wall continuous
runs or distorting room polygon enclosures.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_COLUMN_SEAL = object()


class StructuralColumnProfile(str, Enum):
    CIRCULAR = "CIRCULAR"
    RECTANGULAR = "RECTANGULAR"
    UNIVERSAL_COLUMN_STEEL = "UNIVERSAL_COLUMN_STEEL"
    MASONRY_PIER = "MASONRY_PIER"


class ColumnPlacement(str, Enum):
    ISOLATED_IN_ROOM = "ISOLATED_IN_ROOM"
    EMBEDDED_IN_WALL = "EMBEDDED_IN_WALL"
    ENGAGED_PIER = "ENGAGED_PIER"


@dataclass(frozen=True)
class ColumnPierRecord:
    column_id: str
    profile: StructuralColumnProfile
    placement: ColumnPlacement
    boundary_polygon: Tuple[Tuple[float, float], ...]
    centroid: Tuple[float, float]
    cross_sectional_area_pt2: float
    height_pt: float
    volume_pt3: float
    material: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "column_id": self.column_id,
            "profile": self.profile.value,
            "placement": self.placement.value,
            "boundary_polygon": [list(pt) for pt in self.boundary_polygon],
            "centroid": list(self.centroid),
            "cross_sectional_area_pt2": self.cross_sectional_area_pt2,
            "height_pt": self.height_pt,
            "volume_pt3": self.volume_pt3,
            "material": self.material,
        }


@dataclass(frozen=True)
class ColumnPierInventoryReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_columns_count: int
    isolated_columns_count: int
    embedded_columns_count: int
    engaged_piers_count: int
    total_column_volume_pt3: float
    columns: Tuple[ColumnPierRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _COLUMN_SEAL:
            raise TypeError("ColumnPierInventoryReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_columns_count": self.total_columns_count,
            "isolated_columns_count": self.isolated_columns_count,
            "embedded_columns_count": self.embedded_columns_count,
            "engaged_piers_count": self.engaged_piers_count,
            "total_column_volume_pt3": self.total_column_volume_pt3,
            "columns": [c.to_dict() for c in self.columns],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _polygon_area(poly: Sequence[Tuple[float, float]]) -> float:
    """Computes planar area using the shoelace formula."""
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1]
        area -= poly[j][0] * poly[i][1]
    return abs(area) / 2.0


def _polygon_centroid(poly: Sequence[Tuple[float, float]]) -> Tuple[float, float]:
    """Computes polygon centroid coordinates."""
    n = len(poly)
    if n < 3:
        if n == 0:
            return (0.0, 0.0)
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    area2 = 0.0
    cx = 0.0
    cy = 0.0
    for i in range(n):
        j = (i + 1) % n
        cross = poly[i][0] * poly[j][1] - poly[j][0] * poly[i][1]
        area2 += cross
        cx += (poly[i][0] + poly[j][0]) * cross
        cy += (poly[i][1] + poly[j][1]) * cross
    if abs(area2) < 1e-6:
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    area = area2 / 2.0
    return (cx / (6.0 * area), cy / (6.0 * area))


class SourceColumnPierStructuralBoundaryShadowAuthority:
    """Recovers and inventories structural columns and piers."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def create_circular_column(
        self,
        *,
        center_pt: Tuple[float, float],
        diameter_pt: float,
        height_pt: float,
        placement: ColumnPlacement = ColumnPlacement.ISOLATED_IN_ROOM,
        material: str = "CONCRETE",
        num_circle_segments: int = 16,
    ) -> ColumnPierRecord:
        radius = diameter_pt / 2.0
        area = math.pi * (radius ** 2)
        volume = area * height_pt

        # Approximate circular boundary with polygon
        poly = []
        for i in range(num_circle_segments):
            angle = (2.0 * math.pi * i) / num_circle_segments
            x = center_pt[0] + radius * math.cos(angle)
            y = center_pt[1] + radius * math.sin(angle)
            poly.append((round(x, 4), round(y, 4)))

        col_id = stable_contract_id(
            "COL_CIRCULAR",
            (center_pt, diameter_pt, height_pt, placement.value, material),
        )

        return ColumnPierRecord(
            column_id=col_id,
            profile=StructuralColumnProfile.CIRCULAR,
            placement=placement,
            boundary_polygon=tuple(poly),
            centroid=center_pt,
            cross_sectional_area_pt2=round(area, 4),
            height_pt=round(height_pt, 4),
            volume_pt3=round(volume, 4),
            material=material,
        )

    def create_polygonal_column(
        self,
        *,
        profile: StructuralColumnProfile,
        boundary_polygon: Sequence[Tuple[float, float]],
        height_pt: float,
        placement: ColumnPlacement = ColumnPlacement.ISOLATED_IN_ROOM,
        material: str = "CONCRETE",
    ) -> ColumnPierRecord:
        poly_tuple = tuple(boundary_polygon)
        area = _polygon_area(poly_tuple)
        centroid = _polygon_centroid(poly_tuple)
        volume = area * height_pt

        col_id = stable_contract_id(
            "COL_POLY",
            (profile.value, poly_tuple, height_pt, placement.value, material),
        )

        return ColumnPierRecord(
            column_id=col_id,
            profile=profile,
            placement=placement,
            boundary_polygon=poly_tuple,
            centroid=(round(centroid[0], 4), round(centroid[1], 4)),
            cross_sectional_area_pt2=round(area, 4),
            height_pt=round(height_pt, 4),
            volume_pt3=round(volume, 4),
            material=material,
        )

    def compile_column_inventory_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        columns: Sequence[ColumnPierRecord],
    ) -> ColumnPierInventoryReceipt:
        cols_tuple = tuple(columns)
        total = len(cols_tuple)
        isolated = sum(1 for c in cols_tuple if c.placement == ColumnPlacement.ISOLATED_IN_ROOM)
        embedded = sum(1 for c in cols_tuple if c.placement == ColumnPlacement.EMBEDDED_IN_WALL)
        engaged = sum(1 for c in cols_tuple if c.placement == ColumnPlacement.ENGAGED_PIER)
        total_vol = sum(c.volume_pt3 for c in cols_tuple)

        receipt_id = stable_contract_id(
            "COL_INVENTORY_RECEIPT",
            (document_id, revision_id, source_sha256, total, isolated, embedded, engaged),
        )

        status = EvidenceResolutionStatus.CORROBORATED if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return ColumnPierInventoryReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_columns_count=total,
            isolated_columns_count=isolated,
            embedded_columns_count=embedded,
            engaged_piers_count=engaged,
            total_column_volume_pt3=round(total_vol, 4),
            columns=cols_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_COLUMN_SEAL,
        )
