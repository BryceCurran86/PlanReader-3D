"""Sanitary Plumbing Vacuum Drainage Interface Valve & Buffer Tank Shadow Authority.

Deterministic shadow extraction authority for vacuum sanitary drainage interface valves (VIV),
graywater buffer sumps, vacuum toilets, vacuum station generator skids, and negative-pressure mains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class VacuumDrainageCandidate:
    """Extracted vacuum drainage candidate."""
    item_id: str
    element_type: str  # "VACUUM_INTERFACE_VALVE", "BUFFER_SUMP_UNIT", "VACUUM_TOILET", "VACUUM_STATION_SKID", "STANDARD"
    tag: str
    valve_size_mm: Optional[int]
    actuation_mechanism: str  # "PNEUMATIC_DIAPHRAGM", "ELECTRONIC_SOLENOID", "STANDARD"
    pipe_diameter_mm: Optional[int]
    buffer_capacity_litres: Optional[int]
    operating_vacuum_kpa: Optional[int]
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "element_type": self.element_type,
            "tag": self.tag,
            "valve_size_mm": self.valve_size_mm,
            "actuation_mechanism": self.actuation_mechanism,
            "pipe_diameter_mm": self.pipe_diameter_mm,
            "buffer_capacity_litres": self.buffer_capacity_litres,
            "operating_vacuum_kpa": self.operating_vacuum_kpa,
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


def extract_vacuum_drainage_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[VacuumDrainageCandidate]:
    """Extract vacuum drainage candidates deterministically."""
    results: List[VacuumDrainageCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:VIV|VBU|VWC|VS|VDP|VAC)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    size_pattern = re.compile(r"\b(?:DN|DIA|O)?\s*(100|80|65|50|40|32)\s*(?:MM|DIA|DN|O)?\s*(?:VALVE|PIPE|MAIN|CONNECTION)?\b", re.IGNORECASE)
    vacuum_pattern = re.compile(r"\b(-?[4567]\d)\s*KPA\b", re.IGNORECASE)
    buffer_litres_pattern = re.compile(r"\b(\d{1,3})\s*(?:L|LITRE|LITRES|LITER|LITERS)\s*(?:BUFFER|SUMP|UNIT|BOX)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"vac_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "GRAVITY SEWER", "GRAVITY DRAINAGE", "SOIL STACK", "PVC SEWER DRAIN",
            "MEDICAL VACUUM", "MED GAS", "SIPHONIC ROOF", "SYPHONIC DRAINAGE",
            "GREASE TRAP"
        ]):
            continue

        is_vac = any(k in upper_text for k in [
            "VACUUM DRAINAGE", "VACUUM INTERFACE VALVE", "VACUUM BUFFER",
            "VACUUM TOILET", "VACUUM STATION", "VACUUM SEWER", "VACUUM COLLECTION",
            "VIV-", "VBU-", "VACUUM WC"
        ]) or (tag_pattern.search(text) is not None and ("VACUUM" in upper_text or "VALVE" in upper_text or "BUFFER" in upper_text or "TOILET" in upper_text))

        if not is_vac:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "VAC-ITEM"

        # Operating vacuum
        operating_vacuum_kpa: Optional[int] = None
        v_match = vacuum_pattern.search(text)
        if v_match:
            val = int(v_match.group(1))
            operating_vacuum_kpa = -abs(val)

        # Buffer capacity
        buffer_capacity_litres: Optional[int] = None
        b_match = buffer_litres_pattern.search(text)
        if b_match:
            val = int(b_match.group(1))
            if 5 <= val <= 250:
                buffer_capacity_litres = val

        # Valve / Pipe size
        valve_size_mm: Optional[int] = None
        pipe_diameter_mm: Optional[int] = None
        for m in size_pattern.finditer(text):
            val = int(m.group(1))
            if val in [32, 40, 50, 65, 80, 100]:
                if valve_size_mm is None and val in [50, 65, 80]:
                    valve_size_mm = val
                if pipe_diameter_mm is None:
                    pipe_diameter_mm = val

        # Actuation mechanism
        actuation_mechanism = "PNEUMATIC_DIAPHRAGM"
        if "SOLENOID" in upper_text or "ELECTRONIC" in upper_text or "ELECTRIC" in upper_text:
            actuation_mechanism = "ELECTRONIC_SOLENOID"
        elif "PNEUMATIC" in upper_text or "DIAPHRAGM" in upper_text or "AIR PULSE" in upper_text:
            actuation_mechanism = "PNEUMATIC_DIAPHRAGM"

        # Element type
        element_type = "VACUUM_INTERFACE_VALVE"
        if "STATION" in upper_text or "GENERATOR" in upper_text or "VS-" in tag:
            element_type = "VACUUM_STATION_SKID"
        elif "TOILET" in upper_text or "WC" in upper_text or "PAN" in upper_text or "VWC-" in tag:
            element_type = "VACUUM_TOILET"
        elif "BUFFER" in upper_text or "SUMP" in upper_text or "VBU-" in tag:
            element_type = "BUFFER_SUMP_UNIT"
        elif "VALVE" in upper_text or "INTERFACE" in upper_text or "VIV-" in tag:
            element_type = "VACUUM_INTERFACE_VALVE"

        candidate = VacuumDrainageCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            valve_size_mm=valve_size_mm,
            actuation_mechanism=actuation_mechanism,
            pipe_diameter_mm=pipe_diameter_mm,
            buffer_capacity_litres=buffer_capacity_litres,
            operating_vacuum_kpa=operating_vacuum_kpa,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results