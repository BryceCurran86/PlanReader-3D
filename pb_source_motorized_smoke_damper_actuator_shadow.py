"""
pb_source_motorized_smoke_damper_actuator_shadow.py

Shadow candidate authority for fire life safety smoke dampers, motorized combination
fire/smoke dampers (MFSD), Class I leakage cores, and fast-acting spring-return actuators.

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
class MotorizedSmokeDamperCandidate:
    candidate_id: str
    element_type: str  # COMBINATION_FIRE_SMOKE_DAMPER, LEAKAGE_CLASS_I_SMOKE_DAMPER, MODULATING_SMOKE_CONTROL_DAMPER, FAST_ACTING_SPRING_RETURN_ACTUATOR, THERMAL_DISC_SENSOR_SLEEVE
    width_mm: int
    height_mm: int
    actuator_voltage: str  # 24V_AC_DC, 230V_AC, 120V_AC, PNEUMATIC
    leakage_class: str  # CLASS_I, CLASS_II, CLASS_III
    closure_time_sec: int
    fire_rating_minutes: int
    has_end_switches: bool
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


def extract_motorized_smoke_damper_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[MotorizedSmokeDamperCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[MotorizedSmokeDamperCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:SMOKE\s+DAMPER|FIRE\s+SMOKE\s+DAMPER|FIRE\s+DAMPER|CONTROL\s+DAMPER|MOTORIZED\s+DAMPER|MFSD|FSD|SCD|TSD|DAMPER\s+ACTUATOR)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (gravity backdraft damper, manual volume control damper, acoustic attenuator)
    negative_pattern = re.compile(
        r'\b(?:GRAVITY\s+BACKDRAFT\s+DAMPER|MANUAL\s+VOLUME\s+DAMPER|VCD\s+ONLY|ACOUSTIC\s+ATTENUATOR)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:MFSD|FSD|SD|SCD|TSD|ACT)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    dim_pattern = re.compile(
        r'\b(?:(\d{2,4})\s*[Xx]\s*(\d{2,4})\s*MM|(\d{2,4})\s*MM\s*DIA)\b',
        re.IGNORECASE
    )

    frl_pattern = re.compile(
        r'\b(?:(-?/?\d{2,3}/\d{2,3})|(\d{2,3})\s*(?:MIN|MINUTES|HR|HOUR)\s*FIRE)\b',
        re.IGNORECASE
    )

    time_pattern = re.compile(
        r'\b(?:(\d{1,2})\s*SEC(?:ONDS)?)\b',
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
        if "ACTUATOR ONLY" in upper_text or ("DAMPER ACTUATOR" in upper_text and "DAMPER" not in upper_text.replace("DAMPER ACTUATOR", "")):
            element_type = "FAST_ACTING_SPRING_RETURN_ACTUATOR"
        elif "THERMAL DISC" in upper_text or "TSD" in upper_text or "SENSOR SLEEVE" in upper_text:
            element_type = "THERMAL_DISC_SENSOR_SLEEVE"
        elif "MODULATING" in upper_text or "SCD" in upper_text:
            element_type = "MODULATING_SMOKE_CONTROL_DAMPER"
        elif "CLASS I" in upper_text or "CLASS 1" in upper_text or ("SMOKE DAMPER" in upper_text and "FIRE" not in upper_text):
            element_type = "LEAKAGE_CLASS_I_SMOKE_DAMPER"
        else:
            element_type = "COMBINATION_FIRE_SMOKE_DAMPER"

        # Dimensions: width_mm & height_mm
        width_mm = 450
        height_mm = 450
        dim_match = dim_pattern.search(text)
        if dim_match:
            if dim_match.group(1) and dim_match.group(2):
                width_mm = int(dim_match.group(1))
                height_mm = int(dim_match.group(2))
            elif dim_match.group(3):
                dia = int(dim_match.group(3))
                width_mm = dia
                height_mm = dia

        # Actuator voltage
        if "230V" in upper_text or "240V" in upper_text:
            actuator_voltage = "230V_AC"
        elif "120V" in upper_text:
            actuator_voltage = "120V_AC"
        elif "PNEUMATIC" in upper_text:
            actuator_voltage = "PNEUMATIC"
        else:
            actuator_voltage = "24V_AC_DC"

        # Leakage class
        if "CLASS II" in upper_text or "CLASS 2" in upper_text:
            leakage_class = "CLASS_II"
        elif "CLASS III" in upper_text or "CLASS 3" in upper_text:
            leakage_class = "CLASS_III"
        else:
            leakage_class = "CLASS_I"

        # Closure time sec
        closure_time_sec = 15
        t_match = time_pattern.search(text)
        if t_match:
            closure_time_sec = int(t_match.group(1))

        # Fire rating minutes
        fire_rating_minutes = 120
        frl_match = frl_pattern.search(text)
        if frl_match:
            if frl_match.group(1):
                # e.g. -/120/120 or 120/120
                parts = frl_match.group(1).replace("-", "").split("/")
                nums = [int(p) for p in parts if p.isdigit()]
                if nums:
                    fire_rating_minutes = max(nums)
            elif frl_match.group(2):
                val_hr = int(frl_match.group(2))
                if val_hr in (1, 2, 3, 4):
                    fire_rating_minutes = val_hr * 60
                else:
                    fire_rating_minutes = val_hr

        if element_type == "LEAKAGE_CLASS_I_SMOKE_DAMPER" and "FIRE" not in upper_text:
            fire_rating_minutes = 0

        # End switches
        has_end_switches = bool(
            "SWITCH" in upper_text or
            "AUX" in upper_text or
            "FEEDBACK" in upper_text or
            "MONITOR" in upper_text or
            "BMS" in upper_text or
            "FIP" in upper_text
        )
        if not has_end_switches and element_type in ("COMBINATION_FIRE_SMOKE_DAMPER", "LEAKAGE_CLASS_I_SMOKE_DAMPER"):
            has_end_switches = True  # Standard life safety requirement

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
        if frl_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = MotorizedSmokeDamperCandidate(
            candidate_id=f"cand_smoke_damper_{uuid4().hex[:8]}",
            element_type=element_type,
            width_mm=width_mm,
            height_mm=height_mm,
            actuator_voltage=actuator_voltage,
            leakage_class=leakage_class,
            closure_time_sec=closure_time_sec,
            fire_rating_minutes=fire_rating_minutes,
            has_end_switches=has_end_switches,
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
