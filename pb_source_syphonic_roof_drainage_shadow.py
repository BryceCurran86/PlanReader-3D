"""Source Roof Syphonic Rainwater Drainage Bowl & Tailpipe Tail Shadow Authority.

Extracts candidate syphonic roof drainage outlet bowls, anti-vortex baffles,
tailpipes, and horizontal HDPE collector runs from hydraulic/plumbing plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class SyphonicDrainageCandidate:
    candidate_id: str
    sheet_id: str
    component_type: str
    diameter_dn_mm: Optional[float]
    pipe_material: str
    has_air_baffle: bool
    leaf_guard_type: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "component_type": self.component_type,
            "diameter_dn_mm": self.diameter_dn_mm,
            "pipe_material": self.pipe_material,
            "has_air_baffle": self.has_air_baffle,
            "leaf_guard_type": self.leaf_guard_type,
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


def parse_syphonic_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SYPHONIC",
        "SIPHONIC",
        "ROOF DRAIN BOWL",
        "TAILPIPE",
        "HDPE COLLECTOR",
        "AIR BAFFLE BOWL",
        "ANTI-VORTEX",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Component type
    if "OVERFLOW" in upper:
        component_type = "OVERFLOW_OUTLET"
    elif "TAILPIPE" in upper:
        component_type = "TAILPIPE"
    elif "COLLECTOR" in upper or "HEADER" in upper:
        component_type = "HORIZONTAL_COLLECTOR"
    else:
        component_type = "ROOF_OUTLET_BOWL"

    # Diameter DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    dia_match = re.search(r"(\d{2,3})\s*MM\s*(?:DIA|Ø)?\b", upper)
    diameter_dn_mm = None
    if dn_match:
        diameter_dn_mm = float(dn_match.group(1))
    elif dia_match:
        diameter_dn_mm = float(dia_match.group(1))

    # Material
    if "CAST IRON" in upper or "C.I." in upper:
        pipe_material = "CAST_IRON"
    elif "STAINLESS" in upper or "S.S." in upper:
        pipe_material = "STAINLESS_STEEL"
    else:
        pipe_material = "HDPE"

    # Air baffle
    has_air_baffle = "BAFFLE" in upper or "ANTI-VORTEX" in upper or "VORTEX" in upper

    # Leaf guard
    if "FLAT" in upper:
        leaf_guard_type = "FLAT_GRATE"
    else:
        leaf_guard_type = "DOME_GRATE"

    return {
        "raw_text": clean,
        "component_type": component_type,
        "diameter_dn_mm": diameter_dn_mm,
        "pipe_material": pipe_material,
        "has_air_baffle": has_air_baffle,
        "leaf_guard_type": leaf_guard_type,
    }


def evaluate_syphonic_drainage_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[SyphonicDrainageCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_syphonic_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_srd_{i+1:03d}"
        cand = SyphonicDrainageCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            component_type=parsed["component_type"],
            diameter_dn_mm=parsed["diameter_dn_mm"],
            pipe_material=parsed["pipe_material"],
            has_air_baffle=parsed["has_air_baffle"],
            leaf_guard_type=parsed["leaf_guard_type"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
