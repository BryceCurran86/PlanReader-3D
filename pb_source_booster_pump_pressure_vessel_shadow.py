"""
Source Cold Water Booster Pump Variable Speed Hydro-Pneumatic Pressure Vessel Shadow Authority.

Extracts and validates domestic and commercial cold water booster pump skids, VSD configurations,
hydro-pneumatic pressure vessels, manifold headers, and vibration isolation strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class BoosterPumpPressureVesselCallout:
    raw_text: str
    pump_configuration: str
    pressure_vessel_litres: float
    pressure_rating: str
    control_mode: str
    manifold_diameter_mm: float
    vibration_isolation: bool
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


def parse_booster_pump_pressure_vessel_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "BOOSTER PUMP",
        "PRESSURE VESSEL",
        "HYDRO-PNEUMATIC",
        "WATER PRESSURE SET",
        "PUMP SET",
        "VSD PUMP",
        "COLD WATER BOOSTER",
        "POTABLE WATER BOOSTER",
        "EXPANSION VESSEL",
        "PRESSURE TANK",
        "PRESSURE BOOSTER",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Pump arrangement
    if any(k in upper for k in ["QUADPLEX", "4 PUMP", "FOUR PUMP"]):
        config = "QUADPLEX_PUMP_SET"
    elif any(k in upper for k in ["TRIPLEX", "3 PUMP", "THREE PUMP"]):
        config = "TRIPLEX_PUMP_SET"
    elif any(k in upper for k in ["SIMPLEX", "SINGLE PUMP", "1 PUMP"]):
        config = "SIMPLEX_PUMP_SET"
    else:
        config = "DUPLEX_PUMP_SET"

    # Pressure vessel capacity in litres (e.g. "100L", "200L", "300L", "500 LITRES", "80L", "50L")
    vol_match = re.search(r"\b(\d{2,3})\s*(?:L|LTR|LITRES|LITERS)\b", upper)
    vessel_vol = float(vol_match.group(1)) if vol_match else 100.0

    # Pressure rating
    if "PN25" in upper or "25 BAR" in upper:
        pressure_class = "PN25"
    elif "PN10" in upper or "10 BAR" in upper:
        pressure_class = "PN10"
    else:
        pressure_class = "PN16"

    # Control mode
    if "PRESSURE SWITCH" in upper or "FIXED SPEED" in upper:
        control = "FIXED_SPEED_PRESSURE_SWITCH"
    else:
        control = "VARIABLE_SPEED_DRIVE_VSD"

    # Manifold header diameter
    dia_match = re.search(r"\b(?:DN\s*|Ø\s*)(\d{2,3})\b", upper)
    if not dia_match:
        dia_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:MANIFOLD|HEADER|PIPE)?", upper)
    manifold_dia = float(dia_match.group(1)) if dia_match else 65.0

    # Vibration isolation
    if "WITHOUT ISOLATION" in upper or "NO ISOLATION" in upper:
        vibe = False
    elif any(k in upper for k in ["INERTIA", "SPRING", "ACOUSTIC MOUNT", "ANTI-VIBRATION", "ISOLAT"]):
        vibe = True
    else:
        vibe = True

    return {
        "raw_text": clean,
        "pump_configuration": config,
        "pressure_vessel_litres": vessel_vol,
        "pressure_rating": pressure_class,
        "control_mode": control,
        "manifold_diameter_mm": manifold_dia,
        "vibration_isolation": vibe,
    }


def evaluate_booster_pump_pressure_vessel_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[BoosterPumpPressureVesselCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[BoosterPumpPressureVesselCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_booster_pump_pressure_vessel_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            BoosterPumpPressureVesselCallout(
                raw_text=parsed["raw_text"],
                pump_configuration=parsed["pump_configuration"],
                pressure_vessel_litres=parsed["pressure_vessel_litres"],
                pressure_rating=parsed["pressure_rating"],
                control_mode=parsed["control_mode"],
                manifold_diameter_mm=parsed["manifold_diameter_mm"],
                vibration_isolation=parsed["vibration_isolation"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "pump_standard": "ASNZS3500.1-WATER-SERVICES",
                },
            )
        )

    return results
