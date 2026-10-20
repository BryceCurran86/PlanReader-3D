"""Source Precast Concrete Core Wall Splice Shoe & NMB Splice Sleeve Shadow Authority.

Extracts candidate precast shear wall bolted splice shoes, grouted NMB splice sleeves,
anchor bolts, and panel vertical connection geometry from structural drawings.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class PrecastWallSpliceCandidate:
    candidate_id: str
    sheet_id: str
    splice_type: str
    bar_size: Optional[str]
    bolt_diameter: Optional[str]
    grout_strength_mpa: Optional[float]
    shoe_recess_mm: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "splice_type": self.splice_type,
            "bar_size": self.bar_size,
            "bolt_diameter": self.bolt_diameter,
            "grout_strength_mpa": self.grout_strength_mpa,
            "shoe_recess_mm": self.shoe_recess_mm,
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


def parse_wall_splice_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SPLICE SHOE",
        "WALL SHOE",
        "NMB SPLICE",
        "GROUTED SPLICE",
        "PRECAST WALL SPLICE",
        "REBAR SPLICE SLEEVE",
        "TENSION SPLICE SHOE",
        "SPLICE SLEEVE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Splice type
    if "SHOE" in upper:
        splice_type = "BOLTED_WALL_SHOE"
    elif "NMB" in upper or "SLEEVE" in upper:
        splice_type = "GROUTED_SPLICE_SLEEVE"
    elif "DUCT" in upper:
        splice_type = "GROUTED_CORRUGATED_DUCT"
    else:
        splice_type = "MECHANICAL_COUPLER"

    # Bar size (e.g. "N32", "N28", "N24")
    bar_match = re.search(r"\b([NRnr]\d{2})\b", clean)
    bar_size = bar_match.group(1).upper() if bar_match else None

    # Bolt diameter (e.g. "M30", "M24", "M36")
    bolt_match = re.search(r"\b(M\d{2})\b", clean)
    bolt_diameter = bolt_match.group(1).upper() if bolt_match else None

    # Grout strength (e.g. "80MPA", "100 MPA")
    grout_match = re.search(r"(\d{2,3})\s*MPA\b", upper)
    grout_strength_mpa = float(grout_match.group(1)) if grout_match else 80.0

    # Shoe recess (e.g. "150MM RECESS", "200MM POCKET")
    recess_match = re.search(r"(\d{2,3})\s*MM\s*(?:RECESS|POCKET|BLOCKOUT)", upper)
    shoe_recess_mm = float(recess_match.group(1)) if recess_match else (150.0 if "SHOE" in upper else None)

    return {
        "raw_text": clean,
        "splice_type": splice_type,
        "bar_size": bar_size,
        "bolt_diameter": bolt_diameter,
        "grout_strength_mpa": grout_strength_mpa,
        "shoe_recess_mm": shoe_recess_mm,
    }


def evaluate_precast_splice_shoe_sleeve_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[PrecastWallSpliceCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_wall_splice_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_pss_{i+1:03d}"
        cand = PrecastWallSpliceCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            splice_type=parsed["splice_type"],
            bar_size=parsed["bar_size"],
            bolt_diameter=parsed["bolt_diameter"],
            grout_strength_mpa=parsed["grout_strength_mpa"],
            shoe_recess_mm=parsed["shoe_recess_mm"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
