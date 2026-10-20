"""
pb_source_weather_louver_aerodynamic_free_area_shadow.py

Authoritative shadow-mode extraction and quantification for architectural and mechanical
weather louver banks, aerodynamic net free areas, perimeter frames, and bird mesh screens.

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


class LouverBladeType(str, Enum):
    SINGLE_STAGE_DRAINABLE = "SINGLE_STAGE_DRAINABLE"
    TWO_STAGE_STORM = "TWO_STAGE_STORM"
    ACOUSTIC_CHEVRON = "ACOUSTIC_CHEVRON"
    CONTINUOUS_HORIZONTAL = "CONTINUOUS_HORIZONTAL"


@dataclass
class WeatherLouverSpec:
    louver_id: str
    blade_type: LouverBladeType
    location: Tuple[float, float]
    width_mm: float = 0.0
    height_mm: float = 0.0
    blade_pitch_mm: float = 75.0
    free_area_ratio: float = 0.50
    has_bird_mesh: bool = True
    frame_depth_mm: float = 100.0
    level_id: str = "ELEV"
    source_tag: str = ""


@dataclass
class WeatherLouverQuantities:
    total_louver_count: int
    total_gross_aperture_area_m2: float
    total_aerodynamic_free_area_m2: float
    total_perimeter_frame_length_m: float
    total_estimated_blade_count: int
    total_bird_mesh_area_m2: float


@dataclass
class WeatherLouverExtractionResult:
    louvers: List[WeatherLouverSpec]
    quantities: WeatherLouverQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceWeatherLouverAerodynamicFreeAreaShadowAuthority:
    """Authority for analyzing weather louvers and aerodynamic free areas in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def parse_louver_annotation(annotation: str) -> Tuple[LouverBladeType, float, float, float, float]:
        """
        Parses annotation, e.g.:
        'WEATHER LOUVER 1500W x 2000H TWO STAGE STORM 48% FREE AREA @ 75 PITCH'
        Returns (blade_type, width_mm, height_mm, free_area_ratio, blade_pitch_mm)
        """
        clean = annotation.upper().strip()

        # Blade type
        if "STORM" in clean or "TWO STAGE" in clean or "2 STAGE" in clean:
            b_type = LouverBladeType.TWO_STAGE_STORM
            def_ratio = 0.45
        elif "ACOUSTIC" in clean or "CHEVRON" in clean:
            b_type = LouverBladeType.ACOUSTIC_CHEVRON
            def_ratio = 0.35
        elif "CONTINUOUS" in clean:
            b_type = LouverBladeType.CONTINUOUS_HORIZONTAL
            def_ratio = 0.52
        else:
            b_type = LouverBladeType.SINGLE_STAGE_DRAINABLE
            def_ratio = 0.50

        # Dimensions: (\d+)\s*(?:W)?\s*[xX]\s*(\d+)\s*(?:H)?
        dim_match = re.search(r"(\d+)\s*(?:W)?\s*[xX]\s*(\d+)\s*(?:H)?", clean)
        if dim_match:
            w = float(dim_match.group(1))
            h = float(dim_match.group(2))
        else:
            w, h = 0.0, 0.0

        # Free area percentage: (\d+(?:\.\d+)?)\s*%\s*(?:FREE|AFA)?
        fa_match = re.search(r"(\d+(?:\.\d+)?)\s*%", clean)
        if fa_match:
            free_ratio = float(fa_match.group(1)) / 100.0
        else:
            free_ratio = def_ratio

        # Pitch: (\d+)\s*(?:PITCH|CTS|SPACING)
        pitch_match = re.search(r"(\d+)\s*(?:PITCH|CTS|SPACING)", clean)
        pitch_mm = float(pitch_match.group(1)) if pitch_match else 75.0

        return b_type, w, h, free_ratio, pitch_mm

    @classmethod
    def evaluate_louvers(cls, louvers: List[WeatherLouverSpec]) -> WeatherLouverExtractionResult:
        total_gross_m2 = 0.0
        total_free_m2 = 0.0
        total_frame_m = 0.0
        total_blades = 0
        total_mesh_m2 = 0.0

        for l in louvers:
            w_m = l.width_mm / 1000.0
            h_m = l.height_mm / 1000.0
            gross_area = w_m * h_m
            total_gross_m2 += gross_area

            free_area = gross_area * l.free_area_ratio
            total_free_m2 += free_area

            frame_len = 2.0 * (w_m + h_m)
            total_frame_m += frame_len

            blades = math.ceil(max(0.0, l.height_mm - 100.0) / l.blade_pitch_mm) if l.blade_pitch_mm > 0 else 0
            total_blades += blades

            if l.has_bird_mesh:
                total_mesh_m2 += gross_area

        quantities = WeatherLouverQuantities(
            total_louver_count=len(louvers),
            total_gross_aperture_area_m2=round(total_gross_m2, 3),
            total_aerodynamic_free_area_m2=round(total_free_m2, 3),
            total_perimeter_frame_length_m=round(total_frame_m, 3),
            total_estimated_blade_count=total_blades,
            total_bird_mesh_area_m2=round(total_mesh_m2, 3)
        )

        return WeatherLouverExtractionResult(
            louvers=louvers,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"louver_count": str(len(louvers))}
        )
