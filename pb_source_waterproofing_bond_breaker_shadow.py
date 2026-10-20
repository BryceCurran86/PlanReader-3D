"""
Source Wet Area Waterproofing Membrane & Bond Breaker Fillet Shadow Authority.

Extracts and validates waterproofing membranes (Class I/II/III), bond breaker cove fillets (mm),
vertical upturn heights (mm), dry film thickness (DFT mm), and shower hob details strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class WaterproofingBondBreakerCallout:
    raw_text: str
    membrane_class: str
    bond_breaker_type: str
    fillet_size_mm: float
    upturn_height_mm: float
    dry_film_thickness_dft_mm: float
    hob_detail: str
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


def parse_waterproofing_bond_breaker_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "WATERPROOFING",
        "WATERPROOF",
        "BOND BREAKER",
        "COVE FILLET",
        "WET AREA MEMBRANE",
        "MEMBRANE UPTURN",
        "SHOWER WATERPROOFING",
        "BALCONY WATERPROOFING",
        "FILLET",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Membrane classification
    if "SHEET" in upper or "PVC" in upper or "BUTYL" in upper:
        mem_class = "PREFORMED_SHEET_MEMBRANE"
        dft = 1.5
    elif re.search(r"\b(?:CLASS\s*III|CLASS\s*3)\b", upper) or "POLYURETHANE" in upper or "LIQUID" in upper:
        mem_class = "CLASS_III_HIGH_EXTENSIBILITY_LIQUID"
        dft = 1.2
    elif re.search(r"\b(?:CLASS\s*II|CLASS\s*2)\b", upper):
        mem_class = "CLASS_II_MEDIUM_EXTENSIBILITY"
        dft = 1.2
    else:
        mem_class = "CLASS_III_HIGH_EXTENSIBILITY_LIQUID"
        dft = 1.2

    # DFT override if present (e.g. "1.5MM DFT", "1.2 DFT")
    dft_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:MM)?\s*DFT", upper)
    if dft_match:
        dft = float(dft_match.group(1))

    # Bond breaker type
    if "SILICONE" in upper:
        bb_type = "NEUTRAL_CURE_SILICONE_FILLET"
    elif "TAPE" in upper:
        bb_type = "REINFORCING_BOND_BREAKER_TAPE"
    else:
        bb_type = "ELASTOMERIC_POLYURETHANE_COVE_FILLET"

    # Fillet size mm (e.g. "12X12MM", "12MM FILLET", "15MM BOND BREAKER", "15X15 COVE FILLET")
    fillet_sz = 12.0
    dim_match = re.search(r"\b(\d{1,2})\s*[X*x]\s*(\d{1,2})\b", upper)
    if dim_match:
        fillet_sz = float(dim_match.group(1))
    else:
        sz_match = re.search(r"(\d{1,2})\s*MM\b", upper)
        if sz_match:
            val = float(sz_match.group(1))
            if 6 <= val <= 25:
                fillet_sz = val

    # Upturn height mm (e.g. "150MM UPTURN", "UPTURN 200MM", "1800MM IN SHOWER")
    upturn_mm = 150.0
    up_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:UPTURN|FLASHING|WALL\s*JUNCTION)", upper)
    if up_match:
        upturn_mm = float(up_match.group(1))
    else:
        up_after = re.search(r"(?:UPTURN|FLASHING)\s*(\d{3,4})\s*(?:MM)?", upper)
        if up_after:
            upturn_mm = float(up_after.group(1))
        elif "1800" in upper or "SHOWER" in upper:
            upturn_mm = 1800.0

    # Hob detail
    if "RECESS" in upper or "STEPDOWN" in upper or "SETDOWN" in upper:
        hob = "FLUSH_RECESS_STEPDOWN"
    elif "HOBLESS" in upper or "LEVEL THRESHOLD" in upper or "NO HOB" in upper:
        hob = "NO_HOB_LEVEL_THRESHOLD"
    elif "HOB" in upper:
        hob = "MASONRY_HOB_WATERPROOFED"
    else:
        hob = "FLUSH_RECESS_STEPDOWN"

    return {
        "membrane_class": mem_class,
        "bond_breaker_type": bb_type,
        "fillet_size_mm": fillet_sz,
        "upturn_height_mm": upturn_mm,
        "dry_film_thickness_dft_mm": dft,
        "hob_detail": hob,
    }


class SourceWaterproofingBondBreakerShadowAuthority:
    """Authority for extracting wet area waterproofing and bond breakers in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[WaterproofingBondBreakerCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[WaterproofingBondBreakerCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_waterproofing_bond_breaker_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["membrane_class"], parsed["fillet_size_mm"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = WaterproofingBondBreakerCallout(
                raw_text=text,
                membrane_class=parsed["membrane_class"],
                bond_breaker_type=parsed["bond_breaker_type"],
                fillet_size_mm=parsed["fillet_size_mm"],
                upturn_height_mm=parsed["upturn_height_mm"],
                dry_film_thickness_dft_mm=parsed["dry_film_thickness_dft_mm"],
                hob_detail=parsed["hob_detail"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
