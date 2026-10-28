"""Architectural Metal Composite Material (MCM) / ACM Rainscreen Cladding Shadow Authority.

Deterministic shadow extraction authority for architectural ACM/MCM cladding,
cassette trays, mineral fire-rated cores, ventilated rainscreens, and top-hat subframing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ACMRainscreenCandidate:
    """Extracted ACM / MCM rainscreen cladding candidate."""
    item_id: str
    element_type: str  # "CASSETTE_TRAY", "FLAT_SHEET", "SUBFRAME_TOP_HAT", "HELPING_HAND_BRACKET", "FLASHING", "STANDARD"
    tag: str
    panel_thickness_mm: Optional[int]
    core_material_type: str  # "NON_COMBUSTIBLE_MINERAL", "SOLID_ALUMINIUM", "ALUMINIUM_HONEYCOMB", "STANDARD"
    mounting_system: str  # "CASSETTE_TRAY", "FACE_FIXED", "TONGUE_AND_GROOVE", "STANDARD"
    rainscreen_joint_type: str  # "OPEN_JOINT_VENTILATED", "SEALED_JOINT", "STANDARD"
    cavity_depth_mm: Optional[int]
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
            "panel_thickness_mm": self.panel_thickness_mm,
            "core_material_type": self.core_material_type,
            "mounting_system": self.mounting_system,
            "rainscreen_joint_type": self.rainscreen_joint_type,
            "cavity_depth_mm": self.cavity_depth_mm,
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


def extract_acm_rainscreen_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[ACMRainscreenCandidate]:
    """Extract ACM rainscreen cladding candidates deterministically."""
    results: List[ACMRainscreenCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:ACM|MCM|CLAD|PNL|TH|HHB)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    thickness_pattern = re.compile(r"\b([3456])\s*MM\s*(?:PANEL|ACM|MCM|THICK|THK)?\b", re.IGNORECASE)
    cavity_pattern = re.compile(r"\b(\d{2,3})\s*MM\s*(?:CAVITY|AIR\s*GAP|VOID|SUBFRAME)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"acm_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIBRE CEMENT", "CFC-", "COMPRESSED FIBRE",
            "TIMBER SHIPLAP", "CEDAR CLADDING", "TERRACOTTA RAINSCREEN",
            "SPANDREL GLASS", "VISION GLAZING", "CERAMIC FACADE"
        ]):
            continue

        is_acm = any(k in upper_text for k in [
            "ALUMINIUM COMPOSITE", "ALUMINUM COMPOSITE", "ACM CLADDING", "MCM CLADDING",
            "CASSETTE TRAY", "ALPOLIC", "ALUCOBOND", "METAL COMPOSITE", "RAINSCREEN CLADDING"
        ]) or (tag_pattern.search(text) is not None and ("ACM" in upper_text or "MCM" in upper_text or "CLADDING" in upper_text or "CASSETTE" in upper_text))

        if not is_acm:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "ACM-ITEM"

        # Core material type
        core_material_type = "NON_COMBUSTIBLE_MINERAL"
        if "SOLID" in upper_text or "PLATE" in upper_text:
            core_material_type = "SOLID_ALUMINIUM"
        elif "HONEYCOMB" in upper_text:
            core_material_type = "ALUMINIUM_HONEYCOMB"
        elif "MINERAL" in upper_text or "A2" in upper_text or "FR" in upper_text or "NON-COMBUSTIBLE" in upper_text:
            core_material_type = "NON_COMBUSTIBLE_MINERAL"

        # Mounting system
        mounting_system = "CASSETTE_TRAY"
        if "FACE FIXED" in upper_text or "RIVET" in upper_text or "SCREW FIXED" in upper_text:
            mounting_system = "FACE_FIXED"
        elif "TONGUE & GROOVE" in upper_text or "TONGUE AND GROOVE" in upper_text or "INTERLOCKING" in upper_text:
            mounting_system = "TONGUE_AND_GROOVE"
        elif "CASSETTE" in upper_text or "TRAY" in upper_text or "FOLDED" in upper_text:
            mounting_system = "CASSETTE_TRAY"

        # Element type
        element_type = "CASSETTE_TRAY"
        if "HELPING HAND" in upper_text or "WALL BRACKET" in upper_text or "HHB-" in tag:
            element_type = "HELPING_HAND_BRACKET"
        elif "TOP HAT" in upper_text or "TOP-HAT" in upper_text or "SUBFRAME" in upper_text or "Z-GIRT" in upper_text:
            element_type = "SUBFRAME_TOP_HAT"
        elif "FLASHING" in upper_text or "PARAPET CAP" in upper_text:
            element_type = "FLASHING"
        elif mounting_system == "FACE_FIXED":
            element_type = "FLAT_SHEET"
        elif mounting_system == "CASSETTE_TRAY":
            element_type = "CASSETTE_TRAY"

        # Panel thickness
        panel_thickness_mm: Optional[int] = None
        th_match = thickness_pattern.search(text)
        if th_match:
            panel_thickness_mm = int(th_match.group(1))

        # Rainscreen joint type
        rainscreen_joint_type = "OPEN_JOINT_VENTILATED"
        if "SEALED" in upper_text or "SILICONE" in upper_text or "MASTIC" in upper_text:
            rainscreen_joint_type = "SEALED_JOINT"
        elif "OPEN JOINT" in upper_text or "VENTILATED" in upper_text or "RAINSCREEN" in upper_text:
            rainscreen_joint_type = "OPEN_JOINT_VENTILATED"

        # Cavity depth
        cavity_depth_mm: Optional[int] = None
        cav_match = cavity_pattern.search(text)
        if cav_match:
            cavity_depth_mm = int(cav_match.group(1))

        candidate = ACMRainscreenCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            panel_thickness_mm=panel_thickness_mm,
            core_material_type=core_material_type,
            mounting_system=mounting_system,
            rainscreen_joint_type=rainscreen_joint_type,
            cavity_depth_mm=cavity_depth_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results