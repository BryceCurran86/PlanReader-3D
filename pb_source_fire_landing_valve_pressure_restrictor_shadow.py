"""Fire Protection Wet / Dry Riser Landing Valve & Pressure Restrictor Shadow Authority.

Deterministic shadow extraction authority for wet and dry riser fire landing valves,
pressure restricting devices (PRO), PRVs, and fire hydrant enclosures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FireLandingValveCandidate:
    """Extracted fire landing valve or pressure restrictor candidate."""
    item_id: str
    valve_tag: str
    valve_pattern: str  # "OBLIQUE", "RIGHT_ANGLE", "BIB_NOSE", "STANDARD"
    system_service: str  # "WET_RISER", "DRY_RISER", "COMBINED_STANDPIPE", "HYDRANT"
    inlet_size_mm: int  # usually 65mm / DN65
    coupling_type: str  # "STORZ", "BS336_INSTANTANEOUS", "NH_THREAD", "BIC", "STANDARD"
    pressure_control: str  # "PRESSURE_REDUCING_VALVE", "RESTRICTING_ORIFICE", "FIXED_ORIFICE", "NONE"
    cabinet_type: str  # "RECESSED_CABINET", "SURFACE_CABINET", "EXPOSED", "STANDARD"
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "valve_tag": self.valve_tag,
            "valve_pattern": self.valve_pattern,
            "system_service": self.system_service,
            "inlet_size_mm": self.inlet_size_mm,
            "coupling_type": self.coupling_type,
            "pressure_control": self.pressure_control,
            "cabinet_type": self.cabinet_type,
            "coordinates": self.coordinates,
            "raw_text": self.raw_text,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    """Snap point coordinates to the nearest grid step."""
    return (
        round(round(pt[0] / tolerance) * tolerance, 3),
        round(round(pt[1] / tolerance) * tolerance, 3),
    )


def extract_landing_valves(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[FireLandingValveCandidate]:
    """Extract fire landing valves and pressure restrictors deterministically."""
    results: List[FireLandingValveCandidate] = []
    processed_count = 0

    size_pattern = re.compile(r"\b(?:DN\s*(\d{2})|(\d{2})\s*MM|2\.5(?:\s*INCH|\"))\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:HLV|LV|FH|HV|DRV|WRV)[-_]?\d{1,2}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"flv_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIRE HOSE REEL ONLY", "SPRINKLER HEAD", "GAS SOLENOID",
            "DRAIN VALVE ONLY", "DOMESTIC WATER BIB TAP"
        ]):
            continue

        is_landing_valve = any(k in upper_text for k in [
            "LANDING VALVE", "FIRE LANDING VALVE", "HYDRANT LANDING VALVE",
            "STANDPIPE VALVE", "FIRE HYDRANT VALVE", "DRY RISER OUTLET", "WET RISER OUTLET"
        ]) or (tag_pattern.search(text) is not None and ("RISER" in upper_text or "HYDRANT" in upper_text or "VALVE" in upper_text))

        if not is_landing_valve:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "HLV"

        # Valve pattern
        valve_pattern = "STANDARD"
        if "OBLIQUE" in upper_text:
            valve_pattern = "OBLIQUE"
        elif "RIGHT ANGLE" in upper_text or "90 DEG" in upper_text or "ANGLE VALVE" in upper_text:
            valve_pattern = "RIGHT_ANGLE"
        elif "BIB NOSE" in upper_text or "BIB-NOSE" in upper_text:
            valve_pattern = "BIB_NOSE"

        # System service
        system_service = "HYDRANT"
        if "WET RISER" in upper_text or "WET STANDPIPE" in upper_text:
            system_service = "WET_RISER"
        elif "DRY RISER" in upper_text or "DRY STANDPIPE" in upper_text:
            system_service = "DRY_RISER"
        elif "COMBINED" in upper_text:
            system_service = "COMBINED_STANDPIPE"

        # Inlet size (default 65mm / DN65 standard for fire service)
        inlet_size_mm = 65
        s_match = size_pattern.search(text)
        if s_match:
            if s_match.group(1):
                inlet_size_mm = int(s_match.group(1))
            elif s_match.group(2):
                inlet_size_mm = int(s_match.group(2))

        # Coupling type
        coupling_type = "STANDARD"
        if "STORZ" in upper_text:
            coupling_type = "STORZ"
        elif "BS336" in upper_text or "INSTANTANEOUS" in upper_text:
            coupling_type = "BS336_INSTANTANEOUS"
        elif "NH" in upper_text or "NATIONAL HOSE" in upper_text:
            coupling_type = "NH_THREAD"
        elif "BIC" in upper_text:
            coupling_type = "BIC"

        # Pressure control
        pressure_control = "NONE"
        if "PRV" in upper_text or "PRESSURE REDUCING" in upper_text:
            pressure_control = "PRESSURE_REDUCING_VALVE"
        elif "PRO" in upper_text or "PRESSURE RESTRICTING" in upper_text or "RESTRICTOR" in upper_text:
            pressure_control = "RESTRICTING_ORIFICE"
        elif "ORIFICE PLATE" in upper_text or "FIXED ORIFICE" in upper_text:
            pressure_control = "FIXED_ORIFICE"

        # Cabinet
        cabinet_type = "EXPOSED"
        if "RECESSED" in upper_text or "FLUSH" in upper_text:
            cabinet_type = "RECESSED_CABINET"
        elif "SURFACE" in upper_text or "CABINET" in upper_text:
            cabinet_type = "SURFACE_CABINET"

        candidate = FireLandingValveCandidate(
            item_id=item_id,
            valve_tag=tag,
            valve_pattern=valve_pattern,
            system_service=system_service,
            inlet_size_mm=inlet_size_mm,
            coupling_type=coupling_type,
            pressure_control=pressure_control,
            cabinet_type=cabinet_type,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
