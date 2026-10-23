"""Curtain Wall Perimeter Slab-Edge Firestop & Smoke Seal Shadow Authority.

Deterministic shadow extraction authority for curtain wall perimeter slab-edge firestop,
mineral wool safing insulation, elastomeric smoke seals, and safing brackets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PerimeterFirestopCandidate:
    """Extracted curtain wall perimeter slab-edge firestop candidate."""
    item_id: str
    gap_width_mm: Optional[int]
    fire_rating_minutes: Optional[int]
    safing_type: str  # "MINERAL_WOOL_SAFING", "CERAMIC_BLANKET", "STANDARD_SAFING"
    smoke_seal_type: str  # "ELASTOMERIC_SPRAY", "SILICONE_SEALANT", "INTUMESCENT_SEALANT", "FOIL_BARRIER", "STANDARD"
    has_safing_clips: bool
    movement_capability: str  # "STATIC", "CLASS_I", "CLASS_II", "SEISMIC", "STANDARD"
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "gap_width_mm": self.gap_width_mm,
            "fire_rating_minutes": self.fire_rating_minutes,
            "safing_type": self.safing_type,
            "smoke_seal_type": self.smoke_seal_type,
            "has_safing_clips": self.has_safing_clips,
            "movement_capability": self.movement_capability,
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


def extract_perimeter_firestops(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PerimeterFirestopCandidate]:
    """Extract curtain wall perimeter firestop and smoke seal candidates deterministically."""
    results: List[PerimeterFirestopCandidate] = []
    processed_count = 0

    gap_pattern = re.compile(r"\b(\d{2,3})\s*MM\s*(?:GAP|JOINT|VOID|PERIMETER|SLAB[-\s]EDGE)?\b", re.IGNORECASE)
    frl_pattern = re.compile(r"(?:FRL\s*-?\s*/\s*(\d{2,3})\s*/\s*(\d{2,3})|(\d)\s*(?:HR|HOUR)\s*(?:FIRE|F-RATING)?)", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"firestop_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Negative lookalikes
        if any(neg in upper_text for neg in [
            "PIPE PENETRATION", "CABLE TRAY COLLAR", "DUCT FIREDAMPER",
            "MASONRY CONTROL JOINT", "EXPANSION JOINT FLOOR COVER"
        ]):
            continue

        is_perimeter_firestop = any(k in upper_text for k in [
            "PERIMETER FIRESTOP", "SLAB EDGE FIRESTOP", "SLAB-EDGE FIRESTOP",
            "SAFING INSULATION", "CURTAIN WALL FIRESTOP", "SMOKE SEAL SPRAY",
            "EDGE OF SLAB FIRE BARRIER", "PERIMETER FIRE BARRIER"
        ])

        if not is_perimeter_firestop:
            continue

        # Gap width
        gap_width_mm: Optional[int] = None
        gap_match = gap_pattern.search(text)
        if gap_match:
            gap_width_mm = int(gap_match.group(1))

        # Fire rating
        fire_rating_minutes: Optional[int] = None
        frl_match = frl_pattern.search(text)
        if frl_match:
            if frl_match.group(1):
                fire_rating_minutes = int(frl_match.group(1))
            elif frl_match.group(3):
                fire_rating_minutes = int(frl_match.group(3)) * 60

        # Safing type
        safing_type = "MINERAL_WOOL_SAFING"
        if "CERAMIC" in upper_text:
            safing_type = "CERAMIC_BLANKET"

        # Smoke seal type
        smoke_seal_type = "STANDARD"
        if "ELASTOMERIC" in upper_text or "SPRAY" in upper_text:
            smoke_seal_type = "ELASTOMERIC_SPRAY"
        elif "SILICONE" in upper_text:
            smoke_seal_type = "SILICONE_SEALANT"
        elif "INTUMESCENT" in upper_text:
            smoke_seal_type = "INTUMESCENT_SEALANT"
        elif "FOIL" in upper_text:
            smoke_seal_type = "FOIL_BARRIER"

        # Safing clips
        has_safing_clips = any(c in upper_text for c in ["SAFING CLIP", "Z-CLIP", "Z-BRACKET", "IMPALING BRACKET", "SAFING TRAY"])

        # Movement capability
        movement_capability = "STANDARD"
        if "SEISMIC" in upper_text:
            movement_capability = "SEISMIC"
        elif "CLASS III" in upper_text or "CLASS 3" in upper_text:
            movement_capability = "CLASS_III"
        elif "CLASS II" in upper_text or "CLASS 2" in upper_text:
            movement_capability = "CLASS_II"
        elif "CLASS I" in upper_text or "CLASS 1" in upper_text:
            movement_capability = "CLASS_I"
        elif "STATIC" in upper_text:
            movement_capability = "STATIC"

        candidate = PerimeterFirestopCandidate(
            item_id=item_id,
            gap_width_mm=gap_width_mm,
            fire_rating_minutes=fire_rating_minutes,
            safing_type=safing_type,
            smoke_seal_type=smoke_seal_type,
            has_safing_clips=has_safing_clips,
            movement_capability=movement_capability,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
