"""Source Architectural Louver Penthouse & Acoustic Attenuation Splitter Shadow Authority.

Extracts candidate rooftop mechanical louver penthouses, continuous weatherproof blades,
bird screens, and acoustic silencer/splitter geometry from rooftop plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class LouverPenthouseCandidate:
    candidate_id: str
    sheet_id: str
    enclosure_type: str
    blade_type: str
    height_mm: Optional[float]
    free_area_pct: Optional[float]
    acoustic_rating: Optional[str]
    has_bird_mesh: bool
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "enclosure_type": self.enclosure_type,
            "blade_type": self.blade_type,
            "height_mm": self.height_mm,
            "free_area_pct": self.free_area_pct,
            "acoustic_rating": self.acoustic_rating,
            "has_bird_mesh": self.has_bird_mesh,
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


def parse_louver_penthouse_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "LOUVER PENTHOUSE",
        "LOUVRE PENTHOUSE",
        "LOUVER ENCLOSURE",
        "LOUVRE ENCLOSURE",
        "ACOUSTIC LOUVER",
        "ACOUSTIC LOUVRE",
        "ATTENUATION SPLITTER",
        "ROOFTOP SCREEN",
        "WEATHERPROOF LOUVER",
        "PLANT SCREEN",
        "ACOUSTIC SCREEN",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Enclosure type
    if "SPLITTER" in upper or "ATTENUATION SPLITTER" in upper:
        enclosure_type = "ATTENUATION_SPLITTER"
    elif "ACOUSTIC" in upper:
        enclosure_type = "ACOUSTIC_SCREEN"
    elif "PENTHOUSE" in upper:
        enclosure_type = "LOUVER_PENTHOUSE"
    else:
        enclosure_type = "PLANT_ENCLOSURE"

    # Blade type
    if "SPLITTER" in upper:
        blade_type = "SOUND_ATTENUATION_SPLITTER"
    elif "ACOUSTIC" in upper:
        blade_type = "ACOUSTIC_LOUVER_BOX"
    elif "DRAINABLE" in upper:
        blade_type = "DRAINABLE"
    else:
        blade_type = "WEATHERPROOF_CHEVRON"

    # Height (e.g. "3000H", "2400MM HIGH", "2700 HEIGHT")
    height_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:H|HIGH|HEIGHT)\b", upper)
    height_mm = float(height_match.group(1)) if height_match else None

    # Free area % (e.g. "50% FREE AREA" or "55%")
    area_match = re.search(r"(\d{2})\s*%", upper)
    free_area_pct = float(area_match.group(1)) if area_match else None

    # Acoustic rating (e.g. "Rw 20" or "STC 25")
    rw_match = re.search(r"\b(RW\s*\d{1,2}|STC\s*\d{1,2})\b", upper)
    acoustic_rating = rw_match.group(1).upper() if rw_match else None

    # Bird mesh
    has_bird_mesh = "BIRD" in upper or "MESH" in upper or "INSECT" in upper

    return {
        "raw_text": clean,
        "enclosure_type": enclosure_type,
        "blade_type": blade_type,
        "height_mm": height_mm,
        "free_area_pct": free_area_pct,
        "acoustic_rating": acoustic_rating,
        "has_bird_mesh": has_bird_mesh,
    }


def evaluate_louver_penthouse_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[LouverPenthouseCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_louver_penthouse_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_lps_{i+1:03d}"
        cand = LouverPenthouseCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            enclosure_type=parsed["enclosure_type"],
            blade_type=parsed["blade_type"],
            height_mm=parsed["height_mm"],
            free_area_pct=parsed["free_area_pct"],
            acoustic_rating=parsed["acoustic_rating"],
            has_bird_mesh=parsed["has_bird_mesh"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
