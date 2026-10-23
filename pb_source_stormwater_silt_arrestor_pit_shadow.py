"""
Source Civil Stormwater Silt Arrestor Pit & Ductile Iron Grate Shadow Authority.

Extracts and validates stormwater silt arrestor pits, dimensions (L x W mm),
sump storage depth below invert (mm), ductile iron grate load classes (Class A/B/D), and baffle hoods strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class StormwaterSiltArrestorPitCallout:
    raw_text: str
    pit_type: str
    internal_length_mm: float
    internal_width_mm: float
    sump_depth_below_invert_mm: float
    grate_load_class: str
    baffle_weir_included: bool
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


def parse_stormwater_silt_arrestor_pit_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SILT ARRESTOR",
        "SILT PIT",
        "SEDIMENT PIT",
        "SILT TRAP",
        "SEDIMENT TRAP",
        "SUMP PIT",
        "SILT BOX",
        "STORMWATER SILT",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Pit Type
    if "POLY" in upper or "PLASTIC" in upper:
        pit_type = "POLYETHYLENE_SILT_ARRESTOR"
    elif "INSITU" in upper or "IN-SITU" in upper or "POURED" in upper:
        pit_type = "CAST_IN_SITU_SEDIMENT_SUMP_PIT"
    else:
        pit_type = "PRECAST_CONCRETE_SILT_PIT"

    # Dimensions: L x W mm (e.g. "600X600", "900X900", "600 X 600MM")
    len_mm = 600.0
    wid_mm = 600.0
    dim_match = re.search(r"\b(\d{3,4})\s*[X*x]\s*(\d{3,4})", upper)
    if dim_match:
        len_mm = float(dim_match.group(1))
        wid_mm = float(dim_match.group(2))

    # Sump depth below invert mm (e.g. "300MM SUMP", "450MM SILT STORAGE", "600MM BELOW INVERT")
    sump_mm = 300.0
    sump_match = re.search(r"(\d{2,4})\s*(?:MM)?\s*(?:SUMP|SILT\s*STORAGE|BELOW\s*INVERT|SILT\s*SUMP)", upper)
    if sump_match:
        val = float(sump_match.group(1))
        if 150 <= val <= 1500:
            sump_mm = val

    # Grate Load Class
    if "CLASS D" in upper or "HEAVY DUTY" in upper or "ROADWAY" in upper:
        grate_class = "CLASS_D_HEAVY_DUTY_ROADWAY"
    elif "CLASS B" in upper or "CAR PARK" in upper or "LIGHT DUTY" in upper:
        grate_class = "CLASS_B_CAR_PARK"
    elif "CLASS A" in upper or "PEDESTRIAN" in upper:
        grate_class = "CLASS_A_PEDESTRIAN"
    elif "CLASS C" in upper:
        grate_class = "CLASS_B_CAR_PARK"
    else:
        grate_class = "CLASS_D_HEAVY_DUTY_ROADWAY"

    # Baffle weir / oil hood included
    has_baffle = any(k in upper for k in ["BAFFLE", "WEIR", "HOOD", "OIL TRAP", "TRASH SCREEN"])

    return {
        "pit_type": pit_type,
        "internal_length_mm": len_mm,
        "internal_width_mm": wid_mm,
        "sump_depth_below_invert_mm": sump_mm,
        "grate_load_class": grate_class,
        "baffle_weir_included": has_baffle,
    }


class SourceStormwaterSiltArrestorPitShadowAuthority:
    """Authority for extracting stormwater silt arrestor pits in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[StormwaterSiltArrestorPitCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[StormwaterSiltArrestorPitCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_stormwater_silt_arrestor_pit_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["internal_length_mm"], parsed["internal_width_mm"], parsed["grate_load_class"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = StormwaterSiltArrestorPitCallout(
                raw_text=text,
                pit_type=parsed["pit_type"],
                internal_length_mm=parsed["internal_length_mm"],
                internal_width_mm=parsed["internal_width_mm"],
                sump_depth_below_invert_mm=parsed["sump_depth_below_invert_mm"],
                grate_load_class=parsed["grate_load_class"],
                baffle_weir_included=parsed["baffle_weir_included"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
