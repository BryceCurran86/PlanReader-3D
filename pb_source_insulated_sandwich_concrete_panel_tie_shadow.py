"""Precast Insulated Sandwich Concrete Panel & Composite Tie Shadow Authority.

Deterministic shadow extraction authority for precast insulated sandwich concrete wall
panels, rigid insulation cores (XPS/PIR/EPS), and non-conductive composite connector ties.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SandwichPanelCandidate:
    """Extracted precast insulated sandwich panel candidate."""
    item_id: str
    panel_tag: str
    outer_wythe_mm: Optional[int]
    insulation_core_mm: Optional[int]
    inner_wythe_mm: Optional[int]
    total_thickness_mm: Optional[int]
    insulation_type: str  # "XPS", "PIR", "EPS", "PHENOLIC", "STANDARD"
    connector_tie_type: str  # "FIBERGLASS_GFRP", "BASALT_BFRP", "CARBON_CFRP", "STAINLESS_STEEL", "STANDARD"
    is_non_conductive: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "panel_tag": self.panel_tag,
            "outer_wythe_mm": self.outer_wythe_mm,
            "insulation_core_mm": self.insulation_core_mm,
            "inner_wythe_mm": self.inner_wythe_mm,
            "total_thickness_mm": self.total_thickness_mm,
            "insulation_type": self.insulation_type,
            "connector_tie_type": self.connector_tie_type,
            "is_non_conductive": self.is_non_conductive,
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


def extract_sandwich_panels(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SandwichPanelCandidate]:
    """Extract precast insulated sandwich panels and composite ties deterministically."""
    results: List[SandwichPanelCandidate] = []
    processed_count = 0

    sandwich_triple_pattern = re.compile(r"(\d{2,3})\s*[-/]\s*(\d{2,3})\s*[-/]\s*(\d{2,3})(?:MM)?\b")
    total_thick_pattern = re.compile(r"(\d{3})\s*MM\s*(?:TOTAL|OVERALL)?\s*(?:PANEL|THICKNESS|SANDWICH)?\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:SWP|ISP|PCW|SP|PANEL)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"swp_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "DRYWALL PARTITION", "TIMBER STUD WALL", "CURTAIN WALL TRANSOM",
            "METAL CLADDING ONLY", "MASONRY CAVITY TIE ONLY"
        ]):
            continue

        is_sandwich = any(k in upper_text for k in [
            "SANDWICH PANEL", "INSULATED PRECAST", "THERMOMASS", "COMPOSITE TIE",
            "INSULATED WALL PANEL", "THREE-LAYER PANEL", "PRECAST SANDWICH"
        ]) or (sandwich_triple_pattern.search(text) is not None and ("PRECAST" in upper_text or "PANEL" in upper_text or "WYTHE" in upper_text))

        if not is_sandwich:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "SWP-PANEL"

        # Wythe thicknesses
        outer_wythe_mm: Optional[int] = None
        insulation_core_mm: Optional[int] = None
        inner_wythe_mm: Optional[int] = None
        total_thickness_mm: Optional[int] = None

        triple_match = sandwich_triple_pattern.search(text)
        if triple_match:
            outer_wythe_mm = int(triple_match.group(1))
            insulation_core_mm = int(triple_match.group(2))
            inner_wythe_mm = int(triple_match.group(3))
            total_thickness_mm = outer_wythe_mm + insulation_core_mm + inner_wythe_mm
        else:
            tot_match = total_thick_pattern.search(text)
            if tot_match:
                total_thickness_mm = int(tot_match.group(1))

        # Insulation material
        insulation_type = "STANDARD"
        if "XPS" in upper_text or "EXTRUDED POLYSTYRENE" in upper_text:
            insulation_type = "XPS"
        elif "PIR" in upper_text or "POLYISOCYANURATE" in upper_text:
            insulation_type = "PIR"
        elif "EPS" in upper_text or "EXPANDED POLYSTYRENE" in upper_text:
            insulation_type = "EPS"
        elif "PHENOLIC" in upper_text:
            insulation_type = "PHENOLIC"

        # Connector tie type
        connector_tie_type = "STANDARD"
        is_non_conductive = False
        if any(g in upper_text for g in ["GFRP", "FIBERGLASS", "GLASS FIBER", "FIBREGLASS"]):
            connector_tie_type = "FIBERGLASS_GFRP"
            is_non_conductive = True
        elif any(b in upper_text for b in ["BFRP", "BASALT"]):
            connector_tie_type = "BASALT_BFRP"
            is_non_conductive = True
        elif any(c in upper_text for c in ["CFRP", "CARBON FIBER", "CARBON GRID"]):
            connector_tie_type = "CARBON_CFRP"
            is_non_conductive = True
        elif "STAINLESS" in upper_text:
            connector_tie_type = "STAINLESS_STEEL"
            is_non_conductive = False
        elif "THERMOMASS" in upper_text or "NON-CONDUCTIVE" in upper_text or "COMPOSITE PIN" in upper_text:
            connector_tie_type = "FIBERGLASS_GFRP"
            is_non_conductive = True

        candidate = SandwichPanelCandidate(
            item_id=item_id,
            panel_tag=tag,
            outer_wythe_mm=outer_wythe_mm,
            insulation_core_mm=insulation_core_mm,
            inner_wythe_mm=inner_wythe_mm,
            total_thickness_mm=total_thickness_mm,
            insulation_type=insulation_type,
            connector_tie_type=connector_tie_type,
            is_non_conductive=is_non_conductive,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
