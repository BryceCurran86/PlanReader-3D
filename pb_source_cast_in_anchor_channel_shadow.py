"""
Source Cast-in Concrete Wall Anchor Channel Embed Cold-Formed Channel Shadow Authority.

Extracts and validates cast-in concrete anchor channels, cold-formed/hot-rolled profiles,
embedded stud anchors, foam fillers, and curtain wall/elevator structural attachments strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class CastInAnchorChannelCallout:
    raw_text: str
    channel_profile: str
    channel_series: Optional[str]
    channel_length_mm: Optional[float]
    anchor_stud_type: str
    material_finish: str
    filler_type: str
    structural_application: str
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


def parse_cast_in_anchor_channel_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ANCHOR CHANNEL",
        "CAST-IN CHANNEL",
        "CAST IN CHANNEL",
        "CHANNEL EMBED",
        "EMBEDDED CHANNEL",
        "HALFEN CHANNEL",
        "HALFEN",
        "HILTI HAC",
        "JORDAHL",
        "C-CHANNEL EMBED",
        "FACADE ANCHOR CHANNEL",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("CHANNEL" in upper or "EMBED" in upper)
        and ("CAST-IN" in upper or "CAST IN" in upper or "CURTAIN WALL BRACKET" in upper or "ELEVATOR GUIDE" in upper or "SLAB EDGE" in upper)
    )
    if not has_trigger:
        return None

    # Channel Profile
    if any(k in upper for k in ["TOOTHED", "SERRATED", "HZS", "HAC-T"]):
        channel_profile = "TOOTHED_SERRATED_CHANNEL"
    elif any(k in upper for k in ["HOT ROLLED", "HOT-ROLLED"]):
        channel_profile = "HOT_ROLLED_ANCHOR_CHANNEL"
    elif any(k in upper for k in ["SLAB EDGE", "EDGE OF SLAB", "FACIA CHANNEL"]):
        channel_profile = "SLAB_EDGE_FACIA_CHANNEL"
    elif any(k in upper for k in ["COLD FORMED", "COLD-FORMED", "HAC", "HTA"]):
        channel_profile = "COLD_FORMED_ANCHOR_CHANNEL"
    else:
        channel_profile = "GENERIC_ANCHOR_CHANNEL"

    # Channel Series (e.g. HAC-50, HTA-52/34, HAC-40, W40/22)
    series_m = re.search(r"\b(HAC-?[0-9]{2,3}(?:/[0-9]{2})?|HTA-?[0-9]{2,3}(?:/[0-9]{2})?|HZA-?[0-9]{2,3}(?:/[0-9]{2})?|W[0-9]{2}/[0-9]{2})\b", upper)
    channel_series = series_m.group(1) if series_m else None

    # Channel Length (mm)
    length_mm: Optional[float] = None
    len_m = (
        re.search(r"(\d{3,4})\s*MM\s*(?:LONG|LENGTH|LG)\b", upper)
        or re.search(r"L\s*=\s*(\d{3,4})\s*(?:MM)?\b", upper)
        or re.search(r"\b(\d{3,4})\s*MM\b", upper)
    )
    if len_m:
        length_mm = float(len_m.group(1))

    # Anchor Stud Type
    if any(k in upper for k in ["I-ANCHOR", "I-STUD", "FORGED I", "FORGED ANCHOR"]):
        stud_type = "I_STUD_FORGED_ANCHOR"
    elif any(k in upper for k in ["ROUND HEAD", "ROUND STUD", "HEADED STUD", "STUD ANCHOR", "WELDED STUD"]):
        stud_type = "ROUND_HEAD_STUD_ANCHOR"
    elif any(k in upper for k in ["END LUG", "LUG ANCHOR"]):
        stud_type = "END_LUG_ANCHOR"
    else:
        stud_type = "UNSPECIFIED"

    # Material & Finish
    if any(k in upper for k in ["HOT DIP GALV", "HDG", "GALVANIZED", "GALVANISED"]):
        material_finish = "HOT_DIP_GALVANIZED_STEEL"
    elif any(k in upper for k in ["STAINLESS", "A4", "316", "SS316"]):
        material_finish = "STAINLESS_STEEL_A4_316"
    elif any(k in upper for k in ["MILL FINISH", "BLACK STEEL", "UNCOATED"]):
        material_finish = "CARBON_STEEL_MILL_FINISH"
    else:
        material_finish = "UNSPECIFIED"

    # Filler Type
    if any(k in upper for k in ["COMB FOAM", "RIP-CORD", "RIP CORD"]):
        filler_type = "COMB_FOAM_FILLER"
    elif any(k in upper for k in ["CLOSED CELL FOAM", "FOAM STRIP", "FOAM FILLER"]):
        filler_type = "CLOSED_CELL_FOAM_STRIP"
    elif any(k in upper for k in ["PE FILLER", "PLASTIC FILLER"]):
        filler_type = "PE_PLASTIC_FILLER"
    else:
        filler_type = "UNSPECIFIED"

    # Structural Application
    if any(k in upper for k in ["CURTAIN WALL", "CW BRACKET", "FACADE BRACKET", "GLAZING BRACKET"]):
        app = "CURTAIN_WALL_BRACKET"
    elif any(k in upper for k in ["ELEVATOR", "LIFT GUIDE", "GUIDE RAIL", "SHAFT RAIL"]):
        app = "ELEVATOR_GUIDE_RAIL"
    elif any(k in upper for k in ["PRECAST", "CLADDING PANEL", "SPANDREL BRACKET"]):
        app = "PRECAST_CLADDING_FACADE"
    elif any(k in upper for k in ["PIPE SUPPORT", "CABLE TRAY", "TRAVERSE"]):
        app = "MEP_PIPE_SUPPORT"
    else:
        app = "GENERIC_EMBED_CONNECTION"

    return {
        "raw_text": clean,
        "channel_profile": channel_profile,
        "channel_series": channel_series,
        "channel_length_mm": length_mm,
        "anchor_stud_type": stud_type,
        "material_finish": material_finish,
        "filler_type": filler_type,
        "structural_application": app,
    }


def extract_cast_in_anchor_channel_candidates(
    callout_items: List[Tuple[str, Tuple[float, float]]],
    snap_tol: float = SNAP_TOLERANCE_PT,
    max_cap: int = MAX_SAFETY_CAP_PRIMITIVES,
) -> List[CastInAnchorChannelCallout]:
    results: List[CastInAnchorChannelCallout] = []
    for text, (x, y) in callout_items:
        if len(results) >= max_cap:
            break
        parsed = parse_cast_in_anchor_channel_callout(text)
        if parsed is None:
            continue
        snapped = snap_point(x, y, snap_tol)
        candidate = CastInAnchorChannelCallout(
            raw_text=parsed["raw_text"],
            channel_profile=parsed["channel_profile"],
            channel_series=parsed["channel_series"],
            channel_length_mm=parsed["channel_length_mm"],
            anchor_stud_type=parsed["anchor_stud_type"],
            material_finish=parsed["material_finish"],
            filler_type=parsed["filler_type"],
            structural_application=parsed["structural_application"],
            position=snapped,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "parsed_keys_count": len(parsed),
                "has_series": parsed["channel_series"] is not None,
                "has_length": parsed["channel_length_mm"] is not None,
                "has_studs": parsed["anchor_stud_type"] != "UNSPECIFIED",
            },
        )
        results.append(candidate)
    return results


def validate_cast_in_anchor_channel_system(
    candidates: List[CastInAnchorChannelCallout],
) -> Dict[str, Any]:
    total = len(candidates)
    profile_counts: Dict[str, int] = {}
    application_counts: Dict[str, int] = {}
    specified_series_count = 0
    specified_length_count = 0

    for c in candidates:
        profile_counts[c.channel_profile] = profile_counts.get(c.channel_profile, 0) + 1
        application_counts[c.structural_application] = application_counts.get(c.structural_application, 0) + 1
        if c.channel_series is not None:
            specified_series_count += 1
        if c.channel_length_mm is not None:
            specified_length_count += 1

    return {
        "total_candidates": total,
        "profile_counts": profile_counts,
        "application_counts": application_counts,
        "specified_series_count": specified_series_count,
        "specified_length_count": specified_length_count,
        "all_shadow_status": all(c.status == "CANDIDATE" for c in candidates),
        "all_projection_disallowed": all(not c.commercial_projection_allowed for c in candidates),
        "all_takeoff_disallowed": all(not c.takeoff_eligible for c in candidates),
    }
