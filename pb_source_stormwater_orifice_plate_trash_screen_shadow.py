"""Civil Stormwater Detention Orifice Plate & Trash Screen Pit Shadow Authority.

Deterministic shadow extraction authority for civil stormwater OSD discharge control
pits (DCP), stainless steel orifice plates, trash screens, and overflow weirs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class StormwaterOrificeCandidate:
    """Extracted stormwater orifice plate / trash screen candidate."""
    item_id: str
    element_type: str  # "ORIFICE_PLATE", "TRASH_SCREEN", "DISCHARGE_CONTROL_PIT", "OVERFLOW_WEIR", "STANDARD"
    tag: str
    orifice_diameter_mm: Optional[int]
    plate_material: str  # "STAINLESS_316", "STAINLESS_304", "GALVANIZED_STEEL", "STANDARD"
    trash_screen_type: str  # "INCLINED_SCREEN", "VERTICAL_CAGE", "STEPPED_SCREEN", "STANDARD"
    has_overflow_weir: bool
    weir_width_mm: Optional[int]
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
            "orifice_diameter_mm": self.orifice_diameter_mm,
            "plate_material": self.plate_material,
            "trash_screen_type": self.trash_screen_type,
            "has_overflow_weir": self.has_overflow_weir,
            "weir_width_mm": self.weir_width_mm,
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


def extract_stormwater_orifice_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[StormwaterOrificeCandidate]:
    """Extract stormwater orifice plate and DCP candidates deterministically."""
    results: List[StormwaterOrificeCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:DCP|OP|TS|OSD|WEIR)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    orifice_pattern = re.compile(r"\b(?:DO\s*[:=]?|ORIFICE\s*(?:DIA(?:METER)?)?\s*[:=]?)?\s*(\d{2,3})\s*MM\s*(?:DIA(?:METER)?|O)?\s*(?:ORIFICE|RESTRICTOR|PLATE)?\b", re.IGNORECASE)
    weir_pattern = re.compile(r"(?:WEIR\s*(?:WIDTH|CREST)?\s*[:=]?\s*(\d{3,4})\s*MM|\b(\d{3,4})\s*MM\s*(?:WIDE|WEIR)\b)", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"dcp_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "ROOF DRAIN STRAINER", "LEAF GUARD DOME", "KERB GULLY INLET",
            "TYPE SA PIT", "HEELGUARD TRENCH", "SLOTTED CAST IRON",
            "GREASE TRAP BAFFLE", "SEWER INSPECTION"
        ]):
            continue

        is_dcp = any(k in upper_text for k in [
            "ORIFICE PLATE", "DISCHARGE CONTROL PIT", "DCP", "TRASH SCREEN",
            "OSD OUTLET PIT", "DISCHARGE RESTRICTOR", "ORIFICE RESTRICTOR",
            "DETENTION ORIFICE", "OSD ORIFICE"
        ]) or (tag_pattern.search(text) is not None and ("ORIFICE" in upper_text or "SCREEN" in upper_text or "PIT" in upper_text or "WEIR" in upper_text))

        if not is_dcp:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "DCP-ITEM"

        # Overflow weir
        has_overflow_weir = any(w in upper_text for w in [
            "OVERFLOW WEIR", "WEIR CREST", "WEIR OVERFLOW", "INTERNAL WEIR"
        ])
        weir_width_mm: Optional[int] = None
        if has_overflow_weir:
            w_match = weir_pattern.search(text)
            if w_match:
                val = int(w_match.group(1) or w_match.group(2))
                if 200 <= val <= 3000:
                    weir_width_mm = val

        # Element type
        element_type = "DISCHARGE_CONTROL_PIT"
        if "DISCHARGE CONTROL PIT" in upper_text or "DCP" in upper_text or "OUTLET PIT" in upper_text or "DCP-" in tag:
            element_type = "DISCHARGE_CONTROL_PIT"
        elif "TRASH SCREEN" in upper_text or "MAXI-MESH" in upper_text or "DEBRIS SCREEN" in upper_text or "TS-" in tag:
            element_type = "TRASH_SCREEN"
        elif "ORIFICE PLATE" in upper_text or "ORIFICE RESTRICTOR" in upper_text or "OP-" in tag:
            element_type = "ORIFICE_PLATE"
        elif "OVERFLOW WEIR" in upper_text:
            element_type = "OVERFLOW_WEIR"

        # Orifice diameter
        orifice_diameter_mm: Optional[int] = None
        for m in orifice_pattern.finditer(text):
            val = int(m.group(1))
            if 30 <= val <= 350:
                orifice_diameter_mm = val
                break

        # Plate material
        plate_material = "STAINLESS_316"
        if "316" in upper_text or "SS316" in upper_text:
            plate_material = "STAINLESS_316"
        elif "304" in upper_text or "SS304" in upper_text:
            plate_material = "STAINLESS_304"
        elif "GALV" in upper_text or "HDG" in upper_text:
            plate_material = "GALVANIZED_STEEL"

        # Trash screen type
        trash_screen_type = "INCLINED_SCREEN"
        if "VERTICAL" in upper_text or "BOX CAGE" in upper_text:
            trash_screen_type = "VERTICAL_CAGE"
        elif "STEPPED" in upper_text:
            trash_screen_type = "STEPPED_SCREEN"
        elif "INCLINED" in upper_text or "45 DEG" in upper_text or "45°" in upper_text or "SCREEN" in upper_text:
            trash_screen_type = "INCLINED_SCREEN"

        candidate = StormwaterOrificeCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            orifice_diameter_mm=orifice_diameter_mm,
            plate_material=plate_material,
            trash_screen_type=trash_screen_type,
            has_overflow_weir=has_overflow_weir,
            weir_width_mm=weir_width_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results