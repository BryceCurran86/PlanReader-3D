"""Variable Air Volume (VAV) Terminal Unit & Electric Reheat Coil Shadow Authority.

Deterministic shadow extraction authority for HVAC VAV boxes, fan-powered boxes (FPB),
electric/hydronic reheat coils, inlet diameters, and discharge attenuators.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class VAVTerminalUnitCandidate:
    """Extracted VAV terminal unit candidate."""
    item_id: str
    unit_type: str  # "SINGLE_DUCT_VAV", "FAN_POWERED_PARALLEL", "FAN_POWERED_SERIES", "DUAL_DUCT_VAV", "STANDARD"
    tag: str
    inlet_diameter_mm: Optional[int]
    airflow_lps: Optional[int]
    reheat_type: str  # "ELECTRIC_REHEAT", "HOT_WATER_REHEAT", "NO_REHEAT", "STANDARD"
    reheat_capacity_kw: Optional[float]
    has_discharge_attenuator: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "unit_type": self.unit_type,
            "tag": self.tag,
            "inlet_diameter_mm": self.inlet_diameter_mm,
            "airflow_lps": self.airflow_lps,
            "reheat_type": self.reheat_type,
            "reheat_capacity_kw": self.reheat_capacity_kw,
            "has_discharge_attenuator": self.has_discharge_attenuator,
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


def extract_vav_terminal_unit_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[VAVTerminalUnitCandidate]:
    """Extract VAV terminal unit candidates deterministically."""
    results: List[VAVTerminalUnitCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:VAV|FPB|FPU|TU|CAV)[-_]?(?:[A-Z0-9]{1,5}(?:[-_][A-Z0-9]{1,4})?))\b", re.IGNORECASE)
    inlet_pattern = re.compile(r"\b(?:INLET|SPIGOT|COLLAR|DN|DIA|O)?\s*(400|350|300|250|200|150|125|100)\s*(?:MM|DIA|DN|O)?\s*(?:INLET|SPIGOT|COLLAR)?\b", re.IGNORECASE)
    airflow_pattern = re.compile(r"\b(\d{2,4})\s*(?:L/S|LPS)\b", re.IGNORECASE)
    kw_pattern = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:KW|KILOWATT)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"vav_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "AIR HANDLING UNIT", "AHU-", "PRIMARY AHU",
            "FAN COIL UNIT", "FCU-", "VRF INDOOR",
            "MANUAL VOLUME DAMPER", "MVD-", "FIRE DAMPER",
            "SMOKE DAMPER", "FSD-"
        ]):
            continue

        is_vav = any(k in upper_text for k in [
            "VARIABLE AIR VOLUME", "VAV BOX", "VAV TERMINAL", "FAN POWERED BOX",
            "FPB", "TERMINAL UNIT", "SINGLE DUCT VAV", "THROTTLING VAV", "DUAL DUCT VAV"
        ]) or (tag_pattern.search(text) is not None and ("VAV" in upper_text or "FPB" in upper_text or "TERMINAL" in upper_text or "AIRFLOW" in upper_text))

        if not is_vav:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "VAV-ITEM"

        # Unit type
        unit_type = "SINGLE_DUCT_VAV"
        if "DUAL DUCT" in upper_text:
            unit_type = "DUAL_DUCT_VAV"
        elif "SERIES" in upper_text and ("FAN POWERED" in upper_text or "FPB" in upper_text):
            unit_type = "FAN_POWERED_SERIES"
        elif "PARALLEL" in upper_text and ("FAN POWERED" in upper_text or "FPB" in upper_text):
            unit_type = "FAN_POWERED_PARALLEL"
        elif "FAN POWERED" in upper_text or "FPB" in upper_text:
            unit_type = "FAN_POWERED_PARALLEL"
        elif "SINGLE DUCT" in upper_text or "VAV" in upper_text:
            unit_type = "SINGLE_DUCT_VAV"

        # Reheat Type & Capacity
        reheat_type = "NO_REHEAT"
        reheat_capacity_kw: Optional[float] = None
        kw_match = kw_pattern.search(text)

        if "ELECTRIC REHEAT" in upper_text or "ELECTRIC HEATER" in upper_text or "SCR REHEAT" in upper_text or "E/H" in upper_text:
            reheat_type = "ELECTRIC_REHEAT"
            if kw_match:
                reheat_capacity_kw = float(kw_match.group(1))
        elif "HOT WATER" in upper_text or "LTHW" in upper_text or "HWR" in upper_text or "HEATING COIL" in upper_text:
            reheat_type = "HOT_WATER_REHEAT"
            if kw_match:
                reheat_capacity_kw = float(kw_match.group(1))
        elif "COOLING ONLY" in upper_text or "NO REHEAT" in upper_text:
            reheat_type = "NO_REHEAT"
        elif kw_match:
            reheat_type = "ELECTRIC_REHEAT"
            reheat_capacity_kw = float(kw_match.group(1))

        # Inlet diameter
        inlet_diameter_mm: Optional[int] = None
        for m in inlet_pattern.finditer(text):
            val = int(m.group(1))
            if val in [100, 125, 150, 200, 250, 300, 350, 400]:
                inlet_diameter_mm = val
                break

        # Airflow
        airflow_lps: Optional[int] = None
        af_match = airflow_pattern.search(text)
        if af_match:
            airflow_lps = int(af_match.group(1))

        # Attenuator
        has_discharge_attenuator = any(att in upper_text for att in [
            "ATTENUATOR", "SILENCER", "SOUND BAFFLE", "ACOUSTIC CASING"
        ])

        candidate = VAVTerminalUnitCandidate(
            item_id=item_id,
            unit_type=unit_type,
            tag=tag,
            inlet_diameter_mm=inlet_diameter_mm,
            airflow_lps=airflow_lps,
            reheat_type=reheat_type,
            reheat_capacity_kw=reheat_capacity_kw,
            has_discharge_attenuator=has_discharge_attenuator,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results