"""
pb_source_compressed_air_rotary_screw_dryer_skid_shadow.py

Shadow candidate authority for industrial compressed air rotary screw compressors,
refrigerated and desiccant dryers, vertical receiver vessels, and total air skids.

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
class CompressedAirCandidate:
    candidate_id: str
    element_type: str  # ROTARY_SCREW_AIR_COMPRESSOR, REFRIGERATED_AIR_DRYER, DESICCANT_AIR_DRYER, VERTICAL_AIR_RECEIVER_VESSEL, COMPACT_TOTAL_AIR_SYSTEM_SKID
    motor_power_kw: float
    free_air_delivery_l_s: int
    working_pressure_bar: float
    is_variable_speed_drive: bool
    pressure_dew_point_c: int
    receiver_volume_liters: int
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


def extract_compressed_air_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[CompressedAirCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[CompressedAirCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:AIR\s+COMPRESSOR|SCREW\s+COMPRESSOR|ROTARY\s+SCREW|AIR\s+DRYER|REFRIGERATED\s+DRYER|DESICCANT\s+DRYER|AIR\s+RECEIVER|COMPRESSED\s+AIR\s+SKID|CMP|RAD|DAD|ARV|CAS)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (HVAC DX refrigerant compressor, medical vacuum pump, diesel engine generator)
    negative_pattern = re.compile(
        r'\b(?:CHILLER\s+REFRIGERANT\s+COMPRESSOR|VRV\s+COMPRESSOR|VACUUM\s+PUMP|DIESEL\s+GENERATOR)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:CMP|RAD|DAD|ARV|AR|CAS)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    power_pattern = re.compile(
        r'\b(?:(\d{1,3}(?:\.\d)?)\s*KW|(\d{1,3})\s*HP)\b',
        re.IGNORECASE
    )

    flow_pattern = re.compile(
        r'\b(?:(\d{2,4})\s*L\s*/\s*S|(\d{2,4})\s*L/S|(\d{1,3}(?:\.\d)?)\s*M3/MIN)\b',
        re.IGNORECASE
    )

    pressure_pattern = re.compile(
        r'\b(?:(\d{1,2}(?:\.\d)?)\s*BAR|(\d{2,3})\s*PSI)\b',
        re.IGNORECASE
    )

    receiver_pattern = re.compile(
        r'\b(?:(\d{3,4})\s*L(?:ITRES?|ITERS?)?\s*(?:RECEIVER|VESSEL|TANK)?)\b',
        re.IGNORECASE
    )

    dew_point_pattern = re.compile(
        r'(?:([+-]?\d{1,2})\s*°?\s*C\s*(?:DEW\s*POINT|PDP))\b',
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
        if "SKID" in upper_text and ("TOTAL" in upper_text or "PACKAGE" in upper_text or "ALL-IN-ONE" in upper_text):
            element_type = "COMPACT_TOTAL_AIR_SYSTEM_SKID"
        elif "DESICCANT" in upper_text or "DAD" in upper_text:
            element_type = "DESICCANT_AIR_DRYER"
        elif "DRYER" in upper_text or "RAD" in upper_text or "REFRIGERATED" in upper_text:
            element_type = "REFRIGERATED_AIR_DRYER"
        elif "RECEIVER" in upper_text or "VESSEL" in upper_text or "ARV" in upper_text:
            element_type = "VERTICAL_AIR_RECEIVER_VESSEL"
        else:
            element_type = "ROTARY_SCREW_AIR_COMPRESSOR"

        # Motor power in kW
        motor_power_kw = 37.0
        p_match = power_pattern.search(text)
        if p_match:
            if p_match.group(1):
                motor_power_kw = float(p_match.group(1))
            elif p_match.group(2):
                motor_power_kw = round(float(p_match.group(2)) * 0.7457, 1)

        # Free air delivery in L/s
        free_air_delivery_l_s = 100
        f_match = flow_pattern.search(text)
        if f_match:
            if f_match.group(1) or f_match.group(2):
                val_f = f_match.group(1) or f_match.group(2)
                free_air_delivery_l_s = int(val_f)
            elif f_match.group(3):
                m3_min = float(f_match.group(3))
                free_air_delivery_l_s = int(m3_min * 1000.0 / 60.0)

        # Working pressure in bar
        working_pressure_bar = 8.0
        pres_match = pressure_pattern.search(text)
        if pres_match:
            if pres_match.group(1):
                working_pressure_bar = float(pres_match.group(1))
            elif pres_match.group(2):
                psi = float(pres_match.group(2))
                working_pressure_bar = round(psi * 0.0689476, 1)

        # VSD
        is_variable_speed_drive = bool(
            "VSD" in upper_text or
            "VFD" in upper_text or
            "VARIABLE SPEED" in upper_text or
            "INVERTER" in upper_text
        )

        # Dew point °C
        pressure_dew_point_c = 3
        if element_type == "DESICCANT_AIR_DRYER":
            pressure_dew_point_c = -40
        dp_match = dew_point_pattern.search(text)
        if dp_match:
            pressure_dew_point_c = int(dp_match.group(1))

        # Receiver volume in Liters
        receiver_volume_liters = 1000
        r_match = receiver_pattern.search(text)
        if r_match:
            val_r = int(r_match.group(1))
            if val_r in (250, 300, 500, 750, 1000, 1500, 2000, 3000, 5000):
                receiver_volume_liters = val_r

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
        if p_match:
            confidence += 0.05
        if f_match or pres_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = CompressedAirCandidate(
            candidate_id=f"cand_compressed_air_{uuid4().hex[:8]}",
            element_type=element_type,
            motor_power_kw=motor_power_kw,
            free_air_delivery_l_s=free_air_delivery_l_s,
            working_pressure_bar=working_pressure_bar,
            is_variable_speed_drive=is_variable_speed_drive,
            pressure_dew_point_c=pressure_dew_point_c,
            receiver_volume_liters=receiver_volume_liters,
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
