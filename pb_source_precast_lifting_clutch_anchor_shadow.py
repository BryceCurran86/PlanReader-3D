"""
Source Precast Concrete Sandwich Panel Lifting Clutch & Tilt Anchor Shadow Authority.

Extracts and validates precast and tilt-up concrete wall panel lifting anchors,
rated working capacities (WLL), anchor geometries, recess formers, and edge clearances strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PrecastLiftingClutchAnchorCallout:
    raw_text: str
    working_load_limit_tonnes: float
    anchor_type: str
    recess_former_type: str
    supplementary_reinforcement: str
    min_edge_distance_mm: float
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


def parse_precast_lifting_clutch_anchor_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "LIFTING ANCHOR",
        "TILT ANCHOR",
        "LIFTING CLUTCH",
        "EDGE LIFT ANCHOR",
        "FACE LIFT ANCHOR",
        "ERECTION ANCHOR",
        "PRECAST CLUTCH",
        "REID ANCHOR",
        "SWIFT LIFT",
        "PINTLE ANCHOR",
        "EDGE LIFT",
        "FACE LIFT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Working Load Limit (WLL): e.g. "2.5T", "5.0T", "10.0T", "1.3T", "7.5T", "5T", "10T", "2.5 TONNE"
    wll_match = re.search(r"\b(\d{1,2}(?:\.\d)?)\s*(?:T|TONNE|TONS|TON)\b", upper)
    wll_tonnes = float(wll_match.group(1)) if wll_match else 5.0

    # Anchor application type
    if any(k in upper for k in ["EDGE LIFT", "EDGE-LIFT", "PANEL EDGE", "ERECTION"]):
        anchor_type = "EDGE_LIFT_ERECTION"
    elif any(k in upper for k in ["FACE LIFT", "FACE-LIFT", "TILT UP", "TILT-UP"]):
        anchor_type = "FACE_LIFT_TILT_UP"
    elif any(k in upper for k in ["FOOT ANCHOR", "SPREAD ANCHOR", "SWIFT LIFT"]):
        anchor_type = "SPHERICAL_HEAD_FOOT"
    else:
        anchor_type = "EDGE_LIFT_ERECTION"

    # Recess former type
    if "MAGNET" in upper:
        former = "MAGNETIC_FORMER"
    elif "STEEL" in upper and "FORMER" in upper:
        former = "STEEL_FORMER"
    else:
        former = "RUBBER_RECESS_FORMER"

    # Supplementary reinforcement
    if any(k in upper for k in ["SHEAR BAR", "TENSION BAR", "HAIRPIN", "U-BAR"]):
        reo = "SHEAR_BAR_HAIRPIN"
    elif any(k in upper for k in ["STIRRUP", "TIE", "SPIRAL", "BURSTING"]):
        reo = "PERIMETER_STIRRUPS"
    else:
        reo = "STANDARD_MESH_ONLY"

    # Minimum edge distance (e.g. "150MM EDGE DISTANCE", "200MM MIN DISTANCE", "120MM EDGE")
    dist_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:MIN\s*)?(?:EDGE|DISTANCE)?", upper)
    edge_dist = float(dist_match.group(1)) if dist_match else 150.0

    return {
        "raw_text": clean,
        "working_load_limit_tonnes": wll_tonnes,
        "anchor_type": anchor_type,
        "recess_former_type": former,
        "supplementary_reinforcement": reo,
        "min_edge_distance_mm": edge_dist,
    }


def evaluate_precast_lifting_clutch_anchor_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[PrecastLiftingClutchAnchorCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[PrecastLiftingClutchAnchorCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_precast_lifting_clutch_anchor_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            PrecastLiftingClutchAnchorCallout(
                raw_text=parsed["raw_text"],
                working_load_limit_tonnes=parsed["working_load_limit_tonnes"],
                anchor_type=parsed["anchor_type"],
                recess_former_type=parsed["recess_former_type"],
                supplementary_reinforcement=parsed["supplementary_reinforcement"],
                min_edge_distance_mm=parsed["min_edge_distance_mm"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "anchor_standard": "AS3850-PRECAST-LIFTING",
                },
            )
        )

    return results
