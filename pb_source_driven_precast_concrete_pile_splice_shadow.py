"""
pb_source_driven_precast_concrete_pile_splice_shadow.py

Shadow candidate authority for structural deep foundation driven precast concrete piles,
mechanical locking splices, hardened rock shoes, and pile cut-off starter assemblies.

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
class DrivenPileCandidate:
    candidate_id: str
    element_type: str  # DRIVEN_PRECAST_SQUARE_PILE, MECHANICAL_PILE_SPLICE_JOINT, DRIVING_ROCK_SHOE_POINT, PILE_HEAD_CUTOFF_ASSEMBLY, CYLINDRICAL_SPUN_CONCRETE_PILE
    pile_size_mm: int
    segment_length_m: float
    concrete_strength_mpa: int
    working_load_kn: int
    shoe_type: str  # CHISEL_ROCK_SHOE, FLAT_STEEL_SHOE, OSLO_POINT, STANDARD_BLUNT
    splice_type: str  # MECHANICAL_LOCKING_PINS, WELDED_COLLAR, EPOXY_DOWEL_JOINT, NONE_SINGLE_LENGTH
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


def extract_driven_pile_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[DrivenPileCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[DrivenPileCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:DRIVEN\s+PILE|PRECAST\s+PILE|CONCRETE\s+PILE|PILE\s+SPLICE|ROCK\s+SHOE|DRIVING\s+SHOE|PILE\s+CUT[- ]?OFF|SPUN\s+(?:CONCRETE\s+(?:CYLINDER\s+)?)?PILE|SPUN\s+CONCRETE|CYLINDER\s+PILE|PHC(?:\s+PILE)?|DP|PCCP)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (bored cast-in-situ pier without driven context, sheet pile wall, carpet pile)
    negative_pattern = re.compile(
        r'\b(?:BORED\s+PIER\s+ONLY|CFA\s+PILING|STEEL\s+SHEET\s+PILE|CARPET\s+PILE)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:DP|PCCP|PJ|PS|PHC|CP)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    dim_pattern = re.compile(
        r'\b(?:(\d{3})\s*[Xx]\s*(\d{3})\s*MM|(\d{3})\s*MM\s*(?:SQ|SQUARE|DIA|OCT)?)\b',
        re.IGNORECASE
    )

    len_pattern = re.compile(
        r'\b(?:(\d{1,2}(?:\.\d)?)\s*M\s*(?:LONG|LENGTH|SEGMENT)|L\s*[:=]?\s*(\d{1,2}(?:\.\d)?)\s*M)\b',
        re.IGNORECASE
    )

    mpa_pattern = re.compile(
        r'\b(?:(\d{2})\s*MPA|GRADE\s*(\d{2}))\b',
        re.IGNORECASE
    )

    load_pattern = re.compile(
        r'\b(?:(\d{3,4})\s*KN\s*(?:SWL|LOAD|CAPACITY)?|SWL\s*[:=]?\s*(\d{3,4})\s*KN)\b',
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
        if "CUT-OFF" in upper_text or "CUT OFF" in upper_text or "PILE HEAD" in upper_text:
            element_type = "PILE_HEAD_CUTOFF_ASSEMBLY"
        elif "SPUN" in upper_text or "PHC" in upper_text or "CYLINDER PILE" in upper_text:
            element_type = "CYLINDRICAL_SPUN_CONCRETE_PILE"
        elif "DRIVEN PRECAST" in upper_text or "PRECAST CONCRETE PILE" in upper_text or "DRIVEN CONCRETE PILE" in upper_text or "DRIVEN PILE" in upper_text or "PCCP" in upper_text:
            element_type = "DRIVEN_PRECAST_SQUARE_PILE"
        elif "SPLICE" in upper_text or "PJ" in upper_text or "LOCKING PIN" in upper_text:
            element_type = "MECHANICAL_PILE_SPLICE_JOINT"
        elif "SHOE" in upper_text or "ROCK POINT" in upper_text or "OSLO" in upper_text:
            element_type = "DRIVING_ROCK_SHOE_POINT"
        else:
            element_type = "DRIVEN_PRECAST_SQUARE_PILE"

        # Pile size in mm
        pile_size_mm = 350
        dim_match = dim_pattern.search(text)
        if dim_match:
            if dim_match.group(1):
                pile_size_mm = int(dim_match.group(1))
            elif dim_match.group(3):
                val_d = int(dim_match.group(3))
                if val_d in (200, 250, 275, 300, 350, 400, 450, 500, 600):
                    pile_size_mm = val_d

        # Segment length in meters
        segment_length_m = 12.0
        len_match = len_pattern.search(text)
        if len_match:
            val_l = len_match.group(1) or len_match.group(2)
            if val_l:
                segment_length_m = float(val_l)

        # Concrete strength in MPa
        concrete_strength_mpa = 60
        mpa_match = mpa_pattern.search(text)
        if mpa_match:
            val_mpa = mpa_match.group(1) or mpa_match.group(2)
            if val_mpa:
                concrete_strength_mpa = int(val_mpa)

        # Working load in kN
        working_load_kn = 1200
        l_match = load_pattern.search(text)
        if l_match:
            val_kn = l_match.group(1) or l_match.group(2)
            if val_kn:
                working_load_kn = int(val_kn)

        # Shoe type
        if "OSLO" in upper_text:
            shoe_type = "OSLO_POINT"
        elif "FLAT" in upper_text or "BLUNT" in upper_text:
            shoe_type = "FLAT_STEEL_SHOE"
        else:
            shoe_type = "CHISEL_ROCK_SHOE"

        # Splice type
        if "WELDED" in upper_text or "COLLAR" in upper_text:
            splice_type = "WELDED_COLLAR"
        elif "EPOXY" in upper_text or "DOWEL" in upper_text:
            splice_type = "EPOXY_DOWEL_JOINT"
        elif "SINGLE LENGTH" in upper_text or "NO SPLICE" in upper_text:
            splice_type = "NONE_SINGLE_LENGTH"
        else:
            splice_type = "MECHANICAL_LOCKING_PINS"

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
        if mpa_match or l_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = DrivenPileCandidate(
            candidate_id=f"cand_driven_pile_{uuid4().hex[:8]}",
            element_type=element_type,
            pile_size_mm=pile_size_mm,
            segment_length_m=segment_length_m,
            concrete_strength_mpa=concrete_strength_mpa,
            working_load_kn=working_load_kn,
            shoe_type=shoe_type,
            splice_type=splice_type,
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
