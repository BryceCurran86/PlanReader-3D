"""
pb_source_precast_spandrel_cleat_shadow.py

Authoritative shadow-mode extraction and architectural facade takeoff for precast concrete
spandrel panels, insulated sandwich assemblies, gravity bearing brackets, and slotted tie-backs.

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


class SpandrelPanelType(str, Enum):
    SOLID_PRECAST_SPANDREL = "SOLID_PRECAST_SPANDREL"
    INSULATED_SANDWICH_SPANDREL = "INSULATED_SANDWICH_SPANDREL"
    INTEGRATED_WINDOW_SILL_SPANDREL = "INTEGRATED_WINDOW_SILL_SPANDREL"
    CURVED_RADIUS_SPANDREL = "CURVED_RADIUS_SPANDREL"


class CleatConnectionType(str, Enum):
    GRAVITY_BEARING_BRACKET = "GRAVITY_BEARING_BRACKET"
    TIE_BACK_SLOTTED_CLEAT = "TIE_BACK_SLOTTED_CLEAT"


@dataclass
class PrecastSpandrelSpec:
    panel_id: str
    panel_type: SpandrelPanelType = SpandrelPanelType.SOLID_PRECAST_SPANDREL
    boundary_polygon: List[Tuple[float, float]] = field(default_factory=list)
    panel_length_m: float = 6.0
    panel_height_m: float = 1.2
    thickness_mm: float = 175.0
    gravity_brackets_count: int = 2
    tieback_cleats_count: int = 2
    level_id: str = "L02"
    source_callout: str = ""


@dataclass
class PrecastSpandrelQuantities:
    total_panels_count: int = 0
    total_elevation_area_m2: float = 0.0
    total_concrete_volume_m3: float = 0.0
    total_gravity_brackets_count: int = 0
    total_tieback_cleats_count: int = 0
    total_perimeter_joint_meters: float = 0.0
    area_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class PrecastSpandrelExtractionResult:
    panels: List[PrecastSpandrelSpec] = field(default_factory=list)
    quantities: PrecastSpandrelQuantities = field(default_factory=PrecastSpandrelQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourcePrecastSpandrelCleatShadowAuthority:
    """Authoritative shadow evaluator for architectural precast spandrels and connections."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses architectural precast spandrel panel schedule callouts.
        Example strings:
          - "6000x1200 PRECAST SPANDREL PANEL 175mm THICK W/ 2x GRAVITY BRACKETS & 2x TIE-BACK CLEATS"
          - "7200x1500 INSULATED SANDWICH PRECAST SPANDREL 225mm THICK 4x TIE-BACKS"
          - "INTEGRATED WINDOW SILL SPANDREL PANEL"
        """
        clean = text.upper()
        res = {
            "panel_type": SpandrelPanelType.SOLID_PRECAST_SPANDREL,
            "panel_length_m": 6.0,
            "panel_height_m": 1.2,
            "thickness_mm": 175.0,
            "gravity_brackets_count": 2,
            "tieback_cleats_count": 2,
        }

        # Panel Typology
        if "SANDWICH" in clean or "INSULATED" in clean:
            res["panel_type"] = SpandrelPanelType.INSULATED_SANDWICH_SPANDREL
            res["thickness_mm"] = 225.0
        elif "SILL" in clean or "WINDOW SILL" in clean:
            res["panel_type"] = SpandrelPanelType.INTEGRATED_WINDOW_SILL_SPANDREL
        elif "CURVED" in clean or "RADIUS" in clean:
            res["panel_type"] = SpandrelPanelType.CURVED_RADIUS_SPANDREL
        else:
            res["panel_type"] = SpandrelPanelType.SOLID_PRECAST_SPANDREL

        # Dimensions: 6000x1200 or 7.2x1.5m
        dim_match = re.search(r'(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)', clean)
        if dim_match:
            try:
                v1 = float(dim_match.group(1))
                v2 = float(dim_match.group(2))
                if v1 > 50.0:  # in mm
                    v1 /= 1000.0
                    v2 /= 1000.0
                res["panel_length_m"] = max(v1, v2)
                res["panel_height_m"] = min(v1, v2)
            except ValueError:
                pass

        # Thickness: 175mm, 150mm, 200mm, 225mm THICK
        thk_match = re.search(r'(\d{2,3})\s*MM\s*(?:THICK|THK|DEPTH)?', clean)
        if thk_match:
            try:
                thk = float(thk_match.group(1))
                if 100.0 <= thk <= 400.0:
                    res["thickness_mm"] = thk
            except ValueError:
                pass

        # Gravity brackets: 2x GRAVITY BRACKETS, 2 GRAVITY
        grav_match = re.search(r'(\d+)\s*[xX]?\s*GRAVITY', clean)
        if grav_match:
            try:
                res["gravity_brackets_count"] = int(grav_match.group(1))
            except ValueError:
                res["gravity_brackets_count"] = 2

        # Tie-back cleats: 4x TIE-BACKS, 2 TIE-BACK CLEATS
        tie_match = re.search(r'(\d+)\s*[xX]?\s*TIE[-\s]?BACK', clean)
        if tie_match:
            try:
                res["tieback_cleats_count"] = int(tie_match.group(1))
            except ValueError:
                res["tieback_cleats_count"] = 2

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
    def evaluate_spandrels(
        cls,
        raw_panels_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L02"
    ) -> PrecastSpandrelExtractionResult:
        """
        Authoritative shadow extraction for precast architectural spandrels and connections.
        """
        extracted_panels: List[PrecastSpandrelSpec] = []
        tot_area_m2 = 0.0
        tot_concrete_m3 = 0.0
        tot_gravity_brackets = 0
        tot_tiebacks = 0
        tot_perim_m = 0.0

        area_by_type_dict: Dict[str, float] = {}

        for item in raw_panels_data:
            panel_id = item.get("panel_id", f"SP_{len(extracted_panels)+1:03d}")
            raw_poly = item.get("boundary_polygon", [])
            snapped_poly = [cls.snap_point(pt) for pt in raw_poly]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ptype_val = item.get("panel_type", parsed["panel_type"])
            if isinstance(ptype_val, str):
                try:
                    ptype = SpandrelPanelType(ptype_val)
                except ValueError:
                    ptype = SpandrelPanelType.SOLID_PRECAST_SPANDREL
            else:
                ptype = ptype_val

            l_m = float(item.get("panel_length_m", parsed["panel_length_m"]))
            h_m = float(item.get("panel_height_m", parsed["panel_height_m"]))
            thk_mm = float(item.get("thickness_mm", parsed["thickness_mm"]))
            grav_cnt = int(item.get("gravity_brackets_count", parsed["gravity_brackets_count"]))
            tie_cnt = int(item.get("tieback_cleats_count", parsed["tieback_cleats_count"]))

            poly_area = cls.calculate_polygon_area(snapped_poly, scale_ratio)
            if poly_area > 0.0:
                area_m2 = poly_area
            else:
                area_m2 = round(l_m * h_m, 4)

            spec = PrecastSpandrelSpec(
                panel_id=panel_id,
                panel_type=ptype,
                boundary_polygon=snapped_poly,
                panel_length_m=l_m,
                panel_height_m=h_m,
                thickness_mm=thk_mm,
                gravity_brackets_count=grav_cnt,
                tieback_cleats_count=tie_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_panels.append(spec)

            # Concrete volume: for insulated sandwich, outer wythe 75mm + inner wythe 100mm = 175mm concrete
            net_conc_thk = 175.0 if ptype == SpandrelPanelType.INSULATED_SANDWICH_SPANDREL else thk_mm
            conc_vol = area_m2 * (net_conc_thk / 1000.0)

            perim_m = 2.0 * (l_m + h_m)

            tot_area_m2 += area_m2
            tot_concrete_m3 += conc_vol
            tot_gravity_brackets += grav_cnt
            tot_tiebacks += tie_cnt
            tot_perim_m += perim_m

            t_key = ptype.value
            area_by_type_dict[t_key] = round(area_by_type_dict.get(t_key, 0.0) + area_m2, 4)

        quantities = PrecastSpandrelQuantities(
            total_panels_count=len(extracted_panels),
            total_elevation_area_m2=round(tot_area_m2, 4),
            total_concrete_volume_m3=round(tot_concrete_m3, 4),
            total_gravity_brackets_count=tot_gravity_brackets,
            total_tieback_cleats_count=tot_tiebacks,
            total_perimeter_joint_meters=round(tot_perim_m, 4),
            area_by_type=area_by_type_dict,
        )

        return PrecastSpandrelExtractionResult(
            panels=extracted_panels,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourcePrecastSpandrelCleatShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
