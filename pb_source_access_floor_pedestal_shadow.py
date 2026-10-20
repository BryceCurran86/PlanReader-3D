"""
pb_source_access_floor_pedestal_shadow.py

Authoritative shadow-mode extraction and quantification for modular raised access
flooring systems, 600x600mm panels, pedestal stanchion grids, and underfloor air plenums.

Non-negotiable constraints:
- Status: CANDIDATE
- commercial_projection_allowed: False
- takeoff_eligible: False
- Global snap tolerance: 2.5 pt
"""

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5


class AccessFloorGrade(str, Enum):
    MEDIUM_GRADE = "MEDIUM_GRADE"
    HEAVY_GRADE = "HEAVY_GRADE"
    EXTRA_HEAVY_GRADE = "EXTRA_HEAVY_GRADE"


@dataclass
class AccessFloorZoneSpec:
    zone_id: str
    room_id: str
    boundary_polygon: List[Tuple[float, float]]
    grade: AccessFloorGrade = AccessFloorGrade.HEAVY_GRADE
    ffh_mm: float = 300.0
    panel_size_mm: float = 600.0
    has_underfloor_insulation: bool = False
    level_id: str = "L1"
    source_tag: str = ""


@dataclass
class AccessFloorQuantities:
    total_raised_floor_area_m2: float
    total_perimeter_trim_length_m: float
    total_panel_count: int
    total_pedestal_count: int
    total_plenum_volume_m3: float


@dataclass
class AccessFloorExtractionResult:
    zones: List[AccessFloorZoneSpec]
    quantities: AccessFloorQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceAccessFloorPedestalShadowAuthority:
    """Authority for analyzing raised access flooring and pedestal stanchion grids in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def compute_polygon_area(points: List[Tuple[float, float]]) -> float:
        n = len(points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0

    @staticmethod
    def compute_polygon_perimeter(points: List[Tuple[float, float]]) -> float:
        n = len(points)
        if n < 2:
            return 0.0
        perim = 0.0
        for i in range(n):
            j = (i + 1) % n
            perim += math.hypot(points[j][0] - points[i][0], points[j][1] - points[i][1])
        return perim

    @staticmethod
    def parse_access_floor_tag(tag: str) -> Tuple[AccessFloorGrade, float, float]:
        """
        Parses tag, e.g.:
        'RAISED ACCESS FLOOR 600x600 HEAVY GRADE 300 FFH' or 'ACCESS FLOOR 150 FFH MEDIUM'
        Returns (grade, ffh_mm, panel_size_mm)
        """
        clean = tag.upper().strip()

        # Grade
        if "EXTRA" in clean:
            grade = AccessFloorGrade.EXTRA_HEAVY_GRADE
        elif "MEDIUM" in clean:
            grade = AccessFloorGrade.MEDIUM_GRADE
        else:
            grade = AccessFloorGrade.HEAVY_GRADE

        # FFH: (\d+)\s*(?:MM)?\s*(?:FFH|HEIGHT|VOID)
        ffh_match = re.search(r"(\d+)\s*(?:MM)?\s*(?:FFH|HEIGHT|VOID)", clean)
        ffh_mm = float(ffh_match.group(1)) if ffh_match else 300.0

        # Panel size
        p_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", clean)
        panel_size_mm = float(p_match.group(1)) if p_match else 600.0

        return grade, ffh_mm, panel_size_mm

    @classmethod
    def evaluate_access_flooring(
        cls,
        zones: List[AccessFloorZoneSpec],
        drawing_scale: float = 1.0
    ) -> AccessFloorExtractionResult:
        total_area_m2 = 0.0
        total_trim_m = 0.0
        total_panels = 0
        total_pedestals = 0
        total_plenum_vol_m3 = 0.0

        for z in zones:
            raw_area = cls.compute_polygon_area(z.boundary_polygon)
            area_m2 = raw_area * (drawing_scale ** 2)
            total_area_m2 += area_m2

            raw_perim = cls.compute_polygon_perimeter(z.boundary_polygon)
            perim_m = raw_perim * drawing_scale
            total_trim_m += perim_m

            # Panel count
            panel_m = z.panel_size_mm / 1000.0
            panel_area = panel_m * panel_m
            panels = math.ceil(area_m2 / panel_area) if area_m2 > 0 else 0
            total_panels += panels

            # Pedestals count: Grid points + edge boundaries
            pedestals = math.ceil((area_m2 / panel_area) + (perim_m / (2.0 * panel_m)) + 1.0) if area_m2 > 0 else 0
            total_pedestals += pedestals

            # Plenum volume
            ffh_m = z.ffh_mm / 1000.0
            total_plenum_vol_m3 += area_m2 * ffh_m

        quantities = AccessFloorQuantities(
            total_raised_floor_area_m2=round(total_area_m2, 3),
            total_perimeter_trim_length_m=round(total_trim_m, 3),
            total_panel_count=total_panels,
            total_pedestal_count=total_pedestals,
            total_plenum_volume_m3=round(total_plenum_vol_m3, 3)
        )

        return AccessFloorExtractionResult(
            zones=zones,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"zone_count": str(len(zones))}
        )
