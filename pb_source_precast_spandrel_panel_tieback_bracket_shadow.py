"""Precast Concrete Spandrel Panel Tieback & Gravity Bracket Connection Shadow Authority.

Deterministic shadow extraction authority for architectural precast spandrel panels,
dead-load gravity brackets, wind tieback brackets, cast-in channels, and anchor bolts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PrecastSpandrelBracketCandidate:
    """Extracted precast spandrel bracket connection candidate."""
    item_id: str
    element_type: str  # "GRAVITY_BRACKET", "TIEBACK_BRACKET", "SPANDREL_PANEL", "ALIGNMENT_DOWEL", "SHIM_PACK", "STANDARD"
    tag: str
    bracket_material: str  # "HOT_DIP_GALVANIZED", "STAINLESS_STEEL", "MILD_STEEL", "STANDARD"
    fixing_method: str  # "CAST_IN_CHANNEL", "CAST_IN_PLATE", "CHEMICAL_ANCHOR", "THROUGH_BOLT", "STANDARD"
    anchor_bolt_size: Optional[str]  # e.g. "M16", "M20", "M24", "M30"
    panel_thickness_mm: Optional[int]
    has_slotted_hole_deflection: bool
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
            "bracket_material": self.bracket_material,
            "fixing_method": self.fixing_method,
            "anchor_bolt_size": self.anchor_bolt_size,
            "panel_thickness_mm": self.panel_thickness_mm,
            "has_slotted_hole_deflection": self.has_slotted_hole_deflection,
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


def extract_precast_spandrel_bracket_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PrecastSpandrelBracketCandidate]:
    """Extract precast spandrel panel bracket candidates deterministically."""
    results: List[PrecastSpandrelBracketCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:SP|PSB|GB|TB|PC|BRK)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)
    bolt_pattern = re.compile(r"\b(M16|M20|M24|M30|M12|M36)\b", re.IGNORECASE)
    thickness_pattern = re.compile(r"\b(100|120|125|150|175|200|225|250|300)\s*MM\s*(?:THK|THICK|PANEL)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"spb_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "STEEL STUD DEFLECTION", "SLOTTED DEFLECTION TRACK",
            "TRUSS TIE-DOWN", "HURRICANE CLIP",
            "MULLION BRACKET", "CURTAIN WALL TRANSOM",
            "CABLE TRAY BRACKET", "UNISTRUT TRAPEZE"
        ]):
            continue

        is_spandrel = any(k in upper_text for k in [
            "SPANDREL", "PRECAST SPANDREL", "GRAVITY BRACKET", "TIEBACK BRACKET",
            "BEARING BRACKET", "WIND TIEBACK", "PRECAST BRACKET", "PRECAST PANEL CONNECTION"
        ]) or (tag_pattern.search(text) is not None and ("PRECAST" in upper_text or "BRACKET" in upper_text or "SPANDREL" in upper_text or "TIEBACK" in upper_text))

        if not is_spandrel:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "SPB-ITEM"

        # Slotted hole deflection
        has_slotted_hole_deflection = any(s in upper_text for s in [
            "SLOTTED HOLE", "VERTICALLY SLOTTED", "DEFLECTION SLOT", "SLOT FOR MOVEMENT"
        ])

        # Element type
        element_type = "GRAVITY_BRACKET"
        if "SHIM" in upper_text:
            element_type = "SHIM_PACK"
        elif "DOWEL" in upper_text or "ALIGNMENT PIN" in upper_text:
            element_type = "ALIGNMENT_DOWEL"
        elif "TIEBACK" in upper_text or "WIND BRACKET" in upper_text or "LATERAL RESTRAINT" in upper_text or "TB-" in tag or has_slotted_hole_deflection:
            element_type = "TIEBACK_BRACKET"
        elif "GRAVITY BRACKET" in upper_text or "BEARING BRACKET" in upper_text or "DEAD LOAD" in upper_text or "SHELF ANGLE" in upper_text or "GB-" in tag:
            element_type = "GRAVITY_BRACKET"
        elif "SPANDREL" in upper_text and ("PANEL" in upper_text or "BEAM" in upper_text or "PRECAST" in upper_text):
            element_type = "SPANDREL_PANEL"

        # Material
        bracket_material = "HOT_DIP_GALVANIZED"
        if "STAINLESS" in upper_text or "SS316" in upper_text or "316" in upper_text:
            bracket_material = "STAINLESS_STEEL"
        elif "HOT DIP" in upper_text or "HDG" in upper_text or "GALV" in upper_text:
            bracket_material = "HOT_DIP_GALVANIZED"
        elif "MILD STEEL" in upper_text or "PAINTED" in upper_text:
            bracket_material = "MILD_STEEL"

        # Fixing method
        fixing_method = "CAST_IN_CHANNEL"
        if "HALFEN" in upper_text or "CAST-IN CHANNEL" in upper_text or "CAST IN CHANNEL" in upper_text:
            fixing_method = "CAST_IN_CHANNEL"
        elif "WELD PLATE" in upper_text or "EMBED PLATE" in upper_text or "CAST-IN PLATE" in upper_text:
            fixing_method = "CAST_IN_PLATE"
        elif "CHEMICAL" in upper_text or "EPOXY" in upper_text or "POST-INSTALLED" in upper_text:
            fixing_method = "CHEMICAL_ANCHOR"
        elif "THROUGH BOLT" in upper_text or "THRU-BOLT" in upper_text:
            fixing_method = "THROUGH_BOLT"

        # Bolt size
        anchor_bolt_size: Optional[str] = None
        b_match = bolt_pattern.search(text)
        if b_match:
            anchor_bolt_size = b_match.group(1).upper()

        # Panel thickness
        panel_thickness_mm: Optional[int] = None
        th_match = thickness_pattern.search(text)
        if th_match:
            panel_thickness_mm = int(th_match.group(1))

        candidate = PrecastSpandrelBracketCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            bracket_material=bracket_material,
            fixing_method=fixing_method,
            anchor_bolt_size=anchor_bolt_size,
            panel_thickness_mm=panel_thickness_mm,
            has_slotted_hole_deflection=has_slotted_hole_deflection,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results