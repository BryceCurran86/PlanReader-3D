"""
pb_source_chilled_beam_active_passive_induction_shadow.py

Shadow candidate authority for HVAC active and passive chilled beam induction terminals,
multi-service beams, and exposed architectural hydronic beams.

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
class ChilledBeamCandidate:
    candidate_id: str
    element_type: str  # ACTIVE_CHILLED_BEAM, PASSIVE_CHILLED_BEAM, MULTI_SERVICE_CHILLED_BEAM, EXPOSED_ARCHITECTURAL_BEAM
    length_mm: int
    width_mm: int
    pipe_configuration: str  # 2_PIPE_COOLING, 4_PIPE_HEATING_COOLING, 2_PIPE_PASSIVE
    primary_air_flow_l_s: int
    cooling_capacity_w: int
    has_integrated_lighting: bool
    nozzle_configuration: str  # SMALL_PRESSURE, MEDIUM_PRESSURE, LARGE_PRESSURE, NONE_PASSIVE
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


def extract_chilled_beam_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[ChilledBeamCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[ChilledBeamCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:CHILLED\s+BEAM|ACTIVE\s+BEAM|PASSIVE\s+BEAM|INDUCTION\s+BEAM|MULTI[- ]?SERVICE\s+BEAM|ACB|PCB|MSB)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (structural steel beam, concrete transfer beam, timber beam)
    negative_pattern = re.compile(
        r'\b(?:STEEL\s+BEAM|UNIVERSAL\s+BEAM|CONCRETE\s+BEAM|TIMBER\s+BEAM|TRANSFER\s+BEAM|UB\s+\d+|PFC|RHS)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:ACB|PCB|MSB|CB)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    dim_pattern = re.compile(
        r'\b(?:(\d{4})\s*[Xx]\s*(\d{3})\s*MM|L\s*[:=]?\s*(\d{4})\s*MM|W\s*[:=]?\s*(\d{3})\s*MM)\b',
        re.IGNORECASE
    )

    flow_pattern = re.compile(
        r'\b(?:(\d{1,3})\s*L\s*/\s*S|(\d{1,3})\s*L/S)\b',
        re.IGNORECASE
    )

    capacity_pattern = re.compile(
        r'\b(?:(\d{3,4})\s*W(?:ATTS)?|(\d(?:\.\d)?)\s*KW)\b',
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
        if "MULTI SERVICE" in upper_text or "MULTI-SERVICE" in upper_text or "MSB" in upper_text:
            element_type = "MULTI_SERVICE_CHILLED_BEAM"
        elif "PASSIVE" in upper_text or "PCB" in upper_text:
            element_type = "PASSIVE_CHILLED_BEAM"
        elif "EXPOSED" in upper_text or "FREE HANGING" in upper_text:
            element_type = "EXPOSED_ARCHITECTURAL_BEAM"
        elif "ACTIVE" in upper_text or "ACB" in upper_text:
            element_type = "ACTIVE_CHILLED_BEAM"
        else:
            element_type = "ACTIVE_CHILLED_BEAM"

        # Dimensions: length_mm & width_mm
        length_mm = 2400
        width_mm = 600

        dim_match = dim_pattern.search(text)
        if dim_match:
            if dim_match.group(1) and dim_match.group(2):
                length_mm = int(dim_match.group(1))
                width_mm = int(dim_match.group(2))
            elif dim_match.group(3):
                length_mm = int(dim_match.group(3))
            elif dim_match.group(4):
                width_mm = int(dim_match.group(4))

        # Check for modular lengths in text
        for l_val in (1200, 1800, 2400, 3000, 3600):
            if f"{l_val}MM" in upper_text or f"{l_val} MM" in upper_text:
                length_mm = l_val
                break

        # Check for modular widths in text
        for w_val in (300, 600, 900):
            if f"{w_val}MM" in upper_text or f"{w_val} MM" in upper_text:
                if w_val != length_mm:
                    width_mm = w_val
                    break

        # Pipe configuration
        if "2-PIPE" in upper_text or "2 PIPE" in upper_text:
            pipe_configuration = "2_PIPE_COOLING"
        elif "4-PIPE" in upper_text or "4 PIPE" in upper_text:
            pipe_configuration = "4_PIPE_HEATING_COOLING"
        elif element_type == "PASSIVE_CHILLED_BEAM":
            pipe_configuration = "2_PIPE_PASSIVE"
        else:
            pipe_configuration = "4_PIPE_HEATING_COOLING"

        # Primary airflow
        if element_type == "PASSIVE_CHILLED_BEAM":
            primary_air_flow_l_s = 0
            nozzle_configuration = "NONE_PASSIVE"
        else:
            primary_air_flow_l_s = 25
            nozzle_configuration = "MEDIUM_PRESSURE"
            f_match = flow_pattern.search(text)
            if f_match:
                val_flow = f_match.group(1) or f_match.group(2)
                if val_flow:
                    primary_air_flow_l_s = int(val_flow)

        # Cooling capacity
        cooling_capacity_w = 1200
        cap_match = capacity_pattern.search(text)
        if cap_match:
            if cap_match.group(1):
                cooling_capacity_w = int(cap_match.group(1))
            elif cap_match.group(2):
                cooling_capacity_w = int(float(cap_match.group(2)) * 1000)

        # Integrated lighting
        has_integrated_lighting = bool(
            "LIGHTING" in upper_text or
            "LUMINAIRE" in upper_text or
            re.search(r'\bLED\b', upper_text) or
            element_type == "MULTI_SERVICE_CHILLED_BEAM"
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
        if dim_match:
            confidence += 0.05
        if cap_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = ChilledBeamCandidate(
            candidate_id=f"cand_chilled_beam_{uuid4().hex[:8]}",
            element_type=element_type,
            length_mm=length_mm,
            width_mm=width_mm,
            pipe_configuration=pipe_configuration,
            primary_air_flow_l_s=primary_air_flow_l_s,
            cooling_capacity_w=cooling_capacity_w,
            has_integrated_lighting=has_integrated_lighting,
            nozzle_configuration=nozzle_configuration,
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
