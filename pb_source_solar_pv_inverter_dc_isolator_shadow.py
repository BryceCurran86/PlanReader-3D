"""Solar PV Roof Array DC Isolator Switch & Inverter Shadow Authority.

Deterministic shadow extraction authority for solar PV inverters, rooftop DC isolator
switches, combiner boxes, and balance of system components from electrical plans.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SolarPVItemCandidate:
    """Extracted solar PV electrical item candidate."""
    item_id: str
    element_type: str  # "DC_ISOLATOR", "STRING_INVERTER", "CENTRAL_INVERTER", "COMBINER_BOX"
    tag: str
    power_rating_kw: Optional[float]
    voltage_rating_v: Optional[int]
    current_rating_a: Optional[int]
    ip_rating: str  # "IP66", "IP65", "IP56", "STANDARD"
    mounting_type: str  # "ROOF_MOUNTED", "WALL_MOUNTED", "SHADE_COVERED", "STANDARD"
    mppt_channels: Optional[int]
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
            "power_rating_kw": self.power_rating_kw,
            "voltage_rating_v": self.voltage_rating_v,
            "current_rating_a": self.current_rating_a,
            "ip_rating": self.ip_rating,
            "mounting_type": self.mounting_type,
            "mppt_channels": self.mppt_channels,
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


def extract_solar_pv_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SolarPVItemCandidate]:
    """Extract solar PV inverters and DC isolators deterministically."""
    results: List[SolarPVItemCandidate] = []
    processed_count = 0

    kw_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:KW|KVA)\b", re.IGNORECASE)
    volt_pattern = re.compile(r"(\d{3,4})\s*V(?:\s*DC)?\b", re.IGNORECASE)
    amp_pattern = re.compile(r"\b(\d{2,3})\s*A(?:MP)?\b", re.IGNORECASE)
    ip_pattern = re.compile(r"\b(IP\s*[56]\d)\b", re.IGNORECASE)
    mppt_pattern = re.compile(r"(\d{1,2})\s*MPPT\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:INV|DCI|DC-ISO|PV-INV|CB|COMB)[-_]?\d{1,3}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"pv_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "AC ISOLATOR", "MAIN SWITCHBOARD", "DISTRIBUTION BOARD",
            "MOTOR CONTROL CENTER", "SMOKE DAMPER", "FIRE HYDRANT"
        ]):
            continue

        is_pv_item = any(k in upper_text for k in [
            "DC ISOLATOR", "SOLAR INVERTER", "PV INVERTER", "STRING INVERTER",
            "CENTRAL INVERTER", "COMBINER BOX", "ROOFTOP ISOLATOR", "SOLAR PV ARRAY"
        ]) or tag_pattern.search(text) is not None and ("PV" in upper_text or "INV" in upper_text or "DC" in upper_text)

        if not is_pv_item:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "PV-ITEM"

        # Element type
        element_type = "DC_ISOLATOR"
        if "STRING INVERTER" in upper_text or ("INVERTER" in upper_text and "CENTRAL" not in upper_text):
            element_type = "STRING_INVERTER"
        elif "CENTRAL INVERTER" in upper_text:
            element_type = "CENTRAL_INVERTER"
        elif "COMBINER" in upper_text:
            element_type = "COMBINER_BOX"
        elif "DC ISOLATOR" in upper_text or "DC-ISO" in upper_text or "ROOFTOP ISOLATOR" in upper_text:
            element_type = "DC_ISOLATOR"

        # Ratings
        power_rating_kw: Optional[float] = None
        kw_match = kw_pattern.search(text)
        if kw_match:
            power_rating_kw = float(kw_match.group(1))

        voltage_rating_v: Optional[int] = None
        volt_match = volt_pattern.search(text)
        if volt_match:
            voltage_rating_v = int(volt_match.group(1))

        current_rating_a: Optional[int] = None
        amp_match = amp_pattern.search(text)
        if amp_match:
            current_rating_a = int(amp_match.group(1))

        # IP Rating
        ip_rating = "STANDARD"
        ip_match = ip_pattern.search(text)
        if ip_match:
            ip_rating = ip_match.group(1).replace(" ", "").upper()

        # Mounting
        mounting_type = "STANDARD"
        if "SHADE" in upper_text or "SUNSHADE" in upper_text or "CANOPY" in upper_text:
            mounting_type = "SHADE_COVERED"
        elif "ROOF" in upper_text:
            mounting_type = "ROOF_MOUNTED"
        elif "WALL" in upper_text:
            mounting_type = "WALL_MOUNTED"

        # MPPT
        mppt_channels: Optional[int] = None
        mppt_match = mppt_pattern.search(text)
        if mppt_match:
            mppt_channels = int(mppt_match.group(1))

        candidate = SolarPVItemCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            power_rating_kw=power_rating_kw,
            voltage_rating_v=voltage_rating_v,
            current_rating_a=current_rating_a,
            ip_rating=ip_rating,
            mounting_type=mounting_type,
            mppt_channels=mppt_channels,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
