"""
Source Stormwater Retention OSD Orifice Plate & Trash Screen Shadow Authority.

Extracts and validates stormwater on-site detention (OSD) discharge control pits,
calibrated orifice plates, overflow weir crests, and protective trash screens strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class OSDOrificeTrashScreenCallout:
    raw_text: str
    orifice_diameter_mm: float
    orifice_plate_material: str
    trash_screen_type: str
    overflow_weir_included: bool
    cover_class: str
    anti_vortex_plate: bool
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


def parse_osd_orifice_trash_screen_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ORIFICE PLATE",
        "OSD PIT",
        "DISCHARGE CONTROL PIT",
        "DCP PIT",
        "TRASH SCREEN",
        "OSD DISCHARGE",
        "RETENTION ORIFICE",
        "OSD WEIR",
        "ON-SITE DETENTION PIT",
        "DETENTION ORIFICE",
        "DCP ORIFICE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Orifice diameter (e.g. "Ø75MM ORIFICE", "100MM ORIFICE", "50MM ORIFICE PLATE", "DN80 ORIFICE", "125MM ORIFICE")
    dia_match = re.search(r"\b(?:Ø|DN)?\s*(\d{2,3})\s*MM\s*(?:ORIFICE|DIA)?", upper)
    if not dia_match:
        dia_match = re.search(r"\b(?:ORIFICE|DCP)\s*(?:Ø|DN)?\s*(\d{2,3})\b", upper)
    orifice_dia = float(dia_match.group(1)) if dia_match else 100.0

    # Orifice plate material
    if "STAINLESS" in upper or "316" in upper:
        mat = "STAINLESS_STEEL_316"
    elif "BRASS" in upper:
        mat = "BRASS"
    elif "GALV" in upper:
        mat = "GALVANISED_STEEL"
    else:
        mat = "STAINLESS_STEEL_316"

    # Trash screen configuration
    if "WEDGE WIRE" in upper or "WEDGE-WIRE" in upper:
        screen = "STAINLESS_STEEL_WEDGE_WIRE"
    elif "PERFORATED" in upper:
        screen = "PERFORATED_PLATE"
    else:
        screen = "GALVANISED_MAX_20MM_APERTURE"

    # Overflow weir
    if "WITHOUT WEIR" in upper or "NO WEIR" in upper:
        has_weir = False
    elif any(k in upper for k in ["WEIR", "OVERFLOW", "HIGH LEVEL CREST", "EMERGENCY CREST"]):
        has_weir = True
    else:
        has_weir = True

    # Cover rating
    if any(k in upper for k in ["CLASS B", "FOOTWAY", "VERGE", "NON-TRAFFICABLE"]):
        cover = "CLASS_B_FOOTWAY"
    elif "LIGHT DUTY" in upper:
        cover = "LIGHT_DUTY"
    else:
        cover = "CLASS_D_ROADWAY"

    # Anti-vortex plate
    anti_vortex = any(k in upper for k in ["ANTI-VORTEX", "VORTEX BAFFLE", "VORTEX PLATE"])

    return {
        "raw_text": clean,
        "orifice_diameter_mm": orifice_dia,
        "orifice_plate_material": mat,
        "trash_screen_type": screen,
        "overflow_weir_included": has_weir,
        "cover_class": cover,
        "anti_vortex_plate": anti_vortex,
    }


def evaluate_osd_orifice_trash_screen_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[OSDOrificeTrashScreenCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[OSDOrificeTrashScreenCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_osd_orifice_trash_screen_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            OSDOrificeTrashScreenCallout(
                raw_text=parsed["raw_text"],
                orifice_diameter_mm=parsed["orifice_diameter_mm"],
                orifice_plate_material=parsed["orifice_plate_material"],
                trash_screen_type=parsed["trash_screen_type"],
                overflow_weir_included=parsed["overflow_weir_included"],
                cover_class=parsed["cover_class"],
                anti_vortex_plate=parsed["anti_vortex_plate"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "osd_standard": "AS3500.3-STORMWATER-OSD",
                },
            )
        )

    return results
