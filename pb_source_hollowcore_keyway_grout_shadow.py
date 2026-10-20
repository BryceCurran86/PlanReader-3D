"""Source Precast Concrete Hollowcore Floor Slab Keyway Joint & Tie Grout Shadow Authority.

Extracts candidate hollowcore plank layout, longitudinal shear keyways,
tie reinforcement, and grout fill geometry from structural floor plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class HollowcoreKeywayCandidate:
    candidate_id: str
    sheet_id: str
    slab_depth_mm: Optional[float]
    plank_width_mm: float
    grout_strength_mpa: Optional[float]
    tie_bar_spec: Optional[str]
    has_structural_topping: bool
    topping_thickness_mm: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "slab_depth_mm": self.slab_depth_mm,
            "plank_width_mm": self.plank_width_mm,
            "grout_strength_mpa": self.grout_strength_mpa,
            "tie_bar_spec": self.tie_bar_spec,
            "has_structural_topping": self.has_structural_topping,
            "topping_thickness_mm": self.topping_thickness_mm,
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


def parse_hollowcore_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "HOLLOWCORE",
        "HOLLOW CORE",
        "PRECAST SLAB KEYWAY",
        "SHEAR KEY GROUT",
        "HOLLOWCORE TIE",
        "LONGITUDINAL KEYWAY",
        "HOLLOWCORE PLANK",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Slab depth (e.g. "200MM HOLLOWCORE" or "250 THICK HOLLOW CORE")
    depth_match = re.search(r"\b(150|200|250|300|350|400)\s*MM\b", upper)
    depth_match_alt = re.search(r"\b(150|200|250|300|350|400)\s*(?:THICK|DEEP)\b", upper)
    slab_depth_mm = None
    if depth_match:
        slab_depth_mm = float(depth_match.group(1))
    elif depth_match_alt:
        slab_depth_mm = float(depth_match_alt.group(1))

    # Plank width (default 1200mm)
    width_match = re.search(r"(\d{3,4})\s*MM\s*WIDE", upper)
    plank_width_mm = float(width_match.group(1)) if width_match else 1200.0

    # Grout strength (e.g. "40 MPA GROUT" or "50MPA")
    grout_match = re.search(r"(\d{2})\s*MPA", upper)
    grout_strength_mpa = float(grout_match.group(1)) if grout_match else 40.0

    # Tie bar (e.g. N12, N16, R10)
    tie_match = re.search(r"\b([NRnr]\d{1,2})\b", clean)
    tie_bar_spec = tie_match.group(1).upper() if tie_match else None

    # Structural topping
    has_structural_topping = "TOPPING" in upper or "SCREED" in upper
    topping_match = re.search(r"(\d{2,3})\s*MM\s*(?:TOPPING|SCREED)", upper)
    topping_thickness_mm = float(topping_match.group(1)) if topping_match else (75.0 if has_structural_topping else None)

    return {
        "raw_text": clean,
        "slab_depth_mm": slab_depth_mm,
        "plank_width_mm": plank_width_mm,
        "grout_strength_mpa": grout_strength_mpa,
        "tie_bar_spec": tie_bar_spec,
        "has_structural_topping": has_structural_topping,
        "topping_thickness_mm": topping_thickness_mm,
    }


def evaluate_hollowcore_keyway_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[HollowcoreKeywayCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_hollowcore_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_hck_{i+1:03d}"
        cand = HollowcoreKeywayCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            slab_depth_mm=parsed["slab_depth_mm"],
            plank_width_mm=parsed["plank_width_mm"],
            grout_strength_mpa=parsed["grout_strength_mpa"],
            tie_bar_spec=parsed["tie_bar_spec"],
            has_structural_topping=parsed["has_structural_topping"],
            topping_thickness_mm=parsed["topping_thickness_mm"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
