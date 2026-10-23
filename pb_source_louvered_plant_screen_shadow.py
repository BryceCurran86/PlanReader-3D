"""
Source External Louvered Equipment Screen Plant Deck Shadow Authority.

Extracts and validates plant deck equipment screening, horizontal/acoustic/chevron louver profiles,
aerodynamic free area (%), visual occlusion ratings, overall heights, support posts, and architectural finishes
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class LouveredPlantScreenCallout:
    raw_text: str
    screen_profile: str
    blade_free_area_percent: float
    overall_height_mm: float
    structural_support_post: str
    visual_screening_percent: float
    finish_specification: str
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


def parse_louvered_plant_screen_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "EQUIPMENT SCREEN",
        "PLANT SCREEN",
        "LOUVERED SCREEN",
        "LOUVRE SCREEN",
        "ROOF SCREEN",
        "PLANT DECK SCREEN",
        "CONDENSER SCREEN",
        "CHILLER SCREEN",
        "MECHANICAL SCREEN",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("SCREEN" in upper or "SCREENING" in upper) and ("PLANT" in upper or "LOUVER" in upper or "LOUVRE" in upper or "DECK" in upper)
    )
    if not has_trigger:
        return None

    # Screen blade profile
    if "ACOUSTIC" in upper:
        profile = "ACOUSTIC_LOUVER_SCREEN"
    elif "VERTICAL" in upper:
        profile = "VERTICAL_SLAT_SCREEN"
    elif any(k in upper for k in ["CHEVRON", "INVERTED Y", "SIGHT PROOF"]):
        profile = "CHEVRON_VISUAL_SCREEN"
    elif any(k in upper for k in ["HORIZONTAL", "CONTINUOUS"]):
        profile = "CONTINUOUS_HORIZONTAL_LOUVER"
    else:
        profile = "CONTINUOUS_HORIZONTAL_LOUVER"

    # Aerodynamic free ventilation area percentage
    free_match = re.search(r"(\d{2}(?:\.\d+)?)\s*%\s*(?:FREE\s*AREA|VENTILATION|OPEN)", upper)
    if not free_match:
        free_match = re.search(r"(?:FREE\s*AREA|VENTILATION)\s*(?:OF|:)?\s*(\d{2}(?:\.\d+)?)\s*%", upper)

    if free_match:
        free_pct = float(free_match.group(1))
    else:
        free_pct = 50.0  # standard engineering default for mechanical equipment screens

    # Overall height in mm
    h_match = re.search(r"(\d{4})\s*(?:MM)?\s*(?:HIGH|HEIGHT|OVERALL|O/A)", upper)
    if not h_match:
        h_match = re.search(r"(?:HEIGHT|H)\s*(?:OF|:)?\s*(\d{4})\s*(?:MM)?", upper)
    if not h_match:
        h_match = re.search(r"\b([1-5]\d{3})\s*MM\b", upper)

    if h_match and 1200.0 <= float(h_match.group(1)) <= 6000.0:
        height_mm = float(h_match.group(1))
    else:
        height_mm = 2400.0  # standard plant deck screen height

    # Structural support post
    if any(k in upper for k in ["SHS", "STEEL POST", "RHS", "STEEL COLUMN"]):
        support = "STEEL_SHS_POST"
    elif any(k in upper for k in ["ALUMINIUM BOX", "ALUMINUM BOX", "ALLOY POST", "ALUMINIUM POST"]):
        support = "ALUMINIUM_BOX_POST"
    elif any(k in upper for k in ["CHANNEL", "PFC", "C-CHANNEL"]):
        support = "C-CHANNEL_MULLION"
    elif "UNISTRUT" in upper:
        support = "UNISTRUT_FRAME"
    else:
        support = "STEEL_SHS_POST"

    # Visual screening percentage
    vis_match = re.search(r"(\d{2,3})\s*%\s*(?:VISUAL|BLOCKAGE|SIGHT|OCCLUSION)", upper)
    if vis_match:
        visual_pct = float(vis_match.group(1))
    else:
        if any(k in upper for k in ["FULL SIGHT", "COMPLETE VISUAL", "100%", "NO SIGHTLINE", "CHEVRON"]):
            visual_pct = 100.0
        else:
            visual_pct = 100.0  # standard architectural requirement for plant screens

    # Surface coating / finish (evaluate powder coat / anodize before generic steel!)
    if any(k in upper for k in ["ANODISED", "ANODIZED", "25UM"]):
        finish = "ANODIZED_25UM"
    elif any(k in upper for k in ["POWDER COAT", "DULUX", "INTERPON"]):
        finish = "POWDER_COATED_DULUX"
    elif any(k in upper for k in ["HOT DIP", "HDG", "HOT-DIP"]):
        finish = "HOT_DIP_GALVANIZED"
    elif "MILL FINISH" in upper:
        finish = "MILL_FINISH"
    else:
        finish = "POWDER_COATED_DULUX"

    return {
        "raw_text": clean,
        "screen_profile": profile,
        "blade_free_area_percent": free_pct,
        "overall_height_mm": height_mm,
        "structural_support_post": support,
        "visual_screening_percent": visual_pct,
        "finish_specification": finish,
    }


class SourceLouveredPlantScreenShadowAuthority:
    """Authority for external louvered equipment screens in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[LouveredPlantScreenCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[LouveredPlantScreenCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[LouveredPlantScreenCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_louvered_plant_screen_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = LouveredPlantScreenCallout(
                raw_text=parsed["raw_text"],
                screen_profile=parsed["screen_profile"],
                blade_free_area_percent=parsed["blade_free_area_percent"],
                overall_height_mm=parsed["overall_height_mm"],
                structural_support_post=parsed["structural_support_post"],
                visual_screening_percent=parsed["visual_screening_percent"],
                finish_specification=parsed["finish_specification"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
