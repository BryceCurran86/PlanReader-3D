"""
pb_source_skylight_smoke_vent_shadow.py

Authoritative shadow-mode extraction and takeoff for roof skylights, emergency smoke/heat
exhaust ventilators (ASHEVs), insulated upstand curb framing, and fall-arrest safety mesh.

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
DEFAULT_CV_DISCHARGE: float = 0.65


class RoofVentSkylightType(str, Enum):
    FIXED_SKYLIGHT_DOME = "FIXED_SKYLIGHT_DOME"
    OPERABLE_VENT_SKYLIGHT = "OPERABLE_VENT_SKYLIGHT"
    AUTOMATIC_SMOKE_HEAT_VENT = "AUTOMATIC_SMOKE_HEAT_VENT"
    ROOF_ACCESS_HATCH = "ROOF_ACCESS_HATCH"


class CurbConstructionType(str, Enum):
    INSULATED_STEEL_UPSTAND = "INSULATED_STEEL_UPSTAND"
    STRUCTURAL_TIMBER_KERB = "STRUCTURAL_TIMBER_KERB"
    PRECAST_CONCRETE_UPSTAND = "PRECAST_CONCRETE_UPSTAND"
    ALUMINIUM_EXTRUDED_CURB = "ALUMINIUM_EXTRUDED_CURB"


@dataclass
class SkylightVentSpec:
    unit_id: str
    unit_type: RoofVentSkylightType = RoofVentSkylightType.FIXED_SKYLIGHT_DOME
    curb_type: CurbConstructionType = CurbConstructionType.INSULATED_STEEL_UPSTAND
    center_point: Tuple[float, float] = (0.0, 0.0)
    opening_width_mm: float = 0.0
    opening_length_mm: float = 0.0
    curb_height_mm: float = 0.0
    has_safety_mesh: bool = False
    discharge_coefficient_cv: float = 0.0
    level_id: str = "ROOF"
    source_callout: str = ""


@dataclass
class SkylightVentQuantities:
    total_units_count: int = 0
    total_throat_area_m2: float = 0.0
    total_curb_perimeter_meters: float = 0.0
    total_aerodynamic_free_area_m2: float = 0.0
    smoke_vents_count: int = 0
    skylights_count: int = 0
    units_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class SkylightVentExtractionResult:
    units: List[SkylightVentSpec] = field(default_factory=list)
    quantities: SkylightVentQuantities = field(default_factory=SkylightVentQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSkylightSmokeVentShadowAuthority:
    """Authoritative shadow evaluator for roof penetrations, skylights, and smoke relief vents."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses skylight and smoke vent schedule annotations.
        Example strings:
          - "1200x2400 AUTOMATIC SMOKE & HEAT EXHAUST VENT 200mm INSULATED STEEL CURB W/ SAFETY MESH"
          - "1000x1500 DOUBLE GLAZED SKYLIGHT TIMBER KERB H=150"
          - "ROOF ACCESS HATCH 900x900 INSULATED"
        """
        clean = text.upper()
        res = {
            "unit_type": RoofVentSkylightType.FIXED_SKYLIGHT_DOME,
            "curb_type": CurbConstructionType.INSULATED_STEEL_UPSTAND,
            "opening_width_mm": 0.0,
            "opening_length_mm": 0.0,
            "curb_height_mm": 0.0,
            "has_safety_mesh": False,
            "discharge_coefficient_cv": 0.0,
        }

        # Unit Type
        if "SMOKE" in clean or "HEAT EXHAUST" in clean or "ASHEV" in clean or "EN12101" in clean or "FIRE VENT" in clean:
            res["unit_type"] = RoofVentSkylightType.AUTOMATIC_SMOKE_HEAT_VENT
        elif "ACCESS HATCH" in clean or "ROOF HATCH" in clean:
            res["unit_type"] = RoofVentSkylightType.ROOF_ACCESS_HATCH
        elif "OPERABLE" in clean or "MOTORIZED" in clean or "VENT SKYLIGHT" in clean:
            res["unit_type"] = RoofVentSkylightType.OPERABLE_VENT_SKYLIGHT
        else:
            res["unit_type"] = RoofVentSkylightType.FIXED_SKYLIGHT_DOME

        # Curb Type
        if "TIMBER" in clean or "WOOD" in clean:
            res["curb_type"] = CurbConstructionType.STRUCTURAL_TIMBER_KERB
        elif "CONCRETE" in clean or "PRECAST" in clean:
            res["curb_type"] = CurbConstructionType.PRECAST_CONCRETE_UPSTAND
        elif "ALUMINIUM" in clean or "ALUM" in clean:
            res["curb_type"] = CurbConstructionType.ALUMINIUM_EXTRUDED_CURB
        else:
            res["curb_type"] = CurbConstructionType.INSULATED_STEEL_UPSTAND

        # Dimensions: 1200x2400 or 1000x1500
        dim_match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', clean)
        if dim_match:
            try:
                d1 = float(dim_match.group(1))
                d2 = float(dim_match.group(2))
                res["opening_width_mm"] = min(d1, d2)
                res["opening_length_mm"] = max(d1, d2)
            except ValueError:
                pass

        # Curb height: 200mm CURB, 150mm UPSTAND, H=200, KERB H=150
        curb_match = re.search(r'(?:CURB|UPSTAND|KERB)\s*(?:HEIGHT|H)?\s*[=:]?\s*(\d{2,3})\s*(?:MM\b)?', clean)
        if not curb_match:
            curb_match = re.search(r'\bH\s*[=:]\s*(\d{2,3})\b', clean)
        if not curb_match:
            curb_match = re.search(r'(\d{2,3})\s*MM\s*(?:CURB|UPSTAND|KERB)', clean)
        if not curb_match:
            curb_match = re.search(
                r'(\d{2,3})\s*MM(?:\s+\w+){0,4}\s*(?:CURB|UPSTAND|KERB)',
                clean,
            )
        if curb_match:
            try:
                ch = float(curb_match.group(1))
                if 50.0 <= ch <= 600.0:
                    res["curb_height_mm"] = ch
            except ValueError:
                pass

        # Safety mesh
        if "SAFETY MESH" in clean or "SECURITY MESH" in clean or "FALL ARREST" in clean or "WIRE MESH" in clean:
            res["has_safety_mesh"] = True

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @classmethod
    def evaluate_roof_penetrations(
        cls,
        raw_units_data: List[Dict[str, any]],
        default_level: str = "ROOF"
    ) -> SkylightVentExtractionResult:
        """
        Authoritative shadow extraction for roof skylights and smoke relief vents.
        """
        extracted_units: List[SkylightVentSpec] = []
        tot_throat_area = 0.0
        tot_perimeter_m = 0.0
        tot_aerodynamic_area = 0.0
        smoke_cnt = 0
        skylight_cnt = 0
        by_type: Dict[str, int] = {}

        for item in raw_units_data:
            unit_id = item.get("unit_id", f"RV_{len(extracted_units)+1:03d}")
            raw_center = item.get("center_point", (0.0, 0.0))
            snapped_center = cls.snap_point(raw_center)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            utype_val = item.get("unit_type", parsed["unit_type"])
            if isinstance(utype_val, str):
                try:
                    utype = RoofVentSkylightType(utype_val)
                except ValueError:
                    utype = RoofVentSkylightType.FIXED_SKYLIGHT_DOME
            else:
                utype = utype_val

            ctype_val = item.get("curb_type", parsed["curb_type"])
            if isinstance(ctype_val, str):
                try:
                    ctype = CurbConstructionType(ctype_val)
                except ValueError:
                    ctype = CurbConstructionType.INSULATED_STEEL_UPSTAND
            else:
                ctype = ctype_val

            w_mm = float(item.get("opening_width_mm", parsed["opening_width_mm"]))
            l_mm = float(item.get("opening_length_mm", parsed["opening_length_mm"]))
            curb_h = float(item.get("curb_height_mm", parsed["curb_height_mm"]))
            mesh = bool(item.get("has_safety_mesh", parsed["has_safety_mesh"]))
            cv = float(item.get("discharge_coefficient_cv", parsed["discharge_coefficient_cv"]))

            spec = SkylightVentSpec(
                unit_id=unit_id,
                unit_type=utype,
                curb_type=ctype,
                center_point=snapped_center,
                opening_width_mm=w_mm,
                opening_length_mm=l_mm,
                curb_height_mm=curb_h,
                has_safety_mesh=mesh,
                discharge_coefficient_cv=cv,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_units.append(spec)

            throat_area_m2 = (w_mm / 1000.0) * (l_mm / 1000.0)
            perimeter_m = 2.0 * ((w_mm / 1000.0) + (l_mm / 1000.0))

            tot_throat_area += throat_area_m2
            tot_perimeter_m += perimeter_m

            if utype == RoofVentSkylightType.AUTOMATIC_SMOKE_HEAT_VENT:
                smoke_cnt += 1
                tot_aerodynamic_area += throat_area_m2 * cv
            elif utype in (RoofVentSkylightType.FIXED_SKYLIGHT_DOME, RoofVentSkylightType.OPERABLE_VENT_SKYLIGHT):
                skylight_cnt += 1

            t_key = utype.value
            by_type[t_key] = by_type.get(t_key, 0) + 1

        quantities = SkylightVentQuantities(
            total_units_count=len(extracted_units),
            total_throat_area_m2=round(tot_throat_area, 4),
            total_curb_perimeter_meters=round(tot_perimeter_m, 4),
            total_aerodynamic_free_area_m2=round(tot_aerodynamic_area, 4),
            smoke_vents_count=smoke_cnt,
            skylights_count=skylight_cnt,
            units_by_type=by_type,
        )

        return SkylightVentExtractionResult(
            units=extracted_units,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceSkylightSmokeVentShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
