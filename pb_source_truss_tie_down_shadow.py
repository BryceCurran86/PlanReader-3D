"""
Source Structural Timber Roof Truss Tie-Down & Framing Anchor Shadow Authority.

Extracts and validates roof truss tie-down connectors (triple grips, cyclone straps, framing anchors),
wind classifications, characteristic uplift capacities (kN), and fastener specs strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class TrussTieDownCallout:
    raw_text: str
    bracket_type: str
    wind_rating: str
    fastener_description: str
    characteristic_uplift_kn: float
    strap_gauge_mm: float
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


def parse_truss_tie_down_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "TRUSS TIE-DOWN",
        "TRUSS TIE DOWN",
        "TIE DOWN",
        "TIE-DOWN",
        "TRIPLE GRIP",
        "CYCLONE STRAP",
        "FRAMING ANCHOR",
        "MULTI-GRIP",
        "MULTIGRIP",
        "TRUSS BOOT",
        "RAFTER TIE",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Bracket type
    if "CYCLONE" in upper or "STRAP" in upper:
        bracket = "CYCLONE_TIE_DOWN_STRAP"
        gauge = 1.0
        uplift = 8.5
    elif "TRIPLE GRIP" in upper or "TRIP-L-GRIP" in upper:
        bracket = "TRIPLE_GRIP_FRAMING_ANCHOR"
        gauge = 1.2
        uplift = 4.2
    elif "MULTI-GRIP" in upper or "MULTIGRIP" in upper:
        bracket = "MULTI_GRIP_UNIVERSAL_BRACKET"
        gauge = 1.0
        uplift = 3.8
    elif "BOOT" in upper:
        bracket = "TRUSS_BOOT_INTERNAL_BRACKET"
        gauge = 1.6
        uplift = 12.0
    elif "FRAMING ANCHOR" in upper:
        bracket = "TRIPLE_GRIP_FRAMING_ANCHOR"
        gauge = 1.2
        uplift = 4.5
    else:
        bracket = "TRIPLE_GRIP_FRAMING_ANCHOR"
        gauge = 1.2
        uplift = 4.2

    # Characteristic uplift capacity kN
    up_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:KN|KILONEWTON)", upper)
    if up_match:
        uplift = float(up_match.group(1))

    # Wind rating
    if any(k in upper for k in ["C2", "C3", "C4", "CYCLONIC"]):
        wind = "WIND_CLASS_C2_C3_CYCLONIC"
    elif any(k in upper for k in ["N4", "C1"]):
        wind = "WIND_CLASS_N4_C1"
    elif any(k in upper for k in ["N1", "N2", "N3"]):
        wind = "WIND_CLASS_N2_N3"
    else:
        wind = "WIND_CLASS_N2_N3"

    # Fastener description
    if "SCREW" in upper:
        fastener = "TEK_SCREWS_10_16_TYPE_17"
    elif "6 NAILS" in upper:
        fastener = "6_NAILS_30X2_8MM_PER_LEG"
    elif "4 NAILS" in upper:
        fastener = "4_NAILS_30X2_8MM_PER_LEG"
    else:
        fastener = "4_NAILS_30X2_8MM_PER_LEG"

    # Gauge override
    gauge_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:MM)?\s*(?:GAUGE|BMT)", upper)
    if gauge_match:
        val = float(gauge_match.group(1))
        if 0.5 <= val <= 3.0:
            gauge = val

    return {
        "bracket_type": bracket,
        "wind_rating": wind,
        "fastener_description": fastener,
        "characteristic_uplift_kn": uplift,
        "strap_gauge_mm": gauge,
    }


class SourceTrussTieDownShadowAuthority:
    """Authority for extracting timber roof truss tie-down brackets in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[TrussTieDownCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[TrussTieDownCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_truss_tie_down_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["bracket_type"], parsed["wind_rating"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = TrussTieDownCallout(
                raw_text=text,
                bracket_type=parsed["bracket_type"],
                wind_rating=parsed["wind_rating"],
                fastener_description=parsed["fastener_description"],
                characteristic_uplift_kn=parsed["characteristic_uplift_kn"],
                strap_gauge_mm=parsed["strap_gauge_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
