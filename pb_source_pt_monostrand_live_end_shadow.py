"""
Source Post-Tensioned Concrete Monostrand Live End Anchorage Pocket Shadow Authority.

Extracts and validates post-tensioned slab and beam edge live end anchorage pockets,
strand diameters, pocket blockout geometry, bursting zone reinforcement,
and grout infill specifications strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PTMonostrandLiveEndCallout:
    raw_text: str
    strand_diameter_mm: float
    tendon_type: str
    pocket_width_mm: float
    pocket_depth_mm: float
    bursting_reinforcement: str
    grout_infill_type: str
    edge_cover_mm: float
    position: Tuple[float, float] = (0.0, 0.0)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def snap_point(x: float, y: float, snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    """Snap coordinates to discrete precision grid."""
    if snap_tol <= 0.0:
        return (x, y)
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_pt_monostrand_live_end_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "LIVE END",
        "STRESSING POCKET",
        "PT ANCHORAGE",
        "MONOSTRAND ANCHOR",
        "TENDON ANCHORAGE",
        "LIVE-END ANCHOR",
        "STRESSING RECESS",
        "SLAB EDGE ANCHORAGE",
        "PT STRESSING",
        "ANCHORAGE POCKET",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Strand diameter: 12.7mm or 15.2mm
    dia_match = re.search(r"\b(12\.7|15\.2|12\.5|15\.7)\s*(?:MM)?\b", upper)
    if dia_match:
        strand_dia = float(dia_match.group(1))
    elif "0.5\"" in upper or "0.5 IN" in upper or "1/2\"" in upper:
        strand_dia = 12.7
    elif "0.6\"" in upper or "0.6 IN" in upper:
        strand_dia = 15.2
    else:
        strand_dia = 12.7

    # Tendon type: unbonded monostrand vs bonded multistrand/flat duct
    if "BONDED" in upper and "UNBONDED" not in upper:
        tendon_type = "BONDED_FLAT_DUCT"
    else:
        tendon_type = "UNBONDED_MONOSTRAND"

    # Recess / Pocket blockout dimensions (e.g. "120X70MM POCKET", "150X75 BLOCKOUT", "100X60")
    recess_match = re.search(r"\b(\d{2,3})\s*[xX]\s*(\d{2,3})\s*(?:MM)?\s*(?:POCKET|BLOCKOUT|RECESS)?", upper)
    if recess_match:
        pocket_w = float(recess_match.group(1))
        pocket_d = float(recess_match.group(2))
    else:
        pocket_w = 120.0
        pocket_d = 70.0

    # Bursting reinforcement: helical spiral vs hairpin stirrup
    if any(k in upper for k in ["HAIRPIN", "U-BAR", "STIRRUP", "TIE"]):
        bursting = "HAIRPIN_STIRRUP"
    else:
        bursting = "HELICAL_SPIRAL"

    # Grout infill type
    if "EPOXY" in upper:
        grout = "EPOXY_GROUT"
    elif "DRY-PACK" in upper or "DRY PACK" in upper or "MORTAR" in upper:
        grout = "DRY_PACK_MORTAR"
    else:
        grout = "NON_SHRINK_GROUT"

    # Edge cover / edge distance (e.g. "65MM COVER", "75MM EDGE DISTANCE", "50MM COVER")
    cover_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:COVER|EDGE|RECESS)", upper)
    cover_mm = float(cover_match.group(1)) if cover_match else 65.0

    return {
        "raw_text": clean,
        "strand_diameter_mm": strand_dia,
        "tendon_type": tendon_type,
        "pocket_width_mm": pocket_w,
        "pocket_depth_mm": pocket_d,
        "bursting_reinforcement": bursting,
        "grout_infill_type": grout,
        "edge_cover_mm": cover_mm,
    }


def evaluate_pt_monostrand_live_end_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[PTMonostrandLiveEndCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[PTMonostrandLiveEndCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_pt_monostrand_live_end_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            PTMonostrandLiveEndCallout(
                raw_text=parsed["raw_text"],
                strand_diameter_mm=parsed["strand_diameter_mm"],
                tendon_type=parsed["tendon_type"],
                pocket_width_mm=parsed["pocket_width_mm"],
                pocket_depth_mm=parsed["pocket_depth_mm"],
                bursting_reinforcement=parsed["bursting_reinforcement"],
                grout_infill_type=parsed["grout_infill_type"],
                edge_cover_mm=parsed["edge_cover_mm"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "anchor_standard": "AS3600-PT-LIVE-END",
                },
            )
        )

    return results
