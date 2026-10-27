"""Civil Stormwater Gross Pollutant Trap (GPT) & CDS Unit Shadow Authority.

Deterministic shadow extraction authority for stormwater gross pollutant traps,
continuous deflective separation (CDS) units, and hydrodynamic vortex separators.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class GrossPollutantTrapCandidate:
    """Extracted stormwater GPT or CDS separator candidate."""
    item_id: str
    element_type: str  # "CDS_UNIT", "BASKET_GPT", "HYDRODYNAMIC_SEPARATOR", "BAFFLE_BOX", "STANDARD"
    tag: str
    treatable_flow_lps: Optional[float]
    pipe_size_mm: Optional[int]
    sediment_storage_m3: Optional[float]
    screen_aperture_mm: Optional[float]
    bypass_type: str  # "INTERNAL_WEIR", "EXTERNAL_BYPASS", "OFFLINE", "STANDARD"
    cover_class: str  # "CLASS_D", "CLASS_B", "STANDARD"
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
            "treatable_flow_lps": self.treatable_flow_lps,
            "pipe_size_mm": self.pipe_size_mm,
            "sediment_storage_m3": self.sediment_storage_m3,
            "screen_aperture_mm": self.screen_aperture_mm,
            "bypass_type": self.bypass_type,
            "cover_class": self.cover_class,
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


def extract_gross_pollutant_traps(
    drawing_texts: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT,
    max_primitives: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[GrossPollutantTrapCandidate]:
    """Extract stormwater GPT and CDS units deterministically."""
    results: List[GrossPollutantTrapCandidate] = []
    processed_count = 0

    flow_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L/SEC|LITRES?/SEC(?:OND)?)\b", re.IGNORECASE)
    pipe_pattern = re.compile(r"\b(?:DN\s*(\d{3,4})|(\d{3,4})\s*MM|(\d{2,3})\s*(?:INCH|\"))\b", re.IGNORECASE)
    sediment_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:M3|CUBIC\s*M(?:ETERS?|ETRES?))\s*(?:SEDIMENT|SUMP|STORAGE)?\b", re.IGNORECASE)
    screen_pattern = re.compile(r"(\d+(?:\.\d+)?)\s*(?:MM|MICRON)\s*(?:SCREEN|APERTURE|MESH)\b", re.IGNORECASE)
    tag_pattern = re.compile(r"\b((?:GPT|CDS|HDS|SQID|WSUD)[-_]?(?:[A-Z0-9]{1,4}))\b", re.IGNORECASE)

    for item in drawing_texts:
        if processed_count >= max_primitives:
            break
        processed_count += 1

        text = str(item.get("text", "")).strip()
        coords_raw = item.get("coordinates", (0.0, 0.0))
        item_id = str(item.get("id", f"gpt_{len(results) + 1}"))
        coords = snap_point((float(coords_raw[0]), float(coords_raw[1])), tolerance)
        upper_text = text.upper()

        # Reject negative lookalikes
        if any(neg in upper_text for neg in [
            "GREASE TRAP", "SEWAGE PUMP", "SEPTIC TANK",
            "POTABLE WATER", "GAS REGULATOR", "SLAB EDGE"
        ]):
            continue

        is_gpt = any(k in upper_text for k in [
            "GROSS POLLUTANT TRAP", "GPT", "CONTINUOUS DEFLECTIVE", "CDS UNIT",
            "HYDRODYNAMIC SEPARATOR", "BAFFLE BOX", "SQID", "POLLUTANT INTERCEPTOR",
            "STORMWATER FILTER CHAMBER"
        ]) or (tag_pattern.search(text) is not None and ("STORMWATER" in upper_text or "DRAINAGE" in upper_text or "FLOW" in upper_text or "TREAT" in upper_text))

        if not is_gpt:
            continue

        tag_match = tag_pattern.search(text)
        tag = tag_match.group(1).upper() if tag_match else "GPT-UNIT"

        # Element type
        element_type = "STANDARD"
        if "CDS" in upper_text or "CONTINUOUS DEFLECTIVE" in upper_text:
            element_type = "CDS_UNIT"
        elif "HYDRODYNAMIC" in upper_text or "VORTEX" in upper_text or "HDS" in upper_text:
            element_type = "HYDRODYNAMIC_SEPARATOR"
        elif "BAFFLE BOX" in upper_text:
            element_type = "BAFFLE_BOX"
        elif "BASKET" in upper_text or "DROP-IN" in upper_text or "PIT INSERT" in upper_text:
            element_type = "BASKET_GPT"
        elif "GROSS POLLUTANT TRAP" in upper_text or re.search(r"\bGPT\b", upper_text):
            element_type = "BASKET_GPT"

        # Flow rate (L/s)
        treatable_flow_lps: Optional[float] = None
        fl_match = flow_pattern.search(text)
        if fl_match:
            treatable_flow_lps = float(fl_match.group(1))

        # Pipe size
        pipe_size_mm: Optional[int] = None
        p_match = pipe_pattern.search(text)
        if p_match:
            if p_match.group(1):
                pipe_size_mm = int(p_match.group(1))
            elif p_match.group(2):
                pipe_size_mm = int(p_match.group(2))
            elif p_match.group(3):
                pipe_size_mm = int(round(float(p_match.group(3)) * 25.4))

        # Sediment storage (m3)
        sediment_storage_m3: Optional[float] = None
        sed_match = sediment_pattern.search(text)
        if sed_match:
            sediment_storage_m3 = float(sed_match.group(1))

        # Screen aperture (mm)
        screen_aperture_mm: Optional[float] = None
        sc_match = screen_pattern.search(text)
        if sc_match:
            val = float(sc_match.group(1))
            if "MICRON" in upper_text:
                screen_aperture_mm = round(val / 1000.0, 3)
            else:
                screen_aperture_mm = val

        # Bypass arrangement
        bypass_type = "STANDARD"
        if "INTERNAL WEIR" in upper_text or "WEIR BYPASS" in upper_text:
            bypass_type = "INTERNAL_WEIR"
        elif "EXTERNAL BYPASS" in upper_text:
            bypass_type = "EXTERNAL_BYPASS"
        elif "OFFLINE" in upper_text:
            bypass_type = "OFFLINE"

        # Cover class
        cover_class = "STANDARD"
        if "CLASS D" in upper_text or "HEAVY DUTY" in upper_text or "TRAFFIC" in upper_text:
            cover_class = "CLASS_D"
        elif "CLASS B" in upper_text or "LIGHT DUTY" in upper_text:
            cover_class = "CLASS_B"

        candidate = GrossPollutantTrapCandidate(
            item_id=item_id,
            element_type=element_type,
            tag=tag,
            treatable_flow_lps=treatable_flow_lps,
            pipe_size_mm=pipe_size_mm,
            sediment_storage_m3=sediment_storage_m3,
            screen_aperture_mm=screen_aperture_mm,
            bypass_type=bypass_type,
            cover_class=cover_class,
            coordinates=coords,
            raw_text=text,
        )
        results.append(candidate)

    return results
