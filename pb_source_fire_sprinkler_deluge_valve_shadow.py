"""Source Fire Sprinkler Pre-Action Deluge Valve Station Shadow Authority.

Extracts candidate fire sprinkler pre-action double/single interlock valves,
deluge valve assemblies, trim configurations, and header piping from fire protection plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class DelugeValveCandidate:
    candidate_id: str
    sheet_id: str
    valve_type: str
    diameter_dn_mm: Optional[float]
    release_type: str
    rated_pressure_kpa: Optional[float]
    has_accelerator: bool
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "valve_type": self.valve_type,
            "diameter_dn_mm": self.diameter_dn_mm,
            "release_type": self.release_type,
            "rated_pressure_kpa": self.rated_pressure_kpa,
            "has_accelerator": self.has_accelerator,
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


def parse_deluge_valve_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "PRE-ACTION",
        "PREACTION",
        "DELUGE VALVE",
        "DELUGE STATION",
        "SPRINKLER CONTROL VALVE",
        "DELUGE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Valve type
    if "DOUBLE INTERLOCK" in upper:
        valve_type = "DOUBLE_INTERLOCK_PREACTION"
    elif "SINGLE INTERLOCK" in upper:
        valve_type = "SINGLE_INTERLOCK_PREACTION"
    elif "DELUGE" in upper:
        valve_type = "DELUGE_VALVE"
    else:
        valve_type = "PRE_ACTION_VALVE"

    # Diameter DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    dia_match = re.search(r"\b(\d{2,3})\s*MM\b", upper)
    diameter_dn_mm = None
    if dn_match:
        diameter_dn_mm = float(dn_match.group(1))
    elif dia_match:
        diameter_dn_mm = float(dia_match.group(1))

    # Release type
    if "SOLENOID" in upper or "ELECTRIC" in upper:
        release_type = "ELECTRIC_SOLENOID"
    elif "PNEUMATIC" in upper or "AIR PILOT" in upper:
        release_type = "PNEUMATIC_PILOT"
    elif "HYDRAULIC" in upper:
        release_type = "HYDRAULIC_RELEASE"
    else:
        release_type = "MANUAL_EMERGENCY"

    # Rated pressure (e.g. "1200 KPA", "1600KPA")
    pressure_match = re.search(r"(\d{3,4})\s*KPA\b", upper)
    rated_pressure_kpa = float(pressure_match.group(1)) if pressure_match else 1600.0

    # Has accelerator
    has_accelerator = "ACCELERATOR" in upper or "QOD" in upper

    return {
        "raw_text": clean,
        "valve_type": valve_type,
        "diameter_dn_mm": diameter_dn_mm,
        "release_type": release_type,
        "rated_pressure_kpa": rated_pressure_kpa,
        "has_accelerator": has_accelerator,
    }


def evaluate_fire_sprinkler_deluge_valve_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[DelugeValveCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_deluge_valve_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_fdv_{i+1:03d}"
        cand = DelugeValveCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            valve_type=parsed["valve_type"],
            diameter_dn_mm=parsed["diameter_dn_mm"],
            release_type=parsed["release_type"],
            rated_pressure_kpa=parsed["rated_pressure_kpa"],
            has_accelerator=parsed["has_accelerator"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
