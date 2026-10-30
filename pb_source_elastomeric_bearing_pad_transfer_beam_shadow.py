"""Precast Concrete Bridge / Transfer Beam Neoprene Elastomeric Bearing Pad Shadow Authority.

Deterministic shadow extraction authority for steel-laminated elastomeric bearing pads,
neoprene strips, PTFE sliding bearings, pot bearings, and shear dowels under beams.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ElastomericBearingCandidate:
    """Extracted elastomeric bearing pad candidate."""
    item_id: str
    bearing_type: str  # "STEEL_LAMINATED_ELASTOMERIC", "PLAIN_ELASTOMERIC_STRIP", "PTFE_SLIDING_BEARING", "POT_BEARING", "SHEAR_DOWEL_PIN", "STANDARD"
    tag: str
    plan_dimensions_desc: Optional[str]  # e.g. "400x300mm"
    total_thickness_mm: Optional[int]
    durometer_hardness: str  # "SHORE_60A", "SHORE_50A", "SHORE_70A", "STANDARD"
    has_ptfe_sliding_layer: bool
    vertical_load_capacity_kn: Optional[int]
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "bearing_type": self.bearing_type,
            "tag": self.tag,
            "plan_dimensions_desc": self.plan_dimensions_desc,
            "total_thickness_mm": self.total_thickness_mm,
            "durometer_hardness": self.durometer_hardness,
            "has_ptfe_sliding_layer": self.has_ptfe_sliding_layer,
            "vertical_load_capacity_kn": self.vertical_load_capacity_kn,
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


def extract_elastomeric_bearing_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[ElastomericBearingCandidate]:
    """Extract elastomeric bearing pad candidates deterministically."""
    results: List[ElastomericBearingCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:EBP|BP|BRG|PAD|POT|BEAR)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    dim_3d_pattern = re.compile(r"\b(\d{2,4}\s*[xX]\s*\d{2,4}\s*[xX]\s*\d{2,3}(?:\s*MM)?)\b", re.IGNORECASE)
    dim_2d_pattern = re.compile(r"\b(\d{2,4}\s*[xX]\s*\d{2,4}(?:\s*MM)?)\b", re.IGNORECASE)
    thickness_pattern = re.compile(r"\b(?:THK|THICK|THICKNESS)?\s*(\d{2,3})\s*MM\s*(?:THK|THICK|THICKNESS)?\b", re.IGNORECASE)
    kn_pattern = re.compile(r"\b(\d{3,5})\s*KN\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"ebp_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "STEEL COLUMN BASEPLATE", "BASE PLATE 400X", "RESILIENT CHANNEL",
            "STUD WALL ACOUSTIC", "EQUIPMENT WAFFLE", "CHILLER ISOLATION PAD",
            "PAVER SUPPORT POD", "DECKING PEDESTAL"
        ]):
            continue

        is_bearing = any(k in upper_text for k in [
            "ELASTOMERIC BEARING", "BEARING PAD", "LAMINATED BEARING", "NEOPRENE BEARING",
            "POT BEARING", "PTFE SLIDING BEARING", "GIRDER BEARING", "TRANSFER BEAM BEARING"
        ]) or (tag_pattern.search(text) is not None and ("BEARING" in upper_text or "ELASTOMER" in upper_text or "PAD" in upper_text or "POT" in upper_text))

        if not is_bearing:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "EBP-ITEM"

        # PTFE sliding layer
        has_ptfe_sliding_layer = any(p in upper_text for p in [
            "PTFE", "TEFLON", "SLIDING LAYER", "STAINLESS SLIDING PLATE"
        ])

        # Bearing type
        bearing_type = "STEEL_LAMINATED_ELASTOMERIC"
        if "POT BEARING" in upper_text or "POT-" in tag:
            bearing_type = "POT_BEARING"
        elif has_ptfe_sliding_layer or "SLIDING BEARING" in upper_text:
            bearing_type = "PTFE_SLIDING_BEARING"
        elif "PLAIN" in upper_text or "STRIP" in upper_text or "UNREINFORCED" in upper_text:
            bearing_type = "PLAIN_ELASTOMERIC_STRIP"
        elif "DOWEL" in upper_text or "SHEAR KEY" in upper_text:
            bearing_type = "SHEAR_DOWEL_PIN"
        elif "LAMINATED" in upper_text or "STEEL REINFORCED" in upper_text or "BEARING PAD" in upper_text:
            bearing_type = "STEEL_LAMINATED_ELASTOMERIC"

        # Dimensions & thickness
        plan_dimensions_desc: Optional[str] = None
        total_thickness_mm: Optional[int] = None

        m3d = dim_3d_pattern.search(text)
        if m3d:
            raw_dims = m3d.group(1).lower().replace("mm", "").strip()
            parts = [p.strip() for p in raw_dims.split("x")]
            if len(parts) == 3:
                plan_dimensions_desc = f"{parts[0]}x{parts[1]}mm"
                total_thickness_mm = int(parts[2])
        else:
            m2d = dim_2d_pattern.search(text)
            if m2d:
                raw_dims = m2d.group(1).lower().replace("mm", "").strip()
                parts = [p.strip() for p in raw_dims.split("x")]
                if len(parts) == 2:
                    d1, d2 = int(parts[0]), int(parts[1])
                    if ("STRIP" in upper_text or d2 <= 30) and d2 < d1:
                        plan_dimensions_desc = f"{d1}mm"
                        total_thickness_mm = d2
                    else:
                        plan_dimensions_desc = f"{d1}x{d2}mm"

            if total_thickness_mm is None:
                th_match = thickness_pattern.search(text)
                if th_match:
                    val = int(th_match.group(1))
                    if 10 <= val <= 250:
                        total_thickness_mm = val

        # Durometer hardness
        durometer_hardness = "SHORE_60A"
        if "50A" in upper_text or "50 IRHD" in upper_text or "50 DUROMETER" in upper_text:
            durometer_hardness = "SHORE_50A"
        elif "70A" in upper_text or "70 IRHD" in upper_text or "70 DUROMETER" in upper_text:
            durometer_hardness = "SHORE_70A"
        elif "60A" in upper_text or "60 IRHD" in upper_text or "60 DUROMETER" in upper_text:
            durometer_hardness = "SHORE_60A"

        # Vertical load capacity
        vertical_load_capacity_kn: Optional[int] = None
        kn_match = kn_pattern.search(text)
        if kn_match:
            vertical_load_capacity_kn = int(kn_match.group(1))

        candidate = ElastomericBearingCandidate(
            item_id=item_id,
            bearing_type=bearing_type,
            tag=tag,
            plan_dimensions_desc=plan_dimensions_desc,
            total_thickness_mm=total_thickness_mm,
            durometer_hardness=durometer_hardness,
            has_ptfe_sliding_layer=has_ptfe_sliding_layer,
            vertical_load_capacity_kn=vertical_load_capacity_kn,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results