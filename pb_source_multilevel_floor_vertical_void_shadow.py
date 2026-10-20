"""Producer-Owned Multi-Level Floor Alignment and Vertical Void Shadow Authority.

Workstream A Item 10 / Workstream C Item 27:
Solves multi-story and split-level drawings (stairwells, double-height voids,
vertical service shafts/risers) where upper-level room footprints clash with
lower-level ceiling planes or where stair voids are treated as solid floors,
causing false floor takeoffs or missing vertical envelope connections.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, no projection to commercial takeoff.
- Fail-closed on ambiguous, self-intersecting, or uncorroborated void perimeters.
- Preserves 2.5 pt snapping tolerance and zero hallucination of floor slabs.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceAtom,
    EvidenceResolutionStatus,
    stable_contract_id,
)


class VoidKind(str, Enum):
    STAIRWELL = "STAIRWELL"
    DOUBLE_HEIGHT_VOID = "DOUBLE_HEIGHT_VOID"
    SERVICE_RISER = "SERVICE_RISER"
    LIGHTWELL = "LIGHTWELL"
    ESCALATOR = "ESCALATOR"
    OTHER_VERTICAL_PENETRATION = "OTHER_VERTICAL_PENETRATION"


@dataclass(frozen=True)
class LevelDatum:
    level_id: str
    name: str
    elevation_m: float
    floor_to_floor_height_m: float
    page_number: int


@dataclass(frozen=True)
class VerticalVoidEvidence:
    void_id: str
    level_id: str
    underlying_level_id: Optional[str]
    polygon_pts: Tuple[Tuple[float, float], ...]
    void_kind: VoidKind
    area_sqm: float
    perimeter_m: float
    corroborating_evidence: Tuple[str, ...]
    status: EvidenceResolutionStatus
    notes: str
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "void_id": self.void_id,
            "level_id": self.level_id,
            "underlying_level_id": self.underlying_level_id,
            "polygon_pts": [list(pt) for pt in self.polygon_pts],
            "void_kind": self.void_kind.value,
            "area_sqm": round(self.area_sqm, 4),
            "perimeter_m": round(self.perimeter_m, 4),
            "corroborating_evidence": list(self.corroborating_evidence),
            "status": self.status.value,
            "notes": self.notes,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


@dataclass(frozen=True)
class FloorLevelTakeoffAdjustment:
    level_id: str
    gross_floor_area_sqm: float
    void_deductions_sqm: float
    net_floor_area_sqm: float
    subtracted_void_ids: Tuple[str, ...]
    status: EvidenceResolutionStatus
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "level_id": self.level_id,
            "gross_floor_area_sqm": round(self.gross_floor_area_sqm, 4),
            "void_deductions_sqm": round(self.void_deductions_sqm, 4),
            "net_floor_area_sqm": round(self.net_floor_area_sqm, 4),
            "subtracted_void_ids": list(self.subtracted_void_ids),
            "status": self.status.value,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _polygon_area(pts: Sequence[Tuple[float, float]]) -> float:
    """Shoelace formula for polygon area."""
    n = len(pts)
    if n < 3:
        return 0.0
    area = 0.0
    for i in range(n):
        j = (i + 1) % n
        area += pts[i][0] * pts[j][1]
        area -= pts[j][0] * pts[i][1]
    return abs(area) / 2.0


def _polygon_perimeter(pts: Sequence[Tuple[float, float]]) -> float:
    """Compute polygon perimeter."""
    n = len(pts)
    if n < 2:
        return 0.0
    perim = 0.0
    for i in range(n):
        j = (i + 1) % n
        dx = pts[j][0] - pts[i][0]
        dy = pts[j][1] - pts[i][1]
        perim += math.hypot(dx, dy)
    return perim


def _has_self_intersection(pts: Sequence[Tuple[float, float]]) -> bool:
    """Check if polygon edges intersect each other (non-adjacent edges)."""
    n = len(pts)
    if n < 4:
        return False

    def ccw(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> bool:
        return (c[1] - a[1]) * (b[0] - a[0]) > (b[1] - a[1]) * (c[0] - a[0])

    def intersect(
        p1: Tuple[float, float],
        p2: Tuple[float, float],
        p3: Tuple[float, float],
        p4: Tuple[float, float],
    ) -> bool:
        return (ccw(p1, p3, p4) != ccw(p2, p3, p4)) and (ccw(p1, p2, p3) != ccw(p1, p2, p4))

    for i in range(n):
        p1, p2 = pts[i], pts[(i + 1) % n]
        for j in range(i + 2, n):
            if (i == 0 and j == n - 1):
                continue
            p3, p4 = pts[j], pts[(j + 1) % n]
            if intersect(p1, p2, p3, p4):
                return True
    return False


class MultiLevelFloorVerticalVoidShadowAuthority:
    """Shadow authority for vertical floor penetrations and level alignment."""

    def __init__(self) -> None:
        self._levels: dict[str, LevelDatum] = {}

    def register_level(self, level: LevelDatum) -> None:
        self._levels[level.level_id] = level

    def evaluate_vertical_void(
        self,
        level_id: str,
        underlying_level_id: Optional[str],
        polygon_pts: Sequence[Tuple[float, float]],
        corroborating_tokens: Sequence[str],
        scale_ratio: float,
        void_kind_hint: Optional[VoidKind] = None,
    ) -> VerticalVoidEvidence:
        """Evaluates and proves a vertical void polygon on a specific building level.

        scale_ratio: drawing units (points) to real-world meters, e.g. 1 pt = 0.02 m.
        """
        pts_tuple = tuple((float(x), float(y)) for x, y in polygon_pts)
        void_id = stable_contract_id(
            "VOID",
            (level_id, underlying_level_id or "NONE", pts_tuple),
        )

        # Invariant checks
        if len(pts_tuple) < 3:
            return VerticalVoidEvidence(
                void_id=void_id,
                level_id=level_id,
                underlying_level_id=underlying_level_id,
                polygon_pts=pts_tuple,
                void_kind=VoidKind.OTHER_VERTICAL_PENETRATION,
                area_sqm=0.0,
                perimeter_m=0.0,
                corroborating_evidence=(),
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Degenerate polygon: fewer than 3 vertices.",
            )

        if _has_self_intersection(pts_tuple):
            return VerticalVoidEvidence(
                void_id=void_id,
                level_id=level_id,
                underlying_level_id=underlying_level_id,
                polygon_pts=pts_tuple,
                void_kind=VoidKind.OTHER_VERTICAL_PENETRATION,
                area_sqm=0.0,
                perimeter_m=0.0,
                corroborating_evidence=(),
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Geometric defect: self-intersecting void polygon.",
            )

        raw_area_pt2 = _polygon_area(pts_tuple)
        raw_perim_pt = _polygon_perimeter(pts_tuple)

        area_sqm = raw_area_pt2 * (scale_ratio ** 2)
        perimeter_m = raw_perim_pt * scale_ratio

        # Determine void kind and corroboration
        tokens_upper = [t.strip().upper() for t in corroborating_tokens]
        kind = void_kind_hint or VoidKind.OTHER_VERTICAL_PENETRATION

        matched_tokens = []
        for t in tokens_upper:
            if "STAIR" in t:
                kind = VoidKind.STAIRWELL
                matched_tokens.append(t)
            elif "VOID" in t or "DOUBLE HEIGHT" in t:
                kind = VoidKind.DOUBLE_HEIGHT_VOID
                matched_tokens.append(t)
            elif "RISER" in t or "SHAFT" in t or "DUCT" in t:
                kind = VoidKind.SERVICE_RISER
                matched_tokens.append(t)
            elif "LIGHTWELL" in t:
                kind = VoidKind.LIGHTWELL
                matched_tokens.append(t)
            elif "ESCALATOR" in t:
                kind = VoidKind.ESCALATOR
                matched_tokens.append(t)
            elif "CROSS_STROKES" in t or "DIAGONAL_X" in t:
                matched_tokens.append(t)

        # Minimum physical size thresholds
        min_area = 0.10 if kind == VoidKind.SERVICE_RISER else 0.50
        if area_sqm < min_area:
            return VerticalVoidEvidence(
                void_id=void_id,
                level_id=level_id,
                underlying_level_id=underlying_level_id,
                polygon_pts=pts_tuple,
                void_kind=kind,
                area_sqm=area_sqm,
                perimeter_m=perimeter_m,
                corroborating_evidence=tuple(matched_tokens),
                status=EvidenceResolutionStatus.ABSTAINED,
                notes=f"Void area {area_sqm:.3f} m² below minimum threshold {min_area} m².",
            )

        if not matched_tokens:
            return VerticalVoidEvidence(
                void_id=void_id,
                level_id=level_id,
                underlying_level_id=underlying_level_id,
                polygon_pts=pts_tuple,
                void_kind=kind,
                area_sqm=area_sqm,
                perimeter_m=perimeter_m,
                corroborating_evidence=(),
                status=EvidenceResolutionStatus.ABSTAINED,
                notes="Uncorroborated void: no matching text annotation or diagonal cross linework.",
            )

        return VerticalVoidEvidence(
            void_id=void_id,
            level_id=level_id,
            underlying_level_id=underlying_level_id,
            polygon_pts=pts_tuple,
            void_kind=kind,
            area_sqm=area_sqm,
            perimeter_m=perimeter_m,
            corroborating_evidence=tuple(matched_tokens),
            status=EvidenceResolutionStatus.CORROBORATED,
            notes="Corroborated physical vertical void penetration.",
        )

    def compute_level_net_floor_area(
        self,
        level_id: str,
        gross_floor_area_sqm: float,
        voids: Sequence[VerticalVoidEvidence],
    ) -> FloorLevelTakeoffAdjustment:
        """Computes net floor area after deducting corroborated voids for a level."""
        valid_voids = [
            v for v in voids
            if v.level_id == level_id and v.status == EvidenceResolutionStatus.CORROBORATED
        ]

        total_deduction = sum(v.area_sqm for v in valid_voids)
        net_area = max(0.0, gross_floor_area_sqm - total_deduction)

        status = EvidenceResolutionStatus.CORROBORATED if gross_floor_area_sqm > 0 else EvidenceResolutionStatus.ABSTAINED

        return FloorLevelTakeoffAdjustment(
            level_id=level_id,
            gross_floor_area_sqm=gross_floor_area_sqm,
            void_deductions_sqm=total_deduction,
            net_floor_area_sqm=net_area,
            subtracted_void_ids=tuple(v.void_id for v in valid_voids),
            status=status,
        )
