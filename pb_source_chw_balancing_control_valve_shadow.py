"""
Source Chilled Water Balancing & Modulating Control Valve Shadow Authority.

Extracts and validates CHW modulating control valves, pressure-independent balancing assemblies (PICVs),
design flow rates (L/s), differential pressure thresholds (kPa), actuator signals (0-10V, 4-20mA, BACnet),
and fail-safe spring return positions strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ChwBalancingControlValveCallout:
    raw_text: str
    pipe_diameter_dn: str
    valve_type: str
    design_flow_lps: float
    differential_pressure_kpa: float
    actuator_signal: str
    fail_safe_position: str
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


def parse_chw_balancing_control_valve_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CHW CONTROL VALVE",
        "CHILLED WATER VALVE",
        "PICV",
        "PRESSURE INDEPENDENT CONTROL",
        "MODULATING VALVE",
        "2-WAY CONTROL VALVE",
        "TWO-WAY VALVE",
        "3-WAY CONTROL VALVE",
        "THREE-WAY VALVE",
        "CHW BALANCING",
        "FCU CONTROL VALVE",
        "AHU CONTROL VALVE",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("CHW" in upper or "CHILLED" in upper) and ("VALVE" in upper or "ACTUATOR" in upper)
    )
    if not has_trigger:
        return None

    # Pipe diameter DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    pipe_dn = f"DN{dn_match.group(1)}" if dn_match else "DN25"

    # Valve Type
    if "PICV" in upper or "PRESSURE INDEPENDENT" in upper:
        valve_type = "PRESSURE_INDEPENDENT_CONTROL_VALVE_PICV"
    elif "3-WAY" in upper or "THREE-WAY" in upper or "3 WAY" in upper or "MIXING" in upper:
        valve_type = "THREE_WAY_MODULATING_MIXING"
    elif "2-WAY" in upper or "TWO-WAY" in upper or "2 WAY" in upper or "MODULATING" in upper:
        valve_type = "TWO_WAY_MODULATING"
    elif "CHARACTERIZED BALL" in upper or "CCV" in upper:
        valve_type = "CHARACTERIZED_CONTROL_BALL_VALVE"
    else:
        valve_type = "TWO_WAY_MODULATING"

    # Flow rate L/s
    flow_lps = 0.0
    flow_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L/SEC)", upper)
    if flow_match:
        flow_lps = float(flow_match.group(1))
    else:
        lpm_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/MIN|LPM)", upper)
        if lpm_match:
            flow_lps = round(float(lpm_match.group(1)) / 60.0, 3)

    # Differential pressure kPa
    dp_kpa = 0.0
    dp_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:KPA|KILOPASCAL)", upper)
    if dp_match:
        dp_kpa = float(dp_match.group(1))
    elif "PICV" in valve_type:
        dp_kpa = 20.0  # standard minimum operating delta-P

    # Actuator control signal
    if "BACNET" in upper or "MODBUS" in upper or "DIGITAL" in upper:
        actuator_signal = "BACNET_MODBUS_DIGITAL"
    elif "4-20MA" in upper or "4-20 MA" in upper:
        actuator_signal = "4_20MA_CURRENT_LOOP"
    elif "0-10V" in upper or "0-10 V" in upper or "2-10V" in upper or "ANALOG" in upper:
        actuator_signal = "0_10V_ANALOG"
    elif "FLOATING" in upper or "3-POINT" in upper:
        actuator_signal = "FLOATING_3_POINT"
    else:
        actuator_signal = "0_10V_ANALOG"

    # Fail-safe position
    if "NORMALLY OPEN" in upper or "FAIL OPEN" in upper or "N.O." in upper:
        fail_safe = "SPRING_RETURN_NORMALLY_OPEN"
    elif "NORMALLY CLOSED" in upper or "FAIL CLOSED" in upper or "N.C." in upper:
        fail_safe = "SPRING_RETURN_NORMALLY_CLOSED"
    elif "NON-SPRING" in upper or "FAIL IN PLACE" in upper:
        fail_safe = "FAIL_IN_PLACE"
    else:
        fail_safe = "SPRING_RETURN_NORMALLY_CLOSED"

    return {
        "pipe_diameter_dn": pipe_dn,
        "valve_type": valve_type,
        "design_flow_lps": flow_lps,
        "differential_pressure_kpa": dp_kpa,
        "actuator_signal": actuator_signal,
        "fail_safe_position": fail_safe,
    }


class SourceChwBalancingControlValveShadowAuthority:
    """Authority for extracting and managing CHW balancing and control valves in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[ChwBalancingControlValveCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[ChwBalancingControlValveCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_chw_balancing_control_valve_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["pipe_diameter_dn"], parsed["valve_type"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = ChwBalancingControlValveCallout(
                raw_text=text,
                pipe_diameter_dn=parsed["pipe_diameter_dn"],
                valve_type=parsed["valve_type"],
                design_flow_lps=parsed["design_flow_lps"],
                differential_pressure_kpa=parsed["differential_pressure_kpa"],
                actuator_signal=parsed["actuator_signal"],
                fail_safe_position=parsed["fail_safe_position"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
