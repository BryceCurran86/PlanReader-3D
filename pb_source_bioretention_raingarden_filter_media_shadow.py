"""Stormwater Bioretention Raingarden & Saturated Zone Shadow Authority.

Deterministic shadow extraction authority for bioretention basins, raingardens,
filter media layers, submerged saturated anoxic zones, and slotted underdrains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class BioretentionRaingardenCandidate:
    """Extracted bioretention or raingarden candidate."""
    item_id: str
    element_type: str  # "BIORETENTION_BASIN", "RAINGARDEN_CELL", "TREE_PIT_BIOFILTER", "VEGETATED_SWALE", "STANDARD"
    tag: str
    filter_media_depth_mm: Optional[int]
    transition_layer_depth_mm: Optional[int]
    drainage_layer_depth_mm: Optional[int]
    ponding_depth_mm: Optional[int]
    has_saturated_zone: bool
    saturated_zone_depth_mm: Optional[int]
    underdrain_pipe_mm: Optional[int]
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
            "filter_media_depth_mm": self.filter_media_depth_mm,
            "transition_layer_depth_mm": self.transition_layer_depth_mm,
            "drainage_layer_depth_mm": self.drainage_layer_depth_mm,
            "ponding_depth_mm": self.ponding_depth_mm,
            "has_saturated_zone": self.has_saturated_zone,
            "saturated_zone_depth_mm": self.saturated_zone_depth_mm,
            "underdrain_pipe_mm": self.underdrain_pipe_mm,
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


def extract_bioretention_raingardens(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[BioretentionRaingardenCandidate]:
    """Extract bioretention basin and raingarden items deterministically."""
    results: List[BioretentionRaingardenCandidate] = []
    processed_count = 0

    media_pattern = re.compile(r"(\d{3})\s*MM\s*(?:BIORETENTION\s*)?(?:FILTER\s*)?MEDIA\b", re.IGNORECASE)
    transition_pattern = re.compile(r"(\d{2,3})\s*MM\s*(?:TRANSITION\s*)?(?:SAND\s*)?LAYER\b", re.IGNORECASE)
    drainage_pattern = re.compile(r"(\d{2,3})\s*MM\s*(?:DRAINAGE\s*)?(?:GRAVEL\s*|AGGREGATE\s*)?LAYER\b", re.IGNORECASE)
    ponding_pattern = re.compile(r"(\d{2,3})\s*MM\s*(?:EXTENDED\s*DETENTION\s*|MAX\s*)?PONDING\b", re.IGNORECASE)
    sat_zone_pattern = re.compile(r"(\d{3})\s*MM\s*(?:SUBMERGED\s*|SATURATED\s*|ANOXIC\s*)ZONE\b", re.IGNORECASE)
    pipe_pattern = re.compile(r"\b(?:DN\s*(\d{2,3})|(\d{2,3})\s*MM)\s*(?:SLOTTED|PERFORATED|UNDERDRAIN|AG\s*PIPE)\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:RG|BIO|BR|TREE|SWALE)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"bio_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "GREASE TRAP", "SEWAGE DISPOSAL", "SEPTIC DRAINFIELD",
            "POTABLE WATER", "GAS PIPE", "PLANTROOM LOUVER"
        ]):
            continue

        is_bioretention = any(k in upper_text for k in [
            "BIORETENTION", "RAINGARDEN", "RAIN GARDEN", "TREE PIT BIOFILTER",
            "VEGETATED SWALE", "BIOFILTER", "BIO-RETENTION", "BIOFILTRATION"
        ]) or (tag_pattern.search(text) is not None and ("GARDEN" in upper_text or "MEDIA" in upper_text or "BIO" in upper_text or "SWALE" in upper_text))

        if not is_bioretention:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "BIO-UNIT"

        # Element type
        element_type = "BIORETENTION_BASIN"
        if "TREE PIT" in upper_text or "TREE BIOFILTER" in upper_text:
            element_type = "TREE_PIT_BIOFILTER"
        elif "SWALE" in upper_text:
            element_type = "VEGETATED_SWALE"
        elif "RAINGARDEN" in upper_text or "RAIN GARDEN" in upper_text:
            element_type = "RAINGARDEN_CELL"
        elif "BIORETENTION" in upper_text or "BIOFILTER" in upper_text:
            element_type = "BIORETENTION_BASIN"

        # Depths
        filter_media_depth_mm: Optional[int] = None
        m_match = media_pattern.search(text)
        if m_match:
            filter_media_depth_mm = int(m_match.group(1))

        transition_layer_depth_mm: Optional[int] = None
        t_match = transition_pattern.search(text)
        if t_match and "DRAINAGE" not in text[t_match.start():t_match.end()]:
            transition_layer_depth_mm = int(t_match.group(1))

        drainage_layer_depth_mm: Optional[int] = None
        d_match = drainage_pattern.search(text)
        if d_match:
            drainage_layer_depth_mm = int(d_match.group(1))

        ponding_depth_mm: Optional[int] = None
        p_match = ponding_pattern.search(text)
        if p_match:
            ponding_depth_mm = int(p_match.group(1))

        # Saturated zone
        has_saturated_zone = any(sz in upper_text for sz in ["SATURATED ZONE", "SUBMERGED ZONE", "ANOXIC ZONE", "INTERNAL WATER STORAGE", "IWS"])
        saturated_zone_depth_mm: Optional[int] = None
        sz_match = sat_zone_pattern.search(text)
        if sz_match:
            saturated_zone_depth_mm = int(sz_match.group(1))
            has_saturated_zone = True

        # Underdrain pipe size
        underdrain_pipe_mm: Optional[int] = None
        pipe_match = pipe_pattern.search(text)
        if pipe_match:
            underdrain_pipe_mm = int(pipe_match.group(1) or pipe_match.group(2))

        candidate = BioretentionRaingardenCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            filter_media_depth_mm=filter_media_depth_mm,
            transition_layer_depth_mm=transition_layer_depth_mm,
            drainage_layer_depth_mm=drainage_layer_depth_mm,
            ponding_depth_mm=ponding_depth_mm,
            has_saturated_zone=has_saturated_zone,
            saturated_zone_depth_mm=saturated_zone_depth_mm,
            underdrain_pipe_mm=underdrain_pipe_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
