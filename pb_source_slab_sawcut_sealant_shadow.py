"""
Source Industrial Concrete Slab Sawn Contraction Joint Polyurethane Sealant Shadow Authority.

Extracts and validates concrete slab sawcut crack control joints, saw depths,
sealant materials (semi-rigid polyurea vs polyurethane), and backer rod details strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SlabSawcutSealantCallout:
    raw_text: str
    sawcut_width_mm: float
    depth_specification: str
    depth_numeric_mm: float
    sealant_type: str
    backer_rod_required: bool
    beveled_arris: bool
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


def parse_slab_sawcut_sealant_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SAWN JOINT",
        "SAWCUT JOINT",
        "CONTRACTION JOINT SEALANT",
        "SLAB SAWCUT",
        "SOFF-CUT",
        "EARLY ENTRY SAWCUT",
        "CONTROL JOINT SEALANT",
        "POLYURETHANE JOINT SEALANT",
        "POLYUREA JOINT SEALANT",
        "SAWCUT SEALANT",
        "SAWCUT CRACK CONTROL",
        "SAWN CONTRACTION JOINT",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Sawcut width (e.g. "3MM SAWCUT", "4MM WIDE", "5MM SAWN JOINT", "6MM JOINT")
    width_match = re.search(r"\b([345678]|10)\s*MM\s*(?:WIDE|SAWCUT|SAWN|WIDTH)?\b", upper)
    saw_width = float(width_match.group(1)) if width_match else 4.0

    # Depth specification
    if any(k in upper for k in ["D/4", "T/4", "1/4 SLAB", "ONE QUARTER"]):
        depth_spec = "DEPTH_D_OVER_4"
        depth_val = 50.0
    elif any(k in upper for k in ["D/3", "T/3", "1/3 SLAB", "ONE THIRD"]):
        depth_spec = "DEPTH_D_OVER_3"
        depth_val = 65.0
    else:
        num_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:DEEP|DEPTH)", upper)
        if num_match:
            depth_val = float(num_match.group(1))
            depth_spec = f"DEPTH_{int(depth_val)}MM"
        else:
            depth_spec = "DEPTH_D_OVER_4"
            depth_val = 50.0

    # Sealant material
    if "POLYUREA" in upper or "SEMI-RIGID" in upper or "SHORE A" in upper or "FORKLIFT" in upper:
        sealant = "SEMI_RIGID_POLYUREA"
    elif "SILICONE" in upper:
        sealant = "SILICONE_SEALANT"
    else:
        sealant = "ELASTOMERIC_POLYURETHANE"

    # Backer rod required
    if "WITHOUT BACKER" in upper or "NO BACKER" in upper:
        backer = False
    elif any(k in upper for k in ["BACKER ROD", "PE ROD", "FOAM ROD", "CLOSED CELL"]):
        backer = True
    elif sealant == "SEMI_RIGID_POLYUREA":
        backer = False  # Polyurea is typically installed full depth to support edges
    else:
        backer = True

    # Beveled arris edge
    arris = any(k in upper for k in ["CHAMFER", "BEVEL", "ARIS", "ROUNDED EDGE"])

    return {
        "raw_text": clean,
        "sawcut_width_mm": saw_width,
        "depth_specification": depth_spec,
        "depth_numeric_mm": depth_val,
        "sealant_type": sealant,
        "backer_rod_required": backer,
        "beveled_arris": arris,
    }


def evaluate_slab_sawcut_sealant_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[SlabSawcutSealantCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[SlabSawcutSealantCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_slab_sawcut_sealant_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            SlabSawcutSealantCallout(
                raw_text=parsed["raw_text"],
                sawcut_width_mm=parsed["sawcut_width_mm"],
                depth_specification=parsed["depth_specification"],
                depth_numeric_mm=parsed["depth_numeric_mm"],
                sealant_type=parsed["sealant_type"],
                backer_rod_required=parsed["backer_rod_required"],
                beveled_arris=parsed["beveled_arris"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "sawcut_standard": "ACI302.1R-ACI360R-SAWCUTS",
                },
            )
        )

    return results
