"""
pb_source_plant_screen_acoustic_enclosure_shadow.py

Authoritative shadow-mode extraction and architectural facade takeoff for rooftop plant room
screens, acoustic sound enclosures, structural SHS support posts, and integrated louver doors.

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


class PlantScreenType(str, Enum):
    ARCHITECTURAL_SIGHT_SCREEN = "ARCHITECTURAL_SIGHT_SCREEN"
    CONTINUOUS_ACOUSTIC_LOUVER = "CONTINUOUS_ACOUSTIC_LOUVER"
    WEATHERPROOF_PLANT_ENCLOSURE = "WEATHERPROOF_PLANT_ENCLOSURE"
    SOLID_ACOUSTIC_BARRIER_PANEL = "SOLID_ACOUSTIC_BARRIER_PANEL"


class ScreenSupportType(str, Enum):
    STRUCTURAL_STEEL_SHS = "STRUCTURAL_STEEL_SHS"
    ALUMINIUM_BOX_MULLIONS = "ALUMINIUM_BOX_MULLIONS"
    CANTILEVER_PLINTH_STANCHION = "CANTILEVER_PLINTH_STANCHION"


@dataclass
class PlantScreenSpec:
    screen_id: str
    screen_type: PlantScreenType = PlantScreenType.ARCHITECTURAL_SIGHT_SCREEN
    support_type: ScreenSupportType = ScreenSupportType.STRUCTURAL_STEEL_SHS
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    screen_height_m: float = 2.4
    post_spacing_m: float = 2.0
    integrated_doors_count: int = 0
    door_width_m: float = 1.0
    level_id: str = "ROOF"
    source_callout: str = ""


@dataclass
class PlantScreenQuantities:
    total_screens_count: int = 0
    total_linear_meters: float = 0.0
    total_elevation_area_m2: float = 0.0
    total_support_posts_count: int = 0
    total_integrated_doors_count: int = 0
    sight_screen_linear_meters: float = 0.0
    acoustic_screen_linear_meters: float = 0.0
    linear_meters_by_type: Dict[str, float] = field(default_factory=dict)
    area_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class PlantScreenExtractionResult:
    screens: List[PlantScreenSpec] = field(default_factory=list)
    quantities: PlantScreenQuantities = field(default_factory=PlantScreenQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourcePlantScreenAcousticEnclosureShadowAuthority:
    """Authoritative shadow evaluator for plant room screens and acoustic enclosures."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses plant room screen annotations and schedule callouts.
        Example strings:
          - "2.4m HIGH ARCHITECTURAL SIGHT SCREEN 100x100 SHS POSTS AT 2.0m CTS W/ 1x LOUVER ACCESS DOOR"
          - "CONTINUOUS ACOUSTIC LOUVER ENCLOSURE H=3.0m RW 20dB"
          - "WEATHERPROOF PLANT ENCLOSURE 2.0M HIGH"
        """
        clean = text.upper()
        res = {
            "screen_type": PlantScreenType.ARCHITECTURAL_SIGHT_SCREEN,
            "support_type": ScreenSupportType.STRUCTURAL_STEEL_SHS,
            "screen_height_m": 2.4,
            "post_spacing_m": 2.0,
            "integrated_doors_count": 0,
            "door_width_m": 1.0,
        }

        # Screen Typology
        if "ACOUSTIC" in clean or "SOUND" in clean or "ATTENUAT" in clean or "DECIBEL" in clean or "RW" in clean:
            if "SOLID" in clean or "PANEL" in clean:
                res["screen_type"] = PlantScreenType.SOLID_ACOUSTIC_BARRIER_PANEL
            else:
                res["screen_type"] = PlantScreenType.CONTINUOUS_ACOUSTIC_LOUVER
        elif "WEATHER" in clean or "RAIN" in clean or "STORM" in clean:
            res["screen_type"] = PlantScreenType.WEATHERPROOF_PLANT_ENCLOSURE
        elif "SOLID" in clean:
            res["screen_type"] = PlantScreenType.SOLID_ACOUSTIC_BARRIER_PANEL
        else:
            res["screen_type"] = PlantScreenType.ARCHITECTURAL_SIGHT_SCREEN

        # Support Type
        if "ALUMINIUM" in clean or "ALUM" in clean or "BOX MULLION" in clean:
            res["support_type"] = ScreenSupportType.ALUMINIUM_BOX_MULLIONS
        elif "PLINTH" in clean or "CANTILEVER" in clean or "STANCHION" in clean:
            res["support_type"] = ScreenSupportType.CANTILEVER_PLINTH_STANCHION
        else:
            res["support_type"] = ScreenSupportType.STRUCTURAL_STEEL_SHS

        # Screen Height: 2.4m HIGH, H=3.0m, 2400 HIGH, 3.0M
        h_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b\s*(?:HIGH|HEIGHT)?', clean)
        if h_match:
            try:
                h_val = float(h_match.group(1))
                if 1.0 <= h_val <= 10.0:
                    res["screen_height_m"] = h_val
            except ValueError:
                pass
        else:
            mm_match = re.search(r'(\d{4})\s*(?:MM)?\s*HIGH', clean)
            if mm_match:
                try:
                    res["screen_height_m"] = float(mm_match.group(1)) / 1000.0
                except ValueError:
                    pass

        # Post spacing: POSTS AT 2.0m, 1.8M CENTERS, 2.0M SPACING
        spacing_match = re.search(r'(?:POSTS?\s*(?:AT)?\s*|SPACING\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*M', clean)
        if spacing_match:
            try:
                sp = float(spacing_match.group(1))
                if 0.8 <= sp <= 5.0:
                    res["post_spacing_m"] = sp
            except ValueError:
                pass

        # Integrated Doors: 1x LOUVER ACCESS DOOR, 2 ACCESS DOORS, DOUBLE DOOR
        door_match = re.search(r'(\d+)\s*[xX]?\s*(?:LOUVER\s*)?(?:ACCESS\s*)?DOOR', clean)
        if door_match:
            try:
                res["integrated_doors_count"] = int(door_match.group(1))
            except ValueError:
                res["integrated_doors_count"] = 1
        elif "DOUBLE DOOR" in clean:
            res["integrated_doors_count"] = 2
            res["door_width_m"] = 1.8
        elif "ACCESS DOOR" in clean or "LOUVER DOOR" in clean:
            res["integrated_doors_count"] = 1

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
    def evaluate_screens(
        cls,
        raw_screen_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "ROOF"
    ) -> PlantScreenExtractionResult:
        """
        Authoritative shadow extraction for mechanical plant screens and acoustic enclosures.
        """
        extracted_screens: List[PlantScreenSpec] = []
        tot_linear_m = 0.0
        tot_area_m2 = 0.0
        tot_posts = 0
        tot_doors = 0
        sight_m = 0.0
        acoustic_m = 0.0

        m_by_type: Dict[str, float] = {}
        area_by_type_dict: Dict[str, float] = {}

        for item in raw_screen_data:
            screen_id = item.get("screen_id", f"PS_{len(extracted_screens)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            stype_val = item.get("screen_type", parsed["screen_type"])
            if isinstance(stype_val, str):
                try:
                    stype = PlantScreenType(stype_val)
                except ValueError:
                    stype = PlantScreenType.ARCHITECTURAL_SIGHT_SCREEN
            else:
                stype = stype_val

            suptype_val = item.get("support_type", parsed["support_type"])
            if isinstance(suptype_val, str):
                try:
                    suptype = ScreenSupportType(suptype_val)
                except ValueError:
                    suptype = ScreenSupportType.STRUCTURAL_STEEL_SHS
            else:
                suptype = suptype_val

            screen_h = float(item.get("screen_height_m", parsed["screen_height_m"]))
            post_sp = float(item.get("post_spacing_m", parsed["post_spacing_m"]))
            doors_cnt = int(item.get("integrated_doors_count", parsed["integrated_doors_count"]))
            door_w = float(item.get("door_width_m", parsed["door_width_m"]))

            spec = PlantScreenSpec(
                screen_id=screen_id,
                screen_type=stype,
                support_type=suptype,
                centerline_points=snapped_pts,
                screen_height_m=screen_h,
                post_spacing_m=post_sp,
                integrated_doors_count=doors_cnt,
                door_width_m=door_w,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_screens.append(spec)

            screen_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            screen_area = screen_len_m * screen_h
            posts_for_screen = int(math.ceil(screen_len_m / post_sp)) + 1 if screen_len_m > 0 else 0

            tot_linear_m += screen_len_m
            tot_area_m2 += screen_area
            tot_posts += posts_for_screen
            tot_doors += doors_cnt

            if stype == PlantScreenType.ARCHITECTURAL_SIGHT_SCREEN:
                sight_m += screen_len_m
            elif stype in (PlantScreenType.CONTINUOUS_ACOUSTIC_LOUVER, PlantScreenType.SOLID_ACOUSTIC_BARRIER_PANEL):
                acoustic_m += screen_len_m

            t_key = stype.value
            m_by_type[t_key] = round(m_by_type.get(t_key, 0.0) + screen_len_m, 4)
            area_by_type_dict[t_key] = round(area_by_type_dict.get(t_key, 0.0) + screen_area, 4)

        quantities = PlantScreenQuantities(
            total_screens_count=len(extracted_screens),
            total_linear_meters=round(tot_linear_m, 4),
            total_elevation_area_m2=round(tot_area_m2, 4),
            total_support_posts_count=tot_posts,
            total_integrated_doors_count=tot_doors,
            sight_screen_linear_meters=round(sight_m, 4),
            acoustic_screen_linear_meters=round(acoustic_m, 4),
            linear_meters_by_type=m_by_type,
            area_by_type=area_by_type_dict,
        )

        return PlantScreenExtractionResult(
            screens=extracted_screens,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourcePlantScreenAcousticEnclosureShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
