"""Architectural Acoustic Louver & Plantroom Screen Shadow Authority.

Deterministic shadow extraction authority for architectural acoustic louvers,
rooftop plantroom screen walls, perforated sound attenuating blades, and bird screens.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class AcousticLouverCandidate:
    """Extracted acoustic louver or plantroom screen candidate."""
    item_id: str
    louver_type: str  # "SINGLE_BANK_ACOUSTIC", "DOUBLE_BANK_ACOUSTIC", "PLANTROOM_SCREEN", "WEATHER_LOUVER", "STANDARD"
    tag: str
    frame_depth_mm: Optional[int]
    width_mm: Optional[int]
    height_mm: Optional[int]
    acoustic_rw_db: Optional[int]
    free_area_percent: Optional[float]
    has_bird_mesh: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "louver_type": self.louver_type,
            "tag": self.tag,
            "frame_depth_mm": self.frame_depth_mm,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "acoustic_rw_db": self.acoustic_rw_db,
            "free_area_percent": self.free_area_percent,
            "has_bird_mesh": self.has_bird_mesh,
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


def extract_acoustic_louvers(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[AcousticLouverCandidate]:
    """Extract acoustic louvers and plantroom screens deterministically."""
    results: List[AcousticLouverCandidate] = []
    processed_count = 0

    depth_pattern = re.compile(r"(\d{2,3})\s*MM\s*(?:DEEP|DEPTH|FRAME|THICK)?\b", re.IGNORECASE)
    dim_pattern = re.compile(r"\b(\d{3,4})\s*[xX]\s*(\d{3,4})(?:MM)?\b")
    rw_pattern = re.compile(r"(?:RW|INSERTION\s*LOSS)\s*[:=]?\s*(\d{1,2})\s*DB\b", re.IGNORECASE)
    free_area_pattern = re.compile(r"(\d{2}(?:\.\d+)?)\s*%\s*(?:FREE\s*AREA|OPEN\s*AREA)?\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:SCREEN|AL|LV|LS|PS|L)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"al_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "WINDOW GLAZING", "SUNSHADE CANOPY ONLY", "FIRE DAMPER",
            "MOTORIZED SMOKE RELIEF DAMPER ONLY", "DOOR LEAF"
        ]):
            continue

        is_louver = any(k in upper_text for k in [
            "ACOUSTIC LOUVER", "ACOUSTIC LOUVRE", "PLANTROOM SCREEN",
            "ROOFTOP SCREEN", "WEATHER LOUVER", "WEATHER LOUVRE",
            "SOUND ATTENUATING LOUVER", "LOUVERED SCREEN"
        ]) or (tag_pattern.search(text) is not None and ("LOUVER" in upper_text or "LOUVRE" in upper_text or "SCREEN" in upper_text))

        if not is_louver:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "LOUVER"

        # Frame depth
        frame_depth_mm: Optional[int] = None
        d_match = depth_pattern.search(text)
        if d_match:
            frame_depth_mm = int(d_match.group(1))

        # Dimensions (W x H)
        width_mm: Optional[int] = None
        height_mm: Optional[int] = None
        dim_match = dim_pattern.search(text)
        if dim_match:
            width_mm = int(dim_match.group(1))
            height_mm = int(dim_match.group(2))

        # Louver type
        louver_type = "SINGLE_BANK_ACOUSTIC"
        if "DOUBLE BANK" in upper_text or "DOUBLE-BANK" in upper_text or (frame_depth_mm and frame_depth_mm >= 300):
            louver_type = "DOUBLE_BANK_ACOUSTIC"
        elif "PLANTROOM" in upper_text or "ROOFTOP SCREEN" in upper_text or "SCREEN WALL" in upper_text:
            louver_type = "PLANTROOM_SCREEN"
        elif "WEATHER" in upper_text:
            louver_type = "WEATHER_LOUVER"
        elif "SINGLE BANK" in upper_text or (frame_depth_mm and frame_depth_mm < 300):
            louver_type = "SINGLE_BANK_ACOUSTIC"

        # Acoustic performance (Rw dB)
        acoustic_rw_db: Optional[int] = None
        rw_match = rw_pattern.search(text)
        if rw_match:
            acoustic_rw_db = int(rw_match.group(1))

        # Free area %
        free_area_percent: Optional[float] = None
        fa_match = free_area_pattern.search(text)
        if fa_match:
            free_area_percent = float(fa_match.group(1))

        # Bird mesh
        has_bird_mesh = any(bm in upper_text for bm in ["BIRD MESH", "BIRD SCREEN", "INSECT MESH", "WIRE MESH"])

        candidate = AcousticLouverCandidate(
            item_id=item_id,
            louver_type=louver_type,
            tag=tag,
            frame_depth_mm=frame_depth_mm,
            width_mm=width_mm,
            height_mm=height_mm,
            acoustic_rw_db=acoustic_rw_db,
            free_area_percent=free_area_percent,
            has_bird_mesh=has_bird_mesh,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
