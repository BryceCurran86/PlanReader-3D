"""
Source Cavity Masonry Movement Control Joint & Debonded Tie Shadow Authority.

Extracts and validates masonry vertical articulation movement control joints (MCJ/EJ),
gap widths (mm), debonded slip ties with sleeves, tie vertical spacing (mm), backing rods, and polyurethane sealant strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class MasonryControlJointTieCallout:
    raw_text: str
    joint_width_mm: float
    tie_type: str
    tie_vertical_spacing_mm: float
    sealant_type: str
    backing_rod_diameter_mm: float
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


def parse_masonry_control_joint_tie_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CONTROL JOINT",
        "ARTICULATION JOINT",
        "MOVEMENT JOINT",
        "EXPANSION JOINT",
        "MCJ",
        "AJ",
        "MASONRY JOINT",
        "DEBONDED TIE",
        "SLIP TIE",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Joint width mm
    j_width = 10.0
    w_match = re.search(r"(\d{1,2})\s*(?:MM)?\s*(?:WIDE|WIDTH|GAP|MCJ|AJ|JOINT)", upper)
    if w_match:
        val = float(w_match.group(1))
        if 5 <= val <= 50:
            j_width = val
    else:
        mm_match = re.search(r"(\d{1,2})\s*MM\b", upper)
        if mm_match:
            val = float(mm_match.group(1))
            if 5 <= val <= 50:
                j_width = val

    # Tie type
    if "DOVETAIL" in upper:
        tie = "DOVETAIL_DEBONDED_ANCHOR"
    elif "EXPANSION TIE" in upper or "STAINLESS" in upper:
        tie = "EXPANSION_TIE_STAINLESS_STEEL"
    elif "DEBONDED" in upper or "SLIP" in upper or "SLEEVE" in upper or "TIE" in upper:
        tie = "DEBONDED_SLIP_TIE_WITH_SLEEVE"
    else:
        tie = "DEBONDED_SLIP_TIE_WITH_SLEEVE"

    # Tie vertical spacing mm
    spacing_mm = 400.0
    s_match = re.search(r"(?:@|\bAT\b)\s*(\d{2,4})\s*(?:MM)?\s*(?:CTS|CENTRES|CENTERS|C/C|VERT)?", upper)
    if s_match:
        s_val = float(s_match.group(1))
        if 150 <= s_val <= 1200:
            spacing_mm = s_val

    # Sealant type
    if "SILICONE" in upper:
        sealant = "LOW_MODULUS_SILICONE"
    elif "HYBRID" in upper or "MS POLYMER" in upper:
        sealant = "HYBRID_POLYMER"
    elif "POLYURETHANE" in upper or "PU" in upper or "MASTIC" in upper:
        sealant = "POLYURETHANE_ELASTOMERIC_SEALANT"
    else:
        sealant = "POLYURETHANE_ELASTOMERIC_SEALANT"

    # Backing rod diameter mm (typically 20-30% larger than joint width)
    backing_rod = round(j_width * 1.25)
    rod_match = re.search(r"(\d{1,2})\s*(?:MM)?\s*(?:BACKING ROD|FOAM ROD|PE ROD)", upper)
    if rod_match:
        backing_rod = float(rod_match.group(1))

    return {
        "joint_width_mm": j_width,
        "tie_type": tie,
        "tie_vertical_spacing_mm": spacing_mm,
        "sealant_type": sealant,
        "backing_rod_diameter_mm": backing_rod,
    }


class SourceMasonryControlJointTieShadowAuthority:
    """Authority for extracting masonry movement control joints and debonded ties in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[MasonryControlJointTieCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[MasonryControlJointTieCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_masonry_control_joint_tie_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["joint_width_mm"], parsed["tie_type"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = MasonryControlJointTieCallout(
                raw_text=text,
                joint_width_mm=parsed["joint_width_mm"],
                tie_type=parsed["tie_type"],
                tie_vertical_spacing_mm=parsed["tie_vertical_spacing_mm"],
                sealant_type=parsed["sealant_type"],
                backing_rod_diameter_mm=parsed["backing_rod_diameter_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
