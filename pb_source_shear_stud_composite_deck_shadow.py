"""
Source Headed Concrete Shear Stud & Composite Decking Shadow Authority.

Extracts and validates headed shear studs (diameter/length mm), studs per trough,
composite steel decking profiles (Bondek/Condeck), steel BMT thickness (mm), and shear capacities (kN) strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ShearStudCompositeDeckCallout:
    raw_text: str
    stud_diameter_mm: float
    stud_length_mm: float
    studs_per_trough: int
    decking_profile: str
    deck_bmt_mm: float
    characteristic_shear_kn: float
    position: Tuple[float, float] = (0.0, 0.0)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


def snap_point(x: float, y: float, snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    """Snap coordinates to discrete precision grid."""
    if snap_tol <= 0.0:
        return (x, y)
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_shear_stud_composite_deck_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SHEAR STUD",
        "HEADED STUD",
        "NELSON STUD",
        "COMPOSITE BEAM",
        "COMPOSITE DECK",
        "BONDEK",
        "CONDECK",
        "KINGFLOR",
        "COMFLOR",
        "SHEAR CONNECTOR",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Stud diameter & length (e.g. "19X100", "19MM DIA X 125MM", "19X100MM SHEAR STUDS")
    stud_dia = 19.0
    stud_len = 100.0
    dim_match = re.search(r"\b(\d{2})\s*[X*x]\s*(\d{2,3})(?:MM)?", upper)
    if dim_match:
        stud_dia = float(dim_match.group(1))
        stud_len = float(dim_match.group(2))
    else:
        dia_match = re.search(r"(\d{2})\s*MM\s*(?:DIA|DIAMETER)", upper)
        if dia_match:
            stud_dia = float(dia_match.group(1))
        len_match = re.search(r"(\d{2,3})\s*MM\s*(?:LONG|LENGTH)", upper)
        if len_match:
            stud_len = float(len_match.group(1))

    # Studs per trough / pan / rib (e.g. "1 STUD PER PAN", "2 STUDS PER RIB", "PAIRS OF STUDS")
    if "2 STUD" in upper or "PAIRS" in upper or "DOUBLE STUD" in upper or "2 PER" in upper:
        per_trough = 2
    else:
        per_trough = 1

    # Decking profile
    if "CONDECK" in upper:
        profile = "CONDECK_HP_PROFILE"
    elif "KINGFLOR" in upper or "COMFLOR" in upper or "DOVETAIL" in upper:
        profile = "DOVETAIL_RE-ENTRANT_DECKING"
    elif "BONDEK" in upper or "TRAPEZOIDAL" in upper or "COMPOSITE DECK" in upper:
        profile = "PROFILED_COMPOSITE_STEEL_DECKING_BONDEK"
    else:
        profile = "PROFILED_COMPOSITE_STEEL_DECKING_BONDEK"

    # Deck base metal thickness BMT mm
    bmt = 0.75
    bmt_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:MM)?\s*BMT", upper)
    if bmt_match:
        bmt = float(bmt_match.group(1))
    elif "1.0" in upper or "1.0MM" in upper:
        bmt = 1.0

    # Characteristic shear capacity per stud kN (typically 70-110 kN)
    shear_kn = round(stud_dia * 4.5, 1)  # approx 85 kN for 19mm stud in composite deck

    return {
        "stud_diameter_mm": stud_dia,
        "stud_length_mm": stud_len,
        "studs_per_trough": per_trough,
        "decking_profile": profile,
        "deck_bmt_mm": bmt,
        "characteristic_shear_kn": shear_kn,
    }


class SourceShearStudCompositeDeckShadowAuthority:
    """Authority for extracting headed shear studs and composite steel decking in shadow candidate mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[ShearStudCompositeDeckCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[ShearStudCompositeDeckCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_shear_stud_composite_deck_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["stud_diameter_mm"], parsed["studs_per_trough"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = ShearStudCompositeDeckCallout(
                raw_text=text,
                stud_diameter_mm=parsed["stud_diameter_mm"],
                stud_length_mm=parsed["stud_length_mm"],
                studs_per_trough=parsed["studs_per_trough"],
                decking_profile=parsed["decking_profile"],
                deck_bmt_mm=parsed["deck_bmt_mm"],
                characteristic_shear_kn=parsed["characteristic_shear_kn"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
