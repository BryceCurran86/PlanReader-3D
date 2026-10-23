"""
Source Concrete Slab Dowelled Contraction Joint Flanged Plate Dowel Shadow Authority.

Extracts and validates industrial concrete ground slab plate dowels, diamond dowel systems,
plate thicknesses, joint centers, and expansion sleeves strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FlangedPlateDowelCallout:
    raw_text: str
    dowel_geometry: str
    plate_thickness_mm: float
    plate_width_mm: float
    plate_length_mm: float
    joint_spacing_cts_mm: float
    sleeve_type: str
    steel_grade: str
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


def parse_flanged_plate_dowel_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "PLATE DOWEL",
        "DIAMOND DOWEL",
        "FLANGED DOWEL",
        "DOWEL CRADLE",
        "CONTRACTION JOINT DOWEL",
        "ARMOR EDGE DOWEL",
        "SLAB DOWEL SLEEVE",
        "EXPANSION DOWEL PLATE",
        "JOINT DOWEL",
        "SAWCUT DOWEL",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Dowel geometry
    if "DIAMOND" in upper:
        geometry = "DIAMOND_PLATE"
    elif any(k in upper for k in ["ROUND", "R16", "R20", "R24", "R28", "R32", "BAR DOWEL"]):
        geometry = "ROUND_DOWEL_SLEEVE"
    else:
        geometry = "RECTANGULAR_PLATE"

    # Plate thickness (e.g. "6MM", "10MM", "8MM", "12MM", "20MM")
    thk_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:THK|THICK|PLATE|DOWEL)?\b", upper)
    thickness = float(thk_match.group(1)) if thk_match else 6.0

    # Plate dimensions (e.g. "150X150", "110X110", "100X100", "150X100")
    dim_match = re.search(r"\b(\d{2,3})\s*[xX]\s*(\d{2,3})\b", upper)
    if dim_match:
        width = float(dim_match.group(1))
        length = float(dim_match.group(2))
    elif geometry == "DIAMOND_PLATE":
        width = 150.0
        length = 150.0
    else:
        width = 100.0
        length = 100.0

    # Joint spacing centers (e.g. "450MM CTS", "600MM CTS", "450 CTS", "500MM CENTERS", "600 CTS")
    cts_match = re.search(r"\b(\d{3})\s*(?:MM)?\s*(?:CTS|CENTRES|CENTERS|C/C)\b", upper)
    spacing_cts = float(cts_match.group(1)) if cts_match else 450.0

    # Sleeve type
    if "FOAM" in upper or "LATERAL" in upper:
        sleeve = "COMPRESSIBLE_FOAM_SLEEVE"
    elif "NO SLEEVE" in upper or "WITHOUT SLEEVE" in upper:
        sleeve = "UNSLEEVED_DEBONDED"
    else:
        sleeve = "PLASTIC_EXPANSION_SLEEVE"

    # Steel grade
    if "STAINLESS" in upper or "316" in upper:
        steel = "STAINLESS_STEEL_316"
    elif "GALV" in upper:
        steel = "GALVANISED_STEEL"
    else:
        steel = "GRADE_300_STEEL"

    return {
        "raw_text": clean,
        "dowel_geometry": geometry,
        "plate_thickness_mm": thickness,
        "plate_width_mm": width,
        "plate_length_mm": length,
        "joint_spacing_cts_mm": spacing_cts,
        "sleeve_type": sleeve,
        "steel_grade": steel,
    }


def evaluate_flanged_plate_dowel_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[FlangedPlateDowelCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[FlangedPlateDowelCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_flanged_plate_dowel_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            FlangedPlateDowelCallout(
                raw_text=parsed["raw_text"],
                dowel_geometry=parsed["dowel_geometry"],
                plate_thickness_mm=parsed["plate_thickness_mm"],
                plate_width_mm=parsed["plate_width_mm"],
                plate_length_mm=parsed["plate_length_mm"],
                joint_spacing_cts_mm=parsed["joint_spacing_cts_mm"],
                sleeve_type=parsed["sleeve_type"],
                steel_grade=parsed["steel_grade"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "joint_standard": "ACI360R-AS3600-DOWELS",
                },
            )
        )

    return results
