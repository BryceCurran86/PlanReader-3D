"""
Source Industrial Concrete Slab Sawcut Dowel Basket Assembly Shadow Authority.

Extracts and validates welded wire dowel basket assemblies, round/square dowel bars (R16/R20/R24),
dowel spacing and lengths, slab depths, and de-bonding expansion sleeves strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SlabDowelBasketAssemblyCallout:
    raw_text: str
    joint_type: str
    dowel_bar_type: str
    dowel_spacing_mm: float
    dowel_length_mm: float
    slab_thickness_mm: float
    debonding_treatment: str
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


def parse_slab_dowel_basket_assembly_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "DOWEL BASKET",
        "DOWEL CRADLE",
        "BASKET ASSEMBLY",
        "CONTRACTION JOINT BASKET",
        "SAWCUT JOINT BASKET",
        "CRADLE ASSEMBLY",
        "SLAB DOWEL BASKET",
        "DOWEL BASKET JOINT",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("DOWEL" in upper) and ("BASKET" in upper or "CRADLE" in upper)
    )
    if not has_trigger:
        return None

    # Joint classification
    if any(k in upper for k in ["SAWCUT", "CONTRACTION JOINT", "SAWN JOINT"]):
        joint = "SAWCUT_CONTRACTION_JOINT"
    elif any(k in upper for k in ["EXPANSION JOINT", "EXPANSION BASKET"]):
        joint = "EXPANSION_BASKET_JOINT"
    elif any(k in upper for k in ["INDUCED", "WEAKENED PLANE"]):
        joint = "INDUCED_CRACK_JOINT"
    elif any(k in upper for k in ["LONGITUDINAL", "HINGED"]):
        joint = "LONGITUDINAL_HINGED_JOINT"
    else:
        joint = "SAWCUT_CONTRACTION_JOINT"

    # Dowel bar diameter / shape
    if "PLATE DOWEL" in upper:
        dowel_type = "PLATE_DOWEL_BASKET"
    elif "SQUARE" in upper:
        dowel_type = "SQUARE_DOWEL_BAR"
    elif any(k in upper for k in ["R16", "16MM DIA", "16MM ROUND", "D16"]):
        dowel_type = "ROUND_STEEL_DOWEL_R16"
    elif any(k in upper for k in ["R24", "24MM DIA", "24MM ROUND", "D24"]):
        dowel_type = "ROUND_STEEL_DOWEL_R24"
    elif any(k in upper for k in ["R28", "28MM DIA", "28MM ROUND", "D28"]):
        dowel_type = "ROUND_STEEL_DOWEL_R28"
    elif any(k in upper for k in ["R20", "20MM DIA", "20MM ROUND", "D20"]):
        dowel_type = "ROUND_STEEL_DOWEL_R20"
    else:
        dowel_type = "ROUND_STEEL_DOWEL_R20"

    # Dowel on-center spacing (mm)
    spacing_match = re.search(r"(?:AT|@)\s*(\d{2,4})\s*(?:MM)?\s*(?:CTS?|CENTRES?|CENTERS?|PITCH|O/?C)", upper)
    if not spacing_match:
        spacing_match = re.search(r"(\d{2,4})\s*MM\s*(?:CTS|CENTRES|PITCH|SPACING)", upper)

    if spacing_match:
        spacing_mm = float(spacing_match.group(1))
    else:
        spacing_mm = 300.0  # standard engineering default for heavy industrial slabs

    # Dowel length (mm)
    len_match = re.search(r"(\d{3})\s*MM\s*(?:LONG|LG|LENGTH)", upper)
    if not len_match:
        len_match = re.search(r"(?:X|\*)\s*(\d{3})\s*MM\b", upper)

    if len_match and 300.0 <= float(len_match.group(1)) <= 800.0:
        dowel_len = float(len_match.group(1))
    else:
        dowel_len = 450.0  # standard 450mm dowel length

    # Slab thickness (mm)
    th_match = re.search(r"(\d{2,3})\s*MM(?:\s+[A-Z]+){0,3}\s*SLAB\b", upper)
    if not th_match:
        th_match = re.search(r"(\d{2,3})\s*MM\s*(?:THICK|THICKNESS)", upper)
    if not th_match:
        th_match = re.search(r"(?:SLAB\s*THICKNESS|DEPTH)\s*(?:OF|:)?\s*(\d{2,3})\s*MM", upper)

    if th_match and 100.0 <= float(th_match.group(1)) <= 500.0:
        slab_th = float(th_match.group(1))
    else:
        slab_th = 200.0  # standard industrial slab depth

    # De-bonding treatment (evaluate negation/debonded correctly without substring collisions)
    if any(k in upper for k in ["WITHOUT SLEEVE", "NO SLEEVE", "FULLY BONDED", "UN-DEBONDED"]):
        debond = "NONE"
    elif any(k in upper for k in ["TECTYL", "BITUMEN"]):
        debond = "TECTYL_COATED"
    elif any(k in upper for k in ["GREASE", "GREASED", "DEBONDED", "HALF GREASED"]):
        debond = "HALF_GREASED_DEBONDED"
    elif any(k in upper for k in ["SLEEVE", "EXPANSION CAP", "PLASTIC CAP", "DEBONDING SLEEVE"]):
        debond = "PLASTIC_EXPANSION_SLEEVE"
    else:
        debond = "PLASTIC_EXPANSION_SLEEVE"

    return {
        "raw_text": clean,
        "joint_type": joint,
        "dowel_bar_type": dowel_type,
        "dowel_spacing_mm": spacing_mm,
        "dowel_length_mm": dowel_len,
        "slab_thickness_mm": slab_th,
        "debonding_treatment": debond,
    }


class SourceSlabDowelBasketAssemblyShadowAuthority:
    """Authority for concrete slab dowel basket assemblies in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[SlabDowelBasketAssemblyCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[SlabDowelBasketAssemblyCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[SlabDowelBasketAssemblyCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_slab_dowel_basket_assembly_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = SlabDowelBasketAssemblyCallout(
                raw_text=parsed["raw_text"],
                joint_type=parsed["joint_type"],
                dowel_bar_type=parsed["dowel_bar_type"],
                dowel_spacing_mm=parsed["dowel_spacing_mm"],
                dowel_length_mm=parsed["dowel_length_mm"],
                slab_thickness_mm=parsed["slab_thickness_mm"],
                debonding_treatment=parsed["debonding_treatment"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
