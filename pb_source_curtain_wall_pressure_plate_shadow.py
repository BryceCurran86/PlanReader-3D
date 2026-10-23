"""Source Glazed Aluminium Curtain Wall Pressure Plate & Thermal Break Shadow Authority.

Extracts candidate curtain wall pressure plates, continuous thermal break isolators,
exterior snap-on beauty caps, glazing pocket widths, and mullion depths from facade drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class CurtainWallPressurePlateCandidate:
    candidate_id: str
    sheet_id: str
    thermal_isolator_type: str
    exterior_cap_profile: str
    mullion_depth_mm: float
    mullion_sightline_width_mm: float
    glazing_pocket_mm: float
    cap_projection_depth_mm: float
    pressure_screw_pitch_mm: float
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "thermal_isolator_type": self.thermal_isolator_type,
            "exterior_cap_profile": self.exterior_cap_profile,
            "mullion_depth_mm": self.mullion_depth_mm,
            "mullion_sightline_width_mm": self.mullion_sightline_width_mm,
            "glazing_pocket_mm": self.glazing_pocket_mm,
            "cap_projection_depth_mm": self.cap_projection_depth_mm,
            "pressure_screw_pitch_mm": self.pressure_screw_pitch_mm,
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


def parse_curtain_wall_pressure_plate_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CURTAIN WALL PRESSURE PLATE",
        "PRESSURE PLATE",
        "THERMAL BREAK",
        "THERMALLY BROKEN MULLION",
        "SNAP-ON CAP",
        "SNAP ON CAP",
        "BEAUTY CAP",
        "CURTAIN WALL CAP",
        "FACADE PRESSURE BAR",
        "CURTAIN WALL MULLION",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Thermal isolator type
    if "PVC" in upper:
        isolator = "RIGID_PVC_ISOLATOR"
    elif "EPDM" in upper:
        isolator = "EPDM_ISOLATOR_GASKET"
    else:
        isolator = "POLYAMIDE_STRUT"

    # Exterior cap profile
    if "AEROFOIL" in upper or "AIRFOIL" in upper:
        cap_profile = "AEROFOIL_FEATURE_CAP"
    elif "BULLNOSE" in upper:
        cap_profile = "BULLNOSE_CAP"
    elif "FLUSH" in upper or "NO CAP" in upper or "STRUCTURAL GLAZED" in upper:
        cap_profile = "FLUSH_SEAL_NO_CAP"
    else:
        cap_profile = "RECTANGULAR_BOX_CAP"

    # Mullion structural depth (e.g. "175MM MULLION", "200MM DEEP", "150MM SYSTEM")
    depth_match = re.search(r"\b(\d{3})\s*MM\s*(?:DEEP|MULLION|DEPTH|SYSTEM|BOX)?", upper)
    mullion_depth = float(depth_match.group(1)) if depth_match else 175.0

    # Sightline width (e.g. "50MM SIGHTLINE", "65MM WIDE", "50MM FACE")
    sight_match = re.search(r"\b(\d{2})\s*MM\s*(?:SIGHTLINE|FACE)\b", upper)
    sightline = float(sight_match.group(1)) if sight_match else 50.0

    # Glazing pocket width (e.g. "28MM DGU", "32MM IGU", "36MM POCKET", "42MM TRIPLE")
    pocket_match = re.search(r"\b(\d{2})\s*MM\s*(?:IGU|DGU|GLAZING|POCKET|GLASS|TRIPLE|DOUBLE)\b", upper)
    glazing_pocket = float(pocket_match.group(1)) if pocket_match else 28.0

    # Exterior cap projection (e.g. "100MM FEATURE CAP", "100MM AEROFOIL FEATURE CAP", "50MM CAP")
    cap_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:[A-Z\s]{0,20}?)\s*CAP\b", upper)
    cap_proj = float(cap_match.group(1)) if cap_match else (0.0 if cap_profile == "FLUSH_SEAL_NO_CAP" else 20.0)

    # Pressure screw pitch (e.g. "@ 250 CTS", "200MM PITCH", "@ 300 CTS")
    pitch_match = re.search(r"(?:@|\bAT\b)?\s*(\d{3})\s*(?:MM)?\s*(?:CTS|C\/C|PITCH|CENTRES|CENTERS)", upper)
    screw_pitch = float(pitch_match.group(1)) if pitch_match else 250.0

    return {
        "raw_text": clean,
        "thermal_isolator_type": isolator,
        "exterior_cap_profile": cap_profile,
        "mullion_depth_mm": mullion_depth,
        "mullion_sightline_width_mm": sightline,
        "glazing_pocket_mm": glazing_pocket,
        "cap_projection_depth_mm": cap_proj,
        "pressure_screw_pitch_mm": screw_pitch,
    }


def evaluate_curtain_wall_pressure_plate_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[CurtainWallPressurePlateCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_curtain_wall_pressure_plate_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_cwp_{i+1:03d}"
        cand = CurtainWallPressurePlateCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            thermal_isolator_type=parsed["thermal_isolator_type"],
            exterior_cap_profile=parsed["exterior_cap_profile"],
            mullion_depth_mm=parsed["mullion_depth_mm"],
            mullion_sightline_width_mm=parsed["mullion_sightline_width_mm"],
            glazing_pocket_mm=parsed["glazing_pocket_mm"],
            cap_projection_depth_mm=parsed["cap_projection_depth_mm"],
            pressure_screw_pitch_mm=parsed["pressure_screw_pitch_mm"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
