"""Source High-Voltage Substation Oil Containment Bund & Flame Trap Shadow Authority.

Extracts candidate high-voltage transformer oil containment bund perimeters,
flame trap aggregate layers, wall dimensions, and oil separator sump geometry.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class SubstationBundCandidate:
    candidate_id: str
    sheet_id: str
    bund_type: str
    wall_height_mm: Optional[float]
    wall_thickness_mm: Optional[float]
    containment_volume_m3: Optional[float]
    flame_trap_aggregate: str
    has_flame_trap: bool
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "bund_type": self.bund_type,
            "wall_height_mm": self.wall_height_mm,
            "wall_thickness_mm": self.wall_thickness_mm,
            "containment_volume_m3": self.containment_volume_m3,
            "flame_trap_aggregate": self.flame_trap_aggregate,
            "has_flame_trap": self.has_flame_trap,
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


def parse_substation_bund_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "TRANSFORMER BUND",
        "OIL CONTAINMENT",
        "SUBSTATION BUND",
        "FLAME TRAP",
        "TRANSFORMER PIT",
        "OIL-WATER SEPARATOR",
        "OIL BUND",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Bund type
    if "SUMP" in upper or "SEPARATOR" in upper:
        bund_type = "OIL_WATER_SEPARATOR_SUMP"
    elif "BASIN" in upper and "FLAME" in upper:
        bund_type = "FLAME_TRAP_BASIN"
    elif "WALL" in upper and "CONTAINMENT" in upper:
        bund_type = "SECONDARY_CONTAINMENT_WALL"
    else:
        bund_type = "TRANSFORMER_OIL_BUND"

    # Wall height (e.g. "1200H", "900MM HIGH", "1500 HEIGHT")
    height_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:H|HIGH|HEIGHT)\b", upper)
    wall_height_mm = float(height_match.group(1)) if height_match else None

    # Wall thickness (e.g. "250MM THICK", "200MM WALL", "300MM RC")
    thick_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:THICK|WALL|RC)\b", upper)
    wall_thickness_mm = float(thick_match.group(1)) if thick_match else None

    # Containment volume (e.g. "40 M3", "25.5 M3", "30 CUBIC METRES")
    vol_match = re.search(r"(\d{1,3}(?:\.\d)?)\s*(?:M3|CU\.?\s*M|CUBIC\s*METRES?)\b", upper)
    containment_volume_m3 = float(vol_match.group(1)) if vol_match else None

    # Flame trap aggregate
    if "GRANITE" in upper:
        flame_trap_aggregate = "CRUSHED_GRANITE"
    elif "GRAVEL" in upper or "RIVER" in upper:
        flame_trap_aggregate = "ROUNDED_RIVER_GRAVEL"
    else:
        flame_trap_aggregate = "CRUSHED_BASALT"

    # Has flame trap
    has_flame_trap = "FLAME TRAP" in upper or "FLAME-TRAP" in upper or "BASALT" in upper

    return {
        "raw_text": clean,
        "bund_type": bund_type,
        "wall_height_mm": wall_height_mm,
        "wall_thickness_mm": wall_thickness_mm,
        "containment_volume_m3": containment_volume_m3,
        "flame_trap_aggregate": flame_trap_aggregate,
        "has_flame_trap": has_flame_trap,
    }


def evaluate_substation_bund_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[SubstationBundCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_substation_bund_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_sob_{i+1:03d}"
        cand = SubstationBundCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            bund_type=parsed["bund_type"],
            wall_height_mm=parsed["wall_height_mm"],
            wall_thickness_mm=parsed["wall_thickness_mm"],
            containment_volume_m3=parsed["containment_volume_m3"],
            flame_trap_aggregate=parsed["flame_trap_aggregate"],
            has_flame_trap=parsed["has_flame_trap"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
