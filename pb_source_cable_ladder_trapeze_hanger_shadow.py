"""Source Electrical Cable Ladder Unistrut Trapeze Hanger Shadow Authority.

Extracts candidate electrical cable ladders, unistrut channel trapeze hangers,
threaded drop rods, seismic sway braces, and linear alignments from electrical services plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class CableLadderCandidate:
    candidate_id: str
    sheet_id: str
    material_finish: str
    ladder_width_mm: float
    side_rail_height_mm: float
    channel_profile: str
    threaded_rod_dia_mm: float
    hanger_spacing_mm: float
    fire_rated: bool
    seismic_braced: bool
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "material_finish": self.material_finish,
            "ladder_width_mm": self.ladder_width_mm,
            "side_rail_height_mm": self.side_rail_height_mm,
            "channel_profile": self.channel_profile,
            "threaded_rod_dia_mm": self.threaded_rod_dia_mm,
            "hanger_spacing_mm": self.hanger_spacing_mm,
            "fire_rated": self.fire_rated,
            "seismic_braced": self.seismic_braced,
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


def parse_cable_ladder_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CABLE LADDER",
        "TRAPEZE HANGER",
        "UNISTRUT HANGER",
        "ELECTRICAL LADDER",
        "CABLE TRAY HANGER",
        "HEAVY DUTY LADDER",
        "NEMA LADDER",
        "CABLE SUPPORT LADDER",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Material & Finish
    if "316" in upper or "STAINLESS" in upper:
        material_finish = "STAINLESS_STEEL_316"
    elif "ALUMINIUM" in upper or "ALUMINUM" in upper:
        material_finish = "ALUMINIUM"
    elif "PRE-GAL" in upper or "PRE GAL" in upper:
        material_finish = "PRE_GALVANIZED"
    else:
        material_finish = "HOT_DIP_GALVANIZED"

    # Ladder width (e.g. "600MM WIDE", "450MM CABLE LADDER", "300W")
    w_match = re.search(r"\b(\d{3})\s*MM\s*(?:WIDE|WIDTH|CABLE)?", upper)
    w_short = re.search(r"\b(\d{3})W\b", upper)
    if w_match:
        ladder_width = float(w_match.group(1))
    elif w_short:
        ladder_width = float(w_short.group(1))
    else:
        ladder_width = 450.0

    # Side rail height (e.g. "100MM SIDE RAIL", "75MM HIGH", "125MM RAIL")
    rail_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:HIGH|RAIL|DEPTH|DEEP)", upper)
    rail_height = float(rail_match.group(1)) if rail_match else 100.0

    # Unistrut channel profile (e.g. "P1000", "P2000", "P1001", "41X41")
    if "P2000" in upper or "41X21" in upper:
        channel_profile = "P2000"
    elif "P1001" in upper or "41X82" in upper:
        channel_profile = "P1001"
    else:
        channel_profile = "P1000"

    # Threaded drop rod diameter (e.g. "M12 ROD", "M10 THREADED ROD", "M16")
    rod_match = re.search(r"\bM(\d{2})\b", upper)
    rod_dia = float(rod_match.group(1)) if rod_match else 12.0

    # Hanger spacing (e.g. "@ 1.5M CTS", "@ 1500 CTS", "@ 2.0M SPACING")
    space_m = re.search(r"@\s*(\d(?:\.\d)?)\s*M\b", upper)
    space_mm = re.search(r"(?:@|\bAT\b)?\s*(\d{4})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|SPACING)", upper)
    if space_m:
        spacing = float(space_m.group(1)) * 1000.0
    elif space_mm:
        spacing = float(space_mm.group(1))
    else:
        spacing = 1500.0

    # Fire rating (e.g. "AS/NZS 3013", "FIRE RATED", "2-HR ELECTRICAL")
    fire_rated = any(k in upper for k in ["3013", "FIRE RATED", "FIRE-RATED", "2-HR"])

    # Seismic bracing
    seismic = any(k in upper for k in ["SEISMIC", "SWAY BRACE", "SWAY STRUT", "EARTHQUAKE"])

    return {
        "raw_text": clean,
        "material_finish": material_finish,
        "ladder_width_mm": ladder_width,
        "side_rail_height_mm": rail_height,
        "channel_profile": channel_profile,
        "threaded_rod_dia_mm": rod_dia,
        "hanger_spacing_mm": spacing,
        "fire_rated": fire_rated,
        "seismic_braced": seismic,
    }


def evaluate_cable_ladder_trapeze_hanger_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[CableLadderCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_cable_ladder_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_clt_{i+1:03d}"
        cand = CableLadderCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            material_finish=parsed["material_finish"],
            ladder_width_mm=parsed["ladder_width_mm"],
            side_rail_height_mm=parsed["side_rail_height_mm"],
            channel_profile=parsed["channel_profile"],
            threaded_rod_dia_mm=parsed["threaded_rod_dia_mm"],
            hanger_spacing_mm=parsed["hanger_spacing_mm"],
            fire_rated=parsed["fire_rated"],
            seismic_braced=parsed["seismic_braced"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
