"""Fire Sprinkler Floor Zone Control Valve & Waterflow Detector Switch Shadow Authority.

Deterministic shadow extraction authority for wet fire sprinkler zone control valves,
vane-type waterflow detector switches, tamper switches, and inspector test & drain valves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SprinklerZoneControlCandidate:
    """Extracted fire sprinkler zone control valve or flow switch candidate."""
    item_id: str
    element_type: str  # "ZONE_CONTROL_ASSEMBLY", "FLOW_SWITCH", "TEST_DRAIN_VALVE", "INSPECTOR_TEST"
    tag: str
    pipe_size_mm: int  # DN size (e.g. 50, 65, 80, 100, 150)
    valve_type: str  # "BUTTERFLY_MONITORED", "OS_AND_Y_GATE", "BALL_VALVE", "STANDARD"
    has_tamper_switch: bool
    has_flow_switch: bool
    has_test_and_drain: bool
    test_orifice_size_mm: Optional[float]
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
            "pipe_size_mm": self.pipe_size_mm,
            "valve_type": self.valve_type,
            "has_tamper_switch": self.has_tamper_switch,
            "has_flow_switch": self.has_flow_switch,
            "has_test_and_drain": self.has_test_and_drain,
            "test_orifice_size_mm": self.test_orifice_size_mm,
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


def extract_sprinkler_zone_controls(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SprinklerZoneControlCandidate]:
    """Extract sprinkler zone control valve and flow switch items deterministically."""
    results: List[SprinklerZoneControlCandidate] = []
    processed_count = 0

    size_pattern = re.compile(r"\b(?:DN\s*(\d{2,3})|(\d{2,3})\s*MM|(\d(?:\.5)?)\s*(?:INCH|\"))\b", re.IGNORECASE)
    orifice_pattern = re.compile(r"(?:ORIFICE\s*(?:SIZE\s*)?|K\s*=\s*|TEST\s*ORIFICE\s*)(\d+(?:\.\d+)?)(?:MM)?\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:ZCV|ZCA|FS|WFD|WFS|ITC|TDV)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"zcv_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "GAS VALVE", "CHW BALANCING", "DOMESTIC WATER",
            "DRAIN VALVE ONLY", "SEWAGE", "AIR SEPARATOR"
        ]):
            continue

        is_zcv_item = any(k in upper_text for k in [
            "ZONE CONTROL", "ZCV", "ZCA", "WATERFLOW DETECTOR", "FLOW SWITCH",
            "TEST AND DRAIN", "TEST & DRAIN", "INSPECTOR TEST", "SPRINKLER CONTROL VALVE",
            "FLOOR CONTROL VALVE"
        ]) or (tag_pattern.search(text) is not None and ("SPRINKLER" in upper_text or "FLOW" in upper_text or "ZONE" in upper_text or "RISER" in upper_text))

        if not is_zcv_item:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "ZCV-ITEM"

        # Element type
        element_type = "ZONE_CONTROL_ASSEMBLY"
        if "INSPECTOR TEST" in upper_text or re.search(r"\bITC\b", upper_text):
            element_type = "INSPECTOR_TEST"
        elif "TEST AND DRAIN" in upper_text or "TEST & DRAIN" in upper_text:
            element_type = "TEST_DRAIN_VALVE"
        elif "FLOW SWITCH" in upper_text or "WATERFLOW DETECTOR" in upper_text or re.search(r"\b(?:WFD|WFS)\b", upper_text):
            if "ZONE CONTROL" not in upper_text and "ZCV" not in upper_text and "ZCA" not in upper_text:
                element_type = "FLOW_SWITCH"

        # Pipe size
        pipe_size_mm = 100  # standard default for sprinkler zone risers
        s_match = size_pattern.search(text)
        if s_match:
            if s_match.group(1):
                pipe_size_mm = int(s_match.group(1))
            elif s_match.group(2):
                pipe_size_mm = int(s_match.group(2))
            elif s_match.group(3):
                inch = float(s_match.group(3))
                pipe_size_mm = int(round(inch * 25.4))

        # Valve type
        valve_type = "STANDARD"
        if "BALL VALVE" in upper_text or "BALL" in upper_text:
            valve_type = "BALL_VALVE"
        elif "OS&Y" in upper_text or "OS AND Y" in upper_text or "GATE VALVE" in upper_text:
            valve_type = "OS_AND_Y_GATE"
        elif "BUTTERFLY" in upper_text or "WAFER" in upper_text or "GEAR" in upper_text or "ZCV" in upper_text or "ZCA" in upper_text:
            valve_type = "BUTTERFLY_MONITORED"

        # Switches
        has_tamper_switch = any(t in upper_text for t in ["TAMPER", "MONITORED", "SUPERVISORY", "SUPERVISED"]) or element_type == "ZONE_CONTROL_ASSEMBLY"
        has_flow_switch = any(f in upper_text for f in ["FLOW SWITCH", "WATERFLOW", "WFD", "VANE"]) or element_type == "ZONE_CONTROL_ASSEMBLY"
        has_test_and_drain = any(td in upper_text for td in ["TEST AND DRAIN", "TEST & DRAIN", "TDV"]) or element_type == "ZONE_CONTROL_ASSEMBLY"

        # Orifice size
        test_orifice_size_mm: Optional[float] = None
        o_match = orifice_pattern.search(text)
        if o_match:
            test_orifice_size_mm = float(o_match.group(1))
        elif "1/2\"" in text or "1/2 INCH" in upper_text:
            test_orifice_size_mm = 12.7

        candidate = SprinklerZoneControlCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            pipe_size_mm=pipe_size_mm,
            valve_type=valve_type,
            has_tamper_switch=has_tamper_switch,
            has_flow_switch=has_flow_switch,
            has_test_and_drain=has_test_and_drain,
            test_orifice_size_mm=test_orifice_size_mm,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
