"""Producer-Owned Source External Balcony & Terrace Fall Slope Drainage Shadow Authority.

Workstream B Item 18:
Extracts balcony and terrace boundaries, evaluates drainage fall slopes (e.g. 1:100),
calculates threshold weather step-downs, determines variable screed bedding volume,
and tracks linear strip drain and rainwater outlet positions.

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

_BALCONY_SEAL = object()


@dataclass(frozen=True)
class BalconyDrainageRecord:
    balcony_id: str
    room_id: str
    area_pt2: float
    fall_ratio_1_in_n: float
    fall_distance_pt: float
    vertical_fall_pt: float
    threshold_stepdown_pt: float
    screed_min_thickness_pt: float
    screed_max_thickness_pt: float
    screed_volume_pt3: float
    strip_drain_length_pt: float

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "balcony_id": self.balcony_id,
            "room_id": self.room_id,
            "area_pt2": self.area_pt2,
            "fall_ratio_1_in_n": self.fall_ratio_1_in_n,
            "fall_distance_pt": self.fall_distance_pt,
            "vertical_fall_pt": self.vertical_fall_pt,
            "threshold_stepdown_pt": self.threshold_stepdown_pt,
            "screed_min_thickness_pt": self.screed_min_thickness_pt,
            "screed_max_thickness_pt": self.screed_max_thickness_pt,
            "screed_volume_pt3": self.screed_volume_pt3,
            "strip_drain_length_pt": self.strip_drain_length_pt,
        }


@dataclass(frozen=True)
class BalconyDrainageFallReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_balconies_count: int
    total_balcony_area_pt2: float
    total_screed_volume_pt3: float
    total_strip_drain_length_pt: float
    balconies: Tuple[BalconyDrainageRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _BALCONY_SEAL:
            raise TypeError("BalconyDrainageFallReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_balconies_count": self.total_balconies_count,
            "total_balcony_area_pt2": self.total_balcony_area_pt2,
            "total_screed_volume_pt3": self.total_screed_volume_pt3,
            "total_strip_drain_length_pt": self.total_strip_drain_length_pt,
            "balconies": [b.to_dict() for b in self.balconies],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceBalconyDrainageFallShadowAuthority:
    """Calculates drainage falls, weather step-downs, and variable-thickness screed volumes."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_balcony_drainage(
        self,
        *,
        room_id: str,
        area_pt2: float,
        fall_distance_pt: float,
        fall_ratio_1_in_n: float = 0.0,
        threshold_stepdown_pt: float = 0.0,
        screed_min_thickness_pt: float = 0.0,
        strip_drain_length_pt: float = 0.0,
    ) -> BalconyDrainageRecord:
        ratio = fall_ratio_1_in_n
        vert_fall = fall_distance_pt / ratio if ratio > 0.0 else 0.0
        screed_max = screed_min_thickness_pt + vert_fall
        screed_avg = screed_min_thickness_pt + (vert_fall / 2.0)
        screed_vol = area_pt2 * screed_avg

        balcony_id = stable_contract_id(
            "BALCONY_DRAIN",
            (room_id, round(area_pt2, 2), round(fall_distance_pt, 2), ratio),
        )

        return BalconyDrainageRecord(
            balcony_id=balcony_id,
            room_id=room_id,
            area_pt2=round(area_pt2, 4),
            fall_ratio_1_in_n=ratio,
            fall_distance_pt=round(fall_distance_pt, 4),
            vertical_fall_pt=round(vert_fall, 4),
            threshold_stepdown_pt=round(threshold_stepdown_pt, 4),
            screed_min_thickness_pt=round(screed_min_thickness_pt, 4),
            screed_max_thickness_pt=round(screed_max, 4),
            screed_volume_pt3=round(screed_vol, 4),
            strip_drain_length_pt=round(strip_drain_length_pt, 4),
        )

    def compile_balcony_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        balconies: Sequence[BalconyDrainageRecord],
    ) -> BalconyDrainageFallReceipt:
        b_tuple = tuple(balconies)
        total = len(b_tuple)
        total_area = sum(b.area_pt2 for b in b_tuple)
        total_screed = sum(b.screed_volume_pt3 for b in b_tuple)
        total_drain = sum(b.strip_drain_length_pt for b in b_tuple)

        receipt_id = stable_contract_id(
            "BALCONY_RECEIPT",
            (document_id, revision_id, source_sha256, total, round(total_screed, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return BalconyDrainageFallReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_balconies_count=total,
            total_balcony_area_pt2=round(total_area, 4),
            total_screed_volume_pt3=round(total_screed, 4),
            total_strip_drain_length_pt=round(total_drain, 4),
            balconies=b_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_BALCONY_SEAL,
        )
