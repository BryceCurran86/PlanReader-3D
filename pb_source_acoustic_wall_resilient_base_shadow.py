"""
Source Acoustic Floating Wall Resilient Base Angle Isolator Shadow Authority.

Extracts and validates acoustic floating wall resilient base isolators, continuous elastomeric strips,
discrete resilient angle brackets, fastener acoustic bushings, and perimeter acoustic sealant beads
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class AcousticWallResilientBaseCallout:
    raw_text: str
    isolator_type: str
    elastomer_material: str
    thickness_mm: Optional[float]
    natural_frequency_hz: Optional[float]
    deflection_mm: Optional[float]
    spacing_mm: Optional[str]
    fastener_decoupling: str
    acoustic_sealant: str
    wall_subtype: str
    acoustic_rating: Optional[str]
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


def parse_acoustic_wall_resilient_base_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "RESILIENT BASE",
        "ACOUSTIC WALL BASE",
        "FLOATING WALL BASE",
        "BASE ANGLE ISOLAT",
        "RESILIENT ANGLE",
        "WALL ISOLATOR",
        "WALL BASE ISOLAT",
        "STUD TRACK ISOLAT",
        "SYLOMER BASE STRIP",
        "ACOUSTIC DECOUPL",
        "DECOUPLING STRIP",
        "DECOUPLED SOLE PLATE",
        "ISOLATED BASE TRACK",
        "RESILIENT MOUNT",
        "MOUNT BLOCK",
        "ISOLATION BLOCK",
        "PERIMETER ISOLATION STRIP",
        "ACOUSTIC SOLE PLATE",
        "WALL PERIMETER ISOLAT",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("ACOUSTIC" in upper or "RESILIENT" in upper or "ISOLAT" in upper or "MOUNT" in upper)
        and ("WALL BASE" in upper or "SOLE PLATE" in upper or "BOTTOM TRACK" in upper or "BASE ANGLE" in upper or "BASE BLOCK" in upper)
    )
    if not has_trigger:
        return None

    # Isolator Type
    if any(k in upper for k in ["BASE ANGLE", "RESILIENT ANGLE", "ANGLE BRACKET", "L-BRACKET", "ANGLE ISOLAT"]):
        isolator_type = "RESILIENT_BASE_ANGLE_BRACKET"
    elif any(k in upper for k in ["CONTINUOUS STRIP", "BASE STRIP", "PERIMETER STRIP", "CONTINUOUS ELASTOMER", "RUNNER STRIP"]):
        isolator_type = "CONTINUOUS_ELASTOMERIC_STRIP"
    elif any(k in upper for k in ["DISCRETE", "MOUNT BLOCK", "ISOLATION PAD", "BEARING BLOCK", "ISOLATION BLOCK"]):
        isolator_type = "DISCRETE_MOUNT_BLOCK"
    elif any(k in upper for k in ["BASE CHANNEL", "DEFLECTION CHANNEL", "U-CHANNEL"]):
        isolator_type = "SWAY_BRACE_BASE_CHANNEL"
    elif "STRIP" in upper:
        isolator_type = "CONTINUOUS_ELASTOMERIC_STRIP"
    else:
        isolator_type = "GENERIC_RESILIENT_BASE"

    # Elastomer Material
    if "SYLOMER" in upper:
        elastomer = "SYLOMER"
    elif "REGUPOL" in upper:
        elastomer = "REGUPOL"
    elif "NEOPRENE" in upper:
        elastomer = "NEOPRENE"
    elif "POLYURETHANE" in upper or re.search(r"\bPUR\b", upper):
        elastomer = "POLYURETHANE"
    elif "NATURAL RUBBER" in upper or re.search(r"\bRUBBER\b", upper):
        elastomer = "NATURAL_RUBBER"
    elif "EPDM" in upper:
        elastomer = "EPDM"
    else:
        elastomer = "UNSPECIFIED"

    # Thickness (mm)
    thickness_mm: Optional[float] = None
    th_m = re.search(r"(\d+(?:\.\d+)?)\s*MM\s*(?:THICK|THK|ELASTOMER|STRIP|PAD|ISOLAT)?", upper)
    if th_m:
        val = float(th_m.group(1))
        # Distinguish thickness (typically 5 to 100mm) from center-to-center spacing (300, 400, 600mm)
        if val <= 100.0:
            thickness_mm = val

    # Natural frequency (Hz)
    natural_freq_hz: Optional[float] = None
    fn_m = re.search(r"(\d+(?:\.\d+)?)\s*HZ\b", upper)
    if fn_m:
        natural_freq_hz = float(fn_m.group(1))

    # Static or dynamic deflection (mm)
    deflection_mm: Optional[float] = None
    def_m = re.search(r"(\d+(?:\.\d+)?)\s*MM\s*(?:STATIC\s+)?DEFLECTION", upper)
    if def_m:
        deflection_mm = float(def_m.group(1))

    # Spacing / Centers (mm)
    spacing_mm: Optional[str] = None
    sp_m = re.search(r"(\d{2,4})\s*MM\s*(?:C/?C|CTS|CENTRES|CENTERS|SPACING)", upper)
    if sp_m:
        spacing_mm = f"{sp_m.group(1)}MM C/C"
    elif "CONTINUOUS" in upper:
        spacing_mm = "CONTINUOUS"

    # Fastener Decoupling
    if any(k in upper for k in ["BUSHING AND WASHER", "NEOPRENE BUSHING", "ISOLATION WASHER", "ACOUSTIC BUSHING"]):
        fastener_decoupling = "NEOPRENE_BUSHING_WASHER"
    elif any(k in upper for k in ["ACOUSTIC SLEEVE", "ISOLATION SLEEVE", "ELASTOMERIC SLEEVE"]):
        fastener_decoupling = "ACOUSTIC_SLEEVE"
    elif any(k in upper for k in ["ISOLATED ANCHOR", "ISOLATED BOLT", "DECOUPLED ANCHOR"]):
        fastener_decoupling = "ISOLATED_ANCHOR_BOLT"
    else:
        fastener_decoupling = "UNSPECIFIED"

    # Acoustic Sealant / Caulking
    if any(k in upper for k in ["DUAL BEAD", "DOUBLE BEAD", "TWO BEADS", "2 BEADS"]):
        acoustic_sealant = "DUAL_BEAD_ACOUSTIC_CAULKING"
    elif any(k in upper for k in ["NON-HARDENING", "ACOUSTIC MASTIC"]):
        acoustic_sealant = "NON_HARDENING_MASTIC"
    elif any(k in upper for k in ["ACOUSTIC SEALANT", "ACOUSTIC CAULK", "SINGLE BEAD", "SEALANT BEAD"]):
        acoustic_sealant = "SINGLE_BEAD_ACOUSTIC_SEALANT"
    else:
        acoustic_sealant = "UNSPECIFIED"

    # Wall Subtype
    if any(k in upper for k in ["CINEMA", "AUDITORIUM", "THEATER", "THEATRE"]):
        wall_subtype = "CINEMA_BARRIER"
    elif any(k in upper for k in ["DOUBLE STUD", "TWIN STUD", "STAGGERED STUD"]):
        wall_subtype = "DOUBLE_STUD_ACOUSTIC"
    elif any(k in upper for k in ["MASONRY", "BLOCKWORK", "CMU", "CONCRETE BLOCK"]):
        wall_subtype = "MASONRY_BLOCK_BASE"
    elif any(k in upper for k in ["DRYWALL", "STEEL STUD", "LIGHTWEIGHT STUD", "STUD TRACK", "TIMBER STUD", "SOLE PLATE", "BOTTOM TRACK", "TRACK"]):
        wall_subtype = "DRYWALL_STUD_TRACK"
    else:
        wall_subtype = "GENERIC_PARTITION"

    # Acoustic Rating (STC, Rw, Rw+Ctr)
    acoustic_rating: Optional[str] = None
    stc_m = re.search(r"\b(STC\s*\d{2,3}|RW(?:\s*\+\s*CTR)?\s*\d{2,3})\b", upper)
    if stc_m:
        acoustic_rating = stc_m.group(1).replace(" ", "")

    return {
        "raw_text": clean,
        "isolator_type": isolator_type,
        "elastomer_material": elastomer,
        "thickness_mm": thickness_mm,
        "natural_frequency_hz": natural_freq_hz,
        "deflection_mm": deflection_mm,
        "spacing_mm": spacing_mm,
        "fastener_decoupling": fastener_decoupling,
        "acoustic_sealant": acoustic_sealant,
        "wall_subtype": wall_subtype,
        "acoustic_rating": acoustic_rating,
    }


def extract_acoustic_wall_resilient_base_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[AcousticWallResilientBaseCallout]:
    results: List[AcousticWallResilientBaseCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_acoustic_wall_resilient_base_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = AcousticWallResilientBaseCallout(
            raw_text=parsed["raw_text"],
            isolator_type=parsed["isolator_type"],
            elastomer_material=parsed["elastomer_material"],
            thickness_mm=parsed["thickness_mm"],
            natural_frequency_hz=parsed["natural_frequency_hz"],
            deflection_mm=parsed["deflection_mm"],
            spacing_mm=parsed["spacing_mm"],
            fastener_decoupling=parsed["fastener_decoupling"],
            acoustic_sealant=parsed["acoustic_sealant"],
            wall_subtype=parsed["wall_subtype"],
            acoustic_rating=parsed["acoustic_rating"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_acoustic_decoupling": parsed["fastener_decoupling"] != "UNSPECIFIED",
                "has_sealant": parsed["acoustic_sealant"] != "UNSPECIFIED",
            },
        )
        results.append(candidate)
    return results


def validate_acoustic_wall_resilient_base_system(
    candidates: List[AcousticWallResilientBaseCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    material_counts: Dict[str, int] = {}
    subtype_counts: Dict[str, int] = {}
    isolated_fasteners = 0
    sealed_bases = 0

    for c in candidates:
        type_counts[c.isolator_type] = type_counts.get(c.isolator_type, 0) + 1
        material_counts[c.elastomer_material] = material_counts.get(c.elastomer_material, 0) + 1
        subtype_counts[c.wall_subtype] = subtype_counts.get(c.wall_subtype, 0) + 1
        if c.fastener_decoupling != "UNSPECIFIED":
            isolated_fasteners += 1
        if c.acoustic_sealant != "UNSPECIFIED":
            sealed_bases += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "material_counts": material_counts,
        "subtype_counts": subtype_counts,
        "isolated_fasteners_count": isolated_fasteners,
        "sealed_bases_count": sealed_bases,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
