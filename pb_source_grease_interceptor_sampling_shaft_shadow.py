"""Commercial Kitchen Grease Arrestor / Interceptor Pit & Sampling Shaft Shadow Authority.

Deterministic shadow extraction authority for commercial trade waste grease interceptors,
sampling shafts, remote pump-out lines, gastight covers, and biological dosing units.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GreaseInterceptorCandidate:
    """Extracted commercial grease interceptor candidate."""
    item_id: str
    element_type: str  # "BELOW_GROUND_ARRESTOR", "ABOVE_GROUND_ARRESTOR", "SAMPLING_SHAFT", "PUMP_OUT_LINE", "DOSING_UNIT", "STANDARD"
    tag: str
    capacity_litres: Optional[int]
    tank_material: str  # "PRECAST_CONCRETE", "POLYETHYLENE", "FIBREGLASS_GRP", "STANDARD"
    cover_class: str  # "CLASS_D", "CLASS_B", "GASTIGHT", "STANDARD"
    has_remote_pump_out: bool
    has_coalescing_plates: bool
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
            "capacity_litres": self.capacity_litres,
            "tank_material": self.tank_material,
            "cover_class": self.cover_class,
            "has_remote_pump_out": self.has_remote_pump_out,
            "has_coalescing_plates": self.has_coalescing_plates,
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


def extract_grease_interceptor_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[GreaseInterceptorCandidate]:
    """Extract grease interceptor and sampling shaft candidates deterministically."""
    results: List[GreaseInterceptorCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:GT|GA|GI|SS|TW|GSS)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    capacity_pattern = re.compile(r"\b(\d{3,5})\s*(?:L|LITRE|LITRES|LITER|LITERS|LT)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"gt_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "GROSS POLLUTANT TRAP", "CDS UNIT", "GPT-",
            "SINK BASKET WASTE", "DOMESTIC TRAP", "OIL WATER SEPARATOR",
            "HYDROCARBON COALESCER", "SEPTIC SEWAGE TANK"
        ]):
            continue

        is_grease = any(k in upper_text for k in [
            "GREASE ARRESTOR", "GREASE INTERCEPTOR", "GREASE TRAP", "TRADE WASTE ARRESTOR",
            "TRADE WASTE SAMPLING SHAFT", "SAMPLING SHAFT", "REMOTE PUMP-OUT", "PUMP-OUT LINE",
            "BIO DOSING UNIT"
        ]) or (tag_pattern.search(text) is not None and ("GREASE" in upper_text or "TRADE WASTE" in upper_text or "SAMPLING" in upper_text or "ARRESTOR" in upper_text))

        if not is_grease:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "GT-ITEM"

        # Remote pump out
        has_remote_pump_out = any(po in upper_text for po in [
            "REMOTE PUMP-OUT", "PUMP OUT LINE", "PUMP-OUT LINE", "CAMLOCK", "TANKER SUCTION"
        ])

        # Coalescing plates
        has_coalescing_plates = any(cp in upper_text for cp in [
            "COALESCING PLATE", "COALESCING PACK", "PLATE PACK", "COALESCER"
        ])

        # Element type
        element_type = "BELOW_GROUND_ARRESTOR"
        if "SAMPLING SHAFT" in upper_text or "SS-" in tag or "GSS-" in tag:
            element_type = "SAMPLING_SHAFT"
        elif ("PUMP-OUT" in upper_text or "PUMP OUT" in upper_text or "CAMLOCK" in upper_text) and not any(k in upper_text for k in ["ARRESTOR", "TRAP", "INTERCEPTOR"]):
            element_type = "PUMP_OUT_LINE"
        elif "DOSING" in upper_text or "BIO-DOSING" in upper_text:
            element_type = "DOSING_UNIT"
        elif "ABOVE GROUND" in upper_text or "INDOOR" in upper_text or "BASEMENT SUSPENDED" in upper_text:
            element_type = "ABOVE_GROUND_ARRESTOR"
        elif "BELOW GROUND" in upper_text or "IN-GROUND" in upper_text or "PRECAST CONCRETE" in upper_text or "ARRESTOR" in upper_text or "TRAP" in upper_text or "INTERCEPTOR" in upper_text:
            element_type = "BELOW_GROUND_ARRESTOR"

        # Capacity
        capacity_litres: Optional[int] = None
        cap_match = capacity_pattern.search(text)
        if cap_match:
            val = int(cap_match.group(1))
            if 500 <= val <= 25000:
                capacity_litres = val

        # Tank material
        tank_material = "PRECAST_CONCRETE"
        if "POLYETHYLENE" in upper_text or "POLY" in upper_text or "ROTO-MOULDED" in upper_text:
            tank_material = "POLYETHYLENE"
        elif "FIBREGLASS" in upper_text or "FIBERGLASS" in upper_text or "GRP" in upper_text:
            tank_material = "FIBREGLASS_GRP"
        elif "PRECAST" in upper_text or "CONCRETE" in upper_text:
            tank_material = "PRECAST_CONCRETE"

        # Cover class
        cover_class = "GASTIGHT"
        if "CLASS D" in upper_text or "CLASSD" in upper_text or "HEAVY DUTY TRAFFIC" in upper_text:
            cover_class = "CLASS_D"
        elif "CLASS B" in upper_text or "CLASSB" in upper_text or "LIGHT DUTY" in upper_text:
            cover_class = "CLASS_B"
        elif "GASTIGHT" in upper_text or "SEALED COVER" in upper_text:
            cover_class = "GASTIGHT"

        candidate = GreaseInterceptorCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            capacity_litres=capacity_litres,
            tank_material=tank_material,
            cover_class=cover_class,
            has_remote_pump_out=has_remote_pump_out,
            has_coalescing_plates=has_coalescing_plates,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results