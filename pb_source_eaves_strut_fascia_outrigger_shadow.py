"""Source Structural Steel Purlin Eaves Strut & Fascia Girt Outrigger Shadow Authority.

Extracts candidate eaves struts, fascia girts, cantilever outrigger brackets,
and eaves intersection framing geometry from structural drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class EavesStrutOutriggerCandidate:
    candidate_id: str
    sheet_id: str
    member_type: str
    section_profile: Optional[str]
    outrigger_spacing_mm: Optional[float]
    outrigger_length_mm: Optional[float]
    connection_type: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "member_type": self.member_type,
            "section_profile": self.section_profile,
            "outrigger_spacing_mm": self.outrigger_spacing_mm,
            "outrigger_length_mm": self.outrigger_length_mm,
            "connection_type": self.connection_type,
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


def parse_eaves_strut_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "EAVES STRUT",
        "EAVE STRUT",
        "FASCIA GIRT",
        "EAVES BEAM",
        "FASCIA OUTRIGGER",
        "EAVES PURLIN",
        "EAVE GUTTER OUTRIGGER",
        "EAVES TIE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Member type
    if "OUTRIGGER" in upper:
        member_type = "OUTRIGGER_BRACKET"
    elif "FASCIA GIRT" in upper:
        member_type = "FASCIA_GIRT"
    elif "EAVES BEAM" in upper:
        member_type = "EAVES_BEAM"
    else:
        member_type = "EAVES_STRUT"

    # Section profile
    profile = None
    cz_match = re.search(r"\b([CZcz]\d{5})\b", clean)
    rhs_match = re.search(r"(\d{2,3}\s*[xX]\s*\d{2,3}(?:\s*[xX]\s*\d{1,2})?\s*(?:RHS|SHS|EA))", clean, re.IGNORECASE)
    ub_match = re.search(r"(\d{2,3}\s*(?:PFC|UB|UC))", clean, re.IGNORECASE)

    if cz_match:
        profile = cz_match.group(1).upper()
    elif rhs_match:
        profile = rhs_match.group(1).replace("X", "x").replace(" ", "")
    elif ub_match:
        profile = ub_match.group(1).upper()

    # Outrigger spacing (e.g. "@ 1200 CTS" or "AT 1500MM CENTRES")
    spacing_match = re.search(r"(?:@|AT|\b)\s*(\d{3,4})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS)\b", upper)
    outrigger_spacing_mm = float(spacing_match.group(1)) if spacing_match else None

    # Outrigger length / projection (e.g. "600MM PROJECTION" or "PROJECTION: 450MM")
    proj_match = re.search(r"(?:(?:PROJECTION|LENGTH|CANTILEVER)[:\s]*(\d{3,4})\s*MM|(\d{3,4})\s*MM\s*(?:PROJECTION|CANTILEVER|OUTRIGGER))", upper)
    outrigger_length_mm = None
    if proj_match:
        val = proj_match.group(1) or proj_match.group(2)
        outrigger_length_mm = float(val)

    # Connection type
    if "STUB" in upper or "BOLTED" in upper:
        connection_type = "STUB_OUTRIGGER_BOLTED"
    elif "CLEAT" in upper:
        connection_type = "CLEATED_TO_RAFTER"
    else:
        connection_type = "STANDARD_CONNECTION"

    return {
        "raw_text": clean,
        "member_type": member_type,
        "section_profile": profile,
        "outrigger_spacing_mm": outrigger_spacing_mm,
        "outrigger_length_mm": outrigger_length_mm,
        "connection_type": connection_type,
    }


def evaluate_eaves_strut_outrigger_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[EavesStrutOutriggerCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_eaves_strut_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_eso_{i+1:03d}"
        cand = EavesStrutOutriggerCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            member_type=parsed["member_type"],
            section_profile=parsed["section_profile"],
            outrigger_spacing_mm=parsed["outrigger_spacing_mm"],
            outrigger_length_mm=parsed["outrigger_length_mm"],
            connection_type=parsed["connection_type"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
