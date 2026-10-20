"""
Source Hydronic Heating Chilled Water Air Dirt Separator Magnetic Filter Shadow Authority.

Extracts and validates HVAC hydronic air and dirt separators, magnetic sludge filters,
service loop types (CHW/HHW/CW), connection sizes, and insulation jackets strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class HydronicAirDirtSeparatorCallout:
    raw_text: str
    service_system: str
    connection_diameter_mm: float
    separation_technology: str
    magnetic_core_included: bool
    pressure_rating: str
    insulation_jacket_type: str
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


def parse_hydronic_air_dirt_separator_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "AIR DIRT SEPARATOR",
        "AIR & DIRT SEPARATOR",
        "AIR AND DIRT SEPARATOR",
        "MAGNETIC DIRT FILTER",
        "HYDRONIC SEPARATOR",
        "MICROBUBBLE DEAERATOR",
        "SPIROVENT",
        "DIRT SEPARATOR",
        "MAGNETIC SLUDGE FILTER",
        "CHW AIR SEPARATOR",
        "HHW AIR SEPARATOR",
        "HYDRONIC AIR DIRT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Service system
    if "HHW" in upper or "HEATING" in upper or "HOT WATER" in upper or "BOILER" in upper:
        service = "HEATING_HOT_WATER_HHW"
    elif "CONDENSER" in upper or " CW " in upper or upper.endswith(" CW"):
        service = "CONDENSER_WATER_CW"
    else:
        service = "CHILLED_WATER_CHW"

    # Connection size (DN50 to DN300)
    dia_match = re.search(r"\b(?:DN\s*|Ø\s*)(\d{2,3})\b", upper)
    if not dia_match:
        dia_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:FLANGE|PIPE|CONNECTION)?", upper)
    conn_dia = float(dia_match.group(1)) if dia_match else 100.0

    # Separation technology
    if "DIRT ONLY" in upper or "SLUDGE FILTER" in upper:
        tech = "MAGNETIC_DIRT_ONLY"
    elif "AIR ONLY" in upper or "DEAERATOR ONLY" in upper:
        tech = "AIR_DEAERATOR_ONLY"
    else:
        tech = "COMBINED_MICROBUBBLE_AND_DIRT"

    # Magnetic core included
    if "WITHOUT MAGNET" in upper or "NO MAGNET" in upper:
        has_magnet = False
    elif any(k in upper for k in ["MAGNET", "NEODYMIUM", "FERROUS"]):
        has_magnet = True
    else:
        has_magnet = True  # Standard modern practice

    # Pressure rating
    if "PN25" in upper or "25 BAR" in upper:
        pressure = "PN25"
    elif "PN10" in upper or "10 BAR" in upper:
        pressure = "PN10"
    else:
        pressure = "PN16"

    # Insulation jacket
    if "BARE" in upper or "UNINSULATED" in upper or "NO INSULATION" in upper:
        jacket = "BARE_VESSEL"
    elif "PRE-INSULATED" in upper:
        jacket = "PRE_INSULATED_FACTORY"
    else:
        jacket = "REMOVABLE_INSULATION_JACKET"

    return {
        "raw_text": clean,
        "service_system": service,
        "connection_diameter_mm": conn_dia,
        "separation_technology": tech,
        "magnetic_core_included": has_magnet,
        "pressure_rating": pressure,
        "insulation_jacket_type": jacket,
    }


def evaluate_hydronic_air_dirt_separator_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[HydronicAirDirtSeparatorCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[HydronicAirDirtSeparatorCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_hydronic_air_dirt_separator_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            HydronicAirDirtSeparatorCallout(
                raw_text=parsed["raw_text"],
                service_system=parsed["service_system"],
                connection_diameter_mm=parsed["connection_diameter_mm"],
                separation_technology=parsed["separation_technology"],
                magnetic_core_included=parsed["magnetic_core_included"],
                pressure_rating=parsed["pressure_rating"],
                insulation_jacket_type=parsed["insulation_jacket_type"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "hydronic_standard": "CIBSE-CODE-W-BSRIA-BG29",
                },
            )
        )

    return results
