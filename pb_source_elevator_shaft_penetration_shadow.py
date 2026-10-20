"""
pb_source_elevator_shaft_penetration_shadow.py

Authoritative shadow-mode extraction and multi-level vertical takeoff for elevator /
lift core shafts, pit depths, overrun clearances, enclosure walls, and landing doors.

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


class ElevatorType(str, Enum):
    PASSENGER_TRACTION = "PASSENGER_TRACTION"
    MRL_TRACTION = "MRL_TRACTION"
    HYDRAULIC = "HYDRAULIC"
    GOODS_FREIGHT = "GOODS_FREIGHT"


@dataclass
class ElevatorLandingDoorSpec:
    level_id: str
    width_mm: float = 1000.0
    height_mm: float = 2100.0
    sill_datum_m: float = 0.0


@dataclass
class ElevatorShaftSpec:
    shaft_id: str
    elevator_type: ElevatorType
    clear_width_mm: float
    clear_depth_mm: float
    wall_thickness_mm: float
    lowest_level_id: str
    highest_level_id: str
    pit_depth_mm: float
    overrun_height_mm: float
    floor_to_floor_heights_m: List[float]
    landing_doors: List[ElevatorLandingDoorSpec] = field(default_factory=list)
    source_annotation: str = ""


@dataclass
class ElevatorShaftQuantities:
    total_shaft_count: int
    total_shaft_vertical_height_m: float
    total_shaft_internal_volume_m3: float
    total_gross_enclosure_wall_area_m2: float
    total_net_enclosure_wall_area_m2: float
    total_landing_door_opening_area_m2: float
    total_guide_rail_length_m: float


@dataclass
class ElevatorShaftExtractionResult:
    shafts: List[ElevatorShaftSpec]
    quantities: ElevatorShaftQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceElevatorShaftPenetrationShadowAuthority:
    """Authority for analyzing multi-level elevator core shafts in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def parse_shaft_annotation(annotation: str) -> Tuple[ElevatorType, float, float, float, float]:
        """
        Parses annotation, e.g.:
        'MRL LIFT SHAFT 2100W x 2400D CLEAR, PIT 1500, OVERRUN 4200'
        Returns (elevator_type, clear_width_mm, clear_depth_mm, pit_depth_mm, overrun_height_mm)
        """
        clean = annotation.upper().strip()

        # Type detection
        if "MRL" in clean:
            el_type = ElevatorType.MRL_TRACTION
        elif "HYDRAULIC" in clean or "HYDR" in clean:
            el_type = ElevatorType.HYDRAULIC
        elif "GOODS" in clean or "FREIGHT" in clean:
            el_type = ElevatorType.GOODS_FREIGHT
        else:
            el_type = ElevatorType.PASSENGER_TRACTION

        # Clear dimensions
        w_match = re.search(r"(\d+)\s*W", clean)
        d_match = re.search(r"(\d+)\s*D", clean)

        if w_match and d_match:
            clear_w = float(w_match.group(1))
            clear_d = float(d_match.group(1))
        else:
            dim_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", clean)
            if dim_match:
                clear_w = float(dim_match.group(1))
                clear_d = float(dim_match.group(2))
            else:
                clear_w, clear_d = 2000.0, 2200.0

        # Pit depth
        pit_match = re.search(r"PIT\s*(\d+)", clean)
        pit_depth_mm = float(pit_match.group(1)) if pit_match else 1500.0

        # Overrun
        ovr_match = re.search(r"(?:OVERRUN|OVR)\s*(\d+)", clean)
        overrun_height_mm = float(ovr_match.group(1)) if ovr_match else 4200.0

        return el_type, clear_w, clear_d, pit_depth_mm, overrun_height_mm

    @classmethod
    def evaluate_shafts(cls, shafts: List[ElevatorShaftSpec]) -> ElevatorShaftExtractionResult:
        total_vert_height_m = 0.0
        total_internal_vol_m3 = 0.0
        total_gross_wall_area_m2 = 0.0
        total_net_wall_area_m2 = 0.0
        total_door_area_m2 = 0.0
        total_rail_len_m = 0.0

        for shaft in shafts:
            # Vertical height = pit + floor-to-floor heights + overrun
            pit_m = shaft.pit_depth_mm / 1000.0
            overrun_m = shaft.overrun_height_mm / 1000.0
            travel_m = sum(shaft.floor_to_floor_heights_m)
            shaft_height_m = pit_m + travel_m + overrun_m
            total_vert_height_m += shaft_height_m

            # Internal clear dimensions
            cw_m = shaft.clear_width_mm / 1000.0
            cd_m = shaft.clear_depth_mm / 1000.0
            total_internal_vol_m3 += cw_m * cd_m * shaft_height_m

            # Enclosure wall centerline perimeter
            # Centerline width = clear_width + wall_thickness
            # Centerline depth = clear_depth + wall_thickness
            thk_m = shaft.wall_thickness_mm / 1000.0
            centerline_perim_m = 2.0 * ((cw_m + thk_m) + (cd_m + thk_m))
            gross_wall_m2 = centerline_perim_m * shaft_height_m
            total_gross_wall_area_m2 += gross_wall_m2

            # Deduct landing door openings
            door_deduction_m2 = 0.0
            for door in shaft.landing_doors:
                dw_m = door.width_mm / 1000.0
                dh_m = door.height_mm / 1000.0
                door_area = dw_m * dh_m
                door_deduction_m2 += door_area
                total_door_area_m2 += door_area

            net_wall_m2 = max(0.0, gross_wall_m2 - door_deduction_m2)
            total_net_wall_area_m2 += net_wall_m2

            # Guide rail takeoff: 4 vertical lines (2 car + 2 counterweight)
            total_rail_len_m += 4.0 * shaft_height_m

        quantities = ElevatorShaftQuantities(
            total_shaft_count=len(shafts),
            total_shaft_vertical_height_m=round(total_vert_height_m, 3),
            total_shaft_internal_volume_m3=round(total_internal_vol_m3, 3),
            total_gross_enclosure_wall_area_m2=round(total_gross_wall_area_m2, 3),
            total_net_enclosure_wall_area_m2=round(total_net_wall_area_m2, 3),
            total_landing_door_opening_area_m2=round(total_door_area_m2, 3),
            total_guide_rail_length_m=round(total_rail_len_m, 3)
        )

        return ElevatorShaftExtractionResult(
            shafts=shafts,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"shaft_count": str(len(shafts))}
        )
