"""Source Structural Steel Crane Runway End Stop & Buffer Shadow Authority.

Extracts candidate crane runway travel end stops, energy absorbing buffers,
and end plate bracket assemblies from structural drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class CraneEndStopCandidate:
    candidate_id: str
    sheet_id: str
    stop_type: str
    buffer_type: str
    plate_thickness_mm: Optional[float]
    crane_capacity_tonnes: Optional[float]
    buffer_diameter_mm: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "stop_type": self.stop_type,
            "buffer_type": self.buffer_type,
            "plate_thickness_mm": self.plate_thickness_mm,
            "crane_capacity_tonnes": self.crane_capacity_tonnes,
            "buffer_diameter_mm": self.buffer_diameter_mm,
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


def parse_crane_end_stop_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CRANE END STOP",
        "RUNWAY END STOP",
        "CRANE BUFFER",
        "TRAVEL STOP",
        "HYDRAULIC BUFFER",
        "POLYURETHANE BUFFER",
        "RUNWAY STOP BRACKET",
        "BUFFER STOP",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Stop type
    if "BOLT" in upper:
        stop_type = "BOLTED_END_STOP"
    elif "WELD" in upper:
        stop_type = "WELDED_END_STOP"
    else:
        stop_type = "RUNWAY_TRAVEL_STOP"

    # Buffer type
    if "HYDRAULIC" in upper:
        buffer_type = "HYDRAULIC"
    elif "SPRING" in upper or "COIL" in upper:
        buffer_type = "COIL_SPRING"
    elif "RUBBER" in upper:
        buffer_type = "RUBBER_BUMPER"
    else:
        buffer_type = "POLYURETHANE_CELLULAR"

    # Plate thickness (e.g. "20MM THICK PLATE", "25MM PL", "25MM PLATE", "20MM THICK")
    plate_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:THICK|PL|PLATE)\b", upper)
    plate_thickness_mm = float(plate_match.group(1)) if plate_match else None

    # Crane capacity (e.g. "10T CRANE" or "20 TONNE")
    cap_match = re.search(r"\b(\d{1,3})\s*(?:T|TON|TONNE|TONNES)\b", upper)
    crane_capacity_tonnes = float(cap_match.group(1)) if cap_match else None

    # Buffer diameter (e.g. "160MM DIA BUFFER" or "Ø125 BUFFER")
    dia_match = re.search(r"(?:(?:Ø|DN|DIA|DIAMETER)[:\s]*(\d{2,3})\s*MM|(\d{2,3})\s*MM\s*(?:DIA|Ø|BUFFER))", upper)
    buffer_diameter_mm = None
    if dia_match:
        val = dia_match.group(1) or dia_match.group(2)
        buffer_diameter_mm = float(val)

    return {
        "raw_text": clean,
        "stop_type": stop_type,
        "buffer_type": buffer_type,
        "plate_thickness_mm": plate_thickness_mm,
        "crane_capacity_tonnes": crane_capacity_tonnes,
        "buffer_diameter_mm": buffer_diameter_mm,
    }


def evaluate_crane_end_stop_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[CraneEndStopCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_crane_end_stop_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_ces_{i+1:03d}"
        cand = CraneEndStopCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            stop_type=parsed["stop_type"],
            buffer_type=parsed["buffer_type"],
            plate_thickness_mm=parsed["plate_thickness_mm"],
            crane_capacity_tonnes=parsed["crane_capacity_tonnes"],
            buffer_diameter_mm=parsed["buffer_diameter_mm"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
