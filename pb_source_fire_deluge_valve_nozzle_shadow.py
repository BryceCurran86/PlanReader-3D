"""
Source Fire Protection Deluge Valve & Open Nozzle Water Spray Shadow Authority.

Extracts and validates high-hazard fire protection deluge valve sets, open water spray projectors,
actuation release modes, K-factors, and manual pull stations strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FireDelugeValveNozzleCallout:
    raw_text: str
    component_category: str
    valve_diameter_mm: float
    actuation_mode: str
    nozzle_k_factor: float
    spray_angle_deg: float
    manual_release_included: bool
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


def parse_fire_deluge_valve_nozzle_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "DELUGE VALVE",
        "DELUGE SYSTEM",
        "WATER SPRAY NOZZLE",
        "OPEN NOZZLE SPRAY",
        "TRANSFORMER DELUGE",
        "HIGH VELOCITY SPRAY",
        "MEDIUM VELOCITY NOZZLE",
        "DELUGE SKID",
        "DRAIN DOWN DELUGE",
        "DELUGE WATER SPRAY",
        "OPEN SPRAY PROJECTOR",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Component category
    has_valve = any(k in upper for k in ["DELUGE VALVE", "VALVE SET", "DELUGE SKID"])
    has_nozzle = any(k in upper for k in ["NOZZLE", "PROJECTOR", "SPRAY HEAD"])

    if has_valve and has_nozzle:
        cat = "COMBINED_DELUGE_ARRAY"
    elif has_nozzle and not has_valve:
        cat = "OPEN_WATER_SPRAY_NOZZLE"
    else:
        cat = "DELUGE_VALVE_SET"

    # Valve nominal diameter (DN50 to DN200)
    dia_match = re.search(r"\b(?:DN\s*|Ø\s*)(\d{2,3})\b", upper)
    if not dia_match:
        dia_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:VALVE|MAIN|PIPE)?", upper)
    valve_dia = float(dia_match.group(1)) if dia_match else 100.0

    # Actuation mode: Solenoid vs Pneumatic vs Hydraulic
    if "HYDRAULIC" in upper or "WET PILOT" in upper:
        actuation = "HYDRAULIC_WET_PILOT"
    elif "PNEUMATIC" in upper or "DRY PILOT" in upper or "PILOT LINE" in upper:
        actuation = "PNEUMATIC_DRY_PILOT"
    else:
        actuation = "SOLENOID_ELECTRIC_RELEASE"

    # Nozzle K-factor (e.g. "K23", "K44", "K80", "K17", "K115")
    k_match = re.search(r"\bK\s*(\d{2,3}(?:\.\d)?)\b", upper)
    k_factor = float(k_match.group(1)) if k_match else 44.0

    # Spray angle (e.g. "90 DEG", "120 DEG", "60 DEG", "120°", "90°")
    deg_match = re.search(r"\b(\d{2,3})\s*(?:DEG|°|DEGREE)", upper)
    spray_deg = float(deg_match.group(1)) if deg_match else 120.0

    # Manual emergency release
    if "WITHOUT MANUAL" in upper or "NO MANUAL" in upper:
        has_manual = False
    elif any(k in upper for k in ["MANUAL PULL", "EMERGENCY MANUAL", "MANUAL TRIP", "LOCAL RELEASE"]):
        has_manual = True
    else:
        has_manual = True  # Standard requirement per AS 2118.2

    return {
        "raw_text": clean,
        "component_category": cat,
        "valve_diameter_mm": valve_dia,
        "actuation_mode": actuation,
        "nozzle_k_factor": k_factor,
        "spray_angle_deg": spray_deg,
        "manual_release_included": has_manual,
    }


def evaluate_fire_deluge_valve_nozzle_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[FireDelugeValveNozzleCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[FireDelugeValveNozzleCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_fire_deluge_valve_nozzle_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            FireDelugeValveNozzleCallout(
                raw_text=parsed["raw_text"],
                component_category=parsed["component_category"],
                valve_diameter_mm=parsed["valve_diameter_mm"],
                actuation_mode=parsed["actuation_mode"],
                nozzle_k_factor=parsed["nozzle_k_factor"],
                spray_angle_deg=parsed["spray_angle_deg"],
                manual_release_included=parsed["manual_release_included"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "deluge_standard": "AS2118.2-NFPA15-DELUGE",
                },
            )
        )

    return results
