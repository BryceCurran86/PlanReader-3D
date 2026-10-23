"""
Source Roof Parapet Overflow Scupper & Chute Shadow Authority.

Extracts and validates roof parapet emergency overflow scuppers, chute dimensions (W x H mm),
invert heights (mm), discharge capacities (L/s), and sheet metal linings strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ParapetOverflowScupperCallout:
    raw_text: str
    scupper_type: str
    width_mm: float
    height_mm: float
    invert_elevation_above_sole_mm: float
    overflow_capacity_lps: float
    sheet_metal_material: str
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


def parse_parapet_overflow_scupper_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "OVERFLOW SCUPPER",
        "PARAPET SCUPPER",
        "ROOF SCUPPER",
        "EMERGENCY OVERFLOW",
        "GUTTER OVERFLOW",
        "SCUPPER CHUTE",
        "OVERFLOW CHUTE",
        "BOX GUTTER OVERFLOW",
        "OVERFLOW SLEEVE",
        "OVERFLOW WEIR",
        "WEIR BOX",
        "PARAPET OVERFLOW",
    ]
    if not any(trig in upper for trig in triggers):
        if not ("SCUPPER" in upper or ("OVERFLOW" in upper and any(k in upper for k in ["ROOF", "GUTTER", "PARAPET", "WALL", "SLEEVE", "CHUTE"]))):
            return None

    # Scupper type
    if "CONCEALED" in upper or "WEIR BOX" in upper:
        scupper_type = "CONCEALED_OVERFLOW_WEIR_BOX"
    elif "SLEEVE" in upper or "THROUGH WALL" in upper:
        scupper_type = "THROUGH_WALL_OVERFLOW_SLEEVE"
    else:
        scupper_type = "PARAPET_WALL_OPEN_CHUTE_SCUPPER"

    # Dimensions: W x H mm
    w_mm = 300.0
    h_mm = 150.0
    dim_match = re.search(r"\b(\d{2,4})\s*[X*x]\s*(\d{2,3})(?:MM)?", upper)
    if dim_match:
        w_mm = float(dim_match.group(1))
        h_mm = float(dim_match.group(2))

    # Invert elevation above sole mm (e.g. "50MM ABOVE SOLE", "75MM INVERT")
    inv_mm = 50.0
    inv_match = re.search(r"(\d{2,3})\s*(?:MM)?\s*(?:ABOVE\s*SOLE|INVERT|ABOVE\s*GUTTER)", upper)
    if inv_match:
        inv_mm = float(inv_match.group(1))

    # Overflow capacity L/s
    cap_lps = 0.0
    cap_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS)", upper)
    if cap_match:
        cap_lps = float(cap_match.group(1))
    else:
        # Standard broad-crested weir approximation: Q ~ 1.7 * b * H^(1.5)
        # for b in m and head ~ 0.05m -> Q ~ 1.7 * (w_mm*1e-3) * (0.05^1.5) * 1000 ~ 19 * (w_mm*1e-3)
        cap_lps = round((w_mm / 1000.0) * 20.0, 1)

    # Sheet metal material
    if "316" in upper or "STAINLESS" in upper:
        mat = "STAINLESS_STEEL_316"
    elif "COPPER" in upper:
        mat = "COPPER_SHEET"
    elif "COLORBOND" in upper or "COLOURBOND" in upper:
        mat = "COLORBOND_STEEL"
    else:
        mat = "COLORBOND_STEEL"

    return {
        "scupper_type": scupper_type,
        "width_mm": w_mm,
        "height_mm": h_mm,
        "invert_elevation_above_sole_mm": inv_mm,
        "overflow_capacity_lps": cap_lps,
        "sheet_metal_material": mat,
    }


class SourceParapetOverflowScupperShadowAuthority:
    """Authority for extracting roof parapet overflow scuppers in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[ParapetOverflowScupperCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[ParapetOverflowScupperCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_parapet_overflow_scupper_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["width_mm"], parsed["scupper_type"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = ParapetOverflowScupperCallout(
                raw_text=text,
                scupper_type=parsed["scupper_type"],
                width_mm=parsed["width_mm"],
                height_mm=parsed["height_mm"],
                invert_elevation_above_sole_mm=parsed["invert_elevation_above_sole_mm"],
                overflow_capacity_lps=parsed["overflow_capacity_lps"],
                sheet_metal_material=parsed["sheet_metal_material"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
