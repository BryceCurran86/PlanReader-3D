"""Source Industrial Sectional Overhead Door Counterweight & High-Lift Track Shadow Authority.

Extracts candidate industrial sectional overhead door tracks, lift configurations,
counterweight torsion assemblies, and jamb track guidelines from source plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class SectionalDoorTrackCandidate:
    candidate_id: str
    sheet_id: str
    lift_type: str
    door_width_mm: Optional[float]
    door_height_mm: Optional[float]
    lift_height_mm: Optional[float]
    track_profile: str
    counterweight_type: str
    track_points: List[Tuple[float, float]] = field(default_factory=list)
    track_length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "lift_type": self.lift_type,
            "door_width_mm": self.door_width_mm,
            "door_height_mm": self.door_height_mm,
            "lift_height_mm": self.lift_height_mm,
            "track_profile": self.track_profile,
            "counterweight_type": self.counterweight_type,
            "track_points": self.track_points,
            "track_length_pt": round(self.track_length_pt, 2),
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


def parse_sectional_door_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SECTIONAL",
        "OVERHEAD DOOR",
        "HIGH-LIFT",
        "HIGH LIFT",
        "VERTICAL LIFT",
        "TORSION SPRING",
        "DOOR TRACK",
        "COUNTERWEIGHT",
        "LOADING BAY DOOR",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Lift type
    if "VERTICAL LIFT" in upper or "FULL VERTICAL" in upper:
        lift_type = "VERTICAL_LIFT"
    elif "HIGH-LIFT" in upper or "HIGH LIFT" in upper:
        lift_type = "HIGH_LIFT"
    elif "LOW HEADROOM" in upper or "LOW-HEADROOM" in upper:
        lift_type = "LOW_HEADROOM"
    else:
        lift_type = "STANDARD_LIFT"

    # Dimensions W x H
    dim_match = re.search(r"(\d{3,5})\s*(?:W|MM\s*W|WIDE)?\s*[xX]\s*(\d{3,5})\s*(?:H|MM\s*H|HIGH)?", clean)
    door_width_mm = float(dim_match.group(1)) if dim_match else None
    door_height_mm = float(dim_match.group(2)) if dim_match else None

    # Lift height (e.g. "LIFT: 1200MM" or "1800MM LIFT")
    lift_match = re.search(r"(?:(?:LIFT|RISE)[:\s]*(\d{3,4})\s*MM|(\d{3,4})\s*MM\s*(?:LIFT|RISE))", upper)
    lift_height_mm = None
    if lift_match:
        val = lift_match.group(1) or lift_match.group(2)
        lift_height_mm = float(val)

    # Track profile
    if '3"' in upper or "3 INCH" in upper or "3-INCH" in upper or "75MM" in upper or "75 MM" in upper:
        track_profile = "75MM (3-INCH)"
    else:
        track_profile = "50MM (2-INCH)"

    # Counterweight type
    if "COUNTERWEIGHT DRUM" in upper or "WEIGHT BOX" in upper:
        counterweight_type = "COUNTERWEIGHT_DRUM"
    else:
        counterweight_type = "TORSION_SPRING"

    return {
        "raw_text": clean,
        "lift_type": lift_type,
        "door_width_mm": door_width_mm,
        "door_height_mm": door_height_mm,
        "lift_height_mm": lift_height_mm,
        "track_profile": track_profile,
        "counterweight_type": counterweight_type,
    }


def evaluate_sectional_door_track_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[SectionalDoorTrackCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_sectional_door_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_sdt_{i+1:03d}"
        cand = SectionalDoorTrackCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            lift_type=parsed["lift_type"],
            door_width_mm=parsed["door_width_mm"],
            door_height_mm=parsed["door_height_mm"],
            lift_height_mm=parsed["lift_height_mm"],
            track_profile=parsed["track_profile"],
            counterweight_type=parsed["counterweight_type"],
            track_points=snapped_pts,
            track_length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
