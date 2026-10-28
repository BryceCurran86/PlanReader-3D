"""
pb_source_gas_cylinder_manifold_auto_changeover_shadow.py

Shadow candidate authority for high-purity laboratory gas cylinder manifolds, automatic
changeover panels, point-of-use pressure stations, and ventilated gas cabinets.

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
class GasManifoldCandidate:
    candidate_id: str
    element_type: str  # AUTO_CHANGEOVER_GAS_MANIFOLD, MANUAL_GAS_MANIFOLD, POINT_OF_USE_REGULATOR_PANEL, TOXIC_GAS_SAFETY_CABINET, EXTERNAL_GAS_CYLINDER_CAGE
    gas_service: str  # NITROGEN, ARGON, HELIUM, HYDROGEN, OXYGEN, CARBON_DIOXIDE, SPECIALTY_MIX
    num_cylinders: int
    inlet_pressure_bar: int
    outlet_pressure_bar: int
    purity_grade: str  # GRADE_5_0, GRADE_6_0, INDUSTRIAL_COMMERCIAL
    has_auto_purge_assembly: bool
    has_alarm_annunciator: bool
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


def extract_gas_manifold_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[GasManifoldCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[GasManifoldCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:GAS\s+MANIFOLD|CHANGEOVER\s+MANIFOLD|GAS\s+CYLINDER\s+MANIFOLD|AUTO[- ]?CHANGEOVER|POINT[- ]OF[- ]USE(?:\s+REGULATOR)?|REGULATOR\s+PANEL|GAS\s+(?:SAFETY\s+)?CABINET|CYLINDER\s+CAGE|GCM|ACM|POU|GAS\s+PANEL)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (natural gas boiler meter, domestic LPG cooker bottle, medical air plant compressor)
    negative_pattern = re.compile(
        r'\b(?:NATURAL\s+GAS\s+METER|DOMESTIC\s+BBQ|BOILER\s+BURNER\s+GAS\s+TRAIN|AIR\s+COMPRESSOR\s+ONLY)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:GCM|ACM|POU|GC|MGC)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    cylinder_pattern = re.compile(
        r'\b(?:(\d{1,2})\s*[Xx]\s*(\d{1,2})\s*CYL(?:INDERS?)?|(\d{1,2})\s*CYL(?:INDERS?)?|(\d{1,2})\s*BOTTLES?)\b',
        re.IGNORECASE
    )

    pressure_inlet_pattern = re.compile(
        r'\b(?:(\d{2,3})\s*BAR\s*INLET|INLET\s*[:=]?\s*(\d{2,3})\s*BAR)\b',
        re.IGNORECASE
    )

    pressure_outlet_pattern = re.compile(
        r'\b(?:(\d{1,2})\s*BAR\s*OUTLET|OUTLET\s*[:=]?\s*(\d{1,2})\s*BAR)\b',
        re.IGNORECASE
    )

    purity_pattern = re.compile(
        r'\b(GRADE\s*5\.0|99\.999%|GRADE\s*6\.0|99\.9999%|HIGH[- ]PURITY)\b',
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
        if "CABINET" in upper_text or "TOXIC" in upper_text or "ENCLOSURE" in upper_text:
            element_type = "TOXIC_GAS_SAFETY_CABINET"
        elif "CAGE" in upper_text or "OUTDOOR" in upper_text or "STORE" in upper_text:
            element_type = "EXTERNAL_GAS_CYLINDER_CAGE"
        elif "POINT OF USE" in upper_text or "POINT-OF-USE" in upper_text or "POU" in upper_text:
            element_type = "POINT_OF_USE_REGULATOR_PANEL"
        elif "AUTO" in upper_text or "AUTOMATIC" in upper_text or "ACM" in upper_text:
            element_type = "AUTO_CHANGEOVER_GAS_MANIFOLD"
        else:
            element_type = "MANUAL_GAS_MANIFOLD"

        # Gas Service
        if "ARGON" in upper_text or " AR " in f" {upper_text} ":
            gas_service = "ARGON"
        elif "HELIUM" in upper_text or " HE " in f" {upper_text} ":
            gas_service = "HELIUM"
        elif "HYDROGEN" in upper_text or " H2 " in f" {upper_text} ":
            gas_service = "HYDROGEN"
        elif "OXYGEN" in upper_text or " O2 " in f" {upper_text} ":
            gas_service = "OXYGEN"
        elif "CARBON DIOXIDE" in upper_text or " CO2 " in f" {upper_text} ":
            gas_service = "CARBON_DIOXIDE"
        elif "NITROGEN" in upper_text or " N2 " in f" {upper_text} ":
            gas_service = "NITROGEN"
        elif "CALIBRATION" in upper_text or "SPECIALTY" in upper_text:
            gas_service = "SPECIALTY_MIX"
        else:
            gas_service = "NITROGEN"

        # Number of cylinders
        num_cylinders = 4  # default 2x2
        cyl_match = cylinder_pattern.search(text)
        if cyl_match:
            if cyl_match.group(1) and cyl_match.group(2):
                num_cylinders = int(cyl_match.group(1)) * int(cyl_match.group(2))
            elif cyl_match.group(3):
                num_cylinders = int(cyl_match.group(3))
            elif cyl_match.group(4):
                num_cylinders = int(cyl_match.group(4))

        # Inlet pressure in bar
        inlet_pressure_bar = 200
        p_in = pressure_inlet_pattern.search(text)
        if p_in:
            val_in = p_in.group(1) or p_in.group(2)
            if val_in:
                inlet_pressure_bar = int(val_in)

        # Outlet pressure in bar
        outlet_pressure_bar = 7
        p_out = pressure_outlet_pattern.search(text)
        if p_out:
            val_out = p_out.group(1) or p_out.group(2)
            if val_out:
                outlet_pressure_bar = int(val_out)

        # Purity grade
        purity_grade = "GRADE_5_0"
        pur_match = purity_pattern.search(text)
        if pur_match:
            pur_str = pur_match.group(1).upper()
            if "6.0" in pur_str or "99.9999" in pur_str:
                purity_grade = "GRADE_6_0"
            elif "5.0" in pur_str or "99.999" in pur_str or "HIGH" in pur_str:
                purity_grade = "GRADE_5_0"
            else:
                purity_grade = "INDUSTRIAL_COMMERCIAL"
        elif "INDUSTRIAL" in upper_text or "COMMERCIAL" in upper_text:
            purity_grade = "INDUSTRIAL_COMMERCIAL"

        # Purge assembly
        has_auto_purge_assembly = bool(
            "PURGE" in upper_text or
            "CROSS-PURGE" in upper_text or
            "DEEP PURGE" in upper_text or
            element_type in ("AUTO_CHANGEOVER_GAS_MANIFOLD", "TOXIC_GAS_SAFETY_CABINET")
        )

        # Alarm annunciator
        has_alarm_annunciator = bool(
            "ALARM" in upper_text or
            "ANNUNCIATOR" in upper_text or
            "TELEMETRY" in upper_text or
            "BMS" in upper_text or
            element_type == "TOXIC_GAS_SAFETY_CABINET"
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
        if cyl_match:
            confidence += 0.05
        if pur_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = GasManifoldCandidate(
            candidate_id=f"cand_gas_manifold_{uuid4().hex[:8]}",
            element_type=element_type,
            gas_service=gas_service,
            num_cylinders=num_cylinders,
            inlet_pressure_bar=inlet_pressure_bar,
            outlet_pressure_bar=outlet_pressure_bar,
            purity_grade=purity_grade,
            has_auto_purge_assembly=has_auto_purge_assembly,
            has_alarm_annunciator=has_alarm_annunciator,
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
