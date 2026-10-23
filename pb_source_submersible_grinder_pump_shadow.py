"""
Source Stormwater Retention Sump Submersible Grinder Pump Station Shadow Authority.

Extracts and validates submersible sump pump stations, duplex/simplex configurations,
grinder cutters, hydraulic flow (L/s) and head (m), motor ratings (kW), and auto-coupling duckfoot
guide rail assemblies strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SubmersibleGrinderPumpCallout:
    raw_text: str
    pump_configuration: str
    impeller_type: str
    flow_lps: float
    head_m: float
    motor_power_kw: float
    guide_rail_coupling: str
    sump_dimensions_mm: Tuple[float, float]
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


def parse_submersible_grinder_pump_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SUBMERSIBLE PUMP",
        "GRINDER PUMP",
        "SUMP PUMP",
        "RETENTION PUMP",
        "STORMWATER PUMP",
        "PUMP STATION",
        "SEWAGE EJECTOR",
        "EFFLUENT PUMP",
        "DRAINAGE PUMP",
    ]
    has_trigger = any(trig in upper for trig in triggers) or ("SUBMERSIBLE" in upper and "PUMP" in upper)
    if not has_trigger:
        return None

    # Pump configuration
    if "TRIPLEX" in upper or "3X PUMP" in upper or "3 X PUMP" in upper:
        config = "TRIPLEX_SYSTEM"
    elif any(k in upper for k in ["DUPLEX", "DUTY/STANDBY", "DUTY / STANDBY", "LEAD/LAG", "LEAD / LAG", "2X PUMP", "2 X PUMP", "TWIN PUMP"]):
        config = "DUPLEX_DUTY_STANDBY"
    elif any(k in upper for k in ["SIMPLEX", "1X PUMP", "1 X PUMP", "SINGLE PUMP"]):
        config = "SIMPLEX_PUMP"
    else:
        config = "DUPLEX_DUTY_STANDBY"  # standard redundancy for retention pits

    # Impeller / cutter type
    if any(k in upper for k in ["SHREDDER", "CHOPPER"]):
        impeller = "SHREDDER_PUMP"
    elif any(k in upper for k in ["GRINDER", "RADIAL CUTTER", "CUTTER"]):
        impeller = "RADIAL_CUTTER_GRINDER"
    elif any(k in upper for k in ["VORTEX", "RECEDING IMPELLER"]):
        impeller = "VORTEX_IMPELLER"
    elif any(k in upper for k in ["NON-CLOG", "NON CLOG", "SEMI-OPEN", "SEMI OPEN", "CHANNEL IMPELLER"]):
        impeller = "SEMI_OPEN_NON_CLOG"
    else:
        if "GRINDER" in upper:
            impeller = "RADIAL_CUTTER_GRINDER"
        else:
            impeller = "VORTEX_IMPELLER"

    # Flow rate L/s
    flow_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L\/S|LITRES\s*(?:PER|\/)\s*SEC(?:OND)?)", upper)
    if flow_match:
        flow_lps = float(flow_match.group(1))
    else:
        flow_lps = 10.0  # standard engineering default for retention sumps

    # Total dynamic head (m)
    head_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:M|METRE|METER)?\s*(?:TDH|HEAD|TOTAL\s*DYNAMIC\s*HEAD)", upper)
    if not head_match:
        head_match = re.search(r"(?:TDH|HEAD)\s*(?:OF|:)?\s*(\d+(?:\.\d+)?)\s*(?:M)?", upper)
    if not head_match:
        head_match = re.search(r"(?:@|\bAT\b)\s*(\d+(?:\.\d+)?)\s*(?:M\b|METRE|METER)", upper)

    if head_match:
        head_m = float(head_match.group(1))
    else:
        head_m = 12.0  # standard default

    # Motor power (kW)
    kw_match = re.search(r"(\d+(?:\.\d+)?)\s*KW", upper)
    if kw_match:
        motor_kw = float(kw_match.group(1))
    else:
        motor_kw = 2.2  # standard default

    # Guide rail auto-coupling assembly
    if any(k in upper for k in ["FREE STANDING", "PORTABLE", "FREESTANDING"]):
        coupling = "FREE_STANDING"
    elif any(k in upper for k in ["HOSE DISCHARGE", "FLEXIBLE HOSE"]):
        coupling = "HOSE_DISCHARGE"
    elif any(k in upper for k in ["GUIDE RAIL", "AUTO-COUPLING", "AUTO COUPLING", "DUCKFOOT", "PEDESTAL", "DISCHARGE BEND"]):
        coupling = "DUAL_GUIDE_RAIL_COUPLING"
    else:
        coupling = "DUAL_GUIDE_RAIL_COUPLING"

    # Sump pit dimensions (diameter/width, depth)
    dim_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:DIA|DIAMETER|X|\*)\s*(?:X|\*)?\s*(\d{3,4})\s*(?:MM)?\s*(?:DEEP|DEPTH)?", upper)
    if dim_match:
        sump_dims = (float(dim_match.group(1)), float(dim_match.group(2)))
    else:
        sump_dims = (1200.0, 2000.0)

    return {
        "raw_text": clean,
        "pump_configuration": config,
        "impeller_type": impeller,
        "flow_lps": flow_lps,
        "head_m": head_m,
        "motor_power_kw": motor_kw,
        "guide_rail_coupling": coupling,
        "sump_dimensions_mm": sump_dims,
    }


class SourceSubmersibleGrinderPumpShadowAuthority:
    """Authority for submersible grinder pump stations in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[SubmersibleGrinderPumpCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[SubmersibleGrinderPumpCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[SubmersibleGrinderPumpCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_submersible_grinder_pump_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = SubmersibleGrinderPumpCallout(
                raw_text=parsed["raw_text"],
                pump_configuration=parsed["pump_configuration"],
                impeller_type=parsed["impeller_type"],
                flow_lps=parsed["flow_lps"],
                head_m=parsed["head_m"],
                motor_power_kw=parsed["motor_power_kw"],
                guide_rail_coupling=parsed["guide_rail_coupling"],
                sump_dimensions_mm=parsed["sump_dimensions_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
