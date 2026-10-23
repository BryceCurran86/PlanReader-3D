"""
Source Condenser Water Cooling Tower Side Stream Centrifugal Separator Shadow Authority.

Extracts and validates cooling tower side-stream centrifugal separators, hydrocyclones, basin sweeper systems,
automated motorized purge valves, and solids recovery vessels strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class CoolingTowerSideStreamSeparatorCallout:
    raw_text: str
    separator_type: str
    flow_rate_lps: Optional[float]
    nominal_pipe_dn: Optional[str]
    purge_mechanism: str
    solids_recovery_vessel: str
    pump_skid_mount: str
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


def parse_cooling_tower_side_stream_separator_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CENTRIFUGAL SEPARATOR",
        "HYDROCYCLONE",
        "SIDE STREAM SEPARATOR",
        "SIDE-STREAM SEPARATOR",
        "SIDE STREAM FILTRATION",
        "SIDE-STREAM FILTRATION",
        "COOLING TOWER SEPARATOR",
        "BASIN SWEEPER",
        "LAKOS",
        "SOLIDS SEPARATOR",
        "VORTEX SEPARATOR",
        "SIDE STREAM FILTER",
        "SIDE-STREAM FILTER",
        "TOWER BASIN SEPARATOR",
        "SAND FILTER",
        "MEDIA FILTER",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("COOLING TOWER" in upper or "CONDENSER WATER" in upper)
        and ("SEPARATOR" in upper or "SIDE STREAM" in upper or "SIDE-STREAM" in upper or "HYDROCYCLONE" in upper or "FILTER" in upper or "FILTRATION" in upper)
    )
    if not has_trigger:
        return None

    # Separator Type
    if any(k in upper for k in ["CENTRIFUGAL", "HYDROCYCLONE", "VORTEX", "LAKOS"]):
        separator_type = "CENTRIFUGAL_HYDROCYCLONE"
    elif any(k in upper for k in ["SAND FILTER", "MEDIA FILTER", "MULTIMEDIA"]):
        separator_type = "SIDE_STREAM_SAND_FILTER"
    elif any(k in upper for k in ["BACKWASH", "AUTO-STRAINER", "AUTOMATIC STRAINER"]):
        separator_type = "AUTOMATIC_BACKWASH_STRAINER"
    elif any(k in upper for k in ["BASIN SWEEPER", "SWEEPER PIPING", "SWEEPER JET"]):
        separator_type = "BASIN_SWEEPER_PACKAGE"
    else:
        separator_type = "GENERIC_SIDE_STREAM_SEPARATOR"

    # Flow Rate (L/s or converted from GPM)
    flow_rate_lps: Optional[float] = None
    lps_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L/SEC)", upper)
    if lps_m:
        flow_rate_lps = float(lps_m.group(1))
    else:
        gpm_m = re.search(r"(\d+(?:\.\d+)?)\s*GPM\b", upper)
        if gpm_m:
            flow_rate_lps = round(float(gpm_m.group(1)) * 0.06309, 2)

    # Nominal Pipe Diameter
    nominal_pipe_dn: Optional[str] = None
    dn_m = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    if dn_m:
        nominal_pipe_dn = f"DN{dn_m.group(1)}"
    else:
        inch_m = re.search(r'(\d+(?:\.\d+)?)\s*(?:INCH|["”])\s*(?:PIPE|INLET|OUTLET|FLANGE)?', upper)
        if inch_m:
            val_in = float(inch_m.group(1))
            # Convert common inches to DN
            dn_map = {1.0: 25, 1.5: 40, 2.0: 50, 2.5: 65, 3.0: 80, 4.0: 100, 6.0: 150, 8.0: 200}
            if val_in in dn_map:
                nominal_pipe_dn = f"DN{dn_map[val_in]}"

    # Purge Mechanism
    if any(k in upper for k in ["MOTORIZED PURGE", "AUTOMATIC PURGE", "AUTO PURGE", "MOTORIZED VALVE"]):
        purge_mechanism = "AUTOMATIC_MOTORIZED_PURGE_VALVE"
    elif any(k in upper for k in ["SOLENOID PURGE", "TIMED PURGE", "SOLENOID VALVE"]):
        purge_mechanism = "SOLENOID_TIMED_PURGE"
    elif any(k in upper for k in ["MANUAL PURGE", "MANUAL BLOWDOWN", "MANUAL VALVE"]):
        purge_mechanism = "MANUAL_BLOWDOWN"
    else:
        purge_mechanism = "UNSPECIFIED"

    # Solids Recovery Vessel
    if any(k in upper for k in ["BAG VESSEL", "RECOVERY VESSEL", "SOLIDS RECOVERY", "FILTER BAG", "BAG FILTER"]):
        solids_recovery = "RECOVERY_BAG_VESSEL"
    elif any(k in upper for k in ["SETTLING CHAMBER", "COLLECTION CHAMBER", "SLUDGE BASIN"]):
        solids_recovery = "SLUDGE_SETTLING_CHAMBER"
    elif any(k in upper for k in ["BLOWDOWN TO DRAIN", "DRAIN DISCHARGE", "SUMP DISCHARGE"]):
        solids_recovery = "SUMP_BLOWDOWN_DRAIN"
    else:
        solids_recovery = "UNSPECIFIED"

    # Pump Skid Mount
    if any(k in upper for k in ["SKID", "PACKAGE UNIT", "PRE-ASSEMBLED"]):
        pump_skid_mount = "SKID_MOUNTED_PACKAGE"
    elif any(k in upper for k in ["BOOSTER PUMP", "CIRCULATING PUMP", "INTEGRAL PUMP", "SEPARATE PUMP"]):
        pump_skid_mount = "SEPARATE_BOOSTER_PUMP"
    elif any(k in upper for k in ["EDUCTOR", "SUCTION NOZZLE", "JET NOZZLE"]):
        pump_skid_mount = "BASIN_SUCTION_JET"
    else:
        pump_skid_mount = "UNSPECIFIED"

    # Service Designation
    if any(k in upper for k in ["COOLING TOWER BASIN", "TOWER BASIN", "BASIN SWEEPER"]):
        service_designation = "COOLING_TOWER_BASIN"
    elif any(k in upper for k in ["FLUID COOLER", "CLOSED CIRCUIT"]):
        service_designation = "CLOSED_CIRCUIT_FLUID_COOLER"
    elif any(k in upper for k in ["CHILLED WATER", "CHW"]):
        service_designation = "CHILLED_WATER"
    else:
        service_designation = "CONDENSER_WATER"

    return {
        "raw_text": clean,
        "separator_type": separator_type,
        "flow_rate_lps": flow_rate_lps,
        "nominal_pipe_dn": nominal_pipe_dn,
        "purge_mechanism": purge_mechanism,
        "solids_recovery_vessel": solids_recovery,
        "pump_skid_mount": pump_skid_mount,
        "service_designation": service_designation,
    }


def extract_cooling_tower_side_stream_separator_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[CoolingTowerSideStreamSeparatorCallout]:
    results: List[CoolingTowerSideStreamSeparatorCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_cooling_tower_side_stream_separator_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = CoolingTowerSideStreamSeparatorCallout(
            raw_text=parsed["raw_text"],
            separator_type=parsed["separator_type"],
            flow_rate_lps=parsed["flow_rate_lps"],
            nominal_pipe_dn=parsed["nominal_pipe_dn"],
            purge_mechanism=parsed["purge_mechanism"],
            solids_recovery_vessel=parsed["solids_recovery_vessel"],
            pump_skid_mount=parsed["pump_skid_mount"],
            service_designation=parsed["service_designation"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_auto_purge": parsed["purge_mechanism"] in ("AUTOMATIC_MOTORIZED_PURGE_VALVE", "SOLENOID_TIMED_PURGE"),
                "has_recovery_vessel": parsed["solids_recovery_vessel"] != "UNSPECIFIED",
            },
        )
        results.append(candidate)
    return results


def validate_cooling_tower_side_stream_separator_system(
    candidates: List[CoolingTowerSideStreamSeparatorCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    service_counts: Dict[str, int] = {}
    auto_purge_count = 0
    recovery_vessel_count = 0

    for c in candidates:
        type_counts[c.separator_type] = type_counts.get(c.separator_type, 0) + 1
        service_counts[c.service_designation] = service_counts.get(c.service_designation, 0) + 1
        if c.purge_mechanism in ("AUTOMATIC_MOTORIZED_PURGE_VALVE", "SOLENOID_TIMED_PURGE"):
            auto_purge_count += 1
        if c.solids_recovery_vessel != "UNSPECIFIED":
            recovery_vessel_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "service_counts": service_counts,
        "auto_purge_count": auto_purge_count,
        "recovery_vessel_count": recovery_vessel_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
