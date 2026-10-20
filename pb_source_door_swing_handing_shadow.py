"""Producer-Owned Source Door Swing Direction & Handing Shadow Authority.

Workstream A Item 8 / Workstream B Item 14:
Detects door swing arcs and radial leaf segments to resolve hinge point,
latch point, swing orientation, and architectural door handing (LH, RH, LHR, RHR)
relative to host wall and room boundary. Computes door swept floor clearance envelope.

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

_SWING_SEAL = object()


class DoorHanding(str, Enum):
    LEFT_HAND_INWARD = "LEFT_HAND_INWARD"
    RIGHT_HAND_INWARD = "RIGHT_HAND_INWARD"
    LEFT_HAND_OUTWARD = "LEFT_HAND_OUTWARD"
    RIGHT_HAND_OUTWARD = "RIGHT_HAND_OUTWARD"
    DOUBLE_EGRESS = "DOUBLE_EGRESS"
    SLIDING_OR_CAVITY = "SLIDING_OR_CAVITY"


@dataclass(frozen=True)
class DoorSwingRecord:
    door_id: str
    handing: DoorHanding
    hinge_pt: Tuple[float, float]
    latch_pt: Tuple[float, float]
    leaf_length_pt: float
    swing_angle_deg: float
    swept_area_pt2: float
    is_swing_obstructed: bool

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "door_id": self.door_id,
            "handing": self.handing.value,
            "hinge_pt": list(self.hinge_pt),
            "latch_pt": list(self.latch_pt),
            "leaf_length_pt": self.leaf_length_pt,
            "swing_angle_deg": self.swing_angle_deg,
            "swept_area_pt2": self.swept_area_pt2,
            "is_swing_obstructed": self.is_swing_obstructed,
        }


@dataclass(frozen=True)
class DoorSwingHandingReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_doors_evaluated: int
    swinging_doors_count: int
    sliding_doors_count: int
    doors: Tuple[DoorSwingRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _SWING_SEAL:
            raise TypeError("DoorSwingHandingReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_doors_evaluated": self.total_doors_evaluated,
            "swinging_doors_count": self.swinging_doors_count,
            "sliding_doors_count": self.sliding_doors_count,
            "doors": [d.to_dict() for d in self.doors],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


class SourceDoorSwingHandingShadowAuthority:
    """Evaluates door swing geometry, handing orientation, and swept floor clearances."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def resolve_swing_door(
        self,
        *,
        door_id: str,
        hinge_pt: Tuple[float, float],
        latch_pt: Tuple[float, float],
        is_left_hand: bool,
        swings_inward: bool,
        swing_angle_deg: float = 0.0,
        is_obstructed: bool = False,
    ) -> DoorSwingRecord:
        leaf_len = _pt_dist(hinge_pt, latch_pt)

        # Swept sector area: (angle / 360) * pi * r^2
        swept = (abs(swing_angle_deg) / 360.0) * math.pi * (leaf_len ** 2)

        if is_left_hand and swings_inward:
            handing = DoorHanding.LEFT_HAND_INWARD
        elif not is_left_hand and swings_inward:
            handing = DoorHanding.RIGHT_HAND_INWARD
        elif is_left_hand and not swings_inward:
            handing = DoorHanding.LEFT_HAND_OUTWARD
        else:
            handing = DoorHanding.RIGHT_HAND_OUTWARD

        return DoorSwingRecord(
            door_id=door_id,
            handing=handing,
            hinge_pt=hinge_pt,
            latch_pt=latch_pt,
            leaf_length_pt=round(leaf_len, 4),
            swing_angle_deg=round(swing_angle_deg, 2),
            swept_area_pt2=round(swept, 4),
            is_swing_obstructed=is_obstructed,
        )

    def resolve_sliding_door(
        self,
        *,
        door_id: str,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
    ) -> DoorSwingRecord:
        travel_len = _pt_dist(start_pt, end_pt)

        return DoorSwingRecord(
            door_id=door_id,
            handing=DoorHanding.SLIDING_OR_CAVITY,
            hinge_pt=start_pt,
            latch_pt=end_pt,
            leaf_length_pt=round(travel_len, 4),
            swing_angle_deg=0.0,
            swept_area_pt2=0.0,
            is_swing_obstructed=False,
        )

    def compile_swing_handing_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        doors: Sequence[DoorSwingRecord],
    ) -> DoorSwingHandingReceipt:
        doors_tuple = tuple(doors)
        total = len(doors_tuple)
        sliding = sum(1 for d in doors_tuple if d.handing == DoorHanding.SLIDING_OR_CAVITY)
        swinging = total - sliding

        receipt_id = stable_contract_id(
            "DOOR_SWING_RECEIPT",
            (document_id, revision_id, source_sha256, total, swinging, sliding),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return DoorSwingHandingReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_doors_evaluated=total,
            swinging_doors_count=swinging,
            sliding_doors_count=sliding,
            doors=doors_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_SWING_SEAL,
        )
