"""
Source Cold Water Storage Tank Break Tank Level Transmitter & Spill Flange Shadow Authority.

Extracts and validates cold water break tanks, storage capacities (litres), continuous level transmitters,
overflow spill flanges (DN), and regulatory air gap types strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class BreakTankLevelSpillFlangeCallout:
    raw_text: str
    tank_type: str
    effective_capacity_litres: float
    level_transmitter_type: str
    overflow_spill_flange_dn: str
    air_gap_type: str
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


def parse_break_tank_level_spill_flange_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "BREAK TANK",
        "POTABLE WATER TANK",
        "WATER STORAGE TANK",
        "STORAGE TANK",
        "HEADER TANK",
        "RAINWATER TANK",
        "RECYCLED WATER TANK",
        "FIRE TANK",
        "SPILL FLANGE",
        "OVERFLOW FLANGE",
        "COLD WATER TANK",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("TANK" in upper or "STORAGE" in upper) and ("SPILL" in upper or "OVERFLOW" in upper or "AIR GAP" in upper)
    )
    if not has_trigger:
        return None

    # Tank classification
    if "FIRE" in upper:
        tank_type = "FIRE_WATER_STORAGE_TANK"
    elif any(k in upper for k in ["RAINWATER", "NON-POTABLE", "RECYCLED WATER"]):
        tank_type = "NON_POTABLE_RAINWATER_TANK"
    elif "HEADER" in upper:
        tank_type = "HEADER_TANK"
    else:
        tank_type = "BREAK_TANK_POTABLE"

    # Effective capacity (litres)
    cap_match = re.search(r"(\d{1,3}(?:,\d{3})+|\d+)\s*(?:L\b|LITRES?|LTRS?)", upper)
    if cap_match:
        raw_cap = cap_match.group(1).replace(",", "")
        capacity_l = float(raw_cap)
    else:
        capacity_l = 10000.0  # standard engineering default for commercial break tanks

    # Continuous level transmitter sensor
    if any(k in upper for k in ["HYDROSTATIC", "SUBMERSIBLE LEVEL", "PRESSURE TRANSMITTER"]):
        transmitter = "HYDROSTATIC_SUBMERSIBLE_PRESSURE"
    elif "ULTRASONIC" in upper:
        transmitter = "ULTRASONIC_NON_CONTACT"
    elif any(k in upper for k in ["RADAR", "GUIDED WAVE"]):
        transmitter = "RADAR_GUIDED_WAVE"
    elif any(k in upper for k in ["FLOAT", "CONDUCTIVITY"]):
        transmitter = "MULTI_POINT_CONDUCTIVITY_FLOAT"
    else:
        transmitter = "HYDROSTATIC_SUBMERSIBLE_PRESSURE"

    # Overflow spill flange diameter
    flange_match = re.search(r"(?:OVERFLOW|SPILL|FLANGE|DISCHARGE)\s*(?:SIZE|DN)?\s*:?\s*DN\s*(\d{2,3})", upper)
    if not flange_match:
        flange_match = re.search(r"\bDN\s*(\d{2,3})\s*(?:OVERFLOW|SPILL|FLANGE|DISCHARGE)", upper)
    if not flange_match:
        flange_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)

    if flange_match:
        flange_dn = f"DN{flange_match.group(1)}"
    else:
        flange_dn = "DN100"  # standard overflow spill flange

    # Air gap classification
    if any(k in upper for k in ["TYPE AB", "TYPE-AB"]):
        air_gap = "TYPE_AB_NON_CIRCULAR_OVERFLOW"
    elif any(k in upper for k in ["TYPE AF", "TYPE-AF"]):
        air_gap = "TYPE_AF_DROPLET_AIR_GAP"
    elif any(k in upper for k in ["TYPE AA", "TYPE-AA", "AIR GAP"]):
        air_gap = "TYPE_AA_AIR_GAP"
    else:
        air_gap = "TYPE_AA_AIR_GAP"

    return {
        "raw_text": clean,
        "tank_type": tank_type,
        "effective_capacity_litres": capacity_l,
        "level_transmitter_type": transmitter,
        "overflow_spill_flange_dn": flange_dn,
        "air_gap_type": air_gap,
    }


class SourceBreakTankLevelSpillFlangeShadowAuthority:
    """Authority for break tanks and spill flanges in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[BreakTankLevelSpillFlangeCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[BreakTankLevelSpillFlangeCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[BreakTankLevelSpillFlangeCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_break_tank_level_spill_flange_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = BreakTankLevelSpillFlangeCallout(
                raw_text=parsed["raw_text"],
                tank_type=parsed["tank_type"],
                effective_capacity_litres=parsed["effective_capacity_litres"],
                level_transmitter_type=parsed["level_transmitter_type"],
                overflow_spill_flange_dn=parsed["overflow_spill_flange_dn"],
                air_gap_type=parsed["air_gap_type"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
