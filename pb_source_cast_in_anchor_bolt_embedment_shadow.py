"""
Source Structural Steel Cast-In Anchor Bolt & Embedment Shadow Authority.

Extracts and validates cast-in anchor bolt patterns, bolt grades (Grade 8.8, Grade 4.6),
metric thread diameters (M16-M36), embedment depths (mm), and bottom plate/hook terminations strictly in shadow mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class CastInAnchorBoltEmbedmentCallout:
    raw_text: str
    bolt_grade: str
    thread_size: str
    bolt_count: int
    embedment_depth_mm: float
    anchor_termination: str
    projection_above_top_of_concrete_mm: float
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


def parse_cast_in_anchor_bolt_embedment_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "CAST-IN ANCHOR",
        "CAST IN ANCHOR",
        "HOLD DOWN BOLT",
        "HOLD-DOWN BOLT",
        "HD BOLT",
        "ANCHOR ROD",
        "EMBEDMENT DEPTH",
        "BASE PLATE BOLT",
        "ANCHOR BOLT",
    ]
    if not any(trig in upper for trig in triggers):
        return None

    # Bolt count: e.g. "4-M24", "4xM24", "4 HD BOLTS", "(4) M20"
    count = 4
    count_match = re.search(r"\b(\d+)\s*(?:-|X|\*|\s*(?:NO\.|NOS\.)?)\s*M\d+", upper)
    if count_match:
        count = int(count_match.group(1))
    else:
        num_match = re.search(r"\b(\d+)\s*(?:HD\s*BOLT|HOLD\s*DOWN|ANCHOR)", upper)
        if num_match:
            count = int(num_match.group(1))

    # Metric thread size: M16, M20, M24, M30, M36
    m_match = re.search(r"(?:^|[^A-LN-Z0-9]|(?<=\d)[xX])M(\d{2})\b", upper)
    thread = f"M{m_match.group(1)}" if m_match else "M24"

    # Bolt Grade
    if "8.8" in upper or "GRADE 8" in upper:
        grade = "GRADE_8_8_HIGH_TENSILE"
    elif "4.6" in upper or "GRADE 4" in upper:
        grade = "GRADE_4_6_COMMERCIAL"
    elif "SS" in upper or "STAINLESS" in upper or "316" in upper:
        grade = "STAINLESS_STEEL_A4_70"
    else:
        grade = "GRADE_8_8_HIGH_TENSILE"

    # Embedment depth mm
    embed_mm = 0.0
    embed_match = re.search(r"(\d{3,4})\s*(?:MM)?\s*(?:EMBED|EMBEDMENT|MIN\s*EMBED)", upper)
    if embed_match:
        embed_mm = float(embed_match.group(1))
    else:
        depth_match = re.search(r"(?:EMBED|EMBEDMENT|DEPTH)\s*[:=]?\s*(\d{3,4})", upper)
        if depth_match:
            embed_mm = float(depth_match.group(1))
        else:
            embed_mm = 450.0  # standard typical structural steel column HD bolt embedment

    # Anchor termination
    if "COGGED" in upper or "L-BOLT" in upper or "L-HOOK" in upper:
        term = "COGGED_L_HOOK"
    elif "J-BOLT" in upper or "J-HOOK" in upper:
        term = "J_BOLT_HOOK"
    elif "PLATE WASHER" in upper or "BOTTOM NUT" in upper or "ANCHOR PLATE" in upper:
        term = "HEAVY_HEX_NUT_AND_SQUARE_PLATE_WASHER"
    else:
        term = "HEAVY_HEX_NUT_AND_SQUARE_PLATE_WASHER"

    # Projection above top of concrete mm
    proj_mm = 100.0
    proj_match = re.search(r"(\d{2,3})\s*(?:MM)?\s*(?:PROJ|PROJECTION)", upper)
    if proj_match:
        proj_mm = float(proj_match.group(1))

    return {
        "bolt_grade": grade,
        "thread_size": thread,
        "bolt_count": count,
        "embedment_depth_mm": embed_mm,
        "anchor_termination": term,
        "projection_above_top_of_concrete_mm": proj_mm,
    }


class SourceCastInAnchorBoltEmbedmentShadowAuthority:
    """Authority for extracting and validating cast-in anchor bolt embedment assemblies in shadow mode."""

    def __init__(self, snap_tolerance: float = SNAP_TOLERANCE_PT):
        self.snap_tolerance = snap_tolerance

    def process_callouts(
        self, raw_callouts: List[Tuple[str, Tuple[float, float]]]
    ) -> List[CastInAnchorBoltEmbedmentCallout]:
        if len(raw_callouts) > MAX_SAFETY_CAP_PRIMITIVES:
            raw_callouts = raw_callouts[:MAX_SAFETY_CAP_PRIMITIVES]

        results: List[CastInAnchorBoltEmbedmentCallout] = []
        seen_keys = set()

        for text, raw_pos in raw_callouts:
            parsed = parse_cast_in_anchor_bolt_embedment_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(raw_pos[0], raw_pos[1], self.snap_tolerance)
            dedup_key = (parsed["thread_size"], parsed["bolt_count"], snapped_pos)
            if dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)

            callout = CastInAnchorBoltEmbedmentCallout(
                raw_text=text,
                bolt_grade=parsed["bolt_grade"],
                thread_size=parsed["thread_size"],
                bolt_count=parsed["bolt_count"],
                embedment_depth_mm=parsed["embedment_depth_mm"],
                anchor_termination=parsed["anchor_termination"],
                projection_above_top_of_concrete_mm=parsed["projection_above_top_of_concrete_mm"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            results.append(callout)

        return results
