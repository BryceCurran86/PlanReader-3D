"""
Source Structural Steel Girt Sag Rod & Fly Bracing Shadow Authority.

Extracts and validates cold-formed girt and purlin sag rods, fly bracing angles,
row configurations, and bolt connection details strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SteelGirtSagRodFlyBraceCallout:
    raw_text: str
    component_category: str
    section_profile: str
    row_configuration: str
    fastener_type: str
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


def parse_steel_girt_sag_rod_fly_brace_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SAG ROD",
        "FLY BRACE",
        "FLY BRACING",
        "GIRT SAG",
        "PURLIN SAG",
        "SAG STRAP",
        "SAG SYSTEM",
        "BOTTOM FLANGE FLY BRACE",
        "TIE ROD GIRT",
        "SAG TIE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Category determination
    has_sag = any(k in upper for k in ["SAG", "TIE ROD"])
    has_fly = "FLY" in upper

    if has_sag and has_fly:
        category = "COMBINED_SAG_FLY"
    elif has_fly:
        category = "FLY_BRACE"
    else:
        category = "SAG_ROD_SYSTEM"

    # Section profile
    # For fly brace: e.g. "50X50X5 EA", "50X50X6 EA", "65X50X5 UA", "40X40X4"
    angle_match = re.search(r"\b(\d{2,3}\s*[xX]\s*\d{2,3}\s*[xX]\s*\d{1,2}(?:\.\d)?)\s*(?:EA|UA)?", upper)
    # For sag rod: e.g. "M12", "M16", "M10", "12MM DIA ROD", "16MM ROD"
    rod_match = re.search(r"\b(M10|M12|M16|M20)\b", upper)
    strap_match = re.search(r"\b(\d{2}\s*[xX]\s*\d{1,2})\s*(?:STRAP|FLAT)", upper)

    if category == "FLY_BRACE":
        if angle_match:
            section = angle_match.group(1).replace(" ", "").lower() + " EA"
        else:
            section = "50x50x5 EA"
    elif category == "COMBINED_SAG_FLY":
        sec_parts = []
        if rod_match:
            sec_parts.append(rod_match.group(1))
        else:
            sec_parts.append("M12")
        if angle_match:
            sec_parts.append(angle_match.group(1).replace(" ", "").lower() + " EA")
        else:
            sec_parts.append("50x50x5 EA")
        section = " + ".join(sec_parts)
    else:  # SAG_ROD_SYSTEM
        if rod_match:
            section = rod_match.group(1)
        elif strap_match:
            section = strap_match.group(1).replace(" ", "").lower() + " FLAT STRAP"
        elif "16MM" in upper:
            section = "M16"
        elif "10MM" in upper:
            section = "M10"
        else:
            section = "M12"

    # Row configuration / spacing
    if any(k in upper for k in ["DOUBLE ROW", "TWO ROWS", "2 ROWS", "THIRD POINT"]):
        row_config = "THIRD_POINTS_DOUBLE_ROW"
    elif any(k in upper for k in ["QUARTER POINT", "3 ROWS", "THREE ROWS"]):
        row_config = "QUARTER_POINTS_TRIPLE_ROW"
    else:
        row_config = "MIDSPAN_SINGLE_ROW"

    # Fastener type
    if "8.8" in upper:
        fastener = "M16_GRADE_8.8"
    elif "TEK" in upper or "SCREW" in upper:
        fastener = "SELF_DRILLING_TEK_SCREWS"
    elif "WELD" in upper:
        fastener = "WELDED_CLEAT"
    else:
        fastener = "M12_GRADE_4.6"

    # Finish / coating
    if "ZINC" in upper:
        finish = "ELECTRO_ZINC_PLATED"
    elif "PAINT" in upper or "PRIME" in upper:
        finish = "EPOXY_PRIMER_PAINTED"
    else:
        finish = "HOT_DIP_GALVANISED"

    return {
        "raw_text": clean,
        "component_category": category,
        "section_profile": section,
        "row_configuration": row_config,
        "fastener_type": fastener,
        "finish_coating": finish,
    }


def evaluate_steel_girt_sag_rod_fly_brace_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[SteelGirtSagRodFlyBraceCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[SteelGirtSagRodFlyBraceCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_steel_girt_sag_rod_fly_brace_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            SteelGirtSagRodFlyBraceCallout(
                raw_text=parsed["raw_text"],
                component_category=parsed["component_category"],
                section_profile=parsed["section_profile"],
                row_configuration=parsed["row_configuration"],
                fastener_type=parsed["fastener_type"],
                finish_coating=parsed["finish_coating"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "steel_standard": "AS4100-STEEL-BRACING",
                },
            )
        )

    return results
