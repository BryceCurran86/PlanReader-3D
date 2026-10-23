"""
Source Structural Steel Rafter Knee Haunch Stiffener Plate Shadow Authority.

Extracts and validates structural steel portal frame knee haunches, cut-beam tapered haunches,
column web stiffener plates, moment connection bolt groups, and weld specifications strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SteelKneeHaunchStiffenerCallout:
    raw_text: str
    haunch_type: str
    stiffener_plate_thickness_mm: Optional[float]
    haunch_depth_mm: Optional[float]
    haunch_length_mm: Optional[float]
    bolt_specification: Optional[str]
    weld_specification: Optional[str]
    stiffener_orientation: str
    portal_member_section: Optional[str]
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


def parse_steel_knee_haunch_stiffener_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "KNEE HAUNCH",
        "RAFTER HAUNCH",
        "PORTAL KNEE",
        "HAUNCH STIFFENER",
        "KNEE STIFFENER",
        "EAVES HAUNCH",
        "RAFTER KNEE",
        "HAUNCH CONNECTION",
        "COLUMN KNEE JOINT",
        "KNEE MOMENT CONNECTION",
        "PORTAL FRAME HAUNCH",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("HAUNCH" in upper or "KNEE" in upper)
        and ("RAFTER" in upper or "COLUMN" in upper or "PORTAL" in upper or "MOMENT CONNECTION" in upper or "STIFFENER" in upper)
    )
    if not has_trigger:
        return None

    # Haunch Type
    if any(k in upper for k in ["CUT FROM", "CUT BEAM", "TAPERED UB", "CUT UB"]):
        haunch_type = "TAPERED_CUT_BEAM_HAUNCH"
    elif any(k in upper for k in ["PLATE HAUNCH", "FABRICATED PLATE", "BUILT-UP"]):
        haunch_type = "FABRICATED_PLATE_HAUNCH"
    elif any(k in upper for k in ["FLANGE DOUBLER", "DOUBLER PLATE"]):
        haunch_type = "FLANGE_DOUBLER_HAUNCH"
    else:
        haunch_type = "GENERIC_KNEE_HAUNCH"

    # Stiffener Plate Thickness (mm)
    stiffener_th_mm: Optional[float] = None
    th_m = (
        re.search(r"(\d{1,2})\s*MM(?:\s+(?:THICK|THK))?(?:\s+[A-Z]+){0,3}\s*(?:STIFFENER|STIFF|PLATE)", upper)
        or re.search(r"(?:STIFFENER|STIFF|PLATE)[A-Z\s]{0,25}?(\d{1,2})\s*MM(?:\s+(?:THK|THICK))?", upper)
    )
    if th_m:
        stiffener_th_mm = float(th_m.group(1))

    # Haunch Depth (mm)
    haunch_depth_mm: Optional[float] = None
    depth_m = re.search(r"(\d{3,4})\s*MM\s*(?:DEEP|DEPTH)", upper)
    if depth_m:
        haunch_depth_mm = float(depth_m.group(1))

    # Haunch Length (mm)
    haunch_length_mm: Optional[float] = None
    len_m = re.search(r"(\d{3,4})\s*MM\s*(?:LONG|LENGTH|HAUNCH LENGTH)", upper)
    if len_m:
        haunch_length_mm = float(len_m.group(1))
    else:
        # e.g., 600 DEEP X 1500 LONG or 1500 LG HAUNCH
        lg_m = re.search(r"(\d{3,4})\s*LG\s*(?:HAUNCH)?", upper)
        if lg_m:
            haunch_length_mm = float(lg_m.group(1))

    # Bolt Specification
    bolt_spec: Optional[str] = None
    bolt_m = re.search(r"(\d+\s*[-xX]\s*M\d{2}(?:\s*(?:8\.8/S|8\.8|10\.9|GR\s*8\.8|GRADE\s*8\.8|STRUCTURAL))?)", upper)
    if bolt_m:
        bolt_spec = bolt_m.group(1).replace(" ", "")
    else:
        single_bolt_m = re.search(r"\b(M\d{2}(?:\s*(?:8\.8/S|8\.8|10\.9|GR\s*8\.8|GRADE\s*8\.8|STRUCTURAL))?)\b", upper)
        if single_bolt_m and ("BOLT" in upper or "8.8" in upper):
            bolt_spec = single_bolt_m.group(1).replace(" ", "")

    # Weld Specification
    weld_spec: Optional[str] = None
    weld_m = re.search(r"(\d+\s*MM\s*(?:CFW|FILLET(?:\s*WELD)?|GP\s*WELD|SP\s*WELD))", upper)
    if weld_m:
        weld_spec = weld_m.group(1).replace(" ", "")
    elif "FPBW" in upper or "FULL PENETRATION" in upper or "BUTT WELD" in upper:
        weld_spec = "FPBW"

    # Stiffener Orientation
    if "DIAGONAL" in upper:
        stiffener_orientation = "DIAGONAL_KNEE_STIFFENER"
    elif "TRANSVERSE" in upper or "HORIZONTAL" in upper:
        stiffener_orientation = "TRANSVERSE_COLUMN_STIFFENER"
    elif "CONTINUITY" in upper or "WEB STIFFENER" in upper:
        stiffener_orientation = "WEB_CONTINUITY_STIFFENER"
    else:
        stiffener_orientation = "UNSPECIFIED"

    # Member Section (UB, UC, PFC)
    section_m = re.search(r"\b(\d{3,4}UB\d{2,3}|\d{3,4}UC\d{2,3}|\d{3,4}PFC\d{2,3})\b", upper)
    portal_section = section_m.group(1) if section_m else None

    return {
        "raw_text": clean,
        "haunch_type": haunch_type,
        "stiffener_plate_thickness_mm": stiffener_th_mm,
        "haunch_depth_mm": haunch_depth_mm,
        "haunch_length_mm": haunch_length_mm,
        "bolt_specification": bolt_spec,
        "weld_specification": weld_spec,
        "stiffener_orientation": stiffener_orientation,
        "portal_member_section": portal_section,
    }


def extract_steel_knee_haunch_stiffener_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[SteelKneeHaunchStiffenerCallout]:
    results: List[SteelKneeHaunchStiffenerCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_steel_knee_haunch_stiffener_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = SteelKneeHaunchStiffenerCallout(
            raw_text=parsed["raw_text"],
            haunch_type=parsed["haunch_type"],
            stiffener_plate_thickness_mm=parsed["stiffener_plate_thickness_mm"],
            haunch_depth_mm=parsed["haunch_depth_mm"],
            haunch_length_mm=parsed["haunch_length_mm"],
            bolt_specification=parsed["bolt_specification"],
            weld_specification=parsed["weld_specification"],
            stiffener_orientation=parsed["stiffener_orientation"],
            portal_member_section=parsed["portal_member_section"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_bolts": parsed["bolt_specification"] is not None,
                "has_welds": parsed["weld_specification"] is not None,
                "has_section": parsed["portal_member_section"] is not None,
            },
        )
        results.append(candidate)
    return results


def validate_steel_knee_haunch_stiffener_system(
    candidates: List[SteelKneeHaunchStiffenerCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    type_counts: Dict[str, int] = {}
    orientation_counts: Dict[str, int] = {}
    bolted_connections = 0
    welded_connections = 0

    for c in candidates:
        type_counts[c.haunch_type] = type_counts.get(c.haunch_type, 0) + 1
        orientation_counts[c.stiffener_orientation] = orientation_counts.get(c.stiffener_orientation, 0) + 1
        if c.bolt_specification is not None:
            bolted_connections += 1
        if c.weld_specification is not None:
            welded_connections += 1

    return {
        "total_candidates": total,
        "type_counts": type_counts,
        "orientation_counts": orientation_counts,
        "bolted_connections_count": bolted_connections,
        "welded_connections_count": welded_connections,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
