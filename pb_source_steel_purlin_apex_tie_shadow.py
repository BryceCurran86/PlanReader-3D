"""
Source Structural Steel Purlin Apex Tie & Ridge Cleat Shadow Authority.

Extracts and validates cold-formed purlin apex ties, ridge cleat brackets, roof pitch angles,
purlin section sizes (C/Z), bolt specifications, and galvanized finishes strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class SteelPurlinApexTieCallout:
    raw_text: str
    purlin_section: str
    apex_tie_type: str
    ridge_cleat_gauge_mm: float
    bolt_specification: str
    pitch_degrees: float
    coating_finish: str
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


def parse_steel_purlin_apex_tie_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "APEX TIE",
        "RIDGE CLEAT",
        "APEX BRACKET",
        "RIDGE PURLIN",
        "RIDGE STRAP",
        "PURLIN APEX",
        "ROOF APEX",
        "APEX PURLIN",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("APEX" in upper or "RIDGE" in upper) and ("PURLIN" in upper or "CLEAT" in upper)
    )
    if not has_trigger:
        return None

    # Purlin section size (e.g. C20015, Z20020, C15015)
    sec_match = re.search(r"\b([CZ]\d{5}|[CZ]\d{3})\b", upper)
    if sec_match:
        section = sec_match.group(1)
    else:
        sec_alt = re.search(r"\b(\d{3}[CZ]\d{2})\b", upper)
        if sec_alt:
            section = sec_alt.group(1)
        else:
            section = "C20015"  # standard default

    # Apex tie type
    if any(k in upper for k in ["ANGLE", "STRUT", "RIDGE STRUT"]):
        tie_type = "ANGLE_APEX_STRUT"
    elif any(k in upper for k in ["ROD", "SAG ROD", "ROUND BAR"]):
        tie_type = "SOLID_ROD_APEX_TIE"
    elif any(k in upper for k in ["CHANNEL", "C-SECTION"]):
        tie_type = "CHANNEL_RIDGE_BRACE"
    elif any(k in upper for k in ["STRAP", "FLAT STRAP", "TIE STRAP"]):
        tie_type = "STRAP_APEX_TIE"
    else:
        tie_type = "STRAP_APEX_TIE"

    # Ridge cleat gauge / thickness (mm)
    cleat_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:MM)?\s*(?:RIDGE\s*CLEAT|CLEAT|BRACKET|GAUGE|PLATE|THICK)", upper)
    if cleat_match:
        cleat_mm = float(cleat_match.group(1))
    else:
        alt_th = re.search(r"(\d+(?:\.\d+)?)\s*MM\b", upper)
        if alt_th and float(alt_th.group(1)) in (2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0):
            cleat_mm = float(alt_th.group(1))
        else:
            cleat_mm = 3.0  # standard engineering default for ridge cleats

    # Bolt fastener specification
    bolt_match = re.search(r"(\d+\s*-\s*M\d+(?:\s+[\d\./A-Z]+)?|M\d+(?:\s*(?:GR|GRADE)?\s*[\d\./A-Z]+)?)", upper)
    if bolt_match and "M" in bolt_match.group(1):
        bolt_spec = bolt_match.group(1)
    else:
        bolt_spec = "M12 GR4.6"

    # Roof pitch degrees
    pitch_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:°|DEG|DEGREES?)", upper)
    if pitch_match:
        pitch_deg = float(pitch_match.group(1))
    else:
        pitch_deg = 5.0  # typical low-pitch portal frame roof

    # Coating / finish
    if any(k in upper for k in ["HOT DIP", "HDG", "HOT-DIP"]):
        finish = "HOT_DIP_GALVANIZED"
    elif any(k in upper for k in ["ZINCALUME", "ALUZINC"]):
        finish = "ZINCALUME"
    elif any(k in upper for k in ["Z450", "GALVABOND", "PRE-GALV"]):
        finish = "GALVABOND_Z450"
    else:
        finish = "GALVABOND_Z450"

    return {
        "raw_text": clean,
        "purlin_section": section,
        "apex_tie_type": tie_type,
        "ridge_cleat_gauge_mm": cleat_mm,
        "bolt_specification": bolt_spec,
        "pitch_degrees": pitch_deg,
        "coating_finish": finish,
    }


class SourceSteelPurlinApexTieShadowAuthority:
    """Authority for structural steel purlin apex ties in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[SteelPurlinApexTieCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[SteelPurlinApexTieCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[SteelPurlinApexTieCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_steel_purlin_apex_tie_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = SteelPurlinApexTieCallout(
                raw_text=parsed["raw_text"],
                purlin_section=parsed["purlin_section"],
                apex_tie_type=parsed["apex_tie_type"],
                ridge_cleat_gauge_mm=parsed["ridge_cleat_gauge_mm"],
                bolt_specification=parsed["bolt_specification"],
                pitch_degrees=parsed["pitch_degrees"],
                coating_finish=parsed["coating_finish"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
