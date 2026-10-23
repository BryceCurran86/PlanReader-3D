"""
Source Architectural Louver Storm Proof Blade & Sand Trap Shadow Authority.

Extracts and validates architectural ventilation louvers, stormproof chevron blades,
sand-trap profiles, free area percentages, and screen backings strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class LouverStormProofSandTrapCallout:
    raw_text: str
    blade_profile: str
    frame_depth_mm: float
    blade_pitch_mm: float
    free_area_percent: float
    screen_backing: str
    finish_coating: str
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


def parse_louver_storm_proof_sand_trap_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "STORMPROOF LOUVRE",
        "STORMPROOF LOUVER",
        "SAND TRAP LOUVRE",
        "SAND TRAP LOUVER",
        "TWO STAGE LOUVER",
        "TWO STAGE LOUVRE",
        "DUAL STAGE LOUVRE",
        "DUAL STAGE LOUVER",
        "CHEVRON LOUVRE",
        "CHEVRON LOUVER",
        "WEATHER LOUVER",
        "WEATHER LOUVRE",
        "VENTILATION LOUVER",
        "VENTILATION LOUVRE",
        "PLANTROOM LOUVER",
        "PLANTROOM LOUVRE",
        "DRAINABLE BLADE LOUVER",
        "DRAINABLE BLADE LOUVRE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Blade profile
    if any(k in upper for k in ["SAND TRAP", "SAND-TRAP", "SAND FILTER"]):
        blade_prof = "SAND_TRAP_SELF_DRAINING"
    elif any(k in upper for k in ["TWO STAGE", "DUAL STAGE", "CHEVRON", "CLASS A"]):
        blade_prof = "TWO_STAGE_CHEVRON"
    else:
        blade_prof = "SINGLE_STAGE_DRAINABLE"

    # Frame depth (e.g. "100MM DEEP", "150MM FRAME", "75MM DEEP")
    depth_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:DEEP|FRAME|DEPTH)\b", upper)
    depth_mm = float(depth_match.group(1)) if depth_match else 100.0

    # Blade pitch (e.g. "75MM PITCH", "50MM PITCH", "100MM PITCH")
    pitch_match = re.search(r"\b(\d{2,3})\s*MM\s*PITCH\b", upper)
    pitch_mm = float(pitch_match.group(1)) if pitch_match else 75.0

    # Free area percentage (e.g. "50% FREE AREA", "55% FA", "48% FREE AIR")
    fa_match = re.search(r"\b(\d{2}(?:\.\d)?)\s*%\s*(?:FREE\s*AREA|FA|FREE\s*AIR)?", upper)
    free_area = float(fa_match.group(1)) if fa_match else 50.0

    # Screen backing: stainless bird mesh vs insect screen
    if any(k in upper for k in ["INSECT", "FLY SCREEN", "FLYSCREEN"]):
        screen = "ALUMINIUM_INSECT_SCREEN"
    elif "EXPANDED" in upper:
        screen = "EXPANDED_ALUMINIUM_MESH"
    else:
        screen = "STAINLESS_STEEL_BIRD_MESH"

    # Finish coating
    if "POWDER" in upper or "DULUX" in upper or "INTERPON" in upper:
        finish = "POWDER_COATED_ALUMINIUM"
    elif "ANODIS" in upper or "ANODIZ" in upper:
        finish = "ANODISED_ALUMINIUM"
    elif "GALV" in upper:
        finish = "GALVANISED_STEEL"
    else:
        finish = "POWDER_COATED_ALUMINIUM"

    return {
        "raw_text": clean,
        "blade_profile": blade_prof,
        "frame_depth_mm": depth_mm,
        "blade_pitch_mm": pitch_mm,
        "free_area_percent": free_area,
        "screen_backing": screen,
        "finish_coating": finish,
    }


def evaluate_louver_storm_proof_sand_trap_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[LouverStormProofSandTrapCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[LouverStormProofSandTrapCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_louver_storm_proof_sand_trap_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            LouverStormProofSandTrapCallout(
                raw_text=parsed["raw_text"],
                blade_profile=parsed["blade_profile"],
                frame_depth_mm=parsed["frame_depth_mm"],
                blade_pitch_mm=parsed["blade_pitch_mm"],
                free_area_percent=parsed["free_area_percent"],
                screen_backing=parsed["screen_backing"],
                finish_coating=parsed["finish_coating"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "louver_standard": "ASNZS4740-CLASS-A",
                },
            )
        )

    return results
