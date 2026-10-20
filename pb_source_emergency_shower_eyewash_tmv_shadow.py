"""
Source Emergency Eyewash & Safety Shower Thermostatic Mixing Valve (TMV) Shadow Authority.

Extracts and validates emergency decontamination showers, eye/face wash fixtures, tepid water mixing valves,
cold water bypass mechanisms, alarm flow switches, and hazardous chemical zone requirements strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class EmergencyShowerEyewashTmvCallout:
    raw_text: str
    station_type: str
    tmv_capacity_lpm: Optional[float]
    temperature_setpoint_celsius: Optional[float]
    cold_water_bypass: str
    alarm_actuation: str
    inlet_drain_dn: Optional[str]
    service_hazard: str
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


def parse_emergency_shower_eyewash_tmv_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "EMERGENCY SHOWER",
        "SAFETY SHOWER",
        "EYEWASH",
        "EYE WASH",
        "EYE/FACE WASH",
        "DRENCH SHOWER",
        "EMERGENCY TMV",
        "TEPID WATER TMV",
        "SAFETY TMV",
        "EMERGENCY MIXING VALVE",
        "SAFETY EYEWASH",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("EMERGENCY" in upper or "SAFETY" in upper)
        and ("SHOWER" in upper or "EYEWASH" in upper or "TMV" in upper or "TEPID" in upper)
    )
    if not has_trigger:
        return None

    # Station Type
    if any(k in upper for k in ["COMBINATION", "SHOWER AND EYEWASH", "SHOWER & EYEWASH", "COMBO SHOWER"]):
        station_type = "COMBINATION_SHOWER_EYEWASH"
    elif any(k in upper for k in ["DRENCH SHOWER", "CEILING DRENCH", "OVERHEAD SHOWER"]):
        station_type = "OVERHEAD_DRENCH_SHOWER"
    elif any(k in upper for k in ["PEDESTAL", "FREESTANDING EYEWASH"]):
        station_type = "PEDESTAL_EYEWASH_STATION"
    elif any(k in upper for k in ["WALL MOUNTED", "WALL-MOUNTED", "EYE/FACE WASH", "WALL EYEWASH"]):
        station_type = "WALL_MOUNTED_EYE_FACE_WASH"
    elif "EYEWASH" in upper or "EYE WASH" in upper:
        station_type = "PEDESTAL_EYEWASH_STATION"
    else:
        station_type = "GENERIC_SAFETY_SHOWER"

    # TMV Flow Capacity (L/min or converted GPM)
    capacity_lpm: Optional[float] = None
    lpm_m = re.search(r"(\d{2,3})\s*(?:L/MIN|LPM|L/M)\b", upper)
    if lpm_m:
        capacity_lpm = float(lpm_m.group(1))
    else:
        gpm_m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*GPM\b", upper)
        if gpm_m:
            capacity_lpm = round(float(gpm_m.group(1)) * 3.78541, 1)

    # Temperature Setpoint (°C)
    temp_c: Optional[float] = None
    deg_m = re.search(r"(\d{2})\s*(?:°C|DEG\s*C|DEGREES\s*C)\b", upper)
    if deg_m:
        temp_c = float(deg_m.group(1))

    # Cold Water Bypass / Anti-Scald
    if any(k in upper for k in ["FAIL-SAFE COLD", "FAIL SAFE COLD", "COLD WATER BYPASS", "COLD BYPASS"]):
        cold_bypass = "FAIL_SAFE_COLD_BYPASS"
    elif any(k in upper for k in ["HOT WATER SHUTOFF", "ANTI-SCALD", "POSITIVE SHUTOFF"]):
        cold_bypass = "POSITIVE_HOT_WATER_SHUTOFF"
    else:
        cold_bypass = "UNSPECIFIED"

    # Alarm Actuation
    if any(k in upper for k in ["FLOW SWITCH", "HORN AND STROBE", "AUDIBLE ALARM", "ALARM HORN", "HORN"]):
        alarm = "FLOW_SWITCH_ALARM_HORN"
    elif any(k in upper for k in ["STROBE", "ALARM BEACON", "VISUAL ALARM"]):
        alarm = "STROBE_ALARM_BEACON"
    elif any(k in upper for k in ["BMS CONTACT", "ALARM CONTACT", "SUPERVISORY SWITCH"]):
        alarm = "BMS_SUPERVISORY_CONTACT"
    else:
        alarm = "UNSPECIFIED"

    # Inlet Supply Pipe DN
    inlet_dn: Optional[str] = None
    dn_m = re.search(r"\bDN\s*(20|25|32|40|50)\b", upper)
    if dn_m:
        inlet_dn = f"DN{dn_m.group(1)}"
    else:
        inch_m = re.search(r'\b(3/4|1|1-1/4|1-1/2|2)["”]\s*(?:SUPPLY|INLET|PIPE)?\b', upper)
        if inch_m:
            in_map = {"3/4": "DN20", "1": "DN25", "1-1/4": "DN32", "1-1/2": "DN40", "2": "DN50"}
            inlet_dn = in_map.get(inch_m.group(1))

    # Service Hazard
    if any(k in upper for k in ["BATTERY ROOM", "BATTERY CHARGING", "BATTERY", "CHARGING AREA", "UPS BATTERY"]):
        service_hazard = "BATTERY_CHARGING_ROOM"
    elif any(k in upper for k in ["CHEMICAL", "DOSING", "CHLORINE", "CORROSIVE"]):
        service_hazard = "CHEMICAL_DOSING_AREA"
    elif any(k in upper for k in ["LABORATORY", "LAB CORRIDOR", "CLEANROOM"]):
        service_hazard = "LABORATORY_CORRIDOR"
    elif any(k in upper for k in ["WORKSHOP", "DECONTAMINATION"]):
        service_hazard = "WORKSHOP_DECONTAMINATION"
    else:
        service_hazard = "GENERAL_INDUSTRIAL_HAZARD"

    return {
        "raw_text": clean,
        "station_type": station_type,
        "tmv_capacity_lpm": capacity_lpm,
        "temperature_setpoint_celsius": temp_c,
        "cold_water_bypass": cold_bypass,
        "alarm_actuation": alarm,
        "inlet_drain_dn": inlet_dn,
        "service_hazard": service_hazard,
    }


def extract_emergency_shower_eyewash_tmv_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[EmergencyShowerEyewashTmvCallout]:
    results: List[EmergencyShowerEyewashTmvCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_emergency_shower_eyewash_tmv_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = EmergencyShowerEyewashTmvCallout(
            raw_text=parsed["raw_text"],
            station_type=parsed["station_type"],
            tmv_capacity_lpm=parsed["tmv_capacity_lpm"],
            temperature_setpoint_celsius=parsed["temperature_setpoint_celsius"],
            cold_water_bypass=parsed["cold_water_bypass"],
            alarm_actuation=parsed["alarm_actuation"],
            inlet_drain_dn=parsed["inlet_drain_dn"],
            service_hazard=parsed["service_hazard"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_tmv_capacity": parsed["tmv_capacity_lpm"] is not None,
                "has_alarm": parsed["alarm_actuation"] != "UNSPECIFIED",
                "has_cold_bypass": parsed["cold_water_bypass"] != "UNSPECIFIED",
            },
        )
        results.append(candidate)
    return results


def validate_emergency_shower_eyewash_tmv_system(
    candidates: List[EmergencyShowerEyewashTmvCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    hazard_counts: Dict[str, int] = {}
    alarmed_count = 0
    tmv_sized_count = 0

    for c in candidates:
        type_counts[c.station_type] = type_counts.get(c.station_type, 0) + 1
        hazard_counts[c.service_hazard] = hazard_counts.get(c.service_hazard, 0) + 1
        if c.alarm_actuation != "UNSPECIFIED":
            alarmed_count += 1
        if c.tmv_capacity_lpm is not None:
            tmv_sized_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "hazard_counts": hazard_counts,
        "alarmed_count": alarmed_count,
        "tmv_sized_count": tmv_sized_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
