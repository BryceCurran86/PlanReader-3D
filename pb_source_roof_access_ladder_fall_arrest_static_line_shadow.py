"""Roof Access Ladder with Safety Cage & Fall-Arrest Static Line Shadow Authority.

Deterministic shadow extraction authority for fixed roof access ladders, safety cages,
horizontal static lifelines, rest platforms, access hatches, and lockable security gates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class RoofAccessLadderCandidate:
    """Extracted roof access ladder / height safety candidate."""
    item_id: str
    element_type: str  # "CAGED_ACCESS_LADDER", "UNCAGED_LADDER", "STATIC_LINE_SYSTEM", "ACCESS_HATCH", "STEP_OVER_PLATFORM", "STANDARD"
    tag: str
    ladder_height_mm: Optional[int]
    material: str  # "STRUCTURAL_ALUMINIUM", "HOT_DIP_GALVANIZED", "STAINLESS_STEEL_316", "STANDARD"
    has_safety_cage: bool
    has_rest_platform: bool
    has_lockable_security_gate: bool
    static_line_length_m: Optional[float]
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
            "ladder_height_mm": self.ladder_height_mm,
            "material": self.material,
            "has_safety_cage": self.has_safety_cage,
            "has_rest_platform": self.has_rest_platform,
            "has_lockable_security_gate": self.has_lockable_security_gate,
            "static_line_length_m": self.static_line_length_m,
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


def extract_roof_access_ladder_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[RoofAccessLadderCandidate]:
    """Extract roof access ladder candidates deterministically."""
    results: List[RoofAccessLadderCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:LAD|RAL|SL|RAH|SOP|LADDER)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    height_pattern = re.compile(r"\b(?:HEIGHT|HT|CLIMB)?\s*[:=]?\s*(\d{4})\s*MM\s*(?:HIGH|HT|HEIGHT|CLIMB)?\b", re.IGNORECASE)
    line_len_pattern = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:M|METERS?)\s*(?:STATIC\s*LINE|LIFELINE|RUN|LENGTH)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"lad_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "PORTABLE LADDER", "A-FRAME LADDER", "TIMBER STAIR",
            "CABLE LADDER", "ELECTRICAL CABLE TRAY", "PRECAST STAIR"
        ]):
            continue

        is_safety = any(k in upper_text for k in [
            "ROOF ACCESS LADDER", "CAGED LADDER", "SAFETY CAGE", "CAT LADDER",
            "STATIC LINE", "HORIZONTAL LIFELINE", "ROOF ACCESS HATCH", "STEP-OVER PLATFORM",
            "FALL ARREST"
        ]) or (tag_pattern.search(text) is not None and ("LADDER" in upper_text or "ROOF" in upper_text or "SAFETY" in upper_text or "HATCH" in upper_text))

        if not is_safety:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "LAD-ITEM"

        # Safety Cage
        has_safety_cage = any(sc in upper_text for sc in [
            "SAFETY CAGE", "CAGED", "HOOP CAGE", "CAGE HOOPS"
        ])

        # Rest Platform
        has_rest_platform = any(rp in upper_text for rp in [
            "REST PLATFORM", "REST LANDING", "INTERMEDIATE PLATFORM", "LANDING PLATFORM"
        ])

        # Lockable Security Gate
        has_lockable_security_gate = any(sg in upper_text for sg in [
            "LOCKABLE GATE", "SECURITY GATE", "LOCKABLE COVER", "SECURITY DOOR", "LOCKABLE CAGE DOOR"
        ])

        # Material
        material = "STRUCTURAL_ALUMINIUM"
        if "GALV" in upper_text or "HDG" in upper_text or "STEEL" in upper_text and "STAINLESS" not in upper_text:
            material = "HOT_DIP_GALVANIZED"
        elif "STAINLESS" in upper_text or "316" in upper_text or "SS316" in upper_text:
            material = "STAINLESS_STEEL_316"
        elif "ALUMINIUM" in upper_text or "ALUMINUM" in upper_text:
            material = "STRUCTURAL_ALUMINIUM"

        # Ladder height
        ladder_height_mm: Optional[int] = None
        h_match = height_pattern.search(text)
        if h_match:
            val = int(h_match.group(1))
            if 1000 <= val <= 15000:
                ladder_height_mm = val

        # Static line length
        static_line_length_m: Optional[float] = None
        if "STATIC LINE" in upper_text or "LIFELINE" in upper_text or "SL-" in tag:
            ln_match = line_len_pattern.search(text)
            if ln_match:
                static_line_length_m = float(ln_match.group(1))

        # Element type
        element_type = "CAGED_ACCESS_LADDER" if has_safety_cage or (ladder_height_mm and ladder_height_mm >= 3000) else "UNCAGED_LADDER"
        if "STATIC LINE" in upper_text or "LIFELINE" in upper_text or "SL-" in tag:
            element_type = "STATIC_LINE_SYSTEM"
        elif "HATCH" in upper_text or "RAH-" in tag:
            element_type = "ACCESS_HATCH"
        elif "STEP-OVER" in upper_text or "STEP OVER" in upper_text or "CROSSOVER" in upper_text or "SOP-" in tag:
            element_type = "STEP_OVER_PLATFORM"
        elif has_safety_cage or (ladder_height_mm and ladder_height_mm >= 3000):
            element_type = "CAGED_ACCESS_LADDER"
        elif "LADDER" in upper_text:
            element_type = "UNCAGED_LADDER"

        candidate = RoofAccessLadderCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            ladder_height_mm=ladder_height_mm,
            material=material,
            has_safety_cage=has_safety_cage,
            has_rest_platform=has_rest_platform,
            has_lockable_security_gate=has_lockable_security_gate,
            static_line_length_m=static_line_length_m,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results