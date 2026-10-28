"""Cold Water Pressure Booster Pump Hydro-Pneumatic Variable Speed Skid Shadow Authority.

Deterministic shadow extraction authority for potable water booster skids, VFD pumps,
hydro-pneumatic diaphragm tanks, stainless manifolds, and vibration isolation mounts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PotableWaterBoosterCandidate:
    """Extracted potable water booster pump skid candidate."""
    item_id: str
    skid_configuration: str  # "DUPLEX", "TRIPLEX", "QUADRUPLEX", "SIMPLEX", "STANDARD"
    tag: str
    pump_count: int
    flow_rate_lps: Optional[float]
    design_head_m: Optional[float]
    pressure_vessel_litres: Optional[int]
    has_vfd_control: bool
    manifold_material: str  # "STAINLESS_304", "STAINLESS_316", "COPPER", "STANDARD"
    has_anti_vibration_mounts: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "skid_configuration": self.skid_configuration,
            "tag": self.tag,
            "pump_count": self.pump_count,
            "flow_rate_lps": self.flow_rate_lps,
            "design_head_m": self.design_head_m,
            "pressure_vessel_litres": self.pressure_vessel_litres,
            "has_vfd_control": self.has_vfd_control,
            "manifold_material": self.manifold_material,
            "has_anti_vibration_mounts": self.has_anti_vibration_mounts,
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


def extract_potable_water_booster_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PotableWaterBoosterCandidate]:
    """Extract potable water booster candidates deterministically."""
    results: List[PotableWaterBoosterCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:CWP|BPS|DWP|BOOST|PUMP|SKID)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    flow_pattern = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L/SEC)\b", re.IGNORECASE)
    head_pattern = re.compile(r"\b(\d{1,3}(?:\.\d+)?)\s*(?:M|METERS?)\s*(?:HEAD)?\b", re.IGNORECASE)
    vessel_pattern = re.compile(r"\b(\d{2,4})\s*(?:L|LITRE|LITRES|LITER|LITERS)\s*(?:PRESSURE\s*VESSEL|EXPANSION|DIAPHRAGM|TANK)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"cwp_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIRE SPRINKLER", "FIRE PUMP", "HYDRANT PUMP",
            "SEWAGE EJECTOR", "SEWER PUMP", "SUMP PUMP", "STORMWATER PUMP",
            "CHILLED WATER PUMP", "CHWP-", "HEATING WATER PUMP", "BORE PUMP"
        ]):
            continue

        is_booster = any(k in upper_text for k in [
            "BOOSTER PUMP", "WATER BOOSTER", "PRESSURE BOOSTER", "POTABLE WATER PUMP",
            "COLD WATER PUMP SKID", "BOOSTER SET", "HYDRO-PNEUMATIC"
        ]) or (tag_pattern.search(text) is not None and ("BOOSTER" in upper_text or "WATER" in upper_text or "PUMP" in upper_text))

        if not is_booster:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "CWP-SKID"

        # Skid configuration & pump count
        skid_configuration = "DUPLEX"
        pump_count = 2

        if "QUADRUPLEX" in upper_text or "4-PUMP" in upper_text or "4 PUMP" in upper_text or "FOUR PUMP" in upper_text:
            skid_configuration = "QUADRUPLEX"
            pump_count = 4
        elif "TRIPLEX" in upper_text or "3-PUMP" in upper_text or "3 PUMP" in upper_text or "THREE PUMP" in upper_text:
            skid_configuration = "TRIPLEX"
            pump_count = 3
        elif "SIMPLEX" in upper_text or "1-PUMP" in upper_text or "1 PUMP" in upper_text or "SINGLE PUMP" in upper_text:
            skid_configuration = "SIMPLEX"
            pump_count = 1
        elif "DUPLEX" in upper_text or "2-PUMP" in upper_text or "2 PUMP" in upper_text or "DUTY/STANDBY" in upper_text:
            skid_configuration = "DUPLEX"
            pump_count = 2

        # Flow rate
        flow_rate_lps: Optional[float] = None
        fl_match = flow_pattern.search(text)
        if fl_match:
            flow_rate_lps = float(fl_match.group(1))

        # Design head
        design_head_m: Optional[float] = None
        hd_match = head_pattern.search(text)
        if hd_match:
            val = float(hd_match.group(1))
            if 5.0 <= val <= 250.0:
                design_head_m = val

        # Pressure vessel
        pressure_vessel_litres: Optional[int] = None
        pv_match = vessel_pattern.search(text)
        if pv_match:
            val = int(pv_match.group(1))
            if val in [18, 24, 50, 60, 80, 100, 150, 200, 300, 500, 750, 1000]:
                pressure_vessel_litres = val

        # VFD control
        has_vfd_control = any(v in upper_text for v in [
            "VFD", "VARIABLE SPEED", "VARIABLE FREQUENCY", "INVERTER", "VSD"
        ])

        # Manifold material
        manifold_material = "STAINLESS_304"
        if "316" in upper_text or "SS316" in upper_text:
            manifold_material = "STAINLESS_316"
        elif "304" in upper_text or "SS304" in upper_text or "STAINLESS" in upper_text:
            manifold_material = "STAINLESS_304"
        elif "COPPER" in upper_text:
            manifold_material = "COPPER"

        # Anti-vibration mounts
        has_anti_vibration_mounts = any(av in upper_text for av in [
            "ANTI-VIBRATION", "VIBRATION ISOLATOR", "SPRING MOUNT", "INERTIA BASE", "RUBBER MOUNT"
        ])

        candidate = PotableWaterBoosterCandidate(
            item_id=item_id,
            skid_configuration=skid_configuration,
            tag=tag,
            pump_count=pump_count,
            flow_rate_lps=flow_rate_lps,
            design_head_m=design_head_m,
            pressure_vessel_litres=pressure_vessel_litres,
            has_vfd_control=has_vfd_control,
            manifold_material=manifold_material,
            has_anti_vibration_mounts=has_anti_vibration_mounts,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results