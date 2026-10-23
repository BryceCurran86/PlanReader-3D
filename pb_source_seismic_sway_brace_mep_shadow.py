"""
Source Seismic Restraint Cable Sway Brace MEP Suspended Services Shadow Authority.

Extracts and validates seismic sway braces for suspended MEP services, transverse/longitudinal cable orientations,
aircraft cable diameters, installation angles (°), design acceleration coefficients (g), and structural anchors
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SeismicSwayBraceMepCallout:
    raw_text: str
    brace_type: str
    cable_diameter_mm: float
    brace_angle_degrees: float
    service_type: str
    seismic_design_acceleration_g: float
    anchor_type: str
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


def parse_seismic_sway_brace_mep_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SEISMIC BRACE",
        "SWAY BRACE",
        "SEISMIC RESTRAINT",
        "CABLE BRACE",
        "TRANSVERSE BRACE",
        "LONGITUDINAL BRACE",
        "4-WAY BRACE",
        "MEP SEISMIC",
        "SEISMIC CABLE",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("SEISMIC" in upper or "SWAY" in upper) and ("BRACE" in upper or "CABLE" in upper or "RESTRAINT" in upper)
    )
    if not has_trigger:
        return None

    # Brace mechanism and orientation
    if any(k in upper for k in ["4-WAY", "4 WAY", "RIGID STRUT"]):
        brace = "4_WAY_RIGID_STRUT_BRACE"
    elif "LONGITUDINAL" in upper:
        brace = "LONGITUDINAL_CABLE_SWAY_BRACE"
    elif "TRANSVERSE" in upper:
        brace = "TRANSVERSE_CABLE_SWAY_BRACE"
    elif any(k in upper for k in ["TENSION ONLY", "CABLE BRACE", "AIRCRAFT CABLE"]):
        brace = "TENSION_ONLY_AIRCRAFT_CABLE"
    else:
        brace = "TRANSVERSE_CABLE_SWAY_BRACE"

    # Cable diameter in mm
    if '1/8"' in upper or "3.2MM" in upper:
        cable_dia = 3.2
    elif '1/4"' in upper or "6.4MM" in upper:
        cable_dia = 6.4
    elif '3/16"' in upper or "4.8MM" in upper:
        cable_dia = 4.8
    else:
        dia_match = re.search(r"(\d+(?:\.\d+)?)\s*MM\s*(?:DIA|CABLE|WIRE|AIRCRAFT)?", upper)
        if dia_match and 2.0 <= float(dia_match.group(1)) <= 12.0:
            cable_dia = float(dia_match.group(1))
        else:
            cable_dia = 4.8  # standard 3/16" 7x19 aircraft cable

    # Brace installation angle from horizontal
    angle_match = re.search(r"(\d{2}(?:\.\d+)?)\s*(?:°|DEG|DEGREES?)", upper)
    if angle_match and 25.0 <= float(angle_match.group(1)) <= 90.0:
        angle_deg = float(angle_match.group(1))
    else:
        angle_deg = 45.0  # standard engineering design angle

    # Suspended MEP service type
    if any(k in upper for k in ["SPRINKLER", "FIRE PIPE", "FIRE MAIN"]):
        service = "FIRE_SPRINKLER_MAIN"
    elif any(k in upper for k in ["DUCT", "HVAC", "EXHAUST DUCT", "SUPPLY AIR"]):
        service = "RECTANGULAR_HVAC_DUCT"
    elif any(k in upper for k in ["CABLE TRAY", "LADDER", "ELECTRICAL"]):
        service = "ELECTRICAL_CABLE_TRAY"
    elif any(k in upper for k in ["PIPE", "CHW", "CONDENSER WATER", "HYDRONIC"]):
        service = "SUSPENDED_CHW_PIPE"
    else:
        service = "SUSPENDED_CHW_PIPE"

    # Seismic horizontal design acceleration (g)
    g_match = re.search(r"(\d+(?:\.\d+)?)\s*G\b", upper)
    if g_match and 0.05 <= float(g_match.group(1)) <= 1.50:
        accel_g = float(g_match.group(1))
    else:
        accel_g = 0.25  # standard design baseline

    # Structural anchor substrate attachment
    if any(k in upper for k in ["BEAM CLAMP", "STEEL CLAMP", "FLANGE CLAMP"]):
        anchor = "STEEL_BEAM_CLAMP"
    elif any(k in upper for k in ["THROUGH BOLT", "DECK BOLT"]):
        anchor = "THROUGH_BOLT_DECK"
    elif any(k in upper for k in ["DROP-IN", "DROP IN"]):
        anchor = "DROP_IN_ANCHOR"
    elif any(k in upper for k in ["EXPANSION ANCHOR", "WEDGE ANCHOR", "CONCRETE ANCHOR", "M10 ANCHOR", "M12 ANCHOR"]):
        anchor = "CONCRETE_EXPANSION_ANCHOR"
    else:
        anchor = "CONCRETE_EXPANSION_ANCHOR"

    return {
        "raw_text": clean,
        "brace_type": brace,
        "cable_diameter_mm": cable_dia,
        "brace_angle_degrees": angle_deg,
        "service_type": service,
        "seismic_design_acceleration_g": accel_g,
        "anchor_type": anchor,
    }


class SourceSeismicSwayBraceMepShadowAuthority:
    """Authority for suspended MEP seismic sway braces in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[SeismicSwayBraceMepCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[SeismicSwayBraceMepCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[SeismicSwayBraceMepCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_seismic_sway_brace_mep_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = SeismicSwayBraceMepCallout(
                raw_text=parsed["raw_text"],
                brace_type=parsed["brace_type"],
                cable_diameter_mm=parsed["cable_diameter_mm"],
                brace_angle_degrees=parsed["brace_angle_degrees"],
                service_type=parsed["service_type"],
                seismic_design_acceleration_g=parsed["seismic_design_acceleration_g"],
                anchor_type=parsed["anchor_type"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
