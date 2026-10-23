"""Source Hydraulic Stormwater Sump Silt Trap & Floating Oil Skimmer Shadow Authority.

Extracts candidate stormwater sump pits, sediment/silt traps, floating oil skimmers,
coalescing plates, and grate load classes from civil/hydraulic drainage plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class StormwaterSiltTrapCandidate:
    candidate_id: str
    sheet_id: str
    separator_type: str
    pit_dimensions_description: str
    silt_storage_depth_mm: Optional[float]
    trash_screen_present: bool
    grate_class: str
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "separator_type": self.separator_type,
            "pit_dimensions_description": self.pit_dimensions_description,
            "silt_storage_depth_mm": self.silt_storage_depth_mm,
            "trash_screen_present": self.trash_screen_present,
            "grate_class": self.grate_class,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_stormwater_silt_trap_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SILT TRAP",
        "STORMWATER SUMP",
        "SEDIMENT TRAP",
        "OIL SKIMMER",
        "COALESCING PLATE",
        "HYDROCARBON BAFFLE",
        "SUMP PIT SILT",
        "STORMWATER SILT PIT",
        "SEDIMENT SUMP",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Separator / device type
    if "COALESCING" in upper or "CPS" in upper:
        sep_type = "COALESCING_PLATE_PACK"
    elif "SKIMMER" in upper or "FLOATING" in upper:
        sep_type = "FLOATING_WEIR_SKIMMER"
    elif ("BAFFLE" in upper or "HYDROCARBON" in upper) and not ("WITHOUT BAFFLE" in upper or "NO BAFFLE" in upper):
        sep_type = "HYDROCARBON_BAFFLE"
    else:
        sep_type = "SEDIMENT_SUMP_ONLY"

    # Pit dimensions (e.g. "900X900", "1200X1200", "900 SQ")
    dim_match = re.search(r"\b(\d{3,4}\s*[X*×]\s*\d{3,4})\b", upper)
    sq_match = re.search(r"\b(\d{3,4})\s*(?:SQ|SQUARE)\b", upper)
    if dim_match:
        pit_dim = dim_match.group(1).replace(" ", "")
    elif sq_match:
        s = sq_match.group(1)
        pit_dim = f"{s}x{s}"
    else:
        pit_dim = "900x900"

    # Silt storage depth below invert (e.g. "450MM SILT SUMP", "300MM DEEP SILT TRAP", "600MM SUMP")
    depth_match = re.search(r"\b(\d{3,4})\s*MM\s*(?:DEEP\s*)?(?:SILT|SEDIMENT|SUMP)?", upper)
    silt_depth = float(depth_match.group(1)) if depth_match else 450.0

    # Trash screen
    trash_screen = any(k in upper for k in ["TRASH SCREEN", "BASKET", "STRAINER", "LITTER BASKET", "LEAF BASKET"])

    # Grate class
    if "CLASS B" in upper:
        grate_class = "CLASS_B"
    elif "SOLID" in upper or "COVER" in upper:
        grate_class = "SOLID_COVER"
    else:
        grate_class = "CLASS_D"  # default heavy duty trafficable grate

    return {
        "raw_text": clean,
        "separator_type": sep_type,
        "pit_dimensions_description": pit_dim,
        "silt_storage_depth_mm": silt_depth,
        "trash_screen_present": trash_screen,
        "grate_class": grate_class,
    }


def evaluate_stormwater_silt_trap_skimmer_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[StormwaterSiltTrapCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_stormwater_silt_trap_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_sts_{i+1:03d}"
        cand = StormwaterSiltTrapCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            separator_type=parsed["separator_type"],
            pit_dimensions_description=parsed["pit_dimensions_description"],
            silt_storage_depth_mm=parsed["silt_storage_depth_mm"],
            trash_screen_present=parsed["trash_screen_present"],
            grate_class=parsed["grate_class"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
