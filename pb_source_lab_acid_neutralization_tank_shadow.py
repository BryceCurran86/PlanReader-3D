"""
Source Laboratory Fume Hood Acid Neutralization Polypropylene Tank Shadow Authority.

Extracts and validates laboratory acid neutralization tanks, polypropylene under-sink traps,
limestone chip neutralization basins, pH monitoring sensors, and chemical fume hood drainage connections
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class LabAcidNeutralizationTankCallout:
    raw_text: str
    tank_type: str
    tank_capacity_litres: Optional[float]
    tank_material: str
    neutralization_medium: str
    monitoring_instrumentation: str
    inlet_outlet_dn: Optional[str]
    service_environment: str
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


def parse_lab_acid_neutralization_tank_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ACID NEUTRALIZATION",
        "ACID NEUTRALISATION",
        "NEUTRALIZATION TANK",
        "NEUTRALISATION TANK",
        "NEUTRALIZATION TRAP",
        "PH NEUTRALIZATION",
        "PH NEUTRALISATION",
        "LIMESTONE CHIP TANK",
        "ACID WASTE TANK",
        "ACID DILUTION BASIN",
        "ACID TRAP",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("ACID WASTE" in upper or "FUME HOOD" in upper or "LAB SINK" in upper or "CUP SINK" in upper)
        and ("NEUTRALIZ" in upper or "NEUTRALIS" in upper or "DILUTION" in upper or "PH" in upper or "LIMESTONE" in upper)
    )
    if not has_trigger:
        return None

    # Tank Type
    if any(k in upper for k in ["UNDER SINK", "UNDER-SINK", "POINT OF USE", "POU", "CUP SINK TRAP"]):
        tank_type = "UNDER_SINK_NEUTRALIZATION_TRAP"
    elif any(k in upper for k in ["AUTOMATIC PH", "DOSING SYSTEM", "ACTIVE PH", "CHEMICAL DOSING"]):
        tank_type = "AUTOMATIC_PH_NEUTRALIZATION_SYSTEM"
    elif any(k in upper for k in ["LIMESTONE", "CALCIUM CARBONATE", "MARBLE CHIP"]):
        tank_type = "LIMESTONE_CHIP_NEUTRALIZATION_TANK"
    elif any(k in upper for k in ["CENTRAL", "BELOW GROUND", "BASEMENT SUMP", "DILUTION BASIN"]):
        tank_type = "CENTRAL_DILUTION_BASIN"
    else:
        tank_type = "GENERIC_ACID_WASTE_TANK"

    # Tank Capacity (Litres or converted from Gallons)
    tank_capacity_l: Optional[float] = None
    litres_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:L|LTR|LITRES|LITERS)\b", upper)
    if litres_m:
        tank_capacity_l = float(litres_m.group(1))
    else:
        gal_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:GAL|GALLONS?)\b", upper)
        if gal_m:
            tank_capacity_l = round(float(gal_m.group(1)) * 3.78541, 1)

    # Tank Material
    if any(k in upper for k in ["POLYPROPYLENE", "FLAME RETARDANT PP"]) or re.search(r"\bPP\b", upper):
        tank_material = "POLYPROPYLENE_PP"
    elif any(k in upper for k in ["HDPE", "POLYETHYLENE"]):
        tank_material = "HIGH_DENSITY_POLYETHYLENE_HDPE"
    elif any(k in upper for k in ["PVDF", "KYNAR"]):
        tank_material = "PVDF"
    else:
        tank_material = "UNSPECIFIED"

    # Neutralization Medium
    if any(k in upper for k in ["LIMESTONE", "CALCIUM CARBONATE", "MARBLE CHIP"]):
        neutralization_medium = "CALCIUM_CARBONATE_LIMESTONE_CHIPS"
    elif any(k in upper for k in ["CAUSTIC", "NAOH", "CHEMICAL DOSING", "DOSING PUMP"]):
        neutralization_medium = "CAUSTIC_SODA_DOSING"
    elif any(k in upper for k in ["DILUTION BAFFLE", "WATER DILUTION"]):
        neutralization_medium = "DILUTION_WATER_BAFFLE"
    else:
        neutralization_medium = "UNSPECIFIED"

    # Monitoring / Instrumentation
    if any(k in upper for k in ["PH PROBE", "PH SENSOR", "PH CONTROLLER", "PH MONITOR"]):
        instrumentation = "PH_SENSOR_PROBE_CONTROLLER"
    elif any(k in upper for k in ["HIGH LEVEL ALARM", "LEVEL SWITCH", "ALARM PANEL"]):
        instrumentation = "HIGH_LEVEL_ALARM_SWITCH"
    elif any(k in upper for k in ["SAMPLING PORT", "TEST PORT", "SAMPLING BOWL"]):
        instrumentation = "SAMPLING_PORT_MANHOLE"
    else:
        instrumentation = "UNSPECIFIED"

    # Inlet / Outlet Pipe DN
    inlet_dn: Optional[str] = None
    dn_m = re.search(r"\bDN\s*(40|50|65|80|100|150)\b", upper)
    if dn_m:
        inlet_dn = f"DN{dn_m.group(1)}"
    else:
        inch_m = re.search(r'\b(1\.5|1-1/2|2|3|4)["”]\s*(?:ACID|PIPE|DRAIN|INLET|OUTLET)?\b', upper)
        if inch_m:
            in_map = {"1.5": "DN40", "1-1/2": "DN40", "2": "DN50", "3": "DN80", "4": "DN100"}
            inlet_dn = in_map.get(inch_m.group(1))

    # Service Environment
    if any(k in upper for k in ["FUME HOOD", "FUME CUPBOARD"]):
        service_environment = "LABORATORY_FUME_HOOD"
    elif any(k in upper for k in ["CUP SINK", "BENCH SINK"]):
        service_environment = "CUP_SINK"
    elif any(k in upper for k in ["CLEANROOM", "CLEAN ROOM"]):
        service_environment = "CLEANROOM_BENCH"
    else:
        service_environment = "GENERAL_ACID_WASTE"

    return {
        "raw_text": clean,
        "tank_type": tank_type,
        "tank_capacity_litres": tank_capacity_l,
        "tank_material": tank_material,
        "neutralization_medium": neutralization_medium,
        "monitoring_instrumentation": instrumentation,
        "inlet_outlet_dn": inlet_dn,
        "service_environment": service_environment,
    }


def extract_lab_acid_neutralization_tank_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[LabAcidNeutralizationTankCallout]:
    results: List[LabAcidNeutralizationTankCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_lab_acid_neutralization_tank_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = LabAcidNeutralizationTankCallout(
            raw_text=parsed["raw_text"],
            tank_type=parsed["tank_type"],
            tank_capacity_litres=parsed["tank_capacity_litres"],
            tank_material=parsed["tank_material"],
            neutralization_medium=parsed["neutralization_medium"],
            monitoring_instrumentation=parsed["monitoring_instrumentation"],
            inlet_outlet_dn=parsed["inlet_outlet_dn"],
            service_environment=parsed["service_environment"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_ph_sensor": parsed["monitoring_instrumentation"] == "PH_SENSOR_PROBE_CONTROLLER",
                "has_capacity": parsed["tank_capacity_litres"] is not None,
                "has_inlet_size": parsed["inlet_outlet_dn"] is not None,
            },
        )
        results.append(candidate)
    return results


def validate_lab_acid_neutralization_tank_system(
    candidates: List[LabAcidNeutralizationTankCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    material_counts: Dict[str, int] = {}
    instrumented_count = 0
    sized_capacity_count = 0

    for c in candidates:
        type_counts[c.tank_type] = type_counts.get(c.tank_type, 0) + 1
        material_counts[c.tank_material] = material_counts.get(c.tank_material, 0) + 1
        if c.monitoring_instrumentation != "UNSPECIFIED":
            instrumented_count += 1
        if c.tank_capacity_litres is not None:
            sized_capacity_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "material_counts": material_counts,
        "instrumented_count": instrumented_count,
        "sized_capacity_count": sized_capacity_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
