"""
Source Natural Gas / LPG Service Regulator & OPSO Valve Shadow Authority.

Extracts and validates gas regulators, OPSO overpressure shutoff valves, inlet/outlet pressures (kPa),
pipe sizes (DN), and relief vent connections strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GasRegulatorOpsoCallout:
    raw_text: str
    gas_service_type: str
    regulator_type: str
    pipe_connection_dn: str
    inlet_pressure_kpa: float
    outlet_pressure_kpa: float
    opso_trip_kpa: float
    relief_vent_dn: str
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


def parse_gas_regulator_opso_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "GAS REGULATOR",
        "PRESSURE REGULATOR",
        "OPSO",
        "SLAM SHUT",
        "SLAM-SHUT",
        "GAS SERVICE REGULATOR",
        "LPG REGULATOR",
        "NATURAL GAS REGULATOR",
        "GAS METER REGULATOR",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Gas Service Type
    if "LPG" in upper or "PROPANE" in upper or "BOTTLE" in upper:
        service = "LIQUEFIED_PETROLEUM_GAS_LPG"
    else:
        service = "NATURAL_GAS_NG"

    # Pipe connection DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    pipe_dn = f"DN{dn_match.group(1)}" if dn_match else "DN25"

    # Regulator type
    if "LPG" in service and ("FIRST STAGE" in upper or "HIGH PRESSURE" in upper):
        reg_type = "FIRST_STAGE_LPG_HIGH_PRESSURE"
    elif "APPLIANCE" in upper or "SECONDARY" in upper:
        reg_type = "APPLIANCE_PRESSURE_REGULATOR"
    else:
        reg_type = "SERVICE_REGULATOR_WITH_INTEGRAL_OPSO"

    # Inlet pressure kPa
    inlet_kpa = 200.0 if service == "NATURAL_GAS_NG" else 1000.0
    in_match = re.search(r"(?:INLET|IN)\s*(?:PRESSURE)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:KPA|BAR)?", upper)
    if in_match:
        inlet_kpa = float(in_match.group(1))

    # Outlet delivery pressure kPa
    outlet_kpa = 2.75
    if "MBAR" in upper:
        mbar_match = re.search(r"(\d+(?:\.\d+)?)\s*MBAR", upper)
        if mbar_match:
            outlet_kpa = round(float(mbar_match.group(1)) * 0.1, 2)
    else:
        out_match = re.search(r"(?:OUTLET|OUT|DELIVERY)\s*(?:PRESSURE)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:KPA)?", upper)
        if out_match:
            outlet_kpa = float(out_match.group(1))
        else:
            kpa_low = re.search(r"\b(\d+(?:\.\d+)?)\s*KPA\b", upper)
            if kpa_low:
                val = float(kpa_low.group(1))
                if val <= 15.0:
                    outlet_kpa = val

    # OPSO trip pressure kPa
    opso_trip = round(outlet_kpa * 2.0, 2)
    opso_match = re.search(r"(?:OPSO|SLAM\s*SHUT|TRIP)\s*(?:AT|SET)?\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:KPA)?", upper)
    if opso_match:
        opso_trip = float(opso_match.group(1))

    # Relief vent DN
    vent_match = re.search(r"(?:VENT|ATMOSPHERIC|RELIEF)\s*(?:[A-Z]+\s+)?DN\s*(\d{2})", upper)
    if vent_match and vent_match.group(1):
        vent_dn = f"DN{vent_match.group(1)}"
    else:
        vent_dn = "DN15"

    return {
        "gas_service_type": service,
        "regulator_type": reg_type,
        "pipe_connection_dn": pipe_dn,
        "inlet_pressure_kpa": inlet_kpa,
        "outlet_pressure_kpa": outlet_kpa,
        "opso_trip_kpa": opso_trip,
        "relief_vent_dn": vent_dn,
    }


class SourceGasRegulatorOpsoShadowAuthority:
    """Authority for extracting gas service regulators and OPSO valves in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[GasRegulatorOpsoCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[GasRegulatorOpsoCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_gas_regulator_opso_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["gas_service_type"], parsed["pipe_connection_dn"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = GasRegulatorOpsoCallout(
                raw_text=text,
                gas_service_type=parsed["gas_service_type"],
                regulator_type=parsed["regulator_type"],
                pipe_connection_dn=parsed["pipe_connection_dn"],
                inlet_pressure_kpa=parsed["inlet_pressure_kpa"],
                outlet_pressure_kpa=parsed["outlet_pressure_kpa"],
                opso_trip_kpa=parsed["opso_trip_kpa"],
                relief_vent_dn=parsed["relief_vent_dn"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
