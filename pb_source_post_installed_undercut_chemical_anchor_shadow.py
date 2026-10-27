"""Post-Installed Mechanical Undercut & Chemical Epoxy Anchor Stud Shadow Authority.

Deterministic shadow extraction authority for post-installed concrete fasteners:
undercut anchors, chemical adhesive studs, screw anchors, embedment depths, and seismic ratings.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PostInstalledAnchorCandidate:
    """Extracted post-installed anchor candidate."""
    item_id: str
    anchor_type: str  # "CHEMICAL_EPOXY_STUD", "MECHANICAL_UNDERCUT", "CONCRETE_SCREW_BOLT", "EXPANSION_ANCHOR", "DROP_IN_ANCHOR", "STANDARD"
    tag: str
    thread_size: Optional[str]  # e.g. "M12", "M16", "M20", "M24", "M30"
    embedment_depth_mm: Optional[int]
    steel_material: str  # "GRADE_8_8_GALV", "STAINLESS_A4_316", "HCR_CORROSION", "CARBON_STEEL_ZINC", "STANDARD"
    seismic_category: Optional[str]  # "SEISMIC_C2", "SEISMIC_C1", "STATIC_ONLY"
    cracked_concrete_approved: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "anchor_type": self.anchor_type,
            "tag": self.tag,
            "thread_size": self.thread_size,
            "embedment_depth_mm": self.embedment_depth_mm,
            "steel_material": self.steel_material,
            "seismic_category": self.seismic_category,
            "cracked_concrete_approved": self.cracked_concrete_approved,
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


def extract_post_installed_anchor_items(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PostInstalledAnchorCandidate]:
    """Extract post-installed anchor candidates deterministically."""
    results: List[PostInstalledAnchorCandidate] = []
    processed_count = 0

    tag_pattern = re.compile(r"\b((?:ANC|FA|CA|UA|SA|HA|WA)(?:[-_][A-Z0-9]{1,4}|\d{1,4}))\b", re.IGNORECASE)
    thread_pattern = re.compile(r"\b(M8|M10|M12|M16|M20|M24|M30|M36)\b", re.IGNORECASE)
    hef_pattern = re.compile(r"\b(?:HEF|EMBEDMENT|DEPTH|EMBED)?\s*[:=]?\s*(\d{2,3})\s*MM\s*(?:HEF|EMBEDMENT|DEPTH)?\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"anc_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "STARTER BAR", "LAP LENGTH", "REINFORCING REBAR",
            "DRYWALL ANCHOR", "SPRING TOGGLE", "HOLLOW WALL PLUG",
            "TIMBER SCREW", "COACH SCREW", "CAVITY BRICK TIE", "VENEER TIE"
        ]):
            continue

        is_anchor = any(k in upper_text for k in [
            "UNDERCUT ANCHOR", "CHEMICAL ANCHOR", "EPOXY ANCHOR", "ADHESIVE ANCHOR",
            "CONCRETE SCREW", "SCREW ANCHOR", "WEDGE ANCHOR", "DROP-IN ANCHOR",
            "POST-INSTALLED ANCHOR", "HIT-RE", "TITEN HD", "HUS-4", "HST3"
        ]) or (tag_pattern.search(text) is not None and ("ANCHOR" in upper_text or "STUD" in upper_text or "BOLT" in upper_text))

        if not is_anchor:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "ANC-ITEM"

        # Thread size
        thread_size: Optional[str] = None
        th_match = thread_pattern.search(text)
        if th_match:
            thread_size = th_match.group(1).upper()

        # Anchor type
        anchor_type = "CHEMICAL_EPOXY_STUD"
        if "UNDERCUT" in upper_text or "HDA" in upper_text or "UA-" in tag:
            anchor_type = "MECHANICAL_UNDERCUT"
        elif "CONCRETE SCREW" in upper_text or "SCREW BOLT" in upper_text or "TITEN" in upper_text or "HUS" in upper_text or "SA-" in tag:
            anchor_type = "CONCRETE_SCREW_BOLT"
        elif "WEDGE" in upper_text or "HST" in upper_text or "THROUGH BOLT" in upper_text or "WA-" in tag:
            anchor_type = "EXPANSION_ANCHOR"
        elif "DROP-IN" in upper_text or "DROP IN" in upper_text or "HKD" in upper_text:
            anchor_type = "DROP_IN_ANCHOR"
        elif "CHEMICAL" in upper_text or "EPOXY" in upper_text or "ADHESIVE" in upper_text or "HIT-RE" in upper_text or "CA-" in tag:
            anchor_type = "CHEMICAL_EPOXY_STUD"

        # Embedment depth
        embedment_depth_mm: Optional[int] = None
        hef_match = hef_pattern.search(text)
        if hef_match:
            val = int(hef_match.group(1))
            if 30 <= val <= 600:
                embedment_depth_mm = val

        # Steel material
        steel_material = "GRADE_8_8_GALV"
        if "HCR" in upper_text or "HIGH CORROSION" in upper_text:
            steel_material = "HCR_CORROSION"
        elif "STAINLESS" in upper_text or "A4" in upper_text or "316" in upper_text or "SS316" in upper_text:
            steel_material = "STAINLESS_A4_316"
        elif "GALV" in upper_text or "HDG" in upper_text or "8.8" in upper_text:
            steel_material = "GRADE_8_8_GALV"
        elif "ZINC" in upper_text or "BRIGHT ZINC" in upper_text:
            steel_material = "CARBON_STEEL_ZINC"

        # Seismic category
        seismic_category: Optional[str] = None
        if "C2" in upper_text or "SEISMIC C2" in upper_text:
            seismic_category = "SEISMIC_C2"
        elif "C1" in upper_text or "SEISMIC C1" in upper_text:
            seismic_category = "SEISMIC_C1"
        elif "STATIC" in upper_text:
            seismic_category = "STATIC_ONLY"

        # Cracked concrete
        cracked_concrete_approved = any(cc in upper_text for cc in [
            "CRACKED CONCRETE", "CRACKED & NON-CRACKED", "CRACKED AND UNCRACKED", "C2"
        ]) or seismic_category == "SEISMIC_C2" or anchor_type == "MECHANICAL_UNDERCUT"

        candidate = PostInstalledAnchorCandidate(
            item_id=item_id,
            anchor_type=anchor_type,
            tag=tag,
            thread_size=thread_size,
            embedment_depth_mm=embedment_depth_mm,
            steel_material=steel_material,
            seismic_category=seismic_category,
            cracked_concrete_approved=cracked_concrete_approved,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results