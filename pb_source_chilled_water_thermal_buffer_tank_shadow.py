"""Chilled Water / Condenser Water Thermal Storage Stratified Buffer Tank Shadow Authority.

Deterministic shadow extraction authority for HVAC chilled water buffer tanks,
stratified thermal storage, hydraulic separators, flow diffusers, and insulation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ChilledWaterBufferCandidate:
    """Extracted chilled water buffer tank candidate."""
    item_id: str
    tank_type: str  # "CHILLED_WATER_BUFFER", "HEATING_WATER_BUFFER", "THERMAL_STRATIFIED_STORAGE", "HYDRAULIC_SEPARATOR", "STANDARD"
    tag: str
    storage_volume_litres: Optional[int]
    orientation: str  # "VERTICAL", "HORIZONTAL", "STANDARD"
    has_internal_diffusers: bool
    insulation_type: str  # "CLOSED_CELL_FOAM_CLAD", "UNINSULATED", "STANDARD"
    design_pressure_kpa: Optional[int]
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "tank_type": self.tank_type,
            "tag": self.tag,
            "storage_volume_litres": self.storage_volume_litres,
            "orientation": self.orientation,
            "has_internal_diffusers": self.has_internal_diffusers,
            "insulation_type": self.insulation_type,
            "design_pressure_kpa": self.design_pressure_kpa,
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


def extract_chilled_water_buffer_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[ChilledWaterBufferCandidate]:
    """Extract chilled water buffer tank candidates deterministically."""
    results: List[ChilledWaterBufferCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:CHW[-_]?BT|HHW[-_]?BT|BT|TES|HST|HS)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    volume_pattern = re.compile(r"\b(\d{4,5})\s*(?:L|LITRE|LITRES|LITER|LITERS|LT)\b", re.IGNORECASE)
    pressure_kpa_pattern = re.compile(r"\b(1000|1600|1200|800|600)\s*KPA\b", re.IGNORECASE)
    pressure_bar_pattern = re.compile(r"\b(10|16|12|8|6)\s*BAR\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"cwt_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIRE WATER TANK", "SPRINKLER TANK", "POTABLE WATER TANK",
            "BREAK TANK", "DIESEL FUEL", "DAY TANK", "DIAPHRAGM TANK"
        ]):
            continue

        is_tank = any(k in upper_text for k in [
            "BUFFER TANK", "CHILLED WATER BUFFER", "HEATING WATER BUFFER",
            "THERMAL STORAGE TANK", "STRATIFIED CHILLED WATER", "HYDRAULIC SEPARATOR",
            "LOW LOSS HEADER", "TES TANK", "CHW BUFFER"
        ]) or (tag_pattern.search(text) is not None and ("BUFFER" in upper_text or "TANK" in upper_text or "HYDRAULIC" in upper_text or "CHW" in upper_text or "HHW" in upper_text))

        if not is_tank:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "BT-ITEM"

        # Internal diffusers
        has_internal_diffusers = any(d in upper_text for d in [
            "INTERNAL DIFFUSER", "RADIAL DIFFUSER", "STRATIFICATION BAFFLE", "FLOW DIFFUSER"
        ])

        # Orientation
        orientation = "VERTICAL"
        if "HORIZONTAL" in upper_text:
            orientation = "HORIZONTAL"
        elif "VERTICAL" in upper_text:
            orientation = "VERTICAL"

        # Tank type
        tank_type = "CHILLED_WATER_BUFFER"
        if "HYDRAULIC SEPARATOR" in upper_text or "LOW LOSS HEADER" in upper_text or "HS-" in tag:
            tank_type = "HYDRAULIC_SEPARATOR"
        elif "STRATIFIED" in upper_text or "TES" in upper_text:
            tank_type = "THERMAL_STRATIFIED_STORAGE"
        elif "HEATING WATER" in upper_text or "HHW" in upper_text or "HOT WATER BUFFER" in upper_text:
            tank_type = "HEATING_WATER_BUFFER"
        elif "CHILLED WATER" in upper_text or "CHW" in upper_text or "BUFFER TANK" in upper_text:
            tank_type = "CHILLED_WATER_BUFFER"

        # Volume
        storage_volume_litres: Optional[int] = None
        v_match = volume_pattern.search(text)
        if v_match:
            val = int(v_match.group(1))
            if 500 <= val <= 100000:
                storage_volume_litres = val

        # Pressure rating
        design_pressure_kpa: Optional[int] = None
        pk_match = pressure_kpa_pattern.search(text)
        if pk_match:
            design_pressure_kpa = int(pk_match.group(1))
        else:
            pb_match = pressure_bar_pattern.search(text)
            if pb_match:
                design_pressure_kpa = int(pb_match.group(1)) * 100

        # Insulation
        insulation_type = "CLOSED_CELL_FOAM_CLAD"
        if "UNINSULATED" in upper_text or "BARE" in upper_text:
            insulation_type = "UNINSULATED"
        elif "INSULAT" in upper_text or "CLAD" in upper_text or "PIR" in upper_text or "FOAM" in upper_text:
            insulation_type = "CLOSED_CELL_FOAM_CLAD"

        candidate = ChilledWaterBufferCandidate(
            item_id=item_id,
            tank_type=tank_type,
            tag=tag,
            storage_volume_litres=storage_volume_litres,
            orientation=orientation,
            has_internal_diffusers=has_internal_diffusers,
            insulation_type=insulation_type,
            design_pressure_kpa=design_pressure_kpa,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results