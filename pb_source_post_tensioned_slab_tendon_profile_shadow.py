"""
Source Post-Tensioned Suspended Slab Tendon Profile & Drape Shadow Authority.

Extracts and validates PT tendon lines, strand counts per duct (3/4/5), high/low chair heights (mm),
slab thicknesses (mm), and duct types strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PtTendonProfileCallout:
    raw_text: str
    strand_count: int
    tendon_group_count: int
    high_point_chair_mm: float
    low_point_chair_mm: float
    slab_thickness_mm: float
    duct_type: str
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


def parse_pt_tendon_profile_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "TENDON",
        "PT SLAB",
        "POST TENSION",
        "POST-TENSION",
        "TENDON PROFILE",
        "DRAPE PROFILE",
        "CHAIR HEIGHT",
        "STRAND TENDON",
        "HIGH POINT",
        "LOW POINT",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Strand count per duct: e.g. "4-STRAND", "4 STRAND", "5 STRAND", "3 STRAND"
    strands = 4
    st_match = re.search(r"\b(\d)\s*(?:-|\s*)STRAND", upper)
    if st_match:
        val = int(st_match.group(1))
        if 2 <= val <= 9:
            strands = val
    else:
        s_match = re.search(r"(\d)\s*S\b", upper)
        if s_match:
            val = int(s_match.group(1))
            if 2 <= val <= 9:
                strands = val

    # Tendon group count: e.g. "2x 4-STRAND", "3 TENDONS"
    grp_count = 1
    grp_match = re.search(r"\b(\d+)\s*(?:[X*x]|\s*TENDON)", upper)
    if grp_match:
        grp_count = int(grp_match.group(1))

    # Slab thickness mm (e.g. "200MM SLAB", "220THK", "250 THICK")
    slab_mm = 200.0
    sl_match = re.search(r"(\d{3})\s*(?:MM)?\s*(?:SLAB|THK|THICK|DEPTH)", upper)
    if sl_match:
        s_val = float(sl_match.group(1))
        if 120 <= s_val <= 600:
            slab_mm = s_val

    # High point chair height mm (typically slab_thickness - 35mm cover)
    high_mm = round(slab_mm - 35.0)
    high_match = re.search(r"(?:HIGH|HP|TOP)\s*(?:POINT)?\s*[:=]?\s*(\d{2,3})\s*(?:MM)?", upper)
    if high_match:
        high_mm = float(high_match.group(1))

    # Low point chair height mm (typically 25mm to 35mm bottom cover)
    low_mm = 30.0
    low_match = re.search(r"(?:LOW|LP|BOT|BOTTOM)\s*(?:POINT)?\s*[:=]?\s*(\d{2,3})\s*(?:MM)?", upper)
    if low_match:
        low_mm = float(low_match.group(1))

    # Duct type
    if "STEEL" in upper or "GALV" in upper or "GALVANIZED" in upper:
        duct = "FLAT_GALVANIZED_STEEL_DUCT"
    elif "ROUND" in upper:
        duct = "ROUND_MULTI_STRAND_DUCT"
    else:
        duct = "FLAT_PLASTIC_CORRUGATED_DUCT"

    return {
        "strand_count": strands,
        "tendon_group_count": grp_count,
        "high_point_chair_mm": high_mm,
        "low_point_chair_mm": low_mm,
        "slab_thickness_mm": slab_mm,
        "duct_type": duct,
    }


class SourcePostTensionedSlabTendonProfileShadowAuthority:
    """Authority for extracting post-tensioned slab tendon profiles in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[PtTendonProfileCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[PtTendonProfileCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_pt_tendon_profile_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["strand_count"], parsed["high_point_chair_mm"], parsed["low_point_chair_mm"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = PtTendonProfileCallout(
                raw_text=text,
                strand_count=parsed["strand_count"],
                tendon_group_count=parsed["tendon_group_count"],
                high_point_chair_mm=parsed["high_point_chair_mm"],
                low_point_chair_mm=parsed["low_point_chair_mm"],
                slab_thickness_mm=parsed["slab_thickness_mm"],
                duct_type=parsed["duct_type"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
