"""
pb_source_hollowcore_slab_plank_shadow.py

Authoritative shadow-mode extraction and structural takeoff for precast prestressed
hollowcore concrete planks, shear key longitudinal joints, and composite topping slabs.

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
GROUT_VOLUME_PER_LINEAR_METER_M3: float = 0.0035  # standard shear key cross-section


class HollowcorePlankType(str, Enum):
    STANDARD_EXTRUDED_PLANK = "STANDARD_EXTRUDED_PLANK"
    NARROW_CUT_PLANK = "NARROW_CUT_PLANK"
    OPENING_PENETRATION_PLANK = "OPENING_PENETRATION_PLANK"
    SOLID_FILLED_BEARING_PLANK = "SOLID_FILLED_BEARING_PLANK"


class StructuralToppingType(str, Enum):
    UNSTOPPED = "UNSTOPPED"
    COMPOSITE_TOPPING = "COMPOSITE_TOPPING"


@dataclass
class HollowcorePlankSpec:
    plank_id: str
    plank_type: HollowcorePlankType = HollowcorePlankType.STANDARD_EXTRUDED_PLANK
    topping_type: StructuralToppingType = StructuralToppingType.COMPOSITE_TOPPING
    boundary_polygon: List[Tuple[float, float]] = field(default_factory=list)
    nominal_width_mm: float = 1200.0
    depth_mm: float = 200.0
    length_m: float = 8.0
    area_m2: float = 9.6
    topping_thickness_mm: float = 65.0
    level_id: str = "L02"
    source_callout: str = ""


@dataclass
class HollowcoreSlabQuantities:
    total_planks_count: int = 0
    total_plank_area_m2: float = 0.0
    total_topping_volume_m3: float = 0.0
    total_shear_key_linear_meters: float = 0.0
    total_shear_key_grout_volume_m3: float = 0.0
    planks_by_depth: Dict[str, int] = field(default_factory=dict)
    area_by_depth: Dict[str, float] = field(default_factory=dict)


@dataclass
class HollowcoreSlabExtractionResult:
    planks: List[HollowcorePlankSpec] = field(default_factory=list)
    quantities: HollowcoreSlabQuantities = field(default_factory=HollowcoreSlabQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceHollowcoreSlabPlankShadowAuthority:
    """Authoritative shadow evaluator for precast hollowcore concrete slab planks."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses precast hollowcore plank schedule annotations.
        Example strings:
          - "200mm HOLLOWCORE SLAB W/ 65mm COMPOSITE TOPPING"
          - "250mm PRECAST HOLLOWCORE PLANK UNTOPPED L=9.2m"
          - "HC200 NARROW CUT PLANK 600mm WIDE"
        """
        clean = text.upper()
        res = {
            "plank_type": HollowcorePlankType.STANDARD_EXTRUDED_PLANK,
            "topping_type": StructuralToppingType.COMPOSITE_TOPPING,
            "nominal_width_mm": 1200.0,
            "depth_mm": 200.0,
            "topping_thickness_mm": 65.0,
            "length_m": 8.0,
        }

        # Plank Typology
        if "CUT" in clean or "NARROW" in clean or "RIP" in clean:
            res["plank_type"] = HollowcorePlankType.NARROW_CUT_PLANK
        elif "PENETRATION" in clean or "OPENING" in clean:
            res["plank_type"] = HollowcorePlankType.OPENING_PENETRATION_PLANK
        elif "SOLID" in clean or "FILLED" in clean or "GROUTED BEARING" in clean:
            res["plank_type"] = HollowcorePlankType.SOLID_FILLED_BEARING_PLANK
        else:
            res["plank_type"] = HollowcorePlankType.STANDARD_EXTRUDED_PLANK

        # Topping
        if "UNTOPPED" in clean or "NO TOPPING" in clean or "BARE" in clean:
            res["topping_type"] = StructuralToppingType.UNSTOPPED
            res["topping_thickness_mm"] = 0.0
        else:
            res["topping_type"] = StructuralToppingType.COMPOSITE_TOPPING
            top_match = re.search(r'(\d{2,3})\s*MM\s*(?:COMPOSITE\s*)?TOPPING', clean)
            if top_match:
                try:
                    res["topping_thickness_mm"] = float(top_match.group(1))
                except ValueError:
                    res["topping_thickness_mm"] = 65.0

        # Depth: 150mm, 200mm, 250mm, 300mm, 400mm or HC200, HC250
        hc_match = re.search(r'\bHC(\d{3})\b', clean)
        if hc_match:
            try:
                res["depth_mm"] = float(hc_match.group(1))
            except ValueError:
                pass
        else:
            depth_match = re.search(r'(\d{3})\s*MM\s*(?:HOLLOWCORE|PRECAST|PLANK|SLAB|DEPTH|THICK)', clean)
            if depth_match:
                try:
                    d = float(depth_match.group(1))
                    if 100.0 <= d <= 600.0:
                        res["depth_mm"] = d
                except ValueError:
                    pass

        # Width (e.g. 600mm WIDE, 1200 WIDE)
        width_match = re.search(r'(\d{3,4})\s*MM\s*(?:WIDE|WIDTH)', clean)
        if width_match:
            try:
                w = float(width_match.group(1))
                if 200.0 <= w <= 2400.0:
                    res["nominal_width_mm"] = w
            except ValueError:
                pass

        # Length (e.g. L=9.2m, 8.5M LONG, 8.0M SPAN)
        len_match = re.search(r'(?:L\s*[=:]?\s*|SPAN\s*[=:]?\s*)?(\d+(?:\.\d+)?)\s*M(?:\s*(?:LONG|SPAN|LENGTH))', clean)
        if len_match:
            try:
                l_val = float(len_match.group(1))
                if 1.0 <= l_val <= 30.0:
                    res["length_m"] = l_val
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
    def evaluate_slabs(
        cls,
        raw_plank_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L02"
    ) -> HollowcoreSlabExtractionResult:
        """
        Authoritative shadow extraction for precast hollowcore concrete floor planks.
        """
        extracted_planks: List[HollowcorePlankSpec] = []
        tot_area = 0.0
        tot_topping_vol = 0.0
        tot_shear_key_m = 0.0

        by_depth: Dict[str, int] = {}
        area_by_depth_dict: Dict[str, float] = {}

        for item in raw_plank_data:
            plank_id = item.get("plank_id", f"HC_{len(extracted_planks)+1:03d}")
            raw_poly = item.get("boundary_polygon", [])
            snapped_poly = [cls.snap_point(pt) for pt in raw_poly]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            plank_type_val = item.get("plank_type", parsed["plank_type"])
            if isinstance(plank_type_val, str):
                try:
                    p_type = HollowcorePlankType(plank_type_val)
                except ValueError:
                    p_type = HollowcorePlankType.STANDARD_EXTRUDED_PLANK
            else:
                p_type = plank_type_val

            topping_type_val = item.get("topping_type", parsed["topping_type"])
            if isinstance(topping_type_val, str):
                try:
                    top_type = StructuralToppingType(topping_type_val)
                except ValueError:
                    top_type = StructuralToppingType.COMPOSITE_TOPPING
            else:
                top_type = topping_type_val

            depth_mm = float(item.get("depth_mm", parsed["depth_mm"]))
            width_mm = float(item.get("nominal_width_mm", parsed["nominal_width_mm"]))
            length_m = float(item.get("length_m", parsed["length_m"]))
            top_thk_mm = float(item.get("topping_thickness_mm", parsed["topping_thickness_mm"]))

            poly_area = cls.calculate_polygon_area(snapped_poly, scale_ratio)
            if poly_area > 0.0:
                area_m2 = poly_area
            else:
                area_m2 = round((width_mm / 1000.0) * length_m, 4)

            spec = HollowcorePlankSpec(
                plank_id=plank_id,
                plank_type=p_type,
                topping_type=top_type,
                boundary_polygon=snapped_poly,
                nominal_width_mm=width_mm,
                depth_mm=depth_mm,
                length_m=length_m,
                area_m2=area_m2,
                topping_thickness_mm=top_thk_mm,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_planks.append(spec)

            tot_area += area_m2
            tot_shear_key_m += length_m  # Each plank contributes its span to longitudinal joint lines

            if top_type == StructuralToppingType.COMPOSITE_TOPPING:
                topping_vol = area_m2 * (top_thk_mm / 1000.0)
                tot_topping_vol += topping_vol

            depth_key = f"{int(depth_mm)}mm"
            by_depth[depth_key] = by_depth.get(depth_key, 0) + 1
            area_by_depth_dict[depth_key] = round(area_by_depth_dict.get(depth_key, 0.0) + area_m2, 4)

        tot_grout_vol = tot_shear_key_m * GROUT_VOLUME_PER_LINEAR_METER_M3

        quantities = HollowcoreSlabQuantities(
            total_planks_count=len(extracted_planks),
            total_plank_area_m2=round(tot_area, 4),
            total_topping_volume_m3=round(tot_topping_vol, 4),
            total_shear_key_linear_meters=round(tot_shear_key_m, 4),
            total_shear_key_grout_volume_m3=round(tot_grout_vol, 4),
            planks_by_depth=by_depth,
            area_by_depth=area_by_depth_dict,
        )

        return HollowcoreSlabExtractionResult(
            planks=extracted_planks,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceHollowcoreSlabPlankShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
