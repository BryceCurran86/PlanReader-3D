"""
Source Commercial Kitchen Exhaust Canopy Hood & Baffle Filter Shadow Authority.

Extracts and validates commercial kitchen canopy hoods, dimensions (length/width mm),
baffle filter counts, exhaust airflow rates (L/s), makeup air plenums, and stainless steel grades strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class KitchenExhaustHoodCallout:
    raw_text: str
    hood_type: str
    length_mm: float
    width_mm: float
    exhaust_airflow_lps: float
    filter_count: int
    makeup_air_included: bool
    material_grade: str
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


def parse_kitchen_exhaust_hood_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "KITCHEN EXHAUST",
        "EXHAUST HOOD",
        "CANOPY HOOD",
        "BAFFLE FILTER",
        "RANGE HOOD",
        "GREASE HOOD",
        "EXHAUST CANOPY",
        "COOKING CANOPY",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Hood type
    if "ISLAND" in upper or "DOUBLE" in upper or "V-BANK" in upper:
        hood = "ISLAND_V_BANK_CANOPY"
    elif "BACKSHELF" in upper or "LOW PROXIMITY" in upper:
        hood = "LOW_PROXIMITY_BACKSHELF_HOOD"
    elif "WALL" in upper or "CANOPY" in upper or "HOOD" in upper:
        hood = "WALL_MOUNTED_CANOPY"
    else:
        hood = "WALL_MOUNTED_CANOPY"

    # Dimensions: Length x Width mm (e.g. "2400X1200", "3000 X 1500MM")
    dim_match = re.search(r"(\d{3,4})\s*[X*x]\s*(\d{3,4})", upper)
    if dim_match:
        len_mm = float(dim_match.group(1))
        wid_mm = float(dim_match.group(2))
    else:
        len_mm = 2400.0
        wid_mm = 1200.0

    # Exhaust airflow L/s
    flow_lps = 0.0
    flow_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L/SEC)", upper)
    if flow_match:
        flow_lps = float(flow_match.group(1))
    else:
        m3_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:M3/H|M3/HR)", upper)
        if m3_match:
            flow_lps = round(float(m3_match.group(1)) / 3.6, 1)
        else:
            flow_lps = round(len_mm * 0.45, 1)  # rule of thumb ~450 L/s per linear metre

    # Filter count
    f_match = re.search(r"(\d+)\s*(?:NO\.|NOS\.)?\s*(?:BAFFLE|FILTER|GREASE\s*FILTER)", upper)
    if f_match:
        f_count = int(f_match.group(1))
    else:
        f_count = max(2, int(len_mm // 500))

    # Makeup air included
    makeup = any(k in upper for k in ["MAKEUP", "MAKE-UP", "COMPENSATING", "INDUCTION", "SUPPLY PLENUM"])

    # Material grade
    if "316" in upper:
        mat = "STAINLESS_STEEL_316"
    elif "304" in upper or "SS" in upper or "STAINLESS" in upper:
        mat = "STAINLESS_STEEL_304_NO4_FINISH"
    else:
        mat = "STAINLESS_STEEL_304_NO4_FINISH"

    return {
        "hood_type": hood,
        "length_mm": len_mm,
        "width_mm": wid_mm,
        "exhaust_airflow_lps": flow_lps,
        "filter_count": f_count,
        "makeup_air_included": makeup,
        "material_grade": mat,
    }


class SourceKitchenExhaustHoodShadowAuthority:
    """Authority for extracting commercial kitchen exhaust canopy hoods in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[KitchenExhaustHoodCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[KitchenExhaustHoodCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_kitchen_exhaust_hood_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["length_mm"], parsed["width_mm"], parsed["hood_type"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = KitchenExhaustHoodCallout(
                raw_text=text,
                hood_type=parsed["hood_type"],
                length_mm=parsed["length_mm"],
                width_mm=parsed["width_mm"],
                exhaust_airflow_lps=parsed["exhaust_airflow_lps"],
                filter_count=parsed["filter_count"],
                makeup_air_included=parsed["makeup_air_included"],
                material_grade=parsed["material_grade"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
