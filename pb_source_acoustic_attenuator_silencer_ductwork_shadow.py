"""HVAC Ductwork In-Line Sound Attenuator Silencer Shadow Authority.

Deterministic shadow extraction authority for HVAC sound attenuators, silencers,
and cross-talk acoustic baffles in mechanical ventilation drawings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SoundAttenuatorCandidate:
    """Extracted HVAC sound attenuator or silencer candidate."""
    item_id: str
    tag: str
    shape_profile: str  # "RECTANGULAR", "CIRCULAR", "CROSSTALK", "ELBOW"
    system_service: str  # "SUPPLY_AIR", "RETURN_AIR", "EXHAUST_AIR", "OUTSIDE_AIR", "GENERAL"
    media_type: str  # "DISSIPATIVE", "PACKLESS", "HYGIENIC_MYLAR", "STANDARD"
    width_mm: Optional[int]
    height_mm: Optional[int]
    diameter_mm: Optional[int]
    length_mm: Optional[int]
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "tag": self.tag,
            "shape_profile": self.shape_profile,
            "system_service": self.system_service,
            "media_type": self.media_type,
            "width_mm": self.width_mm,
            "height_mm": self.height_mm,
            "diameter_mm": self.diameter_mm,
            "length_mm": self.length_mm,
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


def extract_sound_attenuators(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SoundAttenuatorCandidate]:
    """Extract HVAC duct sound attenuators and silencers deterministically."""
    results: List[SoundAttenuatorCandidate] = []
    processed_count = 0

    # Dimension patterns
    rect_dim_pattern = re.compile(r"\b(\d{2,4})\s*[xX]\s*(\d{2,4})(?:MM)?\b")
    circ_dim_pattern = re.compile(r"(?:Ø|\bDN\s*|\bDIA\s*|\bROUND\s*)(\d{2,4})\b", re.IGNORECASE)
    circ_suffix_pattern = re.compile(r"\b(\d{2,4})\s*(?:DIA|Ø|MM\s*DIA)\b", re.IGNORECASE)
    length_pattern = re.compile(r"(?:L\s*=\s*|LENGTH\s*=\s*|\bL\b\s*)(\d{3,4})\b|\b(\d{3,4})\s*(?:MM\s*)?(?:LG|LONG)\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:ATT|SIL|SA|CT)[-_]?\d{1,3}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"att_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIRE DAMPER", "SMOKE DAMPER", "VAV BOX", "VOLUME DAMPER",
            "FLEXIBLE DUCT", "DIFFUSER", "GRILLE", "LOUVER", "EXHAUST HOOD"
        ]):
            continue

        is_attenuator = any(k in upper_text for k in [
            "ATTENUATOR", "SILENCER", "SOUND ATTENUATOR", "ACOUSTIC SILENCER",
            "CROSS-TALK", "CROSSTALK", "IN-LINE SILENCER"
        ]) or tag_pattern.search(text) is not None

        if not is_attenuator:
            continue

        # Extract tag
        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "ATT"

        # Determine shape profile
        shape_profile = "RECTANGULAR"
        if "CROSSTALK" in upper_text or "CROSS-TALK" in upper_text:
            shape_profile = "CROSSTALK"
        elif "ELBOW" in upper_text:
            shape_profile = "ELBOW"
        elif any(c in upper_text for c in ["CIRCULAR", "ROUND", "CYLINDRICAL"]) or "Ø" in text:
            shape_profile = "CIRCULAR"

        # System service
        system_service = "GENERAL"
        if any(s in upper_text for s in ["SUPPLY", "SA ", "S/A", "SUPPLY AIR"]):
            system_service = "SUPPLY_AIR"
        elif any(r in upper_text for r in ["RETURN", "RA ", "R/A", "RETURN AIR"]):
            system_service = "RETURN_AIR"
        elif any(e in upper_text for e in ["EXHAUST", "EA ", "E/A", "EXHAUST AIR"]):
            system_service = "EXHAUST_AIR"
        elif any(o in upper_text for o in ["OUTSIDE AIR", "OA ", "O/A", "FRESH AIR"]):
            system_service = "OUTSIDE_AIR"

        # Media type
        media_type = "STANDARD"
        if "PACKLESS" in upper_text or "NO MEDIA" in upper_text:
            media_type = "PACKLESS"
        elif "MYLAR" in upper_text or "HYGIENIC" in upper_text or "CLEANROOM" in upper_text:
            media_type = "HYGIENIC_MYLAR"
        elif "DISSIPATIVE" in upper_text or "MINERAL WOOL" in upper_text or "FIBERGLASS" in upper_text:
            media_type = "DISSIPATIVE"

        # Dimensions
        width_mm: Optional[int] = None
        height_mm: Optional[int] = None
        diameter_mm: Optional[int] = None
        length_mm: Optional[int] = None

        len_match = length_pattern.search(text)
        if len_match:
            length_mm = int(len_match.group(1) or len_match.group(2))

        rect_match = rect_dim_pattern.search(text)
        if rect_match:
            w = int(rect_match.group(1))
            h = int(rect_match.group(2))
            width_mm = w
            height_mm = h
        else:
            circ_match = circ_dim_pattern.search(text) or circ_suffix_pattern.search(text)
            if circ_match:
                diameter_mm = int(circ_match.group(1))
                shape_profile = "CIRCULAR"

        candidate = SoundAttenuatorCandidate(
            item_id=item_id,
            tag=tag,
            shape_profile=shape_profile,
            system_service=system_service,
            media_type=media_type,
            width_mm=width_mm,
            height_mm=height_mm,
            diameter_mm=diameter_mm,
            length_mm=length_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
