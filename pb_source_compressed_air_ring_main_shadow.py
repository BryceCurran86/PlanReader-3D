"""
Source Compressed Air Ring Main Aluminum Piping Drop Leg & Filter Regulator Shadow Authority.

Extracts and validates compressed air modular aluminum ring mains, swan-neck moisture drop legs,
workstation FRL units (Filter-Regulator-Lubricator), automatic condensate drains, and safety quick couplings
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class CompressedAirRingMainCallout:
    raw_text: str
    piping_system_type: str
    pipe_diameter_mm: Optional[float]
    operating_pressure_bar: Optional[float]
    point_of_use_frl: str
    condensate_drain: str
    quick_coupling_safety: str
    service_designation: str
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


def parse_compressed_air_ring_main_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "COMPRESSED AIR",
        "AIR RING MAIN",
        "PNEUMATIC RING MAIN",
        "TRANSAIR",
        "AIRNET",
        "FRL UNIT",
        "AIR DROP LEG",
        "SWAN NECK DROP",
        "SWAN-NECK",
        "COMPRESSED AIR DROP",
        "WORKSHOP AIR",
        "COMPRESSED AIR HEADER",
        "INSTRUMENT AIR",
        "BREATHING AIR",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("COMPRESSED AIR" in upper or "PNEUMATIC" in upper or "AIR HEADER" in upper)
        and ("PIPE" in upper or "RING MAIN" in upper or "DROP LEG" in upper or "FRL" in upper or "HEADER" in upper or "COUPLING" in upper)
    )
    if not has_trigger:
        return None

    # Piping System Type
    if any(k in upper for k in ["SWAN NECK", "SWAN-NECK", "GOOSENECK", "DROP LEG", "DROPPER"]):
        system_type = "SWAN_NECK_DROP_LEG"
    elif any(k in upper for k in ["FRL", "FILTER REGULATOR", "WORKSTATION DROP", "POINT OF USE", "POU"]):
        system_type = "FRL_UNIT_WORKSTATION"
    elif any(k in upper for k in ["HEADER", "DISTRIBUTION MANIFOLD", "MANIFOLD"]):
        system_type = "COMPRESSED_AIR_HEADER"
    elif any(k in upper for k in ["RING MAIN", "LOOP", "TRANSAIR", "AIRNET", "ALUMINUM PIPE", "ALUMINIUM PIPE"]):
        system_type = "ALUMINUM_COMPRESSED_AIR_RING_MAIN"
    else:
        system_type = "GENERIC_PNEUMATIC_PIPE"

    # Pipe Diameter (Outer Diameter in mm)
    diameter_mm: Optional[float] = None
    mm_m = re.search(r"\b(16|20|25|32|40|50|63|76|80|100)\s*MM\b", upper)
    if mm_m:
        diameter_mm = float(mm_m.group(1))
    else:
        dn_m = re.search(r"\bDN\s*(15|20|25|32|40|50|65|80|100)\b", upper)
        if dn_m:
            dn_map = {"15": 20.0, "20": 25.0, "25": 32.0, "32": 40.0, "40": 50.0, "50": 63.0, "65": 76.0, "80": 90.0, "100": 110.0}
            diameter_mm = dn_map.get(dn_m.group(1))

    # Operating Pressure (Bar or converted from kPa / psi)
    operating_pressure_bar: Optional[float] = None
    bar_m = re.search(r"(\d{1,2}(?:\.\d+)?)\s*BAR\b", upper)
    if bar_m:
        operating_pressure_bar = float(bar_m.group(1))
    else:
        kpa_m = re.search(r"(\d{3,4})\s*KPA\b", upper)
        if kpa_m:
            operating_pressure_bar = round(float(kpa_m.group(1)) / 100.0, 1)
        else:
            psi_m = re.search(r"(\d{2,3})\s*PSI\b", upper)
            if psi_m:
                operating_pressure_bar = round(float(psi_m.group(1)) * 0.0689476, 1)

    # Point of Use FRL
    if any(k in upper for k in ["FRL COMBO", "FILTER, REGULATOR, LUBRICATOR", "FILTER REGULATOR LUBRICATOR", "F.R.L."]):
        frl_unit = "FILTER_REGULATOR_LUBRICATOR_COMBO"
    elif any(k in upper for k in ["COALESCING", "OIL REMOVAL", "0.01 MICRON"]):
        frl_unit = "COALESCING_OIL_REMOVAL_FILTER"
    elif any(k in upper for k in ["FILTER REGULATOR", "FR UNIT", "FILTER/REGULATOR", "FRL"]):
        frl_unit = "FILTER_REGULATOR_ONLY"
    else:
        frl_unit = "UNSPECIFIED"

    # Condensate Drain
    if any(k in upper for k in ["AUTO FLOAT", "FLOAT DRAIN", "AUTOMATIC DRAIN", "AUTO DRAIN"]):
        condensate_drain = "AUTOMATIC_FLOAT_DRAIN"
    elif any(k in upper for k in ["ZERO LOSS", "ELECTRONIC DRAIN", "TIMER DRAIN"]):
        condensate_drain = "ZERO_LOSS_ELECTRONIC_DRAIN"
    elif any(k in upper for k in ["MANUAL DRAIN", "MANUAL BALL VALVE", "DRAIN VALVE"]):
        condensate_drain = "MANUAL_DRAIN_VALVE"
    else:
        condensate_drain = "UNSPECIFIED"

    # Quick Coupling Safety
    if any(k in upper for k in ["SAFETY COUPLING", "VENTING COUPLING", "VENTING SAFETY", "SAFETY QUICK COUPLING", "PUSH-BUTTON COUPLER", "ISO 4414"]):
        quick_coupling = "VENTING_SAFETY_QUICK_COUPLING"
    elif any(k in upper for k in ["EURO COUPLING", "HIGH FLOW COUPLER", "EURO STANDARD"]):
        quick_coupling = "EURO_HIGH_FLOW_COUPLING"
    elif any(k in upper for k in ["NITTO", "HI-CUPLA"]):
        quick_coupling = "NITTO_STYLE_PLUG"
    else:
        quick_coupling = "UNSPECIFIED"

    # Service Designation
    if any(k in upper for k in ["INSTRUMENT AIR", "DRY AIR"]):
        service_designation = "INSTRUMENT_AIR"
    elif any(k in upper for k in ["BREATHING AIR"]):
        service_designation = "BREATHING_AIR"
    elif any(k in upper for k in ["TOOL AIR", "WORKSHOP AIR", "GARAGE AIR", "PNEUMATIC TOOL"]):
        service_designation = "WORKSHOP_PNEUMATIC_TOOL"
    else:
        service_designation = "PLANT_COMPRESSED_AIR"

    return {
        "raw_text": clean,
        "piping_system_type": system_type,
        "pipe_diameter_mm": diameter_mm,
        "operating_pressure_bar": operating_pressure_bar,
        "point_of_use_frl": frl_unit,
        "condensate_drain": condensate_drain,
        "quick_coupling_safety": quick_coupling,
        "service_designation": service_designation,
    }


def extract_compressed_air_ring_main_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[CompressedAirRingMainCallout]:
    results: List[CompressedAirRingMainCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_compressed_air_ring_main_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = CompressedAirRingMainCallout(
            raw_text=parsed["raw_text"],
            piping_system_type=parsed["piping_system_type"],
            pipe_diameter_mm=parsed["pipe_diameter_mm"],
            operating_pressure_bar=parsed["operating_pressure_bar"],
            point_of_use_frl=parsed["point_of_use_frl"],
            condensate_drain=parsed["condensate_drain"],
            quick_coupling_safety=parsed["quick_coupling_safety"],
            service_designation=parsed["service_designation"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_diameter": parsed["pipe_diameter_mm"] is not None,
                "has_pressure": parsed["operating_pressure_bar"] is not None,
                "has_frl": parsed["point_of_use_frl"] != "UNSPECIFIED",
            },
        )
        results.append(candidate)
    return results


def validate_compressed_air_ring_main_system(
    candidates: List[CompressedAirRingMainCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    service_counts: Dict[str, int] = {}
    frl_count = 0
    sized_pipe_count = 0

    for c in candidates:
        type_counts[c.piping_system_type] = type_counts.get(c.piping_system_type, 0) + 1
        service_counts[c.service_designation] = service_counts.get(c.service_designation, 0) + 1
        if c.point_of_use_frl != "UNSPECIFIED":
            frl_count += 1
        if c.pipe_diameter_mm is not None:
            sized_pipe_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "service_counts": service_counts,
        "frl_count": frl_count,
        "sized_pipe_count": sized_pipe_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
