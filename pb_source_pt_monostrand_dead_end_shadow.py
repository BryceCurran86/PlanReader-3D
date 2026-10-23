"""
Source Post-Tensioned Concrete Monostrand Dead End Onion Anchor Shadow Authority.

Extracts and validates internal post-tensioned dead-end onion anchors, swaged sleeves,
embedment bond lengths, bursting ties, and concrete covers strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PTMonostrandDeadEndCallout:
    raw_text: str
    strand_diameter_mm: float
    anchor_type: str
    embedment_length_mm: float
    restraint_support: str
    bursting_reinforcement: str
    min_cover_mm: float
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


def parse_pt_monostrand_dead_end_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "DEAD END",
        "DEAD-END",
        "ONION ANCHOR",
        "BULB ANCHOR",
        "SWAGED ANCHOR",
        "BLIND ANCHOR",
        "INTERNAL ANCHORAGE",
        "PASSIVE ANCHOR",
        "PT DEAD END",
        "NON-STRESSING END",
        "DEAD END ANCHORAGE",
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

    # Anchor type / geometry
    if any(k in upper for k in ["SWAGED", "BARREL", "COMPRESSION SLEEVE"]):
        anchor_type = "SWAGED_BARREL_SLEEVE"
    elif any(k in upper for k in ["BEARING PLATE", "DEAD END PLATE"]):
        anchor_type = "PLATE_DEAD_END"
    else:
        anchor_type = "HYDRAULIC_ONION_BULB"

    # Development / embedment length
    emb_match = re.search(r"\b(\d{3,4})\s*MM\s*(?:EMBEDMENT|DEV|BOND|LENGTH)?", upper)
    emb_len = float(emb_match.group(1)) if emb_match else 750.0

    # Restraint / support mechanism
    if "CHAIR" in upper:
        support = "CHAIR_SUPPORT"
    elif "MESH TIE" in upper:
        support = "MESH_TIE"
    else:
        support = "SPIRAL_SPRING_CLIP"

    # Bursting reinforcement
    if any(k in upper for k in ["HAIRPIN", "U-BAR", "BURSTING TIES", "STIRRUP"]):
        bursting = "N12_HAIRPIN_TIES"
    elif "HELIX" in upper or "HELICAL" in upper or ("SPIRAL" in upper and "CLIP" not in upper):
        bursting = "HELICAL_SPIRAL"
    else:
        bursting = "N12_HAIRPIN_TIES"

    # Minimum concrete cover
    cov_match = re.search(r"\b(\d{2})\s*MM\s*COVER\b", upper)
    cover_mm = float(cov_match.group(1)) if cov_match else 40.0

    return {
        "raw_text": clean,
        "strand_diameter_mm": strand_dia,
        "anchor_type": anchor_type,
        "embedment_length_mm": emb_len,
        "restraint_support": support,
        "bursting_reinforcement": bursting,
        "min_cover_mm": cover_mm,
    }


def evaluate_pt_monostrand_dead_end_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[PTMonostrandDeadEndCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[PTMonostrandDeadEndCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_pt_monostrand_dead_end_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            PTMonostrandDeadEndCallout(
                raw_text=parsed["raw_text"],
                strand_diameter_mm=parsed["strand_diameter_mm"],
                anchor_type=parsed["anchor_type"],
                embedment_length_mm=parsed["embedment_length_mm"],
                restraint_support=parsed["restraint_support"],
                bursting_reinforcement=parsed["bursting_reinforcement"],
                min_cover_mm=parsed["min_cover_mm"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "dead_end_standard": "AS3600-PT-DEAD-END",
                },
            )
        )

    return results
