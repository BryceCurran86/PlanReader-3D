"""Source Structural Steel Cross-Bracing Gusset Plate & Slotted Pin Hole Shadow Authority.

Extracts candidate structural steel cross-bracing gusset plates, plate thicknesses,
bolt groups, slotted pin holes, and edge stiffener geometry from structural drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class SteelGussetCandidate:
    candidate_id: str
    sheet_id: str
    gusset_type: str
    plate_thickness_mm: Optional[float]
    bolt_spec: Optional[str]
    bolt_count: Optional[int]
    has_slotted_holes: bool
    has_edge_stiffener: bool
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "gusset_type": self.gusset_type,
            "plate_thickness_mm": self.plate_thickness_mm,
            "bolt_spec": self.bolt_spec,
            "bolt_count": self.bolt_count,
            "has_slotted_holes": self.has_slotted_holes,
            "has_edge_stiffener": self.has_edge_stiffener,
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


def parse_steel_gusset_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "GUSSET PLATE",
        "CROSS-BRACING GUSSET",
        "BRACING GUSSET",
        "TENSION ROD GUSSET",
        "PINNED GUSSET",
        "BRACED BAY GUSSET",
        "GUSSET PL",
    ]
    if not any(t in upper for t in triggers) and not ("GUSSET" in upper and "PLATE" in upper):
        return None

    # Gusset type
    if "CHEVRON" in upper or "V-BRACE" in upper or "K-BRACE" in upper:
        gusset_type = "CHEVRON_V_BRACE_GUSSET"
    elif "PIN" in upper or "ROD" in upper:
        gusset_type = "TENSION_ROD_PIN_GUSSET"
    elif "X-BRACE" in upper or "CENTER" in upper or "CENTRE" in upper:
        gusset_type = "X_BRACE_CENTER_GUSSET"
    else:
        gusset_type = "CORNER_BEAM_COLUMN_GUSSET"

    # Plate thickness (e.g. "20MM THICK", "16MM PL", "25MM PLATE")
    thick_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:THICK|PL\b|PLATE\b)", upper)
    plate_thickness_mm = float(thick_match.group(1)) if thick_match else None

    # Bolt count & spec (e.g. "6XM24 8.8/S" or "4XM20" or "8 BOLTS")
    count_match = re.search(r"\b(\d{1,2})\s*[xX]\s*(M\d{2}(?:\s*8\.8(?:/[Ss])?)?)\b", clean)
    bolt_count = None
    bolt_spec = None
    if count_match:
        bolt_count = int(count_match.group(1))
        bolt_spec = count_match.group(2).replace(" ", "")
    else:
        spec_match = re.search(r"\b(M\d{2})\b", clean)
        bolt_spec = spec_match.group(1).upper() if spec_match else None
        num_bolts = re.search(r"\b(\d{1,2})\s*BOLTS?\b", upper)
        bolt_count = int(num_bolts.group(1)) if num_bolts else None

    # Slotted holes
    has_slotted_holes = "SLOT" in upper or "SLOTTED" in upper or "OVERSIZED" in upper

    # Edge stiffener
    has_edge_stiffener = "STIFFENER" in upper or "STIFFENED" in upper or "FLANGED" in upper

    return {
        "raw_text": clean,
        "gusset_type": gusset_type,
        "plate_thickness_mm": plate_thickness_mm,
        "bolt_spec": bolt_spec,
        "bolt_count": bolt_count,
        "has_slotted_holes": has_slotted_holes,
        "has_edge_stiffener": has_edge_stiffener,
    }


def evaluate_steel_cross_bracing_gusset_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[SteelGussetCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_steel_gusset_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_cbg_{i+1:03d}"
        cand = SteelGussetCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            gusset_type=parsed["gusset_type"],
            plate_thickness_mm=parsed["plate_thickness_mm"],
            bolt_spec=parsed["bolt_spec"],
            bolt_count=parsed["bolt_count"],
            has_slotted_holes=parsed["has_slotted_holes"],
            has_edge_stiffener=parsed["has_edge_stiffener"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
