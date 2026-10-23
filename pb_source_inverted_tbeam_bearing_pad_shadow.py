"""Source Precast Concrete Inverted T-Beam & Ledger Bearing Pad Shadow Authority.

Extracts candidate precast inverted T-beams, L-ledger beams, ledge dimensions,
and elastomeric neoprene bearing pad geometry from structural framing plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class InvertedTBeamCandidate:
    candidate_id: str
    sheet_id: str
    beam_type: str
    web_width_mm: Optional[float]
    overall_depth_mm: Optional[float]
    ledge_width_mm: Optional[float]
    bearing_pad_material: str
    bearing_pad_thickness_mm: Optional[float]
    durometer_hardness: Optional[int]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "beam_type": self.beam_type,
            "web_width_mm": self.web_width_mm,
            "overall_depth_mm": self.overall_depth_mm,
            "ledge_width_mm": self.ledge_width_mm,
            "bearing_pad_material": self.bearing_pad_material,
            "bearing_pad_thickness_mm": self.bearing_pad_thickness_mm,
            "durometer_hardness": self.durometer_hardness,
            "points": self.points,
            "length_pt": round(self.length_pt, 2),
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def snap_polyline(points: List[Tuple[float, float]], snap_tol: float = SNAP_TOLERANCE_PT) -> List[Tuple[float, float]]:
    if not points:
        return []
    snapped = [snap_point(points[0], snap_tol)]
    for pt in points[1:]:
        s_pt = snap_point(pt, snap_tol)
        if s_pt != snapped[-1]:
            snapped.append(s_pt)
    return snapped


def calculate_polyline_length(points: List[Tuple[float, float]]) -> float:
    if len(points) < 2:
        return 0.0
    length = 0.0
    for i in range(len(points) - 1):
        dx = points[i + 1][0] - points[i][0]
        dy = points[i + 1][1] - points[i][1]
        length += math.hypot(dx, dy)
    return length


def parse_inverted_tbeam_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "INVERTED T-BEAM",
        "INVERTED TEE",
        "INVERTED T BEAM",
        "LEDGER BEAM",
        "LEDGE BEAM",
        "BEARING PAD",
        "NEOPRENE BEARING STRIP",
        "ELASTOMERIC BEARING",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Beam type
    if "LEDGER" in upper or "L-SHAPED" in upper or "L BEAM" in upper:
        beam_type = "L_SHAPED_LEDGER_BEAM"
    elif "INVERTED" in upper or "TEE" in upper or "T-BEAM" in upper or "T BEAM" in upper:
        beam_type = "INVERTED_T_BEAM"
    else:
        beam_type = "PRECAST_BEAM"

    # Dimensions W x D (e.g. "600W X 900D" or "500 x 800")
    dim_match = re.search(r"(\d{3,4})\s*(?:W|MM\s*W|WIDE)?\s*[xX]\s*(\d{3,4})\s*(?:D|MM\s*D|DEEP)?", clean)
    web_width_mm = float(dim_match.group(1)) if dim_match else None
    overall_depth_mm = float(dim_match.group(2)) if dim_match else None

    # Ledge width (e.g. "150MM LEDGE" or "LEDGE: 200MM")
    ledge_match = re.search(r"(?:(\d{2,3})\s*MM\s*LEDGE|LEDGE[:\s]*(\d{2,3})\s*MM)", upper)
    ledge_width_mm = None
    if ledge_match:
        val = ledge_match.group(1) or ledge_match.group(2)
        ledge_width_mm = float(val)

    # Bearing pad material
    if "PTFE" in upper or "TEFLON" in upper:
        bearing_pad_material = "PTFE_SLIDE_PAD"
    elif "REINFORCED" in upper:
        bearing_pad_material = "REINFORCED_ELASTOMERIC"
    else:
        bearing_pad_material = "CHLOROPRENE_NEOPRENE"

    # Bearing pad thickness (e.g. "10MM ELASTOMERIC" or "12MM BEARING PAD")
    thick_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:BEARING|PAD|STRIP|ELASTOMERIC|NEOPRENE)\b", upper)
    bearing_pad_thickness_mm = float(thick_match.group(1)) if thick_match else None

    # Durometer (e.g. "60 DUROMETER" or "70 DURO")
    duro_match = re.search(r"\b(\d{2})\s*(?:DURO|DUROMETER)\b", upper)
    durometer_hardness = int(duro_match.group(1)) if duro_match else 60

    return {
        "raw_text": clean,
        "beam_type": beam_type,
        "web_width_mm": web_width_mm,
        "overall_depth_mm": overall_depth_mm,
        "ledge_width_mm": ledge_width_mm,
        "bearing_pad_material": bearing_pad_material,
        "bearing_pad_thickness_mm": bearing_pad_thickness_mm,
        "durometer_hardness": durometer_hardness,
    }


def evaluate_inverted_tbeam_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[InvertedTBeamCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_inverted_tbeam_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_itb_{i+1:03d}"
        cand = InvertedTBeamCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            beam_type=parsed["beam_type"],
            web_width_mm=parsed["web_width_mm"],
            overall_depth_mm=parsed["overall_depth_mm"],
            ledge_width_mm=parsed["ledge_width_mm"],
            bearing_pad_material=parsed["bearing_pad_material"],
            bearing_pad_thickness_mm=parsed["bearing_pad_thickness_mm"],
            durometer_hardness=parsed["durometer_hardness"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
