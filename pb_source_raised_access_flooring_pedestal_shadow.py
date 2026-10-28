"""Raised Access Computer Flooring Pedestal & Stringer Shadow Authority.

Deterministic shadow extraction authority for raised access flooring (RAF),
adjustable pedestals, grid stringers, perforated tiles, and cable grommets.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class RaisedAccessFlooringCandidate:
    """Extracted raised access flooring candidate."""
    item_id: str
    element_type: str  # "PANEL", "PEDESTAL", "STRINGER", "RAMP_STEP", "CABLE_GROMMET", "AIR_GRILLE", "STANDARD"
    tag: str
    finished_floor_height_mm: Optional[int]
    panel_size_desc: Optional[str]  # e.g. "600x600mm"
    panel_core_type: str  # "STEEL_CEMENTITIOUS", "WOODCORE", "CALCIUM_SULPHATE", "PERFORATED_AIRFLOW", "STANDARD"
    stringer_type: str  # "BOLTED", "SNAP_ON", "NONE", "STANDARD"
    load_rating_class: str  # "LIGHT", "MEDIUM", "HEAVY", "EXTRA_HEAVY", "STANDARD"
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
            "finished_floor_height_mm": self.finished_floor_height_mm,
            "panel_size_desc": self.panel_size_desc,
            "panel_core_type": self.panel_core_type,
            "stringer_type": self.stringer_type,
            "load_rating_class": self.load_rating_class,
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


def extract_raised_access_flooring_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[RaisedAccessFlooringCandidate]:
    """Extract raised access flooring candidates deterministically."""
    results: List[RaisedAccessFlooringCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:RAF|AF|PED|STR|GRM)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)
    ffh_pattern = re.compile(r"\b(?:FFH|HEIGHT|HT|VOID)?\s*(\d{2,4})\s*MM\s*(?:FFH|FINISHED FLOOR HEIGHT|VOID)?\b", re.IGNORECASE)
    size_pattern = re.compile(r"\b(600\s*[xX]\s*600(?:\s*MM)?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"raf_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "CERAMIC FLOOR TILE", "PORCELAIN TILE", "TILED FLOOR",
            "DIRECT STICK CARPET", "BROADLOOM CARPET", "PAVER PEDESTAL",
            "DECKING PEDESTAL", "BALCONY POD", "EXPOSED CEILING GRID"
        ]):
            continue

        is_raf = any(k in upper_text for k in [
            "RAISED ACCESS FLOOR", "ACCESS FLOOR", "RAF", "COMPUTER FLOOR",
            "ACCESS FLOORING", "FLOOR PEDESTAL", "FLOOR STRINGER", "CABLE GROMMET",
            "AIRFLOW PANEL", "PERFORATED TILE"
        ]) or (tag_pattern.search(text) is not None and ("FLOOR" in upper_text or "PEDESTAL" in upper_text or "STRINGER" in upper_text or "GROMMET" in upper_text))

        if not is_raf:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "RAF-ITEM"

        # Element type
        element_type = "PANEL"
        if "PEDESTAL" in upper_text:
            element_type = "PEDESTAL"
        elif "STRINGER" in upper_text:
            element_type = "STRINGER"
        elif "RAMP" in upper_text or "STEP" in upper_text or "FASCIA" in upper_text:
            element_type = "RAMP_STEP"
        elif "GROMMET" in upper_text or "BRUSH SEAL" in upper_text:
            element_type = "CABLE_GROMMET"
        elif "AIRFLOW" in upper_text or "PERFORATED" in upper_text or "GRILLE" in upper_text:
            element_type = "AIR_GRILLE"
        elif "PANEL" in upper_text or "TILE" in upper_text or "ACCESS FLOOR" in upper_text:
            element_type = "PANEL"

        # FFH
        finished_floor_height_mm: Optional[int] = None
        ffh_match = ffh_pattern.search(text)
        if ffh_match:
            val = int(ffh_match.group(1))
            if 50 <= val <= 1500:
                finished_floor_height_mm = val

        # Panel size
        panel_size_desc: Optional[str] = None
        size_match = size_pattern.search(text)
        if size_match:
            panel_size_desc = "600x600mm"

        # Core type
        panel_core_type = "STEEL_CEMENTITIOUS"
        if "CEMENTITIOUS" in upper_text or "CEMENT" in upper_text:
            panel_core_type = "STEEL_CEMENTITIOUS"
        elif "WOODCORE" in upper_text or "PARTICLEBOARD" in upper_text or "TIMBER CORE" in upper_text:
            panel_core_type = "WOODCORE"
        elif "CALCIUM SULPHATE" in upper_text or "GYPSUM" in upper_text:
            panel_core_type = "CALCIUM_SULPHATE"
        elif "PERFORATED" in upper_text or "AIRFLOW" in upper_text or "GRATE" in upper_text:
            panel_core_type = "PERFORATED_AIRFLOW"

        # Stringer type
        stringer_type = "STANDARD"
        if "BOLTED" in upper_text:
            stringer_type = "BOLTED"
        elif "SNAP ON" in upper_text or "SNAP-ON" in upper_text:
            stringer_type = "SNAP_ON"
        elif "STRINGERLESS" in upper_text or "NO STRINGER" in upper_text:
            stringer_type = "NONE"

        # Load rating
        load_rating_class = "MEDIUM"
        if "EXTRA HEAVY" in upper_text or "EXTRA-HEAVY" in upper_text or "9.0 KN" in upper_text or "9KN" in upper_text:
            load_rating_class = "EXTRA_HEAVY"
        elif "HEAVY" in upper_text or "6.7 KN" in upper_text or "6.7KN" in upper_text:
            load_rating_class = "HEAVY"
        elif "LIGHT" in upper_text or "3.0 KN" in upper_text or "3KN" in upper_text:
            load_rating_class = "LIGHT"
        elif "MEDIUM" in upper_text or "4.5 KN" in upper_text or "4.5KN" in upper_text:
            load_rating_class = "MEDIUM"

        candidate = RaisedAccessFlooringCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            finished_floor_height_mm=finished_floor_height_mm,
            panel_size_desc=panel_size_desc,
            panel_core_type=panel_core_type,
            stringer_type=stringer_type,
            load_rating_class=load_rating_class,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results