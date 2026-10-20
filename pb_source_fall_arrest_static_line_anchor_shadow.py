"""
pb_source_fall_arrest_static_line_anchor_shadow.py

Authoritative shadow-mode extraction and safety takeoff for roof fall arrest static lines,
intermediate pass-through brackets, energy absorbers, and certified anchor points.

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


class FallProtectionType(str, Enum):
    HORIZONTAL_STATIC_LIFELINE = "HORIZONTAL_STATIC_LIFELINE"
    SINGLE_POINT_FALL_ARREST_ANCHOR = "SINGLE_POINT_FALL_ARREST_ANCHOR"
    ROPE_ACCESS_ABSEIL_ANCHOR = "ROPE_ACCESS_ABSEIL_ANCHOR"
    RIGID_RAIL_FALL_SYSTEM = "RIGID_RAIL_FALL_SYSTEM"


class AnchorMountingSubstrate(str, Enum):
    PURLIN_METAL_DECK_MOUNT = "PURLIN_METAL_DECK_MOUNT"
    CONCRETE_STRUCTURE_MOUNT = "CONCRETE_STRUCTURE_MOUNT"
    STEEL_BEAM_CLAMP_MOUNT = "STEEL_BEAM_CLAMP_MOUNT"


@dataclass
class FallProtectionItemSpec:
    item_id: str
    protection_type: FallProtectionType = FallProtectionType.HORIZONTAL_STATIC_LIFELINE
    mounting_substrate: AnchorMountingSubstrate = AnchorMountingSubstrate.PURLIN_METAL_DECK_MOUNT
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    location_point: Tuple[float, float] = (0.0, 0.0)
    cable_diameter_mm: float = 8.0
    load_rating_kn: float = 15.0
    intermediate_spacing_m: float = 8.0
    intermediate_brackets_count: int = 2
    end_anchors_count: int = 2
    energy_absorbers_count: int = 1
    level_id: str = "ROOF"
    source_callout: str = ""


@dataclass
class FallProtectionQuantities:
    total_systems_count: int = 0
    total_cable_length_meters: float = 0.0
    total_intermediate_brackets_count: int = 0
    total_anchor_points_count: int = 0
    total_energy_absorbers_count: int = 0
    cable_length_by_type: Dict[str, float] = field(default_factory=dict)
    anchors_by_substrate: Dict[str, int] = field(default_factory=dict)


@dataclass
class FallProtectionExtractionResult:
    items: List[FallProtectionItemSpec] = field(default_factory=list)
    quantities: FallProtectionQuantities = field(default_factory=FallProtectionQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceFallArrestStaticLineAnchorShadowAuthority:
    """Authoritative shadow evaluator for roof fall arrest static lines and safety anchors."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses roof safety fall protection callouts.
        Example strings:
          - "8mm SS HORIZONTAL STATIC LINE ON PURLIN MOUNT BRACKETS AT 8.0m CTS W/ 2x ENERGY ABSORBERS"
          - "15kN SINGLE POINT FALL ARREST ANCHOR CONCRETE MOUNT"
          - "22kN ROPE ACCESS ABSEIL ANCHOR STEEL BEAM CLAMP"
          - "OVERHEAD RIGID RAIL FALL SYSTEM"
        """
        clean = text.upper()
        res = {
            "protection_type": FallProtectionType.HORIZONTAL_STATIC_LIFELINE,
            "mounting_substrate": AnchorMountingSubstrate.PURLIN_METAL_DECK_MOUNT,
            "cable_diameter_mm": 8.0,
            "load_rating_kn": 15.0,
            "intermediate_spacing_m": 8.0,
            "energy_absorbers_count": 1,
        }

        # Typology
        if "ROPE ACCESS" in clean or "ABSEIL" in clean:
            res["protection_type"] = FallProtectionType.ROPE_ACCESS_ABSEIL_ANCHOR
            res["load_rating_kn"] = 22.0
        elif "SINGLE POINT" in clean or "EYEBOLT" in clean or "ANCHOR POINT" in clean:
            res["protection_type"] = FallProtectionType.SINGLE_POINT_FALL_ARREST_ANCHOR
            res["load_rating_kn"] = 15.0
        elif "RIGID RAIL" in clean:
            res["protection_type"] = FallProtectionType.RIGID_RAIL_FALL_SYSTEM
        else:
            res["protection_type"] = FallProtectionType.HORIZONTAL_STATIC_LIFELINE
            res["load_rating_kn"] = 15.0

        # Substrate
        if "CONCRETE" in clean:
            res["mounting_substrate"] = AnchorMountingSubstrate.CONCRETE_STRUCTURE_MOUNT
        elif "STEEL" in clean or "BEAM CLAMP" in clean:
            res["mounting_substrate"] = AnchorMountingSubstrate.STEEL_BEAM_CLAMP_MOUNT
        else:
            res["mounting_substrate"] = AnchorMountingSubstrate.PURLIN_METAL_DECK_MOUNT

        # Cable diameter: 8mm SS, 10mm CABLE
        dia_match = re.search(r'(\d{1,2})\s*MM\s*(?:SS|STAINLESS|WIRE|CABLE)?', clean)
        if dia_match:
            try:
                d = float(dia_match.group(1))
                if 4.0 <= d <= 20.0:
                    res["cable_diameter_mm"] = d
            except ValueError:
                pass

        # Rating: 15kN, 22kN
        kn_match = re.search(r'(\d{2})\s*KN', clean)
        if kn_match:
            try:
                res["load_rating_kn"] = float(kn_match.group(1))
            except ValueError:
                pass

        # Intermediate bracket spacing: AT 8.0m CTS, 6.0m SPACING
        spc_match = re.search(r'(?:AT\s*)?(\d+(?:\.\d+)?)\s*M\s*(?:CTS|CENTRES|CENTERS|SPACING)', clean)
        if spc_match:
            try:
                s = float(spc_match.group(1))
                if 2.0 <= s <= 15.0:
                    res["intermediate_spacing_m"] = s
            except ValueError:
                pass

        # Energy absorbers: 2x ENERGY ABSORBERS, 1 ABSORBER
        abs_match = re.search(r'(\d+)\s*[xX]?\s*(?:ENERGY\s*)?ABSORBER', clean)
        if abs_match:
            try:
                res["energy_absorbers_count"] = int(abs_match.group(1))
            except ValueError:
                res["energy_absorbers_count"] = 1

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
        tot_len = 0.0
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            tot_len += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        return round(tot_len * scale_ratio, 4)

    @classmethod
    def evaluate_systems(
        cls,
        raw_systems_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "ROOF"
    ) -> FallProtectionExtractionResult:
        """
        Authoritative shadow extraction for roof fall arrest static lines and anchor points.
        """
        extracted_items: List[FallProtectionItemSpec] = []
        tot_cable_m = 0.0
        tot_intermediate = 0
        tot_anchors = 0
        tot_absorbers = 0

        cable_by_type: Dict[str, float] = {}
        anchors_by_sub: Dict[str, int] = {}

        for item in raw_systems_data:
            item_id = item.get("item_id", f"FP_{len(extracted_items)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            raw_loc = item.get("location_point", snapped_pts[0] if snapped_pts else (0.0, 0.0))
            snapped_loc = cls.snap_point(raw_loc)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ptype_val = item.get("protection_type", parsed["protection_type"])
            if isinstance(ptype_val, str):
                try:
                    ptype = FallProtectionType(ptype_val)
                except ValueError:
                    ptype = FallProtectionType.HORIZONTAL_STATIC_LIFELINE
            else:
                ptype = ptype_val

            msub_val = item.get("mounting_substrate", parsed["mounting_substrate"])
            if isinstance(msub_val, str):
                try:
                    msub = AnchorMountingSubstrate(msub_val)
                except ValueError:
                    msub = AnchorMountingSubstrate.PURLIN_METAL_DECK_MOUNT
            else:
                msub = msub_val

            cable_dia_mm = float(item.get("cable_diameter_mm", parsed["cable_diameter_mm"]))
            rating_kn = float(item.get("load_rating_kn", parsed["load_rating_kn"]))
            spc_m = float(item.get("intermediate_spacing_m", parsed["intermediate_spacing_m"]))
            abs_cnt = int(item.get("energy_absorbers_count", parsed["energy_absorbers_count"]))

            line_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            if ptype in (FallProtectionType.HORIZONTAL_STATIC_LIFELINE, FallProtectionType.RIGID_RAIL_FALL_SYSTEM):
                # 2 end anchor posts + intermediate brackets
                end_cnt = 2
                if line_len_m > 0.0 and spc_m > 0.0:
                    int_cnt = max(0, int(math.ceil(line_len_m / spc_m)) - 1)
                else:
                    int_cnt = 0
                cable_m = line_len_m
                total_anchor_pts = end_cnt
                absorbers = abs_cnt
            else:
                # Single/Twin anchor point
                end_cnt = 0
                int_cnt = 0
                cable_m = 0.0
                total_anchor_pts = 1
                absorbers = 0

            spec = FallProtectionItemSpec(
                item_id=item_id,
                protection_type=ptype,
                mounting_substrate=msub,
                centerline_points=snapped_pts,
                location_point=snapped_loc,
                cable_diameter_mm=cable_dia_mm,
                load_rating_kn=rating_kn,
                intermediate_spacing_m=spc_m,
                intermediate_brackets_count=int_cnt,
                end_anchors_count=end_cnt,
                energy_absorbers_count=absorbers,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_items.append(spec)

            tot_cable_m += cable_m
            tot_intermediate += int_cnt
            tot_anchors += total_anchor_pts
            tot_absorbers += absorbers

            t_key = ptype.value
            cable_by_type[t_key] = round(cable_by_type.get(t_key, 0.0) + cable_m, 4)

            s_key = msub.value
            anchors_by_sub[s_key] = anchors_by_sub.get(s_key, 0) + total_anchor_pts

        quantities = FallProtectionQuantities(
            total_systems_count=len(extracted_items),
            total_cable_length_meters=round(tot_cable_m, 4),
            total_intermediate_brackets_count=tot_intermediate,
            total_anchor_points_count=tot_anchors,
            total_energy_absorbers_count=tot_absorbers,
            cable_length_by_type=cable_by_type,
            anchors_by_substrate=anchors_by_sub,
        )

        return FallProtectionExtractionResult(
            items=extracted_items,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceFallArrestStaticLineAnchorShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
