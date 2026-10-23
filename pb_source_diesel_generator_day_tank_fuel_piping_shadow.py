"""Emergency Diesel Generator Fuel Day Tank & Double-Wall Piping Shadow Authority.

Deterministic shadow extraction authority for emergency generator fuel supply systems,
including day tanks, base/belly tanks, and double-wall fuel transfer piping.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GeneratorFuelItemCandidate:
    """Extracted generator fuel day tank or fuel piping candidate."""
    item_id: str
    element_type: str  # "DAY_TANK", "BELLY_TANK", "FUEL_PIPE", "LEAK_SENSOR"
    capacity_liters: Optional[float]
    fuel_type: str  # "DIESEL", "HVO", "FUEL_OIL", "GENERIC"
    mounting_bunding: str  # "SELF_BUNDED", "BELLY_TANK", "SKID_MOUNTED", "WALL_MOUNTED", "STANDARD"
    pipe_service: Optional[str]  # "SUPPLY", "RETURN", "FILL", "OVERFLOW", "VENT"
    pipe_size_mm: Optional[int]
    is_double_wall: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "element_type": self.element_type,
            "capacity_liters": self.capacity_liters,
            "fuel_type": self.fuel_type,
            "mounting_bunding": self.mounting_bunding,
            "pipe_service": self.pipe_service,
            "pipe_size_mm": self.pipe_size_mm,
            "is_double_wall": self.is_double_wall,
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


def extract_generator_fuel_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[GeneratorFuelItemCandidate]:
    """Extract generator fuel day tanks and fuel piping candidates deterministically."""
    results: List[GeneratorFuelItemCandidate] = []
    processed_count = 0

    # Capacity regex (e.g., 500L, 1000 L, 2500 LITRES, 200 GALLON, 500 GAL)
    cap_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:L(?:ITRES?|ITERS?)?|GAL(?:LONS?)?)\b", re.IGNORECASE)
    # Pipe size regex (e.g., DN25, DN50, 25MM, 50 MM, 1", 2")
    pipe_size_pattern = re.compile(r"\b(?:DN\s*(\d{2,3})|(\d{2,3})\s*MM)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"gen_fuel_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "WATER TANK", "RAINWATER", "EXPANSION VESSEL", "COMPRESSED AIR",
            "SEWAGE", "STORMWATER", "GREASE TRAP", "HYDRONIC"
        ]):
            continue

        # Check for tank vs pipe vs leak sensor
        is_tank = any(k in upper_text for k in [
            "DAY TANK", "FUEL TANK", "DIESEL TANK", "BELLY TANK", "BASE TANK",
            "BULK FUEL", "OIL TANK", "STORAGE TANK"
        ])
        is_pipe = any(k in upper_text for k in [
            "FUEL PIPE", "DIESEL SUPPLY", "DIESEL RETURN", "FUEL OIL LINE",
            "DOUBLE CONTAINMENT", "DOUBLE-WALL", "DOUBLE WALL", "COAXIAL PIPE",
            "FUEL FEED", "FUEL OVERFLOW", "FUEL VENT"
        ])
        is_leak_sensor = any(k in upper_text for k in [
            "INTERSTITIAL SENSOR", "LEAK DETECTION SENSOR", "OPTICAL FLOAT SWITCH", "LEAK DETECTOR"
        ])

        if not (is_tank or is_pipe or is_leak_sensor):
            continue

        # Fuel type classification
        fuel_type = "DIESEL"
        if "HVO" in upper_text:
            fuel_type = "HVO"
        elif "BIODIESEL" in upper_text:
            fuel_type = "BIODIESEL"
        elif "FUEL OIL" in upper_text or "FO " in upper_text:
            fuel_type = "FUEL_OIL"

        # Element type & properties
        element_type = "DAY_TANK"
        capacity_liters: Optional[float] = None
        mounting_bunding = "STANDARD"
        pipe_service: Optional[str] = None
        pipe_size_mm: Optional[int] = None
        is_double_wall = any(dw in upper_text for dw in [
            "DOUBLE WALL", "DOUBLE-WALL", "DOUBLE CONTAINMENT", "COAXIAL", "BUNDED", "SELF-BUNDED"
        ])

        if is_leak_sensor:
            element_type = "LEAK_SENSOR"
        elif is_tank:
            if "BELLY" in upper_text or "BASE TANK" in upper_text:
                element_type = "BELLY_TANK"
                mounting_bunding = "BELLY_TANK"
            elif "SELF-BUNDED" in upper_text or "SELF BUNDED" in upper_text or "DOUBLE-WALL TANK" in upper_text:
                mounting_bunding = "SELF_BUNDED"
            elif "WALL" in upper_text and "MOUNT" in upper_text:
                mounting_bunding = "WALL_MOUNTED"
            elif "SKID" in upper_text:
                mounting_bunding = "SKID_MOUNTED"

            cap_match = cap_pattern.search(text)
            if cap_match:
                val = float(cap_match.group(1))
                if "GAL" in upper_text:
                    capacity_liters = round(val * 3.78541, 1)
                else:
                    capacity_liters = val
        elif is_pipe:
            element_type = "FUEL_PIPE"
            if "SUPPLY" in upper_text or "FEED" in upper_text:
                pipe_service = "SUPPLY"
            elif "RETURN" in upper_text:
                pipe_service = "RETURN"
            elif "OVERFLOW" in upper_text:
                pipe_service = "OVERFLOW"
            elif "VENT" in upper_text:
                pipe_service = "VENT"
            elif "FILL" in upper_text:
                pipe_service = "FILL"

            size_match = pipe_size_pattern.search(text)
            if size_match:
                pipe_size_mm = int(size_match.group(1) or size_match.group(2))

        candidate = GeneratorFuelItemCandidate(
            item_id=item_id,
            element_type=element_type,
            capacity_liters=capacity_liters,
            fuel_type=fuel_type,
            mounting_bunding=mounting_bunding,
            pipe_service=pipe_service,
            pipe_size_mm=pipe_size_mm,
            is_double_wall=is_double_wall,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
