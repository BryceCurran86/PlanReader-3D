"""Source Hydraulic Grease Waste Sampling Pit & Sump Pump Shadow Authority.

Extracts candidate trade waste sampling pits, duplex sump pump chambers,
gas-tight covers, and pump configurations from hydraulic drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class HydraulicPitCandidate:
    candidate_id: str
    sheet_id: str
    pit_type: str
    pit_dimensions_mm: Optional[str]
    depth_mm: Optional[float]
    pump_configuration: str
    cover_type: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "pit_type": self.pit_type,
            "pit_dimensions_mm": self.pit_dimensions_mm,
            "depth_mm": self.depth_mm,
            "pump_configuration": self.pump_configuration,
            "cover_type": self.cover_type,
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


def parse_hydraulic_pit_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    # Negation check
    if "NO SAMPLING" in upper or "NO SAMPLE" in upper or "NOT REQUIRED" in upper:
        return None

    triggers = [
        "SAMPLING PIT",
        "TRADE WASTE PIT",
        "SUMP PUMP",
        "SUBMERSIBLE PUMP",
        "SEWAGE EJECTOR",
        "GREASE WASTE SAMPLING",
        "WASTE PIT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Pit type
    if "EJECTOR" in upper:
        pit_type = "SEWAGE_EJECTOR_PIT"
    elif "SUMP" in upper or "PUMP" in upper:
        pit_type = "SUMP_PUMP_PIT"
    elif "MONITORING" in upper:
        pit_type = "MONITORING_WELL"
    else:
        pit_type = "SAMPLING_PIT"

    # Pump configuration
    if "DUPLEX" in upper or "DUTY/STANDBY" in upper or "DUTY / STANDBY" in upper:
        pump_configuration = "DUPLEX_DUTY_STANDBY"
    elif "TRIPLEX" in upper:
        pump_configuration = "TRIPLEX"
    elif "SIMPLEX" in upper:
        pump_configuration = "SIMPLEX"
    elif pit_type == "SAMPLING_PIT":
        pump_configuration = "NONE_GRAVITY_PIT"
    else:
        pump_configuration = "DUPLEX_DUTY_STANDBY"

    # Dimensions
    dim_match = re.search(r"(\d{3,4}\s*[xX]\s*\d{3,4})\s*(?:MM)?", clean)
    dia_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:DIA|Ø)", upper)
    dia_match_alt = re.search(r"(?:DIA|Ø)[:\s]*(\d{3,4})\s*MM", upper)
    pit_dimensions_mm = None
    if dim_match:
        pit_dimensions_mm = dim_match.group(1).replace(" ", "").upper()
    elif dia_match:
        pit_dimensions_mm = f"{dia_match.group(1)} DIA"
    elif dia_match_alt:
        pit_dimensions_mm = f"{dia_match_alt.group(1)} DIA"

    # Depth (e.g. "1200 DEEP", "1800MM DEPTH", "900 DEEP")
    depth_match = re.search(r"\b(\d{3,4})\s*(?:MM)?\s*(?:DEEP|DEPTH)\b", upper)
    depth_mm = float(depth_match.group(1)) if depth_match else None

    # Cover type
    if "CLASS D" in upper or "HEAVY DUTY" in upper:
        cover_type = "HEAVY_DUTY_CLASS_D"
    elif "GAS-TIGHT" in upper or "GAS TIGHT" in upper or "CLASS B" in upper:
        cover_type = "GAS_TIGHT_CLASS_B"
    else:
        cover_type = "PEDESTRIAN_CLASS_A"

    return {
        "raw_text": clean,
        "pit_type": pit_type,
        "pit_dimensions_mm": pit_dimensions_mm,
        "depth_mm": depth_mm,
        "pump_configuration": pump_configuration,
        "cover_type": cover_type,
    }


def evaluate_hydraulic_pit_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[HydraulicPitCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_hydraulic_pit_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_hps_{i+1:03d}"
        cand = HydraulicPitCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            pit_type=parsed["pit_type"],
            pit_dimensions_mm=parsed["pit_dimensions_mm"],
            depth_mm=parsed["depth_mm"],
            pump_configuration=parsed["pump_configuration"],
            cover_type=parsed["cover_type"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
