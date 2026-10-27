"""
pb_source_louvered_sunshade_aerofoil_cantilever_shadow.py

Shadow candidate authority for architectural louvered sunshades, horizontal aerofoil
cantilevers, vertical solar fins, motorized tracking louvers, and outrigger brackets.

STRICT CONTRACT:
- Candidate authority only: status="CANDIDATE", commercial_projection_allowed=False, takeoff_eligible=False.
- Deterministic 2D grid snapping (SNAP_TOLERANCE_PT = 2.5 pt).
- Primitive safety cap: MAX_SAFETY_CAP_PRIMITIVES = 20_000.
"""

from dataclasses import dataclass
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

SNAP_TOLERANCE_PT: float = 2.5
MAX_SAFETY_CAP_PRIMITIVES: int = 20_000


@dataclass(frozen=True)
class LouveredSunshadeCandidate:
    candidate_id: str
    element_type: str  # HORIZONTAL_CANTILEVER_SUNSHADE, VERTICAL_AEROFOIL_SOLAR_FIN, MOTORIZED_OPERABLE_SOLAR_LOUVER, CONTINUOUS_LINEAR_FACADE_LOUVER, STRUCTURAL_OUTRIGGER_BRACKET
    blade_width_mm: int
    projection_outreach_mm: int
    blade_tilt_angle_deg: int
    blade_profile: str  # AEROFOIL_ELLIPTICAL, RECTANGULAR_BOX, Z_BLADE, C_CHANNEL
    finish_type: str  # POWDER_COATED_DURATEC, ANODIZED_25UM, TIMBER_GRAIN_SUBLIMATION
    is_motorized: bool
    tag: Optional[str]
    raw_annotation: str
    snapped_grid_pt: Tuple[float, float]
    source_primitive_id: str
    confidence: float
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False


def snap_point_to_grid(x: float, y: float, tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    snapped_x = round(x / tolerance) * tolerance
    snapped_y = round(y / tolerance) * tolerance
    return (round(snapped_x, 4), round(snapped_y, 4))


def extract_louvered_sunshade_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[LouveredSunshadeCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[LouveredSunshadeCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:SUNSHADE|SOLAR\s+(?:FIN|LOUVER|SHADE)|AEROFOIL(?:\s+LOUVER)?|AIRFOIL(?:\s+LOUVER)?|CANTILEVER\s+LOUVER|OUTRIGGER\s+BRACKET|FACADE\s+LOUVER|LOUVERED\s+CANOPY|SS|AFL|SF)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (mechanical acoustic louver for plant room intake/discharge without shading, timber interior Venetian blind)
    negative_pattern = re.compile(
        r'\b(?:ACOUSTIC\s+LOUVER|WEATHER\s+LOUVER\s+PLANT\s+INTAKE|INTERIOR\s+VENETIAN\s+BLIND)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:SS|AFL|SF|LOU|OB)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    blade_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*MM\s*(?:AEROFOIL|BLADE|CHORD|AIRFOIL|FIN)|BLADE\s*[:=]?\s*(\d{2,3})\s*MM)\b',
        re.IGNORECASE
    )

    proj_pattern = re.compile(
        r'\b(?:(\d{3,4})\s*MM\s*(?:PROJECTION|OUTREACH|CANTILEVER)|PROJECTION\s*[:=]?\s*(\d{3,4})\s*MM)\b',
        re.IGNORECASE
    )

    angle_pattern = re.compile(
        r'(?:\b(\d{1,2})\s*°|\bTILT\s*[:=]?\s*(\d{1,2})\b|\b(\d{1,2})\s*(?:DEG|DEGREES)\b)',
        re.IGNORECASE
    )

    for prim in primitives:
        text = str(prim.get("text", "")).strip()
        if not text:
            continue

        if negative_pattern.search(text):
            continue

        if not keyword_pattern.search(text):
            continue

        upper_text = text.upper()

        # Classify element_type
        if "OUTRIGGER" in upper_text or "OB" in upper_text:
            element_type = "STRUCTURAL_OUTRIGGER_BRACKET"
        elif "MOTORIZED" in upper_text or "TRACKING" in upper_text or "PIVOT" in upper_text or "ACTUATED" in upper_text:
            element_type = "MOTORIZED_ELECTRIC_OPERABLE_SOLAR_LOUVER"
        elif "VERTICAL" in upper_text or "SF" in upper_text or "FIN" in upper_text:
            element_type = "VERTICAL_AEROFOIL_SOLAR_FIN"
        elif "CONTINUOUS" in upper_text or "LINEAR" in upper_text:
            element_type = "CONTINUOUS_LINEAR_FACADE_LOUVER"
        else:
            element_type = "HORIZONTAL_CANTILEVER_SUNSHADE"

        # Blade width in mm
        blade_width_mm = 200
        b_match = blade_pattern.search(text)
        if b_match:
            val_b = b_match.group(1) or b_match.group(2)
            if val_b:
                blade_width_mm = int(val_b)

        # Projection outreach in mm
        projection_outreach_mm = 900
        if element_type == "VERTICAL_AEROFOIL_SOLAR_FIN":
            projection_outreach_mm = 300
        elif element_type == "STRUCTURAL_OUTRIGGER_BRACKET":
            projection_outreach_mm = 1200
        p_match = proj_pattern.search(text)
        if p_match:
            val_p = p_match.group(1) or p_match.group(2)
            if val_p:
                projection_outreach_mm = int(val_p)

        # Blade tilt angle in degrees
        blade_tilt_angle_deg = 45
        if element_type == "VERTICAL_AEROFOIL_SOLAR_FIN":
            blade_tilt_angle_deg = 90
        ang_match = angle_pattern.search(text)
        if ang_match:
            val_ang = ang_match.group(1) or ang_match.group(2) or ang_match.group(3)
            if val_ang:
                blade_tilt_angle_deg = int(val_ang)

        # Blade profile
        if "BOX" in upper_text or "RECTANGULAR" in upper_text:
            blade_profile = "RECTANGULAR_BOX"
        elif "Z-BLADE" in upper_text or "Z BLADE" in upper_text:
            blade_profile = "Z_BLADE"
        elif "C-CHANNEL" in upper_text or "C CHANNEL" in upper_text:
            blade_profile = "C_CHANNEL"
        else:
            blade_profile = "AEROFOIL_ELLIPTICAL"

        # Finish type
        if "ANODIZED" in upper_text or "ANODISED" in upper_text:
            finish_type = "ANODIZED_25UM"
        elif "TIMBER GRAIN" in upper_text or "SUBLIMATION" in upper_text:
            finish_type = "TIMBER_GRAIN_SUBLIMATION"
        else:
            finish_type = "POWDER_COATED_DURATEC"

        # Motorized
        is_motorized = bool(
            "MOTORIZED" in upper_text or
            "ACTUATOR" in upper_text or
            "AUTOMATED" in upper_text or
            "TRACKING" in upper_text or
            element_type == "MOTORIZED_ELECTRIC_OPERABLE_SOLAR_LOUVER"
        )

        # Tag
        tag = None
        tag_match = tag_pattern.search(text)
        if tag_match:
            tag = tag_match.group(1).upper()

        x = float(prim.get("x", 0.0))
        y = float(prim.get("y", 0.0))
        snapped_pt = snap_point_to_grid(x, y, tolerance)

        confidence = 0.85
        if tag:
            confidence += 0.05
        if b_match:
            confidence += 0.05
        if p_match or ang_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = LouveredSunshadeCandidate(
            candidate_id=f"cand_sunshade_{uuid4().hex[:8]}",
            element_type=element_type,
            blade_width_mm=blade_width_mm,
            projection_outreach_mm=projection_outreach_mm,
            blade_tilt_angle_deg=blade_tilt_angle_deg,
            blade_profile=blade_profile,
            finish_type=finish_type,
            is_motorized=is_motorized,
            tag=tag,
            raw_annotation=text,
            snapped_grid_pt=snapped_pt,
            source_primitive_id=str(prim.get("id", f"prim_{uuid4().hex[:6]}")),
            confidence=confidence,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(candidate)

    return candidates
