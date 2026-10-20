"""
pb_source_timber_roof_truss_pitch_shadow.py

Authoritative shadow-mode extraction and multi-chord geometric takeoff for structural timber
roof trusses, pitch slopes, top/bottom chords, and eaves overhangs.

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


class TrussProfileType(str, Enum):
    UNKNOWN = "UNKNOWN"
    FINK = "FINK"
    HOWE = "HOWE"
    MONO_PITCH = "MONO_PITCH"
    TRUNCATED_GIRDER = "TRUNCATED_GIRDER"
    HIP_RAFTER = "HIP_RAFTER"


@dataclass
class TimberRoofTrussSpec:
    truss_id: str
    truss_type: TrussProfileType
    layout_line: List[Tuple[float, float]]
    span_mm: float
    pitch_deg: float = 0.0
    eaves_overhang_mm: float = 0.0
    spacing_centers_mm: float = 0.0
    count: int = 1
    level_id: str = "ROOF"
    source_tag: str = ""


@dataclass
class TimberTrussQuantities:
    total_truss_count: int
    total_top_chord_sloped_length_m: float
    total_bottom_chord_length_m: float
    total_timber_linear_length_m: float
    total_roof_sloped_coverage_area_m2: float


@dataclass
class TimberTrussExtractionResult:
    trusses: List[TimberRoofTrussSpec]
    quantities: TimberTrussQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceTimberRoofTrussPitchShadowAuthority:
    """Authority for analyzing timber roof trusses and pitch geometry in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def parse_truss_annotation(annotation: str) -> Tuple[TrussProfileType, float, float, float]:
        """
        Parses annotation, e.g.:
        'FINK TRUSS 22.5 DEG PITCH @ 900 CTS 600 O/HANG' or 'SKILLION MONO TRUSS 15 DEG'
        Returns (truss_type, pitch_deg, spacing_mm, overhang_mm)
        """
        clean = annotation.upper().strip()

        # Truss type
        if "MONO" in clean or "SKILLION" in clean:
            t_type = TrussProfileType.MONO_PITCH
        elif "GIRDER" in clean or "TRUNCATED" in clean:
            t_type = TrussProfileType.TRUNCATED_GIRDER
        elif "HIP" in clean or "RAFTER" in clean:
            t_type = TrussProfileType.HIP_RAFTER
        elif "HOWE" in clean:
            t_type = TrussProfileType.HOWE
        elif "FINK" in clean:
            t_type = TrussProfileType.FINK
        else:
            t_type = TrussProfileType.UNKNOWN

        # Pitch angle: (\d+(?:\.\d+)?)\s*(?:DEG|°|PITCH)
        p_match = re.search(r"(\d+(?:\.\d+)?)\s*(?:DEG|°|PITCH)", clean)
        pitch_deg = float(p_match.group(1)) if p_match else 0.0

        # Spacing: (\d+)\s*(?:CTS|CENTRES|CENTERS|SPACING)
        sp_match = re.search(r"(\d+)\s*(?:CTS|CENTRES|CENTERS|SPACING)", clean)
        spacing_mm = float(sp_match.group(1)) if sp_match else 0.0

        # Overhang: (\d+)\s*(?:O/HANG|OVERHANG|EAVES)",
        oh_match = re.search(r"(\d+)\s*(?:O/HANG|OVERHANG|EAVES)", clean)
        overhang_mm = float(oh_match.group(1)) if oh_match else 0.0

        return t_type, pitch_deg, spacing_mm, overhang_mm

    @classmethod
    def evaluate_roof_trusses(
        cls,
        trusses: List[TimberRoofTrussSpec],
        drawing_scale: float = 1.0
    ) -> TimberTrussExtractionResult:
        total_count = 0
        total_top_chord_m = 0.0
        total_bot_chord_m = 0.0
        total_timber_m = 0.0
        total_roof_coverage_m2 = 0.0

        for t in trusses:
            total_count += t.count
            span_m = t.span_mm / 1000.0
            oh_m = t.eaves_overhang_mm / 1000.0
            rad = math.radians(t.pitch_deg)

            if t.truss_type == TrussProfileType.MONO_PITCH:
                # Single sloped top chord
                horizontal_run = span_m + oh_m
                top_chord_per_truss = horizontal_run / math.cos(rad)
                bot_chord_per_truss = span_m + oh_m
                apex_h = horizontal_run * math.tan(rad)
                webs_per_truss = 1.5 * apex_h
            else:
                # Dual pitch symmetrical truss
                half_run = (span_m / 2.0) + oh_m
                top_chord_side = half_run / math.cos(rad)
                top_chord_per_truss = 2.0 * top_chord_side
                bot_chord_per_truss = span_m + (2.0 * oh_m)
                apex_h = half_run * math.tan(rad)
                webs_per_truss = 1.8 * apex_h

            timber_per_truss = top_chord_per_truss + bot_chord_per_truss + webs_per_truss

            total_top_chord_m += top_chord_per_truss * t.count
            total_bot_chord_m += bot_chord_per_truss * t.count
            total_timber_m += timber_per_truss * t.count

            # Roof sloped coverage area per truss tributary width
            spacing_m = t.spacing_centers_mm / 1000.0
            coverage_per_truss = top_chord_per_truss * spacing_m
            total_roof_coverage_m2 += coverage_per_truss * t.count

        quantities = TimberTrussQuantities(
            total_truss_count=total_count,
            total_top_chord_sloped_length_m=round(total_top_chord_m, 3),
            total_bottom_chord_length_m=round(total_bot_chord_m, 3),
            total_timber_linear_length_m=round(total_timber_m, 3),
            total_roof_sloped_coverage_area_m2=round(total_roof_coverage_m2, 3)
        )

        return TimberTrussExtractionResult(
            trusses=trusses,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"truss_spec_count": str(len(trusses))}
        )
