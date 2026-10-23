"""
Source Precast Concrete Corbel & Elastomeric Bearing Pad Shadow Authority.

Extracts and validates precast column corbel geometries (projection/depth mm), elastomeric bearing pads,
Shore A hardness, vertical shear capacity (kN), and steel shims strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class CorbelBearingPadCallout:
    raw_text: str
    corbel_projection_mm: float
    corbel_depth_mm: float
    bearing_pad_material: str
    pad_thickness_mm: float
    shore_a_hardness: int
    design_shear_kn: float
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


def parse_corbel_bearing_pad_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CORBEL",
        "COLUMN BRACKET",
        "BEARING PAD",
        "ELASTOMERIC PAD",
        "NEOPRENE PAD",
        "BEAM SEAT",
        "CORBEL SEAT",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Corbel projection mm
    proj_mm = 300.0
    proj_match = re.search(r"(\d{2,4})\s*(?:MM)?\s*(?:PROJ|PROJECTION|WIDE|WIDTH)", upper)
    if proj_match:
        proj_mm = float(proj_match.group(1))

    # Corbel overall depth mm
    depth_mm = 500.0
    depth_match = re.search(r"(\d{2,4})\s*(?:MM)?\s*(?:DEEP|DEPTH)", upper)
    if depth_match:
        depth_mm = float(depth_match.group(1))

    # Bearing pad material
    if "STEEL" in upper and ("REINFORCED" in upper or "LAMINATED" in upper or "SHIM" in upper):
        pad_mat = "STEEL_REINFORCED_LAMINATED_BEARING"
    elif "PTFE" in upper or "TEFLON" in upper or "SLIDING" in upper:
        pad_mat = "PTFE_SLIDING_PAD"
    elif "NEOPRENE" in upper or "ELASTOMERIC" in upper:
        pad_mat = "PLAIN_ELASTOMERIC_NEOPRENE_PAD"
    else:
        pad_mat = "PLAIN_ELASTOMERIC_NEOPRENE_PAD"

    # Pad thickness mm
    pad_thk = 15.0
    thk_match = re.search(r"(\d{1,2})\s*(?:MM)?\s*(?:THICK|THK|PAD)", upper)
    if thk_match:
        val = float(thk_match.group(1))
        if val <= 60.0:
            pad_thk = val
    else:
        mm_match = re.search(r"(\d{1,2})\s*MM\b", upper)
        if mm_match:
            val = float(mm_match.group(1))
            if val <= 60.0:
                pad_thk = val

    # Shore A hardness
    hardness = 60
    hard_match = re.search(r"SHORE\s*A?\s*(\d{2})", upper)
    if hard_match:
        hardness = int(hard_match.group(1))
    else:
        dur_match = re.search(r"(\d{2})\s*DUROMETER", upper)
        if dur_match:
            hardness = int(dur_match.group(1))

    # Vertical shear design capacity kN
    shear_kn = 250.0
    shear_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:KN|KILONEWTON)", upper)
    if shear_match:
        shear_kn = float(shear_match.group(1))

    return {
        "corbel_projection_mm": proj_mm,
        "corbel_depth_mm": depth_mm,
        "bearing_pad_material": pad_mat,
        "pad_thickness_mm": pad_thk,
        "shore_a_hardness": hardness,
        "design_shear_kn": shear_kn,
    }


class SourceCorbelBearingPadShadowAuthority:
    """Authority for extracting precast corbels and elastomeric bearing pads in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[CorbelBearingPadCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[CorbelBearingPadCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_corbel_bearing_pad_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["bearing_pad_material"], parsed["corbel_projection_mm"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = CorbelBearingPadCallout(
                raw_text=text,
                corbel_projection_mm=parsed["corbel_projection_mm"],
                corbel_depth_mm=parsed["corbel_depth_mm"],
                bearing_pad_material=parsed["bearing_pad_material"],
                pad_thickness_mm=parsed["pad_thickness_mm"],
                shore_a_hardness=parsed["shore_a_hardness"],
                design_shear_kn=parsed["design_shear_kn"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
