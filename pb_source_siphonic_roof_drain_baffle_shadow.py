"""
Source Stormwater Siphon Roof Drainage Primus Baffle & Air Baffle Shadow Authority.

Extracts and validates siphonic roof drainage outlets, anti-vortex air baffles, primus baffles,
tailpipe diameters, design siphonic flow rates, and membrane clamping flanges strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SiphonicRoofDrainBaffleCallout:
    raw_text: str
    outlet_type: str
    baffle_material: str
    design_flow_lps: Optional[float]
    tailpipe_dn: Optional[str]
    grate_guard_type: str
    membrane_flange_connection: str
    drainage_system: str
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


def parse_siphonic_roof_drain_baffle_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SIPHONIC",
        "SYPHONIC",
        "PRIMUS BAFFLE",
        "AIR BAFFLE",
        "ANTI-VORTEX",
        "ANTI VORTEX",
        "VORTEX BAFFLE",
        "SIPHON OUTLET",
        "SIPHON DRAIN",
    ]
    brand_match = any(b in upper for b in ["PLUVIA", "FASTFLOW", "SYFON"]) and any(
        w in upper for w in ["ROOF", "DRAIN", "OUTLET", "GUTTER", "SUMP", "SIPHON", "SYPHON", "BAFFLE"]
    )
    has_trigger = any(trig in upper for trig in triggers) or brand_match or (
        ("SIPHON" in upper or "SYPHON" in upper)
        and ("ROOF" in upper or "OUTLET" in upper or "DRAIN" in upper or "GUTTER" in upper)
    )
    if not has_trigger:
        return None

    # Outlet Type
    if any(k in upper for k in ["PRIMUS BAFFLE", "PRIMUS", "INDUCTION BAFFLE"]):
        outlet_type = "SIPHONIC_OUTLET_PRIMUS_BAFFLE"
    elif any(k in upper for k in ["PARAPET", "SCUPPER"]):
        outlet_type = "PARAPET_SCUPPER_SIPHON_OUTLET"
    elif any(k in upper for k in ["ANTI-VORTEX", "ANTI VORTEX", "VORTEX BAFFLE", "VORTEX PLATE", "AIR BAFFLE PLATE", "VORTEX"]):
        outlet_type = "ANTI_VORTEX_AIR_PLATE"
    elif any(k in upper for k in ["BOX GUTTER", "GUTTER SUMP", "GUTTER"]):
        outlet_type = "GUTTER_SUMP_SIPHON_DRAIN"
    else:
        outlet_type = "GENERIC_SIPHONIC_DRAIN"

    # Baffle Material
    if any(k in upper for k in ["STAINLESS", "SS316", "316 SS", "GRADE 316"]):
        baffle_material = "STAINLESS_STEEL_316"
    elif any(k in upper for k in ["CAST ALLOY", "ALUMINIUM", "ALUMINUM"]):
        baffle_material = "CAST_ALUMINUM"
    elif any(k in upper for k in ["POLYPROPYLENE", "UV STABILIZED", "UV RESISTANT", "PP"]):
        baffle_material = "UV_STABILIZED_POLYPROPYLENE"
    else:
        baffle_material = "UNSPECIFIED"

    # Design Flow (L/s)
    flow_lps: Optional[float] = None
    fl_m = re.search(r"(\d+(?:\.\d+)?)\s*(?:L/S|LPS|L/SEC)", upper)
    if fl_m:
        flow_lps = float(fl_m.group(1))

    # Tailpipe Nominal Diameter (DN)
    tailpipe_dn: Optional[str] = None
    dn_m = re.search(r"\bDN\s*(50|75|90|110|125|160|200)\b", upper)
    if dn_m:
        tailpipe_dn = f"DN{dn_m.group(1)}"
    else:
        mm_m = re.search(r"\b(50|75|90|110|125|160|200)\s*MM\s*(?:TAILPIPE|DROPPER|OUTLET|PIPE)?\b", upper)
        if mm_m:
            tailpipe_dn = f"DN{mm_m.group(1)}"

    # Grate / Guard
    if any(k in upper for k in ["LEAF GUARD", "LEAF BASKET", "LEAF DOME", "LEAF STRAINER"]):
        grate_guard = "LEAF_GUARD_BASKET"
    elif any(k in upper for k in ["GRAVEL GRATE", "GRAVEL GUARD", "GRAVEL COLLAR"]):
        grate_guard = "GRAVEL_GRATE_COLLAR"
    elif any(k in upper for k in ["TERRACE GRATE", "FLAT GRATE", "HEEL-PROOF", "HEELPROOF"]):
        grate_guard = "FLAT_TERRACE_GRATE"
    else:
        grate_guard = "UNSPECIFIED"

    # Clamping / Flange Connection
    if any(k in upper for k in ["CLAMPING FLANGE", "STAINLESS CLAMP", "CLAMP RING", "CLAMPING RING"]):
        membrane_flange = "STAINLESS_CLAMPING_FLANGE"
    elif any(k in upper for k in ["EPDM", "WATERPROOFING COLLAR", "MEMBRANE COLLAR"]):
        membrane_flange = "EPDM_WATERPROOFING_COLLAR"
    elif any(k in upper for k in ["BITUMEN", "BITUMINOUS", "TORCH-ON", "TORCH ON"]):
        membrane_flange = "BITUMINOUS_FLANGE"
    else:
        membrane_flange = "UNSPECIFIED"

    # Drainage System Role
    if any(k in upper for k in ["OVERFLOW", "SECONDARY SIPHON", "EMERGENCY SIPHON"]):
        drainage_system = "SECONDARY_OVERFLOW_SIPHON"
    else:
        drainage_system = "SIPHONIC_STORMWATER"

    return {
        "raw_text": clean,
        "outlet_type": outlet_type,
        "baffle_material": baffle_material,
        "design_flow_lps": flow_lps,
        "tailpipe_dn": tailpipe_dn,
        "grate_guard_type": grate_guard,
        "membrane_flange_connection": membrane_flange,
        "drainage_system": drainage_system,
    }


def extract_siphonic_roof_drain_baffle_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SiphonicRoofDrainBaffleCallout]:
    results: List[SiphonicRoofDrainBaffleCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_siphonic_roof_drain_baffle_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = SiphonicRoofDrainBaffleCallout(
            raw_text=parsed["raw_text"],
            outlet_type=parsed["outlet_type"],
            baffle_material=parsed["baffle_material"],
            design_flow_lps=parsed["design_flow_lps"],
            tailpipe_dn=parsed["tailpipe_dn"],
            grate_guard_type=parsed["grate_guard_type"],
            membrane_flange_connection=parsed["membrane_flange_connection"],
            drainage_system=parsed["drainage_system"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "is_overflow": parsed["drainage_system"] == "SECONDARY_OVERFLOW_SIPHON",
                "has_tailpipe": parsed["tailpipe_dn"] is not None,
                "has_flow_rating": parsed["design_flow_lps"] is not None,
            },
        )
        results.append(candidate)
    return results


def validate_siphonic_roof_drain_baffle_system(
    candidates: List[SiphonicRoofDrainBaffleCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    material_counts: Dict[str, int] = {}
    system_counts: Dict[str, int] = {}
    overflow_count = 0
    rated_flow_count = 0

    for c in candidates:
        type_counts[c.outlet_type] = type_counts.get(c.outlet_type, 0) + 1
        material_counts[c.baffle_material] = material_counts.get(c.baffle_material, 0) + 1
        system_counts[c.drainage_system] = system_counts.get(c.drainage_system, 0) + 1
        if c.drainage_system == "SECONDARY_OVERFLOW_SIPHON":
            overflow_count += 1
        if c.design_flow_lps is not None:
            rated_flow_count += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "material_counts": material_counts,
        "system_counts": system_counts,
        "overflow_count": overflow_count,
        "rated_flow_count": rated_flow_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
