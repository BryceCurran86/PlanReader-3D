"""
pb_source_asphalt_pavement_geogrid_sam_interlayer_shadow.py

Shadow candidate authority for civil asphalt pavement geogrid reinforcements,
Stress Absorbing Membrane Interlayers (SAMI), glass/carbon fiber grids, and crack bandages.

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
class PavementGeogridCandidate:
    candidate_id: str
    element_type: str  # FIBERGLASS_ASPHALT_GEOGRID, CARBON_FIBER_PAVEMENT_GRID, SAMI_STRESS_ABSORBING_MEMBRANE, POLYPROPYLENE_BIAXIAL_GEOGRID, JOINT_SEAL_REINFORCEMENT_STRIP
    ultimate_tensile_strength_kn_m: int
    grid_aperture_mm: int
    roll_width_m: float
    has_adhesive_backing: bool
    bitumen_retention_l_m2: float
    temperature_resistance_c: int
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


def extract_pavement_geogrid_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[PavementGeogridCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[PavementGeogridCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:PAVEMENT\s+(?:GEO)?GRID|ASPHALT\s+(?:GEO)?GRID|FIBERGLASS\s+(?:GEO)?GRID|PAVING\s+FABRIC|SAMI|STRESS\s+ABSORBING\s+MEMBRANE|CRACK\s+BANDAGE|CRACK\s+REINFORCEMENT|GLASGRID|PGR|AGR)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (turf reinforcement mesh, gabion wire basket, tree root barrier)
    negative_pattern = re.compile(
        r'\b(?:TURF\s+GRID|GABION\s+BASKET|TREE\s+ROOT\s+BARRIER|PLASTIC\s+TOPSOIL\s+MESH)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:PGR|AGR|SAMI|CRB|PGF)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    tensile_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*KN\s*/\s*M|(\d{2,3})\s*KN/M)\b',
        re.IGNORECASE
    )

    aperture_pattern = re.compile(
        r'\b(?:(\d{1,2}(?:\.\d)?)\s*[Xx]\s*(\d{1,2}(?:\.\d)?)\s*MM|APERTURE\s*[:=]?\s*(\d{1,2})\s*MM)\b',
        re.IGNORECASE
    )

    width_pattern = re.compile(
        r'\b(?:(\d(?:\.\d)?)\s*M\s*(?:WIDE|WIDTH|ROLL)|(\d{3,4})\s*MM\s*(?:WIDE|WIDTH|BANDAGE))\b',
        re.IGNORECASE
    )

    temp_pattern = re.compile(
        r'\b(?:(\d{3})\s*°?\s*C)\b',
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
        if "BANDAGE" in upper_text or "CRACK STRIP" in upper_text or "JOINT SEAL" in upper_text or "CRB" in upper_text:
            element_type = "JOINT_SEAL_REINFORCEMENT_STRIP"
        elif "SAMI" in upper_text or "STRESS ABSORBING" in upper_text or "PAVING FABRIC" in upper_text:
            element_type = "SAMI_STRESS_ABSORBING_MEMBRANE"
        elif "CARBON" in upper_text:
            element_type = "CARBON_FIBER_PAVEMENT_GRID"
        elif "POLYPROPYLENE" in upper_text or "SUBBASE" in upper_text or "BIAXIAL" in upper_text:
            element_type = "POLYPROPYLENE_BIAXIAL_GEOGRID"
        else:
            element_type = "FIBERGLASS_ASPHALT_GEOGRID"

        # Tensile strength in kN/m
        ultimate_tensile_strength_kn_m = 100
        ten_match = tensile_pattern.search(text)
        if ten_match:
            val_ten = ten_match.group(1) or ten_match.group(2)
            if val_ten:
                ultimate_tensile_strength_kn_m = int(val_ten)

        # Grid aperture in mm
        grid_aperture_mm = 25
        if element_type == "SAMI_STRESS_ABSORBING_MEMBRANE":
            grid_aperture_mm = 0
        ap_match = aperture_pattern.search(text)
        if ap_match:
            if ap_match.group(1):
                grid_aperture_mm = int(float(ap_match.group(1)))
            elif ap_match.group(3):
                grid_aperture_mm = int(ap_match.group(3))

        # Roll width in meters
        roll_width_m = 2.0
        if element_type == "JOINT_SEAL_REINFORCEMENT_STRIP":
            roll_width_m = 0.5
        w_match = width_pattern.search(text)
        if w_match:
            if w_match.group(1):
                roll_width_m = float(w_match.group(1))
            elif w_match.group(2):
                roll_width_m = round(float(w_match.group(2)) / 1000.0, 2)

        # Adhesive backing
        has_adhesive_backing = bool(
            "SELF-ADHESIVE" in upper_text or
            "ADHESIVE" in upper_text or
            "PRESSURE SENSITIVE" in upper_text or
            element_type in ("FIBERGLASS_ASPHALT_GEOGRID", "JOINT_SEAL_REINFORCEMENT_STRIP")
        )

        # Bitumen retention
        bitumen_retention_l_m2 = 1.1 if element_type == "SAMI_STRESS_ABSORBING_MEMBRANE" else 0.0

        # Temperature resistance °C
        temperature_resistance_c = 250
        temp_match = temp_pattern.search(text)
        if temp_match:
            temperature_resistance_c = int(temp_match.group(1))

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
        if ten_match:
            confidence += 0.05
        if ap_match or w_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = PavementGeogridCandidate(
            candidate_id=f"cand_pavement_grid_{uuid4().hex[:8]}",
            element_type=element_type,
            ultimate_tensile_strength_kn_m=ultimate_tensile_strength_kn_m,
            grid_aperture_mm=grid_aperture_mm,
            roll_width_m=roll_width_m,
            has_adhesive_backing=has_adhesive_backing,
            bitumen_retention_l_m2=bitumen_retention_l_m2,
            temperature_resistance_c=temperature_resistance_c,
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
