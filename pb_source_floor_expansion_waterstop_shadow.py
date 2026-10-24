"""
Source Architectural Expansion Joint Waterstop Floor Floor Shadow Authority.

Extracts and validates architectural floor-to-floor expansion joints, seismic gap widths,
elastomeric Santoprene seals, sub-slab waterstop drainage troughs, and traffic ratings strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FloorExpansionWaterstopCallout:
    raw_text: str
    gap_width_mm: float
    surface_cover_profile: str
    sub_slab_waterstop_type: str
    movement_capacity_mm: float
    traffic_duty_rating: str
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


def parse_floor_expansion_waterstop_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "FLOOR EXPANSION JOINT",
        "SEISMIC FLOOR JOINT",
        "FLOOR-TO-FLOOR EXPANSION",
        "LATHAM FLOOR JOINT",
        "UNIFLEX FLOOR JOINT",
        "EXPANSION JOINT WATERSTOP",
        "FLOOR MOVEMENT JOINT",
        "WATERPROOF EXPANSION JOINT",
        "CARPARK EXPANSION JOINT",
        "ARCHITECTURAL FLOOR JOINT",
        "PODIUM EXPANSION JOINT",
        "EXPANSION JOINT",
        "FLOOR JOINT",
        "SEISMIC JOINT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Gap width (e.g. "25MM GAP", "50MM JOINT", "75MM GAP", "100MM SEISMIC JOINT", "50MM GAP")
    gap_match = re.search(r"\b(25|30|40|50|75|100|150)\s*MM\s*(?:GAP|JOINT|WIDTH)?\b", upper)
    gap_width = float(gap_match.group(1)) if gap_match else 50.0

    # Surface cover profile
    if any(k in upper for k in ["SERRATED", "ALUMINIUM COVER", "ALUM COVER", "ALUMINIUM PLATE"]):
        profile = "ALUMINIUM_SERRATED_COVER_PLATE"
    elif any(k in upper for k in ["STAINLESS", "PAN SYSTEM", "TILE INFILL", "RECESSED PAN"]):
        profile = "STAINLESS_STEEL_PAN_PLATE"
    else:
        profile = "FLUSH_CENTRAL_SANTOPRENE_SEAL"

    # Sub-slab waterstop membrane
    if any(k in upper for k in ["PVC WATERSTOP", "REARGUARD", "CENTRAL BULB"]):
        waterstop = "CENTRAL_BULB_PVC_WATERSTOP"
    elif any(k in upper for k in ["HYDROPHILIC", "INJECTION HOSE"]):
        waterstop = "HYDROPHILIC_INJECTION_HOSE"
    else:
        waterstop = "CONTINUOUS_EPDM_DRAINAGE_TROUGH"

    # Movement capacity (e.g. "+/- 25MM", "+/- 50MM", "+/- 15MM", "50MM MOVEMENT")
    mov_match = re.search(r"\b(?:\+\/-\s*)?(\d{2})\s*MM\s*MOVEMENT\b", upper)
    if not mov_match:
        mov_match = re.search(r"\+\/-\s*(\d{2})\s*MM\b", upper)
    movement = float(mov_match.group(1)) if mov_match else 25.0

    # Traffic duty rating
    if any(k in upper for k in ["CARPARK", "VEHICULAR", "FORKLIFT", "HEAVY DUTY", "TRUCK"]):
        traffic = "HEAVY_DUTY_VEHICULAR"
    else:
        traffic = "PEDESTRIAN_COMMERCIAL"

    return {
        "raw_text": clean,
        "gap_width_mm": gap_width,
        "surface_cover_profile": profile,
        "sub_slab_waterstop_type": waterstop,
        "movement_capacity_mm": movement,
        "traffic_duty_rating": traffic,
    }


def evaluate_floor_expansion_waterstop_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[FloorExpansionWaterstopCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[FloorExpansionWaterstopCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_floor_expansion_waterstop_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            FloorExpansionWaterstopCallout(
                raw_text=parsed["raw_text"],
                gap_width_mm=parsed["gap_width_mm"],
                surface_cover_profile=parsed["surface_cover_profile"],
                sub_slab_waterstop_type=parsed["sub_slab_waterstop_type"],
                movement_capacity_mm=parsed["movement_capacity_mm"],
                traffic_duty_rating=parsed["traffic_duty_rating"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "expansion_standard": "AS1170.4-SEISMIC-EXPANSION",
                },
            )
        )

    return results
