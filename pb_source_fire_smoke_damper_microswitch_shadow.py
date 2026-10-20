"""
Source Fire Smoke Damper Fusible Link & Microswitch Actuator Shadow Authority.

Extracts and validates fire and smoke dampers (FSD/FD), motorized spring-return actuators (24V/240V),
fusible link release temperatures (°C), dual auxiliary microswitches, duct dimensions, and fire ratings
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FireSmokeDamperMicroswitchCallout:
    raw_text: str
    damper_type: str
    actuator_control: str
    fusible_link_rating_deg_c: float
    auxiliary_microswitch: str
    duct_dimensions_mm: Tuple[float, float]
    frl_minutes: int
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


def parse_fire_smoke_damper_microswitch_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "FIRE DAMPER",
        "SMOKE DAMPER",
        "FIRE/SMOKE DAMPER",
        "FIRE SMOKE DAMPER",
        "FSD",
        "F.S.D.",
        "MVD",
        "FUSIBLE LINK DAMPER",
        "COMBINATION DAMPER",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("DAMPER" in upper) and ("FIRE" in upper or "SMOKE" in upper or "FUSIBLE" in upper)
    )
    if not has_trigger:
        return None

    # Damper mechanism type - evaluate combination / multi-role before single-role
    if any(k in upper for k in ["COMBINATION", "FIRE/SMOKE", "FIRE SMOKE", "FSD", "F.S.D."]):
        damper_type = "COMBINATION_FIRE_SMOKE_DAMPER"
    elif "INTUMESCENT" in upper:
        damper_type = "INTUMESCENT_FIRE_DAMPER"
    elif "CURTAIN" in upper:
        damper_type = "CURTAIN_FIRE_DAMPER"
    elif "SMOKE DAMPER" in upper or "SMOKE CONTROL" in upper:
        damper_type = "SMOKE_CONTROL_DAMPER"
    else:
        damper_type = "COMBINATION_FIRE_SMOKE_DAMPER"

    # Actuator control
    if any(k in upper for k in ["240V", "240 V", "230V"]):
        actuator = "MOTORISED_SPRING_RETURN_240V"
    elif any(k in upper for k in ["24V", "24 V", "24VAC", "24VDC"]):
        actuator = "MOTORISED_SPRING_RETURN_24V"
    elif any(k in upper for k in ["MOTORISED", "MOTORIZED", "SPRING RETURN", "BELIMO"]):
        actuator = "MOTORISED_SPRING_RETURN_24V"
    elif any(k in upper for k in ["FUSIBLE LINK ONLY", "GRAVITY", "THERMAL RELEASE ONLY"]):
        actuator = "THERMAL_FUSIBLE_LINK_GRAVITY"
    else:
        actuator = "MOTORISED_SPRING_RETURN_24V"

    # Fusible link rating (°C)
    link_match = re.search(r"(\d{2,3}(?:\.\d+)?)\s*(?:°C|DEG\s*C|DEGREES\s*C|°\s*C)?\s*(?:FUSIBLE\s*LINK|THERMAL\s*LINK|THERMAL\s*RELEASE)", upper)
    if not link_match:
        link_match = re.search(r"(?:FUSIBLE\s*LINK|THERMAL\s*RELEASE)\s*(?:@|AT|OF)?\s*(\d{2,3}(?:\.\d+)?)\s*(?:°C|DEG\s*C)?", upper)

    if link_match:
        temp_val = float(link_match.group(1))
        if 50.0 <= temp_val <= 180.0:
            link_rating = temp_val
        else:
            link_rating = 71.0
    else:
        link_rating = 71.0  # standard BCA/NCC AS1668.1 compliance rating

    # Auxiliary microswitch status
    if any(k in upper for k in ["WITHOUT MICROSWITCH", "NO MICROSWITCH", "NO END SWITCH"]):
        microswitch = "NONE"
    elif any(k in upper for k in ["CLOSED ONLY", "SINGLE MICROSWITCH", "1X MICROSWITCH"]):
        microswitch = "CLOSED_ONLY_MICROSWITCH"
    elif any(k in upper for k in ["AUXILIARY MICROSWITCH", "END SWITCH", "OPEN/CLOSED", "OPEN & CLOSED", "DUAL SWITCH", "POSITION SWITCH", "MICROSWITCH"]):
        microswitch = "OPEN_AND_CLOSED_MICROSWITCHES"
    else:
        microswitch = "OPEN_AND_CLOSED_MICROSWITCHES"

    # Duct dimensions (width, height)
    dim_match = re.search(r"(\d{3,4})\s*(?:X|\*)\s*(\d{2,4})\s*(?:MM)?", upper)
    if dim_match:
        dims = (float(dim_match.group(1)), float(dim_match.group(2)))
    else:
        dia_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*DIA", upper)
        if dia_match:
            dims = (float(dia_match.group(1)), float(dia_match.group(1)))
        else:
            dims = (600.0, 400.0)

    # Fire resistance level FRL (minutes)
    frl_match = re.search(r"-\s*/\s*(\d+)\s*/\s*-?", upper)
    if frl_match:
        frl_min = int(frl_match.group(1))
    else:
        frl_hr = re.search(r"(\d+)\s*(?:HR|HOUR)\s*(?:FIRE|FRL)", upper)
        if frl_hr:
            frl_min = int(frl_hr.group(1)) * 60
        else:
            frl_min_match = re.search(r"(\d{2,3})\s*(?:MIN|MINUTES)\s*(?:FIRE|FRL)", upper)
            if frl_min_match:
                frl_min = int(frl_min_match.group(1))
            else:
                frl_min = 120  # standard 2-hour rating

    return {
        "raw_text": clean,
        "damper_type": damper_type,
        "actuator_control": actuator,
        "fusible_link_rating_deg_c": link_rating,
        "auxiliary_microswitch": microswitch,
        "duct_dimensions_mm": dims,
        "frl_minutes": frl_min,
    }


class SourceFireSmokeDamperMicroswitchShadowAuthority:
    """Authority for fire/smoke dampers in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[FireSmokeDamperMicroswitchCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[FireSmokeDamperMicroswitchCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[FireSmokeDamperMicroswitchCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_fire_smoke_damper_microswitch_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = FireSmokeDamperMicroswitchCallout(
                raw_text=parsed["raw_text"],
                damper_type=parsed["damper_type"],
                actuator_control=parsed["actuator_control"],
                fusible_link_rating_deg_c=parsed["fusible_link_rating_deg_c"],
                auxiliary_microswitch=parsed["auxiliary_microswitch"],
                duct_dimensions_mm=parsed["duct_dimensions_mm"],
                frl_minutes=parsed["frl_minutes"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
