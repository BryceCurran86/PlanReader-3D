"""
pb_source_escalator_trimmer_void_shadow.py

Authoritative shadow-mode extraction and spatial takeoff for commercial escalators,
moving walkways (autowalks), slab trimmer voids, and perimeter smoke drop baffles.

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


class VerticalTransportationType(str, Enum):
    COMMERCIAL_ESCALATOR_30_DEG = "COMMERCIAL_ESCALATOR_30_DEG"
    PUBLIC_TRANSIT_ESCALATOR_35_DEG = "PUBLIC_TRANSIT_ESCALATOR_35_DEG"
    HORIZONTAL_MOVING_WALKWAY = "HORIZONTAL_MOVING_WALKWAY"
    INCLINED_MOVING_WALKWAY_12_DEG = "INCLINED_MOVING_WALKWAY_12_DEG"


@dataclass
class EscalatorVoidSpec:
    void_id: str
    unit_type: VerticalTransportationType = VerticalTransportationType.COMMERCIAL_ESCALATOR_30_DEG
    boundary_polygon: List[Tuple[float, float]] = field(default_factory=list)
    vertical_rise_m: float = 4.5
    incline_angle_deg: float = 30.0
    step_pallet_width_mm: float = 1000.0
    has_smoke_baffle: bool = True
    smoke_baffle_depth_mm: float = 500.0
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class EscalatorTrimmerQuantities:
    total_units_count: int = 0
    total_void_area_m2: float = 0.0
    total_trimmer_perimeter_linear_meters: float = 0.0
    total_inclined_travel_meters: float = 0.0
    total_smoke_baffle_perimeter_meters: float = 0.0
    total_smoke_baffle_area_m2: float = 0.0
    units_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class EscalatorTrimmerExtractionResult:
    voids: List[EscalatorVoidSpec] = field(default_factory=list)
    quantities: EscalatorTrimmerQuantities = field(default_factory=EscalatorTrimmerQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceEscalatorTrimmerVoidShadowAuthority:
    """Authoritative shadow evaluator for escalator penetrations, trimmer voids, and smoke baffles."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses escalator and moving walkway schedule callouts.
        Example strings:
          - "COMMERCIAL ESCALATOR 30 DEG W=1000mm RISE=4.5m W/ 500mm GLASS SMOKE BAFFLE"
          - "TRANSIT ESCALATOR 35 DEG INCLINE H=6.0m"
          - "MOVING WALKWAY AUTOWALK 12 DEG INCLINE"
        """
        clean = text.upper()
        res = {
            "unit_type": VerticalTransportationType.COMMERCIAL_ESCALATOR_30_DEG,
            "vertical_rise_m": 4.5,
            "incline_angle_deg": 30.0,
            "step_pallet_width_mm": 1000.0,
            "has_smoke_baffle": False,
            "smoke_baffle_depth_mm": 500.0,
        }

        # Unit Typology & Incline
        if "WALKWAY" in clean or "AUTOWALK" in clean or "TRAVELATOR" in clean or "MOVING WALK" in clean:
            if "12" in clean or "INCLINE" in clean or "RAMP" in clean or "10" in clean:
                res["unit_type"] = VerticalTransportationType.INCLINED_MOVING_WALKWAY_12_DEG
                res["incline_angle_deg"] = 12.0
            else:
                res["unit_type"] = VerticalTransportationType.HORIZONTAL_MOVING_WALKWAY
                res["incline_angle_deg"] = 0.0
        elif "35" in clean or "TRANSIT" in clean or "METRO" in clean:
            res["unit_type"] = VerticalTransportationType.PUBLIC_TRANSIT_ESCALATOR_35_DEG
            res["incline_angle_deg"] = 35.0
        else:
            res["unit_type"] = VerticalTransportationType.COMMERCIAL_ESCALATOR_30_DEG
            res["incline_angle_deg"] = 30.0

        # Vertical Rise: RISE=4.5m, H=6.0m, 4500mm RISE
        rise_match = re.search(r'(?:RISE\s*[=:]?\s*|H\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*M\b', clean)
        if rise_match:
            try:
                r_val = float(rise_match.group(1))
                if 1.0 <= r_val <= 30.0:
                    res["vertical_rise_m"] = r_val
            except ValueError:
                pass
        else:
            rise_mm = re.search(r'(\d{4})\s*MM\s*RISE', clean)
            if rise_mm:
                try:
                    res["vertical_rise_m"] = float(rise_mm.group(1)) / 1000.0
                except ValueError:
                    pass

        # Step/Pallet Width: W=1000mm, 1000mm STEP, 800mm PALLET
        step_match = re.search(r'(?:W\s*[=:]?\s*)?(\d{3,4})\s*MM\s*(?:STEP|PALLET|WIDTH)?', clean)
        if step_match:
            try:
                sw = float(step_match.group(1))
                if 600.0 <= sw <= 1600.0:
                    res["step_pallet_width_mm"] = sw
            except ValueError:
                pass

        # Smoke baffle / draft curtain
        if "SMOKE" in clean or "DRAFT" in clean or "BAFFLE" in clean or "SKIRT" in clean:
            res["has_smoke_baffle"] = True
            baf_m = re.search(r'(\d{3})\s*MM\s*(?:GLASS\s*)?(?:SMOKE|DRAFT|BAFFLE|SKIRT)', clean)
            if baf_m:
                try:
                    res["smoke_baffle_depth_mm"] = float(baf_m.group(1))
                except ValueError:
                    res["smoke_baffle_depth_mm"] = 500.0

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

    @staticmethod
    def calculate_polygon_perimeter(poly: List[Tuple[float, float]], scale_ratio: float = 0.001) -> float:
        if len(poly) < 2:
            return 0.0
        tot = 0.0
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            xi, yi = poly[i]
            xj, yj = poly[j]
            tot += math.hypot(xj - xi, yj - yi)
        return round(tot * scale_ratio, 4)

    @classmethod
    def evaluate_escalator_voids(
        cls,
        raw_void_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> EscalatorTrimmerExtractionResult:
        """
        Authoritative shadow extraction for escalator/moving walkway trimmer voids and smoke baffles.
        """
        extracted_voids: List[EscalatorVoidSpec] = []
        tot_void_area = 0.0
        tot_trimmer_perim = 0.0
        tot_travel_m = 0.0
        tot_smoke_perim = 0.0
        tot_smoke_area = 0.0
        by_type: Dict[str, int] = {}

        for item in raw_void_data:
            void_id = item.get("void_id", f"EV_{len(extracted_voids)+1:03d}")
            raw_poly = item.get("boundary_polygon", [])
            snapped_poly = [cls.snap_point(pt) for pt in raw_poly]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            utype_val = item.get("unit_type", parsed["unit_type"])
            if isinstance(utype_val, str):
                try:
                    utype = VerticalTransportationType(utype_val)
                except ValueError:
                    utype = VerticalTransportationType.COMMERCIAL_ESCALATOR_30_DEG
            else:
                utype = utype_val

            rise_m = float(item.get("vertical_rise_m", parsed["vertical_rise_m"]))
            angle_deg = float(item.get("incline_angle_deg", parsed["incline_angle_deg"]))
            step_w = float(item.get("step_pallet_width_mm", parsed["step_pallet_width_mm"]))
            has_baffle = bool(item.get("has_smoke_baffle", parsed["has_smoke_baffle"]))
            baffle_d = float(item.get("smoke_baffle_depth_mm", parsed["smoke_baffle_depth_mm"]))

            spec = EscalatorVoidSpec(
                void_id=void_id,
                unit_type=utype,
                boundary_polygon=snapped_poly,
                vertical_rise_m=rise_m,
                incline_angle_deg=angle_deg,
                step_pallet_width_mm=step_w,
                has_smoke_baffle=has_baffle,
                smoke_baffle_depth_mm=baffle_d,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_voids.append(spec)

            v_area = cls.calculate_polygon_area(snapped_poly, scale_ratio)
            v_perim = cls.calculate_polygon_perimeter(snapped_poly, scale_ratio)

            tot_void_area += v_area
            tot_trimmer_perim += v_perim

            # Travel distance: if angle > 0: rise / sin(angle), else horizontal length
            if angle_deg > 0.0:
                travel_len = rise_m / math.sin(math.radians(angle_deg))
            else:
                travel_len = max(v_perim * 0.25, rise_m)

            tot_travel_m += travel_len

            if has_baffle:
                tot_smoke_perim += v_perim
                tot_smoke_area += v_perim * (baffle_d / 1000.0)

            t_key = utype.value
            by_type[t_key] = by_type.get(t_key, 0) + 1

        quantities = EscalatorTrimmerQuantities(
            total_units_count=len(extracted_voids),
            total_void_area_m2=round(tot_void_area, 4),
            total_trimmer_perimeter_linear_meters=round(tot_trimmer_perim, 4),
            total_inclined_travel_meters=round(tot_travel_m, 4),
            total_smoke_baffle_perimeter_meters=round(tot_smoke_perim, 4),
            total_smoke_baffle_area_m2=round(tot_smoke_area, 4),
            units_by_type=by_type,
        )

        return EscalatorTrimmerExtractionResult(
            voids=extracted_voids,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceEscalatorTrimmerVoidShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
