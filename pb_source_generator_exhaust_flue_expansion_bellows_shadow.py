"""Emergency Generator Exhaust Flue & Expansion Bellows Compensator Shadow Authority.

Deterministic shadow extraction authority for emergency generator exhaust flue systems,
corrugated stainless steel expansion bellows, critical silencers, and discharge cowls.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GeneratorExhaustCandidate:
    """Extracted emergency generator exhaust component candidate."""
    item_id: str
    element_type: str  # "EXHAUST_FLUE", "EXPANSION_BELLOWS", "EXHAUST_SILENCER", "DISCHARGE_COWL", "WALL_THIMBLE", "STANDARD"
    tag: str
    flue_diameter_mm: Optional[int]
    wall_construction: str  # "TWIN_WALL_INSULATED", "SINGLE_WALL_CLAD", "UNINSULATED", "STANDARD"
    flue_material: str  # "STAINLESS_316", "STAINLESS_304", "MILD_STEEL", "STANDARD"
    silencer_attenuation_grade: Optional[str]  # "HOSPITAL", "CRITICAL", "RESIDENTIAL", "INDUSTRIAL", "STANDARD"
    has_drain_plug: bool
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
            "flue_diameter_mm": self.flue_diameter_mm,
            "wall_construction": self.wall_construction,
            "flue_material": self.flue_material,
            "silencer_attenuation_grade": self.silencer_attenuation_grade,
            "has_drain_plug": self.has_drain_plug,
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


def extract_generator_exhaust_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[GeneratorExhaustCandidate]:
    """Extract generator exhaust candidates deterministically."""
    results: List[GeneratorExhaustCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:GEN[-_]?EX|EXH|SIL|BEL|THM|COWL)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    diameter_pattern = re.compile(r"\b(?:DN|DIA|O)?\s*(500|450|400|350|300|250|200|150|125|100)\s*(?:MM|DIA|DN|O)?\s*(?:EXHAUST|FLUE|PIPE|BELLOWS|SILENCER)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"gen_ex_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "BOILER FLUE", "CONDENSING BOILER", "HOT WATER HEATER FLUE",
            "KITCHEN HOOD EXHAUST", "GREASE DUCT", "TOILET EXHAUST DUCT",
            "EXHAUST AIR DUCT", "EAD-", "FUEL SUPPLY PIPE", "DIESEL OIL LINE"
        ]):
            continue

        is_gen_ex = any(k in upper_text for k in [
            "GENERATOR EXHAUST", "GENSET EXHAUST", "DIESEL EXHAUST",
            "ENGINE EXHAUST", "EXHAUST BELLOWS", "EXHAUST SILENCER",
            "EXHAUST THIMBLE", "EXHAUST COWL"
        ]) or (tag_pattern.search(text) is not None and ("EXHAUST" in upper_text or "GEN" in upper_text or "BELLOWS" in upper_text or "SILENCER" in upper_text))

        if not is_gen_ex:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "GEN-EX-ITEM"

        # Drain plug
        has_drain_plug = any(d in upper_text for d in [
            "DRAIN PLUG", "DRAIN TRAP", "CONDENSATE DRAIN", "DRAIN VALVE", "DRAIN LEG"
        ])

        # Element type
        element_type = "EXHAUST_FLUE"
        if "BELLOWS" in upper_text or "EXPANSION COMPENSATOR" in upper_text or "BEL-" in tag:
            element_type = "EXPANSION_BELLOWS"
        elif "SILENCER" in upper_text or "MUFFLER" in upper_text or "SIL-" in tag:
            element_type = "EXHAUST_SILENCER"
        elif "COWL" in upper_text or "RAIN CAP" in upper_text or "DISCHARGE CONE" in upper_text or "JET CAP" in upper_text:
            element_type = "DISCHARGE_COWL"
        elif "THIMBLE" in upper_text or "PENETRATION SLEEVE" in upper_text:
            element_type = "WALL_THIMBLE"
        elif "FLUE" in upper_text or "EXHAUST PIPE" in upper_text or "STACK" in upper_text:
            element_type = "EXHAUST_FLUE"

        # Diameter
        flue_diameter_mm: Optional[int] = None
        for m in diameter_pattern.finditer(text):
            val = int(m.group(1))
            if val in [100, 125, 150, 200, 250, 300, 350, 400, 450, 500]:
                flue_diameter_mm = val
                break

        # Wall construction
        wall_construction = "TWIN_WALL_INSULATED"
        if "TWIN WALL" in upper_text or "DOUBLE WALL" in upper_text or "FACTORY INSULATED" in upper_text:
            wall_construction = "TWIN_WALL_INSULATED"
        elif "SINGLE WALL" in upper_text or "LAGGED" in upper_text or "CLAD" in upper_text:
            wall_construction = "SINGLE_WALL_CLAD"
        elif "UNINSULATED" in upper_text or "BARE" in upper_text:
            wall_construction = "UNINSULATED"

        # Flue material
        flue_material = "STAINLESS_316"
        if "316" in upper_text or "SS316" in upper_text or "GRADE 316" in upper_text:
            flue_material = "STAINLESS_316"
        elif "304" in upper_text or "SS304" in upper_text:
            flue_material = "STAINLESS_304"
        elif "MILD STEEL" in upper_text or "CARBON STEEL" in upper_text:
            flue_material = "MILD_STEEL"

        # Silencer attenuation grade
        silencer_attenuation_grade: Optional[str] = None
        if "HOSPITAL" in upper_text:
            silencer_attenuation_grade = "HOSPITAL"
        elif "CRITICAL" in upper_text:
            silencer_attenuation_grade = "CRITICAL"
        elif "RESIDENTIAL" in upper_text:
            silencer_attenuation_grade = "RESIDENTIAL"
        elif "INDUSTRIAL" in upper_text:
            silencer_attenuation_grade = "INDUSTRIAL"
        elif element_type == "EXHAUST_SILENCER":
            silencer_attenuation_grade = "CRITICAL"

        candidate = GeneratorExhaustCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            flue_diameter_mm=flue_diameter_mm,
            wall_construction=wall_construction,
            flue_material=flue_material,
            silencer_attenuation_grade=silencer_attenuation_grade,
            has_drain_plug=has_drain_plug,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results