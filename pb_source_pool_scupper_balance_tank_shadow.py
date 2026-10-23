"""Source Swimming Pool Overflow Scupper & Perimeter Balance Tank Shadow Authority.

Extracts candidate pool overflow gutters, wet deck scuppers, balance/surge tanks,
grating specifications, and drain piping from aquatic/hydraulic plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class PoolBalanceTankCandidate:
    candidate_id: str
    sheet_id: str
    system_type: str
    grating_material: str
    gutter_width_mm: Optional[float]
    gutter_depth_mm: Optional[float]
    balance_tank_capacity_litres: Optional[float]
    drain_pipe_dia_mm: Optional[float]
    level_sensors: bool
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
            "grating_material": self.grating_material,
            "gutter_width_mm": self.gutter_width_mm,
            "gutter_depth_mm": self.gutter_depth_mm,
            "balance_tank_capacity_litres": self.balance_tank_capacity_litres,
            "drain_pipe_dia_mm": self.drain_pipe_dia_mm,
            "level_sensors": self.level_sensors,
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


def parse_pool_scupper_balance_tank_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "POOL OVERFLOW",
        "WET DECK GUTTER",
        "BALANCE TANK",
        "SCUPPER OUTLET",
        "PERIMETER SCUPPER",
        "SURGE TANK",
        "POOL GUTTER GRATING",
        "WET DECK SCUPPER",
    ]
    if not any(t in upper for t in triggers):
        return None

    # System type
    if "BALANCE TANK" in upper or "SURGE TANK" in upper:
        system_type = "BALANCE_TANK"
    else:
        system_type = "WET_DECK_OVERFLOW_GUTTER"

    # Grating material
    if "STAINLESS" in upper or "WEDGE WIRE" in upper or "316" in upper:
        grating_material = "STAINLESS_STEEL_WEDGE_WIRE"
    elif "SLOT" in upper or "FINGER" in upper:
        grating_material = "FINGER_SAFE_SLOT_DRAIN"
    else:
        grating_material = "POLYPROPYLENE_TRANSVERSE"

    # Gutter width & depth (e.g. "250X200 GUTTER", "250MM WIDE X 200MM DEEP", "300MM GUTTER")
    dim_match = re.search(r"\b(\d{3})\s*[X*×]\s*(\d{3})\b", upper)
    w_match = re.search(r"\b(\d{3})\s*MM\s*(?:WIDE|WIDTH|GUTTER)", upper)
    d_match = re.search(r"\b(\d{3})\s*MM\s*(?:DEEP|DEPTH)", upper)
    if dim_match:
        gutter_w = float(dim_match.group(1))
        gutter_d = float(dim_match.group(2))
    else:
        gutter_w = float(w_match.group(1)) if w_match else 250.0
        gutter_d = float(d_match.group(1)) if d_match else 200.0

    # Balance tank capacity (e.g. "20,000L", "25000L", "20M3", "25 KL")
    tank_litres = None
    l_match = re.search(r"\b(\d{1,3}(?:,\d{3})+|\d{4,6})\s*(?:L|LTR|LITRES|LITERS)\b", upper)
    m3_match = re.search(r"\b(\d{1,3})\s*(?:M3|M³|CUM)\b", upper)
    kl_match = re.search(r"\b(\d{1,3})\s*KL\b", upper)
    if l_match:
        tank_litres = float(l_match.group(1).replace(",", ""))
    elif m3_match:
        tank_litres = float(m3_match.group(1)) * 1000.0
    elif kl_match:
        tank_litres = float(kl_match.group(1)) * 1000.0
    elif system_type == "BALANCE_TANK":
        tank_litres = 20000.0

    # Drain pipe diameter (e.g. "200 DIA DRAIN", "150MM PIPE", "DN200")
    pipe_match = re.search(r"(?:DN|\bDIA\s*|Ø\s*)(\d{3})\b", upper)
    if not pipe_match:
        pipe_match = re.search(r"\b(\d{3})\s*MM\s*(?:DRAIN|PIPE|GRAVITY)", upper)
    drain_dia = float(pipe_match.group(1)) if pipe_match else 200.0

    # Level sensors
    sensors = any(k in upper for k in ["LEVEL SENSOR", "FLOAT SWITCH", "ULTRASONIC", "LEVEL CONTROL"])

    return {
        "raw_text": clean,
        "system_type": system_type,
        "grating_material": grating_material,
        "gutter_width_mm": gutter_w,
        "gutter_depth_mm": gutter_d,
        "balance_tank_capacity_litres": tank_litres,
        "drain_pipe_dia_mm": drain_dia,
        "level_sensors": sensors,
    }


def evaluate_pool_scupper_balance_tank_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[PoolBalanceTankCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_pool_scupper_balance_tank_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_pbt_{i+1:03d}"
        cand = PoolBalanceTankCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            system_type=parsed["system_type"],
            grating_material=parsed["grating_material"],
            gutter_width_mm=parsed["gutter_width_mm"],
            gutter_depth_mm=parsed["gutter_depth_mm"],
            balance_tank_capacity_litres=parsed["balance_tank_capacity_litres"],
            drain_pipe_dia_mm=parsed["drain_pipe_dia_mm"],
            level_sensors=parsed["level_sensors"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
