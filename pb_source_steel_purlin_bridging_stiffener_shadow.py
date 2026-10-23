"""
Source Structural Steel Purlin Bridging Hook Bolt & C-Section Stiffener Shadow Authority.

Extracts and validates cold-formed purlin and girt bridging channels, hook bolts,
purlin section series, row configurations, and web stiffeners strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SteelPurlinBridgingStiffenerCallout:
    raw_text: str
    bridging_system: str
    hook_bolt_size: str
    purlin_series: str
    row_configuration: str
    web_stiffener_required: bool
    finish_coating: str
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


def parse_steel_purlin_bridging_stiffener_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "PURLIN BRIDGING",
        "GIRT BRIDGING",
        "BRIDGING HOOK BOLT",
        "BRIDGING SYSTEM",
        "PURLIN STRUT",
        "WEB STIFFENER",
        "FASCIA BRIDGING",
        "CONTINUOUS BRIDGING",
        "BRIDGING CHANNEL",
        "ROOF BRIDGING",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Bridging system
    if any(k in upper for k in ["EXPANSION", "SLOTTED"]):
        system = "EXPANSION_BRIDGING"
    elif any(k in upper for k in ["SOLID STRUT", "TUBULAR", "PIPE"]):
        system = "SOLID_STRUT_BRIDGING"
    else:
        system = "HOOK_BOLT_CHANNEL_BRIDGING"

    # Hook bolt size (e.g. "M12", "M16", "M10", "12MM")
    bolt_match = re.search(r"\b(M10|M12|M16)\b", upper)
    if bolt_match:
        bolt_size = bolt_match.group(1)
    elif "16MM" in upper:
        bolt_size = "M16"
    elif "10MM" in upper:
        bolt_size = "M10"
    else:
        bolt_size = "M12"

    # Purlin series (e.g. "C150", "C200", "Z200", "Z250", "C300", "Z300", "Z150")
    purlin_match = re.search(r"\b([CZ]\s*\d{3})\b", upper)
    if purlin_match:
        purlin_sec = purlin_match.group(1).replace(" ", "")
    elif "250" in upper:
        purlin_sec = "Z250"
    elif "150" in upper:
        purlin_sec = "Z150"
    elif "300" in upper:
        purlin_sec = "Z300"
    else:
        purlin_sec = "Z200"

    # Row configuration
    if any(k in upper for k in ["2 ROW", "TWO ROW", "DOUBLE ROW", "THIRD POINT"]):
        row_cfg = "2_ROWS_THIRD_POINTS"
    elif any(k in upper for k in ["3 ROW", "THREE ROW", "QUARTER POINT"]):
        row_cfg = "3_ROWS_QUARTER_POINTS"
    else:
        row_cfg = "1_ROW_MIDSPAN"

    # Web stiffener plate
    has_stiffener = any(k in upper for k in ["WEB STIFFENER", "STIFFENER PLATE", "CLEAT STIFFENER"])
    if "NO STIFFENER" in upper or "WITHOUT STIFFENER" in upper:
        has_stiffener = False

    # Finish coating
    if "HOT DIP" in upper or "HDG" in upper:
        finish = "HOT_DIP_GALVANISED"
    elif "ZINC" in upper:
        finish = "ELECTRO_ZINC_PLATED"
    else:
        finish = "GALVABOND_Z275"

    return {
        "raw_text": clean,
        "bridging_system": system,
        "hook_bolt_size": bolt_size,
        "purlin_series": purlin_sec,
        "row_configuration": row_cfg,
        "web_stiffener_required": has_stiffener,
        "finish_coating": finish,
    }


def evaluate_steel_purlin_bridging_stiffener_shadow(
    callouts: List[Any],
    positions: Optional[List[Tuple[float, float]]] = None,
    snap_tol: float = SNAP_TOLERANCE_PT,
) -> List[SteelPurlinBridgingStiffenerCallout]:
    if len(callouts) > MAX_SAFETY_CAP_PRIMITIVES:
        callouts = callouts[:MAX_SAFETY_CAP_PRIMITIVES]

    results: List[SteelPurlinBridgingStiffenerCallout] = []

    for idx, item in enumerate(callouts):
        if isinstance(item, dict):
            text = item.get("text", "")
            pos = item.get("position", (0.0, 0.0))
        elif isinstance(item, str):
            text = item
            pos = positions[idx] if (positions and idx < len(positions)) else (0.0, 0.0)
        else:
            continue

        parsed = parse_steel_purlin_bridging_stiffener_callout(text)
        if not parsed:
            continue

        snapped = snap_point(pos[0], pos[1], snap_tol=snap_tol)

        results.append(
            SteelPurlinBridgingStiffenerCallout(
                raw_text=parsed["raw_text"],
                bridging_system=parsed["bridging_system"],
                hook_bolt_size=parsed["hook_bolt_size"],
                purlin_series=parsed["purlin_series"],
                row_configuration=parsed["row_configuration"],
                web_stiffener_required=parsed["web_stiffener_required"],
                finish_coating=parsed["finish_coating"],
                position=snapped,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={
                    "primitive_index": idx,
                    "snap_tolerance_pt": snap_tol,
                    "bridging_standard": "ASNZS4600-PURLIN-BRIDGING",
                },
            )
        )

    return results
