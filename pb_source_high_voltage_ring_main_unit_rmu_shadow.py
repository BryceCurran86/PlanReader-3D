"""High-Voltage Electrical Ring Main Unit (RMU) & SF6/Dry Air Switchgear Shadow Authority.

Deterministic shadow extraction authority for 11kV/22kV/33kV ring main units (RMU),
SF6/dry air switchgear, vacuum circuit breakers (VCB), and IAC arc containment.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class HighVoltageRMUCandidate:
    """Extracted high voltage ring main unit candidate."""
    item_id: str
    switchgear_type: str  # "RING_MAIN_UNIT", "CIRCUIT_BREAKER_UNIT", "METERING_UNIT", "EXTENSIBLE_SWITCHGEAR", "STANDARD"
    tag: str
    rated_voltage_kv: Optional[int]
    switch_function_desc: Optional[str]  # e.g. "3-way CCV", "4-way CCVV"
    insulation_medium: str  # "SF6_GAS", "DRY_AIR_SF6_FREE", "SOLID_INSULATED", "STANDARD"
    short_circuit_ka: Optional[int]
    has_iac_arc_containment: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "switchgear_type": self.switchgear_type,
            "tag": self.tag,
            "rated_voltage_kv": self.rated_voltage_kv,
            "switch_function_desc": self.switch_function_desc,
            "insulation_medium": self.insulation_medium,
            "short_circuit_ka": self.short_circuit_ka,
            "has_iac_arc_containment": self.has_iac_arc_containment,
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


def extract_high_voltage_rmu_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[HighVoltageRMUCandidate]:
    """Extract high voltage RMU switchgear candidates deterministically."""
    results: List[HighVoltageRMUCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:RMU|HVSWG|SWG|HV|VCB|LBS)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    voltage_pattern = re.compile(r"\b(11|22|33|6\.6)\s*KV\b", re.IGNORECASE)
    ka_pattern = re.compile(r"\b(16|20|21|25|31\.5)\s*KA\b", re.IGNORECASE)
    way_pattern = re.compile(r"\b([23456])[-\s]*WAY\b", re.IGNORECASE)
    function_code_pattern = re.compile(r"\b(CCV|CCVV|CCCV|CVC|CCCC)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"rmu_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "415V", "400V", "MAIN SWITCHBOARD 4", "LV SWITCHBOARD",
            "415V MCC", "TRANSFORMER 11KV/415V", "CAST RESIN TRANSFORMER",
            "110V DC BATTERY", "DC TRIPPING"
        ]):
            continue

        is_rmu = any(k in upper_text for k in [
            "RING MAIN UNIT", "RMU", "HIGH VOLTAGE SWITCHGEAR", "HV SWITCHGEAR",
            "GAS INSULATED SWITCHGEAR", "GIS SWITCHGEAR", "VACUUM CIRCUIT BREAKER",
            "11KV SWITCHGEAR", "22KV SWITCHGEAR", "33KV SWITCHGEAR"
        ]) or (tag_pattern.search(text) is not None and ("RMU" in upper_text or "HV" in upper_text or "SWITCHGEAR" in upper_text or "KV" in upper_text))

        if not is_rmu:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "RMU-ITEM"

        # Arc containment
        has_iac_arc_containment = any(iac in upper_text for iac in [
            "IAC", "AFLR", "INTERNAL ARC", "ARC CLASSIFIED"
        ])

        # Insulation medium
        insulation_medium = "SF6_GAS"
        if "DRY AIR" in upper_text or "SF6-FREE" in upper_text or "CLEAN AIR" in upper_text:
            insulation_medium = "DRY_AIR_SF6_FREE"
        elif "SOLID INSULATED" in upper_text or "SOLID DIELECTRIC" in upper_text:
            insulation_medium = "SOLID_INSULATED"
        elif "SF6" in upper_text or "GAS INSULATED" in upper_text:
            insulation_medium = "SF6_GAS"

        # Switchgear type
        switchgear_type = "RING_MAIN_UNIT"
        if "METERING" in upper_text or "VT/CT" in upper_text or "TARIFF" in upper_text:
            switchgear_type = "METERING_UNIT"
        elif "EXTENSIBLE" in upper_text:
            switchgear_type = "EXTENSIBLE_SWITCHGEAR"
        elif "CIRCUIT BREAKER" in upper_text and "RING MAIN" not in upper_text and "RMU" not in upper_text:
            switchgear_type = "CIRCUIT_BREAKER_UNIT"
        elif "RING MAIN" in upper_text or "RMU" in upper_text:
            switchgear_type = "RING_MAIN_UNIT"

        # Voltage
        rated_voltage_kv: Optional[int] = None
        v_match = voltage_pattern.search(text)
        if v_match:
            try:
                rated_voltage_kv = int(v_match.group(1))
            except ValueError:
                pass

        # Breaking capacity kA
        short_circuit_ka: Optional[int] = None
        ka_match = ka_pattern.search(text)
        if ka_match:
            try:
                short_circuit_ka = int(round(float(ka_match.group(1))))
            except ValueError:
                pass

        # Switch function description
        switch_function_desc: Optional[str] = None
        way_m = way_pattern.search(text)
        code_m = function_code_pattern.search(text)
        if way_m and code_m:
            switch_function_desc = f"{way_m.group(1)}-way {code_m.group(1).upper()}"
        elif way_m:
            switch_function_desc = f"{way_m.group(1)}-way"
        elif code_m:
            switch_function_desc = code_m.group(1).upper()

        candidate = HighVoltageRMUCandidate(
            item_id=item_id,
            switchgear_type=switchgear_type,
            tag=tag,
            rated_voltage_kv=rated_voltage_kv,
            switch_function_desc=switch_function_desc,
            insulation_medium=insulation_medium,
            short_circuit_ka=short_circuit_ka,
            has_iac_arc_containment=has_iac_arc_containment,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results