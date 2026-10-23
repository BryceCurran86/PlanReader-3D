"""
pb_source_parapet_capping_flashing_shadow.py

Authoritative shadow-mode extraction and linear/area quantification for parapet wall
capping flashing, waterproof membrane upstands, and counter-flashing reglets.

Non-negotiable constraints:
- Status: CANDIDATE
- commercial_projection_allowed: False
- takeoff_eligible: False
- Global snap tolerance: 2.5 pt
"""

from dataclasses import dataclass, field
from enum import Enum
import math
import re
from typing import Dict, List, Optional, Tuple

SNAP_TOLERANCE_PT: float = 2.5


class CappingMaterial(str, Enum):
    COLORBOND_STEEL = "COLORBOND_STEEL"
    ALUMINIUM = "ALUMINIUM"
    COPPER = "COPPER"
    ZINC = "ZINC"
    PRECAST_CONCRETE = "PRECAST_CONCRETE"
    NATURAL_STONE = "NATURAL_STONE"
    UNKNOWN = "UNKNOWN"


@dataclass
class ParapetSegmentSpec:
    segment_id: str
    centerline_points: List[Tuple[float, float]]
    wall_thickness_mm: float = 0.0
    upstand_height_mm: float = 0.0
    capping_material: CappingMaterial = CappingMaterial.UNKNOWN
    capping_girth_mm: float = 0.0
    membrane_turnup_height_mm: float = 0.0
    has_drip_groove: bool = False
    level_id: str = "ROOF"
    source_callout: str = ""


@dataclass
class ParapetQuantities:
    total_parapet_length_m: float
    total_capping_flashing_length_m: float
    total_capping_sheet_area_m2: float
    total_membrane_upstand_area_m2: float
    total_counterflashing_length_m: float


@dataclass
class ParapetExtractionResult:
    segments: List[ParapetSegmentSpec]
    quantities: ParapetQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceParapetCappingFlashingShadowAuthority:
    """Authority for analyzing roof parapet capping, flashings, and membrane upstands in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def compute_polyline_length(points: List[Tuple[float, float]]) -> float:
        if len(points) < 2:
            return 0.0
        total = 0.0
        for i in range(len(points) - 1):
            total += math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        return total

    @staticmethod
    def parse_parapet_annotation(annotation: str) -> Tuple[CappingMaterial, float, float, float, float]:
        """
        Parses text annotation, e.g.:
        'PARAPET 200THK x 750H COLORBOND CAPPING 450 GIRTH W/ 250 MEMBRANE UPSTAND'
        Returns (capping_material, wall_thickness_mm, upstand_height_mm, capping_girth_mm, membrane_turnup_mm)
        """
        clean = annotation.upper().strip()

        # Material detection
        if "COLORBOND" in clean:
            mat = CappingMaterial.COLORBOND_STEEL
        elif "ALUMINIUM" in clean or "ALUM" in clean:
            mat = CappingMaterial.ALUMINIUM
        elif "ZINC" in clean:
            mat = CappingMaterial.ZINC
        elif "COPPER" in clean:
            mat = CappingMaterial.COPPER
        elif "PRECAST" in clean or "CONCRETE" in clean:
            mat = CappingMaterial.PRECAST_CONCRETE
        elif "STONE" in clean:
            mat = CappingMaterial.NATURAL_STONE
        else:
            mat = CappingMaterial.UNKNOWN

        # Wall thickness
        thk_match = re.search(r"(\d+)\s*(?:THK|THICK|W\b)", clean)
        thickness_mm = float(thk_match.group(1)) if thk_match else 0.0

        # Upstand height
        h_match = re.search(r"(\d+)\s*(?:H\b|HIGH|HEIGHT|UPSTAND)", clean)
        upstand_height_mm = float(h_match.group(1)) if h_match else 0.0

        # Capping girth
        girth_match = re.search(r"(\d+)\s*(?:GIRTH|DEVELOPMENT|GRT)", clean)
        capping_girth_mm = float(girth_match.group(1)) if girth_match else 0.0

        # Membrane turnup
        turnup_match = re.search(r"(\d+)\s*(?:MEMBRANE|TURNUP|UPSTAND\s*MEM)", clean)
        membrane_turnup_mm = float(turnup_match.group(1)) if turnup_match else 0.0

        return mat, thickness_mm, upstand_height_mm, capping_girth_mm, membrane_turnup_mm

    @classmethod
    def evaluate_parapets(
        cls,
        segments: List[ParapetSegmentSpec],
        drawing_scale: float = 1.0  # units in drawing points/mm to real meters conversion
    ) -> ParapetExtractionResult:
        """
        Evaluates total linear lengths and surface areas for capping, waterproofing membrane,
        and counter-flashing reglets.
        """
        total_parapet_length_m = 0.0
        total_capping_length_m = 0.0
        total_capping_area_m2 = 0.0
        total_membrane_area_m2 = 0.0
        total_counterflashing_m = 0.0

        for seg in segments:
            raw_len = cls.compute_polyline_length(seg.centerline_points)
            len_m = raw_len * drawing_scale

            total_parapet_length_m += len_m
            total_capping_length_m += len_m

            girth_m = seg.capping_girth_mm / 1000.0
            total_capping_area_m2 += len_m * girth_m

            turnup_m = seg.membrane_turnup_height_mm / 1000.0
            total_membrane_area_m2 += len_m * turnup_m

            total_counterflashing_m += len_m

        quantities = ParapetQuantities(
            total_parapet_length_m=round(total_parapet_length_m, 3),
            total_capping_flashing_length_m=round(total_capping_length_m, 3),
            total_capping_sheet_area_m2=round(total_capping_area_m2, 3),
            total_membrane_upstand_area_m2=round(total_membrane_area_m2, 3),
            total_counterflashing_length_m=round(total_counterflashing_m, 3)
        )

        return ParapetExtractionResult(
            segments=segments,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"segment_count": str(len(segments))}
        )
