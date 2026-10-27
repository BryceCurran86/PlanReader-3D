"""
pb_source_retaining_wall_geocomposite_strip_drain_shadow.py

Shadow candidate authority for civil retaining wall perforated corrugated strip drains,
geocomposite sheet drainage, agricultural slotted pipes, and weephole assemblies.

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
class StripDrainCandidate:
    candidate_id: str
    element_type: str  # GEOCOMPOSITE_DIMPLE_SHEET, PERFORATED_STRIP_DRAIN, AGRICULTURAL_AG_PIPE, DISCHARGE_WEEPHOLE_ASSEMBLY, COLLECTOR_DISCHARGE_OUTLET
    width_mm: int
    core_thickness_mm: int
    filter_fabric: str  # NON_WOVEN_GEOTEXTILE, WOVEN_MONOFILAMENT, POLYESTER_FILTER_SOCK, NONE
    flow_capacity_l_min_m: int
    compressive_strength_kpa: int
    installation_orientation: str  # VERTICAL_WALL, HORIZONTAL_DECK, SLOPE_TO_INVERT
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


def extract_strip_drain_candidates(
    primitives: List[Dict[str, Any]],
    tolerance: float = SNAP_TOLERANCE_PT
) -> List[StripDrainCandidate]:
    if len(primitives) > MAX_SAFETY_CAP_PRIMITIVES:
        raise ValueError(f"Exceeded safety cap of {MAX_SAFETY_CAP_PRIMITIVES} primitives")

    candidates: List[StripDrainCandidate] = []

    keyword_pattern = re.compile(
        r'\b(?:STRIP[- ]?DRAIN|GEOCOMPOSITE|DIMPLE(?:D)?\s+SHEET|DRAINAGE\s+CELL|MIRADRAIN|MEGAFLO|AG[- ]?PIPE|SLOTTED\s+PIPE|WEEP[- ]?HOLE|SUBSOIL)\b',
        re.IGNORECASE
    )

    # Negative lookalikes (floor waste strip drain, electrical trench duct, roof gutter)
    negative_pattern = re.compile(
        r'\b(?:SHOWER\s+STRIP\s+DRAIN|BATHROOM\s+DRAIN|LINEAR\s+SHOWER|ROOF\s+GUTTER|ELECTRICAL\s+TRENCH)\b',
        re.IGNORECASE
    )

    tag_pattern = re.compile(
        r'\b((?:SD|GCS|AG|AGP|WEEP|DC)[-_](?:[0-9]+|[A-Z]{1,2}\d+|\d+[A-Z]{1,2}))\b',
        re.IGNORECASE
    )

    dim_pattern = re.compile(
        r'\b(?:(\d{2,4})\s*MM\s*(?:WIDE|WIDTH)?|(\d{1,2})\s*MM\s*(?:THICK|CORE)?)\b',
        re.IGNORECASE
    )

    flow_pattern = re.compile(
        r'\b(?:(\d{2,4})\s*L\s*/\s*(?:MIN|M)|(\d{2,4})\s*L/MIN)\b',
        re.IGNORECASE
    )

    strength_pattern = re.compile(
        r'\b(?:(\d{3,4})\s*KPA)\b',
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
        if "DIMPLE" in upper_text or "MIRADRAIN" in upper_text or "GEOCOMPOSITE SHEET" in upper_text:
            element_type = "GEOCOMPOSITE_DIMPLE_SHEET"
        elif "WEEP" in upper_text:
            element_type = "DISCHARGE_WEEPHOLE_ASSEMBLY"
        elif "AG PIPE" in upper_text or "AG-PIPE" in upper_text or "SLOTTED PIPE" in upper_text or "AGP" in upper_text:
            element_type = "AGRICULTURAL_AG_PIPE"
        elif "OUTLET" in upper_text or "DISCHARGE ADAPTOR" in upper_text or "CONNECTOR" in upper_text:
            element_type = "COLLECTOR_DISCHARGE_OUTLET"
        elif "STRIP DRAIN" in upper_text or "STRIP-DRAIN" in upper_text or "MEGAFLO" in upper_text or "SD" in upper_text:
            element_type = "PERFORATED_STRIP_DRAIN"
        else:
            element_type = "GEOCOMPOSITE_DIMPLE_SHEET"

        # Dimensions: width_mm & core_thickness_mm
        # Defaults
        if element_type == "GEOCOMPOSITE_DIMPLE_SHEET":
            width_mm = 1200
            core_thickness_mm = 10
        elif element_type == "PERFORATED_STRIP_DRAIN":
            width_mm = 300
            core_thickness_mm = 18
        elif element_type == "AGRICULTURAL_AG_PIPE":
            width_mm = 100  # pipe diameter represented as width
            core_thickness_mm = 100
        elif element_type == "DISCHARGE_WEEPHOLE_ASSEMBLY":
            width_mm = 50
            core_thickness_mm = 50
        else:
            width_mm = 150
            core_thickness_mm = 20

        # Scan for explicit width / thickness
        for match in dim_pattern.finditer(text):
            val_wide = match.group(1)
            val_thick = match.group(2)
            if val_wide:
                w = int(val_wide)
                if w in (50, 65, 90, 100, 150, 170, 300, 450, 600, 900, 1000, 1200, 2000, 2400):
                    width_mm = w
            if val_thick:
                t = int(val_thick)
                if t in (4, 8, 10, 12, 15, 18, 20, 25, 30):
                    core_thickness_mm = t

        # Filter fabric
        if "SOCK" in upper_text or "SLEEVE" in upper_text:
            filter_fabric = "POLYESTER_FILTER_SOCK"
        elif "WOVEN" in upper_text and "NON" not in upper_text:
            filter_fabric = "WOVEN_MONOFILAMENT"
        elif "NO FABRIC" in upper_text or "BARE" in upper_text or element_type == "DISCHARGE_WEEPHOLE_ASSEMBLY":
            filter_fabric = "NONE"
        else:
            filter_fabric = "NON_WOVEN_GEOTEXTILE"

        # Flow capacity
        flow_capacity_l_min_m = 250
        f_match = flow_pattern.search(text)
        if f_match:
            val_f = f_match.group(1) or f_match.group(2)
            if val_f:
                flow_capacity_l_min_m = int(val_f)

        # Compressive strength
        compressive_strength_kpa = 600
        s_match = strength_pattern.search(text)
        if s_match:
            compressive_strength_kpa = int(s_match.group(1))

        # Installation orientation
        if "HORIZONTAL" in upper_text or "PLAZA" in upper_text or "ROOF DECK" in upper_text or "PODIUM" in upper_text:
            installation_orientation = "HORIZONTAL_DECK"
        elif "INVERT" in upper_text or "TRENCH" in upper_text or "FOOTING" in upper_text:
            installation_orientation = "SLOPE_TO_INVERT"
        else:
            installation_orientation = "VERTICAL_WALL"

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
        if s_match:
            confidence += 0.05
        if f_match:
            confidence += 0.04
        confidence = min(0.99, round(confidence, 2))

        candidate = StripDrainCandidate(
            candidate_id=f"cand_strip_drain_{uuid4().hex[:8]}",
            element_type=element_type,
            width_mm=width_mm,
            core_thickness_mm=core_thickness_mm,
            filter_fabric=filter_fabric,
            flow_capacity_l_min_m=flow_capacity_l_min_m,
            compressive_strength_kpa=compressive_strength_kpa,
            installation_orientation=installation_orientation,
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
