"""
pb_source_slab_drop_panel_capital_shadow.py

Authoritative shadow-mode extraction and volumetric quantification for suspended concrete
slab drop panels and column capitals resisting punching shear.

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


class ShearThickeningType(str, Enum):
    DROP_PANEL = "DROP_PANEL"
    COLUMN_CAPITAL = "COLUMN_CAPITAL"
    DROP_BEAM_STRIP = "DROP_BEAM_STRIP"


class CapitalShape(str, Enum):
    UNKNOWN = "UNKNOWN"
    PYRAMIDAL = "PYRAMIDAL"
    CONICAL = "CONICAL"
    PRISMATIC = "PRISMATIC"


@dataclass
class DropPanelSpec:
    panel_id: str
    thickening_type: ShearThickeningType
    boundary_polygon: List[Tuple[float, float]]
    drop_thickness_mm: float
    column_id: Optional[str] = None
    level_id: str = ""
    source_annotation: str = ""


@dataclass
class ColumnCapitalSpec:
    capital_id: str
    top_width_mm: float
    top_length_mm: float
    bottom_width_mm: float
    bottom_length_mm: float
    height_mm: float
    shape: CapitalShape = CapitalShape.UNKNOWN
    column_id: Optional[str] = None
    level_id: str = ""


@dataclass
class DropPanelCapitalQuantities:
    total_drop_panel_count: int
    total_drop_concrete_volume_m3: float
    total_drop_soffit_area_m2: float
    total_drop_edge_formwork_area_m2: float
    total_capital_count: int
    total_capital_concrete_volume_m3: float


@dataclass
class DropPanelCapitalExtractionResult:
    drop_panels: List[DropPanelSpec]
    capitals: List[ColumnCapitalSpec]
    quantities: DropPanelCapitalQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSlabDropPanelCapitalShadowAuthority:
    """Authority for analyzing slab drop panels and column capitals in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def compute_polygon_area(points: List[Tuple[float, float]]) -> float:
        """Computes polygon area using the shoelace formula."""
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
        perimeter = 0.0
        for i in range(n):
            j = (i + 1) % n
            perimeter += math.hypot(points[j][0] - points[i][0], points[j][1] - points[i][1])
        return perimeter

    @staticmethod
    def parse_drop_panel_annotation(annotation: str) -> Tuple[float, float, float]:
        """
        Parses annotation, e.g.:
        'DROP PANEL 2400x2400x150 THK DP' or 'DP 2000x2500x200'
        Returns (width_mm, length_mm, drop_thickness_mm)
        """
        clean = annotation.upper().strip()
        dims = re.findall(r"(\d+)", clean)
        if len(dims) >= 3:
            return float(dims[0]), float(dims[1]), float(dims[2])
        elif len(dims) == 2:
            return float(dims[0]), float(dims[0]), float(dims[1])
        return 2000.0, 2000.0, 150.0

    @staticmethod
    def compute_capital_frustum_volume(
        top_w_mm: float,
        top_l_mm: float,
        bot_w_mm: float,
        bot_l_mm: float,
        h_mm: float,
        shape: CapitalShape = CapitalShape.UNKNOWN
    ) -> float:
        """Calculates volume of tapered column capital in cubic meters."""
        if shape not in (CapitalShape.CONICAL, CapitalShape.PYRAMIDAL, CapitalShape.PRISMATIC):
            return 0.0
        h_m = h_mm / 1000.0
        if shape == CapitalShape.CONICAL:
            r1 = (top_w_mm / 2000.0)
            r2 = (bot_w_mm / 2000.0)
            return (math.pi * h_m / 3.0) * (r1 * r1 + r1 * r2 + r2 * r2)
        else:
            # Pyramidal frustum
            a1 = (top_w_mm / 1000.0) * (top_l_mm / 1000.0)
            a2 = (bot_w_mm / 1000.0) * (bot_l_mm / 1000.0)
            return (h_m / 3.0) * (a1 + a2 + math.sqrt(a1 * a2))

    @classmethod
    def evaluate_panels_and_capitals(
        cls,
        drop_panels: List[DropPanelSpec],
        capitals: List[ColumnCapitalSpec],
        drawing_scale: float = 1.0  # meters per drawing coordinate unit
    ) -> DropPanelCapitalExtractionResult:
        total_drop_vol_m3 = 0.0
        total_drop_soffit_area_m2 = 0.0
        total_drop_edge_formwork_area_m2 = 0.0

        for dp in drop_panels:
            raw_area = cls.compute_polygon_area(dp.boundary_polygon)
            area_m2 = raw_area * (drawing_scale ** 2)
            total_drop_soffit_area_m2 += area_m2

            thick_m = dp.drop_thickness_mm / 1000.0
            total_drop_vol_m3 += area_m2 * thick_m

            raw_perim = cls.compute_polygon_perimeter(dp.boundary_polygon)
            perim_m = raw_perim * drawing_scale
            total_drop_edge_formwork_area_m2 += perim_m * thick_m

        total_capital_vol_m3 = 0.0
        for cap in capitals:
            cap_vol = cls.compute_capital_frustum_volume(
                top_w_mm=cap.top_width_mm,
                top_l_mm=cap.top_length_mm,
                bot_w_mm=cap.bottom_width_mm,
                bot_l_mm=cap.bottom_length_mm,
                h_mm=cap.height_mm,
                shape=cap.shape
            )
            total_capital_vol_m3 += cap_vol

        quantities = DropPanelCapitalQuantities(
            total_drop_panel_count=len(drop_panels),
            total_drop_concrete_volume_m3=round(total_drop_vol_m3, 3),
            total_drop_soffit_area_m2=round(total_drop_soffit_area_m2, 3),
            total_drop_edge_formwork_area_m2=round(total_drop_edge_formwork_area_m2, 3),
            total_capital_count=len(capitals),
            total_capital_concrete_volume_m3=round(total_capital_vol_m3, 3)
        )

        return DropPanelCapitalExtractionResult(
            drop_panels=drop_panels,
            capitals=capitals,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "drop_panel_count": str(len(drop_panels)),
                "column_capital_count": str(len(capitals))
            }
        )
