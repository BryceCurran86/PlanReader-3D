"""
pb_source_loading_dock_leveler_bumper_shadow.py

Authoritative shadow-mode extraction and takeoff for loading dock leveler pits,
embed curb angles, and heavy-duty dock bumpers.

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


class DockLevelerType(str, Enum):
    HYDRAULIC_DOCK_LEVELER = "HYDRAULIC_DOCK_LEVELER"
    AIR_POWERED_DOCK_LEVELER = "AIR_POWERED_DOCK_LEVELER"
    MECHANICAL_SPRING_LEVELER = "MECHANICAL_SPRING_LEVELER"
    VERTICAL_STORING_LEVELER = "VERTICAL_STORING_LEVELER"
    EDGE_OF_DOCK_LEVELER = "EDGE_OF_DOCK_LEVELER"


class DockBumperType(str, Enum):
    LAMINATED_RUBBER_BUMPER = "LAMINATED_RUBBER_BUMPER"
    MOLDED_RUBBER_BUMPER = "MOLDED_RUBBER_BUMPER"
    STEEL_FACED_BUMPER = "STEEL_FACED_BUMPER"


@dataclass
class DockLevelerPitSpec:
    dock_id: str
    leveler_type: DockLevelerType = DockLevelerType.HYDRAULIC_DOCK_LEVELER
    boundary_polygon: List[Tuple[float, float]] = field(default_factory=list)
    pit_width_m: float = 1.83
    pit_length_m: float = 2.44
    pit_depth_mm: float = 500.0
    bumper_type: DockBumperType = DockBumperType.LAMINATED_RUBBER_BUMPER
    bumpers_count: int = 2
    curb_angle_embed_meters: float = 6.71  # 3-sided curb embed
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class DockLevelerQuantities:
    total_dock_positions: int = 0
    total_pit_area_m2: float = 0.0
    total_pit_void_volume_m3: float = 0.0
    total_curb_angle_meters: float = 0.0
    total_bumpers_count: int = 0
    positions_by_type: Dict[str, int] = field(default_factory=dict)
    bumpers_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class DockLevelerExtractionResult:
    docks: List[DockLevelerPitSpec] = field(default_factory=list)
    quantities: DockLevelerQuantities = field(default_factory=DockLevelerQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceLoadingDockLevelerBumperShadowAuthority:
    """Authoritative shadow evaluator for loading dock pits, levelers, and bumpers."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses loading dock leveler schedule callouts.
        Example strings:
          - "1830x2440 HYDRAULIC DOCK LEVELER PIT 500mm DEEP W/ 2x LAMINATED BUMPERS & EMBED CURB ANGLES"
          - "2130x2440 AIR-POWERED DOCK LEVELER PIT 600mm DEEP 2x STEEL-FACED BUMPERS"
          - "VERTICAL STORING DOCK LEVELER PIT 300mm DEEP"
          - "EDGE OF DOCK LEVELER"
        """
        clean = text.upper()
        res = {
            "leveler_type": DockLevelerType.HYDRAULIC_DOCK_LEVELER,
            "pit_width_m": 1.83,
            "pit_length_m": 2.44,
            "pit_depth_mm": 500.0,
            "bumper_type": DockBumperType.LAMINATED_RUBBER_BUMPER,
            "bumpers_count": 2,
        }

        # Leveler Typology
        if "AIR" in clean or "AIR-POWERED" in clean or "AIR BAG" in clean:
            res["leveler_type"] = DockLevelerType.AIR_POWERED_DOCK_LEVELER
        elif "VERTICAL" in clean or "VERT-STORING" in clean:
            res["leveler_type"] = DockLevelerType.VERTICAL_STORING_LEVELER
            res["pit_depth_mm"] = 300.0
        elif "EDGE OF DOCK" in clean or "EOD" in clean:
            res["leveler_type"] = DockLevelerType.EDGE_OF_DOCK_LEVELER
            res["pit_depth_mm"] = 0.0
        elif "MECHANICAL" in clean or "SPRING" in clean:
            res["leveler_type"] = DockLevelerType.MECHANICAL_SPRING_LEVELER
        else:
            res["leveler_type"] = DockLevelerType.HYDRAULIC_DOCK_LEVELER

        # Bumper Typology
        if "STEEL" in clean or "STEEL-FACED" in clean:
            res["bumper_type"] = DockBumperType.STEEL_FACED_BUMPER
        elif "MOLDED" in clean:
            res["bumper_type"] = DockBumperType.MOLDED_RUBBER_BUMPER
        else:
            res["bumper_type"] = DockBumperType.LAMINATED_RUBBER_BUMPER

        # Dimensions: 1830x2440, 2130x2440 or 1.83x2.44m
        dim_match = re.search(r'(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)', clean)
        if dim_match:
            try:
                v1 = float(dim_match.group(1))
                v2 = float(dim_match.group(2))
                if v1 > 50.0:  # in mm
                    v1 /= 1000.0
                    v2 /= 1000.0
                res["pit_width_m"] = min(v1, v2)
                res["pit_length_m"] = max(v1, v2)
            except ValueError:
                pass

        # Pit depth: 500mm DEEP, 600mm DEEP, 300mm DEPTH
        depth_match = re.search(r'(\d{2,4})\s*MM\s*(?:DEEP|DEPTH)?', clean)
        if depth_match:
            try:
                d = float(depth_match.group(1))
                if 100.0 <= d <= 1200.0:
                    res["pit_depth_mm"] = d
            except ValueError:
                pass

        # Bumper counts: 2x LAMINATED BUMPERS, 4 BUMPERS
        bmp_match = re.search(r'(\d+)\s*[xX]?\s*(?:LAMINATED|MOLDED|STEEL-FACED)?\s*BUMPER', clean)
        if bmp_match:
            try:
                res["bumpers_count"] = int(bmp_match.group(1))
            except ValueError:
                res["bumpers_count"] = 2

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @staticmethod
    def calculate_polygon_area(poly: List[Tuple[float, float]], scale_ratio: float = 0.001) -> float:
        if len(poly) < 3:
            return 0.0
        n = len(poly)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            xi, yi = poly[i]
            xj, yj = poly[j]
            area += (xi * yj) - (xj * yi)
        area_m2 = abs(area) * 0.5 * (scale_ratio ** 2)
        return round(area_m2, 4)

    @classmethod
    def evaluate_docks(
        cls,
        raw_docks_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> DockLevelerExtractionResult:
        """
        Authoritative shadow extraction for loading dock pits, levelers, and bumpers.
        """
        extracted_docks: List[DockLevelerPitSpec] = []
        tot_pit_area_m2 = 0.0
        tot_pit_volume_m3 = 0.0
        tot_curb_m = 0.0
        tot_bumpers = 0

        pos_by_type: Dict[str, int] = {}
        bmp_by_type: Dict[str, int] = {}

        for item in raw_docks_data:
            dock_id = item.get("dock_id", f"DK_{len(extracted_docks)+1:02d}")
            raw_poly = item.get("boundary_polygon", [])
            snapped_poly = [cls.snap_point(pt) for pt in raw_poly]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ltype_val = item.get("leveler_type", parsed["leveler_type"])
            if isinstance(ltype_val, str):
                try:
                    ltype = DockLevelerType(ltype_val)
                except ValueError:
                    ltype = DockLevelerType.HYDRAULIC_DOCK_LEVELER
            else:
                ltype = ltype_val

            bmptype_val = item.get("bumper_type", parsed["bumper_type"])
            if isinstance(bmptype_val, str):
                try:
                    bmptype = DockBumperType(bmptype_val)
                except ValueError:
                    bmptype = DockBumperType.LAMINATED_RUBBER_BUMPER
            else:
                bmptype = bmptype_val

            w_m = float(item.get("pit_width_m", parsed["pit_width_m"]))
            l_m = float(item.get("pit_length_m", parsed["pit_length_m"]))
            d_mm = float(item.get("pit_depth_mm", parsed["pit_depth_mm"]))
            bmp_cnt = int(item.get("bumpers_count", parsed["bumpers_count"]))

            poly_area = cls.calculate_polygon_area(snapped_poly, scale_ratio)
            if poly_area > 0.0:
                area_m2 = poly_area
            else:
                area_m2 = round(w_m * l_m, 4)

            # 3-sided curb angle embed (rear + 2 sides, front open to apron face)
            curb_m = round(w_m + 2.0 * l_m, 4)
            void_vol_m3 = round(area_m2 * (d_mm / 1000.0), 4)

            spec = DockLevelerPitSpec(
                dock_id=dock_id,
                leveler_type=ltype,
                boundary_polygon=snapped_poly,
                pit_width_m=w_m,
                pit_length_m=l_m,
                pit_depth_mm=d_mm,
                bumper_type=bmptype,
                bumpers_count=bmp_cnt,
                curb_angle_embed_meters=curb_m,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_docks.append(spec)

            tot_pit_area_m2 += area_m2
            tot_pit_volume_m3 += void_vol_m3
            tot_curb_m += curb_m
            tot_bumpers += bmp_cnt

            t_key = ltype.value
            pos_by_type[t_key] = pos_by_type.get(t_key, 0) + 1

            b_key = bmptype.value
            bmp_by_type[b_key] = bmp_by_type.get(b_key, 0) + bmp_cnt

        quantities = DockLevelerQuantities(
            total_dock_positions=len(extracted_docks),
            total_pit_area_m2=round(tot_pit_area_m2, 4),
            total_pit_void_volume_m3=round(tot_pit_volume_m3, 4),
            total_curb_angle_meters=round(tot_curb_m, 4),
            total_bumpers_count=tot_bumpers,
            positions_by_type=pos_by_type,
            bumpers_by_type=bmp_by_type,
        )

        return DockLevelerExtractionResult(
            docks=extracted_docks,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceLoadingDockLevelerBumperShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
