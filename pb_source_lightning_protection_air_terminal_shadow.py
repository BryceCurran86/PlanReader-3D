"""Commercial Building Lightning Protection Air Terminal & Down-Conductor Shadow Authority.

Deterministic shadow extraction authority for lightning protection air terminals,
ESE ionizing heads, roof mesh conductors, down-conductor tapes, and test wells.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class LightningProtectionCandidate:
    """Extracted lightning protection item candidate."""
    item_id: str
    element_type: str  # "AIR_TERMINAL", "ESE_TERMINAL", "DOWN_CONDUCTOR", "EARTH_PIT", "TEST_CLAMP", "STANDARD"
    tag: str
    terminal_height_mm: Optional[int]
    conductor_material: str  # "COPPER", "ALUMINIUM", "STAINLESS_STEEL", "STANDARD"
    conductor_size_desc: Optional[str]  # e.g. "25x3mm", "50mm2", "70mm2"
    protection_method: str  # "FARADAY_MESH", "EARLY_STREAMER", "FRANKLIN_ROD", "STANDARD"
    has_test_clamp: bool
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
            "terminal_height_mm": self.terminal_height_mm,
            "conductor_material": self.conductor_material,
            "conductor_size_desc": self.conductor_size_desc,
            "protection_method": self.protection_method,
            "has_test_clamp": self.has_test_clamp,
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


def extract_lightning_protection_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[LightningProtectionCandidate]:
    """Extract lightning protection system items deterministically."""
    results: List[LightningProtectionCandidate] = []
    processed_count = 0

    height_mm_pattern = re.compile(r"(\d{3,4})\s*MM\s*(?:AIR\s*)?(?:TERMINAL|ROD)?\b", re.IGNORECASE)
    height_m_pattern = re.compile(r"(\d(?:\.\d+)?)\s*M\s*(?:AIR\s*)?(?:TERMINAL|ROD|MAST)\b", re.IGNORECASE)
    size_tape_pattern = re.compile(r"\b(25\s*[xX]\s*3(?:\.0)?(?:MM)?)\b", re.IGNORECASE)
    size_cable_pattern = re.compile(r"\b(\d{2,3})\s*MM2\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:AT|ESE|LPS|LP|DC|EP|TC)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"lp_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "SOLAR PANEL", "PHOTOVOLTAIC", "TV ANTENNA", "CELLULAR ANTENNA",
            "MOTOR CONTROL", "DOMESTIC WATER"
        ]):
            continue

        is_lps = any(k in upper_text for k in [
            "LIGHTNING PROTECTION", "AIR TERMINAL", "DOWN CONDUCTOR", "DOWN-CONDUCTOR",
            "EARLY STREAMER", "ESE TERMINAL", "FRANKLIN ROD", "STRIKE TERMINATION",
            "EARTH PIT", "EARTH INSPECTION WELL", "DISCONNECT TEST CLAMP"
        ]) or (tag_pattern.search(text) is not None and ("LIGHTNING" in upper_text or "TERMINAL" in upper_text or "CONDUCTOR" in upper_text or "EARTH" in upper_text))

        if not is_lps:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "LPS-ITEM"

        # Protection method
        protection_method = "FARADAY_MESH"
        if "EARLY STREAMER" in upper_text or "ESE" in upper_text:
            protection_method = "EARLY_STREAMER"
        elif "FRANKLIN" in upper_text:
            protection_method = "FRANKLIN_ROD"
        elif "FARADAY" in upper_text or "MESH" in upper_text:
            protection_method = "FARADAY_MESH"

        # Element type
        element_type = "AIR_TERMINAL"
        if "EARTH PIT" in upper_text or "INSPECTION WELL" in upper_text or "EP-" in tag:
            element_type = "EARTH_PIT"
        elif "TEST CLAMP" in upper_text or "DISCONNECT CLAMP" in upper_text or "TC-" in tag:
            element_type = "TEST_CLAMP"
        elif "DOWN CONDUCTOR" in upper_text or "DOWN-CONDUCTOR" in upper_text or "DC-" in tag:
            element_type = "DOWN_CONDUCTOR"
        elif "EARLY STREAMER" in upper_text or "ESE" in upper_text:
            element_type = "ESE_TERMINAL"
        elif "AIR TERMINAL" in upper_text or "FRANKLIN ROD" in upper_text or "STRIKE TERMINATION" in upper_text or "AT-" in tag:
            element_type = "AIR_TERMINAL"

        # Terminal height
        terminal_height_mm: Optional[int] = None
        h_match = height_mm_pattern.search(text)
        if h_match:
            terminal_height_mm = int(h_match.group(1))
        else:
            hm_match = height_m_pattern.search(text)
            if hm_match:
                terminal_height_mm = int(round(float(hm_match.group(1)) * 1000))

        # Conductor material
        conductor_material = "COPPER"
        if "ALUMINIUM" in upper_text or "ALUMINUM" in upper_text:
            conductor_material = "ALUMINIUM"
        elif "STAINLESS" in upper_text:
            conductor_material = "STAINLESS_STEEL"
        elif "COPPER" in upper_text:
            conductor_material = "COPPER"

        # Conductor size description
        conductor_size_desc: Optional[str] = None
        tape_match = size_tape_pattern.search(text)
        if tape_match:
            conductor_size_desc = "25x3mm"
        else:
            cable_match = size_cable_pattern.search(text)
            if cable_match:
                conductor_size_desc = f"{cable_match.group(1)}mm2"

        # Test clamp
        has_test_clamp = any(tc in upper_text for tc in ["TEST CLAMP", "DISCONNECT", "TESTING POINT"]) or element_type == "TEST_CLAMP"

        candidate = LightningProtectionCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            terminal_height_mm=terminal_height_mm,
            conductor_material=conductor_material,
            conductor_size_desc=conductor_size_desc,
            protection_method=protection_method,
            has_test_clamp=has_test_clamp,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
