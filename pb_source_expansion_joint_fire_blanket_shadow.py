"""Source Architectural Expansion Joint Fire Barrier Blanket Shadow Authority.

Extracts candidate expansion/seismic joint fire barrier blankets, ceramic fiber mats,
fire resistance ratings, and joint alignment geometry from architectural/fire plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class FireBlanketCandidate:
    candidate_id: str
    sheet_id: str
    joint_type: str
    fire_rating_hours: Optional[float]
    joint_width_mm: Optional[float]
    barrier_material: str
    movement_capacity_pct: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "joint_type": self.joint_type,
            "fire_rating_hours": self.fire_rating_hours,
            "joint_width_mm": self.joint_width_mm,
            "barrier_material": self.barrier_material,
            "movement_capacity_pct": self.movement_capacity_pct,
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


def parse_fire_blanket_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "EXPANSION JOINT FIRE",
        "FIRE BLANKET",
        "FIRE BARRIER BLANKET",
        "SEISMIC JOINT FIRE",
        "CERAMIC FIBER FIRE",
        "CERAMIC FIBRE FIRE",
        "JOINT FIRE BARRIER",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Joint type
    if "WALL" in upper:
        joint_type = "WALL_EXPANSION_JOINT"
    elif "CEILING" in upper:
        joint_type = "CEILING_EXPANSION_JOINT"
    elif "ROOF" in upper:
        joint_type = "ROOF_EXPANSION_JOINT"
    else:
        joint_type = "FLOOR_EXPANSION_JOINT"

    # Fire rating in hours (e.g. "2-HR", "2-HOUR", "FRL -/120/120")
    hr_match = re.search(r"\b(\d{1,2})\s*(?:-|–|\s*)?(?:HR|HOUR)\b", upper)
    frl_match = re.search(r"FRL\s*-?/?(\d{2,3})", upper)
    fire_rating_hours = None
    if hr_match:
        fire_rating_hours = float(hr_match.group(1))
    elif frl_match:
        mins = float(frl_match.group(1))
        fire_rating_hours = round(mins / 60.0, 1)
    else:
        fire_rating_hours = 2.0

    # Joint width (e.g. "100MM EXPANSION JOINT", "50MM JOINT")
    width_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:EXPANSION|JOINT|GAP|SEISMIC|WIDTH)?", upper)
    joint_width_mm = float(width_match.group(1)) if width_match else None

    # Barrier material
    if "INTUMESCENT" in upper:
        barrier_material = "INTUMESCENT_FABRIC"
    elif "MINERAL" in upper:
        barrier_material = "MINERAL_WOOL_MAT"
    elif "GRAPHITE" in upper:
        barrier_material = "GRAPHITE_COMPOSITE"
    else:
        barrier_material = "CERAMIC_FIBRE_BLANKET"

    # Movement capacity (e.g. "+/- 50%" or "50% MOVEMENT")
    move_match = re.search(r"(?:\+\/-\s*|±\s*)?(\d{2})\s*%", upper)
    movement_capacity_pct = float(move_match.group(1)) if move_match else 50.0

    return {
        "raw_text": clean,
        "joint_type": joint_type,
        "fire_rating_hours": fire_rating_hours,
        "joint_width_mm": joint_width_mm,
        "barrier_material": barrier_material,
        "movement_capacity_pct": movement_capacity_pct,
    }


def evaluate_expansion_joint_fire_blanket_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[FireBlanketCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_fire_blanket_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_fbb_{i+1:03d}"
        cand = FireBlanketCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            joint_type=parsed["joint_type"],
            fire_rating_hours=parsed["fire_rating_hours"],
            joint_width_mm=parsed["joint_width_mm"],
            barrier_material=parsed["barrier_material"],
            movement_capacity_pct=parsed["movement_capacity_pct"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
