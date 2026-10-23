"""
Source Hot Water Expansion Vessel & Relief Valve Shadow Authority.

Extracts and validates hot water expansion vessels, capacities (L), pre-charge pressures (kPa),
PTRV relief valve thresholds (kPa), temperature trip limits (°C), and drain diameters (DN) strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ExpansionVesselReliefValveCallout:
    raw_text: str
    vessel_capacity_litres: float
    precharge_pressure_kpa: float
    relief_valve_set_kpa: float
    relief_temperature_deg_c: float
    relief_drain_dn: str
    bladder_material: str
    position: Tuple[float, float] = (0.0, 0.0)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def snap_point(x: float, y: float, snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    """Snap coordinates to discrete precision grid."""
    if snap_tol <= 0.0:
        return (x, y)
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_expansion_vessel_relief_valve_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "EXPANSION VESSEL",
        "EXPANSION TANK",
        "POTABLE EXPANSION",
        "PRESSURE RELIEF VALVE",
        "PTRV",
        "P&T RELIEF VALVE",
        "TEMPERATURE RELIEF VALVE",
        "SAFETY RELIEF VALVE",
        "THERMAL EXPANSION TANK",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Vessel capacity litres
    vol_litres = 24.0
    vol_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:LITRES|LITRE|L\b)", upper)
    if vol_match:
        vol_litres = float(vol_match.group(1))

    # Precharge pressure kPa
    precharge = 450.0
    pre_match = re.search(r"(?:PRECHARGE|PRE-CHARGE|CHARGE)\s*[:=]?\s*(\d{2,4})\s*(?:KPA)?", upper)
    if pre_match:
        precharge = float(pre_match.group(1))

    # Relief valve set pressure kPa
    relief_kpa = 850.0
    rel_match = re.search(r"(?:RELIEF|SET|PTRV)\s*(?:AT|PRESSURE)?\s*[:=]?\s*(\d{3,4})\s*(?:KPA)?", upper)
    if rel_match:
        val = float(rel_match.group(1))
        if 500 <= val <= 2000:
            relief_kpa = val

    # Relief temperature deg C
    rel_temp = 99.0
    temp_match = re.search(r"(\d{2,3})\s*(?:DEG|°)?\s*C\b", upper)
    if temp_match:
        t_val = float(temp_match.group(1))
        if 80 <= t_val <= 110:
            rel_temp = t_val

    # Drain line DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    drain_dn = f"DN{dn_match.group(1)}" if dn_match else "DN20"

    # Bladder material
    if "BUTYL" in upper:
        mat = "BUTYL_RUBBER_FOOD_GRADE"
    elif "EPDM" in upper:
        mat = "EPDM_MEMBRANE"
    elif "DIAPHRAGM" in upper:
        mat = "DIAPHRAGM_POTABLE"
    else:
        mat = "BUTYL_RUBBER_FOOD_GRADE"

    return {
        "vessel_capacity_litres": vol_litres,
        "precharge_pressure_kpa": precharge,
        "relief_valve_set_kpa": relief_kpa,
        "relief_temperature_deg_c": rel_temp,
        "relief_drain_dn": drain_dn,
        "bladder_material": mat,
    }


class SourceExpansionVesselReliefValveShadowAuthority:
    """Authority for extracting hot water expansion vessels and relief valves in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[ExpansionVesselReliefValveCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[ExpansionVesselReliefValveCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_expansion_vessel_relief_valve_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["vessel_capacity_litres"], parsed["relief_drain_dn"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = ExpansionVesselReliefValveCallout(
                raw_text=text,
                vessel_capacity_litres=parsed["vessel_capacity_litres"],
                precharge_pressure_kpa=parsed["precharge_pressure_kpa"],
                relief_valve_set_kpa=parsed["relief_valve_set_kpa"],
                relief_temperature_deg_c=parsed["relief_temperature_deg_c"],
                relief_drain_dn=parsed["relief_drain_dn"],
                bladder_material=parsed["bladder_material"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
