"""
Source Fire Sprinkler Dry Pipe Accelerator Quick Opening Device Shadow Authority.

Extracts and validates fire sprinkler dry pipe accelerators, system exhausters, quick-opening devices (QOD),
integral anti-flooding devices, trim pressure gauges, and cold/freezing hazard protection zones strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SprinklerDryPipeAcceleratorCallout:
    raw_text: str
    device_type: str
    valve_connection_dn: Optional[str]
    dry_valve_size_dn: Optional[str]
    anti_flooding_device: str
    trim_pressure_gauges: str
    rated_operating_pressure_kpa: Optional[float]
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


def parse_sprinkler_dry_pipe_accelerator_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "DRY PIPE ACCELERATOR",
        "DRY VALVE ACCELERATOR",
        "QUICK OPENING DEVICE",
        "QUICK-OPENING DEVICE",
        "QOD",
        "SYSTEM EXHAUSTER",
        "SPRINKLER ACCELERATOR",
        "DIFFERENTIAL ACCELERATOR",
        "ACCELERATOR TRIM",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("ACCELERATOR" in upper or "EXHAUSTER" in upper)
        and ("DRY PIPE" in upper or "DRY VALVE" in upper or "SPRINKLER" in upper)
    )
    if not has_trigger:
        return None

    # Device Type
    if "EXHAUSTER" in upper:
        device_type = "SYSTEM_EXHAUSTER"
    elif "ACCELERATOR" in upper:
        device_type = "DRY_PIPE_ACCELERATOR"
    elif any(k in upper for k in ["QUICK OPENING", "QUICK-OPENING", "QOD"]):
        device_type = "QUICK_OPENING_DEVICE"
    else:
        device_type = "GENERIC_DRY_VALVE_TRIM"

    # Valve Connection DN
    valve_connection_dn: Optional[str] = None
    conn_m = re.search(r"\bDN\s*(15|20|25|32)\b", upper)
    if conn_m:
        valve_connection_dn = f"DN{conn_m.group(1)}"
    else:
        inch_m = re.search(r'\b(1/2|3/4|1)["”]\s*(?:NPT|TRIM|VALVE|CONNECTION)?\b', upper)
        if inch_m:
            in_map = {"1/2": "DN15", "3/4": "DN20", "1": "DN25"}
            valve_connection_dn = in_map.get(inch_m.group(1))

    # Associated Dry Valve Size DN
    dry_valve_size_dn: Optional[str] = None
    dv_m = re.search(r"\bDN\s*(80|100|150|200)\b", upper)
    if dv_m:
        dry_valve_size_dn = f"DN{dv_m.group(1)}"
    else:
        inch_dv = re.search(r'\b([3468])["”]\s*(?:DRY\s*PIPE\s*VALVE|DRY\s*VALVE|VALVE)?\b', upper)
        if inch_dv:
            dv_map = {"3": "DN80", "4": "DN100", "6": "DN150", "8": "DN200"}
            dry_valve_size_dn = dv_map.get(inch_dv.group(1))

    # Anti-Flooding Device
    if any(k in upper for k in ["INTEGRAL ANTI-FLOOD", "BUILT-IN ANTI-FLOOD", "INTEGRAL ANTI FLOOD", "ANTI-FLOODING DEVICE", "ANTI-FLOOD DEVICE"]):
        anti_flooding = "INTEGRAL_ANTI_FLOODING_DEVICE"
    elif any(k in upper for k in ["ANTI-FLOOD BALL VALVE", "EXTERNAL ANTI-FLOOD"]):
        anti_flooding = "SEPARATE_ANTI_FLOOD_BALL_VALVE"
    elif any(k in upper for k in ["RESTRICTION ORIFICE", "AIR RESTRICTION"]):
        anti_flooding = "AIR_RESTRICTION_ORIFICE"
    else:
        anti_flooding = "UNSPECIFIED"

    # Trim Pressure Gauges
    if any(k in upper for k in ["AIR/WATER", "DUAL PRESSURE GAUGE", "AIR AND WATER GAUGE", "AIR & WATER GAUGE"]):
        trim_gauges = "AIR_WATER_DUAL_PRESSURE_GAUGE"
    elif any(k in upper for k in ["AIR GAUGE", "AIR PRESSURE GAUGE"]):
        trim_gauges = "AIR_PRESSURE_GAUGE"
    elif any(k in upper for k in ["PRESSURE GAUGE", "TRIM GAUGE"]):
        trim_gauges = "SYSTEM_TRIM_GAUGE"
    else:
        trim_gauges = "UNSPECIFIED"

    # Rated Operating Pressure (kPa or converted from psi)
    operating_pressure_kpa: Optional[float] = None
    kpa_m = re.search(r"(\d{3,4})\s*KPA\b", upper)
    if kpa_m:
        operating_pressure_kpa = float(kpa_m.group(1))
    else:
        psi_m = re.search(r"(\d{2,3})\s*PSI\b", upper)
        if psi_m:
            operating_pressure_kpa = round(float(psi_m.group(1)) * 6.89476, 1)

    # Service Hazard
    if any(k in upper for k in ["COLD STORAGE", "FREEZER", "REFRIGERATED", "COOL ROOM"]):
        service_hazard = "REFRIGERATED_WAREHOUSE"
    elif any(k in upper for k in ["CAR PARK", "PARKING", "GARAGE"]):
        service_hazard = "CAR_PARK"
    elif any(k in upper for k in ["FREEZING", "UNHEATED", "CANOPY", "LOADING DOCK"]):
        service_hazard = "FREEZING_EXPOSURE"
    elif any(k in upper for k in ["ATTIC", "ROOF SPACE"]):
        service_hazard = "ATTIC_PROTECTION"
    else:
        service_hazard = "GENERIC_DRY_ZONE"

    return {
        "raw_text": clean,
        "device_type": device_type,
        "valve_connection_dn": valve_connection_dn,
        "dry_valve_size_dn": dry_valve_size_dn,
        "anti_flooding_device": anti_flooding,
        "trim_pressure_gauges": trim_gauges,
        "rated_operating_pressure_kpa": operating_pressure_kpa,
        "service_hazard": service_hazard,
    }


def extract_sprinkler_dry_pipe_accelerator_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SprinklerDryPipeAcceleratorCallout]:
    results: List[SprinklerDryPipeAcceleratorCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_sprinkler_dry_pipe_accelerator_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = SprinklerDryPipeAcceleratorCallout(
            raw_text=parsed["raw_text"],
            device_type=parsed["device_type"],
            valve_connection_dn=parsed["valve_connection_dn"],
            dry_valve_size_dn=parsed["dry_valve_size_dn"],
            anti_flooding_device=parsed["anti_flooding_device"],
            trim_pressure_gauges=parsed["trim_pressure_gauges"],
            rated_operating_pressure_kpa=parsed["rated_operating_pressure_kpa"],
            service_hazard=parsed["service_hazard"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_anti_flooding": parsed["anti_flooding_device"] != "UNSPECIFIED",
                "has_dry_valve_size": parsed["dry_valve_size_dn"] is not None,
                "has_pressure_rating": parsed["rated_operating_pressure_kpa"] is not None,
            },
        )
        results.append(candidate)
    return results


def validate_sprinkler_dry_pipe_accelerator_system(
    candidates: List[SprinklerDryPipeAcceleratorCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    hazard_counts: Dict[str, int] = {}
    anti_flood_count = 0
    sized_dry_valve_count = 0

    for c in candidates:
        type_counts[c.device_type] = type_counts.get(c.device_type, 0) + 1
        hazard_counts[c.service_hazard] = hazard_counts.get(c.service_hazard, 0) + 1
        if c.anti_flooding_device != "UNSPECIFIED":
            anti_flood_count += 1
        if c.dry_valve_size_dn is not None:
            sized_dry_valve_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "hazard_counts": hazard_counts,
        "anti_flood_count": anti_flood_count,
        "sized_dry_valve_count": sized_dry_valve_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
