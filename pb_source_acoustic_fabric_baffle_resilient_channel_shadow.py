"""Source Acoustic Wall Fabric Baffle & Resilient Channel Shadow Authority.

Extracts candidate acoustic fabric-wrapped wall panels, sound absorbing baffles,
resilient channels, NRC ratings, and layout alignments from architectural interior plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class AcousticWallBaffleCandidate:
    candidate_id: str
    sheet_id: str
    panel_core_material: str
    panel_thickness_mm: float
    nrc_rating: float
    resilient_channel_type: str
    channel_spacing_mm: Optional[float]
    fabric_finish: str
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "panel_core_material": self.panel_core_material,
            "panel_thickness_mm": self.panel_thickness_mm,
            "nrc_rating": self.nrc_rating,
            "resilient_channel_type": self.resilient_channel_type,
            "channel_spacing_mm": self.channel_spacing_mm,
            "fabric_finish": self.fabric_finish,
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


def parse_acoustic_wall_baffle_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ACOUSTIC WALL PANEL",
        "FABRIC BAFFLE",
        "RESILIENT CHANNEL",
        "RC-1 CHANNEL",
        "RC-2 CHANNEL",
        "ACOUSTIC BAFFLE",
        "FABRIC WRAPPED PANEL",
        "SOUND ABSORBING PANEL",
        "ACOUSTIC WALL LINING",
        "ACOUSTIC PANEL",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Panel core material
    if "POLYESTER" in upper:
        core_material = "POLYESTER_FIBRE"
    elif "FOAM" in upper or "MELAMINE" in upper:
        core_material = "ACOUSTIC_FOAM"
    elif "TIMBER" in upper or "SLAT" in upper:
        core_material = "TIMBER_ACOUSTIC_SLAT"
    else:
        core_material = "FIBERGLASS_CORE"

    # Panel thickness (e.g. "50MM ACOUSTIC PANEL", "25MM THICK", "50MM FABRIC")
    thick_match = re.search(r"\b(\d{2})\s*MM\b", upper)
    panel_thick = float(thick_match.group(1)) if thick_match else 50.0

    # NRC rating (e.g. "NRC 0.85", "0.95 NRC", "NRC=1.00")
    nrc_match = re.search(r"NRC\s*(?:=|\s)?\s*(0\.\d{2}|1\.00?)", upper)
    if not nrc_match:
        nrc_match = re.search(r"\b(0\.\d{2}|1\.00?)\s*NRC\b", upper)
    nrc = float(nrc_match.group(1)) if nrc_match else 0.85

    # Resilient channel / mounting type
    if "RC-2" in upper or "DOUBLE LEG" in upper:
        channel_type = "RC_2_DOUBLE_LEG"
    elif "RC-1" in upper or "RESILIENT CHANNEL" in upper:
        channel_type = "RC_1_SINGLE_LEG"
    elif "CLIP" in upper or "ISOLATION CLIP" in upper:
        channel_type = "RESILIENT_CLIP"
    else:
        channel_type = "DIRECT_ADHESIVE"

    # Channel spacing (e.g. "@ 400 CTS", "@ 600MM C/C", "600 CTS")
    space_match = re.search(r"(?:@|\bAT\b)?\s*(\d{3})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS|SPACING)", upper)
    spacing = float(space_match.group(1)) if space_match else (600.0 if "RC" in channel_type or "CLIP" in channel_type else None)

    # Fabric finish
    if "VINYL" in upper:
        finish = "PERFORATED_VINYL"
    elif "FABRIC" in upper or "TEXTILE" in upper:
        finish = "ACOUSTIC_TEXTILE"
    else:
        finish = "UNFINISHED"

    return {
        "raw_text": clean,
        "panel_core_material": core_material,
        "panel_thickness_mm": panel_thick,
        "nrc_rating": nrc,
        "resilient_channel_type": channel_type,
        "channel_spacing_mm": spacing,
        "fabric_finish": finish,
    }


def evaluate_acoustic_fabric_baffle_resilient_channel_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[AcousticWallBaffleCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_acoustic_wall_baffle_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_awb_{i+1:03d}"
        cand = AcousticWallBaffleCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            panel_core_material=parsed["panel_core_material"],
            panel_thickness_mm=parsed["panel_thickness_mm"],
            nrc_rating=parsed["nrc_rating"],
            resilient_channel_type=parsed["resilient_channel_type"],
            channel_spacing_mm=parsed["channel_spacing_mm"],
            fabric_finish=parsed["fabric_finish"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
