"""
pb_source_steel_baseplate_grout_bolt_shadow.py

Authoritative shadow-mode extraction and quantification for structural steel column
baseplates, holding down anchor bolt cages, and non-shrink cementitious grout beds.

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
STEEL_DENSITY_KG_M3: float = 7850.0


class BoltGrade(str, Enum):
    UNKNOWN = "UNKNOWN"
    GRADE_4_6 = "GRADE_4_6"
    GRADE_8_8 = "GRADE_8_8"
    GRADE_10_9 = "GRADE_10_9"


@dataclass
class SteelBaseplateSpec:
    connection_id: str
    column_id: str
    location: Tuple[float, float]
    plate_width_mm: float = 0.0
    plate_length_mm: float = 0.0
    plate_thickness_mm: float = 0.0
    bolt_count: int = 0
    bolt_diameter_mm: float = 0.0
    bolt_embedment_depth_mm: float = 0.0
    bolt_grade: BoltGrade = BoltGrade.UNKNOWN
    grout_thickness_mm: float = 0.0
    grout_oversize_mm: float = 0.0
    nut_thread_extension_mm: float = 0.0
    level_id: str = "L0"
    source_callout: str = ""


@dataclass
class SteelBaseplateQuantities:
    total_connection_count: int
    total_baseplate_mass_kg: float
    total_anchor_bolt_count: int
    total_anchor_bolt_rod_length_m: float
    total_grout_volume_m3: float
    total_grout_footprint_area_m2: float


@dataclass
class SteelBaseplateExtractionResult:
    connections: List[SteelBaseplateSpec]
    quantities: SteelBaseplateQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSteelBaseplateGroutBoltShadowAuthority:
    """Authority for analyzing column baseplates, anchor bolts, and grout beds in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def parse_baseplate_annotation(annotation: str) -> Tuple[float, float, float, int, float, float, float]:
        """
        Parses annotation, e.g.:
        'BASEPLATE 350x350x25 THK W/ 4-M24 HD BOLTS (450 EMBED) & 35 GROUT BED'
        Returns (plate_w, plate_l, plate_thk, bolt_count, bolt_dia, bolt_embed, grout_thk)
        """
        clean = annotation.upper().strip()

        # Baseplate dimensions: (\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)
        p_match = re.search(r"(\d+)\s*[xX]\s*(\d+)\s*[xX]\s*(\d+)", clean)
        if p_match:
            plate_w = float(p_match.group(1))
            plate_l = float(p_match.group(2))
            plate_thk = float(p_match.group(3))
        else:
            plate_w, plate_l, plate_thk = 0.0, 0.0, 0.0

        # Bolt count and diameter: (\d+)\s*[-xX]\s*M(\d+)
        b_match = re.search(r"(\d+)\s*[-xX]\s*M(\d+)", clean)
        if b_match:
            bolt_count = int(b_match.group(1))
            bolt_dia = float(b_match.group(2))
        else:
            bolt_count = 0
            bolt_dia = 0.0

        # Bolt embedment depth: (\d+)\s*(?:EMBED|EMBEDMENT)
        emb_match = re.search(r"(\d+)\s*(?:EMBED|EMBEDMENT)", clean)
        bolt_embed = float(emb_match.group(1)) if emb_match else 0.0

        # Grout thickness: (\d+)\s*(?:GROUT|BED)
        grt_match = re.search(r"(\d+)\s*(?:GROUT|BED)", clean)
        grout_thk = float(grt_match.group(1)) if grt_match else 0.0

        return plate_w, plate_l, plate_thk, bolt_count, bolt_dia, bolt_embed, grout_thk

    @classmethod
    def evaluate_connections(cls, connections: List[SteelBaseplateSpec]) -> SteelBaseplateExtractionResult:
        total_mass_kg = 0.0
        total_bolts = 0
        total_rod_len_m = 0.0
        total_grout_vol_m3 = 0.0
        total_grout_area_m2 = 0.0

        for conn in connections:
            w_m = conn.plate_width_mm / 1000.0
            l_m = conn.plate_length_mm / 1000.0
            t_m = conn.plate_thickness_mm / 1000.0
            plate_vol_m3 = w_m * l_m * t_m
            total_mass_kg += plate_vol_m3 * STEEL_DENSITY_KG_M3

            total_bolts += conn.bolt_count

            rod_len_mm = (
                conn.bolt_embedment_depth_mm
                + conn.plate_thickness_mm
                + conn.grout_thickness_mm
                + conn.nut_thread_extension_mm
            )
            rod_len_m = (rod_len_mm / 1000.0) * conn.bolt_count
            total_rod_len_m += rod_len_m

            gw_m = (conn.plate_width_mm + conn.grout_oversize_mm) / 1000.0
            gl_m = (conn.plate_length_mm + conn.grout_oversize_mm) / 1000.0
            gt_m = conn.grout_thickness_mm / 1000.0
            grout_bed_area = gw_m * gl_m
            total_grout_area_m2 += grout_bed_area
            total_grout_vol_m3 += grout_bed_area * gt_m

        quantities = SteelBaseplateQuantities(
            total_connection_count=len(connections),
            total_baseplate_mass_kg=round(total_mass_kg, 3),
            total_anchor_bolt_count=total_bolts,
            total_anchor_bolt_rod_length_m=round(total_rod_len_m, 3),
            total_grout_volume_m3=round(total_grout_vol_m3, 4),
            total_grout_footprint_area_m2=round(total_grout_area_m2, 3)
        )

        return SteelBaseplateExtractionResult(
            connections=connections,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"connection_count": str(len(connections))}
        )
