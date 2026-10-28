"""Vertical Transportation Machine-Room-Less (MRL) Traction Elevator Pit & Buffer Spring Shadow Authority.

Deterministic shadow extraction authority for MRL passenger/goods lift pits,
car and counterweight buffers (oil/spring/polyurethane), guide rail brackets, and pit ladders.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class MRLElevatorPitCandidate:
    """Extracted MRL elevator pit / buffer candidate."""
    item_id: str
    element_type: str  # "ELEVATOR_PIT", "CAR_BUFFER", "COUNTERWEIGHT_BUFFER", "GUIDE_RAIL_BRACKET", "PIT_LADDER", "PIT_SUMP", "STANDARD"
    tag: str
    rated_speed_mps: Optional[float]
    rated_load_kg: Optional[int]
    pit_depth_mm: Optional[int]
    buffer_technology: str  # "HYDRAULIC_OIL", "ENERGY_ACCUMULATION_SPRING", "POLYURETHANE_CELLULAR", "STANDARD"
    has_retractable_ladder: bool
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
            "rated_speed_mps": self.rated_speed_mps,
            "rated_load_kg": self.rated_load_kg,
            "pit_depth_mm": self.pit_depth_mm,
            "buffer_technology": self.buffer_technology,
            "has_retractable_ladder": self.has_retractable_ladder,
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


def extract_mrl_elevator_pit_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[MRLElevatorPitCandidate]:
    """Extract MRL elevator pit and buffer candidates deterministically."""
    results: List[MRLElevatorPitCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:LIFT|EL|ELEV|BUF|PIT|CWT)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    speed_pattern = re.compile(r"\b(\d(?:\.\d+)?)\s*(?:M/S|MPS|METERS?\s*PER\s*SEC(?:OND)?)\b", re.IGNORECASE)
    load_pattern = re.compile(r"\b(\d{3,4})\s*KG\b", re.IGNORECASE)
    depth_pattern = re.compile(r"\b(?:PIT\s*DEPTH|DEPTH|DEEP)?\s*[:=]?\s*(\d{4})\s*MM\s*(?:PIT\s*DEPTH|DEEP|DEPTH)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"lift_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "PLATFORM LIFT", "DDA LIFT", "DUMBWAITER",
            "ESCALATOR PIT", "MOVING WALKWAY", "CARPARK SUMP",
            "STORM WATER SUMP"
        ]):
            continue

        is_elevator = any(k in upper_text for k in [
            "LIFT PIT", "ELEVATOR PIT", "MRL LIFT", "TRACTION LIFT", "TRACTION ELEVATOR",
            "CAR BUFFER", "COUNTERWEIGHT BUFFER", "CWT BUFFER", "GUIDE RAIL BRACKET",
            "PIT LADDER", "LIFT BUFFER"
        ]) or (tag_pattern.search(text) is not None and ("LIFT" in upper_text or "ELEVATOR" in upper_text or "BUFFER" in upper_text or "PIT" in upper_text))

        if not is_elevator:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "LIFT-PIT"

        # Ladder
        has_retractable_ladder = any(lad in upper_text for lad in [
            "RETRACTABLE LADDER", "FOLDING LADDER", "RETRACTABLE PIT LADDER"
        ])

        # Speed
        rated_speed_mps: Optional[float] = None
        sp_match = speed_pattern.search(text)
        if sp_match:
            rated_speed_mps = float(sp_match.group(1))

        # Load
        rated_load_kg: Optional[int] = None
        ld_match = load_pattern.search(text)
        if ld_match:
            val = int(ld_match.group(1))
            if 300 <= val <= 5000:
                rated_load_kg = val

        # Pit depth
        pit_depth_mm: Optional[int] = None
        dp_match = depth_pattern.search(text)
        if dp_match:
            val = int(dp_match.group(1))
            if 1000 <= val <= 3500:
                pit_depth_mm = val

        # Element type
        element_type = "ELEVATOR_PIT"
        if "CWT BUFFER" in upper_text or "COUNTERWEIGHT BUFFER" in upper_text:
            element_type = "COUNTERWEIGHT_BUFFER"
        elif "CAR BUFFER" in upper_text:
            element_type = "CAR_BUFFER"
        elif "GUIDE RAIL" in upper_text or "T-RAIL" in upper_text or "RAIL BRACKET" in upper_text:
            element_type = "GUIDE_RAIL_BRACKET"
        elif "SUMP" in upper_text:
            element_type = "PIT_SUMP"
        elif "ELEVATOR PIT" in upper_text or "LIFT PIT" in upper_text or (pit_depth_mm is not None and "LAD" not in tag):
            element_type = "ELEVATOR_PIT"
        elif "LADDER" in upper_text:
            element_type = "PIT_LADDER"
        elif "BUFFER" in upper_text:
            element_type = "CAR_BUFFER"

        # Buffer technology
        buffer_technology = "HYDRAULIC_OIL"
        if "POLYURETHANE" in upper_text or "CELLULAR" in upper_text:
            buffer_technology = "POLYURETHANE_CELLULAR"
        elif "SPRING" in upper_text or "COIL" in upper_text or (rated_speed_mps and rated_speed_mps <= 1.0):
            buffer_technology = "ENERGY_ACCUMULATION_SPRING"
        elif "OIL" in upper_text or "HYDRAULIC" in upper_text or (rated_speed_mps and rated_speed_mps > 1.0):
            buffer_technology = "HYDRAULIC_OIL"

        candidate = MRLElevatorPitCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            rated_speed_mps=rated_speed_mps,
            rated_load_kg=rated_load_kg,
            pit_depth_mm=pit_depth_mm,
            buffer_technology=buffer_technology,
            has_retractable_ladder=has_retractable_ladder,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results