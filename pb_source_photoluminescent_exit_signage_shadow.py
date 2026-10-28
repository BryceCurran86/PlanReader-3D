"""Emergency Exit Photoluminescent & Egress Signage Shadow Authority.

Deterministic shadow extraction authority for photoluminescent exit signage,
self-luminous egress route markers, and directional running man symbols.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ExitSignCandidate:
    """Extracted emergency exit sign candidate."""
    item_id: str
    sign_type: str  # "PHOTOLUMINESCENT", "SELF_LUMINOUS", "LED_ILLUMINATED", "STANDARD"
    tag: str
    direction: str  # "RUNNING_MAN_LEFT", "RUNNING_MAN_RIGHT", "RUNNING_MAN_STRAIGHT", "EXIT_ONLY", "DOUBLE_SIDED"
    viewing_distance_m: Optional[int]
    luminance_class: str  # "CLASS_A", "CLASS_B", "CLASS_C", "CLASS_D", "UL924", "STANDARD"
    mounting: str  # "WALL_MOUNTED", "CEILING_SUSPENDED", "FLAG_MOUNTED", "RECESSED", "STANDARD"
    is_double_sided: bool
    coordinates: Tuple[float, float]
    raw_text: str
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "item_id": self.item_id,
            "sign_type": self.sign_type,
            "tag": self.tag,
            "direction": self.direction,
            "viewing_distance_m": self.viewing_distance_m,
            "luminance_class": self.luminance_class,
            "mounting": self.mounting,
            "is_double_sided": self.is_double_sided,
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


def extract_exit_signs(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[ExitSignCandidate]:
    """Extract emergency exit signs and photoluminescent markers deterministically."""
    results: List[ExitSignCandidate] = []
    processed_count = 0

    dist_pattern = re.compile(r"(\d{2})\s*M(?:ETERS?|ETRES?)?\s*(?:VIEWING|DISTANCE)?\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:EX|EXIT|PL|ES|EMX|RMS)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"exit_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "FIRE EXTINGUISHER ONLY", "HOSE REEL ONLY", "FIRE HYDRANT ONLY",
            "SMOKE ALARM", "EXIT DOOR GRILLE"
        ]):
            continue

        is_exit_sign = any(k in upper_text for k in [
            "EXIT SIGN", "RUNNING MAN", "PHOTOLUMINESCENT", "SELF-LUMINOUS",
            "EGRESS SIGN", "EMERGENCY EXIT", "ESCAPE ROUTE SIGN"
        ]) or (tag_pattern.search(text) is not None and ("EXIT" in upper_text or "SIGN" in upper_text or "LUM" in upper_text))

        if not is_exit_sign:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "EXIT-SIGN"

        # Sign type
        sign_type = "STANDARD"
        if "PHOTOLUMINESCENT" in upper_text or "GLOW IN THE DARK" in upper_text or "PL SIGN" in upper_text:
            sign_type = "PHOTOLUMINESCENT"
        elif "SELF-LUMINOUS" in upper_text or "TRITIUM" in upper_text:
            sign_type = "SELF_LUMINOUS"
        elif "LED" in upper_text or "ILLUMINATED" in upper_text:
            sign_type = "LED_ILLUMINATED"

        # Double sided
        is_double_sided = any(ds in upper_text for ds in ["DOUBLE SIDED", "DOUBLE-SIDED", "2-SIDED", "FLAG MOUNT"])

        # Direction
        direction = "EXIT_ONLY"
        if is_double_sided:
            direction = "DOUBLE_SIDED"
        elif any(l in upper_text for l in ["LEFT", "<-", "<="]):
            direction = "RUNNING_MAN_LEFT"
        elif any(r in upper_text for r in ["RIGHT", "->", "=>"]):
            direction = "RUNNING_MAN_RIGHT"
        elif "STRAIGHT" in upper_text or "ARROW UP" in upper_text or "FORWARD" in upper_text:
            direction = "RUNNING_MAN_STRAIGHT"
        elif "RUNNING MAN" in upper_text or "PICTO" in upper_text:
            direction = "RUNNING_MAN_STRAIGHT"

        # Viewing distance
        viewing_distance_m: Optional[int] = None
        dist_match = dist_pattern.search(text)
        if dist_match:
            viewing_distance_m = int(dist_match.group(1))

        # Luminance class (check Class D, C, B, A in strict order)
        luminance_class = "STANDARD"
        if "CLASS D" in upper_text:
            luminance_class = "CLASS_D"
        elif "CLASS C" in upper_text:
            luminance_class = "CLASS_C"
        elif "CLASS B" in upper_text:
            luminance_class = "CLASS_B"
        elif "CLASS A" in upper_text:
            luminance_class = "CLASS_A"
        elif "UL924" in upper_text or "UL 924" in upper_text:
            luminance_class = "UL924"

        # Mounting
        mounting = "STANDARD"
        if "FLAG" in upper_text or "CANTILEVER" in upper_text:
            mounting = "FLAG_MOUNTED"
        elif "CEILING" in upper_text or "SUSPENDED" in upper_text or "PENDANT" in upper_text:
            mounting = "CEILING_SUSPENDED"
        elif "RECESSED" in upper_text or "FLUSH" in upper_text:
            mounting = "RECESSED"
        elif "WALL" in upper_text:
            mounting = "WALL_MOUNTED"

        candidate = ExitSignCandidate(
            item_id=item_id,
            sign_type=sign_type,
            tag=tag,
            direction=direction,
            viewing_distance_m=viewing_distance_m,
            luminance_class=luminance_class,
            mounting=mounting,
            is_double_sided=is_double_sided,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
