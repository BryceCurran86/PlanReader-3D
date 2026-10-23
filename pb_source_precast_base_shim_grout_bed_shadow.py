"""
Source Precast Concrete Panel Base Shim Pack & Structural Grout Bed Shadow Authority.

Extracts and validates precast concrete wall panel base levelling shim packs, nominal grout bed
thicknesses, high-strength non-shrink grout specifications, placement methods, and backer containment
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class PrecastBaseShimGroutBedCallout:
    raw_text: str
    grout_bed_thickness_mm: float
    shim_pack_type: str
    shim_dimensions_mm: Tuple[float, float]
    grout_strength_mpa: float
    grout_placement_method: str
    containment_backer: str
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


def parse_precast_base_shim_grout_bed_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SHIM",
        "GROUT BED",
        "BASE GROUT",
        "BEDDING GROUT",
        "PANEL BASE",
        "NON-SHRINK GROUT",
        "NON SHRINK GROUT",
        "PACKER",
        "LEVELLING PACK",
        "DRY PACK",
        "DRYPACK",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Grout bed thickness extraction (e.g. 20mm, 25mm, 30mm, 40mm, 50mm)
    thickness_mm = 25.0  # standard engineering default for precast wall base joint
    th_match = re.search(
        r"(?:(?:GROUT\s*(?:BED|JOINT)?|BASE|BEDDING|GAP|NOMINAL)\s*(?:THICKNESS|DEPTH)?\s*(?:OF|:)?\s*|\b)(\d{2,3})\s*(?:MM|MILLIMETRE)",
        upper,
    )
    if th_match:
        thickness_mm = float(th_match.group(1))

    # Shim pack type determination
    if any(k in upper for k in ["STEEL PACKER", "STEEL SHIM", "MILD STEEL PACKER", "STEEL LEVELLING PLATE"]):
        shim_type = "STEEL_PACKER_PLATE"
    elif any(k in upper for k in ["NEOPRENE", "ELASTOMERIC", "RUBBER BEARING PAD"]):
        shim_type = "ELASTOMERIC_BEARING_PAD"
    elif any(k in upper for k in ["HORSESHOE", "PLASTIC SHIM", "POLYPROPYLENE SHIM", "HDPE SHIM", "PLASTIC PACKER", "NON-SKID SHIM"]):
        shim_type = "PLASTIC_HORSESHOE_SHIM"
    elif "SHIM" in upper or "PACKER" in upper:
        shim_type = "HIGH_DENSITY_PLASTIC_SHIM"
    else:
        shim_type = "STANDARD_LEVELLING_SHIM"

    # Shim dimensions (e.g. 100x100mm, 150x100mm, 75x75mm)
    dim_match = re.search(r"(\d{2,3})\s*(?:X|\*)\s*(\d{2,3})\s*(?:MM)?", upper)
    if dim_match:
        shim_dims = (float(dim_match.group(1)), float(dim_match.group(2)))
    else:
        shim_dims = (100.0, 100.0)

    # Grout compressive strength (MPa)
    mpa_match = re.search(r"(\d{2,3})\s*(?:MPA|MEGAPASCAL)", upper)
    if mpa_match:
        strength_mpa = float(mpa_match.group(1))
    else:
        if "CLASS C" in upper:
            strength_mpa = 70.0
        elif "HIGH STRENGTH" in upper:
            strength_mpa = 65.0
        else:
            strength_mpa = 60.0

    # Grout placement method
    if any(k in upper for k in ["DRY PACK", "DRY-PACK", "DRYPACK", "RAMMED MORTAR"]):
        placement = "DRY_PACK_MORTAR"
    elif any(k in upper for k in ["PUMPED", "PRESSURE PUMP", "PRESSURE GROUT"]):
        placement = "PRESSURE_PUMPED_GROUT"
    elif any(k in upper for k in ["FLOWABLE", "FLUID", "GRAVITY FLOW", "TREMIE"]):
        placement = "FLOWABLE_FLUID_GROUT"
    else:
        placement = "STANDARD_NON_SHRINK_GROUT"

    # Containment backer
    if any(k in upper for k in ["BACKER ROD", "FOAM ROD", "PE FOAM ROD"]):
        containment = "FOAM_BACKER_ROD"
    elif any(k in upper for k in ["GROUT TAPE", "FOAM TAPE", "SEALING TAPE"]):
        containment = "GROUT_FOAM_TAPE"
    elif any(k in upper for k in ["TIMBER STOP", "PLYWOOD STOP", "TIMBER FORMWORK"]):
        containment = "TIMBER_STOP"
    else:
        containment = "UNSPECIFIED"

    return {
        "raw_text": clean,
        "grout_bed_thickness_mm": thickness_mm,
        "shim_pack_type": shim_type,
        "shim_dimensions_mm": shim_dims,
        "grout_strength_mpa": strength_mpa,
        "grout_placement_method": placement,
        "containment_backer": containment,
    }


class SourcePrecastBaseShimGroutBedShadowAuthority:
    """Authority for precast concrete panel base shim packs and grout beds in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[PrecastBaseShimGroutBedCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[PrecastBaseShimGroutBedCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[PrecastBaseShimGroutBedCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_precast_base_shim_grout_bed_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = PrecastBaseShimGroutBedCallout(
                raw_text=parsed["raw_text"],
                grout_bed_thickness_mm=parsed["grout_bed_thickness_mm"],
                shim_pack_type=parsed["shim_pack_type"],
                shim_dimensions_mm=parsed["shim_dimensions_mm"],
                grout_strength_mpa=parsed["grout_strength_mpa"],
                grout_placement_method=parsed["grout_placement_method"],
                containment_backer=parsed["containment_backer"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
