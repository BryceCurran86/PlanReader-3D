"""
pb_source_operable_movable_acoustic_partition_shadow.py

Shadow candidate authority for architectural operable movable acoustic partition walls,
stacking pocket enclosures, pass-door inserts, and overhead structural tracks.

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
class OperableWallCandidate:
    candidate_id: str
    element_type: str  # OPERABLE_ACOUSTIC_WALL_RUN, STACKING_POCKET_ENCLOSURE, PASS_DOOR_INSERT_PANEL, OVERHEAD_STRUCTURAL_TRACK, MOTORIZED_ELECTRIC_OPERABLE_WALL
    acoustic_rating_rw_stc: int
    panel_thickness_mm: int
    panel_height_mm: int
    surface_finish: str  # FABRIC_ACOUSTIC_WRAPPED, TIMBER_VENEER, HIGH_PRESSURE_LAMINATE, MAGNETIC_WHITEBOARD, RAW_MDF_PREP
    has_retractable_seals: bool
    suspension_type: str  # TOP_HUNG_OMNI_DIRECTIONAL, TOP_HUNG_CENTER_STACK, FLOOR_SUPPORTED
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


def extract_operable_wall_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[OperableWallCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[OperableWallCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:OPERABLE\s+WALL|MOVABLE\s+(?:ACOUSTIC\s+)?WALL|OPERABLE\s+PARTITION|MOVABLE\s+PARTITION|OPERABLE\s+PANEL|ACOUSTIC\s+PARTITION\s+WALL|STACKING\s+POCKET|OVERHEAD\s+TRACK|PASS[- ]?DOOR(?:\s+PANEL)?|SLIDING\s+FOLDING\s+WALL|OW|MAP|OP|SWP)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (standard drywall stud wall, fixed glass partition, sliding pocket timber door)
    negative_pattern = re.compile(
        r'\b(?:STANDARD\s+DRYWALL|FIXED\s+PLASTERBOARD|FIXED\s+GLASS\s+PARTITION|DOMESTIC\s+SLIDING\s+DOOR\s+ONLY)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:OW|MAP|OP|SP|SWP|OHT)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    stc_pattern = re.compile(
        r'\b(?:RW|STC)\s*[:=]?\s*(\d{2})\b|(?<![-_A-Z0-9])(\d{2})\s*(?:RW|STC|DB)\b',
        re.IGNORECASE
    )

    thk_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*MM\s*(?:THK|THICK|PANEL))\b',
        re.IGNORECASE
    )

    height_pattern = re.compile(
        r'\b(?:H\s*[:=]?\s*(\d{4})\s*MM|(\d{4})\s*MM\s*HIGH)\b',
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
        if "TRACK" in upper_text or "OHT" in upper_text or "CARRIER" in upper_text:
            element_type = "OVERHEAD_STRUCTURAL_TRACK"
        elif "POCKET" in upper_text or "STACKING" in upper_text or "PARKING BAY" in upper_text:
            element_type = "STACKING_POCKET_ENCLOSURE"
        elif "PASS DOOR" in upper_text or "PASS-DOOR" in upper_text or "INSERT DOOR" in upper_text:
            element_type = "PASS_DOOR_INSERT_PANEL"
        elif "MOTORIZED" in upper_text or "ELECTRIC" in upper_text or "CONTINUOUS HINGE" in upper_text:
            element_type = "MOTORIZED_ELECTRIC_OPERABLE_WALL"
        else:
            element_type = "OPERABLE_ACOUSTIC_WALL_RUN"

        # Acoustic rating Rw/STC
        acoustic_rating_rw_stc = 50
        stc_match = stc_pattern.search(text)
        if stc_match:
            val_stc = stc_match.group(1) or stc_match.group(2)
            if val_stc:
                acoustic_rating_rw_stc = int(val_stc)

        # Panel thickness
        panel_thickness_mm = 100
        thk_match = thk_pattern.search(text)
        if thk_match:
            val_t = thk_match.group(1)
            if val_t:
                t = int(val_t)
                if t in (65, 75, 80, 85, 100, 105, 110, 120, 125, 150):
                    panel_thickness_mm = t

        # Panel height
        panel_height_mm = 3000
        h_match = height_pattern.search(text)
        if h_match:
            val_h = h_match.group(1) or h_match.group(2)
            if val_h:
                panel_height_mm = int(val_h)

        # Surface finish
        if "FABRIC" in upper_text or "ACOUSTIC WRAPPED" in upper_text:
            surface_finish = "FABRIC_ACOUSTIC_WRAPPED"
        elif "TIMBER" in upper_text or "VENEER" in upper_text:
            surface_finish = "TIMBER_VENEER"
        elif "WHITEBOARD" in upper_text or "MAGNETIC" in upper_text:
            surface_finish = "MAGNETIC_WHITEBOARD"
        elif "RAW" in upper_text or "MDF" in upper_text:
            surface_finish = "RAW_MDF_PREP"
        else:
            surface_finish = "HIGH_PRESSURE_LAMINATE"

        # Retractable seals
        has_retractable_seals = bool(
            "SEAL" in upper_text or
            "CRANK" in upper_text or
            "MECHANICAL" in upper_text or
            element_type in ("OPERABLE_ACOUSTIC_WALL_RUN", "PASS_DOOR_INSERT_PANEL")
        )

        # Suspension type
        if "CENTER STACK" in upper_text or "CENTRE STACK" in upper_text:
            suspension_type = "TOP_HUNG_CENTER_STACK"
        elif "FLOOR SUPPORTED" in upper_text or "FLOOR TRACK" in upper_text:
            suspension_type = "FLOOR_SUPPORTED"
        else:
            suspension_type = "TOP_HUNG_OMNI_DIRECTIONAL"

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
        if stc_match:
            confidence += 0.05
        if thk_match or h_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = OperableWallCandidate(
            candidate_id=f"cand_operable_wall_{uuid4().hex[:8]}",
            element_type=element_type,
            acoustic_rating_rw_stc=acoustic_rating_rw_stc,
            panel_thickness_mm=panel_thickness_mm,
            panel_height_mm=panel_height_mm,
            surface_finish=surface_finish,
            has_retractable_seals=has_retractable_seals,
            suspension_type=suspension_type,
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
