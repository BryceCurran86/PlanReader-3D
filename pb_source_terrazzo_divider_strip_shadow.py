"""Source Epoxy Terrazzo Floor Divider Strip & Movement Joint Shadow Authority.

Extracts candidate terrazzo brass/zinc divider strips, neoprene movement joints,
pattern grid modules, and finish boundary geometry from architectural plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class TerrazzoDividerStripCandidate:
    candidate_id: str
    sheet_id: str
    strip_type: str
    strip_material: str
    strip_width_mm: Optional[float]
    strip_height_mm: Optional[float]
    grid_module_mm: Optional[str]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "strip_type": self.strip_type,
            "strip_material": self.strip_material,
            "strip_width_mm": self.strip_width_mm,
            "strip_height_mm": self.strip_height_mm,
            "grid_module_mm": self.grid_module_mm,
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


def parse_terrazzo_strip_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "TERRAZZO",
        "DIVIDER STRIP",
        "ZINC STRIP",
        "BRASS STRIP",
        "TERRAZZO JOINT",
        "CONTROL STRIP",
        "NEOPRENE MOVEMENT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Strip type
    if "PERIMETER" in upper:
        strip_type = "PERIMETER_EXPANSION_JOINT"
    elif "MOVEMENT" in upper or "EXPANSION" in upper or "CONTROL" in upper:
        strip_type = "MOVEMENT_JOINT"
    elif "TRANSITION" in upper:
        strip_type = "TRANSITION_STRIP"
    else:
        strip_type = "DIVIDER_STRIP"

    # Material
    if "BRASS" in upper:
        strip_material = "BRASS"
    elif "ZINC" in upper:
        strip_material = "ZINC"
    elif "ALUMINIUM" in upper or "ALUMINUM" in upper or "ALUM" in upper:
        strip_material = "ALUMINIUM"
    elif "NEOPRENE" in upper:
        strip_material = "NEOPRENE_COMPOSITE"
    elif "STAINLESS" in upper or "S.S." in upper:
        strip_material = "STAINLESS_STEEL"
    else:
        strip_material = "BRASS"

    # Width (e.g. "3MM BRASS", "10MM NEOPRENE", "6MM WIDE")
    width_match = re.search(r"\b(\d{1,2}(?:\.\d)?)\s*MM\s*(?:THICK|WIDE|WIDTH)?\b", upper)
    strip_width_mm = float(width_match.group(1)) if width_match else None

    # Height / depth (e.g. "12MM HIGH" or "9.5MM DEEP")
    height_match = re.search(r"\b(\d{1,2}(?:\.\d)?)\s*MM\s*(?:HIGH|HEIGHT|DEEP|DEPTH)\b", upper)
    strip_height_mm = float(height_match.group(1)) if height_match else None

    # Grid module (e.g. "1200x1200" or "900 X 900")
    grid_match = re.search(r"(\d{3,4}\s*[xX]\s*\d{3,4})\s*(?:MM)?\s*(?:GRID|MODULE)?", clean)
    grid_module_mm = grid_match.group(1).replace(" ", "").upper() if grid_match else None

    return {
        "raw_text": clean,
        "strip_type": strip_type,
        "strip_material": strip_material,
        "strip_width_mm": strip_width_mm,
        "strip_height_mm": strip_height_mm,
        "grid_module_mm": grid_module_mm,
    }


def evaluate_terrazzo_divider_strip_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[TerrazzoDividerStripCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_terrazzo_strip_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_tds_{i+1:03d}"
        cand = TerrazzoDividerStripCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            strip_type=parsed["strip_type"],
            strip_material=parsed["strip_material"],
            strip_width_mm=parsed["strip_width_mm"],
            strip_height_mm=parsed["strip_height_mm"],
            grid_module_mm=parsed["grid_module_mm"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
