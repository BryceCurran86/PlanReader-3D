"""
Source Acoustic Gypsum Plasterboard Resilient Mount Wall Furring Channel Shadow Authority.

Extracts and validates acoustic wall isolation clips, steel furring channels,
cavity depths, insulation batts, and multi-layer plasterboard linings strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class ResilientMountFurringChannelCallout:
    raw_text: str
    mount_type: str
    furring_channel_depth_mm: float
    channel_spacing_cts_mm: float
    cavity_depth_mm: float
    insulation_type: str
    lining_configuration: str
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


def parse_resilient_mount_furring_channel_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "RESILIENT MOUNT",
        "RESILMOUNT",
        "ACOUSTIC CLIP",
        "FURRING CHANNEL CLIP",
        "ISOLATION CLIP",
        "ACOUSTIC WALL FURRING",
        "RESILIENT WALL ISOLATOR",
        "HAT CHANNEL CLIP",
        "SOUND ISOLATION CLIP",
        "RESILIENT CHANNEL",
        "ACOUSTIC FURRING",
        "SPRING MOUNT",
        "WALL ISOLATOR",
        "HAT TRACK",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Mount type
    if "SPRING" in upper:
        mount = "STEEL_SPRING_MOUNT"
    elif "RESILIENT CHANNEL" in upper or "RC-1" in upper or "RC1" in upper:
        mount = "DIRECT_RESILIENT_CHANNEL"
    else:
        mount = "THERMOPLASTIC_RUBBER_CLIP"

    # Furring channel depth (16mm or 28mm)
    depth_match = re.search(r"\b(16|28)\s*MM\s*(?:FURRING|HAT|CHANNEL)?\b", upper)
    if depth_match:
        furring_depth = float(depth_match.group(1))
    elif "16MM" in upper:
        furring_depth = 16.0
    else:
        furring_depth = 28.0

    # Channel spacing centers (e.g. "450MM CTS", "600MM CTS", "600 CTS", "450 CTS")
    cts_match = re.search(r"\b(\d{3})\s*(?:MM)?\s*(?:CTS|CENTRES|CENTERS|C/C)\b", upper)
    spacing_cts = float(cts_match.group(1)) if cts_match else 600.0

    # Cavity depth (e.g. "20MM CAVITY", "25MM CAVITY", "50MM CAVITY")
    cav_match = re.search(r"\b(\d{2,3})\s*MM\s*CAVITY\b", upper)
    cavity_depth = float(cav_match.group(1)) if cav_match else 25.0

    # Insulation type
    if "ROCKWOOL" in upper or "MINERAL" in upper:
        insul = "ROCKWOOL_ACOUSTIC_BATTS"
    elif "POLYESTER" in upper:
        insul = "POLYESTER_ACOUSTIC_BATTS"
    else:
        insul = "GLASSWOOL_ACOUSTIC_BATTS"

    # Plasterboard lining configuration
    lining_match = re.search(r"\b([123])\s*[xX]\s*(\d{2})\s*MM\s*(SOUNDSTOP|FYRCHEK|PLASTERBOARD|GYPROCK|BOARD)?\b", upper)
    if lining_match:
        qty = lining_match.group(1)
        thk = lining_match.group(2)
        prod = lining_match.group(3) or "ACOUSTIC_BOARD"
        lining = f"{qty}x{thk}mm {prod}"
    elif "SOUNDSTOP" in upper or "ACOUSTIC BOARD" in upper:
        lining = "2x13mm SOUNDSTOP"
    elif "FYRCHEK" in upper or "FIRE BOARD" in upper:
        lining = "2x16mm FYRCHEK"
    else:
        lining = "2x13mm ACOUSTIC_PLASTERBOARD"

    return {
        "raw_text": clean,
        "mount_type": mount,
        "furring_channel_depth_mm": furring_depth,
        "channel_spacing_cts_mm": spacing_cts,
        "cavity_depth_mm": cavity_depth,
        "insulation_type": insul,
        "lining_configuration": lining,
    }


def evaluate_resilient_mount_furring_channel_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[ResilientMountFurringChannelCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[ResilientMountFurringChannelCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_resilient_mount_furring_channel_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            ResilientMountFurringChannelCallout(
                raw_text=parsed["raw_text"],
                mount_type=parsed["mount_type"],
                furring_channel_depth_mm=parsed["furring_channel_depth_mm"],
                channel_spacing_cts_mm=parsed["channel_spacing_cts_mm"],
                cavity_depth_mm=parsed["cavity_depth_mm"],
                insulation_type=parsed["insulation_type"],
                lining_configuration=parsed["lining_configuration"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "acoustic_standard": "NCC-BCA-ACOUSTIC-RW-CTR",
                },
            )
        )

    return results
