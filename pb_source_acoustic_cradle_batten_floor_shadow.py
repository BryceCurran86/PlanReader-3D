"""Source Acoustic Floating Timber Floor Battens & Cradle Shadow Authority.

Extracts candidate acoustic cradles, floating timber battens, subfloor void heights,
cavity insulation, decking thicknesses, and layout runs from architectural flooring plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class AcousticCradleFloorCandidate:
    candidate_id: str
    sheet_id: str
    cradle_material: str
    batten_profile_description: str
    batten_spacing_mm: float
    cradle_void_height_mm: float
    insulation_infill_thickness_mm: Optional[float]
    decking_thickness_mm: float
    perimeter_flanking_band_thickness_mm: float
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "cradle_material": self.cradle_material,
            "batten_profile_description": self.batten_profile_description,
            "batten_spacing_mm": self.batten_spacing_mm,
            "cradle_void_height_mm": self.cradle_void_height_mm,
            "insulation_infill_thickness_mm": self.insulation_infill_thickness_mm,
            "decking_thickness_mm": self.decking_thickness_mm,
            "perimeter_flanking_band_thickness_mm": self.perimeter_flanking_band_thickness_mm,
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


def parse_acoustic_cradle_floor_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ACOUSTIC CRADLE",
        "FLOATING BATTEN",
        "ACOUSTIC CRADLE FLOOR",
        "SPRUNG TIMBER FLOOR",
        "ACOUSTIC BATTEN",
        "CRADLE AND BATTEN",
        "RESILIENT CRADLE",
        "TIMBER SPORTS FLOOR",
        "CRADLE FLOOR",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Cradle material
    if "NEOPRENE" in upper or "ELASTOMER" in upper:
        cradle_mat = "ELASTOMERIC_NEOPRENE"
    elif "PEDESTAL" in upper or "SCREWJACK" in upper or "POLYPROPYLENE" in upper:
        cradle_mat = "POLYPROPYLENE_ADJUSTABLE"
    else:
        cradle_mat = "RECYCLED_CRUMB_RUBBER"

    # Batten profile (e.g. "45x45", "45x70", "50x50")
    prof_match = re.search(r"\b(\d{2}\s*[X*×]\s*\d{2})\b", upper)
    batten_prof = prof_match.group(1).replace(" ", "").lower() if prof_match else "45x45"

    # Batten spacing (e.g. "@ 400 CTS", "@ 450 CTS", "@ 600MM C/C")
    space_match = re.search(r"(?:@|\bAT\b)?\s*(\d{3})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS|SPACING)", upper)
    batten_spacing = float(space_match.group(1)) if space_match else 400.0

    # Cradle void height (e.g. "50MM VOID", "35MM CRADLE", "75MM CAVITY")
    void_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:VOID|CAVITY|CRADLE|RISER)?\b", upper)
    cradle_void = float(void_match.group(1)) if void_match else 50.0

    # Insulation infill (e.g. "25MM MINERAL WOOL", "50MM INSULATION", "25MM QUILT")
    insul_match = re.search(r"\b(\d{2})\s*MM\s*(?:MINERAL|WOOL|INSULATION|QUILT|POLYESTER|BATT)\b", upper)
    insul_thick = float(insul_match.group(1)) if insul_match else None

    # Decking thickness (e.g. "22MM T&G", "18MM PLYWOOD", "22MM FLOORBOARD")
    deck_match = re.search(r"\b(\d{2})\s*MM\s*(?:T&G|TIMBER|PLYWOOD|CHIPBOARD|FLOORBOARD|DECK|BOARD)\b", upper)
    deck_thick = float(deck_match.group(1)) if deck_match else 22.0

    # Perimeter flanking band (e.g. "10MM FLANKING STRIP", "15MM FLANKING BAND", "10MM PERIMETER FOAM")
    flank_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:FLANKING|PERIMETER)\b", upper)
    flank_thick = float(flank_match.group(1)) if flank_match else 10.0

    return {
        "raw_text": clean,
        "cradle_material": cradle_mat,
        "batten_profile_description": batten_prof,
        "batten_spacing_mm": batten_spacing,
        "cradle_void_height_mm": cradle_void,
        "insulation_infill_thickness_mm": insul_thick,
        "decking_thickness_mm": deck_thick,
        "perimeter_flanking_band_thickness_mm": flank_thick,
    }


def evaluate_acoustic_cradle_batten_floor_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[AcousticCradleFloorCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_acoustic_cradle_floor_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_cbf_{i+1:03d}"
        cand = AcousticCradleFloorCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            cradle_material=parsed["cradle_material"],
            batten_profile_description=parsed["batten_profile_description"],
            batten_spacing_mm=parsed["batten_spacing_mm"],
            cradle_void_height_mm=parsed["cradle_void_height_mm"],
            insulation_infill_thickness_mm=parsed["insulation_infill_thickness_mm"],
            decking_thickness_mm=parsed["decking_thickness_mm"],
            perimeter_flanking_band_thickness_mm=parsed["perimeter_flanking_band_thickness_mm"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
