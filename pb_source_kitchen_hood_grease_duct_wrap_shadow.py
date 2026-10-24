"""Source Commercial Kitchen Exhaust Hood Grease Duct Fire Wrap Shadow Authority.

Extracts candidate kitchen exhaust grease ducts, fire-rated duct wrap blankets,
welded duct gauges, cleanout doors, and alignments from mechanical/fire plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class GreaseDuctWrapCandidate:
    candidate_id: str
    sheet_id: str
    duct_material: str
    wrap_material: str
    fire_rating_hours: float
    wrap_thickness_mm: Optional[float]
    duct_size_description: str
    cleanout_doors: bool
    slope_pct: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "duct_material": self.duct_material,
            "wrap_material": self.wrap_material,
            "fire_rating_hours": self.fire_rating_hours,
            "wrap_thickness_mm": self.wrap_thickness_mm,
            "duct_size_description": self.duct_size_description,
            "cleanout_doors": self.cleanout_doors,
            "slope_pct": self.slope_pct,
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


def parse_grease_duct_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "GREASE DUCT",
        "KITCHEN EXHAUST DUCT",
        "KITCHEN HOOD DUCT",
        "GREASE EXHAUST",
        "FIRE WRAP DUCT",
        "DUCT FIRE BLANKET",
        "FIREMASTER WRAP",
        "GREASE HOOD EXHAUST",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Duct material
    if "STAINLESS" in upper or "SS" in upper:
        duct_material = "WELDED_STAINLESS_STEEL"
    else:
        duct_material = "WELDED_MILD_STEEL"

    # Wrap material
    if "CALCIUM SILICATE" in upper or "CAL-SIL" in upper:
        wrap_material = "CALCIUM_SILICATE_BOARD"
    elif "BIO-SOLUBLE" in upper or "BIO SOLUBLE" in upper:
        wrap_material = "BIO_SOLUBLE_WOOL"
    else:
        wrap_material = "CERAMIC_FIBER_BLANKET"

    # Fire rating in hours (e.g. "2-HR", "2 HOUR", "FRL -/120/120")
    hr_match = re.search(r"\b(\d{1,2})\s*(?:-|–|\s*)?(?:HR|HOUR)\b", upper)
    frl_match = re.search(r"FRL\s*-?/?(\d{2,3})", upper)
    if hr_match:
        fire_rating_hours = float(hr_match.group(1))
    elif frl_match:
        mins = float(frl_match.group(1))
        fire_rating_hours = round(mins / 60.0, 1)
    else:
        fire_rating_hours = 2.0

    # Wrap thickness (e.g. "38MM WRAP", "50MM BLANKET", "2X38MM")
    thick_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:THICK|WRAP|BLANKET|LAYER)?", upper)
    wrap_thick = float(thick_match.group(1)) if thick_match else 38.0

    # Duct dimensions (e.g. "600X450", "500 DIA", "Ø450")
    dim_match = re.search(r"\b(\d{3,4}\s*[X*×]\s*\d{3,4})\b", upper)
    dia_match = re.search(r"(?:DIA|Ø)\s*(\d{3,4})", upper)
    if dim_match:
        duct_size = dim_match.group(1).replace(" ", "")
    elif dia_match:
        duct_size = f"DIA_{dia_match.group(1)}"
    else:
        duct_size = "STANDARD_GREASE_DUCT"

    # Cleanout doors
    cleanout = any(k in upper for k in ["CLEANOUT", "ACCESS DOOR", "ACCESS PANEL", "INSPECTION HATCH"])

    # Slope
    slope_match = re.search(r"SLOPE\s*(?:OF\s*)?(\d{1,2})\s*%", upper)
    ratio_slope = re.search(r"SLOPE\s*1:(\d{2})", upper)
    if slope_match:
        slope_pct = float(slope_match.group(1))
    elif ratio_slope:
        slope_pct = round(100.0 / float(ratio_slope.group(1)), 1)
    else:
        slope_pct = 2.0  # 1:50 standard slope toward hood

    return {
        "raw_text": clean,
        "duct_material": duct_material,
        "wrap_material": wrap_material,
        "fire_rating_hours": fire_rating_hours,
        "wrap_thickness_mm": wrap_thick,
        "duct_size_description": duct_size,
        "cleanout_doors": cleanout,
        "slope_pct": slope_pct,
    }


def evaluate_kitchen_hood_grease_duct_wrap_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[GreaseDuctWrapCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_grease_duct_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_gdw_{i+1:03d}"
        cand = GreaseDuctWrapCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            duct_material=parsed["duct_material"],
            wrap_material=parsed["wrap_material"],
            fire_rating_hours=parsed["fire_rating_hours"],
            wrap_thickness_mm=parsed["wrap_thickness_mm"],
            duct_size_description=parsed["duct_size_description"],
            cleanout_doors=parsed["cleanout_doors"],
            slope_pct=parsed["slope_pct"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
