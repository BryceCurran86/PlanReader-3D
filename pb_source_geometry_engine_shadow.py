"""Producer-Owned Source Geometry Engine Shadow Authority.

Workstream C Item 30:
Delivers an integration-ready source geometry engine that coordinates and unifies
upstream geometric subsystems (structural walls, openings, rooms, ceilings, vertical voids)
into an immutable, sealed compilation receipt for downstream consumption (GPT1 measurement,
GPT2 room takeoff, GPT3 sealed run export/signing, GPT MAX host binding).

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Strict evaluator separation: zero benchmark gold or project-specific hardcoding.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_ENGINE_SEAL = object()

SOURCE_GEOMETRY_ENGINE_RESOLVED = "source_geometry_engine_resolved"
SOURCE_GEOMETRY_ENGINE_CANDIDATE = "source_geometry_engine_candidate"
SOURCE_GEOMETRY_ENGINE_UNAVAILABLE = "source_geometry_engine_unavailable"
GEOMETRY_COMPILATION_EMPTY = "geometry_compilation_empty"


@dataclass(frozen=True)
class CompiledSourcePlanGeometryReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    total_wall_runs_count: int
    total_wall_length_m: float
    total_openings_count: int
    total_opening_void_area_sqm: float
    total_rooms_count: int
    total_internal_floor_area_sqm: float
    total_ceilings_count: int
    total_ceiling_area_sqm: float
    total_vertical_voids_count: int
    total_vertical_void_deduction_sqm: float
    net_floor_area_sqm: float
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: Tuple[str, ...] = (SOURCE_GEOMETRY_ENGINE_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _ENGINE_SEAL:
            raise TypeError("CompiledSourcePlanGeometryReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "page_id": self.page_id,
            "total_wall_runs_count": self.total_wall_runs_count,
            "total_wall_length_m": round(self.total_wall_length_m, 4),
            "total_openings_count": self.total_openings_count,
            "total_opening_void_area_sqm": round(self.total_opening_void_area_sqm, 4),
            "total_rooms_count": self.total_rooms_count,
            "total_internal_floor_area_sqm": round(self.total_internal_floor_area_sqm, 4),
            "total_ceilings_count": self.total_ceilings_count,
            "total_ceiling_area_sqm": round(self.total_ceiling_area_sqm, 4),
            "total_vertical_voids_count": self.total_vertical_voids_count,
            "total_vertical_void_deduction_sqm": round(self.total_vertical_void_deduction_sqm, 4),
            "net_floor_area_sqm": round(self.net_floor_area_sqm, 4),
            "status": self.status.value,
            "reason_codes": list(self.reason_codes),
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class SourceGeometryEngine:
    """Unified engine compiling source drawing geometry into an authenticated receipt."""

    def __init__(self) -> None:
        self._walls: List[Any] = []
        self._openings: List[Any] = []
        self._rooms: List[Any] = []
        self._ceilings: List[Any] = []
        self._vertical_voids: List[Any] = []

    def add_wall_run(self, wall: Any) -> None:
        self._walls.append(wall)

    def add_opening(self, opening: Any) -> None:
        self._openings.append(opening)

    def add_room(self, room: Any) -> None:
        self._rooms.append(room)

    def add_ceiling(self, ceiling: Any) -> None:
        self._ceilings.append(ceiling)

    def add_vertical_void(self, void: Any) -> None:
        self._vertical_voids.append(void)

    def compile_plan_geometry(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        page_id: str,
    ) -> CompiledSourcePlanGeometryReceipt:
        """Compiles registered geometry items into an immutable, authenticated receipt."""
        # Calculate wall totals
        total_wall_len = 0.0
        for w in self._walls:
            total_wall_len += getattr(w, "length_m", 0.0) or getattr(w, "wall_length_m", 0.0)

        # Calculate opening totals
        total_opening_area = 0.0
        for op in self._openings:
            total_opening_area += getattr(op, "opening_area_sqm", 0.0) or getattr(op, "void_area_sqm", 0.0)

        # Calculate room floor totals
        total_floor_area = 0.0
        for rm in self._rooms:
            total_floor_area += getattr(rm, "area_sqm", 0.0) or getattr(rm, "internal_area_sqm", 0.0) or getattr(rm, "internal_floor_area_sq_pt", 0.0) * 0.0001

        # Calculate ceiling totals
        total_clg_area = 0.0
        for clg in self._ceilings:
            total_clg_area += getattr(clg, "area_sqm", 0.0) or getattr(clg, "metric_area_sqm", 0.0)

        # Calculate vertical void deductions
        total_void_deduction = 0.0
        for vd in self._vertical_voids:
            total_void_deduction += getattr(vd, "area_sqm", 0.0)

        net_floor = max(0.0, total_floor_area - total_void_deduction)

        is_empty = (
            len(self._walls) == 0
            and len(self._openings) == 0
            and len(self._rooms) == 0
            and len(self._ceilings) == 0
            and len(self._vertical_voids) == 0
        )

        status = EvidenceResolutionStatus.ABSTAINED if is_empty else EvidenceResolutionStatus.CANDIDATE
        reason_codes = (GEOMETRY_COMPILATION_EMPTY,) if is_empty else (SOURCE_GEOMETRY_ENGINE_RESOLVED, SOURCE_GEOMETRY_ENGINE_CANDIDATE)

        receipt_id = stable_contract_id(
            "COMPILED_GEOM_RECEIPT",
            (document_id, revision_id, source_sha256, page_id, len(self._walls), len(self._openings), len(self._rooms)),
        )

        return CompiledSourcePlanGeometryReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            page_id=page_id,
            total_wall_runs_count=len(self._walls),
            total_wall_length_m=total_wall_len,
            total_openings_count=len(self._openings),
            total_opening_void_area_sqm=total_opening_area,
            total_rooms_count=len(self._rooms),
            total_internal_floor_area_sqm=total_floor_area,
            total_ceilings_count=len(self._ceilings),
            total_ceiling_area_sqm=total_clg_area,
            total_vertical_voids_count=len(self._vertical_voids),
            total_vertical_void_deduction_sqm=total_void_deduction,
            net_floor_area_sqm=net_floor,
            status=status,
            reason_codes=reason_codes,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_ENGINE_SEAL,
        )
