"""
pb_source_foam_bladder_tank_proportioner_skid_shadow.py

Shadow candidate authority for fire protection foam-water deluge systems, bladder tanks,
ratio controllers, proportioner skids, and high-expansion foam generators.

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
class FoamBladderTankCandidate:
    candidate_id: str
    element_type: str  # VERTICAL_BLADDER_TANK_PROPORTIONER, HORIZONTAL_BLADDER_TANK_PROPORTIONER, FOAM_WATER_DELUGE_VALVE_SKID, INLINE_BALANCED_PRESSURE_PROPORTIONER, HIGH_EXPANSION_FOAM_GENERATOR
    tank_capacity_liters: int
    proportioning_ratio_percent: int
    ratio_controller_size_mm: int
    foam_concentrate_type: str  # FLUORINE_FREE_SFFF, AR_AFFF_ALCOHOL_RESISTANT, AFFF_STANDARD, HIGH_EXPANSION_DETERGENT
    design_pressure_kpa: int
    has_water_actuated_foam_valve: bool
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


def extract_foam_bladder_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[FoamBladderTankCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[FoamBladderTankCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:BLADDER\s+TANK|FOAM\s+(?:WATER\s+)?DELUGE|DELUGE\s+VALVE|FOAM\s+PROPORTIONER|PROPORTIONER(?:\s+SKID)?|FOAM\s+SKID|FOAM\s+GENERATOR|RATIO\s+CONTROLLER|FBT|FPS|FDV|HFG)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (potable water hydropneumatic expansion bladder tank, acoustic foam insulation panel)
    negative_pattern = re.compile(
        r'\b(?:DOMESTIC\s+EXPANSION\s+TANK|POTABLE\s+WATER\s+EXPANSION|ACOUSTIC\s+FOAM\s+PANEL|SPRAY\s+FOAM\s+INSULATION)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:FBT|FPS|FDV|HFG|WRP)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    cap_pattern = re.compile(
        r'\b(?:(\d{3,5})\s*L(?:ITRES?|ITERS?)?\s*(?:CAPACITY|TANK|BLADDER)?|CAPACITY\s*[:=]?\s*(\d{3,5})\s*L)\b',
        re.IGNORECASE
    )

    ratio_pattern = re.compile(
        r'\b([136])\s*%\s*(?:RATIO|PROPORTIONING|FOAM)?\b',
        re.IGNORECASE
    )

    rc_size_pattern = re.compile(
        r'\b(?:DN\s*(\d{2,3})|(\d{2,3})\s*MM\s*(?:RATIO\s*CONTROLLER|PROPORTIONER)?)\b',
        re.IGNORECASE
    )

    pressure_pattern = re.compile(
        r'\b(?:(\d{3,4})\s*KPA|(\d{2,3})\s*BAR|(\d{3})\s*PSI)\b',
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
        if "HIGH EXPANSION" in upper_text or "HFG" in upper_text:
            element_type = "HIGH_EXPANSION_FOAM_GENERATOR"
        elif "DELUGE" in upper_text or "FDV" in upper_text:
            element_type = "FOAM_WATER_DELUGE_VALVE_SKID"
        elif "BALANCED PRESSURE" in upper_text or "ILBP" in upper_text or "FPS" in upper_text:
            element_type = "INLINE_BALANCED_PRESSURE_PROPORTIONER"
        elif "HORIZONTAL" in upper_text:
            element_type = "HORIZONTAL_BLADDER_TANK_PROPORTIONER"
        else:
            element_type = "VERTICAL_BLADDER_TANK_PROPORTIONER"

        # Tank capacity in Liters
        tank_capacity_liters = 2000
        if element_type == "HIGH_EXPANSION_FOAM_GENERATOR":
            tank_capacity_liters = 0
        cap_match = cap_pattern.search(text)
        if cap_match:
            val_c = cap_match.group(1) or cap_match.group(2)
            if val_c:
                tank_capacity_liters = int(val_c)

        # Proportioning ratio % (1, 3, or 6)
        proportioning_ratio_percent = 3
        rat_match = ratio_pattern.search(text)
        if rat_match:
            proportioning_ratio_percent = int(rat_match.group(1))

        # Ratio controller size in mm
        ratio_controller_size_mm = 100
        rc_match = rc_size_pattern.search(text)
        if rc_match:
            val_rc = rc_match.group(1) or rc_match.group(2)
            if val_rc:
                rc_val = int(val_rc)
                if rc_val in (50, 65, 80, 100, 125, 150, 200, 250):
                    ratio_controller_size_mm = rc_val

        # Foam concentrate type
        if "SFFF" in upper_text or "FLUORINE-FREE" in upper_text or "FLUORINE FREE" in upper_text:
            foam_concentrate_type = "FLUORINE_FREE_SFFF"
        elif "AR-AFFF" in upper_text or "ALCOHOL RESISTANT" in upper_text:
            foam_concentrate_type = "AR_AFFF_ALCOHOL_RESISTANT"
        elif "HIGH EXP" in upper_text or element_type == "HIGH_EXPANSION_FOAM_GENERATOR":
            foam_concentrate_type = "HIGH_EXPANSION_DETERGENT"
        else:
            foam_concentrate_type = "FLUORINE_FREE_SFFF"

        # Design pressure kPa
        design_pressure_kpa = 1725  # standard 250 psi / 17.25 bar
        p_match = pressure_pattern.search(text)
        if p_match:
            if p_match.group(1):
                design_pressure_kpa = int(p_match.group(1))
            elif p_match.group(2):
                design_pressure_kpa = int(p_match.group(2)) * 100
            elif p_match.group(3):
                psi = int(p_match.group(3))
                design_pressure_kpa = int(psi * 6.89476)

        # Water actuated valve
        has_water_actuated_foam_valve = bool(
            "WATER ACTUATED" in upper_text or
            "HYDRAULIC VALVE" in upper_text or
            "CONCENTRATE VALVE" in upper_text or
            element_type in ("FOAM_WATER_DELUGE_VALVE_SKID", "VERTICAL_BLADDER_TANK_PROPORTIONER", "HORIZONTAL_BLADDER_TANK_PROPORTIONER")
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
        if cap_match:
            confidence += 0.05
        if rat_match or rc_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = FoamBladderTankCandidate(
            candidate_id=f"cand_foam_bladder_{uuid4().hex[:8]}",
            element_type=element_type,
            tank_capacity_liters=tank_capacity_liters,
            proportioning_ratio_percent=proportioning_ratio_percent,
            ratio_controller_size_mm=ratio_controller_size_mm,
            foam_concentrate_type=foam_concentrate_type,
            design_pressure_kpa=design_pressure_kpa,
            has_water_actuated_foam_valve=has_water_actuated_foam_valve,
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
