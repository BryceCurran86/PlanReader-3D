"""Source Architectural Operable Acoustic Movable Wall Track & Stacking Pocket Shadow Authority.

Extracts candidate acoustic operable wall overhead tracks, stacking pockets,
acoustic ratings, and panel seal geometry from architectural interior plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class OperableWallCandidate:
    candidate_id: str
    sheet_id: str
    partition_type: str
    acoustic_rating_rw: Optional[str]
    height_mm: Optional[float]
    stacking_type: str
    seal_type: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "partition_type": self.partition_type,
            "acoustic_rating_rw": self.acoustic_rating_rw,
            "height_mm": self.height_mm,
            "stacking_type": self.stacking_type,
            "seal_type": self.seal_type,
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


def parse_operable_wall_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "OPERABLE WALL",
        "ACOUSTIC OPERABLE",
        "MOVABLE PARTITION",
        "OPERABLE PARTITION",
        "STACKING POCKET",
        "OVERHEAD TRACK",
        "STACKING BAY",
        "MOVABLE WALL",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Partition type
    if "GLASS" in upper:
        partition_type = "GLASS_MOVABLE_WALL"
    elif "ACCORDION" in upper:
        partition_type = "ACCORDION_PARTITION"
    else:
        partition_type = "ACOUSTIC_OPERABLE_WALL"

    # Acoustic rating (e.g. "Rw 50", "Rw 45", "STC 50")
    rw_match = re.search(r"\b(RW\s*\d{2}|STC\s*\d{2})\b", upper)
    acoustic_rating_rw = rw_match.group(1).upper() if rw_match else None

    # Height (e.g. "3200H", "3000MM HIGH", "2700 HEIGHT")
    height_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:H|HIGH|HEIGHT)\b", upper)
    height_mm = float(height_match.group(1)) if height_match else None

    # Stacking type
    if "REMOTE" in upper:
        stacking_type = "REMOTE_STACKING_BAY"
    elif "PERPENDICULAR" in upper or "90 DEG" in upper:
        stacking_type = "PERPENDICULAR_STACKING"
    else:
        stacking_type = "PARALLEL_STACKING_POCKET"

    # Seal type
    if "SWEEP" in upper:
        seal_type = "SWEEP_SEALS"
    elif "AUTO" in upper or "PRESSURE" in upper:
        seal_type = "AUTOMATIC_PRESSURE_SEAL"
    else:
        seal_type = "EXPANDING_MECHANICAL_SEAL"

    return {
        "raw_text": clean,
        "partition_type": partition_type,
        "acoustic_rating_rw": acoustic_rating_rw,
        "height_mm": height_mm,
        "stacking_type": stacking_type,
        "seal_type": seal_type,
    }


def evaluate_operable_wall_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[OperableWallCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_operable_wall_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_opw_{i+1:03d}"
        cand = OperableWallCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            partition_type=parsed["partition_type"],
            acoustic_rating_rw=parsed["acoustic_rating_rw"],
            height_mm=parsed["height_mm"],
            stacking_type=parsed["stacking_type"],
            seal_type=parsed["seal_type"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
