"""Precast Concrete Stair Flight & Rebated Landing Bearing Shadow Authority.

Deterministic shadow extraction authority for precast concrete stair flights,
rebated landing nib bearings, acoustic isolation strips, and shear dowel pins.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PrecastStairCandidate:
    """Extracted precast concrete stair flight and bearing candidate."""
    item_id: str
    flight_tag: str
    riser_count: Optional[int]
    riser_height_mm: Optional[float]
    going_count: Optional[int]
    going_depth_mm: Optional[float]
    flight_width_mm: Optional[int]
    landing_connection_type: str  # "REBATED_NIB", "CORBEL_BEARING", "INTEGRAL_LANDING", "BOLTED_ANGLE", "STANDARD"
    rebate_depth_mm: Optional[int]
    acoustic_bearing: str  # "SYLOMER", "NEOPRENE", "ELASTOMERIC", "NONE"
    has_shear_dowels: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "flight_tag": self.flight_tag,
            "riser_count": self.riser_count,
            "riser_height_mm": self.riser_height_mm,
            "going_count": self.going_count,
            "going_depth_mm": self.going_depth_mm,
            "flight_width_mm": self.flight_width_mm,
            "landing_connection_type": self.landing_connection_type,
            "rebate_depth_mm": self.rebate_depth_mm,
            "acoustic_bearing": self.acoustic_bearing,
            "has_shear_dowels": self.has_shear_dowels,
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


def extract_precast_stairs(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PrecastStairCandidate]:
    """Extract precast stair flights and landing bearings deterministically."""
    results: List[PrecastStairCandidate] = []
    processed_count = 0

    riser_pattern = re.compile(r"(\d{1,2})\s*(?:RISERS?|R)\s*@\s*(\d{2,3}(?:\.\d+)?)(?:MM)?\b", re.IGNORECASE)
    going_pattern = re.compile(r"(\d{1,2})\s*(?:GOINGS?|G|TREADS?)\s*@\s*(\d{2,3}(?:\.\d+)?)(?:MM)?\b", re.IGNORECASE)
    width_pattern = re.compile(r"(\d{3,4})\s*MM\s*(?:CLEAR\s*)?(?:WIDTH|WIDE)\b", re.IGNORECASE)
    rebate_pattern = re.compile(r"(\d{2,3})(?:x\d{2,3})?\s*MM\s*(?:REBATE|NIB|BEARING\s*NIB|STEPPED\s*BEARING)\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:ST|STAIR|SF|FL)[-_]?\d{1,2}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"stair_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "STAIR VOID PENETRATION ONLY", "ESCALATOR TIE", "LADDER ACCESS",
            "SCAFFOLD STAIR", "HANDRAIL ONLY"
        ]):
            continue

        is_stair = any(k in upper_text for k in [
            "PRECAST STAIR", "STAIR FLIGHT", "LANDING BEARING", "REBATED NIB",
            "PRECAST FLIGHT", "STAIR TREADS", "STAIR RISERS"
        ]) or (tag_pattern.search(text) is not None and ("STAIR" in upper_text or "FLIGHT" in upper_text or "RISER" in upper_text)) \
           or (riser_pattern.search(text) is not None and going_pattern.search(text) is not None)

        if not is_stair:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "ST-FLIGHT"

        # Riser / going counts & sizes
        riser_count: Optional[int] = None
        riser_height_mm: Optional[float] = None
        r_match = riser_pattern.search(text)
        if r_match:
            riser_count = int(r_match.group(1))
            riser_height_mm = float(r_match.group(2))

        going_count: Optional[int] = None
        going_depth_mm: Optional[float] = None
        g_match = going_pattern.search(text)
        if g_match:
            going_count = int(g_match.group(1))
            going_depth_mm = float(g_match.group(2))

        # Clear width
        flight_width_mm: Optional[int] = None
        w_match = width_pattern.search(text)
        if w_match:
            flight_width_mm = int(w_match.group(1))

        # Landing connection type
        landing_connection_type = "STANDARD"
        if "REBATED" in upper_text or "NIB" in upper_text or "STEPPED" in upper_text:
            landing_connection_type = "REBATED_NIB"
        elif "CORBEL" in upper_text:
            landing_connection_type = "CORBEL_BEARING"
        elif "INTEGRAL" in upper_text:
            landing_connection_type = "INTEGRAL_LANDING"
        elif "BOLTED ANGLE" in upper_text:
            landing_connection_type = "BOLTED_ANGLE"

        # Rebate depth
        rebate_depth_mm: Optional[int] = None
        reb_match = rebate_pattern.search(text)
        if reb_match:
            rebate_depth_mm = int(reb_match.group(1))

        # Acoustic bearing
        acoustic_bearing = "NONE"
        if "SYLOMER" in upper_text:
            acoustic_bearing = "SYLOMER"
        elif "NEOPRENE" in upper_text:
            acoustic_bearing = "NEOPRENE"
        elif "ELASTOMERIC" in upper_text or "ACOUSTIC BEARING" in upper_text or "ISOLATION STRIP" in upper_text:
            acoustic_bearing = "ELASTOMERIC"

        # Dowels
        has_shear_dowels = any(d in upper_text for d in ["DOWEL", "SHEAR PIN", "GROUT TUBE", "N16 DOWEL", "N20 DOWEL"])

        candidate = PrecastStairCandidate(
            item_id=item_id,
            flight_tag=tag,
            riser_count=riser_count,
            riser_height_mm=riser_height_mm,
            going_count=going_count,
            going_depth_mm=going_depth_mm,
            flight_width_mm=flight_width_mm,
            landing_connection_type=landing_connection_type,
            rebate_depth_mm=rebate_depth_mm,
            acoustic_bearing=acoustic_bearing,
            has_shear_dowels=has_shear_dowels,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
