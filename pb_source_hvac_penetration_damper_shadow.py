"""
pb_source_hvac_penetration_damper_shadow.py

Authoritative shadow-mode extraction and quantification for mechanical HVAC ductwork
penetrations, fire/smoke damper sleeves, retaining mounting flanges, and annular
firestop mortar packing volumes.

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


class PenetratedElementKind(str, Enum):
    WALL_PARTITION = "WALL_PARTITION"
    FLOOR_SLAB = "FLOOR_SLAB"


class DuctProfileShape(str, Enum):
    UNKNOWN = "UNKNOWN"
    RECTANGULAR = "RECTANGULAR"
    CIRCULAR = "CIRCULAR"


@dataclass
class FireDamperSpec:
    damper_id: str
    penetrated_element: PenetratedElementKind
    duct_shape: DuctProfileShape
    location: Tuple[float, float]
    width_mm: float = 0.0
    height_mm: float = 0.0
    element_thickness_mm: float = 0.0
    sleeve_extension_mm: float = 0.0
    annular_gap_mm: float = 0.0
    frl_rating: str = ""
    is_motorized: bool = False
    level_id: str = "L1"
    source_tag: str = ""


@dataclass
class HVACPenetrationQuantities:
    total_damper_count: int
    total_duct_airflow_area_m2: float
    total_rough_opening_area_m2: float
    total_retaining_flange_length_m: float
    total_firestop_mortar_volume_m3: float


@dataclass
class HVACPenetrationExtractionResult:
    dampers: List[FireDamperSpec]
    quantities: HVACPenetrationQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceHVACPenetrationDamperShadowAuthority:
    """Authority for analyzing HVAC fire dampers and partition penetrations in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def parse_damper_annotation(annotation: str) -> Tuple[DuctProfileShape, float, float, str, bool]:
        """
        Parses annotation, e.g.:
        'FIRE DAMPER 600W x 400H FRL -/120/120 MOTORIZED' or 'CIRCULAR FD 300 DIA FRL -/60/60'
        Returns (shape, width_or_dia_mm, height_mm, frl, is_motorized)
        """
        clean = annotation.upper().strip()

        # Shape detection
        is_circ = "CIRCULAR" in clean or "DIA" in clean or "ROUND" in clean
        dim_match = re.search(r"(\d+)\s*(?:W)?\s*[xX]\s*(\d+)\s*(?:H)?", clean)
        if is_circ:
            shape = DuctProfileShape.CIRCULAR
        elif "RECT" in clean or dim_match is not None:
            shape = DuctProfileShape.RECTANGULAR
        else:
            shape = DuctProfileShape.UNKNOWN

        # Motorized
        is_mot = "MOTOR" in clean or "MOT" in clean or "FSD" in clean

        # FRL
        frl_match = re.search(r"FRL\s*([-\d/]+)", clean)
        frl = frl_match.group(1) if frl_match else ""

        # Dimensions: (\d+)\s*[xX]\s*(\d+) or (\d+)\s*W\s*[xX]\s*(\d+)\s*H or (\d+)\s*DIA
        if is_circ:
            dia_match = re.search(r"(\d+)\s*(?:DIA|MM)", clean)
            dia = float(dia_match.group(1)) if dia_match else 0.0
            return shape, dia, dia, frl, is_mot
        else:
            if dim_match:
                w = float(dim_match.group(1))
                h = float(dim_match.group(2))
            else:
                w, h = 0.0, 0.0
            return shape, w, h, frl, is_mot

    @classmethod
    def evaluate_dampers(cls, dampers: List[FireDamperSpec]) -> HVACPenetrationExtractionResult:
        total_airflow_area_m2 = 0.0
        total_opening_area_m2 = 0.0
        total_flange_len_m = 0.0
        total_firestop_vol_m3 = 0.0

        for d in dampers:
            g_m = d.annular_gap_mm / 1000.0
            t_m = d.element_thickness_mm / 1000.0

            if d.duct_shape == DuctProfileShape.CIRCULAR:
                r_m = (d.width_mm / 2000.0)
                duct_area = math.pi * r_m * r_m
                total_airflow_area_m2 += duct_area

                ro_r_m = r_m + g_m
                opening_area = math.pi * ro_r_m * ro_r_m
                total_opening_area_m2 += opening_area

                # Flange ring perimeter on 2 faces = 2 * (2 * pi * r)
                flange_m = 2.0 * (2.0 * math.pi * r_m)
                total_flange_len_m += flange_m

                firestop_vol = (opening_area - duct_area) * t_m
                total_firestop_vol_m3 += firestop_vol
            elif d.duct_shape == DuctProfileShape.RECTANGULAR:
                w_m = d.width_mm / 1000.0
                h_m = d.height_mm / 1000.0
                duct_area = w_m * h_m
                total_airflow_area_m2 += duct_area

                opening_w_m = w_m + 2.0 * g_m
                opening_h_m = h_m + 2.0 * g_m
                opening_area = opening_w_m * opening_h_m
                total_opening_area_m2 += opening_area

                # Flange angles on 2 faces = 2 * 2 * (w + h)
                flange_m = 4.0 * (w_m + h_m)
                total_flange_len_m += flange_m

                firestop_vol = (opening_area - duct_area) * t_m
                total_firestop_vol_m3 += firestop_vol

        quantities = HVACPenetrationQuantities(
            total_damper_count=len(dampers),
            total_duct_airflow_area_m2=round(total_airflow_area_m2, 3),
            total_rough_opening_area_m2=round(total_opening_area_m2, 3),
            total_retaining_flange_length_m=round(total_flange_len_m, 3),
            total_firestop_mortar_volume_m3=round(total_firestop_vol_m3, 4)
        )

        return HVACPenetrationExtractionResult(
            dampers=dampers,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"damper_count": str(len(dampers))}
        )
