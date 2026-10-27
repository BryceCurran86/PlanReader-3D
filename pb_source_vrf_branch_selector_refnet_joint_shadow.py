"""HVAC VRF / VRV Branch Selector Box & Refnet Joint Shadow Authority.

Deterministic shadow extraction authority for variable refrigerant flow (VRF/VRV)
branch selector boxes, mode control units, Refnet Y-joints, and header manifolds.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class VRFComponentCandidate:
    """Extracted VRF branch selector box or Refnet joint candidate."""
    item_id: str
    element_type: str  # "BRANCH_SELECTOR_BOX", "REFNET_JOINT", "REFNET_HEADER", "STANDARD"
    tag: str
    port_count: Optional[int]
    system_architecture: str  # "HEAT_RECOVERY_3_PIPE", "HEAT_PUMP_2_PIPE", "WATER_COOLED", "STANDARD"
    has_condensate_drain: bool
    requires_power_supply: bool
    liquid_pipe_mm: Optional[float]
    gas_pipe_mm: Optional[float]
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
            "port_count": self.port_count,
            "system_architecture": self.system_architecture,
            "has_condensate_drain": self.has_condensate_drain,
            "requires_power_supply": self.requires_power_supply,
            "liquid_pipe_mm": self.liquid_pipe_mm,
            "gas_pipe_mm": self.gas_pipe_mm,
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


def extract_vrf_components(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[VRFComponentCandidate]:
    """Extract VRF branch selector boxes and Refnet joints deterministically."""
    results: List[VRFComponentCandidate] = []
    processed_count = 0

    port_pattern = re.compile(r"(\d{1,2})[-\s]*(?:PORT|BRANCH|WAY)S?\b", re.IGNORECASE)
    pipe_pattern = re.compile(r"(\d{1,2}(?:\.\d{1,2})?)\s*MM\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:BS|BSB|MCU|HRV|RJ|RH|REF)[-_]?\d{1,3}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"vrf_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "CHILLED WATER", "CONDENSER WATER", "AIR DIRT SEPARATOR",
            "FIRE DAMPER", "VAV BOX", "EXPANSION VESSEL"
        ]):
            continue

        is_vrf = any(k in upper_text for k in [
            "BRANCH SELECTOR", "BS BOX", "MODE CONTROL UNIT", "MCU",
            "REFNET", "REFNET JOINT", "REFNET HEADER", "HEAT RECOVERY BOX",
            "VRF BRANCH", "VRV BRANCH", "REFRIGERANT Y-JOINT"
        ]) or (tag_pattern.search(text) is not None and ("VRF" in upper_text or "VRV" in upper_text or "PORT" in upper_text))

        if not is_vrf:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "VRF-ITEM"

        # Element type
        element_type = "BRANCH_SELECTOR_BOX"
        if "REFNET HEADER" in upper_text or "REFNET MANIFOLD" in upper_text:
            element_type = "REFNET_HEADER"
        elif "REFNET" in upper_text or "Y-JOINT" in upper_text:
            element_type = "REFNET_JOINT"
        elif "BRANCH SELECTOR" in upper_text or "BS BOX" in upper_text or "MCU" in upper_text or "HRV" in upper_text:
            element_type = "BRANCH_SELECTOR_BOX"

        # Port count
        port_count: Optional[int] = None
        port_match = port_pattern.search(text)
        if port_match:
            port_count = int(port_match.group(1))
        elif element_type == "BRANCH_SELECTOR_BOX" and "SINGLE" in upper_text:
            port_count = 1
        elif element_type == "REFNET_JOINT":
            port_count = 2  # standard binary branch

        # System architecture
        system_architecture = "HEAT_RECOVERY_3_PIPE"
        if "2-PIPE" in upper_text or "HEAT PUMP" in upper_text:
            system_architecture = "HEAT_PUMP_2_PIPE"
        elif "WATER-COOLED" in upper_text or "WATER COOLED" in upper_text:
            system_architecture = "WATER_COOLED"
        elif "3-PIPE" in upper_text or "HEAT RECOVERY" in upper_text or element_type == "BRANCH_SELECTOR_BOX":
            system_architecture = "HEAT_RECOVERY_3_PIPE"

        # Condensate drain
        has_condensate_drain = any(d in upper_text for d in ["DRAIN", "CONDENSATE TRAY", "DRAIN CONNECTION"]) and "NO DRAIN" not in upper_text

        # Power supply
        requires_power_supply = False
        if element_type == "BRANCH_SELECTOR_BOX":
            if "NO POWER" in upper_text or "COMM POWERED" in upper_text or "BUS POWERED" in upper_text:
                requires_power_supply = False
            else:
                requires_power_supply = True

        # Pipe sizes
        liquid_pipe_mm: Optional[float] = None
        gas_pipe_mm: Optional[float] = None
        pipes = [float(p) for p in pipe_pattern.findall(text)]
        if len(pipes) >= 2:
            liquid_pipe_mm = min(pipes)
            gas_pipe_mm = max(pipes)
        elif len(pipes) == 1:
            gas_pipe_mm = pipes[0]

        candidate = VRFComponentCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            port_count=port_count,
            system_architecture=system_architecture,
            has_condensate_drain=has_condensate_drain,
            requires_power_supply=requires_power_supply,
            liquid_pipe_mm=liquid_pipe_mm,
            gas_pipe_mm=gas_pipe_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
