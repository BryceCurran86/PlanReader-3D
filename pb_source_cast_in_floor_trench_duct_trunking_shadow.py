"""
pb_source_cast_in_floor_trench_duct_trunking_shadow.py

Shadow candidate authority for cast-in and in-screed electrical floor trench ducts,
multi-compartment trunking, service outlet boxes, and crossover junction boxes.

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
class FloorTrenchDuctCandidate:
    candidate_id: str
    element_type: str  # FLUSH_FLOOR_TRUNK_3_COMPARTMENT, FLUSH_FLOOR_TRUNK_2_COMPARTMENT, IN_SCREED_FLOOR_DUCT, SERVICE_OUTLET_BOX, INTERSECTION_JUNCTION_BOX
    width_mm: int
    depth_mm: int
    num_compartments: int
    cover_type: str  # FLUSH_BRASS_TRIM, FLUSH_STAINLESS_TRIM, CARPET_INFILL_TRAY, TILE_INFILL_LID, SCREED_ENCLOSED
    has_flyover_bridge: bool
    load_class: str  # LIGHT_PEDESTRIAN, MEDIUM_COMMERCIAL, HEAVY_WHEELED
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


def extract_floor_trench_duct_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[FloorTrenchDuctCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[FloorTrenchDuctCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:FLOOR\s+TRUNKING|FLOOR\s+TRENCH|IN[- ]?SCREED(?:\s+FLOOR)?\s+DUCT|FLUSH\s+FLOOR|SERVICE\s+OUTLET(?:\s+BOX)?|JUNCTION\s+BOX|TRUNK[- ]?DUCT|FLOOR\s+DUCT)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (linear civil trench drain, roof gutter, plumbing shower waste)
    negative_pattern = re.compile(
        r'\b(?:STORMWATER|GRATE\s+DRAIN|SHOWER\s+WASTE|ROOF\s+GUTTER|CIVIL\s+DRAINAGE)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:FT|JB|SOB|TD|FDB)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    dim_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*[Xx]\s*(\d{2,3})\s*MM|(\d{2,3})\s*MM\s*WIDE|(\d{2,3})\s*MM\s*DEEP)\b',
        re.IGNORECASE
    )

    compartment_pattern = re.compile(
        r'\b([1-4])[- ]?(?:COMPARTMENT|COMPT|WAY)\b',
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

        # Compartments
        num_compartments = 3  # default standard is 3-compartment (power, data, aux)
        comp_match = compartment_pattern.search(text)
        if comp_match:
            num_compartments = int(comp_match.group(1))
        elif "2 COMPARTMENT" in upper_text or "TWO COMPARTMENT" in upper_text or "2-WAY" in upper_text:
            num_compartments = 2
        elif "1 COMPARTMENT" in upper_text or "SINGLE COMPARTMENT" in upper_text:
            num_compartments = 1

        # Classify element_type
        if "SERVICE OUTLET" in upper_text or "SOB" in upper_text or "POPOUT BOX" in upper_text:
            element_type = "SERVICE_OUTLET_BOX"
        elif "JUNCTION BOX" in upper_text or "CROSSOVER" in upper_text or "INTERSECTION" in upper_text or "JB" in upper_text:
            element_type = "INTERSECTION_JUNCTION_BOX"
        elif "IN-SCREED" in upper_text or "IN SCREED" in upper_text or "CONCEALED DUCT" in upper_text:
            element_type = "IN_SCREED_FLOOR_DUCT"
        elif num_compartments == 2:
            element_type = "FLUSH_FLOOR_TRUNK_2_COMPARTMENT"
        else:
            element_type = "FLUSH_FLOOR_TRUNK_3_COMPARTMENT"

        # Dimensions: width_mm & depth_mm
        if element_type == "SERVICE_OUTLET_BOX":
            width_mm = 250
            depth_mm = 75
        elif element_type == "INTERSECTION_JUNCTION_BOX":
            width_mm = 350
            depth_mm = 65
        elif element_type == "IN_SCREED_FLOOR_DUCT":
            width_mm = 225
            depth_mm = 38
        else:
            width_mm = 300
            depth_mm = 38

        dim_match = dim_pattern.search(text)
        if dim_match:
            if dim_match.group(1) and dim_match.group(2):
                d1 = int(dim_match.group(1))
                d2 = int(dim_match.group(2))
                width_mm = max(d1, d2)
                depth_mm = min(d1, d2)
            elif dim_match.group(3):
                width_mm = int(dim_match.group(3))
            elif dim_match.group(4):
                depth_mm = int(dim_match.group(4))

        # Cover type
        if "CARPET" in upper_text:
            cover_type = "CARPET_INFILL_TRAY"
        elif "TILE" in upper_text:
            cover_type = "TILE_INFILL_LID"
        elif "BRASS" in upper_text:
            cover_type = "FLUSH_BRASS_TRIM"
        elif "STAINLESS" in upper_text:
            cover_type = "FLUSH_STAINLESS_TRIM"
        elif element_type == "IN_SCREED_FLOOR_DUCT":
            cover_type = "SCREED_ENCLOSED"
        else:
            cover_type = "CARPET_INFILL_TRAY"

        # Flyover bridge
        has_flyover_bridge = bool(
            "FLYOVER" in upper_text or
            "CROSSOVER" in upper_text or
            "SEGREGATION BRIDGE" in upper_text or
            element_type == "INTERSECTION_JUNCTION_BOX"
        )

        # Load class
        if "HEAVY" in upper_text or "WHEELED" in upper_text or "VEHICLE" in upper_text:
            load_class = "HEAVY_WHEELED"
        elif "LIGHT" in upper_text or "DOMESTIC" in upper_text:
            load_class = "LIGHT_PEDESTRIAN"
        else:
            load_class = "MEDIUM_COMMERCIAL"

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
        if comp_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = FloorTrenchDuctCandidate(
            candidate_id=f"cand_floor_trench_{uuid4().hex[:8]}",
            element_type=element_type,
            width_mm=width_mm,
            depth_mm=depth_mm,
            num_compartments=num_compartments,
            cover_type=cover_type,
            has_flyover_bridge=has_flyover_bridge,
            load_class=load_class,
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
