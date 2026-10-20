"""
pb_source_retaining_wall_drainage_shadow.py

Authoritative shadow-mode extraction and multi-component takeoff for structural earth
retaining walls, continuous spread footings, subsoil agricultural drainage pipes,
granular drainage aggregate backfill, and tanking waterproofing membranes.

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


class RetainingWallType(str, Enum):
    RC_CANTILEVER = "RC_CANTILEVER"
    CORE_FILLED_BLOCK = "CORE_FILLED_BLOCK"
    GRAVITY_CRIB_MASS = "GRAVITY_CRIB_MASS"
    SOLDIER_PILE_SLEEPER = "SOLDIER_PILE_SLEEPER"


@dataclass
class RetainingWallSpec:
    wall_id: str
    wall_type: RetainingWallType
    centerline_points: List[Tuple[float, float]]
    stem_thickness_mm: float = 0.0
    retained_height_mm: float = 0.0
    footing_width_mm: float = 0.0
    footing_depth_mm: float = 0.0
    ag_pipe_diameter_mm: float = 0.0
    agg_backfill_width_mm: float = 0.0
    has_tanking_membrane: bool = False
    level_id: str = "SITE"
    source_annotation: str = ""


@dataclass
class RetainingWallQuantities:
    total_wall_length_m: float
    total_stem_concrete_volume_m3: float
    total_footing_concrete_volume_m3: float
    total_concrete_volume_m3: float
    total_drainage_agg_volume_m3: float
    total_tanking_membrane_area_m2: float
    total_ag_pipe_length_m: float


@dataclass
class RetainingWallExtractionResult:
    walls: List[RetainingWallSpec]
    quantities: RetainingWallQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceRetainingWallDrainageShadowAuthority:
    """Authority for analyzing structural retaining walls and drainage layers in shadow mode."""

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
    def parse_retaining_wall_annotation(annotation: str) -> Tuple[RetainingWallType, float, float, float, float]:
        """
        Parses text annotation, e.g.:
        'RETAINING WALL 200THK STEM x 1800H W/ 1200W x 300D FOOTING'
        Returns (wall_type, stem_thk_mm, retained_h_mm, footing_w_mm, footing_d_mm)
        """
        clean = annotation.upper().strip()

        # Wall type detection
        if "BLOCK" in clean or "CORE" in clean:
            w_type = RetainingWallType.CORE_FILLED_BLOCK
        elif "GRAVITY" in clean or "CRIB" in clean:
            w_type = RetainingWallType.GRAVITY_CRIB_MASS
        elif "SLEEPER" in clean or "SOLDIER" in clean:
            w_type = RetainingWallType.SOLDIER_PILE_SLEEPER
        else:
            w_type = RetainingWallType.RC_CANTILEVER

        # Stem thickness
        stem_match = re.search(r"(\d+)\s*(?:THK|STEM)", clean)
        stem_thk_mm = float(stem_match.group(1)) if stem_match else 0.0

        # Retained height
        h_match = re.search(r"(\d+)\s*(?:H\b|HIGH|HEIGHT)", clean)
        retained_h_mm = float(h_match.group(1)) if h_match else 0.0

        # Footing dimensions
        fw_match = re.search(r"(\d+)\s*(?:W\b|WIDE)", clean)
        footing_w_mm = float(fw_match.group(1)) if fw_match else 0.0

        fd_match = re.search(r"(\d+)\s*(?:D\b|DEEP|FOOTING)", clean)
        footing_d_mm = float(fd_match.group(1)) if fd_match else 0.0

        return w_type, stem_thk_mm, retained_h_mm, footing_w_mm, footing_d_mm

    @classmethod
    def evaluate_retaining_walls(
        cls,
        walls: List[RetainingWallSpec],
        drawing_scale: float = 1.0  # meters per drawing coordinate unit
    ) -> RetainingWallExtractionResult:
        total_len_m = 0.0
        total_stem_vol_m3 = 0.0
        total_footing_vol_m3 = 0.0
        total_agg_vol_m3 = 0.0
        total_tanking_m2 = 0.0
        total_pipe_m = 0.0

        for w in walls:
            raw_len = cls.compute_polyline_length(w.centerline_points)
            len_m = raw_len * drawing_scale
            total_len_m += len_m

            stem_t_m = w.stem_thickness_mm / 1000.0
            stem_h_m = w.retained_height_mm / 1000.0
            stem_vol = len_m * stem_t_m * stem_h_m
            total_stem_vol_m3 += stem_vol

            foot_w_m = w.footing_width_mm / 1000.0
            foot_d_m = w.footing_depth_mm / 1000.0
            foot_vol = len_m * foot_w_m * foot_d_m
            total_footing_vol_m3 += foot_vol

            agg_w_m = w.agg_backfill_width_mm / 1000.0
            agg_vol = len_m * agg_w_m * stem_h_m
            total_agg_vol_m3 += agg_vol

            if w.has_tanking_membrane:
                total_tanking_m2 += len_m * stem_h_m

            if w.ag_pipe_diameter_mm > 0:
                total_pipe_m += len_m

        total_conc_vol_m3 = total_stem_vol_m3 + total_footing_vol_m3

        quantities = RetainingWallQuantities(
            total_wall_length_m=round(total_len_m, 3),
            total_stem_concrete_volume_m3=round(total_stem_vol_m3, 3),
            total_footing_concrete_volume_m3=round(total_footing_vol_m3, 3),
            total_concrete_volume_m3=round(total_conc_vol_m3, 3),
            total_drainage_agg_volume_m3=round(total_agg_vol_m3, 3),
            total_tanking_membrane_area_m2=round(total_tanking_m2, 3),
            total_ag_pipe_length_m=round(total_pipe_m, 3)
        )

        return RetainingWallExtractionResult(
            walls=walls,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"wall_count": str(len(walls))}
        )
