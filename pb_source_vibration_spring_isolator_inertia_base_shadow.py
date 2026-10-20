"""
Source Mechanical Vibration Spring Isolator & Inertia Base Shadow Authority.

Extracts and validates vibration spring isolators, static deflection (mm), load capacity (kg),
concrete inertia base frames (depth mm), neoprene pads, and seismic snubbers strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class VibrationSpringIsolatorCallout:
    raw_text: str
    isolator_type: str
    static_deflection_mm: float
    load_capacity_kg: float
    inertia_base_included: bool
    inertia_base_depth_mm: float
    neoprene_pad_thickness_mm: float
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


def parse_vibration_spring_isolator_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SPRING ISOLATOR",
        "VIBRATION ISOLATOR",
        "INERTIA BASE",
        "INERTIA FRAME",
        "SPRING MOUNT",
        "SEISMIC SPRING",
        "STATIC DEFLECTION",
        "VIBRATION MOUNT",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Isolator type
    if "HOUSED" in upper or "ENCLOSED" in upper:
        iso_type = "HOUSED_SPRING_ISOLATOR_WITH_SNUBBER"
    elif "SEISMIC" in upper or "RESTRAINED" in upper or "SNUBBER" in upper:
        iso_type = "SEISMIC_RESTRAINED_SPRING_MOUNT"
    else:
        iso_type = "OPEN_SPRING_ISOLATOR"

    # Static deflection mm (typically 25mm, 50mm, 75mm)
    deflection_mm = 25.0
    def_match = re.search(r"(\d{2})\s*(?:MM)?\s*(?:DEFLECTION|STATIC\s*DEFLECTION)", upper)
    if def_match:
        val = float(def_match.group(1))
        if 10 <= val <= 100:
            deflection_mm = val

    # Load capacity kg
    load_kg = 500.0
    load_match = re.search(r"(\d{3,5})\s*(?:KG|KILOGRAM)", upper)
    if load_match:
        load_kg = float(load_match.group(1))
    else:
        kn_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:KN|KILONEWTON)", upper)
        if kn_match:
            load_kg = round(float(kn_match.group(1)) * 101.97, 1)

    # Inertia base included & frame depth mm
    has_inertia = any(k in upper for k in ["INERTIA BASE", "INERTIA FRAME", "CONCRETE BASE", "C-CHANNEL FRAME"])
    base_depth = 0.0
    if has_inertia:
        base_depth = 150.0  # default 150mm channel
        depth_match = re.search(r"(\d{2,3})\s*(?:MM)?\s*(?:DEEP|THICK|DEPTH|C-CHANNEL|CHANNEL)", upper)
        if depth_match:
            d_val = float(depth_match.group(1))
            if 100 <= d_val <= 400:
                base_depth = d_val

    # Neoprene pad thickness mm
    pad_thk = 10.0
    pad_match = re.search(r"(\d{1,2})\s*(?:MM)?\s*(?:NEOPRENE|RUBBER|ACOUSTIC\s*PAD|FRICTION\s*PAD)", upper)
    if pad_match:
        pad_thk = float(pad_match.group(1))

    return {
        "isolator_type": iso_type,
        "static_deflection_mm": deflection_mm,
        "load_capacity_kg": load_kg,
        "inertia_base_included": has_inertia,
        "inertia_base_depth_mm": base_depth,
        "neoprene_pad_thickness_mm": pad_thk,
    }


class SourceVibrationSpringIsolatorInertiaBaseShadowAuthority:
    """Authority for extracting vibration spring isolators and inertia bases in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[VibrationSpringIsolatorCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[VibrationSpringIsolatorCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_vibration_spring_isolator_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["isolator_type"], parsed["load_capacity_kg"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = VibrationSpringIsolatorCallout(
                raw_text=text,
                isolator_type=parsed["isolator_type"],
                static_deflection_mm=parsed["static_deflection_mm"],
                load_capacity_kg=parsed["load_capacity_kg"],
                inertia_base_included=parsed["inertia_base_included"],
                inertia_base_depth_mm=parsed["inertia_base_depth_mm"],
                neoprene_pad_thickness_mm=parsed["neoprene_pad_thickness_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
