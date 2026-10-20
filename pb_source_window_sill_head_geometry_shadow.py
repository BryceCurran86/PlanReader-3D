"""Producer-Owned Source Glazing Window Sill Height & Head Level Geometry Shadow Authority.

Workstream A Item 9 / Workstream B Item 13:
Reconciles 2D window opening plan footprints with elevation/schedule sill heights
and head heights to compute 3D wall aperture voids, sub-sill apron wall mass,
and overhead lintel/header beam depths, preventing windows from falsely cutting
walls floor-to-ceiling.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_WINDOW_GEO_SEAL = object()


@dataclass(frozen=True)
class WindowVerticalGeometryRecord:
    window_id: str
    wall_id: str
    sill_height_pt: float
    head_height_pt: float
    wall_height_pt: float
    aperture_height_pt: float
    sub_sill_apron_height_pt: float
    overhead_lintel_height_pt: float
    aperture_void_volume_pt3: float
    retained_wall_volume_pt3: float

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "window_id": self.window_id,
            "wall_id": self.wall_id,
            "sill_height_pt": self.sill_height_pt,
            "head_height_pt": self.head_height_pt,
            "wall_height_pt": self.wall_height_pt,
            "aperture_height_pt": self.aperture_height_pt,
            "sub_sill_apron_height_pt": self.sub_sill_apron_height_pt,
            "overhead_lintel_height_pt": self.overhead_lintel_height_pt,
            "aperture_void_volume_pt3": self.aperture_void_volume_pt3,
            "retained_wall_volume_pt3": self.retained_wall_volume_pt3,
        }


@dataclass(frozen=True)
class WindowVerticalGeometryReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_windows_count: int
    total_glazing_void_volume_pt3: float
    total_retained_wall_volume_pt3: float
    windows: Tuple[WindowVerticalGeometryRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _WINDOW_GEO_SEAL:
            raise TypeError("WindowVerticalGeometryReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_windows_count": self.total_windows_count,
            "total_glazing_void_volume_pt3": self.total_glazing_void_volume_pt3,
            "total_retained_wall_volume_pt3": self.total_retained_wall_volume_pt3,
            "windows": [w.to_dict() for w in self.windows],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceWindowSillHeadGeometryShadowAuthority:
    """Computes vertical partition geometry and volume deductions for window openings."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_window_vertical_partition(
        self,
        *,
        window_id: str,
        wall_id: str,
        opening_length_pt: float,
        wall_thickness_pt: float,
        wall_height_pt: float,
        sill_height_pt: float = 25.5,  # ~900mm in pt (at 1:100 scale: 25.5 pt)
        head_height_pt: float = 59.5,  # ~2100mm in pt (at 1:100 scale: 59.5 pt)
    ) -> WindowVerticalGeometryRecord:
        # Clamped vertical bounds
        clamped_sill = max(0.0, min(sill_height_pt, wall_height_pt))
        clamped_head = max(clamped_sill, min(head_height_pt, wall_height_pt))

        aperture_h = clamped_head - clamped_sill
        apron_h = clamped_sill
        lintel_h = max(0.0, wall_height_pt - clamped_head)

        footprint_area = opening_length_pt * wall_thickness_pt
        void_vol = footprint_area * aperture_h
        retained_vol = footprint_area * (apron_h + lintel_h)

        return WindowVerticalGeometryRecord(
            window_id=window_id,
            wall_id=wall_id,
            sill_height_pt=round(clamped_sill, 4),
            head_height_pt=round(clamped_head, 4),
            wall_height_pt=round(wall_height_pt, 4),
            aperture_height_pt=round(aperture_h, 4),
            sub_sill_apron_height_pt=round(apron_h, 4),
            overhead_lintel_height_pt=round(lintel_h, 4),
            aperture_void_volume_pt3=round(void_vol, 4),
            retained_wall_volume_pt3=round(retained_vol, 4),
        )

    def compile_vertical_geometry_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        windows: Sequence[WindowVerticalGeometryRecord],
    ) -> WindowVerticalGeometryReceipt:
        wins_tuple = tuple(windows)
        total = len(wins_tuple)
        total_void = sum(w.aperture_void_volume_pt3 for w in wins_tuple)
        total_retained = sum(w.retained_wall_volume_pt3 for w in wins_tuple)

        receipt_id = stable_contract_id(
            "WINDOW_VERTICAL_RECEIPT",
            (document_id, revision_id, source_sha256, total, total_void, total_retained),
        )

        status = EvidenceResolutionStatus.CORROBORATED if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return WindowVerticalGeometryReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_windows_count=total,
            total_glazing_void_volume_pt3=round(total_void, 4),
            total_retained_wall_volume_pt3=round(total_retained, 4),
            windows=wins_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_WINDOW_GEO_SEAL,
        )
