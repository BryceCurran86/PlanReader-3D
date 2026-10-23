"""Source Geotechnical Screw Pier & Helical Anchor Shadow Authority.

Extracts candidate helical screw piles, screw piers, shaft dimensions,
helix blade configurations, working capacities, and refusal torques from foundation drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class ScrewPierCandidate:
    candidate_id: str
    sheet_id: str
    shaft_type: str
    shaft_diameter_mm: float
    helix_configuration: str
    helix_diameters_mm: List[float]
    working_capacity_kn: float
    minimum_depth_m: Optional[float]
    target_torque_knm: Optional[float]
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "shaft_type": self.shaft_type,
            "shaft_diameter_mm": self.shaft_diameter_mm,
            "helix_configuration": self.helix_configuration,
            "helix_diameters_mm": self.helix_diameters_mm,
            "working_capacity_kn": self.working_capacity_kn,
            "minimum_depth_m": self.minimum_depth_m,
            "target_torque_knm": self.target_torque_knm,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_screw_pier_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SCREW PIER",
        "HELICAL PILE",
        "SCREW PILE",
        "HELICAL ANCHOR",
        "GROUND SCREW",
        "CHANCE PILE",
        "TORQUE PIER",
        "HELICAL SCREW PILE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Shaft type
    if "SQUARE" in upper or "RCS" in upper or "SOLID" in upper:
        shaft_type = "SOLID_SQUARE_SHAFT"
    else:
        shaft_type = "PIPE_SHAFT_CHS"

    # Shaft diameter (e.g. "89MM CHS", "76MM SHAFT", "114MM", "89 DIA", "45MM SQUARE")
    s_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:SHAFT|CHS|PIPE|SQUARE)?", upper)
    dia_match = re.search(r"(?:DIA|Ø)\s*(\d{2,3})", upper)
    if s_match:
        shaft_dia = float(s_match.group(1))
    elif dia_match:
        shaft_dia = float(dia_match.group(1))
    else:
        shaft_dia = 89.0 if shaft_type == "PIPE_SHAFT_CHS" else 45.0

    # Helix configuration & blade diameters (e.g. "250/300/350 HELIX", "250/300 DOUBLE HELIX", "300MM SINGLE HELIX")
    h_multi = re.search(r"\b(\d{3}(?:[\/\-]\d{3})+)\s*(?:MM)?\s*(?:HELIX|HELICES|BLADES)?", upper)
    if h_multi:
        parts = re.split(r"[\/\-]", h_multi.group(1))
        helix_diameters = [float(p) for p in parts]
    else:
        single_h = re.search(r"\b(\d{3})\s*MM\s*(?:[A-Z\s]{0,10}?)\s*(?:HELIX|BLADE)", upper)
        if single_h:
            helix_diameters = [float(single_h.group(1))]
        elif "SINGLE" in upper:
            helix_diameters = [300.0]
        else:
            helix_diameters = [250.0, 300.0]

    if "SINGLE" in upper or len(helix_diameters) == 1:
        helix_config = "SINGLE_HELIX"
    elif "TRIPLE" in upper or len(helix_diameters) >= 3:
        helix_config = "TRIPLE_HELIX"
    else:
        helix_config = "DOUBLE_HELIX"

    # Working capacity (e.g. "150 KN", "250KN CAPACITY", "200 KN SWL")
    cap_match = re.search(r"\b(\d{2,3})\s*KN\b", upper)
    capacity = float(cap_match.group(1)) if cap_match else 150.0

    # Minimum depth (e.g. "6.0M DEPTH", "MIN 4.5M", "6M EMBEDMENT")
    depth_match = re.search(r"(?:MIN\s*)?(\d(?:\.\d)?)\s*M\s*(?:DEPTH|DEEP|EMBEDMENT)", upper)
    depth = float(depth_match.group(1)) if depth_match else None

    # Target torque (e.g. "15 KNM TORQUE", "12KNM", "20 KN.M")
    torque_match = re.search(r"\b(\d{1,2})\s*(?:KNM|KN\.M)\b", upper)
    torque = float(torque_match.group(1)) if torque_match else None

    return {
        "raw_text": clean,
        "shaft_type": shaft_type,
        "shaft_diameter_mm": shaft_dia,
        "helix_configuration": helix_config,
        "helix_diameters_mm": helix_diameters,
        "working_capacity_kn": capacity,
        "minimum_depth_m": depth,
        "target_torque_knm": torque,
    }


def evaluate_screw_pier_helical_anchor_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[ScrewPierCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_screw_pier_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_shp_{i+1:03d}"
        cand = ScrewPierCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            shaft_type=parsed["shaft_type"],
            shaft_diameter_mm=parsed["shaft_diameter_mm"],
            helix_configuration=parsed["helix_configuration"],
            helix_diameters_mm=parsed["helix_diameters_mm"],
            working_capacity_kn=parsed["working_capacity_kn"],
            minimum_depth_m=parsed["minimum_depth_m"],
            target_torque_knm=parsed["target_torque_knm"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
