"""Source Fire Sprinkler Alarm Check Valve & Water Motor Gong Shadow Authority.

Extracts candidate fire sprinkler alarm check valves, retard chambers, water motor gongs,
drain connections, and pressure switches from fire protection service plans.
Operates strictly in shadow candidate mode (non-commercial, non-takeoff).
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT = 2.5
MAX_PRIMITIVES_SAFETY_CAP = 20000


@dataclass
class SprinklerAlarmValveCandidate:
    candidate_id: str
    sheet_id: str
    valve_configuration: str
    valve_size_mm: float
    water_motor_gong_present: bool
    retard_chamber_present: bool
    pressure_switch_present: bool
    main_drain_size_mm: float
    working_pressure_kpa: float
    position: Optional[Tuple[float, float]] = None
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "sheet_id": self.sheet_id,
            "valve_configuration": self.valve_configuration,
            "valve_size_mm": self.valve_size_mm,
            "water_motor_gong_present": self.water_motor_gong_present,
            "retard_chamber_present": self.retard_chamber_present,
            "pressure_switch_present": self.pressure_switch_present,
            "main_drain_size_mm": self.main_drain_size_mm,
            "working_pressure_kpa": self.working_pressure_kpa,
            "position": self.position,
            "status": self.status,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def snap_point(pt: Tuple[float, float], snap_tol: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
    x, y = pt
    return (round(x / snap_tol) * snap_tol, round(y / snap_tol) * snap_tol)


def parse_sprinkler_alarm_valve_callout(text: str) -> Optional[Dict[str, Any]]:
    clean = text.strip()
    upper = clean.upper()

    triggers = [
        "ALARM CHECK VALVE",
        "WET ALARM VALVE",
        "WATER MOTOR GONG",
        "SPRINKLER ALARM VALVE",
        "RETARD CHAMBER",
        "SPRINKLER CONTROL VALVE",
        "MOTOR GONG",
        "ALARM VALVE",
    ]
    if not any(t in upper for t in triggers):
        return None

    # Retard chamber
    retard_present = any(k in upper for k in ["RETARD", "RETARD CHAMBER", "VARIABLE PRESSURE"])
    valve_config = "VARIABLE_PRESSURE_RETARD" if retard_present else "CONSTANT_PRESSURE"

    # Main drain size (e.g. "DN50 DRAIN", "50MM DRAIN")
    drain_match = re.search(r"\b(?:DN|DRAIN\s*)(\d{2})\s*(?:DRAIN)?\b", upper)
    drain_size = float(drain_match.group(1)) if drain_match else 50.0

    # Valve size (e.g. "DN150", "150MM", "100MM", "DN100", "200MM") excluding drain callouts
    upper_no_drain = re.sub(r"\b(?:DN\s*\d{2}|\d{2}\s*MM)?\s*DRAIN\b", "", upper)
    dn_match = re.search(r"\bDN(\d{2,3})\b", upper_no_drain)
    mm_match = re.search(r"\b(\d{2,3})\s*MM\s*(?:ALARM|VALVE|RISER)?", upper_no_drain)
    if dn_match:
        valve_size = float(dn_match.group(1))
    elif mm_match:
        valve_size = float(mm_match.group(1))
    else:
        valve_size = 150.0

    # Water motor alarm gong
    gong_present = any(k in upper for k in ["GONG", "WATER MOTOR", "HYDRAULIC ALARM", "ALARM GONG"])

    # Pressure switch (e.g. "PRESSURE SWITCH", "PS", "FIP INTERFACE")
    ps_present = any(k in upper for k in ["PRESSURE SWITCH", "ALARM SWITCH", "FIP INTERFACE", "FLOW SWITCH"])

    # Working pressure (e.g. "1200 KPA", "1400KPA", "175 PSI")
    kpa_match = re.search(r"\b(\d{3,4})\s*KPA\b", upper)
    psi_match = re.search(r"\b(\d{3})\s*PSI\b", upper)
    if kpa_match:
        working_press = float(kpa_match.group(1))
    elif psi_match:
        working_press = round(float(psi_match.group(1)) * 6.89476, 0)
    else:
        working_press = 1200.0

    return {
        "raw_text": clean,
        "valve_configuration": valve_config,
        "valve_size_mm": valve_size,
        "water_motor_gong_present": gong_present,
        "retard_chamber_present": retard_present,
        "pressure_switch_present": ps_present,
        "main_drain_size_mm": drain_size,
        "working_pressure_kpa": working_press,
    }


def evaluate_fire_sprinkler_alarm_valve_gong_shadow(
    sheet_id: str,
    callouts: List[str],
    positions: Optional[List[Tuple[float, float]]] = None,
    max_primitives: int = MAX_PRIMITIVES_SAFETY_CAP,
) -> List[SprinklerAlarmValveCandidate]:
    candidates = []
    pts = positions or []

    for i, callout in enumerate(callouts):
        if len(candidates) >= max_primitives:
            break
        parsed = parse_sprinkler_alarm_valve_callout(callout)
        if not parsed:
            continue

        raw_pos = pts[i] if i < len(pts) else None
        snapped_pos = snap_point(raw_pos) if raw_pos else None

        cid = f"{sheet_id}_avg_{i+1:03d}"
        cand = SprinklerAlarmValveCandidate(
            candidate_id=cid,
            sheet_id=sheet_id,
            valve_configuration=parsed["valve_configuration"],
            valve_size_mm=parsed["valve_size_mm"],
            water_motor_gong_present=parsed["water_motor_gong_present"],
            retard_chamber_present=parsed["retard_chamber_present"],
            pressure_switch_present=parsed["pressure_switch_present"],
            main_drain_size_mm=parsed["main_drain_size_mm"],
            working_pressure_kpa=parsed["working_pressure_kpa"],
            position=snapped_pos,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
        )
        candidates.append(cand)

    return candidates
