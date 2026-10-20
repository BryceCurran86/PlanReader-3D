"""Producer-Owned Source Plan Drawing Sheet Registration & North Rotation Alignment Shadow Authority.

Workstream C Item 23:
Computes 2D affine similarity transformation parameters (translation, scale
normalization, project north vs sheet rotation) between disparate drawing sheets
using structural grid intersection control points, mapping all sheets into a
unified Global Project Coordinate System (GPCS).

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_ALIGN_SEAL = object()


@dataclass(frozen=True)
class SheetControlPointRecord:
    point_name: str
    local_pt: Tuple[float, float]
    global_pt: Tuple[float, float]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "point_name": self.point_name,
            "local_pt": list(self.local_pt),
            "global_pt": list(self.global_pt),
        }


@dataclass(frozen=True)
class SheetAlignmentTransformRecord:
    sheet_id: str
    scale_factor: float
    rotation_deg: float
    translation_x: float
    translation_y: float
    residual_error_pt: float
    control_points: Tuple[SheetControlPointRecord, ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "sheet_id": self.sheet_id,
            "scale_factor": self.scale_factor,
            "rotation_deg": self.rotation_deg,
            "translation_x": self.translation_x,
            "translation_y": self.translation_y,
            "residual_error_pt": self.residual_error_pt,
            "control_points": [cp.to_dict() for cp in self.control_points],
        }

    def transform_point(self, local_pt: Tuple[float, float]) -> Tuple[float, float]:
        rad = math.radians(self.rotation_deg)
        cos_t = math.cos(rad)
        sin_t = math.sin(rad)
        x = self.scale_factor * (local_pt[0] * cos_t - local_pt[1] * sin_t) + self.translation_x
        y = self.scale_factor * (local_pt[0] * sin_t + local_pt[1] * cos_t) + self.translation_y
        return (round(x, 4), round(y, 4))


@dataclass(frozen=True)
class SheetRegistrationAlignmentReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_registered_sheets: int
    transforms: Tuple[SheetAlignmentTransformRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _ALIGN_SEAL:
            raise TypeError("SheetRegistrationAlignmentReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_registered_sheets": self.total_registered_sheets,
            "transforms": [t.to_dict() for t in self.transforms],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


class SourceSheetRegistrationAlignmentShadowAuthority:
    """Computes similarity transformations between sheet coordinate space and global project space."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_sheet_alignment(
        self,
        *,
        sheet_id: str,
        control_point_1: SheetControlPointRecord,
        control_point_2: SheetControlPointRecord,
    ) -> SheetAlignmentTransformRecord:
        p1 = control_point_1.local_pt
        p2 = control_point_2.local_pt
        P1 = control_point_1.global_pt
        P2 = control_point_2.global_pt

        d_local = _pt_dist(p1, p2)
        d_global = _pt_dist(P1, P2)

        if d_local < 1e-4:
            raise ValueError("Control points are coincident in local space")

        scale = d_global / d_local

        theta_local = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        theta_global = math.atan2(P2[1] - P1[1], P2[0] - P1[0])
        theta = theta_global - theta_local
        theta_deg = math.degrees(theta) % 360.0

        cos_t = math.cos(theta)
        sin_t = math.sin(theta)

        # tx, ty from P1
        tx = P1[0] - scale * (p1[0] * cos_t - p1[1] * sin_t)
        ty = P1[1] - scale * (p1[0] * sin_t + p1[1] * cos_t)

        # Check residual error at P2
        pred_P2_x = scale * (p2[0] * cos_t - p2[1] * sin_t) + tx
        pred_P2_y = scale * (p2[0] * sin_t + p2[1] * cos_t) + ty
        residual = _pt_dist((pred_P2_x, pred_P2_y), P2)

        return SheetAlignmentTransformRecord(
            sheet_id=sheet_id,
            scale_factor=round(scale, 6),
            rotation_deg=round(theta_deg, 4),
            translation_x=round(tx, 4),
            translation_y=round(ty, 4),
            residual_error_pt=round(residual, 6),
            control_points=(control_point_1, control_point_2),
        )

    def compile_alignment_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        transforms: Sequence[SheetAlignmentTransformRecord],
    ) -> SheetRegistrationAlignmentReceipt:
        t_tuple = tuple(transforms)
        total = len(t_tuple)

        receipt_id = stable_contract_id(
            "ALIGNMENT_RECEIPT",
            (document_id, revision_id, source_sha256, total),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return SheetRegistrationAlignmentReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_registered_sheets=total,
            transforms=t_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_ALIGN_SEAL,
        )
