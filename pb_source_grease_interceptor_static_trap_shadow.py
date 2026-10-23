"""
Source Hydraulic Trade Waste Grease Interceptor Static Trap Shadow Authority.

Extracts and validates trade waste grease arrestors, passive interceptor capacities,
vessel materials, baffle configurations, gastight covers, and sampling pits strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GreaseInterceptorStaticTrapCallout:
    raw_text: str
    capacity_litres: float
    vessel_material: str
    baffle_configuration: str
    cover_class: str
    vent_specification: str
    sampling_pit_included: bool
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


def parse_grease_interceptor_static_trap_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "GREASE TRAP",
        "GREASE INTERCEPTOR",
        "TRADE WASTE INTERCEPTOR",
        "GREASE ARRESTOR",
        "GREASE ARRESTER",
        "STATIC GREASE TRAP",
        "PASSIVE GREASE INTERCEPTOR",
        "G.I.T.",
        "GIT IN PIT",
        "FOOD WASTE GREASE TRAP",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Capacity in litres (e.g. "1000L", "1500L", "2000L", "3000L", "5000 LITRES", "2500 LTR")
    cap_match = re.search(r"\b(\d{3,4})\s*(?:L|LTR|LITRES|LITERS)\b", upper)
    capacity = float(cap_match.group(1)) if cap_match else 1500.0

    # Vessel construction material
    if "POLY" in upper or "FRP" in upper or "FIBREGLASS" in upper:
        vessel_mat = "ROTOMOULDED_POLYETHYLENE"
    elif "CONCRETE" in upper or "PRECAST" in upper or "BLOCKWORK" in upper:
        vessel_mat = "PRECAST_CONCRETE"
    elif "STAINLESS" in upper or "316" in upper or "SS" in upper:
        vessel_mat = "FABRICATED_STAINLESS_STEEL"
    else:
        vessel_mat = "ROTOMOULDED_POLYETHYLENE"

    # Baffle configuration
    if "SUBMERGED" in upper:
        baffle = "SUBMERGED_BAFFLE"
    elif "T-PIECE" in upper or "T-PIPE" in upper or "DIP PIPE" in upper:
        baffle = "T_PIECE_INLET_OUTLET"
    else:
        baffle = "INTERNAL_BAFFLE_WALL"

    # Cover load class / gastight seal
    if "CLASS D" in upper or "TRAFFICABLE" in upper or "CARPARK" in upper:
        cover_class = "CLASS_D_GASTIGHT"
    elif "CLASS B" in upper or "FOOTWAY" in upper or "PEDESTRIAN" in upper:
        cover_class = "CLASS_B_GASTIGHT"
    else:
        cover_class = "BOLTED_AIRTIGHT"

    # Vent connection
    if "DN50" in upper or "50MM VENT" in upper:
        vent_spec = "DN50_VENT_TO_ATMOSPHERE"
    elif "DN80" in upper or "80MM VENT" in upper:
        vent_spec = "DN80_VENT_TO_ATMOSPHERE"
    else:
        vent_spec = "DN100_VENT_TO_ATMOSPHERE"

    # Sampling pit included
    has_sampling = any(k in upper for k in ["SAMPLE", "SAMPLING", "TEST PIT", "INSPECTION PIT", "INSPECTION OPENING"])
    if "NO SAMPLING" in upper or "WITHOUT SAMPLING" in upper:
        has_sampling = False
    elif not has_sampling:
        has_sampling = True  # Standard requirement per trade waste codes

    return {
        "raw_text": clean,
        "capacity_litres": capacity,
        "vessel_material": vessel_mat,
        "baffle_configuration": baffle,
        "cover_class": cover_class,
        "vent_specification": vent_spec,
        "sampling_pit_included": has_sampling,
    }


def evaluate_grease_interceptor_static_trap_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[GreaseInterceptorStaticTrapCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[GreaseInterceptorStaticTrapCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_grease_interceptor_static_trap_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            GreaseInterceptorStaticTrapCallout(
                raw_text=parsed["raw_text"],
                capacity_litres=parsed["capacity_litres"],
                vessel_material=parsed["vessel_material"],
                baffle_configuration=parsed["baffle_configuration"],
                cover_class=parsed["cover_class"],
                vent_specification=parsed["vent_specification"],
                sampling_pit_included=parsed["sampling_pit_included"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "trade_waste_standard": "ASNZS3500.2-GREASE-INTERCEPTOR",
                },
            )
        )

    return results
