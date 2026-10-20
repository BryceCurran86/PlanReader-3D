"""
pb_source_roof_drainage_gutter_downpipe_shadow.py

Authoritative shadow-mode extraction and quantification for roof drainage networks,
including internal box gutters, eaves gutters, downpipe vertical drops, rainwater
collection sumps/heads, and emergency overflow scuppers.

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


class GutterType(str, Enum):
    BOX_GUTTER = "BOX_GUTTER"
    EAVES_QUAD_GUTTER = "EAVES_QUAD_GUTTER"
    HALF_ROUND_GUTTER = "HALF_ROUND_GUTTER"
    VALLEY_GUTTER = "VALLEY_GUTTER"


class DrainageMaterial(str, Enum):
    COLORBOND_STEEL = "COLORBOND_STEEL"
    PVC = "PVC"
    COPPER = "COPPER"
    STAINLESS_STEEL = "STAINLESS_STEEL"
    CAST_IRON = "CAST_IRON"
    UNKNOWN = "UNKNOWN"


@dataclass
class GutterSpec:
    gutter_id: str
    gutter_type: GutterType
    centerline_points: List[Tuple[float, float]]
    width_mm: float = 300.0
    depth_mm: float = 150.0
    material: DrainageMaterial = DrainageMaterial.COLORBOND_STEEL
    fall_ratio: float = 0.01
    level_id: str = "ROOF"
    source_annotation: str = ""


@dataclass
class DownpipeSpec:
    downpipe_id: str
    location: Tuple[float, float]
    diameter_mm: float = 100.0
    height_drop_m: float = 3.0
    material: DrainageMaterial = DrainageMaterial.PVC
    level_id: str = "ROOF"


@dataclass
class OverflowScupperSpec:
    scupper_id: str
    location: Tuple[float, float]
    width_mm: float = 300.0
    height_mm: float = 100.0
    freeboard_mm: float = 50.0
    level_id: str = "ROOF"


@dataclass
class RainwaterHeadSpec:
    head_id: str
    location: Tuple[float, float]
    width_mm: float = 400.0
    depth_mm: float = 250.0
    height_mm: float = 300.0
    level_id: str = "ROOF"


@dataclass
class RoofDrainageQuantities:
    total_box_gutter_length_m: float
    total_eaves_gutter_length_m: float
    total_gutter_length_m: float
    total_gutter_sheet_area_m2: float
    total_downpipe_count: int
    total_downpipe_length_m: float
    total_scupper_count: int
    total_rainwater_head_count: int


@dataclass
class RoofDrainageExtractionResult:
    gutters: List[GutterSpec]
    downpipes: List[DownpipeSpec]
    scuppers: List[OverflowScupperSpec]
    rainwater_heads: List[RainwaterHeadSpec]
    quantities: RoofDrainageQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceRoofDrainageGutterDownpipeShadowAuthority:
    """Authority for analyzing roof drainage systems in shadow mode."""

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
    def parse_gutter_annotation(annotation: str) -> Tuple[GutterType, float, float, DrainageMaterial]:
        """
        Parses annotation, e.g.:
        'COLORBOND BOX GUTTER 350W x 200D W/ 1:100 FALL'
        Returns (gutter_type, width_mm, depth_mm, material)
        """
        clean = annotation.upper().strip()

        # Type detection
        if "BOX" in clean:
            g_type = GutterType.BOX_GUTTER
        elif "VALLEY" in clean:
            g_type = GutterType.VALLEY_GUTTER
        elif "HALF" in clean:
            g_type = GutterType.HALF_ROUND_GUTTER
        else:
            g_type = GutterType.EAVES_QUAD_GUTTER

        # Material detection
        if "COLORBOND" in clean:
            mat = DrainageMaterial.COLORBOND_STEEL
        elif "STAINLESS" in clean or "S/S" in clean:
            mat = DrainageMaterial.STAINLESS_STEEL
        elif "COPPER" in clean:
            mat = DrainageMaterial.COPPER
        elif "PVC" in clean:
            mat = DrainageMaterial.PVC
        elif "CAST" in clean:
            mat = DrainageMaterial.CAST_IRON
        else:
            mat = DrainageMaterial.COLORBOND_STEEL

        # Dimensions: (\d+)\s*W\s*[xX]\s*(\d+)\s*D or (\d+)\s*[xX]\s*(\d+)
        w_match = re.search(r"(\d+)\s*W", clean)
        d_match = re.search(r"(\d+)\s*D", clean)

        if w_match and d_match:
            width_mm = float(w_match.group(1))
            depth_mm = float(d_match.group(1))
        else:
            dim_match = re.search(r"(\d+)\s*[xX]\s*(\d+)", clean)
            if dim_match:
                width_mm = float(dim_match.group(1))
                depth_mm = float(dim_match.group(2))
            else:
                width_mm, depth_mm = 300.0, 150.0

        return g_type, width_mm, depth_mm, mat

    @classmethod
    def evaluate_roof_drainage(
        cls,
        gutters: List[GutterSpec],
        downpipes: List[DownpipeSpec],
        scuppers: List[OverflowScupperSpec],
        rainwater_heads: List[RainwaterHeadSpec],
        drawing_scale: float = 1.0  # meters per drawing coordinate unit
    ) -> RoofDrainageExtractionResult:
        total_box_m = 0.0
        total_eaves_m = 0.0
        total_sheet_area_m2 = 0.0

        for g in gutters:
            raw_len = cls.compute_polyline_length(g.centerline_points)
            len_m = raw_len * drawing_scale

            if g.gutter_type == GutterType.BOX_GUTTER:
                total_box_m += len_m
            else:
                total_eaves_m += len_m

            # Gutter girth development: width + 2*depth + flanges (e.g. 50mm * 2)
            girth_m = (g.width_mm + 2.0 * g.depth_mm + 100.0) / 1000.0
            total_sheet_area_m2 += len_m * girth_m

        total_dp_len_m = sum(dp.height_drop_m for dp in downpipes)

        quantities = RoofDrainageQuantities(
            total_box_gutter_length_m=round(total_box_m, 3),
            total_eaves_gutter_length_m=round(total_eaves_m, 3),
            total_gutter_length_m=round(total_box_m + total_eaves_m, 3),
            total_gutter_sheet_area_m2=round(total_sheet_area_m2, 3),
            total_downpipe_count=len(downpipes),
            total_downpipe_length_m=round(total_dp_len_m, 3),
            total_scupper_count=len(scuppers),
            total_rainwater_head_count=len(rainwater_heads)
        )

        return RoofDrainageExtractionResult(
            gutters=gutters,
            downpipes=downpipes,
            scuppers=scuppers,
            rainwater_heads=rainwater_heads,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "gutter_count": str(len(gutters)),
                "downpipe_count": str(len(downpipes)),
                "scupper_count": str(len(scuppers)),
                "rainwater_head_count": str(len(rainwater_heads))
            }
        )
