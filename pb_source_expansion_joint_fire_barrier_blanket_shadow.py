"""
Source Architectural Expansion Joint Fire Barrier Blanket Shadow Authority.

Extracts and validates expansion joint fire barrier blankets, ceramic fiber foil blankets,
joint gap widths, movement percentages (+/-%), and 1-4 hour fire resistance ratings strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ExpansionJointFireBarrierBlanketCallout:
    raw_text: str
    barrier_type: str
    nominal_joint_width_mm: Optional[float]
    movement_capacity_percent: Optional[str]
    fire_rating_hours: Optional[str]
    retaining_flange_brackets: str
    smoke_barrier_layer: str
    joint_orientation: str
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


def parse_expansion_joint_fire_barrier_blanket_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "FIRE BARRIER BLANKET",
        "EXPANSION JOINT FIRE BARRIER",
        "SEISMIC JOINT FIRE BARRIER",
        "FIRELINE",
        "FIRE BARRIER SYSTEM",
        "JOINT FIRE BARRIER",
        "FIRE RATED EXPANSION JOINT",
        "FLEXIBLE FIRE BARRIER",
        "CERAMIC FIBER FIRE BARRIER",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("EXPANSION JOINT" in upper or "SEISMIC JOINT" in upper or "MOVEMENT JOINT" in upper or "JOINT GAP" in upper)
        and ("FIRE BARRIER" in upper or "FIRE BLANKET" in upper or "FIRE RATED" in upper or "FIRE RESISTANCE" in upper)
    )
    if not has_trigger:
        return None

    # Barrier Type
    if any(k in upper for k in ["CERAMIC FIBER", "CERAMIC FIBRE", "FOIL BLANKET", "QUILTED CERAMIC", "CERAMIC BLANKET"]):
        barrier_type = "CERAMIC_FIBER_FOIL_BLANKET"
    elif any(k in upper for k in ["INTUMESCENT", "MULTI-LAYER", "MULTILAYER"]):
        barrier_type = "MULTI_LAYER_INTUMESCENT_BLANKET"
    elif any(k in upper for k in ["MINERAL WOOL", "PRE-COMPRESSED", "ELASTOMERIC COATING", "FOAM SEAL"]):
        barrier_type = "MINERAL_WOOL_ELASTOMERIC_SEAL"
    elif any(k in upper for k in ["MODULAR", "FIRELINE", "REFLEX"]):
        barrier_type = "MODULAR_FIRE_BARRIER_SYSTEM"
    else:
        barrier_type = "GENERIC_FIRE_BLANKET"

    # Nominal Joint Width (mm)
    joint_width_mm: Optional[float] = None
    jw_m = (
        re.search(r"(\d{2,3})\s*MM\s*(?:NOMINAL\s+)?(?:JOINT|GAP|WIDTH|EXPANSION\s*JOINT)\b", upper)
        or re.search(r"(?:JOINT|GAP|WIDTH)\s*(?:OF\s*)?(\d{2,3})\s*MM\b", upper)
        or re.search(r"\b(\d{2,3})\s*MM\b", upper)
    )
    if jw_m:
        val = float(jw_m.group(1))
        # Expansion joints are typically 25mm to 500mm wide
        if 20.0 <= val <= 500.0:
            joint_width_mm = val

    # Movement Capacity (% e.g. +/-50%, +/-25%)
    movement_pct: Optional[str] = None
    mov_m = re.search(r"([±\+\/-]+\s*\d{2,3}\s*%)", upper)
    if mov_m:
        movement_pct = mov_m.group(1).replace(" ", "")

    # Fire Rating Hours / FRL
    fire_rating: Optional[str] = None
    fr_m = re.search(r"\b([1-4])\s*(?:HR|HOUR|HOURS)\b", upper)
    if fr_m:
        fire_rating = f"{fr_m.group(1)}HR"
    else:
        frl_m = re.search(r"\b(FRL\s*[-/0-9]+)\b", upper)
        if frl_m:
            fire_rating = frl_m.group(1).replace(" ", "")

    # Retaining Flange / Brackets
    if any(k in upper for k in ["RETAINING ANGLE", "GALVANIZED ANGLE", "GALV ANGLE", "STEEL ANGLE"]):
        retaining_flange = "GALVANIZED_RETAINING_ANGLES"
    elif any(k in upper for k in ["SPRING CLIP", "STAINLESS CLIP", "SPRING BRACKET"]):
        retaining_flange = "STAINLESS_STEEL_SPRING_CLIPS"
    elif any(k in upper for k in ["PINNED", "FASTENER COLLAR"]):
        retaining_flange = "FASTENER_PINNED_COLLAR"
    else:
        retaining_flange = "UNSPECIFIED"

    # Smoke Barrier Layer
    if any(k in upper for k in ["VAPOR MEMBRANE", "VAPOUR MEMBRANE", "SMOKE MEMBRANE", "VAPOUR BARRIER", "VAPOR BARRIER"]):
        smoke_layer = "INTEGRAL_VAPOR_SMOKE_MEMBRANE"
    elif any(k in upper for k in ["ELASTOMERIC SMOKE COATING", "ELASTOMERIC COATING", "SMOKE SEAL COATING", "SMOKE COATING"]):
        smoke_layer = "ELASTOMERIC_SMOKE_COATING"
    elif any(k in upper for k in ["DUAL SMOKE SEAL", "DOUBLE SMOKE SEAL"]):
        smoke_layer = "DUAL_SMOKE_SEAL"
    else:
        smoke_layer = "UNSPECIFIED"

    # Joint Orientation
    if any(k in upper for k in ["SOFFIT", "CEILING"]):
        orientation = "SOFFIT_EXPANSION_JOINT"
    elif any(k in upper for k in ["WALL", "PARTITION", "VERTICAL JOINT"]):
        orientation = "WALL_EXPANSION_JOINT"
    elif any(k in upper for k in ["ROOF", "PARAPET"]):
        orientation = "ROOF_EXPANSION_JOINT"
    elif any(k in upper for k in ["FLOOR", "SLAB", "HORIZONTAL JOINT"]):
        orientation = "FLOOR_EXPANSION_JOINT"
    else:
        orientation = "GENERIC_JOINT"

    return {
        "raw_text": clean,
        "barrier_type": barrier_type,
        "nominal_joint_width_mm": joint_width_mm,
        "movement_capacity_percent": movement_pct,
        "fire_rating_hours": fire_rating,
        "retaining_flange_brackets": retaining_flange,
        "smoke_barrier_layer": smoke_layer,
        "joint_orientation": orientation,
    }


def extract_expansion_joint_fire_barrier_blanket_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[ExpansionJointFireBarrierBlanketCallout]:
    results: List[ExpansionJointFireBarrierBlanketCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_expansion_joint_fire_barrier_blanket_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = ExpansionJointFireBarrierBlanketCallout(
            raw_text=parsed["raw_text"],
            barrier_type=parsed["barrier_type"],
            nominal_joint_width_mm=parsed["nominal_joint_width_mm"],
            movement_capacity_percent=parsed["movement_capacity_percent"],
            fire_rating_hours=parsed["fire_rating_hours"],
            retaining_flange_brackets=parsed["retaining_flange_brackets"],
            smoke_barrier_layer=parsed["smoke_barrier_layer"],
            joint_orientation=parsed["joint_orientation"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_fire_rating": parsed["fire_rating_hours"] is not None,
                "has_width": parsed["nominal_joint_width_mm"] is not None,
                "has_movement": parsed["movement_capacity_percent"] is not None,
            },
        )
        results.append(candidate)
    return results


def validate_expansion_joint_fire_barrier_blanket_system(
    candidates: List[ExpansionJointFireBarrierBlanketCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    orientation_counts: Dict[str, int] = {}
    rated_barrier_count = 0
    specified_width_count = 0

    for c in candidates:
        type_counts[c.barrier_type] = type_counts.get(c.barrier_type, 0) + 1
        orientation_counts[c.joint_orientation] = orientation_counts.get(c.joint_orientation, 0) + 1
        if c.fire_rating_hours is not None:
            rated_barrier_count += 1
        if c.nominal_joint_width_mm is not None:
            specified_width_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "orientation_counts": orientation_counts,
        "rated_barrier_count": rated_barrier_count,
        "specified_width_count": specified_width_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
