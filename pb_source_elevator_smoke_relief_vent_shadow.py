"""
Source Elevator Shaft Smoke Relief Vent & Motorized Louver Shadow Authority.

Extracts and validates elevator shaft smoke relief vents, motorized louvers, dimensions (W x H mm),
aerodynamic free area (m2), 24V fail-safe open actuators, and weather blade profiles strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ElevatorSmokeReliefVentCallout:
    raw_text: str
    vent_type: str
    width_mm: float
    height_mm: float
    aerodynamic_free_area_m2: float
    actuator_operation: str
    blade_profile: str
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


def parse_elevator_smoke_relief_vent_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SMOKE RELIEF",
        "HOISTWAY VENT",
        "SHAFT SMOKE VENT",
        "LIFT SHAFT VENT",
        "ELEVATOR SMOKE",
        "PRESSURE RELIEF LOUVER",
        "PRESSURE RELIEF VENT",
        "RELIEF LOUVER",
        "SMOKE VENT LOUVER",
        "HOISTWAY RELIEF",
        "VENT COWL",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        any(h in upper for h in ["HOISTWAY", "LIFT SHAFT", "ELEVATOR SHAFT", "SHAFT"])
        and any(v in upper for v in ["VENT", "LOUVER", "RELIEF", "COWL"])
    )
    if not has_trigger:
        return None

    # Vent type
    if "GRAVITY" in upper or "COUNTERBALANCE" in upper:
        vent_type = "GRAVITY_COUNTERBALANCED_PRESSURE_RELIEF_VENT"
    elif "COWL" in upper or "UPSTAND" in upper:
        vent_type = "ROOF_UPSTAND_VENT_COWL"
    elif "MOTORIZED" in upper or "ACTUATOR" in upper or "LOUVER" in upper or "SMOKE" in upper:
        vent_type = "MOTORIZED_HOISTWAY_SMOKE_RELIEF_LOUVER"
    else:
        vent_type = "MOTORIZED_HOISTWAY_SMOKE_RELIEF_LOUVER"

    # Dimensions: W x H mm
    w_mm = 800.0
    h_mm = 600.0
    dim_match = re.search(r"(\d{3,4})\s*[X*x]\s*(\d{3,4})", upper)
    if dim_match:
        w_mm = float(dim_match.group(1))
        h_mm = float(dim_match.group(2))

    # Aerodynamic free area m2
    area_m2 = 0.0
    area_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:M2|SQM|M²|SQ\s*M)", upper)
    if area_match:
        area_m2 = float(area_match.group(1))
    else:
        # standard 50% free area approximation
        area_m2 = round((w_mm * h_mm * 1e-6) * 0.50, 3)

    # Actuator operation
    if "PNEUMATIC" in upper:
        actuator = "PNEUMATIC_FAIL_OPEN"
    elif "FUSIBLE" in upper or "MANUAL" in upper:
        actuator = "MANUAL_FUSIBLE_LINK"
    elif "24V" in upper or "SPRING" in upper or "FAIL OPEN" in upper or "FAIL-SAFE" in upper:
        actuator = "FAIL_SAFE_SPRING_OPEN_24V_DC"
    else:
        actuator = "FAIL_SAFE_SPRING_OPEN_24V_DC"

    # Blade profile
    if "DRAINABLE" in upper or "WEATHER" in upper:
        blade = "DRAINABLE_WEATHER_BLADE"
    elif "ACOUSTIC" in upper or "CHEVRON" in upper:
        blade = "CHEVRON_ACOUSTIC_BLADE"
    else:
        blade = "DRAINABLE_WEATHER_BLADE"

    return {
        "vent_type": vent_type,
        "width_mm": w_mm,
        "height_mm": h_mm,
        "aerodynamic_free_area_m2": area_m2,
        "actuator_operation": actuator,
        "blade_profile": blade,
    }


class SourceElevatorSmokeReliefVentShadowAuthority:
    """Authority for extracting elevator shaft smoke relief vents in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[ElevatorSmokeReliefVentCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[ElevatorSmokeReliefVentCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_elevator_smoke_relief_vent_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["width_mm"], parsed["height_mm"], parsed["vent_type"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = ElevatorSmokeReliefVentCallout(
                raw_text=text,
                vent_type=parsed["vent_type"],
                width_mm=parsed["width_mm"],
                height_mm=parsed["height_mm"],
                aerodynamic_free_area_m2=parsed["aerodynamic_free_area_m2"],
                actuator_operation=parsed["actuator_operation"],
                blade_profile=parsed["blade_profile"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
