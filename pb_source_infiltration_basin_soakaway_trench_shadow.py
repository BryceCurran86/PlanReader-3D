"""Civil Subsurface Infiltration Basin & Trench Geocellular Drainage Shadow Authority.

Deterministic shadow extraction authority for subsurface stormwater infiltration basins,
soakaway trenches, geocellular crates, non-woven geotextile wraps, and inspection risers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class InfiltrationBasinCandidate:
    """Extracted infiltration basin / soakaway candidate."""
    item_id: str
    system_type: str  # "GEOCELLULAR_BASIN", "INFILTRATION_TRENCH", "SURFACE_BASIN", "INSPECTION_RISER", "SILT_TRAP", "STANDARD"
    tag: str
    storage_volume_m3: Optional[float]
    trench_depth_mm: Optional[int]
    geotextile_wrap: str  # "NON_WOVEN_GEOTEXTILE", "IMPERMEABLE_GEOMEMBRANE", "STANDARD"
    aggregate_grading_desc: Optional[str]  # e.g. "20-40mm", "40-70mm"
    has_inspection_riser: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "system_type": self.system_type,
            "tag": self.tag,
            "storage_volume_m3": self.storage_volume_m3,
            "trench_depth_mm": self.trench_depth_mm,
            "geotextile_wrap": self.geotextile_wrap,
            "aggregate_grading_desc": self.aggregate_grading_desc,
            "has_inspection_riser": self.has_inspection_riser,
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


def extract_infiltration_basin_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[InfiltrationBasinCandidate]:
    """Extract stormwater infiltration basin and soakaway candidates deterministically."""
    results: List[InfiltrationBasinCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:INF|IT|IB|SK|SOAK|ST|INSP)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)
    volume_pattern = re.compile(r"\b(\d+(?:\.\d+)?)\s*(?:M3|M\^3|CU\.M|CUBIC METERS?)\b", re.IGNORECASE)
    depth_pattern = re.compile(r"\b(?:DEPTH|DEEP|DP)?\s*(\d{3,4})\s*MM\s*(?:DEEP|DEPTH)?\b", re.IGNORECASE)
    aggregate_pattern = re.compile(r"\b((?:20[-/]40|40[-/]70|20[-/]50|10[-/]20)\s*MM)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"inf_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "IMPERMEABLE DETENTION TANK", "OSD TANK", "RAINWATER RETENTION",
            "SEPTIC ABSORPTION", "EFFLUENT DISPOSAL", "SEPTIC TANK",
            "AG DRAIN BEHIND", "AGRICULTURAL DRAIN BEHIND",
            "TRADE WASTE", "GREASE TRAP"
        ]):
            continue

        is_inf = any(k in upper_text for k in [
            "INFILTRATION BASIN", "INFILTRATION TRENCH", "SOAKAWAY TRENCH",
            "INFILTRATION CRATE", "GEOCELLULAR INFILTRATION", "SOAKAWAY CRATE",
            "MODULAR SOAKAWAY", "INFILTRATION SYSTEM"
        ]) or (tag_pattern.search(text) is not None and ("INFILTRATION" in upper_text or "SOAKAWAY" in upper_text or "TRENCH" in upper_text or "CRATE" in upper_text))

        if not is_inf:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "INF-ITEM"

        # Inspection riser
        has_inspection_riser = any(r in upper_text for r in [
            "INSPECTION RISER", "INSPECTION SHAFT", "INSPECTION PORT", "VENT RISER"
        ])

        # Element type
        element_type = "INFILTRATION_TRENCH"
        if "SILT TRAP" in upper_text or "SEDIMENT SUMP" in upper_text or "PRE-TREATMENT" in upper_text or "ST-" in tag:
            element_type = "SILT_TRAP"
        elif "CRATE" in upper_text or "GEOCELLULAR" in upper_text or "MODULAR" in upper_text:
            element_type = "GEOCELLULAR_BASIN"
        elif "INSP-" in tag or (("INSPECTION RISER" in upper_text or "INSPECTION SHAFT" in upper_text) and not any(k in upper_text for k in ["CRATE", "BASIN", "TRENCH", "SOAKAWAY"])):
            element_type = "INSPECTION_RISER"
        elif "SURFACE" in upper_text or "SWALE" in upper_text or "OPEN BASIN" in upper_text or ("BASIN" in upper_text and "TRENCH" not in upper_text):
            element_type = "SURFACE_BASIN"
        elif "TRENCH" in upper_text or "SOAKAWAY" in upper_text:
            element_type = "INFILTRATION_TRENCH"

        # Storage volume
        storage_volume_m3: Optional[float] = None
        v_match = volume_pattern.search(text)
        if v_match:
            storage_volume_m3 = float(v_match.group(1))

        # Trench depth
        trench_depth_mm: Optional[int] = None
        d_match = depth_pattern.search(text)
        if d_match:
            val = int(d_match.group(1))
            if 300 <= val <= 5000:
                trench_depth_mm = val

        # Geotextile wrap
        geotextile_wrap = "NON_WOVEN_GEOTEXTILE"
        if "GEOMEMBRANE" in upper_text or "IMPERMEABLE" in upper_text:
            geotextile_wrap = "IMPERMEABLE_GEOMEMBRANE"
        elif "GEOTEXTILE" in upper_text or "NON-WOVEN" in upper_text or "BIDIM" in upper_text:
            geotextile_wrap = "NON_WOVEN_GEOTEXTILE"

        # Aggregate grading
        aggregate_grading_desc: Optional[str] = None
        agg_match = aggregate_pattern.search(text)
        if agg_match:
            aggregate_grading_desc = agg_match.group(1).lower().replace(" ", "")
        elif "AGGREGATE" in upper_text or "BLUE METAL" in upper_text or "GRAVEL" in upper_text:
            aggregate_grading_desc = "20-40mm"

        candidate = InfiltrationBasinCandidate(
            item_id=item_id,
            system_type=element_type,
            tag=tag,
            storage_volume_m3=storage_volume_m3,
            trench_depth_mm=trench_depth_mm,
            geotextile_wrap=geotextile_wrap,
            aggregate_grading_desc=aggregate_grading_desc,
            has_inspection_riser=has_inspection_riser,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results