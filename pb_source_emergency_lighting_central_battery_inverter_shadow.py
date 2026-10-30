"""Emergency Lighting Central Battery System & Static Inverter Shadow Authority.

Deterministic shadow extraction authority for emergency lighting central battery systems (CBS),
static inverter cubicles, modular battery racks, and addressable monitoring panels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class CentralBatterySystemCandidate:
    """Extracted central battery system or static inverter candidate."""
    item_id: str
    element_type: str  # "CENTRAL_BATTERY_SYSTEM", "STATIC_INVERTER", "BATTERY_RACK", "EMERGENCY_UPS"
    tag: str
    capacity_kva: Optional[float]
    autonomy_minutes: Optional[int]
    battery_chemistry: str  # "VRLA", "LI_ION", "NICD", "GEL", "STANDARD"
    output_voltage: str  # "230V_1PH", "400V_3PH", "110V_DC", "24V_DC", "STANDARD"
    is_dali_addressable: bool
    ip_rating: str  # "IP20", "IP31", "IP54", "IP65", "STANDARD"
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
            "capacity_kva": self.capacity_kva,
            "autonomy_minutes": self.autonomy_minutes,
            "battery_chemistry": self.battery_chemistry,
            "output_voltage": self.output_voltage,
            "is_dali_addressable": self.is_dali_addressable,
            "ip_rating": self.ip_rating,
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


def extract_central_battery_systems(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[CentralBatterySystemCandidate]:
    """Extract emergency lighting central battery systems and static inverters deterministically."""
    results: List[CentralBatterySystemCandidate] = []
    processed_count = 0

    kva_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:KVA|KW)\b", re.IGNORECASE)
    duration_min_pattern = re.compile(r"(\d{2,3})\s*(?:MIN|MINS|MINUTES)\b", re.IGNORECASE)
    duration_hr_pattern = re.compile(r"(\d(?:\.\d+)?)\s*(?:HR|HRS|HOURS?)\s*(?:AUTONOMY|BACKUP|DURATION)?\b", re.IGNORECASE)
    ip_pattern = re.compile(r"\b(IP\s*[2356]\d)\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:CBS|INV|UPS|SI|CBU)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"cbs_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "SOLAR INVERTER", "PV INVERTER", "MOTOR STARTER",
            "FIRE ALARM CONTROL PANEL", "SMOKE DAMPER"
        ]):
            continue

        is_cbs = any(k in upper_text for k in [
            "CENTRAL BATTERY", "STATIC INVERTER", "EMERGENCY LIGHTING INVERTER",
            "EMERGENCY BATTERY", "CBS PANEL", "CENTRAL BATTERY SYSTEM",
            "BATTERY RACK FOR EMERGENCY", "EMERGENCY UPS"
        ]) or (tag_pattern.search(text) is not None and ("EMERGENCY" in upper_text or "BATTERY" in upper_text or "CBS" in upper_text or "INVERTER" in upper_text))

        if not is_cbs:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "CBS-UNIT"

        # Element type
        element_type = "CENTRAL_BATTERY_SYSTEM"
        if "STATIC INVERTER" in upper_text:
            element_type = "STATIC_INVERTER"
        elif "BATTERY RACK" in upper_text:
            element_type = "BATTERY_RACK"
        elif "UPS" in upper_text:
            element_type = "EMERGENCY_UPS"

        # Capacity (kVA)
        capacity_kva: Optional[float] = None
        kva_match = kva_pattern.search(text)
        if kva_match:
            capacity_kva = float(kva_match.group(1))

        # Autonomy (minutes)
        autonomy_minutes: Optional[int] = None
        dur_min_match = duration_min_pattern.search(text)
        if dur_min_match:
            autonomy_minutes = int(dur_min_match.group(1))
        else:
            dur_hr_match = duration_hr_pattern.search(text)
            if dur_hr_match:
                autonomy_minutes = int(float(dur_hr_match.group(1)) * 60)

        # Battery chemistry
        battery_chemistry = "VRLA"
        if "LI-ION" in upper_text or "LIFEPO4" in upper_text or "LITHIUM" in upper_text:
            battery_chemistry = "LI_ION"
        elif "NICD" in upper_text or "NICKEL CADMIUM" in upper_text:
            battery_chemistry = "NICD"
        elif "GEL" in upper_text:
            battery_chemistry = "GEL"
        elif "VRLA" in upper_text or "LEAD ACID" in upper_text:
            battery_chemistry = "VRLA"

        # Output voltage / phase
        output_voltage = "230V_1PH"
        if "400V" in upper_text or "3-PHASE" in upper_text or "3PH" in upper_text:
            output_voltage = "400V_3PH"
        elif "110V" in upper_text or "110V DC" in upper_text:
            output_voltage = "110V_DC"
        elif "24V" in upper_text or "24V DC" in upper_text:
            output_voltage = "24V_DC"
        elif "230V" in upper_text or "1-PHASE" in upper_text or "1PH" in upper_text:
            output_voltage = "230V_1PH"

        # DALI addressable
        is_dali_addressable = any(d in upper_text for d in ["DALI", "ADDRESSABLE", "AUTOMATIC TEST SYSTEM", "ATS"])

        # IP Rating
        ip_rating = "STANDARD"
        ip_match = ip_pattern.search(text)
        if ip_match:
            ip_rating = ip_match.group(1).replace(" ", "").upper()

        candidate = CentralBatterySystemCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            capacity_kva=capacity_kva,
            autonomy_minutes=autonomy_minutes,
            battery_chemistry=battery_chemistry,
            output_voltage=output_voltage,
            is_dali_addressable=is_dali_addressable,
            ip_rating=ip_rating,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
