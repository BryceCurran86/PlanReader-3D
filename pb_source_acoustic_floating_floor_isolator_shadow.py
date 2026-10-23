"""Source Acoustic Floating Floor Isolator Jack-Up Mount Shadow Authority.

Extracts candidate acoustic floating floor isolators, jack-up spring boxes, elastomeric mounts,
floating slab thicknesses, air gaps, and perimeter flanking isolation from acoustic/structural plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class AcousticFloatingFloorCandidate:
    candidate_id: str
    sheet_id: str
    isolator_type: str
    floating_slab_thickness_mm: Optional[float]
    air_cavity_height_mm: Optional[float]
    perimeter_isolation_thickness_mm: Optional[float]
    grid_spacing_mm: Optional[float]
    natural_frequency_hz: Optional[float]
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "isolator_type": self.isolator_type,
            "floating_slab_thickness_mm": self.floating_slab_thickness_mm,
            "air_cavity_height_mm": self.air_cavity_height_mm,
            "perimeter_isolation_thickness_mm": self.perimeter_isolation_thickness_mm,
            "grid_spacing_mm": self.grid_spacing_mm,
            "natural_frequency_hz": self.natural_frequency_hz,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_acoustic_floating_floor_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "FLOATING FLOOR",
        "ACOUSTIC FLOATING SLAB",
        "JACK-UP ISOLATOR",
        "JACK UP MOUNT",
        "JACK-UP MOUNT",
        "SPRING ISOLATOR CANISTER",
        "NEOPRENE FLOOR MOUNT",
        "PERIMETER ISOLATION BOARD",
        "FLOATING SLAB ISOLATOR",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Isolator type
    if "SPRING" in upper or "JACK" in upper or "CANISTER" in upper:
        isolator_type = "JACK_UP_SPRING_CANISTER"
    elif "SYLOMER" in upper or "REGUPOL" in upper or "MAT" in upper or "UNDERLAY" in upper:
        isolator_type = "POLYURETHANE_FOAM_MAT"
    else:
        isolator_type = "ELASTOMERIC_NEOPRENE_PAD"

    # Floating slab thickness (e.g. "150MM FLOATING SLAB", "100MM THK SLAB", "200MM CONCRETE")
    slab_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:THK\s*)?(?:FLOATING\s*)?(?:CONCRETE\s*)?SLAB\b", upper)
    floating_slab = float(slab_match.group(1)) if slab_match else 150.0

    # Air cavity height / gap (e.g. "50MM AIR GAP", "75MM AIR CAVITY", "50MM VOID")
    gap_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:AIR\s*)?(?:GAP|CAVITY|VOID)\b", upper)
    air_gap = float(gap_match.group(1)) if gap_match else 50.0

    # Perimeter isolation strip thickness (e.g. "20MM PERIMETER BOARD", "15MM FLANKING STRIP")
    flank_match = re.search(r"\b(\d{1,2})\s*MM\s*(?:PERIMETER|FLANKING|ISOLATION BOARD|EDGE STRIP)\b", upper)
    flank_thick = float(flank_match.group(1)) if flank_match else 20.0

    # Grid spacing (e.g. "@ 1200MM CTS", "1200X1200 GRID", "@ 1000 CTS")
    grid_match = re.search(r"(?:@|\bAT\b)?\s*(\d{3,4})\s*(?:MM)?\s*(?:CTS|C\/C|CENTRES|CENTERS|GRID)", upper)
    grid_spacing = float(grid_match.group(1)) if grid_match else 1200.0

    # Natural frequency (e.g. "5.0 HZ", "3.5HZ NATURAL FREQUENCY")
    fn_match = re.search(r"\b(\d{1,2}(?:\.\d)?)\s*HZ\b", upper)
    nat_freq = float(fn_match.group(1)) if fn_match else (4.5 if isolator_type == "JACK_UP_SPRING_CANISTER" else 8.0)

    return {
        "raw_text": clean,
        "isolator_type": isolator_type,
        "floating_slab_thickness_mm": floating_slab,
        "air_cavity_height_mm": air_gap,
        "perimeter_isolation_thickness_mm": flank_thick,
        "grid_spacing_mm": grid_spacing,
        "natural_frequency_hz": nat_freq,
    }


def evaluate_acoustic_floating_floor_isolator_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[AcousticFloatingFloorCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_acoustic_floating_floor_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_aff_{i+1:03d}"
        cand = AcousticFloatingFloorCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            isolator_type=parsed["isolator_type"],
            floating_slab_thickness_mm=parsed["floating_slab_thickness_mm"],
            air_cavity_height_mm=parsed["air_cavity_height_mm"],
            perimeter_isolation_thickness_mm=parsed["perimeter_isolation_thickness_mm"],
            grid_spacing_mm=parsed["grid_spacing_mm"],
            natural_frequency_hz=parsed["natural_frequency_hz"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
