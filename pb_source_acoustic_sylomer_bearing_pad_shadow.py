"""
Source Acoustic Floating Floor Sylomer Isolation Bearing Pad Shadow Authority.

Extracts and validates acoustic floating floor elastomer pads (Sylomer / Sylodyn), material grades,
static load capacities (N/mm²), natural frequencies (Hz), pad dimensions, and perimeter flanking isolation
strictly in shadow candidate mode.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class AcousticSylomerBearingPadCallout:
    raw_text: str
    sylomer_grade: str
    static_range_n_per_mm2: float
    pad_thickness_mm: float
    pad_dimensions_mm: Tuple[float, float]
    natural_frequency_hz: float
    air_cavity_depth_mm: float
    perimeter_isolation: str
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


def parse_acoustic_sylomer_bearing_pad_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "SYLOMER",
        "SYLODYN",
        "FLOATING FLOOR",
        "FLOATING SLAB",
        "ACOUSTIC BEARING PAD",
        "ISOLATION BEARING PAD",
        "RESILIENT FLOOR PAD",
    ]
    has_trigger = any(trig in upper for trig in triggers) or (
        ("ACOUSTIC" in upper or "ISOLATION" in upper) and ("BEARING" in upper or "PAD" in upper or "FLOOR" in upper)
    )
    if not has_trigger:
        return None

    # Sylomer grade and static load mapping (N/mm²)
    if "SYLODYN" in upper:
        grade = "SYLODYN_NC"
        static_n = 1.200
    elif re.search(r"\bSR\s*11\b", upper):
        grade = "SYLOMER_SR11"
        static_n = 0.011
    elif re.search(r"\bSR\s*18\b", upper):
        grade = "SYLOMER_SR18"
        static_n = 0.018
    elif re.search(r"\bSR\s*28\b", upper):
        grade = "SYLOMER_SR28"
        static_n = 0.028
    elif re.search(r"\bSR\s*42\b", upper):
        grade = "SYLOMER_SR42"
        static_n = 0.042
    elif re.search(r"\bSR\s*110\b", upper):
        grade = "SYLOMER_SR110"
        static_n = 0.110
    elif re.search(r"\bSR\s*220\b", upper):
        grade = "SYLOMER_SR220"
        static_n = 0.220
    elif re.search(r"\bSR\s*450\b", upper):
        grade = "SYLOMER_SR450"
        static_n = 0.450
    elif re.search(r"\bSR\s*850\b", upper):
        grade = "SYLOMER_SR850"
        static_n = 0.850
    elif re.search(r"\bSR\s*55\b", upper):
        grade = "SYLOMER_SR55"
        static_n = 0.055
    else:
        grade = "SYLOMER_SR55"
        static_n = 0.055

    # Pad thickness (mm) - require THICK / THICKNESS keyword or known thickness indicator
    th_match = re.search(r"(\d+(?:\.\d+)?)\s*MM\s*(?:THICK|THICKNESS)", upper)
    if not th_match:
        th_match = re.search(r"(?:THICKNESS|DEPTH)\s*(?:OF|:)?\s*(\d+(?:\.\d+)?)\s*MM", upper)
    if not th_match:
        # Check standard Sylomer thicknesses if explicitly formatted like '25MM PAD' or '12.5MM PAD'
        th_match = re.search(r"\b(12\.5|25|50)\s*MM\s*(?:PAD|ELASTOMER|BEARING)", upper)

    if th_match:
        pad_th = float(th_match.group(1))
    else:
        pad_th = 25.0  # standard engineering default for floating floor pads

    # Pad dimensions (width, length)
    dim_match = re.search(r"(\d{2,3})\s*(?:X|\*)\s*(\d{2,3})\s*(?:MM)?", upper)
    if dim_match:
        dims = (float(dim_match.group(1)), float(dim_match.group(2)))
    else:
        strip_match = re.search(r"(\d{2,3})\s*MM\s*STRIP", upper)
        if strip_match:
            dims = (float(strip_match.group(1)), 1000.0)
        else:
            dims = (100.0, 100.0)

    # Natural frequency (Hz)
    hz_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:HZ|HERTZ)", upper)
    if hz_match:
        fn_hz = float(hz_match.group(1))
    else:
        fn_hz = 8.0  # typical low-frequency target for floating concrete slabs

    # Air cavity depth (mm)
    cav_match = re.search(r"(\d{2,3})\s*(?:MM)?\s*(?:AIR\s*CAVITY|AIR\s*GAP|AIR\s*VOID|VOID|CAVITY)", upper)
    if cav_match:
        cav_depth = float(cav_match.group(1))
    else:
        cav_depth = 50.0  # standard air void

    # Perimeter isolation - evaluate negation first
    if any(k in upper for k in ["WITHOUT PERIMETER", "NO PERIMETER", "WITHOUT FLANKING"]):
        perim = "NONE"
    elif any(k in upper for k in ["PERIMETER", "FLANKING STRIP", "EDGE STRIP", "PERIMETER STRIP"]):
        perim = "PERIMETER_ISOLATION_STRIP"
    elif any(k in upper for k in ["ACOUSTIC CAULK", "MASTIC", "RESILIENT SEALANT"]):
        perim = "RESILIENT_CAULKING"
    else:
        perim = "PERIMETER_ISOLATION_STRIP"

    return {
        "raw_text": clean,
        "sylomer_grade": grade,
        "static_range_n_per_mm2": static_n,
        "pad_thickness_mm": pad_th,
        "pad_dimensions_mm": dims,
        "natural_frequency_hz": fn_hz,
        "air_cavity_depth_mm": cav_depth,
        "perimeter_isolation": perim,
    }


class SourceAcousticSylomerBearingPadShadowAuthority:
    """Authority for acoustic floating floor Sylomer isolation bearing pads in shadow mode."""

    def __init__(self, snap_tolerance_pt: float = SNAP_TOLERANCE_PT) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self.callouts: List[AcousticSylomerBearingPadCallout] = []

    def process_raw_candidates(
        self, candidates: List[Tuple[str, Tuple[float, float]]]
    ) -> List[AcousticSylomerBearingPadCallout]:
        """Process raw candidates subject to safety cap and snapping."""
        results: List[AcousticSylomerBearingPadCallout] = []
        truncated = candidates[:MAX_SAFETY_CAP_PRIMITIVES]

        for text, (x, y) in truncated:
            parsed = parse_acoustic_sylomer_bearing_pad_callout(text)
            if not parsed:
                continue

            snapped_pos = snap_point(x, y, self.snap_tolerance_pt)
            callout = AcousticSylomerBearingPadCallout(
                raw_text=parsed["raw_text"],
                sylomer_grade=parsed["sylomer_grade"],
                static_range_n_per_mm2=parsed["static_range_n_per_mm2"],
                pad_thickness_mm=parsed["pad_thickness_mm"],
                pad_dimensions_mm=parsed["pad_dimensions_mm"],
                natural_frequency_hz=parsed["natural_frequency_hz"],
                air_cavity_depth_mm=parsed["air_cavity_depth_mm"],
                perimeter_isolation=parsed["perimeter_isolation"],
                position=snapped_pos,
                status="CANDIDATE",
                commercial_projection_allowed=False,
                takeoff_eligible=False,
                metadata={"snap_tolerance_pt": self.snap_tolerance_pt},
            )
            results.append(callout)

        self.callouts = results
        return results
