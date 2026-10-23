"""Galvanized Structural Steel Shelf Angle & Brickwork Lintel Shadow Authority.

Deterministic shadow extraction authority for galvanized steel shelf angles,
masonry cavity lintels, and T-bar beams from structural and architectural drawings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SteelLintelCandidate:
    """Extracted galvanized steel lintel or shelf angle candidate."""
    item_id: str
    lintel_type: str  # "EQUAL_ANGLE", "UNEQUAL_ANGLE", "T_BAR", "SHELF_ANGLE", "PROPRIETARY_LINTEL"
    leg1_mm: Optional[int]
    leg2_mm: Optional[int]
    thickness_mm: Optional[float]
    length_mm: Optional[int]
    min_bearing_mm: int
    corrosion_protection: str  # "HOT_DIP_GALVANIZED", "STAINLESS_STEEL_316", "STAINLESS_STEEL_304", "STANDARD"
    is_slotted_connection: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "lintel_type": self.lintel_type,
            "leg1_mm": self.leg1_mm,
            "leg2_mm": self.leg2_mm,
            "thickness_mm": self.thickness_mm,
            "length_mm": self.length_mm,
            "min_bearing_mm": self.min_bearing_mm,
            "corrosion_protection": self.corrosion_protection,
            "is_slotted_connection": self.is_slotted_connection,
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


def extract_steel_lintels(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SteelLintelCandidate]:
    """Extract galvanized steel lintels and shelf angles deterministically."""
    results: List[SteelLintelCandidate] = []
    processed_count = 0

    # Dimension pattern: e.g. 100x100x6, 150x100x8, 200x100x10.0, 100x75x6
    sec_pattern = re.compile(r"\b(\d{2,3})\s*[xX]\s*(\d{2,3})\s*[xX]\s*(\d{1,2}(?:\.\d+)?)\s*(?:EA|UA|ANGLE)?\b", re.IGNORECASE)
    len_pattern = re.compile(r"(?:L\s*=\s*|\bL\b\s*|SPAN\s*=\s*)(\d{3,4})\b|\b(\d{3,4})\s*(?:MM\s*)?(?:LG|LONG)\b", re.IGNORECASE)
    bearing_pattern = re.compile(r"(\d{2,3})\s*MM\s*(?:MIN\s*)?(?:END\s*)?BEARING\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"lintel_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "LVL", "GLULAM", "PRECAST CONCRETE LINTEL", "TIMBER LINTEL",
            "REBAR", "SLAB EDGE FORMWORK", "CURTAIN WALL TRANSOM"
        ]):
            continue

        is_lintel = any(k in upper_text for k in [
            "LINTEL", "SHELF ANGLE", "GALINTEL", "RENDABAR", "T-BAR",
            "STEEL ANGLE OVER OPENING", "BRICK LINTEL", "CAVITY LINTEL"
        ]) or sec_pattern.search(text) is not None and ("EA" in upper_text or "UA" in upper_text or "ANGLE" in upper_text)

        if not is_lintel:
            continue

        # Extract dimensions
        leg1_mm: Optional[int] = None
        leg2_mm: Optional[int] = None
        thickness_mm: Optional[float] = None
        sec_match = sec_pattern.search(text)
        if sec_match:
            leg1_mm = int(sec_match.group(1))
            leg2_mm = int(sec_match.group(2))
            thickness_mm = float(sec_match.group(3))

        # Lintel type
        lintel_type = "EQUAL_ANGLE"
        if "SHELF ANGLE" in upper_text or "SHELF-ANGLE" in upper_text:
            lintel_type = "SHELF_ANGLE"
        elif "T-BAR" in upper_text or "T BAR" in upper_text:
            lintel_type = "T_BAR"
        elif "GALINTEL" in upper_text or "RENDABAR" in upper_text:
            lintel_type = "PROPRIETARY_LINTEL"
        elif leg1_mm and leg2_mm:
            if leg1_mm == leg2_mm:
                lintel_type = "EQUAL_ANGLE"
            else:
                lintel_type = "UNEQUAL_ANGLE"
        elif "UA" in upper_text or "UNEQUAL" in upper_text:
            lintel_type = "UNEQUAL_ANGLE"

        # Length
        length_mm: Optional[int] = None
        len_match = len_pattern.search(text)
        if len_match:
            length_mm = int(len_match.group(1) or len_match.group(2))

        # Bearing (default 150mm standard per masonry codes)
        min_bearing_mm = 150
        brg_match = bearing_pattern.search(text)
        if brg_match:
            min_bearing_mm = int(brg_match.group(1))

        # Corrosion protection
        corrosion_protection = "HOT_DIP_GALVANIZED"
        if "316" in upper_text:
            corrosion_protection = "STAINLESS_STEEL_316"
        elif "304" in upper_text:
            corrosion_protection = "STAINLESS_STEEL_304"
        elif "PAINTED" in upper_text or "PRIMER ONLY" in upper_text:
            corrosion_protection = "STANDARD"

        is_slotted_connection = any(s in upper_text for s in ["SLOTTED", "SLOT HOLE", "ADJUSTABLE SHIM"])

        candidate = SteelLintelCandidate(
            item_id=item_id,
            lintel_type=lintel_type,
            leg1_mm=leg1_mm,
            leg2_mm=leg2_mm,
            thickness_mm=thickness_mm,
            length_mm=length_mm,
            min_bearing_mm=min_bearing_mm,
            corrosion_protection=corrosion_protection,
            is_slotted_connection=is_slotted_connection,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
