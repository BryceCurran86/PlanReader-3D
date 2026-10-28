"""
pb_source_expansion_joint_cover_seismic_bellows_shadow.py

Shadow candidate authority for architectural expansion joint covers, seismic floor/wall
bellows, fire-rated barriers, and roof weather-seal joints.

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
class ExpansionJointCoverCandidate:
    candidate_id: str
    element_type: str  # SEISMIC_FLOOR_JOINT_COVER, FLUSH_WALL_JOINT_COVER, CEILING_EXPANSION_COVER, ROOF_EXPANSION_BELLOWS, FIRE_RATED_BLANKET_BARRIER
    nominal_joint_gap_mm: int
    movement_capacity_percent: int
    cover_material: str  # ANODIZED_ALUMINUM, STAINLESS_STEEL, EXTRUDED_BRONZE, SANTOPRENE_ELASTOMER, WATERPROOF_EPDM
    has_fire_barrier: bool
    has_vapor_water_barrier: bool
    load_rating: str  # PEDESTRIAN_STANDARD, PNEUMATIC_TIRE, HEAVY_FORKLIFT_STEEL_WHEEL
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


def extract_expansion_joint_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[ExpansionJointCoverCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[ExpansionJointCoverCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:EXPANSION\s+JOINT(?:\s+COVER)?|SEISMIC\s+JOINT|MOVEMENT\s+JOINT|FLOOR\s+JOINT|WALL\s+JOINT|BELLOWS\s+JOINT|FIRE\s+BLANKET\s+JOINT|EJC|SJC|FJC)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (duct flexible connection, pipe expansion bellows, saw cut control joint)
    negative_pattern = re.compile(
        r'\b(?:SAW\s+CUT|CONTROL\s+JOINT\s+SEALANT\s+ONLY|PIPE\s+BELLOWS|DUCT\s+FLEXIBLE\s+CANVAS)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:EJC|SJC|WJC|FJC|RJC)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    gap_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*MM\s*(?:GAP|JOINT|OPENING|WIDTH)?|GAP\s*[:=]?\s*(\d{2,3})\s*MM)\b',
        re.IGNORECASE
    )

    movement_pattern = re.compile(
        r'(?:[+±/\-]{1,3}|\b)\s*(\d{2,3})\s*%',
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
        if ("FIRE BLANKET" in upper_text or "FIRE BARRIER" in upper_text) and "COVER" not in upper_text:
            element_type = "FIRE_RATED_BLANKET_BARRIER"
        elif "ROOF" in upper_text or "WEATHERPROOF" in upper_text or "RJC" in upper_text:
            element_type = "ROOF_EXPANSION_BELLOWS"
        elif "CEILING" in upper_text or "SOFFIT" in upper_text:
            element_type = "CEILING_EXPANSION_COVER"
        elif "WALL" in upper_text or "WJC" in upper_text or "PARTITION" in upper_text:
            element_type = "FLUSH_WALL_JOINT_COVER"
        elif "FLOOR" in upper_text or "SEISMIC" in upper_text or "SJC" in upper_text or "EJC" in upper_text or "FJC" in upper_text:
            element_type = "SEISMIC_FLOOR_JOINT_COVER"
        else:
            element_type = "SEISMIC_FLOOR_JOINT_COVER"

        # Gap size in mm
        nominal_joint_gap_mm = 50
        gap_match = gap_pattern.search(text)
        if gap_match:
            val_gap = gap_match.group(1) or gap_match.group(2)
            if val_gap:
                g = int(val_gap)
                if g in (20, 25, 30, 40, 50, 75, 100, 150, 200, 250, 300, 400, 500):
                    nominal_joint_gap_mm = g

        # Movement capacity percent
        movement_capacity_percent = 50
        m_match = movement_pattern.search(text)
        if m_match:
            movement_capacity_percent = int(m_match.group(1))

        # Cover material
        if "STAINLESS" in upper_text:
            cover_material = "STAINLESS_STEEL"
        elif "BRONZE" in upper_text or "BRASS" in upper_text:
            cover_material = "EXTRUDED_BRONZE"
        elif "EPDM" in upper_text:
            cover_material = "WATERPROOF_EPDM"
        elif "SANTOPRENE" in upper_text or "NEOPRENE" in upper_text or "RUBBER" in upper_text:
            cover_material = "SANTOPRENE_ELASTOMER"
        else:
            cover_material = "ANODIZED_ALUMINUM"

        # Fire barrier
        has_fire_barrier = bool(
            "FIRE" in upper_text or
            "INTUMESCENT" in upper_text or
            "FRL" in upper_text or
            "2HR" in upper_text or
            "2-HOUR" in upper_text or
            element_type == "FIRE_RATED_BLANKET_BARRIER"
        )

        # Vapor / water barrier
        has_vapor_water_barrier = bool(
            "WATER" in upper_text or
            "VAPOR" in upper_text or
            "MOISTURE" in upper_text or
            "EPDM" in upper_text or
            "DRAIN TUBE" in upper_text or
            element_type == "ROOF_EXPANSION_BELLOWS"
        )

        # Load rating
        if "FORKLIFT" in upper_text or "STEEL WHEEL" in upper_text or "HEAVY" in upper_text:
            load_rating = "HEAVY_FORKLIFT_STEEL_WHEEL"
        elif "VEHICLE" in upper_text or "CAR" in upper_text or "PARKING" in upper_text or "TIRE" in upper_text:
            load_rating = "PNEUMATIC_TIRE"
        else:
            load_rating = "PEDESTRIAN_STANDARD"

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
        if gap_match:
            confidence += 0.05
        if m_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = ExpansionJointCoverCandidate(
            candidate_id=f"cand_expansion_joint_{uuid4().hex[:8]}",
            element_type=element_type,
            nominal_joint_gap_mm=nominal_joint_gap_mm,
            movement_capacity_percent=movement_capacity_percent,
            cover_material=cover_material,
            has_fire_barrier=has_fire_barrier,
            has_vapor_water_barrier=has_vapor_water_barrier,
            load_rating=load_rating,
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
