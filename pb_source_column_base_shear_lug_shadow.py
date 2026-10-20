"""Source Structural Steel Column Base Grout Key & Shear Lug Shadow Authority.

Extracts candidate column baseplate welded shear lugs, foundation pedestal grout key boxouts,
projection depths, and non-shrink grout specifications from structural steel details.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class ColumnBaseShearLugCandidate:
    candidate_id: str
    sheet_id: str
    lug_type: str
    lug_section: Optional[str]
    lug_projection_mm: Optional[float]
    grout_key_size_mm: Optional[str]
    grout_strength_mpa: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "lug_type": self.lug_type,
            "lug_section": self.lug_section,
            "lug_projection_mm": self.lug_projection_mm,
            "grout_key_size_mm": self.grout_key_size_mm,
            "grout_strength_mpa": self.grout_strength_mpa,
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


def parse_shear_lug_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SHEAR LUG",
        "GROUT KEY",
        "BASEPLATE SHEAR",
        "BASE PLATE SHEAR",
        "SHEAR KEY RECESS",
        "SHEAR KEY BOXOUT",
        "BASE PLATE LUG",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Lug type
    if "SHS" in upper or "RHS" in upper or "BOX" in upper:
        lug_type = "SHS_BOX_LUG"
    elif "UB" in upper or "UC" in upper:
        lug_type = "UB_SECTION_LUG"
    elif "ANGLE" in upper or bool(re.search(r"\bEA\b", upper)):
        lug_type = "DOUBLE_ANGLE_LUG"
    else:
        lug_type = "PLATE_SHEAR_LUG"

    # Lug section
    section = None
    shs_match = re.search(r"(\d{2,3}\s*[xX]\s*\d{2,3}(?:\s*[xX]\s*\d{1,2})?\s*(?:SHS|RHS|EA))", clean, re.IGNORECASE)
    ub_match = re.search(r"(\d{2,3}\s*(?:UB|UC)\s*\d{1,3})", clean, re.IGNORECASE)
    pl_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:THICK\s*)?PL(?:ATE)?\b", upper)

    if shs_match:
        section = shs_match.group(1).replace("X", "x").replace(" ", "")
    elif ub_match:
        section = ub_match.group(1).replace(" ", "").upper()
    elif pl_match:
        section = f"{pl_match.group(1)}MM PL"

    # Projection (e.g. "100MM PROJECTION" or "150MM PROJ")
    proj_match = re.search(r"(?:(?:PROJECTION|PROJ|DEPTH)[:\s]*(\d{2,3})\s*MM|(\d{2,3})\s*MM\s*(?:PROJECTION|PROJ|DEEP|INTO))", upper)
    lug_projection_mm = None
    if proj_match:
        val = proj_match.group(1) or proj_match.group(2)
        lug_projection_mm = float(val)

    # Grout key size (e.g. "IN 200X200 GROUT KEY" or "GROUT KEY: 250X250")
    key_match = re.search(r"(?:IN\s*)?(\d{2,4}\s*[xX]\s*\d{2,4})\s*(?:MM)?\s*GROUT\s*KEY", clean, re.IGNORECASE)
    key_match_alt = re.search(r"GROUT\s*KEY[:\s]*(\d{2,4}\s*[xX]\s*\d{2,4})", clean, re.IGNORECASE)
    grout_key_size_mm = None
    if key_match:
        grout_key_size_mm = key_match.group(1).replace(" ", "").upper()
    elif key_match_alt:
        grout_key_size_mm = key_match_alt.group(1).replace(" ", "").upper()

    # Grout strength (e.g. "60 MPA", "70MPA")
    grout_match = re.search(r"(\d{2})\s*MPA\b", upper)
    grout_strength_mpa = float(grout_match.group(1)) if grout_match else 60.0

    return {
        "raw_text": clean,
        "lug_type": lug_type,
        "lug_section": section,
        "lug_projection_mm": lug_projection_mm,
        "grout_key_size_mm": grout_key_size_mm,
        "grout_strength_mpa": grout_strength_mpa,
    }


def evaluate_column_base_shear_lug_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[ColumnBaseShearLugCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_shear_lug_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_csl_{i+1:03d}"
        cand = ColumnBaseShearLugCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            lug_type=parsed["lug_type"],
            lug_section=parsed["lug_section"],
            lug_projection_mm=parsed["lug_projection_mm"],
            grout_key_size_mm=parsed["grout_key_size_mm"],
            grout_strength_mpa=parsed["grout_strength_mpa"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
