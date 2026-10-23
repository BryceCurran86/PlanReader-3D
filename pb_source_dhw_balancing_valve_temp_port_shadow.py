"""
Source Domestic Hot Water Recirculation Balancing Valve & Temperature Port Shadow Authority.

Extracts and validates DHW return balancing valves, thermostatic vs manual circuit setters,
return flow rates (L/min), design set temperatures (°C), test ports (P/T plugs/wells),
and legionella thermal disinfection bypass modes strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class DhwBalancingValveTempPortCallout:
    raw_text: str
    pipe_diameter_dn: str
    valve_type: str
    design_flow_lpm: float
    set_temperature_deg_c: float
    temperature_port_type: str
    disinfection_override: str
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


def parse_dhw_balancing_valve_temp_port_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "BALANCING VALVE",
        "CIRCUIT SETTER",
        "DHW RECIRCULATION",
        "DHW RETURN",
        "HOT WATER RETURN",
        "THERMAL BALANCING",
        "THERMOSTATIC BALANCING",
        "AUTOFLOW VALVE",
        "RETURN BALANCING",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("BALANCING" in upper or "RETURN" in upper) and ("DHW" in upper or "HOT WATER" in upper or "VALVE" in upper)
    )
    if not has_trigger:
        return None

    # Pipe size DN (e.g. DN15, DN20, DN25, DN32, DN40, DN50)
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    if dn_match:
        dn_size = f"DN{dn_match.group(1)}"
    else:
        mm_match = re.search(r"(\d{2,3})\s*MM\b", upper)
        if mm_match and int(mm_match.group(1)) in (15, 20, 25, 32, 40, 50, 65, 80):
            dn_size = f"DN{mm_match.group(1)}"
        else:
            dn_size = "DN20"  # standard DHW return branch size

    # Valve mechanism type
    if any(k in upper for k in ["PRESSURE INDEPENDENT", "PIBCV", "DYNAMIC"]):
        valve_type = "DYNAMIC_PRESSURE_INDEPENDENT"
    elif any(k in upper for k in ["MANUAL", "CIRCUIT SETTER", "ORIFICE", "DOUBLE REGULATING", "DRV"]):
        valve_type = "MANUAL_CIRCUIT_SETTER_ORIFICE"
    elif any(k in upper for k in ["AUTOFLOW", "AUTOMATIC CARTRIDGE"]):
        valve_type = "AUTOMATIC_CARTRIDGE_BALANCING"
    elif any(k in upper for k in ["THERMAL", "THERMOSTATIC", "MTCV", "TEMPERING"]):
        valve_type = "THERMAL_BALANCING_VALVE"
    else:
        valve_type = "THERMAL_BALANCING_VALVE"

    # Design return flow rate in L/min
    flow_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/MIN|LPM|L\/MIN|LITRES\s*(?:PER|\/)\s*MIN(?:UTE)?)", upper)
    if flow_match:
        flow_lpm = float(flow_match.group(1))
    else:
        flow_lpm = 2.0  # typical standard return branch flow

    # Temperature set point (°C)
    temp_match = re.search(r"(?:SET\s*(?:POINT|AT|TEMP)?\s*:?\s*|@\s*)?(\d{2}(?:\.\d+)?)\s*(?:°C|DEG\s*C|DEGREES\s*C|°\s*C)", upper)
    if temp_match and 40.0 <= float(temp_match.group(1)) <= 85.0:
        set_temp = float(temp_match.group(1))
    else:
        set_temp = 55.0  # standard BCA/NCC AS3500.4 minimum recirculation temperature

    # Temperature test port type
    if any(k in upper for k in ["P/T", "PT PLUG", "TEST POINT", "BINDER POINT", "NEEDLE POINT", "TEST PORT"]):
        test_port = "PT_PRESSURE_TEMPERATURE_PLUG"
    elif any(k in upper for k in ["IMMERSION WELL", "THERMOWELL"]):
        test_port = "DIRECT_IMMERSION_WELL"
    elif any(k in upper for k in ["DIAL THERMOMETER", "TEMPERATURE GAUGE"]):
        test_port = "DIAL_THERMOMETER_GAUGE"
    elif "DRY WELL" in upper:
        test_port = "INTEGRAL_DRY_WELL"
    else:
        test_port = "PT_PRESSURE_TEMPERATURE_PLUG"

    # Legionella thermal disinfection override
    if any(k in upper for k in ["DISINFECTION", "LEGIONELLA", "THERMAL PURGE", "70°C", "70 DEG C"]):
        disinfection = "AUTOMATIC_LEGIONELLA_DISINFECTION_BYPASS"
    elif any(k in upper for k in ["MANUAL OVERRIDE", "PURGE LEVER"]):
        disinfection = "MANUAL_PURGE_OVERRIDE"
    else:
        disinfection = "NONE"

    return {
        "raw_text": clean,
        "pipe_diameter_dn": dn_size,
        "valve_type": valve_type,
        "design_flow_lpm": flow_lpm,
        "set_temperature_deg_c": set_temp,
        "temperature_port_type": test_port,
        "disinfection_override": disinfection,
    }


class SourceDhwBalancingValveTempPortShadowAuthority:
    """Authority for domestic hot water recirculation balancing valves in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[DhwBalancingValveTempPortCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[DhwBalancingValveTempPortCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[DhwBalancingValveTempPortCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_dhw_balancing_valve_temp_port_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = DhwBalancingValveTempPortCallout(
                raw_text=parsed["raw_text"],
                pipe_diameter_dn=parsed["pipe_diameter_dn"],
                valve_type=parsed["valve_type"],
                design_flow_lpm=parsed["design_flow_lpm"],
                set_temperature_deg_c=parsed["set_temperature_deg_c"],
                temperature_port_type=parsed["temperature_port_type"],
                disinfection_override=parsed["disinfection_override"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
