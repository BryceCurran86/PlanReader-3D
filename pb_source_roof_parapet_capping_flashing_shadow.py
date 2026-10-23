"""Source Roof Parapet Capping & Standing Seam Flashing Shadow Authority.

Extracts candidate parapet metal cappings, standing seam flashings, counter-flashings,
apron flashings, material gauges, slopes, and linear alignments from architectural roof plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class RoofFlashingCandidate:
    candidate_id: str
    sheet_id: str
    flashing_type: str
    material: str
    thickness_mm: Optional[float]
    girth_or_width_mm: Optional[float]
    fall_slope_pct: Optional[float]
    fixing_method: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "flashing_type": self.flashing_type,
            "material": self.material,
            "thickness_mm": self.thickness_mm,
            "girth_or_width_mm": self.girth_or_width_mm,
            "fall_slope_pct": self.fall_slope_pct,
            "fixing_method": self.fixing_method,
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


def parse_roof_flashing_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "PARAPET CAPPING",
        "METAL CAPPING",
        "STANDING SEAM FLASHING",
        "APRON FLASHING",
        "COUNTER FLASHING",
        "PARAPET FLASHING",
        "ROOF CAPPING",
        "DRIP EDGE FLASHING",
        "PARAPET CAP",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Flashing type
    if "STANDING SEAM" in upper:
        flashing_type = "STANDING_SEAM_FLASHING"
    elif "COUNTER" in upper:
        flashing_type = "COUNTER_FLASHING"
    elif "APRON" in upper:
        flashing_type = "APRON_FLASHING"
    elif "DRIP" in upper:
        flashing_type = "DRIP_EDGE"
    else:
        flashing_type = "PARAPET_CAPPING"

    # Material
    if "ZINC" in upper or "VMZINC" in upper or "RHEINZINK" in upper:
        material = "ZINC"
    elif "ALUMINIUM" in upper or "ALUMINUM" in upper:
        material = "ALUMINIUM"
    elif "COPPER" in upper:
        material = "COPPER"
    elif "STAINLESS" in upper:
        material = "STAINLESS_STEEL"
    else:
        material = "COLORBOND_STEEL"

    # Thickness / BMT (e.g. "0.55MM", "0.7MM", "1.2MM BMT")
    thk_match = re.search(r"\b(0\.\d{1,2}|1\.\d{1,2})\s*MM\b", upper)
    thickness_mm = float(thk_match.group(1)) if thk_match else (0.55 if material == "COLORBOND_STEEL" else 0.7)

    # Girth / Width (e.g. "450MM GIRTH", "300MM WIDE CAPPING", "400MM PARAPET")
    width_match = re.search(r"\b(\d{3,4})\s*MM\s*(?:GIRTH|WIDE|WIDTH|CAPPING|CAP)?", upper)
    girth_or_width_mm = float(width_match.group(1)) if width_match else 400.0

    # Fall / Slope (e.g. "FALL 1:20", "FALL 3%", "FALL 5°")
    slope_pct = None
    slope_match = re.search(r"FALL\s*(?:OF\s*)?(\d{1,2})\s*%", upper)
    ratio_match = re.search(r"FALL\s*1:(\d{1,2})", upper)
    if slope_pct is not None:
        pass
    elif slope_match:
        slope_pct = float(slope_match.group(1))
    elif ratio_match:
        slope_pct = round(100.0 / float(ratio_match.group(1)), 1)
    else:
        slope_pct = 3.0  # standard minimum 1:33 / ~3% fall inward

    # Fixing method
    if "CLEAT" in upper:
        fixing_method = "CONTINUOUS_CLEAT"
    elif "RIVET" in upper:
        fixing_method = "POP_RIVETED"
    else:
        fixing_method = "SCREW_FIXED"

    return {
        "raw_text": clean,
        "flashing_type": flashing_type,
        "material": material,
        "thickness_mm": thickness_mm,
        "girth_or_width_mm": girth_or_width_mm,
        "fall_slope_pct": slope_pct,
        "fixing_method": fixing_method,
    }


def evaluate_roof_parapet_capping_flashing_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[RoofFlashingCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_roof_flashing_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_rcf_{i+1:03d}"
        cand = RoofFlashingCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            flashing_type=parsed["flashing_type"],
            material=parsed["material"],
            thickness_mm=parsed["thickness_mm"],
            girth_or_width_mm=parsed["girth_or_width_mm"],
            fall_slope_pct=parsed["fall_slope_pct"],
            fixing_method=parsed["fixing_method"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
