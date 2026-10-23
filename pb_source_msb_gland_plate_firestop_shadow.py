"""
Source Electrical Main Switchboard Cable Entry Gland Plate & Firestop Shadow Authority.

Extracts and validates main switchboard cable entry gland plates, non-magnetic materials,
IP ratings, modular cable transit frames, and firestop seals strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class MSBGlandPlateFirestopCallout:
    raw_text: str
    gland_plate_material: str
    plate_thickness_mm: float
    entry_orientation: str
    firestop_transit_type: str
    ip_rating: str
    eddy_current_slots_required: bool
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


def parse_msb_gland_plate_firestop_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "GLAND PLATE",
        "MSB CABLE ENTRY",
        "CABLE TRANSIT",
        "NON-MAGNETIC GLAND",
        "SWITCHBOARD CABLE ENTRY",
        "ROXTEC",
        "MCT FRAME",
        "SWITCHBOARD FIRESTOP",
        "MDB GLAND PLATE",
        "EDDY CURRENT GLAND",
        "SWITCHBOARD GLAND",
        "CABLE ENTRY GLAND",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Gland plate material
    if "BRASS" in upper:
        mat = "BRASS_NON_MAGNETIC"
    elif any(k in upper for k in ["BAKELITE", "COMPOSITE", "NON-METALLIC"]):
        mat = "COMPOSITE_BAKELITE"
    elif "MILD STEEL" in upper or ("STEEL" in upper and "STAINLESS" not in upper and "ALUM" not in upper):
        mat = "MILD_STEEL_MAGNETIC"
    else:
        mat = "ALUMINIUM_NON_MAGNETIC"

    # Plate thickness (e.g. "3MM", "5MM", "6MM", "4MM")
    thk_match = re.search(r"\b([34568]|10)\s*MM\s*(?:THK|THICK|ALUM|PLATE)?", upper)
    plate_thk = float(thk_match.group(1)) if thk_match else 5.0

    # Entry orientation
    if "TOP" in upper or "OVERHEAD" in upper:
        orientation = "TOP_CABLE_ENTRY"
    else:
        orientation = "BOTTOM_CABLE_ENTRY"

    # Firestop transit method
    if any(k in upper for k in ["ROXTEC", "MCT", "MODULAR TRANSIT", "TRANSIT FRAME"]):
        firestop = "MODULAR_TRANSIT_FRAME"
    elif any(k in upper for k in ["PILLOW", "INTUMESCENT", "FIRESTOP MORTAR"]):
        firestop = "INTUMESCENT_FIRESTOP_PILLOWS"
    else:
        firestop = "CABLE_GLANDS_IP65"

    # IP rating (e.g. "IP54", "IP65", "IP56", "IP42")
    ip_match = re.search(r"\b(IP\s*\d{2})\b", upper)
    ip_val = ip_match.group(1).replace(" ", "") if ip_match else "IP54"

    # Eddy current slotting requirement
    if mat == "MILD_STEEL_MAGNETIC":
        eddy_slots = True
    else:
        eddy_slots = any(k in upper for k in ["SLOTTED", "EDDY CURRENT SLOTS", "SLOT BETWEEN"])

    return {
        "raw_text": clean,
        "gland_plate_material": mat,
        "plate_thickness_mm": plate_thk,
        "entry_orientation": orientation,
        "firestop_transit_type": firestop,
        "ip_rating": ip_val,
        "eddy_current_slots_required": eddy_slots,
    }


def evaluate_msb_gland_plate_firestop_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[MSBGlandPlateFirestopCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[MSBGlandPlateFirestopCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_msb_gland_plate_firestop_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            MSBGlandPlateFirestopCallout(
                raw_text=parsed["raw_text"],
                gland_plate_material=parsed["gland_plate_material"],
                plate_thickness_mm=parsed["plate_thickness_mm"],
                entry_orientation=parsed["entry_orientation"],
                firestop_transit_type=parsed["firestop_transit_type"],
                ip_rating=parsed["ip_rating"],
                eddy_current_slots_required=parsed["eddy_current_slots_required"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "electrical_standard": "ASNZS3000-ASNZS61439-MSB",
                },
            )
        )

    return results
