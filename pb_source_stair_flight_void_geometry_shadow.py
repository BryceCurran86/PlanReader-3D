"""Producer-Owned Source Multilevel Stair Tread, Riser & Flight Void Geometry Shadow Authority.

Workstream A Item 7 / Workstream B Item 12:
Extracts staircase flight boundaries, parallel tread line arrays, riser count,
tread going, total flight vertical rise, and slab penetration void footprint
to prevent slabs from sealing over vertical circulation cores.

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

_STAIR_SEAL = object()


class StairLayoutType(str, Enum):
    STRAIGHT_FLIGHT = "STRAIGHT_FLIGHT"
    L_SHAPED_WITH_LANDING = "L_SHAPED_WITH_LANDING"
    U_SHAPED_DOGLEG = "U_SHAPED_DOGLEG"
    SPIRAL_CIRCULAR = "SPIRAL_CIRCULAR"


@dataclass(frozen=True)
class StairFlightRecord:
    flight_id: str
    layout_type: StairLayoutType
    direction: str
    riser_count: int
    tread_count: int
    riser_height_pt: float
    tread_going_pt: float
    flight_width_pt: float
    flight_length_pt: float
    total_rise_pt: float
    pitch_deg: float
    walkline_length_pt: float
    void_polygon: Tuple[Tuple[float, float], ...]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "flight_id": self.flight_id,
            "layout_type": self.layout_type.value,
            "direction": self.direction,
            "riser_count": self.riser_count,
            "tread_count": self.tread_count,
            "riser_height_pt": self.riser_height_pt,
            "tread_going_pt": self.tread_going_pt,
            "flight_width_pt": self.flight_width_pt,
            "flight_length_pt": self.flight_length_pt,
            "total_rise_pt": self.total_rise_pt,
            "pitch_deg": self.pitch_deg,
            "walkline_length_pt": self.walkline_length_pt,
            "void_polygon": [list(pt) for pt in self.void_polygon],
        }


@dataclass(frozen=True)
class StairFlightVoidReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_flights_count: int
    total_risers_count: int
    total_void_area_pt2: float
    flights: Tuple[StairFlightRecord, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _STAIR_SEAL:
            raise TypeError("StairFlightVoidReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_flights_count": self.total_flights_count,
            "total_risers_count": self.total_risers_count,
            "total_void_area_pt2": self.total_void_area_pt2,
            "flights": [f.to_dict() for f in self.flights],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _polygon_area(poly: Sequence[Tuple[float, float]]) -> float:
    n = len(poly)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += poly[i][0] * poly[j][1]
        area -= poly[j][0] * poly[i][1]
    return abs(area) / 2.0


class SourceStairFlightVoidGeometryShadowAuthority:
    """Computes stair flight geometry and upper slab penetration void envelopes."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt

    def compute_straight_flight(
        self,
        *,
        flight_id: str,
        origin_pt: Tuple[float, float],
        direction: str = "UP",
        riser_count: int = 0,
        riser_height_pt: float = 0.0,
        tread_going_pt: float = 0.0,
        flight_width_pt: float = 0.0,
        is_horizontal_run: bool = True,
    ) -> StairFlightRecord:
        tread_count = max(0, riser_count - 1)
        flight_len = tread_count * tread_going_pt
        total_rise = riser_count * riser_height_pt

        pitch_rad = math.atan2(riser_height_pt, tread_going_pt)
        pitch_deg = math.degrees(pitch_rad)
        walkline_len = math.hypot(flight_len, total_rise)

        ox, oy = origin_pt
        if is_horizontal_run:
            void_poly = (
                (round(ox, 4), round(oy, 4)),
                (round(ox + flight_len, 4), round(oy, 4)),
                (round(ox + flight_len, 4), round(oy + flight_width_pt, 4)),
                (round(ox, 4), round(oy + flight_width_pt, 4)),
            )
        else:
            void_poly = (
                (round(ox, 4), round(oy, 4)),
                (round(ox + flight_width_pt, 4), round(oy, 4)),
                (round(ox + flight_width_pt, 4), round(oy + flight_len, 4)),
                (round(ox, 4), round(oy + flight_len, 4)),
            )

        return StairFlightRecord(
            flight_id=flight_id,
            layout_type=StairLayoutType.STRAIGHT_FLIGHT,
            direction=direction.upper(),
            riser_count=riser_count,
            tread_count=tread_count,
            riser_height_pt=round(riser_height_pt, 4),
            tread_going_pt=round(tread_going_pt, 4),
            flight_width_pt=round(flight_width_pt, 4),
            flight_length_pt=round(flight_len, 4),
            total_rise_pt=round(total_rise, 4),
            pitch_deg=round(pitch_deg, 2),
            walkline_length_pt=round(walkline_len, 4),
            void_polygon=void_poly,
        )

    def compile_stair_void_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        flights: Sequence[StairFlightRecord],
    ) -> StairFlightVoidReceipt:
        flights_tuple = tuple(flights)
        total = len(flights_tuple)
        total_risers = sum(f.riser_count for f in flights_tuple)
        total_void_area = sum(_polygon_area(f.void_polygon) for f in flights_tuple)

        receipt_id = stable_contract_id(
            "STAIR_VOID_RECEIPT",
            (document_id, revision_id, source_sha256, total, total_risers, round(total_void_area, 2)),
        )

        status = EvidenceResolutionStatus.CANDIDATE if total > 0 else EvidenceResolutionStatus.ABSTAINED

        return StairFlightVoidReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_flights_count=total,
            total_risers_count=total_risers,
            total_void_area_pt2=round(total_void_area, 4),
            flights=flights_tuple,
            status=status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_STAIR_SEAL,
        )
