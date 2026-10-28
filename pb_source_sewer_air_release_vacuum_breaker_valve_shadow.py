"""
pb_source_sewer_air_release_vacuum_breaker_valve_shadow.py

Shadow candidate authority for civil sewer force main combination air valves,
vacuum breaker valves, isolation/flush assemblies, and valve chamber pits.

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
class SewerAirValveCandidate:
    candidate_id: str
    element_type: str  # SEWAGE_COMBINATION_AIR_VALVE, SEWAGE_AIR_RELEASE_VALVE, VACUUM_BREAKER_VALVE, ISOLATION_AND_FLUSH_ASSEMBLY, AIR_VALVE_CHAMBER_PIT
    valve_size_mm: int
    pressure_class_pn: int
    body_material: str  # DUCTILE_IRON_EPOXY_COATED, STAINLESS_STEEL_316, REINFORCED_NYLON_POLYMERIC
    has_odor_control_filter: bool
    has_backflush_assembly: bool
    pit_diameter_mm: int
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


def extract_sewer_air_valve_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[SewerAirValveCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[SewerAirValveCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:SEWER\s+AIR\s+VALVE|SEWAGE\s+AIR\s+VALVE|COMBINATION\s+AIR\s+VALVE|VACUUM\s+BREAKER\s+VALVE|AIR\s+RELEASE\s+VALVE|AIR\s+VALVE\s+PIT|AIR\s+VALVE|SAV|CAV|VBV|AVP)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (potable water air valve without sewage context, pneumatic solenoid, HVAC air terminal)
    negative_pattern = re.compile(
        r'\b(?:HVAC\s+AIR|DIFFUSER|PNEUMATIC\s+ACTUATOR|DOMESTIC\s+WATER\s+ONLY)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:SAV|CAV|VBV|AVP|ARV)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    dn_pattern = re.compile(
        r'\b(?:DN\s*(\d{2,3})|(\d{2,3})\s*MM\s*(?:VALVE|DIA|NB)?)\b',
        re.IGNORECASE
    )

    pn_pattern = re.compile(
        r'\b(?:PN\s*(\d{1,2})|CLASS\s*(\d{2,3}))\b',
        re.IGNORECASE
    )

    pit_dim_pattern = re.compile(
        r'\b(?:(\d{4})\s*MM\s*(?:DIA|PIT|CHAMBER)|PIT\s*[:=]?\s*(\d{4})\s*MM)\b',
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
        if "CHAMBER" in upper_text or "PIT" in upper_text or "AVP" in upper_text:
            element_type = "AIR_VALVE_CHAMBER_PIT"
        elif "VACUUM BREAKER" in upper_text or "VACUUM RELIEF" in upper_text or "VBV" in upper_text:
            element_type = "VACUUM_BREAKER_VALVE"
        elif "COMBINATION" in upper_text or "CAV" in upper_text or "NON-SLAM" in upper_text:
            element_type = "SEWAGE_COMBINATION_AIR_VALVE"
        elif "RELEASE" in upper_text or "ARV" in upper_text or "SAV" in upper_text:
            element_type = "SEWAGE_AIR_RELEASE_VALVE"
        elif "ISOLATION AND FLUSH" in upper_text or "FLUSH ASSEMBLY" in upper_text or ("ISOLATION" in upper_text and "FLUSH" in upper_text):
            element_type = "ISOLATION_AND_FLUSH_ASSEMBLY"
        else:
            element_type = "SEWAGE_COMBINATION_AIR_VALVE"

        # Valve size in mm
        valve_size_mm = 80
        dn_match = dn_pattern.search(text)
        if dn_match:
            val_dn = dn_match.group(1) or dn_match.group(2)
            if val_dn:
                val = int(val_dn)
                if val in (50, 65, 80, 100, 150, 200, 250, 300):
                    valve_size_mm = val

        # Pressure class PN
        pressure_class_pn = 16
        pn_match = pn_pattern.search(text)
        if pn_match:
            if pn_match.group(1):
                pressure_class_pn = int(pn_match.group(1))
            elif pn_match.group(2):
                cls_val = int(pn_match.group(2))
                if cls_val == 150:
                    pressure_class_pn = 20
                elif cls_val == 300:
                    pressure_class_pn = 40

        # Body material
        if "316" in upper_text or "STAINLESS" in upper_text:
            body_material = "STAINLESS_STEEL_316"
        elif "NYLON" in upper_text or "POLYMER" in upper_text or "COMPOSITE" in upper_text:
            body_material = "REINFORCED_NYLON_POLYMERIC"
        else:
            body_material = "DUCTILE_IRON_EPOXY_COATED"

        # Odor control filter
        has_odor_control_filter = bool(
            "ODOR" in upper_text or
            "ODOUR" in upper_text or
            "CARBON" in upper_text or
            "FILTER" in upper_text
        )

        # Backflush assembly
        has_backflush_assembly = bool(
            "FLUSH" in upper_text or
            "BACKFLUSH" in upper_text or
            "HOSE TAP" in upper_text or
            "RINSE" in upper_text
        )

        # Pit diameter
        pit_diameter_mm = 1200
        pit_match = pit_dim_pattern.search(text)
        if pit_match:
            val_pit = pit_match.group(1) or pit_match.group(2)
            if val_pit:
                pit_diameter_mm = int(val_pit)

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
        if dn_match:
            confidence += 0.05
        if pn_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = SewerAirValveCandidate(
            candidate_id=f"cand_sewer_air_valve_{uuid4().hex[:8]}",
            element_type=element_type,
            valve_size_mm=valve_size_mm,
            pressure_class_pn=pressure_class_pn,
            body_material=body_material,
            has_odor_control_filter=has_odor_control_filter,
            has_backflush_assembly=has_backflush_assembly,
            pit_diameter_mm=pit_diameter_mm,
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
