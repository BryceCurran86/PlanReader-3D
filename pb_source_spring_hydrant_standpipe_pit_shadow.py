"""
Source Underground Fire Hydrant Spring Hydrant & Standpipe Pit Shadow Authority.

Extracts and validates civil and fire services underground spring hydrants,
standpipe connection pits, pipe sizes, cover classes, and drainage details strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SpringHydrantStandpipePitCallout:
    raw_text: str
    hydrant_valve_type: str
    main_diameter_mm: float
    pit_box_material: str
    surface_cover_class: str
    drainage_type: str
    cover_marking: str
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


def parse_spring_hydrant_standpipe_pit_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SPRING HYDRANT",
        "IN-GROUND HYDRANT",
        "UNDERGROUND HYDRANT",
        "FIRE HYDRANT PIT",
        "STANDPIPE PIT",
        "SPRING VALVE HYDRANT",
        "FH PIT",
        "GROUND HYDRANT",
        "FH IN PIT",
        "MILLCOCK HYDRANT",
        "STANDPIPE HYDRANT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Valve type
    if "SCREW" in upper:
        valve_type = "SCREW_DOWN_HYDRANT"
    elif "SLUICE" in upper or "GATE" in upper:
        valve_type = "SLUICE_VALVE_HYDRANT"
    else:
        valve_type = "SPRING_VALVE_AS3952"

    # Main nominal diameter (e.g. "DN100", "DN150", "100MM", "150MM", "DN80")
    dia_match = re.search(r"\b(?:DN\s*|Ø\s*)(\d{2,3})\b", upper)
    if not dia_match:
        dia_match = re.search(r"\b(\d{2,3})\s*MM\b", upper)
    main_dia = float(dia_match.group(1)) if dia_match else 100.0

    # Pit box material: precast concrete vs polymer vs cast iron surround
    if "CONCRETE" in upper or "PRECAST" in upper:
        pit_mat = "PRECAST_CONCRETE"
    elif any(k in upper for k in ["POLYMER", "COMPOSITE", "PLASTIC", "FRP"]):
        pit_mat = "POLYMER_COMPOSITE"
    else:
        pit_mat = "CAST_IRON_SURROUND"

    # Surface cover rating
    if any(k in upper for k in ["CLASS D", "TRAFFICABLE", "ROADWAY", "CARPARK"]):
        cover_class = "CLASS_D_ROADWAY"
    elif any(k in upper for k in ["CLASS B", "FOOTWAY", "VERGE", "NON-TRAFFICABLE", "LANDSCAPE"]):
        cover_class = "CLASS_B_FOOTWAY"
    else:
        cover_class = "CLASS_D_ROADWAY"

    # Drainage type
    if "SUMP" in upper or "DRAIN PIPE" in upper:
        drainage = "SUMP_DRAIN"
    else:
        drainage = "GRAVEL_SOAKAWAY"

    return {
        "raw_text": clean,
        "hydrant_valve_type": valve_type,
        "main_diameter_mm": main_dia,
        "pit_box_material": pit_mat,
        "surface_cover_class": cover_class,
        "drainage_type": drainage,
        "cover_marking": "FH_FIRE_HYDRANT",
    }


def evaluate_spring_hydrant_standpipe_pit_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[SpringHydrantStandpipePitCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[SpringHydrantStandpipePitCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_spring_hydrant_standpipe_pit_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            SpringHydrantStandpipePitCallout(
                raw_text=parsed["raw_text"],
                hydrant_valve_type=parsed["hydrant_valve_type"],
                main_diameter_mm=parsed["main_diameter_mm"],
                pit_box_material=parsed["pit_box_material"],
                surface_cover_class=parsed["surface_cover_class"],
                drainage_type=parsed["drainage_type"],
                cover_marking=parsed["cover_marking"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "hydrant_standard": "AS3952-AS2419.1",
                },
            )
        )

    return results
