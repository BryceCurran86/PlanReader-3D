"""Commercial Kitchen Exhaust Hood Grease Filter & Ansul Fire Suppression Shadow Authority.

Deterministic shadow extraction authority for commercial kitchen exhaust hoods,
stainless steel baffle filters, UV-C grease destruction, and Ansul wet chemical fire suppression.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class KitchenHoodCandidate:
    """Extracted commercial kitchen hood / fire suppression candidate."""
    item_id: str
    hood_type: str  # "TYPE_1_GREASE_HOOD", "TYPE_2_CONDENSATE_HOOD", "ISLAND_CANOPY", "WALL_MOUNTED_CANOPY", "STANDARD"
    tag: str
    length_mm: Optional[int]
    width_mm: Optional[int]
    filter_type: str  # "BAFFLE_GREASE_FILTER", "UV_C_SYSTEM", "WATER_WASH", "MESH_FILTER", "STANDARD"
    has_fire_suppression: bool
    fire_suppression_brand: Optional[str]  # e.g. "ANSUL_R102", "AMEREX_KP"
    exhaust_airflow_lps: Optional[int]
    has_gas_interlock: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "hood_type": self.hood_type,
            "tag": self.tag,
            "length_mm": self.length_mm,
            "width_mm": self.width_mm,
            "filter_type": self.filter_type,
            "has_fire_suppression": self.has_fire_suppression,
            "fire_suppression_brand": self.fire_suppression_brand,
            "exhaust_airflow_lps": self.exhaust_airflow_lps,
            "has_gas_interlock": self.has_gas_interlock,
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


def extract_kitchen_hood_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[KitchenHoodCandidate]:
    """Extract commercial kitchen exhaust hood candidates deterministically."""
    results: List[KitchenHoodCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:KH|CKH|HOOD|EC|KEH)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    dim_pattern = re.compile(r"\b(\d{3,4})\s*[xX]\s*(\d{3,4})(?:\s*MM)?\b", re.IGNORECASE)
    airflow_pattern = re.compile(r"\b(\d{3,5})\s*(?:L/S|LPS|L/SEC)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"kh_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "DOMESTIC RANGEHOOD", "UNDER-CABINET", "FUME CUPBOARD",
            "LABORATORY FUME HOOD", "BIOSAFETY CABINET", "LAMINAR FLOW",
            "EXHAUST LOUVER"
        ]):
            continue

        is_hood = any(k in upper_text for k in [
            "KITCHEN EXHAUST HOOD", "EXHAUST HOOD", "GREASE HOOD", "CANOPY HOOD",
            "EXHAUST CANOPY", "CONDENSATE HOOD", "KITCHEN HOOD", "ANSUL",
            "WET CHEMICAL SUPPRESSION", "BAFFLE FILTER"
        ]) or (tag_pattern.search(text) is not None and ("HOOD" in upper_text or "CANOPY" in upper_text or "KITCHEN" in upper_text or "GREASE" in upper_text or "FILTER" in upper_text))

        if not is_hood:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "KH-ITEM"

        # Dimensions
        length_mm: Optional[int] = None
        width_mm: Optional[int] = None
        dim_match = dim_pattern.search(text)
        if dim_match:
            d1, d2 = int(dim_match.group(1)), int(dim_match.group(2))
            length_mm = max(d1, d2)
            width_mm = min(d1, d2)

        # Airflow
        exhaust_airflow_lps: Optional[int] = None
        af_match = airflow_pattern.search(text)
        if af_match:
            val = int(af_match.group(1))
            if 150 <= val <= 10000:
                exhaust_airflow_lps = val

        # Filter type
        filter_type = "BAFFLE_GREASE_FILTER"
        if "UV-C" in upper_text or "UVC" in upper_text or "ULTRAVIOLET" in upper_text:
            filter_type = "UV_C_SYSTEM"
        elif "WATER WASH" in upper_text or "WATER-WASH" in upper_text:
            filter_type = "WATER_WASH"
        elif "MESH" in upper_text and "BAFFLE" not in upper_text:
            filter_type = "MESH_FILTER"
        elif "BAFFLE" in upper_text or "GREASE FILTER" in upper_text:
            filter_type = "BAFFLE_GREASE_FILTER"

        # Fire suppression & Brand
        has_fire_suppression = False
        if not ("NO FIRE SUPPRESSION" in upper_text or "WITHOUT FIRE SUPPRESSION" in upper_text or "NO ANSUL" in upper_text):
            has_fire_suppression = any(fs in upper_text for fs in [
                "ANSUL", "AMEREX", "WET CHEMICAL", "FIRE SUPPRESSION", "PYRO-CHEM", "R-102", "R102"
            ])
        fire_suppression_brand: Optional[str] = None
        if has_fire_suppression:
            if "ANSUL" in upper_text or "R-102" in upper_text or "R102" in upper_text:
                fire_suppression_brand = "ANSUL_R102"
            elif "AMEREX" in upper_text or ("KP" in upper_text and "AMEREX" in upper_text):
                fire_suppression_brand = "AMEREX_KP"
            else:
                fire_suppression_brand = "ANSUL_R102"

        # Gas interlock
        has_gas_interlock = any(gi in upper_text for gi in [
            "GAS INTERLOCK", "GAS SOLENOID", "GAS SHUT OFF", "GAS SHUTOFF", "VALVE INTERLOCK"
        ])

        # Hood type
        hood_type = "TYPE_1_GREASE_HOOD"
        if "TYPE 2" in upper_text or "CONDENSATE" in upper_text or "DISHWASHER" in upper_text or "STEAM HOOD" in upper_text:
            hood_type = "TYPE_2_CONDENSATE_HOOD"
        elif "ISLAND" in upper_text:
            hood_type = "ISLAND_CANOPY"
        elif "WALL" in upper_text:
            hood_type = "WALL_MOUNTED_CANOPY"
        elif "TYPE 1" in upper_text or "GREASE" in upper_text or has_fire_suppression:
            hood_type = "TYPE_1_GREASE_HOOD"

        candidate = KitchenHoodCandidate(
            item_id=item_id,
            hood_type=hood_type,
            tag=tag,
            length_mm=length_mm,
            width_mm=width_mm,
            filter_type=filter_type,
            has_fire_suppression=has_fire_suppression,
            fire_suppression_brand=fire_suppression_brand,
            exhaust_airflow_lps=exhaust_airflow_lps,
            has_gas_interlock=has_gas_interlock,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results