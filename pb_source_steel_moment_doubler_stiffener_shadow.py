"""Source Structural Steel Moment Connection Web Doubler Plate & Continuity Stiffener Shadow Authority.

Extracts candidate column web doubler plates, continuity stiffeners, panel zone reinforcement,
weld specifications, and connection coordinates from structural steel detail drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class MomentDoublerStiffenerCandidate:
    candidate_id: str
    sheet_id: str
    doubler_configuration: str
    doubler_thickness_mm: Optional[float]
    continuity_stiffener_thickness_mm: Optional[float]
    continuity_stiffener_pairs: int
    weld_type: str
    weld_size_mm: Optional[float]
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "doubler_configuration": self.doubler_configuration,
            "doubler_thickness_mm": self.doubler_thickness_mm,
            "continuity_stiffener_thickness_mm": self.continuity_stiffener_thickness_mm,
            "continuity_stiffener_pairs": self.continuity_stiffener_pairs,
            "weld_type": self.weld_type,
            "weld_size_mm": self.weld_size_mm,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_moment_doubler_stiffener_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "WEB DOUBLER",
        "DOUBLER PLATE",
        "CONTINUITY STIFFENER",
        "MOMENT CONNECTION STIFFENER",
        "PANEL ZONE DOUBLER",
        "COLUMN STIFFENER PL",
        "MOMENT STIFFENER",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Doubler configuration
    if "BOTH SIDES" in upper or "2 SIDES" in upper or "DOUBLE DOUBLER" in upper:
        doubler_config = "DOUBLE_DOUBLER"
    elif "DOUBLER" in upper:
        doubler_config = "SINGLE_DOUBLER"
    else:
        doubler_config = "NONE"

    # Doubler thickness (e.g. "16MM DOUBLER", "12MM WEB DOUBLER PL", "WEB DOUBLER 2 SIDES 12MM")
    doubler_thick = None
    d_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:PL|PLATE|WEB)?\s*DOUBLER\b", upper)
    if not d_match:
        d_match = re.search(r"\bDOUBLER\s*(?:[A-Z0-9\s]{0,15}?)\s*(\d{1,2})\s*MM\b", upper)
    if d_match:
        doubler_thick = float(d_match.group(1))
    elif doubler_config != "NONE":
        doubler_thick = 16.0

    # Continuity stiffener thickness (e.g. "20MM CONTINUITY STIFFENER", "16MM STIFFENER PL", "25MM CONT STIFF")
    stiff_thick = None
    s_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:THICK|PL|PLATE)?\s*(?:CONTINUITY|COLUMN|TRANSVERSE)?\s*STIFFENER\b", upper)
    if not s_match:
        s_match = re.search(r"\bSTIFFENER\s*(?:PL|PLATE)?\s*(\d{1,2})\s*MM\b", upper)
    if s_match:
        stiff_thick = float(s_match.group(1))
    else:
        stiff_thick = 16.0

    # Continuity stiffener pairs (top and bottom flanges = 2 pairs; 1 flange = 1 pair)
    if "TOP & BTM" in upper or "BOTH FLANGES" in upper or "TOP AND BOTTOM" in upper or "4 NO." in upper:
        stiff_pairs = 2
    elif "1 PAIR" in upper or "TOP FLANGE ONLY" in upper:
        stiff_pairs = 1
    else:
        stiff_pairs = 2  # standard moment connection has stiffeners at both flanges

    # Weld type
    if "CJP" in upper or "COMPLETE PENETRATION" in upper or "FULL PENETRATION" in upper:
        weld_type = "CJP_GROOVE"
        weld_size = None
    elif "BEVEL" in upper or "GROOVE" in upper:
        weld_type = "BEVEL_GROOVE"
        weld_size = None
    else:
        weld_type = "FILLET_WELD"
        w_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:CFW|FILLET|WELD|FW)\b", upper)
        weld_size = float(w_match.group(1)) if w_match else 8.0

    return {
        "raw_text": clean,
        "doubler_configuration": doubler_config,
        "doubler_thickness_mm": doubler_thick,
        "continuity_stiffener_thickness_mm": stiff_thick,
        "continuity_stiffener_pairs": stiff_pairs,
        "weld_type": weld_type,
        "weld_size_mm": weld_size,
    }


def evaluate_steel_moment_doubler_stiffener_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[MomentDoublerStiffenerCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_moment_doubler_stiffener_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_mds_{i+1:03d}"
        cand = MomentDoublerStiffenerCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            doubler_configuration=parsed["doubler_configuration"],
            doubler_thickness_mm=parsed["doubler_thickness_mm"],
            continuity_stiffener_thickness_mm=parsed["continuity_stiffener_thickness_mm"],
            continuity_stiffener_pairs=parsed["continuity_stiffener_pairs"],
            weld_type=parsed["weld_type"],
            weld_size_mm=parsed["weld_size_mm"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
