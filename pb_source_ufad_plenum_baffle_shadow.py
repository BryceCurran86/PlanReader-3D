"""Source Underfloor Air Distribution (UFAD) Plenum Baffle & Pressurization Partition Shadow Authority.

Extracts candidate raised access floor plenum air baffles, pressure partitions,
acoustic subfloor barriers, and gasketed boundary geometry from mechanical/interior plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import math
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class UfadPlenumBaffleCandidate:
    candidate_id: str
    sheet_id: str
    baffle_type: str
    material: str
    height_mm: Optional[float]
    gasket_seal: str
    differential_pressure_pa: Optional[float]
    points: List[Tuple[float, float]] = field(default_factory=list)
    length_pt: float = 0.0
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "baffle_type": self.baffle_type,
            "material": self.material,
            "height_mm": self.height_mm,
            "gasket_seal": self.gasket_seal,
            "differential_pressure_pa": self.differential_pressure_pa,
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


def parse_ufad_baffle_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "UFAD",
        "UNDERFLOOR AIR",
        "PLENUM BAFFLE",
        "PLENUM PARTITION",
        "PRESSURIZATION BAFFLE",
        "SUBFLOOR AIR BARRIER",
        "UFAD ZONE",
        "UNDERFLOOR ACOUSTIC",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Baffle type
    if "FIRE" in upper or "SMOKE" in upper:
        baffle_type = "FIRE_SMOKE_STOP"
    elif "ACOUSTIC" in upper:
        baffle_type = "ACOUSTIC_PLENUM_BARRIER"
    elif "THERMAL" in upper or "ZONE DIVIDER" in upper or "ZONE" in upper:
        baffle_type = "THERMAL_ZONE_DIVIDER"
    else:
        baffle_type = "AIR_PRESSURE_BAFFLE"

    # Material
    if "MINERAL" in upper:
        material = "MINERAL_FIBRE_BOARD"
    elif "CALCIUM" in upper:
        material = "CALCIUM_SILICATE"
    elif "GYPSUM" in upper or "PLASTERBOARD" in upper:
        material = "GYPSUM_BOARD"
    else:
        material = "GALVANIZED_SHEET_STEEL"

    # Height (e.g. "300H", "450MM HIGH", "300 DEEP")
    height_match = re.search(r"(\d{3})\s*(?:MM)?\s*(?:H|HIGH|HEIGHT|DEEP)\b", upper)
    height_mm = float(height_match.group(1)) if height_match else None

    # Gasket seal
    if "INTUMESCENT" in upper:
        gasket_seal = "INTUMESCENT_MASTIC"
    elif "ACOUSTIC SEAL" in upper or "ACOUSTIC SEALANT" in upper:
        gasket_seal = "ACOUSTIC_SEALANT"
    else:
        gasket_seal = "NEOPRENE_FOAM"

    # Differential pressure (e.g. "25 PA" or "12.5PA")
    pa_match = re.search(r"\b(\d{1,2}(?:\.\d)?)\s*PA\b", upper)
    differential_pressure_pa = float(pa_match.group(1)) if pa_match else None

    return {
        "raw_text": clean,
        "baffle_type": baffle_type,
        "material": material,
        "height_mm": height_mm,
        "gasket_seal": gasket_seal,
        "differential_pressure_pa": differential_pressure_pa,
    }


def evaluate_ufad_plenum_baffle_shadow(
    sheet_id: str,
    callouts: List[str],
    polylines: Optional[List[List[Tuple[float, float]]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[UfadPlenumBaffleCandidate]:
    candidates = []
    polys = polylines or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_ufad_baffle_callout(callout)
        if not parsed:
            continue

        pts = polys[i] if i < len(polys) else []
        snapped_pts = snap_polyline(pts)
        length = calculate_polyline_length(snapped_pts)

        cid = f"{sheet_id}_upb_{i+1:03d}"
        cand = UfadPlenumBaffleCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            baffle_type=parsed["baffle_type"],
            material=parsed["material"],
            height_mm=parsed["height_mm"],
            gasket_seal=parsed["gasket_seal"],
            differential_pressure_pa=parsed["differential_pressure_pa"],
            points=snapped_pts,
            length_pt=length,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
