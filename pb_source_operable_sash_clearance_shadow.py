"""
pb_source_operable_sash_clearance_shadow.py

Authoritative shadow-mode extraction and quantification for window operable sashes,
fixed vision panels, natural ventilation free openable areas, and insect screens.

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


class SashOperationType(str, Enum):
    AWNING = "AWNING"
    CASEMENT_LH = "CASEMENT_LH"
    CASEMENT_RH = "CASEMENT_RH"
    SLIDING = "SLIDING"
    TILT_TURN = "TILT_TURN"
    LOUVRE = "LOUVRE"
    FIXED = "FIXED"


@dataclass
class OperableSashSpec:
    sash_id: str
    parent_window_id: str
    operation_type: SashOperationType
    width_mm: float
    height_mm: float
    opening_angle_deg: float = 0.0
    max_projection_mm: float = 0.0
    has_insect_screen: bool = False
    level_id: str = "L1"
    source_annotation: str = ""


@dataclass
class SashClearanceQuantities:
    total_sash_count: int
    total_operable_sash_count: int
    total_fixed_panel_count: int
    total_gross_sash_area_m2: float
    total_effective_ventilation_area_m2: float
    total_insect_screen_area_m2: float
    total_screen_count: int


@dataclass
class SashClearanceExtractionResult:
    sashes: List[OperableSashSpec]
    quantities: SashClearanceQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceOperableSashClearanceShadowAuthority:
    """Authority for analyzing window operable sashes, ventilation areas, and clearances in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def parse_sash_annotation(annotation: str) -> Tuple[SashOperationType, float, float, bool]:
        """
        Parses annotation, e.g.:
        'AWNING SASH 900W x 1200H W/ CHAIN WINDER & FLYSCREEN'
        Returns (operation_type, width_mm, height_mm, has_insect_screen)
        """
        clean = annotation.upper().strip()

        # Type detection
        if "FIXED" in clean:
            op_type = SashOperationType.FIXED
        elif "AWNING" in clean:
            op_type = SashOperationType.AWNING
        elif "CASEMENT" in clean:
            op_type = SashOperationType.CASEMENT_RH if "RH" in clean else SashOperationType.CASEMENT_LH
        elif "SLIDING" in clean or "SLIDER" in clean:
            op_type = SashOperationType.SLIDING
        elif "LOUVRE" in clean or "LOUVER" in clean:
            op_type = SashOperationType.LOUVRE
        elif "TILT" in clean:
            op_type = SashOperationType.TILT_TURN
        else:
            op_type = SashOperationType.FIXED

        # Dimensions: (\d+)\s*W\s*[xX]\s*(\d+)\s*H or (\d+)\s*[xX]\s*(\d+)
        w_match = re.search(r"(\d+)\s*W", clean)
        h_match = re.search(r"(\d+)\s*H", clean)

        if w_match and h_match:
            width_mm = float(w_match.group(1))
            height_mm = float(h_match.group(1))
        else:
            dim_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", clean)
            if dim_match:
                width_mm = float(dim_match.group(1))
                height_mm = float(dim_match.group(2))
            else:
                width_mm, height_mm = 0.0, 0.0

        # Insect screen detection
        has_screen = ("SCREEN" in clean or "FLYSCREEN" in clean) and (op_type != SashOperationType.FIXED)

        return op_type, width_mm, height_mm, has_screen

    @staticmethod
    def compute_ventilation_area(sash: OperableSashSpec) -> float:
        """
        Computes effective openable natural ventilation area in m2 according to NCC/BCA.
        """
        w_m = sash.width_mm / 1000.0
        h_m = sash.height_mm / 1000.0
        gross_area = w_m * h_m

        if sash.operation_type == SashOperationType.FIXED:
            return 0.0
        elif sash.operation_type == SashOperationType.SLIDING:
            return 0.5 * gross_area
        elif sash.operation_type in (SashOperationType.CASEMENT_LH, SashOperationType.CASEMENT_RH):
            if sash.opening_angle_deg <= 0.0:
                return 0.0
            angle_rad = math.radians(min(90.0, sash.opening_angle_deg))
            return gross_area * math.sin(angle_rad)
        elif sash.operation_type == SashOperationType.AWNING:
            proj_m = sash.max_projection_mm / 1000.0
            throat_area = proj_m * (w_m + 2.0 * h_m)
            return min(gross_area, throat_area)
        elif sash.operation_type == SashOperationType.LOUVRE:
            return 0.70 * gross_area
        elif sash.operation_type == SashOperationType.TILT_TURN:
            return 0.85 * gross_area
        return 0.0

    @classmethod
    def evaluate_sashes(cls, sashes: List[OperableSashSpec]) -> SashClearanceExtractionResult:
        total_gross_area = 0.0
        total_vent_area = 0.0
        total_screen_area = 0.0
        operable_count = 0
        fixed_count = 0
        screen_count = 0

        for s in sashes:
            w_m = s.width_mm / 1000.0
            h_m = s.height_mm / 1000.0
            sash_area = w_m * h_m
            total_gross_area += sash_area

            if s.operation_type == SashOperationType.FIXED:
                fixed_count += 1
            else:
                operable_count += 1
                vent_a = cls.compute_ventilation_area(s)
                total_vent_area += vent_a

                if s.has_insect_screen:
                    screen_count += 1
                    total_screen_area += sash_area

        quantities = SashClearanceQuantities(
            total_sash_count=len(sashes),
            total_operable_sash_count=operable_count,
            total_fixed_panel_count=fixed_count,
            total_gross_sash_area_m2=round(total_gross_area, 3),
            total_effective_ventilation_area_m2=round(total_vent_area, 3),
            total_insect_screen_area_m2=round(total_screen_area, 3),
            total_screen_count=screen_count
        )

        return SashClearanceExtractionResult(
            sashes=sashes,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "sash_count": str(len(sashes)),
                "operable_count": str(operable_count),
                "fixed_count": str(fixed_count)
            }
        )
