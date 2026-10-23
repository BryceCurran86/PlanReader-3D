"""
Source High-Pressure Misting Fire Suppression Nozzle & Zoned Solenoid Valve Shadow Authority.

Extracts and validates high-pressure water mist nozzles, micro-orifice K-factors, 316L stainless steel tubing,
zoned high-pressure solenoid control valves, and critical equipment hazard zones strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class HighPressureWaterMistNozzleCallout:
    raw_text: str
    nozzle_type: str
    operating_pressure_bar: Optional[float]
    k_factor: Optional[str]
    droplet_size_microns: Optional[float]
    piping_material: str
    zone_solenoid_valve_dn: Optional[str]
    protected_hazard: str
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


def parse_high_pressure_water_mist_nozzle_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "WATER MIST",
        "HIGH PRESSURE MIST",
        "HPWM",
        "MIST NOZZLE",
        "MISTING NOZZLE",
        "HI-FOG",
        "SEM-SAFE",
        "MICROMIST",
        "MIST SUPPRESSION",
        "MIST HEAD",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("MIST" in upper or "MISTING" in upper)
        and ("NOZZLE" in upper or "HEAD" in upper or "SOLENOID" in upper or "SUPPRESSION" in upper or "VALVE" in upper)
    )
    if not has_trigger:
        return None

    # Nozzle Type
    if any(k in upper for k in ["AUTOMATIC BULB", "CLOSED NOZZLE", "GLASS BULB", "57°C", "68°C", "THERMAL BULB", "BULB HEAD"]):
        nozzle_type = "AUTOMATIC_BULB_MIST_HEAD"
    elif any(k in upper for k in ["OPEN NOZZLE", "DELUGE MIST", "OPEN DELUGE"]):
        nozzle_type = "OPEN_DELUGE_MIST_NOZZLE"
    elif any(k in upper for k in ["TOTAL FLOODING", "MICRO-ORIFICE", "MICRO ORIFICE"]):
        nozzle_type = "TOTAL_FLOODING_MICRO_ORIFICE"
    elif any(k in upper for k in ["HIGH PRESSURE", "HIGH-PRESSURE", "HPWM", "HI-FOG"]):
        nozzle_type = "HIGH_PRESSURE_WATER_MIST_NOZZLE"
    else:
        nozzle_type = "GENERIC_WATER_MIST_HEAD"

    # Operating Pressure (Bar or converted from MPa)
    operating_pressure_bar: Optional[float] = None
    bar_m = re.search(r"(\d{2,3})\s*BAR\b", upper)
    if bar_m:
        operating_pressure_bar = float(bar_m.group(1))
    else:
        mpa_m = re.search(r"(\d+(?:\.\d+)?)\s*MPA\b", upper)
        if mpa_m:
            operating_pressure_bar = round(float(mpa_m.group(1)) * 10.0, 1)

    # K-Factor
    k_factor: Optional[str] = None
    k_m = re.search(r"\bK\s*[-=:]?\s*(\d+(?:\.\d+)?)\b", upper)
    if k_m:
        k_factor = f"K{k_m.group(1)}"

    # Droplet Size (microns)
    droplet_size_um: Optional[float] = None
    drop_m = re.search(r"(\d{2,3})\s*(?:MICRONS?|UM|µM)\b", upper)
    if drop_m:
        droplet_size_um = float(drop_m.group(1))

    # Piping Material
    if any(k in upper for k in ["316L", "SS316L", "GRADE 316L", "316 STAINLESS"]):
        piping_material = "STAINLESS_STEEL_316L"
    elif any(k in upper for k in ["DUPLEX", "2205"]):
        piping_material = "DUPLEX_2205"
    elif any(k in upper for k in ["SEAMLESS TUBING", "STAINLESS TUBING", "SEAMLESS TUBE"]):
        piping_material = "SEAMLESS_SS_TUBING"
    else:
        piping_material = "UNSPECIFIED"

    # Zoned Solenoid Valve DN
    solenoid_dn: Optional[str] = None
    dn_m = re.search(r"\bDN\s*(15|20|25|32|40|50)\b", upper)
    if dn_m and ("SOLENOID" in upper or "VALVE" in upper or "ZONE" in upper):
        solenoid_dn = f"DN{dn_m.group(1)}"
    elif "SOLENOID VALVE" in upper:
        v_m = re.search(r"SOLENOID VALVE\s*(?:DN\s*)?(15|20|25|32|40|50)?", upper)
        if v_m and v_m.group(1):
            solenoid_dn = f"DN{v_m.group(1)}"

    # Protected Hazard
    if any(k in upper for k in ["TURBINE", "GENERATOR", "GENSET", "DIESEL GENERATOR"]):
        protected_hazard = "TURBINE_GENERATOR_ENCLOSURE"
    elif any(k in upper for k in ["DATA CENTER", "DATA CENTRE", "SERVER ROOM", "UPS ROOM"]):
        protected_hazard = "SERVER_ROOM_DATA_CENTER"
    elif any(k in upper for k in ["KITCHEN", "COOKING HOOD", "FRYER"]):
        protected_hazard = "COMMERCIAL_KITCHEN_HOOD"
    elif any(k in upper for k in ["ARCHIVE", "HERITAGE", "MUSEUM", "LIBRARY"]):
        protected_hazard = "HERITAGE_ARCHIVE_STORAGE"
    else:
        protected_hazard = "GENERAL_EQUIPMENT_ZONE"

    return {
        "raw_text": clean,
        "nozzle_type": nozzle_type,
        "operating_pressure_bar": operating_pressure_bar,
        "k_factor": k_factor,
        "droplet_size_microns": droplet_size_um,
        "piping_material": piping_material,
        "zone_solenoid_valve_dn": solenoid_dn,
        "protected_hazard": protected_hazard,
    }


def extract_high_pressure_water_mist_nozzle_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[HighPressureWaterMistNozzleCallout]:
    results: List[HighPressureWaterMistNozzleCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_high_pressure_water_mist_nozzle_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = HighPressureWaterMistNozzleCallout(
            raw_text=parsed["raw_text"],
            nozzle_type=parsed["nozzle_type"],
            operating_pressure_bar=parsed["operating_pressure_bar"],
            k_factor=parsed["k_factor"],
            droplet_size_microns=parsed["droplet_size_microns"],
            piping_material=parsed["piping_material"],
            zone_solenoid_valve_dn=parsed["zone_solenoid_valve_dn"],
            protected_hazard=parsed["protected_hazard"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_pressure": parsed["operating_pressure_bar"] is not None,
                "has_k_factor": parsed["k_factor"] is not None,
                "has_solenoid_valve": parsed["zone_solenoid_valve_dn"] is not None,
            },
        )
        results.append(candidate)
    return results


def validate_high_pressure_water_mist_nozzle_system(
    candidates: List[HighPressureWaterMistNozzleCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    hazard_counts: Dict[str, int] = {}
    pressurized_count = 0
    k_factor_count = 0

    for c in candidates:
        type_counts[c.nozzle_type] = type_counts.get(c.nozzle_type, 0) + 1
        hazard_counts[c.protected_hazard] = hazard_counts.get(c.protected_hazard, 0) + 1
        if c.operating_pressure_bar is not None:
            pressurized_count += 1
        if c.k_factor is not None:
            k_factor_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "hazard_counts": hazard_counts,
        "pressurized_count": pressurized_count,
        "k_factor_count": k_factor_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
