"""Stormwater Permeable Pavement & Geocellular Crate Shadow Authority.

Deterministic shadow extraction authority for permeable interlocking concrete pavements,
pervious concrete, and subsurface geocellular attenuation/infiltration crates.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PermeableStormwaterCandidate:
    """Extracted permeable pavement or geocellular crate candidate."""
    item_id: str
    system_type: str  # "PERMEABLE_PAVERS", "GEOCELLULAR_CRATES", "PERVIOUS_CONCRETE", "POROUS_ASPHALT", "STANDARD"
    tag: str
    subbase_depth_mm: Optional[int]
    storage_volume_m3: Optional[float]
    void_ratio_percent: Optional[float]
    liner_type: str  # "NON_WOVEN_GEOTEXTILE", "IMPERMEABLE_GEOMEMBRANE", "STANDARD"
    traffic_loading: str  # "HEAVY_VEHICLE", "MEDIUM_CAR_PARK", "LIGHT_PEDESTRIAN", "STANDARD"
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
            "subbase_depth_mm": self.subbase_depth_mm,
            "storage_volume_m3": self.storage_volume_m3,
            "void_ratio_percent": self.void_ratio_percent,
            "liner_type": self.liner_type,
            "traffic_loading": self.traffic_loading,
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


def extract_permeable_stormwater_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PermeableStormwaterCandidate]:
    """Extract permeable pavement and geocellular crate items deterministically."""
    results: List[PermeableStormwaterCandidate] = []
    processed_count = 0

    depth_pattern = re.compile(r"(\d{2,3})\s*MM\s*(?:SUBBASE|OPEN[-\s]GRADED|BASE\s*COURSE|CRUSHED\s*ROCK|BEDDING)?\b", re.IGNORECASE)
    vol_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:M3|CUBIC\s*M(?:ETERS?|ETRES?))\b", re.IGNORECASE)
    void_pattern = re.compile(r"(\d{2}(?:\.\d+)?)\s*%\s*(?:VOID|POROSITY)\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:PP|PICP|OSTA|GEO|ATN|ATT)[-_]?\d{1,2}[A-Z]?)\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"perm_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "STANDARD ASPHALT", "IMPERMEABLE CONCRETE SLAB", "ROOF MEMBRANE",
            "RETAINING WALL", "KERB ONLY", "FOUL SEWER"
        ]):
            continue

        is_permeable = any(k in upper_text for k in [
            "PERMEABLE PAV", "POROUS ASPHALT", "PERVIOUS CONCRETE", "PICP",
            "GEOCELLULAR", "ATTENUATION CRATE", "INFILTRATION CRATE", "MODULAR CRATE TANK",
            "OPEN GRADED CRUSHED ROCK SUBBASE"
        ]) or (tag_pattern.search(text) is not None and ("PAVE" in upper_text or "CRATE" in upper_text or "ATTENUATION" in upper_text))

        if not is_permeable:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "PERM-STORM"

        # System type
        system_type = "PERMEABLE_PAVERS"
        if "GEOCELLULAR" in upper_text or "CRATE" in upper_text:
            system_type = "GEOCELLULAR_CRATES"
        elif "POROUS ASPHALT" in upper_text:
            system_type = "POROUS_ASPHALT"
        elif "PERVIOUS CONCRETE" in upper_text:
            system_type = "PERVIOUS_CONCRETE"

        # Subbase depth
        subbase_depth_mm: Optional[int] = None
        d_match = depth_pattern.search(text)
        if d_match:
            subbase_depth_mm = int(d_match.group(1))

        # Storage volume
        storage_volume_m3: Optional[float] = None
        v_match = vol_pattern.search(text)
        if v_match:
            storage_volume_m3 = float(v_match.group(1))

        # Void ratio
        void_ratio_percent: Optional[float] = None
        vd_match = void_pattern.search(text)
        if vd_match:
            void_ratio_percent = float(vd_match.group(1))
        elif system_type == "GEOCELLULAR_CRATES":
            void_ratio_percent = 95.0  # standard engineering default for modular geocellular crates

        # Liner type
        liner_type = "STANDARD"
        if "HDPE" in upper_text or "IMPERMEABLE" in upper_text or "GEOMEMBRANE" in upper_text:
            liner_type = "IMPERMEABLE_GEOMEMBRANE"
        elif "GEOTEXTILE" in upper_text or "NON-WOVEN" in upper_text or "FILTER SOCK" in upper_text:
            liner_type = "NON_WOVEN_GEOTEXTILE"

        # Traffic loading
        traffic_loading = "STANDARD"
        if any(h in upper_text for h in ["HEAVY VEHICLE", "CLASS D", "40 TONNE", "FIRE APPLIANCE"]):
            traffic_loading = "HEAVY_VEHICLE"
        elif any(m in upper_text for m in ["CAR PARK", "CARPARK", "CLASS B", "TRAFFIC RATED"]):
            traffic_loading = "MEDIUM_CAR_PARK"
        elif any(p in upper_text for p in ["PEDESTRIAN", "FOOTPATH", "CLASS A"]):
            traffic_loading = "LIGHT_PEDESTRIAN"

        candidate = PermeableStormwaterCandidate(
            item_id=item_id,
            system_type=system_type,
            tag=tag,
            subbase_depth_mm=subbase_depth_mm,
            storage_volume_m3=storage_volume_m3,
            void_ratio_percent=void_ratio_percent,
            liner_type=liner_type,
            traffic_loading=traffic_loading,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
