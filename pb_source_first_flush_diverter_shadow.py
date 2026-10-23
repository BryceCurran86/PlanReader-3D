"""
Source Rainwater Harvesting First Flush Diverter Shadow Authority.

Extracts and validates first flush rainwater diverters, collection chamber volumes (L),
pipe diameters (DN), slow-release bleed valves, and leaf screen filter assemblies strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FirstFlushDiverterCallout:
    raw_text: str
    pipe_diameter_dn: str
    chamber_volume_litres: float
    diverter_type: str
    drain_bleed_mechanism: str
    filter_mesh_screen_type: str
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


def parse_first_flush_diverter_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "FIRST FLUSH",
        "ROOF FLUSH DIVERTER",
        "RAINWATER DIVERTER",
        "FIRST-FLUSH",
        "FLUSH DIVERTER",
        "DOWNPIPE DIVERTER",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Pipe diameter DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    pipe_dn = f"DN{dn_match.group(1)}" if dn_match else "DN100"

    # Diverter type
    if "COMMERCIAL" in upper or "HIGH VOLUME" in upper or "MULTI-PIPE" in upper:
        diverter_type = "COMMERCIAL_HIGH_VOLUME"
    elif "IN-GROUND" in upper or "INGROUND" in upper or "PIT" in upper:
        diverter_type = "IN_GROUND_VERTICAL_CHAMBER"
    elif "WALL MOUNT" in upper or "DOWNPIPE" in upper or "POST" in upper:
        diverter_type = "WALL_MOUNTED_POST_DOWNPIPE"
    else:
        diverter_type = "WALL_MOUNTED_POST_DOWNPIPE"

    # Chamber volume in litres
    vol_litres = 0.0
    vol_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:LITRES|LITRE|L\b)", upper)
    if vol_match:
        vol_litres = float(vol_match.group(1))
    elif "COMMERCIAL" in diverter_type:
        vol_litres = 200.0
    else:
        vol_litres = 50.0  # standard domestic/commercial downpipe first flush capacity

    # Drain bleed mechanism
    if "ELECTRONIC" in upper or "TIMER" in upper or "SOLENOID" in upper:
        bleed_mech = "ELECTRONIC_TIMER_PURGE"
    elif "MANUAL" in upper or "BALL VALVE" in upper:
        bleed_mech = "MANUAL_DRAIN_VALVE"
    elif "SLOW RELEASE" in upper or "BLEED" in upper or "ORIFICE" in upper or "DRIP" in upper:
        bleed_mech = "SLOW_RELEASE_BLEED_CONTROL_VALVE"
    else:
        bleed_mech = "SLOW_RELEASE_BLEED_CONTROL_VALVE"

    # Filter mesh / screen type
    if "LEAF EATER" in upper or "RAIN HEAD" in upper:
        screen_type = "STAINLESS_STEEL_LEAF_EATER_SCREEN"
    elif "MESH CAGE" in upper or "STRAINER" in upper:
        screen_type = "PRIMARY_MESH_CAGE"
    elif "BALL FLOAT" in upper or "SEALING BALL" in upper:
        screen_type = "INTEGRAL_BALL_FLOAT"
    else:
        screen_type = "INTEGRAL_BALL_FLOAT"

    return {
        "pipe_diameter_dn": pipe_dn,
        "chamber_volume_litres": vol_litres,
        "diverter_type": diverter_type,
        "drain_bleed_mechanism": bleed_mech,
        "filter_mesh_screen_type": screen_type,
    }


class SourceFirstFlushDiverterShadowAuthority:
    """Authority for extracting and validating first flush diverter assemblies in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[FirstFlushDiverterCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[FirstFlushDiverterCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_first_flush_diverter_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["pipe_diameter_dn"], parsed["diverter_type"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = FirstFlushDiverterCallout(
                raw_text=text,
                pipe_diameter_dn=parsed["pipe_diameter_dn"],
                chamber_volume_litres=parsed["chamber_volume_litres"],
                diverter_type=parsed["diverter_type"],
                drain_bleed_mechanism=parsed["drain_bleed_mechanism"],
                filter_mesh_screen_type=parsed["filter_mesh_screen_type"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
