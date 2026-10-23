"""
Source Fire Hose Reel Cabinet Recessed Thermally Insulated Door Shadow Authority.

Extracts and validates fire hose reel (FHR) cabinets, recessed/semi-recessed/surface mountings,
thermally insulated doors, fire resistance levels (FRL), hose lengths, and cabinet dimensions
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class FhrRecessedCabinetCallout:
    raw_text: str
    mounting: str
    door_type: str
    insulation_core: str
    frl_minutes: int
    hose_length_m: float
    dimensions_mm: Tuple[float, float, float]
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


def parse_fhr_recessed_cabinet_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "FHR",
        "FIRE HOSE REEL",
        "HOSE REEL",
        "F.H.R.",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Mounting type - evaluate SEMI-RECESSED before RECESSED
    if any(k in upper for k in ["SEMI-RECESSED", "SEMI RECESSED"]):
        mounting = "SEMI_RECESSED"
    elif any(k in upper for k in ["RECESSED", "FLUSH RECESSED", "IN-WALL", "CAVITY RECESSED"]):
        mounting = "FULLY_RECESSED"
    elif any(k in upper for k in ["SURFACE MOUNTED", "SURFACE"]):
        mounting = "SURFACE_MOUNTED"
    else:
        mounting = "FULLY_RECESSED"  # standard architectural specification default for corridors

    # Insulation core - evaluate negation first
    if any(k in upper for k in ["UNINSULATED", "WITHOUT INSULATION", "NO INSULATION"]):
        insulation = "NONE"
    elif any(k in upper for k in ["ROCKWOOL", "MINERAL WOOL", "MINERAL FIBER", "MINERAL FIBRE"]):
        insulation = "ROCKWOOL_MINERAL_FIBER"
    elif "CERAMIC" in upper:
        insulation = "CERAMIC_BLANKET"
    elif any(k in upper for k in ["INSULATED", "THERMAL CORE", "INSULATION CORE"]):
        insulation = "THERMAL_INSULATED_CORE"
    else:
        insulation = "NONE"

    # Door type
    if any(k in upper for k in ["BREAK GLASS", "BREAK-GLASS"]):
        door_type = "BREAK_GLASS_DOOR"
    elif any(k in upper for k in ["GLAZED", "GLASS VISION", "VISION PANEL", "ACRYLIC WINDOW"]):
        door_type = "GLAZED_DOOR"
    elif any(k in upper for k in ["STAINLESS", "SS DOOR"]):
        door_type = "STAINLESS_STEEL_DOOR"
    elif any(k in upper for k in ["SOLID FLUSH", "FLUSH METAL", "STEEL FLUSH", "INSULATED FLUSH"]):
        door_type = "SOLID_FLUSH_DOOR"
    else:
        door_type = "SOLID_FLUSH_DOOR"

    # Fire resistance level FRL (minutes)
    frl_match = re.search(r"-\s*/\s*(\d+)\s*/\s*(\d+)", upper)
    if frl_match:
        frl_minutes = int(frl_match.group(2))
    else:
        frl_hr_match = re.search(r"(\d+)\s*(?:HR|HOUR)\s*(?:FIRE|FRL)", upper)
        if frl_hr_match:
            frl_minutes = int(frl_hr_match.group(1)) * 60
        else:
            frl_min_match = re.search(r"(\d{2,3})\s*(?:MIN|MINUTES)\s*(?:FIRE|FRL)", upper)
            if frl_min_match:
                frl_minutes = int(frl_min_match.group(1))
            else:
                frl_minutes = 0

    # Hose reel length (m)
    hose_match = re.search(r"(\d{2})\s*(?:M|METRE|METER)\s*(?:X\s*\d+\s*MM)?\s*(?:HOSE|FHR)?", upper)
    if hose_match and float(hose_match.group(1)) in (30.0, 36.0, 45.0, 50.0):
        hose_length_m = float(hose_match.group(1))
    else:
        hose_length_m = 36.0  # standard BCA/NCC compliance default

    # Cabinet dimensions (width, height, depth)
    dim_match = re.search(r"(\d{3,4})\s*(?:X|\*)\s*(\d{3,4})\s*(?:X|\*)\s*(\d{2,4})\s*(?:MM)?", upper)
    if dim_match:
        dims = (
            float(dim_match.group(1)),
            float(dim_match.group(2)),
            float(dim_match.group(3)),
        )
    else:
        dims = (800.0, 1050.0, 300.0)

    return {
        "raw_text": clean,
        "mounting": mounting,
        "door_type": door_type,
        "insulation_core": insulation,
        "frl_minutes": frl_minutes,
        "hose_length_m": hose_length_m,
        "dimensions_mm": dims,
    }


class SourceFhrRecessedCabinetShadowAuthority:
    """Authority for fire hose reel recessed cabinets in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[FhrRecessedCabinetCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[FhrRecessedCabinetCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[FhrRecessedCabinetCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_fhr_recessed_cabinet_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = FhrRecessedCabinetCallout(
                raw_text=parsed["raw_text"],
                mounting=parsed["mounting"],
                door_type=parsed["door_type"],
                insulation_core=parsed["insulation_core"],
                frl_minutes=parsed["frl_minutes"],
                hose_length_m=parsed["hose_length_m"],
                dimensions_mm=parsed["dimensions_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
