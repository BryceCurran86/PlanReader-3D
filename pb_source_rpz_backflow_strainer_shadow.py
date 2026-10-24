"""
Source Cold Water RPZ Backflow Prevention Device Strainer Shadow Authority.

Extracts and validates reduced pressure zone (RPZ/RPZD) backflow preventers, upstream Y-strainers,
high/medium hazard classifications, nominal diameters (DN), lockable isolation valves, and air-gap tundish drains
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class RpzBackflowStrainerCallout:
    raw_text: str
    device_type: str
    hazard_rating: str
    nominal_size_dn: str
    strainer_type: str
    isolation_valves: str
    relief_drain_air_gap_tundish: str
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


def parse_rpz_backflow_strainer_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "RPZ",
        "RPZD",
        "REDUCED PRESSURE ZONE",
        "BACKFLOW PREVENTER",
        "BACKFLOW PREVENTION",
        "DCV",
        "DOUBLE CHECK VALVE",
        "DUAL CHECK",
        "BACKFLOW DEVICE",
        "VACUUM BREAKER",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("BACKFLOW" in upper) and ("VALVE" in upper or "DEVICE" in upper or "PREVENTION" in upper)
    )
    if not has_trigger:
        return None

    # Device classification
    if any(k in upper for k in ["DOUBLE CHECK", "DCV"]):
        device = "DOUBLE_CHECK_VALVE_DCV"
    elif "DUAL CHECK" in upper:
        device = "DUAL_CHECK_VALVE"
    elif any(k in upper for k in ["VACUUM BREAKER", "ATMOSPHERIC"]):
        device = "VACUUM_BREAKER"
    elif any(k in upper for k in ["RPZ", "RPZD", "REDUCED PRESSURE"]):
        device = "REDUCED_PRESSURE_ZONE_RPZ"
    else:
        device = "REDUCED_PRESSURE_ZONE_RPZ"

    # Hazard rating
    if any(k in upper for k in ["MEDIUM HAZARD", "MEDIUM-HAZARD"]):
        hazard = "MEDIUM_HAZARD"
    elif any(k in upper for k in ["LOW HAZARD", "LOW-HAZARD"]):
        hazard = "LOW_HAZARD"
    elif any(k in upper for k in ["HIGH HAZARD", "HIGH-HAZARD"]):
        hazard = "HIGH_HAZARD"
    else:
        if device == "REDUCED_PRESSURE_ZONE_RPZ":
            hazard = "HIGH_HAZARD"  # standard requirement for RPZ
        elif device == "DOUBLE_CHECK_VALVE_DCV":
            hazard = "MEDIUM_HAZARD"
        else:
            hazard = "LOW_HAZARD"

    # Nominal DN size (e.g. DN25, DN32, DN40, DN50, DN65, DN80, DN100)
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    if dn_match:
        dn_size = f"DN{dn_match.group(1)}"
    else:
        mm_match = re.search(r"(\d{2,3})\s*MM\b", upper)
        if mm_match and int(mm_match.group(1)) in (15, 20, 25, 32, 40, 50, 65, 80, 100, 150):
            dn_size = f"DN{mm_match.group(1)}"
        else:
            dn_size = "DN50"  # standard commercial RPZ size

    # Upstream strainer
    if any(k in upper for k in ["WITHOUT STRAINER", "NO STRAINER"]):
        strainer = "NONE"
    elif "BASKET STRAINER" in upper:
        strainer = "BASKET_STRAINER"
    elif "INTEGRAL STRAINER" in upper:
        strainer = "INTEGRAL_STRAINER"
    elif any(k in upper for k in ["Y-STRAINER", "Y STRAINER", "Y-TYPE", "STRAINER"]):
        strainer = "Y_TYPE_STRAINER_BLOWDOWN"
    else:
        strainer = "Y_TYPE_STRAINER_BLOWDOWN"

    # Isolation valves
    if any(k in upper for k in ["GATE VALVE", "OS&Y", "RESILIENT SEAT"]):
        isolation = "RESILIENT_SEAT_GATE_VALVES_OSY"
    elif any(k in upper for k in ["BUTTERFLY VALVE", "GEAR OPERATED"]):
        isolation = "BUTTERFLY_VALVES_GEAR_OPERATED"
    elif any(k in upper for k in ["BALL VALVE", "FULL BORE", "LOCKABLE"]):
        isolation = "FULL_BORE_BALL_VALVES_LOCKABLE"
    else:
        isolation = "FULL_BORE_BALL_VALVES_LOCKABLE"

    # Tundish air-gap relief drainage
    if any(k in upper for k in ["TUNDISH", "AIR GAP FUNNEL", "AIR GAP DRAIN", "TUNDISH DRAIN", "AIR GAP"]):
        relief = "TUNDISH_AIR_GAP_DRAIN"
    elif any(k in upper for k in ["DIRECT RUNOUT", "DIRECT DRAIN"]):
        relief = "DIRECT_DRAIN_RUNOUT"
    else:
        relief = "TUNDISH_AIR_GAP_DRAIN"

    return {
        "raw_text": clean,
        "device_type": device,
        "hazard_rating": hazard,
        "nominal_size_dn": dn_size,
        "strainer_type": strainer,
        "isolation_valves": isolation,
        "relief_drain_air_gap_tundish": relief,
    }


class SourceRpzBackflowStrainerShadowAuthority:
    """Authority for RPZ backflow preventers in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[RpzBackflowStrainerCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[RpzBackflowStrainerCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[RpzBackflowStrainerCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_rpz_backflow_strainer_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = RpzBackflowStrainerCallout(
                raw_text=parsed["raw_text"],
                device_type=parsed["device_type"],
                hazard_rating=parsed["hazard_rating"],
                nominal_size_dn=parsed["nominal_size_dn"],
                strainer_type=parsed["strainer_type"],
                isolation_valves=parsed["isolation_valves"],
                relief_drain_air_gap_tundish=parsed["relief_drain_air_gap_tundish"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
