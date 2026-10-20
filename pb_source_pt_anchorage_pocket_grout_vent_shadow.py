"""Source Post-Tensioned Concrete Anchorage Pocket & Grout Vent Shadow Authority.

Extracts candidate PT slab stressing pockets, live/dead end anchorages,
strand counts, and high/low point grout vent geometry from structural PT plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class PtAnchoragePocketCandidate:
    candidate_id: str
    sheet_id: str
    anchorage_type: str
    strand_count: Optional[int]
    strand_diameter_mm: float
    pocket_recess_mm: Optional[float]
    grout_vent_type: Optional[str]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "anchorage_type": self.anchorage_type,
            "strand_count": self.strand_count,
            "strand_diameter_mm": self.strand_diameter_mm,
            "pocket_recess_mm": self.pocket_recess_mm,
            "grout_vent_type": self.grout_vent_type,
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


def parse_pt_anchorage_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "POST-TENSION",
        "POST TENSION",
        "PT ANCHOR",
        "STRESSING POCKET",
        "GROUT VENT",
        "LIVE END",
        "DEAD END",
        "TENDON DUCT VENT",
        "PT POCKET",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Anchorage type
    if "VENT" in upper:
        anchorage_type = "GROUT_VENT_POINT"
    elif "COUPLER" in upper:
        anchorage_type = "INTERMEDIATE_COUPLER"
    elif "DEAD" in upper or "FIXED" in upper:
        anchorage_type = "DEAD_END_FIXED"
    else:
        anchorage_type = "LIVE_END_STRESSING"

    # Strand count (e.g. "4-STRAND", "5 STRAND", "12 STRAND")
    strand_match = re.search(r"\b(\d{1,2})\s*(?:-|\s*)STRAND\b", upper)
    strand_count = int(strand_match.group(1)) if strand_match else None

    # Strand diameter (e.g. "12.7MM" or "15.2MM")
    dia_match = re.search(r"\b(12\.7|15\.2)\s*MM\b", upper)
    strand_diameter_mm = float(dia_match.group(1)) if dia_match else 12.7

    # Pocket recess (e.g. "100MM RECESSED POCKET" or "75MM POCKET")
    recess_match = re.search(r"(\d{2,3})\s*MM\s*(?:RECESSED|RECESS|POCKET|BLOCKOUT)", upper)
    pocket_recess_mm = float(recess_match.group(1)) if recess_match else (100.0 if "POCKET" in upper else None)

    # Grout vent type
    if "HIGH" in upper:
        grout_vent_type = "HIGH_POINT_VENT"
    elif "LOW" in upper or "DRAIN" in upper:
        grout_vent_type = "LOW_POINT_DRAIN"
    elif "VENT" in upper:
        grout_vent_type = "INTERMEDIATE_VENT"
    else:
        grout_vent_type = None

    return {
        "raw_text": clean,
        "anchorage_type": anchorage_type,
        "strand_count": strand_count,
        "strand_diameter_mm": strand_diameter_mm,
        "pocket_recess_mm": pocket_recess_mm,
        "grout_vent_type": grout_vent_type,
    }


def evaluate_pt_anchorage_pocket_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[PtAnchoragePocketCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_pt_anchorage_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_ptp_{i+1:03d}"
        cand = PtAnchoragePocketCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            anchorage_type=parsed["anchorage_type"],
            strand_count=parsed["strand_count"],
            strand_diameter_mm=parsed["strand_diameter_mm"],
            pocket_recess_mm=parsed["pocket_recess_mm"],
            grout_vent_type=parsed["grout_vent_type"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
