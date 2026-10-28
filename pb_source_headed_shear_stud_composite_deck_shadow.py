"""Structural Steel Welded Headed Shear Stud Connector & Composite Decking Shadow Authority.

Deterministic shadow extraction authority for welded headed shear stud connectors (Nelson studs),
through-deck welding, trapezoidal/re-entrant metal decking, and edge form trims.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class HeadedShearStudCandidate:
    """Extracted headed shear stud / composite deck candidate."""
    item_id: str
    element_type: str  # "SHEAR_STUD_GROUP", "COMPOSITE_DECK", "EDGE_FORM_TRIM", "STANDARD"
    tag: str
    stud_diameter_mm: Optional[int]
    stud_length_mm: Optional[int]
    stud_layout: str  # "ONE_PER_TROUGH", "TWO_PER_TROUGH", "STAGGERED_PAIRS", "CONTINUOUS_PITCH", "STANDARD"
    welding_method: str  # "THROUGH_DECK_WELD", "DIRECT_TO_FLANGE_WELD", "STANDARD"
    deck_profile_type: str  # "TRAPEZOIDAL", "RE_ENTRANT", "NONE", "STANDARD"
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
            "stud_diameter_mm": self.stud_diameter_mm,
            "stud_length_mm": self.stud_length_mm,
            "stud_layout": self.stud_layout,
            "welding_method": self.welding_method,
            "deck_profile_type": self.deck_profile_type,
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


def extract_headed_shear_stud_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[HeadedShearStudCandidate]:
    """Extract headed shear stud candidates deterministically."""
    results: List[HeadedShearStudCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:HSS|SS|STUD|DECK|BONDEK|EF)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    stud_dim_pattern = re.compile(r"\b(16|19|22|25)\s*[xX/]\s*(\d{2,3})\s*(?:MM)?(?:\s*(?:HEADED\s*)?(?:SHEAR\s*)?STUDS?)?\b", re.IGNORECASE)
    dim_fallback_pattern = re.compile(r"\b(?:DIA|D)?\s*(16|19|22|25)\s*MM\s*(?:DIA\s*)?(?:HEADED\s*)?STUDS?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"stud_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "WALL STUD", "DRYWALL STUD", "LGS STUD", "TIMBER STUD",
            "CHEMICAL ANCHOR STUD", "EPOXY STUD", "STIRRUPS", "SHEAR TIES"
        ]):
            continue

        is_stud = any(k in upper_text for k in [
            "HEADED SHEAR STUD", "SHEAR STUD", "NELSON STUD", "COMPOSITE DECK",
            "THROUGH-DECK WELD", "THRU-DECK WELD", "BONDEK", "COMFLOR",
            "CONDEK", "EDGE FORM TRIM", "POUR STOP"
        ]) or (tag_pattern.search(text) is not None and ("STUD" in upper_text or "DECK" in upper_text or "SHEAR" in upper_text or "BONDEK" in upper_text))

        if not is_stud:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "STUD-ITEM"

        # Deck profile type
        deck_profile_type = "TRAPEZOIDAL"
        if "BONDEK" in upper_text or "CONDEK" in upper_text or "RE-ENTRANT" in upper_text or "REENTRANT" in upper_text:
            deck_profile_type = "RE_ENTRANT"
        elif "COMFLOR" in upper_text or "TRAPEZOIDAL" in upper_text or "METAL DECK" in upper_text:
            deck_profile_type = "TRAPEZOIDAL"
        elif "BARE FLANGE" in upper_text or "DIRECT TO FLANGE" in upper_text:
            deck_profile_type = "NONE"

        # Element type
        element_type = "SHEAR_STUD_GROUP"
        if "EDGE FORM" in upper_text or "POUR STOP" in upper_text or "SLAB EDGE TRIM" in upper_text:
            element_type = "EDGE_FORM_TRIM"
        elif ("COMPOSITE DECK" in upper_text or "BONDEK" in upper_text or "COMFLOR" in upper_text) and not ("STUD" in upper_text or "NELSON" in upper_text):
            element_type = "COMPOSITE_DECK"
        elif "SHEAR STUD" in upper_text or "NELSON" in upper_text or "STUD" in upper_text:
            element_type = "SHEAR_STUD_GROUP"

        # Stud dimensions
        stud_diameter_mm: Optional[int] = None
        stud_length_mm: Optional[int] = None

        m_stud = stud_dim_pattern.search(text)
        if m_stud:
            stud_diameter_mm = int(m_stud.group(1))
            stud_length_mm = int(m_stud.group(2))
        else:
            m_fall = dim_fallback_pattern.search(text)
            if m_fall:
                stud_diameter_mm = int(m_fall.group(1))
                if "100" in upper_text:
                    stud_length_mm = 100
                elif "125" in upper_text:
                    stud_length_mm = 125
                elif "150" in upper_text:
                    stud_length_mm = 150
                elif "95" in upper_text:
                    stud_length_mm = 95

        # Welding method
        welding_method = "THROUGH_DECK_WELD"
        if "DIRECT" in upper_text or "BARE FLANGE" in upper_text or "SHOP WELD" in upper_text or deck_profile_type == "NONE":
            welding_method = "DIRECT_TO_FLANGE_WELD"
        elif "THROUGH DECK" in upper_text or "THRU-DECK" in upper_text or "THRU DECK" in upper_text or "THROUGH-DECK" in upper_text:
            welding_method = "THROUGH_DECK_WELD"

        # Stud layout
        stud_layout = "ONE_PER_TROUGH"
        if "2 PER TROUGH" in upper_text or "TWO PER TROUGH" in upper_text or "PAIRS PER TROUGH" in upper_text:
            stud_layout = "TWO_PER_TROUGH"
        elif "STAGGERED" in upper_text:
            stud_layout = "STAGGERED_PAIRS"
        elif "CONTINUOUS" in upper_text or "PITCH" in upper_text or "CENTRES" in upper_text:
            stud_layout = "CONTINUOUS_PITCH"
        elif "1 PER TROUGH" in upper_text or "ONE PER TROUGH" in upper_text or "SINGLE STUD" in upper_text:
            stud_layout = "ONE_PER_TROUGH"

        candidate = HeadedShearStudCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            stud_diameter_mm=stud_diameter_mm,
            stud_length_mm=stud_length_mm,
            stud_layout=stud_layout,
            welding_method=welding_method,
            deck_profile_type=deck_profile_type,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results