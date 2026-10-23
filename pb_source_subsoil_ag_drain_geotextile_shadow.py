"""
Source Underground Subsoil Ag Drain & Geotextile Sock Shadow Authority.

Extracts and validates agricultural subsoil drainage runs (ag pipe), pipe diameters (DN65-DN160),
corrugated slotted profiles, class stiffness (Class 400/1000), geotextile filter socks, and aggregate backfill strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SubsoilAgDrainGeotextileCallout:
    raw_text: str
    pipe_diameter_dn: str
    pipe_profile: str
    class_stiffness: str
    geotextile_filter_sock: str
    gravel_backfill_depth_mm: float
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


def parse_subsoil_ag_drain_geotextile_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "AG PIPE",
        "AG-PIPE",
        "AG DRAIN",
        "AGRICULTURAL DRAIN",
        "SUBSOIL DRAIN",
        "SUBSOIL PIPE",
        "SLOTTED DRAIN",
        "PERFORATED DRAIN",
        "GEOTEXTILE SOCK",
        "FILTER SOCK",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Pipe diameter DN
    dn_match = re.search(r"\bDN\s*(\d{2,3})\b", upper)
    pipe_dn = f"DN{dn_match.group(1)}" if dn_match else "DN100"

    # Pipe profile
    if "UNSLOTTED" in upper or "SOLID CARRIER" in upper or "NON-PERFORATED" in upper:
        profile = "UNSLOTTED_CARRIER"
    elif "SMOOTH" in upper:
        profile = "SMOOTH_BORE_PERFORATED"
    elif "SLOTTED" in upper or "PERFORATED" in upper or "CORRUGATED" in upper or "AG" in upper:
        profile = "SLOTTED_PERFORATED_CORRUGATED"
    else:
        profile = "SLOTTED_PERFORATED_CORRUGATED"

    # Class stiffness
    if "1000" in upper or "CLASS 1000" in upper or "HEAVY DUTY" in upper:
        stiffness = "CLASS_1000_HEAVY_DUTY"
    elif "400" in upper or "CLASS 400" in upper:
        stiffness = "CLASS_400_STANDARD"
    else:
        stiffness = "CLASS_400_STANDARD"

    # Geotextile filter sock
    if "POLYESTER" in upper or "SEAMLESS" in upper or "KNITTED" in upper:
        sock = "SEAMLESS_KNITTED_POLYESTER_SLEEVE"
    elif "NO SOCK" in upper or "BARE" in upper or "WITHOUT SOCK" in upper:
        sock = "NONE_GRAVEL_SURROUND_ONLY"
    elif "SOCK" in upper or "GEOTEXTILE" in upper or "FILTER" in upper:
        sock = "NON_WOVEN_GEOTEXTILE_FILTER_SOCK"
    else:
        sock = "NON_WOVEN_GEOTEXTILE_FILTER_SOCK"

    # Gravel backfill depth mm
    gravel_mm = 300.0
    g_match = re.search(r"(\d{2,4})\s*(?:MM)?\s*(?:GRAVEL|AGGREGATE|BED|BEDDING|SURROUND)", upper)
    if g_match:
        gravel_mm = float(g_match.group(1))
    else:
        g_after = re.search(r"(?:GRAVEL|AGGREGATE|BED|BEDDING|SURROUND)\s*(?:[A-Z]+\s+)?(\d{2,4})\s*(?:MM)?", upper)
        if g_after:
            gravel_mm = float(g_after.group(1))

    return {
        "pipe_diameter_dn": pipe_dn,
        "pipe_profile": profile,
        "class_stiffness": stiffness,
        "geotextile_filter_sock": sock,
        "gravel_backfill_depth_mm": gravel_mm,
    }


class SourceSubsoilAgDrainGeotextileShadowAuthority:
    """Authority for extracting and managing subsoil agricultural drains in shadow mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[SubsoilAgDrainGeotextileCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[SubsoilAgDrainGeotextileCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_subsoil_ag_drain_geotextile_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["pipe_diameter_dn"], parsed["geotextile_filter_sock"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = SubsoilAgDrainGeotextileCallout(
                raw_text=text,
                pipe_diameter_dn=parsed["pipe_diameter_dn"],
                pipe_profile=parsed["pipe_profile"],
                class_stiffness=parsed["class_stiffness"],
                geotextile_filter_sock=parsed["geotextile_filter_sock"],
                gravel_backfill_depth_mm=parsed["gravel_backfill_depth_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
