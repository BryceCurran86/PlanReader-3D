"""Source Structural Concrete Corbels & Precast Beam Bearing Nibs Shadow Authority.

Extracts candidate concrete corbels, column brackets, dapped beam nibs,
reinforcement ties, horizontal stirrups, and bearing pads from structural drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class ConcreteCorbelCandidate:
    candidate_id: str
    sheet_id: str
    corbel_configuration: str
    projection_length_mm: Optional[float]
    root_depth_mm: Optional[float]
    width_mm: Optional[float]
    primary_tie_reinforcement: str
    horizontal_stirrups_description: str
    bearing_pad_type: str
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "corbel_configuration": self.corbel_configuration,
            "projection_length_mm": self.projection_length_mm,
            "root_depth_mm": self.root_depth_mm,
            "width_mm": self.width_mm,
            "primary_tie_reinforcement": self.primary_tie_reinforcement,
            "horizontal_stirrups_description": self.horizontal_stirrups_description,
            "bearing_pad_type": self.bearing_pad_type,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_concrete_corbel_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CONCRETE CORBEL",
        "COLUMN CORBEL",
        "BEAM NIB",
        "DAPPED END",
        "WALL BRACKET",
        "BEARING NIB",
        "PRECAST CORBEL",
        "PRECAST BEARING NIB",
        "CORBEL DETAIL",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Corbel configuration
    if "DAPPED" in upper or "BEAM NIB" in upper or "BEARING NIB" in upper:
        config = "DAPPED_BEAM_NIB"
    elif "WALL" in upper or "BRACKET" in upper:
        config = "WALL_CORBEL"
    else:
        config = "COLUMN_CORBEL"

    # Projection length (e.g. "300MM PROJECTION", "350 PROJ", "300MM OUTSTAND")
    proj_match = re.search(r"\b(\d{3})\s*MM?\s*(?:PROJECTION|PROJ|OUTSTAND|LONG|LENGTH)\b", upper)
    proj_len = float(proj_match.group(1)) if proj_match else 300.0

    # Root depth (e.g. "450MM DEEP", "500MM ROOT DEPTH", "400 DEPTH")
    depth_match = re.search(r"\b(\d{3})\s*MM?\s*(?:DEEP|DEPTH|ROOT)\b", upper)
    root_depth = float(depth_match.group(1)) if depth_match else 450.0

    # Width (e.g. "350MM WIDE", "300 WIDTH")
    width_match = re.search(r"\b(\d{3})\s*MM?\s*(?:WIDE|WIDTH)\b", upper)
    width = float(width_match.group(1)) if width_match else 350.0

    # Primary tie reinforcement (e.g. "3-N24", "4-N20", "3-HD25", "4-Y25", "3N24")
    rebar_match = re.search(r"\b(\d\s*[-–]?\s*[NHDY]\s*\d{2})\b", upper)
    rebar = rebar_match.group(1).replace(" ", "") if rebar_match else "3-N24"

    # Horizontal stirrups (e.g. "N10 @ 100", "N10-100 CTS", "N12 STIRRUPS @ 120")
    stirrup_match = re.search(r"\b([NHDY]\s*\d{2}(?:\s*STIRRUPS)?\s*(?:@|AT|-)\s*\d{2,3}(?:\s*CTS)?)\b", upper)
    stirrups = stirrup_match.group(1) if stirrup_match else "N10 @ 100 CTS"

    # Bearing pad type
    if "STEEL" in upper or "PLATE" in upper:
        bearing_pad = "STEEL_BEARING_PLATE"
    elif "PTFE" in upper or "SLIDING" in upper:
        bearing_pad = "PTFE_SLIDING_PAD"
    else:
        bearing_pad = "ELASTOMERIC_PAD"

    return {
        "raw_text": clean,
        "corbel_configuration": config,
        "projection_length_mm": proj_len,
        "root_depth_mm": root_depth,
        "width_mm": width,
        "primary_tie_reinforcement": rebar,
        "horizontal_stirrups_description": stirrups,
        "bearing_pad_type": bearing_pad,
    }


def evaluate_concrete_corbel_bearing_nib_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[ConcreteCorbelCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_concrete_corbel_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_cbn_{i+1:03d}"
        cand = ConcreteCorbelCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            corbel_configuration=parsed["corbel_configuration"],
            projection_length_mm=parsed["projection_length_mm"],
            root_depth_mm=parsed["root_depth_mm"],
            width_mm=parsed["width_mm"],
            primary_tie_reinforcement=parsed["primary_tie_reinforcement"],
            horizontal_stirrups_description=parsed["horizontal_stirrups_description"],
            bearing_pad_type=parsed["bearing_pad_type"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
