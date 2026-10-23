"""Producer-Owned Source Glazing Mullion & Transom Sub-Framing Geometry Shadow Authority.

Workstream A Item 10 / Workstream B Item 13:
Partitions window opening apertures into individual glass lites, intermediate
vertical mullions, and horizontal transoms. Computes sub-frame linear profiles,
individual pane surface areas, aspect ratios, and total glazing takeoff.

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

_SUBFRAME_SEAL = object()


@dataclass(frozen=True)
class GlassLiteRecord:
    lite_id: str
    bay_index: int
    tier_index: int
    width_pt: float
    height_pt: float
    area_pt2: float
    aspect_ratio: float

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "lite_id": self.lite_id,
            "bay_index": self.bay_index,
            "tier_index": self.tier_index,
            "width_pt": self.width_pt,
            "height_pt": self.height_pt,
            "area_pt2": self.area_pt2,
            "aspect_ratio": self.aspect_ratio,
        }


@dataclass(frozen=True)
class WindowSubframeAssemblyRecord:
    window_id: str
    total_width_pt: float
    total_height_pt: float
    mullion_count: int
    transom_count: int
    mullion_linear_pt: float
    transom_linear_pt: float
    outer_frame_perimeter_pt: float
    total_glazing_net_area_pt2: float
    glass_lites: Tuple[GlassLiteRecord, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "window_id": self.window_id,
            "total_width_pt": self.total_width_pt,
            "total_height_pt": self.total_height_pt,
            "mullion_count": self.mullion_count,
            "transom_count": self.transom_count,
            "mullion_linear_pt": self.mullion_linear_pt,
            "transom_linear_pt": self.transom_linear_pt,
            "outer_frame_perimeter_pt": self.outer_frame_perimeter_pt,
            "total_glazing_net_area_pt2": self.total_glazing_net_area_pt2,
            "glass_lites": [l.to_dict() for l in self.glass_lites],
        }


@dataclass(frozen=True)
class WindowSubframingReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_windows_evaluated: int
    total_lites_count: int
    total_mullion_linear_pt: float
    total_transom_linear_pt: float
    total_glazing_area_pt2: float
    assemblies: Tuple[WindowSubframeAssemblyRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _SUBFRAME_SEAL:
            raise TypeError("WindowSubframingReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_windows_evaluated": self.total_windows_evaluated,
            "total_lites_count": self.total_lites_count,
            "total_mullion_linear_pt": self.total_mullion_linear_pt,
            "total_transom_linear_pt": self.total_transom_linear_pt,
            "total_glazing_area_pt2": self.total_glazing_area_pt2,
            "assemblies": [a.to_dict() for a in self.assemblies],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceGlazingMullionTransomSubframingShadowAuthority:
    """Partitions window openings into sub-frames, calculating mullions, transoms, and lites."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def partition_window_subframe(
        self,
        *,
        window_id: str,
        total_width_pt: float,
        total_height_pt: float,
        mullion_count: int = 0,
        transom_count: int = 0,
        frame_profile_thickness_pt: float = 0.0,
        mullion_profile_width_pt: float = 0.0,
        transom_profile_height_pt: float = 0.0,
    ) -> WindowSubframeAssemblyRecord:
        n_bays = mullion_count + 1
        n_tiers = transom_count + 1

        clear_w = max(0.0, total_width_pt - 2.0 * frame_profile_thickness_pt)
        clear_h = max(0.0, total_height_pt - 2.0 * frame_profile_thickness_pt)

        net_w_for_glass = max(0.0, clear_w - (mullion_count * mullion_profile_width_pt))
        net_h_for_glass = max(0.0, clear_h - (transom_count * transom_profile_height_pt))

        lite_w = net_w_for_glass / n_bays
        lite_h = net_h_for_glass / n_tiers
        lite_area = lite_w * lite_h
        aspect_ratio = lite_w / lite_h if lite_h > 1e-4 else 1.0

        lites: List[GlassLiteRecord] = []
        for tier in range(n_tiers):
            for bay in range(n_bays):
                lite_id = stable_contract_id(
                    "LITE",
                    (window_id, bay, tier, round(lite_w, 2), round(lite_h, 2)),
                )
                lites.append(
                    GlassLiteRecord(
                        lite_id=lite_id,
                        bay_index=bay,
                        tier_index=tier,
                        width_pt=round(lite_w, 4),
                        height_pt=round(lite_h, 4),
                        area_pt2=round(lite_area, 4),
                        aspect_ratio=round(aspect_ratio, 4),
                    )
                )

        outer_perimeter = 2.0 * (total_width_pt + total_height_pt)
        mullion_linear = mullion_count * clear_h
        transom_linear = transom_count * clear_w
        total_net_glazing = lite_area * len(lites)

        return WindowSubframeAssemblyRecord(
            window_id=window_id,
            total_width_pt=round(total_width_pt, 4),
            total_height_pt=round(total_height_pt, 4),
            mullion_count=mullion_count,
            transom_count=transom_count,
            mullion_linear_pt=round(mullion_linear, 4),
            transom_linear_pt=round(transom_linear, 4),
            outer_frame_perimeter_pt=round(outer_perimeter, 4),
            total_glazing_net_area_pt2=round(total_net_glazing, 4),
            glass_lites=tuple(lites),
        )

    def compile_subframing_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        assemblies: Sequence[WindowSubframeAssemblyRecord],
    ) -> WindowSubframingReceipt:
        assys_tuple = tuple(assemblies)
        total = len(assys_tuple)
        total_lites = sum(len(a.glass_lites) for a in assys_tuple)
        total_mullion_lin = sum(a.mullion_linear_pt for a in assys_tuple)
        total_transom_lin = sum(a.transom_linear_pt for a in assys_tuple)
        total_glaze_area = sum(a.total_glazing_net_area_pt2 for a in assys_tuple)

        receipt_id = stable_contract_id(
            "SUBFRAME_RECEIPT",
            (document_id, revision_id, source_sha256, total, total_lites, total_mullion_lin),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return WindowSubframingReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_windows_evaluated=total,
            total_lites_count=total_lites,
            total_mullion_linear_pt=round(total_mullion_lin, 4),
            total_transom_linear_pt=round(total_transom_lin, 4),
            total_glazing_area_pt2=round(total_glaze_area, 4),
            assemblies=assys_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_SUBFRAME_SEAL,
        )
