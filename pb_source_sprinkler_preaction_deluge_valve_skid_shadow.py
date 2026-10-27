"""
pb_source_sprinkler_preaction_deluge_valve_skid_shadow.py

Shadow candidate authority for automatic sprinkler system pre-action and deluge
valve skids, trim stations, and release manifolds.

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
class PreactionDelugeValveCandidate:
    candidate_id: str
    element_type: str  # SINGLE_INTERLOCK_PREACTION, DOUBLE_INTERLOCK_PREACTION, NON_INTERLOCK_PREACTION, DELUGE_VALVE_SKID, PREACTION_TRIM_STATION
    valve_size_mm: int
    actuation_type: str  # ELECTRIC_PNEUMATIC, ELECTRIC_ONLY, PNEUMATIC_ONLY, HYDRAULIC, MANUAL_EMERGENCY
    supervisory_gas: str  # NITROGEN, COMPRESSED_AIR, NONE
    pressure_rating_kpa: int
    has_solenoid_release: bool
    has_air_maintenance_device: bool
    has_water_motor_alarm_gong: bool
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


def extract_preaction_deluge_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[PreactionDelugeValveCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[PreactionDelugeValveCandidate] = []

    # Keywords for preaction / deluge systems
    keyword_pattern = re.compile(
        r'\b(?:PRE[- ]?ACTION|DELUGE|SINGLE[- ]INTERLOCK|DOUBLE[- ]INTERLOCK|NON[- ]INTERLOCK|PAV|DEL[- ]?SKID)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (domestic PRV, backflow preventer without deluge, standard wet alarm check valve)
    negative_pattern = re.compile(
        r'\b(?:DOMESTIC\s+WATER|PRESSURE\s+REDUCING\s+VALVE\s+ONLY|BACKFLOW\s+PREVENTER\s+RPZ|STANDARD\s+WET\s+ALARM\s+VALVE\s+ONLY)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:PAV|DEL|PA|DVS)[-_][A-Z0-9]{1,4})\b',
        re.IGNORECASE
    )

    dn_pattern = re.compile(
        r'\b(?:DN\s*(\d{2,3})|(\d{2,3})\s*MM|([1-8])\s*(?:INCH|\"))\b',
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
        if "DOUBLE INTERLOCK" in upper_text or "DOUBLE-INTERLOCK" in upper_text:
            element_type = "DOUBLE_INTERLOCK_PREACTION"
        elif "SINGLE INTERLOCK" in upper_text or "SINGLE-INTERLOCK" in upper_text:
            element_type = "SINGLE_INTERLOCK_PREACTION"
        elif "NON INTERLOCK" in upper_text or "NON-INTERLOCK" in upper_text:
            element_type = "NON_INTERLOCK_PREACTION"
        elif "DELUGE" in upper_text or "DEL-" in upper_text or "DEL " in upper_text or "DVS" in upper_text:
            element_type = "DELUGE_VALVE_SKID"
        elif "PREACTION" in upper_text or "PRE-ACTION" in upper_text or "PAV" in upper_text:
            element_type = "PREACTION_TRIM_STATION"
        else:
            element_type = "PREACTION_TRIM_STATION"

        # Valve size in mm
        # Default DN100 (100mm / 4 inch)
        valve_size_mm = 100
        size_match = dn_pattern.search(text)
        if size_match:
            if size_match.group(1):
                valve_size_mm = int(size_match.group(1))
            elif size_match.group(2):
                val = int(size_match.group(2))
                if val in (40, 50, 65, 80, 100, 125, 150, 200, 250):
                    valve_size_mm = val
            elif size_match.group(3):
                inch = int(size_match.group(3))
                inch_map = {1: 25, 2: 50, 3: 80, 4: 100, 6: 150, 8: 200}
                valve_size_mm = inch_map.get(inch, inch * 25)

        # Actuation type
        if "ELECTRIC" in upper_text and "PNEUMATIC" in upper_text:
            actuation_type = "ELECTRIC_PNEUMATIC"
        elif "ELECTRIC" in upper_text or "SOLENOID" in upper_text:
            actuation_type = "ELECTRIC_ONLY"
        elif "PNEUMATIC" in upper_text or "AIR RELEASE" in upper_text:
            actuation_type = "PNEUMATIC_ONLY"
        elif "HYDRAULIC" in upper_text:
            actuation_type = "HYDRAULIC"
        elif "MANUAL" in upper_text:
            actuation_type = "MANUAL_EMERGENCY"
        else:
            # Default for double interlock is electric/pneumatic, single interlock is electric
            if element_type == "DOUBLE_INTERLOCK_PREACTION":
                actuation_type = "ELECTRIC_PNEUMATIC"
            elif element_type == "SINGLE_INTERLOCK_PREACTION":
                actuation_type = "ELECTRIC_ONLY"
            else:
                actuation_type = "ELECTRIC_PNEUMATIC"

        # Supervisory gas
        if "NITROGEN" in upper_text or " N2 " in f" {upper_text} ":
            supervisory_gas = "NITROGEN"
        elif "AIR" in upper_text or "PNEUMATIC" in upper_text or "COMPRESSOR" in upper_text:
            supervisory_gas = "COMPRESSED_AIR"
        elif element_type == "DELUGE_VALVE_SKID":
            supervisory_gas = "NONE"
        else:
            supervisory_gas = "COMPRESSED_AIR"

        # Pressure rating
        pressure_rating_kpa = 1725  # default 250 psi / 17.25 bar
        pres_match = pressure_pattern.search(text)
        if pres_match:
            if pres_match.group(1):
                pressure_rating_kpa = int(pres_match.group(1))
            elif pres_match.group(2):
                pressure_rating_kpa = int(pres_match.group(2)) * 100
            elif pres_match.group(3):
                psi = int(pres_match.group(3))
                pressure_rating_kpa = int(psi * 6.89476)

        # Ancillaries
        has_solenoid_release = bool(
            "SOLENOID" in upper_text or
            "24V" in upper_text or
            "ELECTRIC" in upper_text or
            actuation_type in ("ELECTRIC_ONLY", "ELECTRIC_PNEUMATIC")
        )

        has_air_maintenance_device = bool(
            "AIR MAINTENANCE" in upper_text or
            "AMD" in upper_text or
            "PRESSURE REGULATOR" in upper_text or
            supervisory_gas in ("COMPRESSED_AIR", "NITROGEN")
        )

        has_water_motor_alarm_gong = bool(
            "GONG" in upper_text or
            "WATER MOTOR" in upper_text or
            "ALARM GONG" in upper_text or
            "WMAG" in upper_text
        )

        # Tag
        tag = None
        tag_match = tag_pattern.search(text)
        if tag_match:
            tag = tag_match.group(1).upper()

        x = float(prim.get("x", 0.0))
        y = float(prim.get("y", 0.0))
        snapped_pt = snap_point_to_grid(x, y, tolerance)

        # Confidence calculation
        confidence = 0.85
        if tag:
            confidence += 0.05
        if size_match:
            confidence += 0.05
        if pres_match:
            confidence += 0.05
        confidence = min(0.99, round(confidence, 2))

        candidate = PreactionDelugeValveCandidate(
            candidate_id=f"cand_preaction_deluge_{uuid4().hex[:8]}",
            element_type=element_type,
            valve_size_mm=valve_size_mm,
            actuation_type=actuation_type,
            supervisory_gas=supervisory_gas,
            pressure_rating_kpa=pressure_rating_kpa,
            has_solenoid_release=has_solenoid_release,
            has_air_maintenance_device=has_air_maintenance_device,
            has_water_motor_alarm_gong=has_water_motor_alarm_gong,
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
