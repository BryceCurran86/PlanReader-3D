"""Source Cast-In Concrete Starter Bar Dowel Box & Pull-Out Rebend Shadow Authority.

Extracts candidate starter bar rebend boxes, pull-out continuity strips, bar diameters,
spacings, casing widths, and joint layout alignments from structural concrete drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class StarterBarRebendCandidate:
    candidate_id: str
    sheet_id: str
    row_configuration: str
    bar_diameter_mm: float
    bar_spacing_mm: float
    casing_width_mm: float
    pull_out_lap_length_mm: float
    joint_location: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "row_configuration": self.row_configuration,
            "bar_diameter_mm": self.bar_diameter_mm,
            "bar_spacing_mm": self.bar_spacing_mm,
            "casing_width_mm": self.casing_width_mm,
            "pull_out_lap_length_mm": self.pull_out_lap_length_mm,
            "joint_location": self.joint_location,
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


def parse_starter_bar_rebend_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "STARTER BAR BOX",
        "REBEND BOX",
        "PULL-OUT BAR",
        "PULL OUT BAR",
        "DOWEL BOX",
        "REIDBOX",
        "EAZISTRIP",
        "BARTEC BOX",
        "CONTINUITY STRIP BOX",
        "STARTER BOX",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Row configuration
    if "DOUBLE" in upper or "2 ROW" in upper or "2-ROW" in upper:
        row_config = "DOUBLE_ROW"
    else:
        row_config = "SINGLE_ROW"

    # Bar diameter (e.g. "N12", "N16", "12MM BAR", "16MM")
    bar_dia = None
    bar_match = re.search(r"\b[NHDY](\d{2})\b", upper)
    mm_match = re.search(r"\b(\d{2})\s*MM\s*(?:BAR|REBAR|ROD)?", upper)
    if bar_match:
        bar_dia = float(bar_match.group(1))
    elif mm_match:
        bar_dia = float(mm_match.group(1))
    else:
        bar_dia = 12.0

    # Bar spacing (e.g. "@ 150 CTS", "@ 200 C/C", "150 CTS", "@ 200MM")
    space_match = re.search(r"(?:@|\bAT\b)?\s*(\d{3})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS|SPACING)", upper)
    bar_spacing = float(space_match.group(1)) if space_match else 200.0

    # Casing width (e.g. "150MM WIDE CASING", "100MM BOX", "170MM CASING")
    case_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:WIDE\s*)?(?:CASING|BOX|WIDTH)", upper)
    casing_width = float(case_match.group(1)) if case_match else (150.0 if row_config == "DOUBLE_ROW" else 100.0)

    # Pull out lap length (e.g. "500MM LAP", "600MM PULL OUT", "500 LAP")
    lap_match = re.search(r"\b(\d{3})\s*MM?\s*(?:LAP|PULL|DEVELOPMENT|PROJECTION)", upper)
    lap_len = float(lap_match.group(1)) if lap_match else 500.0

    # Joint location
    if "SLAB TO WALL" in upper or "SLAB-TO-WALL" in upper:
        location = "SLAB_TO_WALL"
    elif "WALL TO SLAB" in upper or "WALL-TO-SLAB" in upper:
        location = "WALL_TO_SLAB"
    elif "WALL TO WALL" in upper or "WALL-TO-WALL" in upper:
        location = "WALL_TO_WALL"
    else:
        location = "SLAB_TO_WALL"

    return {
        "raw_text": clean,
        "row_configuration": row_config,
        "bar_diameter_mm": bar_dia,
        "bar_spacing_mm": bar_spacing,
        "casing_width_mm": casing_width,
        "pull_out_lap_length_mm": lap_len,
        "joint_location": location,
    }


def evaluate_starter_bar_rebend_box_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[StarterBarRebendCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_starter_bar_rebend_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_sbb_{i+1:03d}"
        cand = StarterBarRebendCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            row_configuration=parsed["row_configuration"],
            bar_diameter_mm=parsed["bar_diameter_mm"],
            bar_spacing_mm=parsed["bar_spacing_mm"],
            casing_width_mm=parsed["casing_width_mm"],
            pull_out_lap_length_mm=parsed["pull_out_lap_length_mm"],
            joint_location=parsed["joint_location"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
