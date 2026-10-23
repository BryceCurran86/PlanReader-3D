"""
pb_source_fire_smoke_damper_hvac_shadow.py

Authoritative shadow-mode extraction and MEP/passive fire takeoff for ducted HVAC fire dampers,
smoke dampers, motorized combination FSDs, retaining angles, and inspection access doors.

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


class DamperType(str, Enum):
    MOTORIZED_FIRE_SMOKE_DAMPER = "MOTORIZED_FIRE_SMOKE_DAMPER"
    MECHANICAL_CURTAIN_FIRE_DAMPER = "MECHANICAL_CURTAIN_FIRE_DAMPER"
    MULTI_BLADE_SMOKE_DAMPER = "MULTI_BLADE_SMOKE_DAMPER"
    INTUMESCENT_AIR_TRANSFER_DAMPER = "INTUMESCENT_AIR_TRANSFER_DAMPER"


class ActuatorPowerType(str, Enum):
    ELECTRIC_SPRING_RETURN_24V = "ELECTRIC_SPRING_RETURN_24V"
    ELECTRIC_SPRING_RETURN_240V = "ELECTRIC_SPRING_RETURN_240V"
    THERMAL_FUSIBLE_LINK_ONLY = "THERMAL_FUSIBLE_LINK_ONLY"


@dataclass
class HVACDamperSpec:
    damper_id: str
    damper_type: DamperType = DamperType.MOTORIZED_FIRE_SMOKE_DAMPER
    actuator_type: ActuatorPowerType = ActuatorPowerType.ELECTRIC_SPRING_RETURN_24V
    location_point: Tuple[float, float] = (0.0, 0.0)
    duct_width_mm: float = 600.0
    duct_height_mm: float = 400.0
    fire_rating_frl: str = "-/120/-"
    access_door_included: bool = True
    level_id: str = "L01"
    host_wall_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class HVACDamperQuantities:
    total_dampers_count: int = 0
    total_face_area_m2: float = 0.0
    total_retaining_angles_meters: float = 0.0
    total_motorized_actuators_count: int = 0
    total_access_doors_count: int = 0
    dampers_by_type: Dict[str, int] = field(default_factory=dict)
    dampers_by_frl: Dict[str, int] = field(default_factory=dict)


@dataclass
class HVACDamperExtractionResult:
    dampers: List[HVACDamperSpec] = field(default_factory=list)
    quantities: HVACDamperQuantities = field(default_factory=HVACDamperQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceFireSmokeDamperHVACShadowAuthority:
    """Authoritative shadow evaluator for ducted HVAC fire and smoke dampers."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses mechanical HVAC damper schedule callouts.
        Example strings:
          - "600x400 MOTORIZED COMBINATION FIRE/SMOKE DAMPER FRL -/120/- W/ 24V SPRING RETURN ACTUATOR & 450x450 ACCESS PANEL"
          - "400x300 MECHANICAL CURTAIN FIRE DAMPER FRL -/120/- FUSIBLE LINK"
          - "800x600 MULTI-BLADE SMOKE DAMPER 240V ACTUATOR"
          - "300x150 INTUMESCENT AIR TRANSFER DAMPER FRL -/60/-"
        """
        clean = text.upper()
        res = {
            "damper_type": DamperType.MOTORIZED_FIRE_SMOKE_DAMPER,
            "actuator_type": ActuatorPowerType.ELECTRIC_SPRING_RETURN_24V,
            "duct_width_mm": 600.0,
            "duct_height_mm": 400.0,
            "fire_rating_frl": "-/120/-",
            "access_door_included": True,
        }

        # Typology
        if "INTUMESCENT" in clean or "AIR TRANSFER" in clean:
            res["damper_type"] = DamperType.INTUMESCENT_AIR_TRANSFER_DAMPER
            res["actuator_type"] = ActuatorPowerType.THERMAL_FUSIBLE_LINK_ONLY
            res["access_door_included"] = False
            res["fire_rating_frl"] = "-/60/-"
        elif "CURTAIN" in clean or "FUSIBLE" in clean and "MOTOR" not in clean:
            res["damper_type"] = DamperType.MECHANICAL_CURTAIN_FIRE_DAMPER
            res["actuator_type"] = ActuatorPowerType.THERMAL_FUSIBLE_LINK_ONLY
        elif "SMOKE DAMPER" in clean and "FIRE" not in clean:
            res["damper_type"] = DamperType.MULTI_BLADE_SMOKE_DAMPER
            res["fire_rating_frl"] = "SMOKE-ONLY"
        else:
            res["damper_type"] = DamperType.MOTORIZED_FIRE_SMOKE_DAMPER

        # Actuator voltage
        if "240V" in clean:
            res["actuator_type"] = ActuatorPowerType.ELECTRIC_SPRING_RETURN_240V
        elif "24V" in clean:
            res["actuator_type"] = ActuatorPowerType.ELECTRIC_SPRING_RETURN_24V
        elif "FUSIBLE" in clean or "CURTAIN" in clean:
            res["actuator_type"] = ActuatorPowerType.THERMAL_FUSIBLE_LINK_ONLY

        # Dimensions: 600x400, 400x300, etc.
        dim_match = re.search(r'(\d{2,4})\s*[xX*]\s*(\d{2,4})', clean)
        if dim_match:
            try:
                res["duct_width_mm"] = float(dim_match.group(1))
                res["duct_height_mm"] = float(dim_match.group(2))
            except ValueError:
                pass

        # FRL Rating: -/120/-, -/240/-, -/60/-
        frl_match = re.search(r'(-/\d{2,3}/-|\d{2,3}/\d{2,3}/\d{2,3})', clean)
        if frl_match:
            res["fire_rating_frl"] = frl_match.group(1)
        elif "240" in clean:
            res["fire_rating_frl"] = "-/240/-"
        elif "120" in clean or "2 HR" in clean:
            res["fire_rating_frl"] = "-/120/-"
        elif "60" in clean or "1 HR" in clean:
            res["fire_rating_frl"] = "-/60/-"

        # Access door: ACCESS PANEL, ACCESS DOOR, NO ACCESS
        if "NO ACCESS" in clean:
            res["access_door_included"] = False
        elif "ACCESS" in clean or "INSPECTION" in clean:
            res["access_door_included"] = True

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @classmethod
    def evaluate_dampers(
        cls,
        raw_dampers_data: List[Dict[str, any]],
        default_level: str = "L01"
    ) -> HVACDamperExtractionResult:
        """
        Authoritative shadow extraction for HVAC fire and smoke dampers.
        """
        extracted_dampers: List[HVACDamperSpec] = []
        tot_face_area = 0.0
        tot_angles_m = 0.0
        tot_actuators = 0
        tot_access_doors = 0

        dampers_by_type_dict: Dict[str, int] = {}
        dampers_by_frl_dict: Dict[str, int] = {}

        for item in raw_dampers_data:
            damper_id = item.get("damper_id", f"FD_{len(extracted_dampers)+1:02d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            dtype_val = item.get("damper_type", parsed["damper_type"])
            if isinstance(dtype_val, str):
                try:
                    dtype = DamperType(dtype_val)
                except ValueError:
                    dtype = DamperType.MOTORIZED_FIRE_SMOKE_DAMPER
            else:
                dtype = dtype_val

            act_val = item.get("actuator_type", parsed["actuator_type"])
            if isinstance(act_val, str):
                try:
                    act_type = ActuatorPowerType(act_val)
                except ValueError:
                    act_type = ActuatorPowerType.ELECTRIC_SPRING_RETURN_24V
            else:
                act_type = act_val

            w_mm = float(item.get("duct_width_mm", parsed["duct_width_mm"]))
            h_mm = float(item.get("duct_height_mm", parsed["duct_height_mm"]))
            frl = item.get("fire_rating_frl", parsed["fire_rating_frl"])
            acc_inc = bool(item.get("access_door_included", parsed["access_door_included"]))

            face_m2 = round((w_mm / 1000.0) * (h_mm / 1000.0), 4)
            # Bilateral retaining angles: 2 sides * (2 * (W + H))
            angles_m = round(4.0 * ((w_mm + h_mm) / 1000.0), 4)

            spec = HVACDamperSpec(
                damper_id=damper_id,
                damper_type=dtype,
                actuator_type=act_type,
                location_point=snapped_pt,
                duct_width_mm=w_mm,
                duct_height_mm=h_mm,
                fire_rating_frl=frl,
                access_door_included=acc_inc,
                level_id=item.get("level_id", default_level),
                host_wall_id=item.get("host_wall_id"),
                source_callout=callout,
            )
            extracted_dampers.append(spec)

            tot_face_area += face_m2
            tot_angles_m += angles_m
            if act_type in (ActuatorPowerType.ELECTRIC_SPRING_RETURN_24V, ActuatorPowerType.ELECTRIC_SPRING_RETURN_240V):
                tot_actuators += 1
            if acc_inc:
                tot_access_doors += 1

            t_key = dtype.value
            dampers_by_type_dict[t_key] = dampers_by_type_dict.get(t_key, 0) + 1

            dampers_by_frl_dict[frl] = dampers_by_frl_dict.get(frl, 0) + 1

        quantities = HVACDamperQuantities(
            total_dampers_count=len(extracted_dampers),
            total_face_area_m2=round(tot_face_area, 4),
            total_retaining_angles_meters=round(tot_angles_m, 4),
            total_motorized_actuators_count=tot_actuators,
            total_access_doors_count=tot_access_doors,
            dampers_by_type=dampers_by_type_dict,
            dampers_by_frl=dampers_by_frl_dict,
        )

        return HVACDamperExtractionResult(
            dampers=extracted_dampers,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceFireSmokeDamperHVACShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
