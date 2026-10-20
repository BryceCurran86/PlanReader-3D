"""Source Structural Timber Glulam Beam Moment Connection & Concealed Knife Plate Shadow Authority.

Extracts candidate mass timber glulam beam dimensions, concealed knife/flitch plates,
tight-fit dowel pins, and moment connection geometry from structural drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class GlulamConnectionCandidate:
    candidate_id: str
    sheet_id: str
    connection_type: str
    timber_grade: Optional[str]
    timber_width_mm: Optional[float]
    timber_depth_mm: Optional[float]
    knife_plate_thickness_mm: Optional[float]
    dowel_diameter_mm: Optional[float]
    dowel_count: Optional[int]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "connection_type": self.connection_type,
            "timber_grade": self.timber_grade,
            "timber_width_mm": self.timber_width_mm,
            "timber_depth_mm": self.timber_depth_mm,
            "knife_plate_thickness_mm": self.knife_plate_thickness_mm,
            "dowel_diameter_mm": self.dowel_diameter_mm,
            "dowel_count": self.dowel_count,
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


def parse_glulam_connection_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "GLULAM",
        "KNIFE PLATE",
        "FLITCH PLATE",
        "SLOTTED TIMBER",
        "DOWEL PIN",
        "MASS TIMBER",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Connection type
    if "DOUBLE" in upper and ("FLITCH" in upper or "KNIFE" in upper):
        connection_type = "DOUBLE_INTERNAL_FLITCH"
    elif "MOMENT SPLICE" in upper or "SPLICE" in upper:
        connection_type = "MOMENT_SPLICE"
    elif "PINNED" in upper:
        connection_type = "BEAM_TO_COLUMN_PINNED"
    else:
        connection_type = "CONCEALED_KNIFE_PLATE"

    # Timber grade (e.g. GL18, GL17, GL13, GL28h)
    grade_match = re.search(r"\b(GL\d{1,2}[A-Za-z]?)\b", upper)
    timber_grade = grade_match.group(1).upper() if grade_match else None

    # Timber section W x D (e.g. 200x600, 150X450)
    dim_match = re.search(r"(\d{2,3})\s*(?:W|WIDTH)?\s*[xX]\s*(\d{2,4})\s*(?:D|DEPTH)?", clean)
    timber_width_mm = float(dim_match.group(1)) if dim_match else None
    timber_depth_mm = float(dim_match.group(2)) if dim_match else None

    # Knife plate thickness (e.g. "16MM KNIFE PLATE", "12MM FLITCH", "12MM STEEL PL", "16MM PL")
    plate_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:STEEL\s*)?(?:KNIFE|FLITCH|INTERNAL|PLATE|PL)\b", upper)
    knife_plate_thickness_mm = float(plate_match.group(1)) if plate_match else None

    # Dowel diameter (e.g. "12MM DOWEL PINS", "16MM DOWELS")
    dowel_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:DIA|Ø)?\s*(?:DOWEL|PIN)", upper)
    dowel_diameter_mm = float(dowel_match.group(1)) if dowel_match else None

    # Dowel count (e.g. "8 DOWELS", "12 X DOWEL PINS")
    count_match = re.search(r"\b(\d{1,2})\s*(?:X\s*)?(?:DOWELS?|PINS?)\b", upper)
    dowel_count = int(count_match.group(1)) if count_match else None

    return {
        "raw_text": clean,
        "connection_type": connection_type,
        "timber_grade": timber_grade,
        "timber_width_mm": timber_width_mm,
        "timber_depth_mm": timber_depth_mm,
        "knife_plate_thickness_mm": knife_plate_thickness_mm,
        "dowel_diameter_mm": dowel_diameter_mm,
        "dowel_count": dowel_count,
    }


def evaluate_glulam_moment_knife_plate_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[GlulamConnectionCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_glulam_connection_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_gkc_{i+1:03d}"
        cand = GlulamConnectionCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            connection_type=parsed["connection_type"],
            timber_grade=parsed["timber_grade"],
            timber_width_mm=parsed["timber_width_mm"],
            timber_depth_mm=parsed["timber_depth_mm"],
            knife_plate_thickness_mm=parsed["knife_plate_thickness_mm"],
            dowel_diameter_mm=parsed["dowel_diameter_mm"],
            dowel_count=parsed["dowel_count"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
