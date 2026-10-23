"""Source Precast Architectural Facade Feature Fin & Sunshade Louver Shadow Authority.

Extracts candidate precast concrete feature fins, horizontal/vertical sunshades,
aerofoil solar shading louvers, and facade attachment geometry from source drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class FacadeFinSunshadeCandidate:
    candidate_id: str
    sheet_id: str
    fin_type: str
    material: str
    fin_width_mm: Optional[float]
    fin_depth_mm: Optional[float]
    fin_spacing_mm: Optional[float]
    blade_angle_deg: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "fin_type": self.fin_type,
            "material": self.material,
            "fin_width_mm": self.fin_width_mm,
            "fin_depth_mm": self.fin_depth_mm,
            "fin_spacing_mm": self.fin_spacing_mm,
            "blade_angle_deg": self.blade_angle_deg,
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


def parse_facade_fin_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ARCHITECTURAL FIN",
        "PRECAST FIN",
        "FEATURE FIN",
        "FACADE FIN",
        "SUNSHADE",
        "SOLAR BLADE",
        "AEROFOIL",
        "SHADING BLADE",
        "FACADE BLADE",
    ]
    has_trigger = any(t in upper for t in triggers) or bool(re.search(r"\b(?:PRECAST|FACADE|FEATURE|SOLAR)\s*FINS?\b", upper))
    if not has_trigger:
        return None

    # Avoid false positive with "FINISH" or "FINAL"
    if "FINISH" in upper and not any(t in upper for t in triggers):
        return None

    # Fin type
    if "AEROFOIL" in upper:
        fin_type = "AEROFOIL_LOUVER"
    elif "HORIZONTAL" in upper or "SUNSHADE" in upper:
        fin_type = "HORIZONTAL_SUNSHADE"
    elif "VERTICAL" in upper or "FIN" in upper:
        fin_type = "VERTICAL_FIN"
    else:
        fin_type = "SOLID_BLADE"

    # Material
    if "ALUMINIUM" in upper or "ALUMINUM" in upper or "ALUM" in upper:
        material = "EXTRUDED_ALUMINIUM"
    elif "UHPC" in upper:
        material = "UHPC"
    elif "GRP" in upper or "FRP" in upper:
        material = "GRP"
    else:
        material = "PRECAST_CONCRETE"

    # Dimensions W x D
    dim_match = re.search(r"(\d{2,4})\s*(?:W|MM\s*W|WIDE)?\s*[xX]\s*(\d{2,4})\s*(?:D|MM\s*D|DEEP)?", clean)
    single_match = re.search(r"(\d{2,4})\s*MM\s*(?:AEROFOIL|BLADE|FIN)", upper)
    fin_width_mm = None
    fin_depth_mm = None
    if dim_match:
        fin_width_mm = float(dim_match.group(1))
        fin_depth_mm = float(dim_match.group(2))
    elif single_match:
        fin_depth_mm = float(single_match.group(1))

    # Spacing (e.g. "@ 900 CTS" or "AT 1200MM CENTRES")
    spacing_match = re.search(r"(?:@|AT|\b)\s*(\d{3,4})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS)\b", upper)
    fin_spacing_mm = float(spacing_match.group(1)) if spacing_match else None

    # Blade angle (e.g. "45 DEG" or "30° TILT")
    angle_match = re.search(r"(\d{1,2})\s*(?:DEG|DEGREES|°)", upper)
    blade_angle_deg = float(angle_match.group(1)) if angle_match else None

    return {
        "raw_text": clean,
        "fin_type": fin_type,
        "material": material,
        "fin_width_mm": fin_width_mm,
        "fin_depth_mm": fin_depth_mm,
        "fin_spacing_mm": fin_spacing_mm,
        "blade_angle_deg": blade_angle_deg,
    }


def evaluate_facade_fin_sunshade_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[FacadeFinSunshadeCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_facade_fin_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_ffs_{i+1:03d}"
        cand = FacadeFinSunshadeCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            fin_type=parsed["fin_type"],
            material=parsed["material"],
            fin_width_mm=parsed["fin_width_mm"],
            fin_depth_mm=parsed["fin_depth_mm"],
            fin_spacing_mm=parsed["fin_spacing_mm"],
            blade_angle_deg=parsed["blade_angle_deg"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
