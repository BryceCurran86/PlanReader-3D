"""
pb_source_drywall_shaftwall_deflection_head_shadow.py

Authoritative shadow-mode extraction and drywall partition takeoff for fire-rated drywall walls,
elevator/riser shaftwalls (C-H studs, 25mm Shaftliner), and slotted deflection head joints.

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


class DrywallSystemType(str, Enum):
    STANDARD_FIRE_PARTITION = "STANDARD_FIRE_PARTITION"
    SHAFTWALL_SYSTEM = "SHAFTWALL_SYSTEM"
    HIGH_WALL_CORRIDOR = "HIGH_WALL_CORRIDOR"
    ACOUSTIC_DOUBLE_STUD = "ACOUSTIC_DOUBLE_STUD"


class DeflectionHeadType(str, Enum):
    SLOTTED_DEFLECTION_TRACK = "SLOTTED_DEFLECTION_TRACK"
    DEEP_LEG_NESTED_TRACK = "DEEP_LEG_NESTED_TRACK"
    FIRE_RATED_INTUMESCENT_TRACK = "FIRE_RATED_INTUMESCENT_TRACK"
    STANDARD_FIXED_HEAD = "STANDARD_FIXED_HEAD"


@dataclass
class DrywallPartitionSpec:
    wall_id: str
    system_type: DrywallSystemType = DrywallSystemType.STANDARD_FIRE_PARTITION
    deflection_head_type: DeflectionHeadType = DeflectionHeadType.SLOTTED_DEFLECTION_TRACK
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    wall_height_m: float = 0.0
    stud_width_mm: float = 0.0
    deflection_allowance_mm: float = 25.0
    fire_rating_hours: int = 2
    has_shaftliner_core: bool = False
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class DrywallShaftwallQuantities:
    total_walls_count: int = 0
    total_linear_meters: float = 0.0
    total_wall_area_m2: float = 0.0
    deflection_head_linear_meters: float = 0.0
    shaftwall_linear_meters: float = 0.0
    shaftliner_core_area_m2: float = 0.0
    linear_meters_by_fire_rating: Dict[str, float] = field(default_factory=dict)
    linear_meters_by_system: Dict[str, float] = field(default_factory=dict)


@dataclass
class DrywallShaftwallExtractionResult:
    walls: List[DrywallPartitionSpec] = field(default_factory=list)
    quantities: DrywallShaftwallQuantities = field(default_factory=DrywallShaftwallQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceDrywallShaftwallDeflectionHeadShadowAuthority:
    """Authoritative shadow evaluator for fire-rated drywall partitions and shaftwalls."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses drywall partition and shaftwall annotations.
        Example strings:
          - "92mm STEEL STUD SHAFTWALL 2-HR W/ 25mm SHAFTLINER SLOTTED DEFLECTION HEAD 25mm TRAVEL H=3.6m"
          - "64mm C-STUD FIRE PARTITION 1-HR DEEP LEG DEFLECTION TRACK"
          - "DOUBLE STUD ACOUSTIC WALL 2-HR INTUMESCENT HEAD TRACK"
        """
        clean = text.upper()
        res = {
            "system_type": DrywallSystemType.STANDARD_FIRE_PARTITION,
            "deflection_head_type": DeflectionHeadType.SLOTTED_DEFLECTION_TRACK,
            "wall_height_m": 0.0,
            "stud_width_mm": 0.0,
            "deflection_allowance_mm": 25.0,
            "fire_rating_hours": 2,
            "has_shaftliner_core": False,
        }

        # System Type
        if "SHAFT" in clean or "SHAFTLINER" in clean or "C-H" in clean or "CH-STUD" in clean or "LIFT CORE" in clean:
            res["system_type"] = DrywallSystemType.SHAFTWALL_SYSTEM
            res["has_shaftliner_core"] = True
        elif "DOUBLE STUD" in clean or "TWIN STUD" in clean or "STAGGERED" in clean:
            res["system_type"] = DrywallSystemType.ACOUSTIC_DOUBLE_STUD
        elif "HIGH WALL" in clean or "HIGH-WALL" in clean or "HEAVY GAUGE" in clean:
            res["system_type"] = DrywallSystemType.HIGH_WALL_CORRIDOR
        else:
            res["system_type"] = DrywallSystemType.STANDARD_FIRE_PARTITION

        # Deflection Head Track Type
        if "SLOTTED" in clean:
            res["deflection_head_type"] = DeflectionHeadType.SLOTTED_DEFLECTION_TRACK
        elif "DEEP LEG" in clean or "DEEP-LEG" in clean or "NESTED" in clean:
            res["deflection_head_type"] = DeflectionHeadType.DEEP_LEG_NESTED_TRACK
        elif "INTUMESCENT" in clean or "FIRE-RATED HEAD" in clean or "FIRE RATED HEAD" in clean:
            res["deflection_head_type"] = DeflectionHeadType.FIRE_RATED_INTUMESCENT_TRACK
        elif "FIXED" in clean or "NO DEFLECTION" in clean:
            res["deflection_head_type"] = DeflectionHeadType.STANDARD_FIXED_HEAD
        else:
            res["deflection_head_type"] = DeflectionHeadType.SLOTTED_DEFLECTION_TRACK

        # Stud width: 64mm, 76mm, 92mm, 150mm
        stud_match = re.search(r'(\d{2,3})\s*MM\s*(?:STUD|C-STUD|CH-STUD|STEEL)', clean)
        if stud_match:
            try:
                sw = float(stud_match.group(1))
                if 40.0 <= sw <= 200.0:
                    res["stud_width_mm"] = sw
            except ValueError:
                pass

        # Deflection allowance: 25mm, 20mm, 35mm, 50mm
        defl_match = re.search(r'(?:DEFLECTION|TRAVEL|ALLOWANCE)\s*(?:[=:]?\s*)?(\d{2})\s*MM', clean)
        if not defl_match:
            defl_match = re.search(r'(\d{2})\s*MM\s*(?:DEFLECTION|TRAVEL)', clean)
        if defl_match:
            try:
                da = float(defl_match.group(1))
                if 10.0 <= da <= 100.0:
                    res["deflection_allowance_mm"] = da
            except ValueError:
                pass

        # Fire rating: 1-HR, 2-HR, 3-HR, 4-HR, -/120/120
        frl_match = re.search(r'-\s*/\s*(\d{2,3})\s*/\s*\d{2,3}', clean)
        if frl_match:
            try:
                mins = int(frl_match.group(1))
                res["fire_rating_hours"] = max(1, round(mins / 60))
            except ValueError:
                pass
        else:
            hr_match = re.search(r'(\d+)\s*(?:-|HR|HOUR)\b', clean)
            if hr_match:
                try:
                    h = int(hr_match.group(1))
                    if 1 <= h <= 4:
                        res["fire_rating_hours"] = h
                except ValueError:
                    pass

        # Wall height: H=3.6m, 4.0M HIGH
        h_match = re.search(r'(?:H\s*[=:]?\s*|HEIGHT\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*M\b', clean)
        if not h_match:
            h_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b\s*(?:HIGH|HEIGHT)', clean)
        if h_match:
            try:
                wh = float(h_match.group(1))
                if 1.5 <= wh <= 20.0:
                    res["wall_height_m"] = wh
            except ValueError:
                pass

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
        tot = 0.0
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            tot += math.hypot(x2 - x1, y2 - y1)
        return round(tot * scale_ratio, 4)

    @classmethod
    def evaluate_partitions(
        cls,
        raw_partition_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> DrywallShaftwallExtractionResult:
        """
        Authoritative shadow extraction for fire-rated drywall partitions and deflection heads.
        """
        extracted_walls: List[DrywallPartitionSpec] = []
        tot_linear_m = 0.0
        tot_wall_area_m2 = 0.0
        deflection_head_m = 0.0
        shaftwall_linear_m = 0.0
        shaftliner_area_m2 = 0.0

        m_by_rating: Dict[str, float] = {}
        m_by_system: Dict[str, float] = {}

        for item in raw_partition_data:
            wall_id = item.get("wall_id", f"DW_{len(extracted_walls)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            stype_val = item.get("system_type", parsed["system_type"])
            if isinstance(stype_val, str):
                try:
                    stype = DrywallSystemType(stype_val)
                except ValueError:
                    stype = DrywallSystemType.STANDARD_FIRE_PARTITION
            else:
                stype = stype_val

            head_val = item.get("deflection_head_type", parsed["deflection_head_type"])
            if isinstance(head_val, str):
                try:
                    head_type = DeflectionHeadType(head_val)
                except ValueError:
                    head_type = DeflectionHeadType.SLOTTED_DEFLECTION_TRACK
            else:
                head_type = head_val

            wall_h = float(item.get("wall_height_m", parsed["wall_height_m"]))
            stud_w = float(item.get("stud_width_mm", parsed["stud_width_mm"]))
            defl_allow = float(item.get("deflection_allowance_mm", parsed["deflection_allowance_mm"]))
            rating_hrs = int(item.get("fire_rating_hours", parsed["fire_rating_hours"]))
            has_liner = bool(item.get("has_shaftliner_core", parsed["has_shaftliner_core"]))

            spec = DrywallPartitionSpec(
                wall_id=wall_id,
                system_type=stype,
                deflection_head_type=head_type,
                centerline_points=snapped_pts,
                wall_height_m=wall_h,
                stud_width_mm=stud_w,
                deflection_allowance_mm=defl_allow,
                fire_rating_hours=rating_hrs,
                has_shaftliner_core=has_liner,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_walls.append(spec)

            wall_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            wall_area = wall_len_m * wall_h

            tot_linear_m += wall_len_m
            tot_wall_area_m2 += wall_area

            if head_type != DeflectionHeadType.STANDARD_FIXED_HEAD:
                deflection_head_m += wall_len_m

            if stype == DrywallSystemType.SHAFTWALL_SYSTEM or has_liner:
                shaftwall_linear_m += wall_len_m
                shaftliner_area_m2 += wall_area

            r_key = f"{rating_hrs}HR"
            m_by_rating[r_key] = round(m_by_rating.get(r_key, 0.0) + wall_len_m, 4)

            sys_key = stype.value
            m_by_system[sys_key] = round(m_by_system.get(sys_key, 0.0) + wall_len_m, 4)

        quantities = DrywallShaftwallQuantities(
            total_walls_count=len(extracted_walls),
            total_linear_meters=round(tot_linear_m, 4),
            total_wall_area_m2=round(tot_wall_area_m2, 4),
            deflection_head_linear_meters=round(deflection_head_m, 4),
            shaftwall_linear_meters=round(shaftwall_linear_m, 4),
            shaftliner_core_area_m2=round(shaftliner_area_m2, 4),
            linear_meters_by_fire_rating=m_by_rating,
            linear_meters_by_system=m_by_system,
        )

        return DrywallShaftwallExtractionResult(
            walls=extracted_walls,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceDrywallShaftwallDeflectionHeadShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
