"""
Source Acoustic Ceiling Baffle Suspended Absorber Shadow Authority.

Extracts and validates suspended acoustic ceiling baffles/blades, PET polyester vs fiberglass materials,
NRC sound absorption ratings, baffle dimensions, on-center spacing, and cable suspension hardware
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class AcousticCeilingBaffleCallout:
    raw_text: str
    baffle_material: str
    nrc_sound_absorption: float
    baffle_thickness_mm: float
    baffle_dimensions_mm: Tuple[float, float]
    suspension_method: str
    center_spacing_mm: float
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


def parse_acoustic_ceiling_baffle_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ACOUSTIC BAFFLE",
        "CEILING BAFFLE",
        "ACOUSTIC BLADE",
        "SUSPENDED BAFFLE",
        "HANGING BAFFLE",
        "SOUND BAFFLE",
        "PET BAFFLE",
        "BAFFLE CEILING",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("BAFFLE" in upper or "BLADE" in upper) and ("ACOUSTIC" in upper or "CEILING" in upper)
    )
    if not has_trigger:
        return None

    # Material classification
    if any(k in upper for k in ["TIMBER", "WOOD", "TIMBER SLAT", "VENEER"]):
        material = "TIMBER_SLAT_PERFORATED"
    elif any(k in upper for k in ["ALUMINIUM", "ALUMINUM", "METAL BAFFLE"]):
        material = "ALUMINIUM_BAFFLE_MICRO_PERF"
    elif any(k in upper for k in ["FIBERGLASS", "GLASSWOOL", "MINERAL WOOL", "FABRIC WRAPPED"]):
        material = "GLASSWOOL_RESIN_BONDED"
    elif any(k in upper for k in ["PET", "POLYESTER", "AUTEX", "ECHO PANEL", "FELT"]):
        material = "POLYESTER_FIBER_PET"
    else:
        material = "POLYESTER_FIBER_PET"

    # NRC rating
    nrc_match = re.search(r"NRC\s*(?:RATING)?\s*:?\s*(\d+(?:\.\d+)?)", upper)
    if not nrc_match:
        nrc_match = re.search(r"(\d+(?:\.\d+)?)\s*NRC", upper)

    if nrc_match:
        nrc_val = float(nrc_match.group(1))
        if 0.40 <= nrc_val <= 1.10:
            nrc_rating = nrc_val
        else:
            nrc_rating = 0.85
    else:
        nrc_rating = 0.85  # standard high-performance PET baffle rating

    # Baffle thickness (mm)
    th_match = re.search(r"\b(12|24|40|50)\s*MM\b", upper)
    if th_match:
        baffle_th = float(th_match.group(1))
    else:
        alt_th = re.search(r"(\d{1,2}(?:\.\d+)?)\s*MM\s*(?:THICK|THICKNESS)", upper)
        if alt_th:
            baffle_th = float(alt_th.group(1))
        else:
            baffle_th = 24.0  # standard 24mm PET baffle default

    # Baffle dimensions (length, depth)
    dim_match = re.search(r"(\d{3,4})\s*(?:X|\*)\s*(\d{2,4})\s*(?:MM)?", upper)
    if dim_match:
        dims = (float(dim_match.group(1)), float(dim_match.group(2)))
    else:
        dims = (2400.0, 300.0)  # standard commercial ceiling baffle dimensions

    # Center spacing / pitch (mm)
    spacing_match = re.search(r"(?:AT|@)\s*(\d{2,4})\s*(?:MM)?\s*(?:CTS?|CENTRES?|CENTERS?|PITCH|O/?C)", upper)
    if not spacing_match:
        spacing_match = re.search(r"(\d{2,4})\s*MM\s*(?:CTS|CENTRES|PITCH|SPACING)", upper)

    if spacing_match:
        spacing_mm = float(spacing_match.group(1))
    else:
        spacing_mm = 300.0  # standard architectural spacing

    # Suspension method
    if any(k in upper for k in ["THREADED ROD", "M6 ROD", "M8 ROD", "STEEL ROD"]):
        suspension = "THREADED_ROD_SUSPENSION"
    elif any(k in upper for k in ["UNISTRUT", "CHANNEL", "T-GRID CLIP", "DIRECT FIX"]):
        suspension = "DIRECT_UNISTRUT_CHANNEL"
    elif any(k in upper for k in ["AIRCRAFT CABLE", "WIRE", "GRIPPLE", "SUSPENSION CABLE", "HANGING WIRE"]):
        suspension = "ADJUSTABLE_AIRCRAFT_WIRE"
    else:
        suspension = "ADJUSTABLE_AIRCRAFT_WIRE"

    return {
        "raw_text": clean,
        "baffle_material": material,
        "nrc_sound_absorption": nrc_rating,
        "baffle_thickness_mm": baffle_th,
        "baffle_dimensions_mm": dims,
        "suspension_method": suspension,
        "center_spacing_mm": spacing_mm,
    }


class SourceAcousticCeilingBaffleShadowAuthority:
    """Authority for acoustic ceiling baffles in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[AcousticCeilingBaffleCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[AcousticCeilingBaffleCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[AcousticCeilingBaffleCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_acoustic_ceiling_baffle_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = AcousticCeilingBaffleCallout(
                raw_text=parsed["raw_text"],
                baffle_material=parsed["baffle_material"],
                nrc_sound_absorption=parsed["nrc_sound_absorption"],
                baffle_thickness_mm=parsed["baffle_thickness_mm"],
                baffle_dimensions_mm=parsed["baffle_dimensions_mm"],
                suspension_method=parsed["suspension_method"],
                center_spacing_mm=parsed["center_spacing_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
