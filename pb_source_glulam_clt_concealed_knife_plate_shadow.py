"""
pb_source_glulam_clt_concealed_knife_plate_shadow.py

Shadow candidate authority for structural timber glulam and CLT concealed knife plate
connections, internal slotted steel blades, drift dowel pins, and standoff column bases.

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
class KnifePlateCandidate:
    candidate_id: str
    element_type: str  # CONCEALED_BEAM_COLUMN_KNIFE_PLATE, CONCEALED_COLUMN_BASE_KNIFE_PLATE, CLT_SHEAR_PANEL_SPLICE_PLATE, TRUSS_NODE_MULTIAXIAL_KNIFE_PLATE, TENSION_TIE_HOLD_DOWN_BLADE
    plate_thickness_mm: int
    num_knife_slots: int
    dowel_diameter_mm: int
    num_dowels: int
    fire_rating_minutes: int
    standoff_height_mm: int
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


def extract_knife_plate_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[KnifePlateCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[KnifePlateCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:KNIFE[- ]?PLATE|CONCEALED\s+PLATE|SLOTTED\s+PLATE|INTERNAL\s+STEEL\s+BLADE|GLULAM(?:\s+CONNECTION)?|CLT(?:\s+CONNECTOR)?|TIMBER\s+DOWEL\s+CONNECTION|TRUSS\s+CONNECTOR|COLUMN\s+BASE|TIMBER\s+CONNECTOR|KP|CBP|TCP)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (structural steel shear tab without timber, drywall stud knife edge, kitchen knife)
    negative_pattern = re.compile(
        r'\b(?:STEEL\s+BEAM\s+TO\s+STEEL|DRYWALL\s+STUD|KITCHEN\s+UTENSIL|ALUMINUM\s+LOUVER)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:KP|CBP|TCP|GLK|CLTK)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    thk_pattern = re.compile(
        r'\b(?:(\d{1,2})\s*MM\s*(?:(?:STEEL\s+)?(?:THK|THICK|PLATE|BLADE))|PL\s*(\d{1,2}))\b',
        re.IGNORECASE
    )

    dowel_pattern = re.compile(
        r'\b(?:(\d{1,2})\s*[Xx]\s*(?:M|Ø|DIA\s*)?(\d{1,2})\s*DOWELS?|(\d{1,2})\s*(?:M|Ø|DIA\s*)(\d{1,2})\s*DOWELS?|(?:Ø|DIA\s*)(\d{1,2})\s*DOWELS?)\b',
        re.IGNORECASE
    )

    blade_slot_pattern = re.compile(
        r'\b(SINGLE|DOUBLE|TRIPLE|[1-3])[- ]?(?:SLOT|BLADE|PLATE)\b',
        re.IGNORECASE
    )

    standoff_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*MM\s*STANDOFF|STANDOFF\s*[:=]?\s*(\d{2,3})\s*MM)\b',
        re.IGNORECASE
    )

    frl_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*(?:MIN|MINUTES|HR|HOUR)\s*FIRE|FRL\s*[:=]?\s*(\d{2,3}))\b',
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
        if "COLUMN BASE" in upper_text or "BASE BOOT" in upper_text or "CBP" in upper_text:
            element_type = "CONCEALED_COLUMN_BASE_KNIFE_PLATE"
        elif "TRUSS" in upper_text or "MULTIAXIAL" in upper_text or "NODE" in upper_text:
            element_type = "TRUSS_NODE_MULTIAXIAL_KNIFE_PLATE"
        elif "TENSION TIE" in upper_text or "HOLD DOWN" in upper_text or "UPLIFT" in upper_text:
            element_type = "TENSION_TIE_HOLD_DOWN_BLADE"
        elif "CLT" in upper_text or "SPLICE" in upper_text or "SHEAR PANEL" in upper_text or "DIAPHRAGM" in upper_text:
            element_type = "CLT_SHEAR_PANEL_SPLICE_PLATE"
        else:
            element_type = "CONCEALED_BEAM_COLUMN_KNIFE_PLATE"

        # Plate thickness in mm
        plate_thickness_mm = 12
        thk_match = thk_pattern.search(text)
        if thk_match:
            val_thk = thk_match.group(1) or thk_match.group(2)
            if val_thk:
                t = int(val_thk)
                if t in (6, 8, 10, 12, 14, 16, 20, 25, 30):
                    plate_thickness_mm = t

        # Knife slots
        num_knife_slots = 1
        slot_match = blade_slot_pattern.search(text)
        if slot_match:
            slot_str = slot_match.group(1).upper()
            if slot_str in ("DOUBLE", "2"):
                num_knife_slots = 2
            elif slot_str in ("TRIPLE", "3"):
                num_knife_slots = 3
            else:
                num_knife_slots = 1

        # Dowels: diameter and count
        dowel_diameter_mm = 16
        num_dowels = 8
        dow_match = dowel_pattern.search(text)
        if dow_match:
            if dow_match.group(1) and dow_match.group(2):
                num_dowels = int(dow_match.group(1))
                dowel_diameter_mm = int(dow_match.group(2))
            elif dow_match.group(3) and dow_match.group(4):
                num_dowels = int(dow_match.group(3))
                dowel_diameter_mm = int(dow_match.group(4))
            elif dow_match.group(5):
                dowel_diameter_mm = int(dow_match.group(5))

        # Standoff height
        standoff_height_mm = 50 if element_type == "CONCEALED_COLUMN_BASE_KNIFE_PLATE" else 0
        stand_match = standoff_pattern.search(text)
        if stand_match:
            val_stand = stand_match.group(1) or stand_match.group(2)
            if val_stand:
                standoff_height_mm = int(val_stand)

        # Fire rating minutes
        fire_rating_minutes = 60
        frl_match = frl_pattern.search(text)
        if frl_match:
            val_f = frl_match.group(1) or frl_match.group(2)
            if val_f:
                val_mins = int(val_f)
                if val_mins in (1, 2):
                    fire_rating_minutes = val_mins * 60
                else:
                    fire_rating_minutes = val_mins

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
        if thk_match:
            confidence += 0.05
        if dow_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = KnifePlateCandidate(
            candidate_id=f"cand_knife_plate_{uuid4().hex[:8]}",
            element_type=element_type,
            plate_thickness_mm=plate_thickness_mm,
            num_knife_slots=num_knife_slots,
            dowel_diameter_mm=dowel_diameter_mm,
            num_dowels=num_dowels,
            fire_rating_minutes=fire_rating_minutes,
            standoff_height_mm=standoff_height_mm,
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
