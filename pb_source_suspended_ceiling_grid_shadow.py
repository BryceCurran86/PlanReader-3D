"""
pb_source_suspended_ceiling_grid_shadow.py

Authoritative shadow-mode extraction and quantification for modular suspended ceiling
grid systems, main runner T-bars, cross tees, perimeter wall angle trims, and
suspension hanger wires.

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


class CeilingGridModule(str, Enum):
    UNKNOWN = "UNKNOWN"
    GRID_1200X600 = "GRID_1200X600"
    GRID_600X600 = "GRID_600X600"
    GRID_1200X300 = "GRID_1200X300"


class CeilingGridType(str, Enum):
    UNKNOWN = "UNKNOWN"
    EXPOSED_TEE = "EXPOSED_TEE"
    CONCEALED_TEE = "CONCEALED_TEE"
    FINELINE_SLOTTED = "FINELINE_SLOTTED"


@dataclass
class SuspendedCeilingSpec:
    ceiling_id: str
    room_id: str
    boundary_polygon: List[Tuple[float, float]]
    grid_module: CeilingGridModule = CeilingGridModule.UNKNOWN
    grid_type: CeilingGridType = CeilingGridType.UNKNOWN
    finished_ceiling_level_mm: float = 0.0
    slab_soffit_level_mm: float = 0.0
    level_id: str = "L1"
    source_annotation: str = ""


@dataclass
class SuspendedCeilingQuantities:
    total_ceiling_area_m2: float
    total_perimeter_wall_trim_length_m: float
    total_main_runner_length_m: float
    total_cross_tee_length_m: float
    total_hanger_wire_points: int
    total_hanger_wire_length_m: float
    total_estimated_tile_count: int


@dataclass
class SuspendedCeilingExtractionResult:
    ceilings: List[SuspendedCeilingSpec]
    quantities: SuspendedCeilingQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSuspendedCeilingGridShadowAuthority:
    """Authority for analyzing suspended ceiling grids and hanger wire networks in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def compute_polygon_area(points: List[Tuple[float, float]]) -> float:
        n = len(points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0

    @staticmethod
    def compute_polygon_perimeter(points: List[Tuple[float, float]]) -> float:
        n = len(points)
        if n < 2:
            return 0.0
        perim = 0.0
        for i in range(n):
            j = (i + 1) % n
            perim += math.hypot(points[j][0] - points[i][0], points[j][1] - points[i][1])
        return perim

    @staticmethod
    def parse_ceiling_annotation(annotation: str) -> Tuple[CeilingGridModule, CeilingGridType, float, float]:
        """
        Parses annotation, e.g.:
        'SUSPENDED CEILING 1200x600 GRID EXPOSED TEE 2700 AFFL PLENUM 600'
        Returns (grid_module, grid_type, finished_ceiling_level_mm, slab_soffit_level_mm)
        """
        clean = annotation.upper().strip()

        # Grid module
        if "600X600" in clean or "600 SQ" in clean:
            mod = CeilingGridModule.GRID_600X600
        elif "1200X300" in clean:
            mod = CeilingGridModule.GRID_1200X300
        elif "1200X600" in clean:
            mod = CeilingGridModule.GRID_1200X600
        else:
            mod = CeilingGridModule.UNKNOWN

        # Grid type
        if "CONCEALED" in clean:
            g_type = CeilingGridType.CONCEALED_TEE
        elif "FINELINE" in clean or "SLOT" in clean:
            g_type = CeilingGridType.FINELINE_SLOTTED
        elif "EXPOSED" in clean:
            g_type = CeilingGridType.EXPOSED_TEE
        else:
            g_type = CeilingGridType.UNKNOWN

        # Levels
        affl_match = re.search(r"(\d+)\s*(?:AFFL|CLG|CEILING)", clean)
        clg_lvl = float(affl_match.group(1)) if affl_match else 0.0

        plenum_match = re.search(r"(?:PLENUM|VOID)\s*(\d+)", clean)
        if plenum_match:
            plenum_mm = float(plenum_match.group(1))
            soffit_lvl = clg_lvl + plenum_mm
        else:
            soffit_lvl = clg_lvl

        return mod, g_type, clg_lvl, soffit_lvl

    @classmethod
    def evaluate_ceilings(
        cls,
        ceilings: List[SuspendedCeilingSpec],
        drawing_scale: float = 1.0  # meters per drawing coordinate unit
    ) -> SuspendedCeilingExtractionResult:
        total_area_m2 = 0.0
        total_trim_m = 0.0
        total_main_m = 0.0
        total_cross_m = 0.0
        total_hangers = 0
        total_wire_len_m = 0.0
        total_tiles = 0

        for c in ceilings:
            raw_area = cls.compute_polygon_area(c.boundary_polygon)
            area_m2 = raw_area * (drawing_scale ** 2)
            total_area_m2 += area_m2

            raw_perim = cls.compute_polygon_perimeter(c.boundary_polygon)
            perim_m = raw_perim * drawing_scale
            total_trim_m += perim_m

            if c.grid_module == CeilingGridModule.GRID_600X600:
                main_m = area_m2 / 1.20
                cross_m = area_m2 / 0.60
                tile_area = 0.60 * 0.60
            elif c.grid_module == CeilingGridModule.GRID_1200X300:
                main_m = area_m2 / 1.20
                cross_m = area_m2 / 0.30
                tile_area = 1.20 * 0.30
            elif c.grid_module == CeilingGridModule.GRID_1200X600:
                main_m = area_m2 / 1.20
                cross_m = area_m2 / 0.60
                tile_area = 1.20 * 0.60
            else:
                main_m = 0.0
                cross_m = 0.0
                tile_area = 0.0

            total_main_m += main_m

            total_cross_m += cross_m

            hangers = (
                math.ceil(area_m2 / 1.44)
                if area_m2 > 0 and c.grid_module is not CeilingGridModule.UNKNOWN
                else 0
            )
            total_hangers += hangers

            # Wire length = plenum depth
            plenum_m = max(0.0, (c.slab_soffit_level_mm - c.finished_ceiling_level_mm) / 1000.0)
            wire_len_m = hangers * plenum_m
            total_wire_len_m += wire_len_m

            tiles = math.ceil(area_m2 / tile_area) if area_m2 > 0 and tile_area > 0 else 0
            total_tiles += tiles

        quantities = SuspendedCeilingQuantities(
            total_ceiling_area_m2=round(total_area_m2, 3),
            total_perimeter_wall_trim_length_m=round(total_trim_m, 3),
            total_main_runner_length_m=round(total_main_m, 3),
            total_cross_tee_length_m=round(total_cross_m, 3),
            total_hanger_wire_points=total_hangers,
            total_hanger_wire_length_m=round(total_wire_len_m, 3),
            total_estimated_tile_count=total_tiles
        )

        return SuspendedCeilingExtractionResult(
            ceilings=ceilings,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"ceiling_count": str(len(ceilings))}
        )
