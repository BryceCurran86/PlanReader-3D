"""
pb_source_expansion_joint_cover_shadow.py

Authoritative shadow-mode extraction and linear takeoff for architectural floor/wall/ceiling
expansion joint cover plate assemblies, elastomeric movement seals, fire barrier blankets,
and sub-joint EPDM moisture collection gutters.

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


class CoverSystemType(str, Enum):
    FLUSH_ELASTOMERIC = "FLUSH_ELASTOMERIC"
    ALL_METAL_HEAVY_DUTY = "ALL_METAL_HEAVY_DUTY"
    SURFACE_MOUNTED_PLATE = "SURFACE_MOUNTED_PLATE"
    VERTICAL_WALL_COVER = "VERTICAL_WALL_COVER"
    CEILING_COVER = "CEILING_COVER"


class JointLocation(str, Enum):
    FLOOR = "FLOOR"
    WALL = "WALL"
    CEILING = "CEILING"
    ROOF = "ROOF"


@dataclass
class ExpansionJointCoverSpec:
    joint_id: str
    location: JointLocation = JointLocation.FLOOR
    cover_system_type: CoverSystemType = CoverSystemType.FLUSH_ELASTOMERIC
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    nominal_gap_width_mm: float = 50.0
    plate_width_mm: float = 150.0
    movement_capacity_mm: float = 25.0
    has_fire_barrier: bool = False
    fire_rating_hours: int = 0
    has_moisture_barrier: bool = False
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class ExpansionJointCoverQuantities:
    total_joints_count: int = 0
    total_linear_meters: float = 0.0
    floor_cover_linear_meters: float = 0.0
    wall_cover_linear_meters: float = 0.0
    ceiling_cover_linear_meters: float = 0.0
    fire_barrier_linear_meters: float = 0.0
    moisture_barrier_linear_meters: float = 0.0
    linear_meters_by_system: Dict[str, float] = field(default_factory=dict)


@dataclass
class ExpansionJointCoverExtractionResult:
    joints: List[ExpansionJointCoverSpec] = field(default_factory=list)
    quantities: ExpansionJointCoverQuantities = field(default_factory=ExpansionJointCoverQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceExpansionJointCoverShadowAuthority:
    """Authoritative shadow evaluator for architectural expansion joint cover assemblies."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Extracts joint gap width, cover profile, location, fire barrier and moisture gutter specs.
        Example text:
          - "50mm GAP FLUSH ELASTOMERIC FLOOR JOINT COVER W/ 2-HR FIRE BARRIER"
          - "EJ-100 HEAVY DUTY ALL-METAL PLATE COVER EPDM GUTTER"
          - "75mm VERTICAL WALL EXPANSION JOINT COVER"
        """
        clean_text = text.upper()
        res = {
            "gap_width_mm": 50.0,
            "plate_width_mm": 150.0,
            "system_type": CoverSystemType.FLUSH_ELASTOMERIC,
            "location": JointLocation.FLOOR,
            "has_fire_barrier": False,
            "fire_rating_hours": 0,
            "has_moisture_barrier": False,
        }

        # Gap width pattern
        gap_match = re.search(r'(?:EJ[-\s]*)?(\d+)(?:\s*MM)?\s*(?:GAP|JOINT|EXPANSION|WIDTH)?', clean_text)
        if gap_match:
            try:
                gw = float(gap_match.group(1))
                if 10.0 <= gw <= 500.0:
                    res["gap_width_mm"] = gw
                    res["plate_width_mm"] = max(gw * 2.0, 100.0)
            except ValueError:
                pass

        # Location
        if "WALL" in clean_text or "VERTICAL" in clean_text:
            res["location"] = JointLocation.WALL
            res["system_type"] = CoverSystemType.VERTICAL_WALL_COVER
        elif "CEILING" in clean_text or "SOFFIT" in clean_text:
            res["location"] = JointLocation.CEILING
            res["system_type"] = CoverSystemType.CEILING_COVER
        elif "ROOF" in clean_text:
            res["location"] = JointLocation.ROOF
            res["has_moisture_barrier"] = True
        else:
            res["location"] = JointLocation.FLOOR

        # Cover system type override
        if "HEAVY DUTY" in clean_text or "ALL-METAL" in clean_text or "ALL METAL" in clean_text:
            res["system_type"] = CoverSystemType.ALL_METAL_HEAVY_DUTY
        elif "SURFACE" in clean_text or "SURFACE-MOUNTED" in clean_text:
            res["system_type"] = CoverSystemType.SURFACE_MOUNTED_PLATE
        elif "FLUSH" in clean_text or "ELASTOMERIC" in clean_text or "SANTOPRENE" in clean_text:
            if res["location"] == JointLocation.FLOOR:
                res["system_type"] = CoverSystemType.FLUSH_ELASTOMERIC

        # Fire barrier
        fb_match = re.search(r'(\d+)\s*(?:-|HR|HOUR)\s*FIRE', clean_text)
        if fb_match:
            res["has_fire_barrier"] = True
            try:
                res["fire_rating_hours"] = int(fb_match.group(1))
            except ValueError:
                res["fire_rating_hours"] = 2
        elif "FIRE BARRIER" in clean_text or "FIRE BLANKET" in clean_text:
            res["has_fire_barrier"] = True
            res["fire_rating_hours"] = 2

        # Moisture barrier gutter
        if "EPDM" in clean_text or "GUTTER" in clean_text or "MOISTURE" in clean_text or "WATERPROOF" in clean_text:
            res["has_moisture_barrier"] = True

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @staticmethod
    def calculate_polyline_length(points: List[Tuple[float, float]], scale_ratio: float = 0.001) -> float:
        if len(points) < 2:
            return 0.0
        total_len = 0.0
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            seg_len = math.hypot(x2 - x1, y2 - y1)
            total_len += seg_len
        return round(total_len * scale_ratio, 4)

    @classmethod
    def evaluate_joints(
        cls,
        raw_joint_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> ExpansionJointCoverExtractionResult:
        """
        Authoritative shadow extraction for expansion joint cover runs.
        """
        extracted_joints: List[ExpansionJointCoverSpec] = []
        tot_linear_m = 0.0
        floor_linear_m = 0.0
        wall_linear_m = 0.0
        ceiling_linear_m = 0.0
        fire_barrier_m = 0.0
        moisture_m = 0.0
        by_system: Dict[str, float] = {}

        for item in raw_joint_data:
            joint_id = item.get("joint_id", f"EJ_{len(extracted_joints)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            gap_width = float(item.get("gap_width_mm", parsed["gap_width_mm"]))
            plate_width = float(item.get("plate_width_mm", parsed["plate_width_mm"]))
            movement_cap = float(item.get("movement_capacity_mm", gap_width * 0.5))

            loc = item.get("location", parsed["location"])
            if isinstance(loc, str):
                try:
                    loc = JointLocation(loc)
                except ValueError:
                    loc = JointLocation.FLOOR

            syst = item.get("cover_system_type", parsed["system_type"])
            if isinstance(syst, str):
                try:
                    syst = CoverSystemType(syst)
                except ValueError:
                    syst = CoverSystemType.FLUSH_ELASTOMERIC

            has_fire = bool(item.get("has_fire_barrier", parsed["has_fire_barrier"]))
            fire_hrs = int(item.get("fire_rating_hours", parsed["fire_rating_hours"]))
            has_moisture = bool(item.get("has_moisture_barrier", parsed["has_moisture_barrier"]))

            spec = ExpansionJointCoverSpec(
                joint_id=joint_id,
                location=loc,
                cover_system_type=syst,
                centerline_points=snapped_pts,
                nominal_gap_width_mm=gap_width,
                plate_width_mm=plate_width,
                movement_capacity_mm=movement_cap,
                has_fire_barrier=has_fire,
                fire_rating_hours=fire_hrs,
                has_moisture_barrier=has_moisture,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_joints.append(spec)

            joint_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            tot_linear_m += joint_len_m

            if loc == JointLocation.FLOOR:
                floor_linear_m += joint_len_m
            elif loc == JointLocation.WALL:
                wall_linear_m += joint_len_m
            elif loc == JointLocation.CEILING:
                ceiling_linear_m += joint_len_m

            if has_fire:
                fire_barrier_m += joint_len_m
            if has_moisture:
                moisture_m += joint_len_m

            sys_key = syst.value
            by_system[sys_key] = round(by_system.get(sys_key, 0.0) + joint_len_m, 4)

        quantities = ExpansionJointCoverQuantities(
            total_joints_count=len(extracted_joints),
            total_linear_meters=round(tot_linear_m, 4),
            floor_cover_linear_meters=round(floor_linear_m, 4),
            wall_cover_linear_meters=round(wall_linear_m, 4),
            ceiling_cover_linear_meters=round(ceiling_linear_m, 4),
            fire_barrier_linear_meters=round(fire_barrier_m, 4),
            moisture_barrier_linear_meters=round(moisture_m, 4),
            linear_meters_by_system=by_system,
        )

        return ExpansionJointCoverExtractionResult(
            joints=extracted_joints,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceExpansionJointCoverShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
