"""
Source Sanitary Sewer Reflux Valve & Overflow Relief Gully Shadow Authority.

Extracts and validates sanitary overflow relief gullies (ORG), sewer reflux non-return valves,
pipe sizes (DN100-DN150), pop-up loose grates, flapper mechanisms, and freeboard clearances strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SewerRefluxValveOrgCallout:
    raw_text: str
    fixture_type: str
    pipe_diameter_dn: str
    grate_type: str
    valve_mechanism: str
    min_freeboard_clearance_mm: float
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


def parse_sewer_reflux_valve_org_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "OVERFLOW RELIEF GULLY",
        "REFLUX VALVE",
        "BACKWATER VALVE",
        "ORG",
        "O.R.G.",
        "SEWER REFLUX",
        "SURCHARGE GULLY",
        "OVERFLOW GULLY",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Pipe diameter DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    pipe_dn = f"DN{dn_match.group(1)}" if dn_match else "DN100"

    # Fixture type
    has_org = any(k in upper for k in ["ORG", "O.R.G.", "OVERFLOW RELIEF", "OVERFLOW GULLY", "SURCHARGE GULLY"])
    has_reflux = any(k in upper for k in ["REFLUX", "BACKWATER", "NON-RETURN", "CHECK VALVE"])

    if has_org and has_reflux:
        fixture = "COMBINED_ORG_WITH_REFLUX_VALVE"
    elif has_reflux:
        fixture = "SEWER_REFLUX_BACKWATER_VALVE"
    else:
        fixture = "OVERFLOW_RELIEF_GULLY_ORG"

    # Grate type
    if "CAST IRON" in upper or "C.I." in upper:
        grate = "CAST_IRON_HINGED_GRATE"
    elif "BRASS" in upper:
        grate = "BRASS_LOCKABLE_SURCHARGE_GRATE"
    elif "POP-UP" in upper or "LOOSE" in upper or "PLASTIC" in upper or "PVC" in upper or has_org:
        grate = "LOOSE_POP_UP_PLASTIC_GRATE"
    else:
        grate = "LOOSE_POP_UP_PLASTIC_GRATE"

    # Valve mechanism
    if "BALL" in upper or "DUAL" in upper:
        valve = "DUAL_BALL_FLOAT_BACKWATER"
    elif "FLAPPER" in upper or "SWING" in upper or has_reflux:
        valve = "SWING_FLAPPER_NON_RETURN"
    else:
        valve = "NONE_GRAVITY_OPEN"

    # Minimum freeboard clearance mm (standard 75mm above unpaved or 150mm below fixture spill)
    freeboard = 75.0
    fb_match = re.search(r"(\d{2,3})\s*(?:MM)?\s*(?:FREEBOARD|CLEARANCE|ABOVE\s*GROUND)", upper)
    if fb_match:
        freeboard = float(fb_match.group(1))

    return {
        "fixture_type": fixture,
        "pipe_diameter_dn": pipe_dn,
        "grate_type": grate,
        "valve_mechanism": valve,
        "min_freeboard_clearance_mm": freeboard,
    }


class SourceSewerRefluxValveOrgShadowAuthority:
    """Authority for extracting sanitary sewer reflux valves and ORGs in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[SewerRefluxValveOrgCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[SewerRefluxValveOrgCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_sewer_reflux_valve_org_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["fixture_type"], parsed["pipe_diameter_dn"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = SewerRefluxValveOrgCallout(
                raw_text=text,
                fixture_type=parsed["fixture_type"],
                pipe_diameter_dn=parsed["pipe_diameter_dn"],
                grate_type=parsed["grate_type"],
                valve_mechanism=parsed["valve_mechanism"],
                min_freeboard_clearance_mm=parsed["min_freeboard_clearance_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
