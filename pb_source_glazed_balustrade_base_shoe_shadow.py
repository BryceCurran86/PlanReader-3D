"""Structural Glazed Balustrade & Base U-Channel Shoe Shadow Authority.

Deterministic shadow extraction authority for architectural structural glazed
balustrades, continuous base shoe channels, spigots, standoffs, and handrails.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GlazedBalustradeCandidate:
    """Extracted structural glazed balustrade candidate."""
    item_id: str
    system_type: str  # "BASE_SHOE", "SPIGOT", "POINT_FIXED", "POST_AND_RAIL", "STANDARD"
    tag: str
    glass_thickness_mm: Optional[float]
    glass_type: str  # "TOUGHENED_LAMINATED", "TOUGHENED_MONOLITHIC", "STANDARD"
    handrail_type: str  # "CHANNEL_CAP", "OFFSET_HANDRAIL", "TOP_RAIL", "FRAMELESS", "STANDARD"
    mounting_type: str  # "TOP_MOUNT", "SIDE_MOUNT", "CORE_DRILLED", "STANDARD"
    height_mm: Optional[int]
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "system_type": self.system_type,
            "tag": self.tag,
            "glass_thickness_mm": self.glass_thickness_mm,
            "glass_type": self.glass_type,
            "handrail_type": self.handrail_type,
            "mounting_type": self.mounting_type,
            "height_mm": self.height_mm,
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


def extract_glazed_balustrade_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[GlazedBalustradeCandidate]:
    """Extract glazed balustrade candidates deterministically."""
    results: List[GlazedBalustradeCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:BAL|GB|GLB|GBL|BL)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)
    glass_thick_pattern = re.compile(r"\b(21\.52|17\.52|12\.76|13\.52|10\.76|25|21|19|17|15|12|10)\s*MM\b", re.IGNORECASE)
    height_pattern = re.compile(r"\b(1000|1050|1100|1150|1200|1250|1300|1400)\s*MM\s*(?:HIGH|HT|AFFL|BARRIER|HEIGHT)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"gb_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "SHOWER SCREEN", "SHOWER ENCLOSURE", "DOUBLE GLAZED WINDOW",
            "CURTAIN WALL GLAZING", "VISION GLASS", "OFFICE PARTITION",
            "GLASS SPLASHBACK", "SLIDING GLASS DOOR", "STOREFRONT GLAZING"
        ]):
            continue

        is_balustrade = any(k in upper_text for k in [
            "BALUSTRADE", "GLASS BALUSTRADE", "BASE SHOE", "BASE CHANNEL",
            "SPIGOT", "STANDOFF", "POINT FIXING", "EDGE BARRIER", "GLASS RAILING"
        ]) or (tag_pattern.search(text) is not None and ("GLASS" in upper_text or "BALUSTRADE" in upper_text or "RAIL" in upper_text))

        if not is_balustrade:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "BAL-ITEM"

        # System Type
        system_type = "BASE_SHOE"
        if "SPIGOT" in upper_text or "MINI POST" in upper_text or "MINI-POST" in upper_text:
            system_type = "SPIGOT"
        elif "STANDOFF" in upper_text or "POINT FIXED" in upper_text or "POINT FIXING" in upper_text or "DISC FIXING" in upper_text:
            system_type = "POINT_FIXED"
        elif "POST & RAIL" in upper_text or "POST AND RAIL" in upper_text or "BALUSTER POST" in upper_text:
            system_type = "POST_AND_RAIL"
        elif "BASE SHOE" in upper_text or "BASE CHANNEL" in upper_text or "U-CHANNEL" in upper_text or "DRY GLAZED" in upper_text:
            system_type = "BASE_SHOE"

        # Glass Thickness
        glass_thickness_mm: Optional[float] = None
        thick_match = glass_thick_pattern.search(text)
        if thick_match:
            glass_thickness_mm = float(thick_match.group(1))

        # Glass Type
        glass_type = "TOUGHENED_LAMINATED"
        if "LAMINATED" in upper_text or "SENTRYGLAS" in upper_text or "PVB" in upper_text or (glass_thickness_mm and glass_thickness_mm in [17.52, 21.52, 12.76, 13.52, 10.76]):
            glass_type = "TOUGHENED_LAMINATED"
        elif "MONOLITHIC" in upper_text or ("TOUGHENED" in upper_text and "LAMINATED" not in upper_text):
            glass_type = "TOUGHENED_MONOLITHIC"

        # Handrail Type
        handrail_type = "STANDARD"
        if "FRAMELESS" in upper_text or "NO HANDRAIL" in upper_text:
            handrail_type = "FRAMELESS"
        elif "CHANNEL CAP" in upper_text or "SLIMLINE CAP" in upper_text or "TOP CAP" in upper_text or "U-PROFILE CAP" in upper_text:
            handrail_type = "CHANNEL_CAP"
        elif "OFFSET HANDRAIL" in upper_text or "OFFSET RAIL" in upper_text or "SIDE HANDRAIL" in upper_text:
            handrail_type = "OFFSET_HANDRAIL"
        elif "TOP RAIL" in upper_text or "HANDRAIL" in upper_text:
            handrail_type = "TOP_RAIL"

        # Mounting Type
        mounting_type = "TOP_MOUNT"
        if "SIDE MOUNT" in upper_text or "FASCIA MOUNT" in upper_text or "FACE FIXED" in upper_text:
            mounting_type = "SIDE_MOUNT"
        elif "CORE DRILLED" in upper_text or "CORE-DRILLED" in upper_text or "GROUTED SPIGOT" in upper_text:
            mounting_type = "CORE_DRILLED"
        elif "TOP MOUNT" in upper_text or "BASE MOUNT" in upper_text or "SURFACE MOUNT" in upper_text:
            mounting_type = "TOP_MOUNT"

        # Height
        height_mm: Optional[int] = None
        h_match = height_pattern.search(text)
        if h_match:
            height_mm = int(h_match.group(1))

        candidate = GlazedBalustradeCandidate(
            item_id=item_id,
            system_type=system_type,
            tag=tag,
            glass_thickness_mm=glass_thickness_mm,
            glass_type=glass_type,
            handrail_type=handrail_type,
            mounting_type=mounting_type,
            height_mm=height_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results