"""Source Electrical Busway Trunking & Tap-Off Plug Unit Shadow Authority.

Extracts candidate electrical feeder/plug-in busway trunking, tap-off plug units,
and riser distribution geometry from electrical engineering drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class ElectricalBuswayCandidate:
    candidate_id: str
    sheet_id: str
    system_type: str
    rating_amperes: Optional[float]
    conductor_material: str
    poles_count: str
    enclosure_ip_rating: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "system_type": self.system_type,
            "rating_amperes": self.rating_amperes,
            "conductor_material": self.conductor_material,
            "poles_count": self.poles_count,
            "enclosure_ip_rating": self.enclosure_ip_rating,
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


def parse_busway_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "BUSWAY",
        "BUSDUCT",
        "BUS TRUNKING",
        "TAP-OFF",
        "TAP OFF",
        "PLUG-IN UNIT",
        "POWER BUS",
        "SANDWICH BUS",
    ]
    if not any(t in upper for t in triggers):
        return None

    # System type
    if "TAP-OFF" in upper or "TAP OFF" in upper or "PLUG-IN UNIT" in upper:
        system_type = "TAP_OFF_UNIT"
    elif "EXPANSION" in upper:
        system_type = "EXPANSION_JOINT"
    elif "FEEDER" in upper:
        system_type = "FEEDER_BUSWAY"
    else:
        system_type = "PLUG_IN_BUSWAY"

    # Rating (e.g. "1600A", "800 AMP", "250A")
    rating_match = re.search(r"\b(\d{3,5})\s*A(?:MP)?\b", upper)
    rating_amperes = float(rating_match.group(1)) if rating_match else None

    # Material
    if "ALUMINIUM" in upper or "ALUMINUM" in upper or "ALUM" in upper:
        conductor_material = "ALUMINIUM"
    else:
        conductor_material = "COPPER"

    # Poles
    if "4P" in upper or "4-POLE" in upper or "4 POLE" in upper or "3P+N+E" in upper or "4WIRE" in upper:
        poles_count = "4P"
    else:
        poles_count = "3P"

    # IP rating (e.g. IP54, IP55, IP65)
    ip_match = re.search(r"\b(IP\s*\d{2})\b", upper)
    enclosure_ip_rating = ip_match.group(1).replace(" ", "") if ip_match else "IP54"

    return {
        "raw_text": clean,
        "system_type": system_type,
        "rating_amperes": rating_amperes,
        "conductor_material": conductor_material,
        "poles_count": poles_count,
        "enclosure_ip_rating": enclosure_ip_rating,
    }


def evaluate_electrical_busway_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[ElectricalBuswayCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_busway_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_ebt_{i+1:03d}"
        cand = ElectricalBuswayCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            system_type=parsed["system_type"],
            rating_amperes=parsed["rating_amperes"],
            conductor_material=parsed["conductor_material"],
            poles_count=parsed["poles_count"],
            enclosure_ip_rating=parsed["enclosure_ip_rating"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
