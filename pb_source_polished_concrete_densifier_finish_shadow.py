"""Concrete Slab Polished Finish & Penetrating Silicate Densifier Shadow Authority.

Deterministic shadow extraction authority for polished concrete slab finishes,
lithium/sodium silicate hardeners/densifiers, aggregate exposure classes, and gloss levels.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PolishedConcreteCandidate:
    """Extracted polished concrete finish or densifier candidate."""
    item_id: str
    finish_tag: str
    sheen_level: str  # "GROUND_MATTE", "HONED_SATIN", "SEMI_GLOSS", "HIGH_GLOSS", "BURNISHED", "STANDARD"
    aggregate_exposure: str  # "CLASS_A_CREAM", "CLASS_B_SALT_PEPPER", "CLASS_C_MEDIUM", "CLASS_D_FULL", "STANDARD"
    densifier_type: str  # "LITHIUM_SILICATE", "SODIUM_SILICATE", "POTASSIUM_SILICATE", "COLLOIDAL_SILICA", "STANDARD"
    has_penetrating_guard: bool
    grit_level: Optional[int]
    slip_rating: Optional[str]  # e.g. "P3", "P4", "R9", "R10"
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "finish_tag": self.finish_tag,
            "sheen_level": self.sheen_level,
            "aggregate_exposure": self.aggregate_exposure,
            "densifier_type": self.densifier_type,
            "has_penetrating_guard": self.has_penetrating_guard,
            "grit_level": self.grit_level,
            "slip_rating": self.slip_rating,
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


def extract_polished_concrete(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[PolishedConcreteCandidate]:
    """Extract polished concrete finish and densifier items deterministically."""
    results: List[PolishedConcreteCandidate] = []
    processed_count = 0

    grit_pattern = re.compile(r"(\d{3,4})\s*(?:GRIT|\b#\d{3,4})\b", re.IGNORECASE)
    slip_pattern = re.compile(r"\b(P[1-5]|R(?:9|1[0-3]))\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:PC|FIN|POL|CF)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"pc_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "CARPET", "VINYL", "CERAMIC TILE", "EPOXY COATING ONLY",
            "TIMBER FLOORING", "PAINT FINISH TO WALL", "ASPHALT"
        ]):
            continue

        is_polished = any(k in upper_text for k in [
            "POLISHED CONCRETE", "HONED CONCRETE", "BURNISHED CONCRETE",
            "CONCRETE DENSIFIER", "LITHIUM SILICATE", "DIAMOND POLISH",
            "EXPOSED AGGREGATE POLISH", "SALT AND PEPPER FINISH", "SALT & PEPPER"
        ]) or (tag_pattern.search(text) is not None and ("POLISH" in upper_text or "HONED" in upper_text or "DENSIFIER" in upper_text or "SLAB FINISH" in upper_text))

        if not is_polished:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "PC-FIN"

        # Sheen / finish level
        sheen_level = "HONED_SATIN"
        if "HIGH GLOSS" in upper_text or "HIGH-GLOSS" in upper_text or "3000 GRIT" in upper_text:
            sheen_level = "HIGH_GLOSS"
        elif "SEMI GLOSS" in upper_text or "SEMI-GLOSS" in upper_text or "1500 GRIT" in upper_text:
            sheen_level = "SEMI_GLOSS"
        elif "BURNISHED" in upper_text:
            sheen_level = "BURNISHED"
        elif "MATTE" in upper_text or "GROUND MATTE" in upper_text or "200 GRIT" in upper_text or "100 GRIT" in upper_text:
            sheen_level = "GROUND_MATTE"
        elif "HONED" in upper_text or "SATIN" in upper_text or "800 GRIT" in upper_text or "400 GRIT" in upper_text:
            sheen_level = "HONED_SATIN"

        # Aggregate exposure
        aggregate_exposure = "STANDARD"
        if "SALT AND PEPPER" in upper_text or "SALT & PEPPER" in upper_text or "CLASS B" in upper_text:
            aggregate_exposure = "CLASS_B_SALT_PEPPER"
        elif "FULL EXPOSURE" in upper_text or "CLASS D" in upper_text:
            aggregate_exposure = "CLASS_D_FULL"
        elif "MEDIUM AGGREGATE" in upper_text or "CLASS C" in upper_text:
            aggregate_exposure = "CLASS_C_MEDIUM"
        elif "CREAM" in upper_text or "ZERO EXPOSURE" in upper_text or "CLASS A" in upper_text:
            aggregate_exposure = "CLASS_A_CREAM"

        # Densifier chemical
        densifier_type = "STANDARD"
        if "LITHIUM" in upper_text:
            densifier_type = "LITHIUM_SILICATE"
        elif "SODIUM" in upper_text:
            densifier_type = "SODIUM_SILICATE"
        elif "POTASSIUM" in upper_text:
            densifier_type = "POTASSIUM_SILICATE"
        elif "COLLOIDAL" in upper_text:
            densifier_type = "COLLOIDAL_SILICA"

        # Penetrating guard
        has_penetrating_guard = any(g in upper_text for g in ["GUARD", "STAIN PROTECTOR", "PENETRATING SEALER", "SEALER", "STAIN SHIELD"])

        # Grit level
        grit_level: Optional[int] = None
        g_match = grit_pattern.search(text)
        if g_match:
            grit_level = int(g_match.group(1))

        # Slip rating
        slip_rating: Optional[str] = None
        sl_match = slip_pattern.search(text)
        if sl_match:
            slip_rating = sl_match.group(1).upper()

        candidate = PolishedConcreteCandidate(
            item_id=item_id,
            finish_tag=tag,
            sheen_level=sheen_level,
            aggregate_exposure=aggregate_exposure,
            densifier_type=densifier_type,
            has_penetrating_guard=has_penetrating_guard,
            grit_level=grit_level,
            slip_rating=slip_rating,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
