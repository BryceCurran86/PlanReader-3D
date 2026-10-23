"""
Source Emergency Eyewash & Safety Shower Station Shadow Authority.

Extracts and validates combination safety showers, pedestal and wall-mounted eyewash stations,
supply diameters (DN), drench and eyewash flow rates (L/min), tepid water TMVs, and alarm beacons strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class EyewashSafetyShowerCallout:
    raw_text: str
    station_type: str
    supply_pipe_dn: str
    bowl_material: str
    drench_shower_flow_lpm: float
    eyewash_flow_lpm: float
    tepid_water_tmv_included: bool
    flow_switch_alarm: str
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


def parse_eyewash_safety_shower_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SAFETY SHOWER",
        "EMERGENCY SHOWER",
        "EMERGENCY EYEWASH",
        "EYE WASH",
        "EYEWASH",
        "DRENCH SHOWER",
        "COMBINATION SHOWER/EYEWASH",
        "COMBINATION SHOWER & EYEWASH",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Supply Pipe DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    supply_dn = f"DN{dn_match.group(1)}" if dn_match else "DN25"

    # Station type
    if ("SHOWER" in upper and "EYE" in upper) or "COMBINATION" in upper:
        station_type = "COMBINATION_SHOWER_AND_EYEWASH"
        shower_flow = 76.0
        eye_flow = 12.0
    elif "SHOWER" in upper or "DRENCH" in upper:
        station_type = "OVERHEAD_DRENCH_SHOWER"
        shower_flow = 76.0
        eye_flow = 0.0
    elif "WALL" in upper:
        station_type = "WALL_MOUNTED_EYEWASH"
        shower_flow = 0.0
        eye_flow = 12.0
    elif "PEDESTAL" in upper or "COLUMN" in upper:
        station_type = "PEDESTAL_EYEWASH_STATION"
        shower_flow = 0.0
        eye_flow = 12.0
    else:
        station_type = "COMBINATION_SHOWER_AND_EYEWASH"
        shower_flow = 76.0
        eye_flow = 12.0

    # Flow rate overrides if specified in text
    flow_matches = re.findall(r"(\d+(?:\.\d+)?)\s*(?:L/MIN|LPM)", upper)
    if flow_matches:
        if len(flow_matches) == 1:
            val = float(flow_matches[0])
            if val >= 50.0:
                shower_flow = val
            else:
                eye_flow = val
        elif len(flow_matches) >= 2:
            shower_flow = float(flow_matches[0])
            eye_flow = float(flow_matches[1])

    # Bowl material
    if "SS" in upper or "STAINLESS" in upper or "316" in upper or "304" in upper:
        bowl_mat = "STAINLESS_STEEL_316"
    elif "PLASTIC" in upper or "ABS" in upper or "YELLOW" in upper:
        bowl_mat = "HIGH_VISIBILITY_ABS_PLASTIC"
    else:
        bowl_mat = "STAINLESS_STEEL_316"

    # Tepid water TMV
    tepid = any(k in upper for k in ["TEPID", "TMV", "TEMPERING", "MIXING VALVE", "WARM WATER"])

    # Flow switch & alarm
    if any(k in upper for k in ["ALARM", "BEACON", "STROBE", "FLOW SWITCH", "HORN", "SIREN"]):
        alarm = "FLOW_SWITCH_WITH_BEACON_ALARM"
    else:
        alarm = "NONE"

    return {
        "station_type": station_type,
        "supply_pipe_dn": supply_dn,
        "bowl_material": bowl_mat,
        "drench_shower_flow_lpm": shower_flow,
        "eyewash_flow_lpm": eye_flow,
        "tepid_water_tmv_included": tepid,
        "flow_switch_alarm": alarm,
    }


class SourceEyewashSafetyShowerShadowAuthority:
    """Authority for extracting and managing emergency eyewash & safety shower stations in shadow mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[EyewashSafetyShowerCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[EyewashSafetyShowerCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_eyewash_safety_shower_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["station_type"], parsed["supply_pipe_dn"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = EyewashSafetyShowerCallout(
                raw_text=text,
                station_type=parsed["station_type"],
                supply_pipe_dn=parsed["supply_pipe_dn"],
                bowl_material=parsed["bowl_material"],
                drench_shower_flow_lpm=parsed["drench_shower_flow_lpm"],
                eyewash_flow_lpm=parsed["eyewash_flow_lpm"],
                tepid_water_tmv_included=parsed["tepid_water_tmv_included"],
                flow_switch_alarm=parsed["flow_switch_alarm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
