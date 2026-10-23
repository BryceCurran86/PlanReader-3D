"""
pb_source_slab_edge_thickening_footing_shadow.py

Authoritative shadow-mode extraction and quantification for structural foundation
strip footings, slab-on-ground edge thickening beams with brick rebates, and
internal stiffening ribs.

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


class FootingBeamType(str, Enum):
    EDGE_BEAM = "EDGE_BEAM"
    STRIP_FOOTING = "STRIP_FOOTING"
    INTERNAL_STIFFENER = "INTERNAL_STIFFENER"
    PAD_FOOTING = "PAD_FOOTING"


class SoilBearingClass(str, Enum):
    CLASS_A = "CLASS_A"
    CLASS_S = "CLASS_S"
    CLASS_M = "CLASS_M"
    CLASS_H1 = "CLASS_H1"
    CLASS_H2 = "CLASS_H2"
    CLASS_E = "CLASS_E"
    UNKNOWN = "UNKNOWN"


@dataclass
class BrickRebateSpec:
    width_mm: float
    depth_mm: float


@dataclass
class FootingBeamSpec:
    beam_id: str
    beam_type: FootingBeamType
    centerline_points: List[Tuple[float, float]]
    width_mm: float
    depth_mm: float
    rebate: Optional[BrickRebateSpec] = None
    level_id: str = "L0"
    source_annotation: str = ""


@dataclass
class FoundationQuantities:
    total_centerline_length_m: float
    total_excavation_volume_m3: float
    total_concrete_volume_m3: float
    total_edge_formwork_area_m2: float
    rebate_length_m: float


@dataclass
class FoundationFootingExtractionResult:
    beams: List[FootingBeamSpec]
    quantities: FoundationQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSlabEdgeThickeningFootingShadowAuthority:
    """Authority for analyzing structural foundation footings and slab edge thickenings in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        """Snaps pt to reference_points if within SNAP_TOLERANCE_PT."""
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
    def parse_beam_annotation(annotation: str) -> Tuple[FootingBeamType, float, float, Optional[BrickRebateSpec]]:
        """
        Parses engineering text annotations, e.g.:
        - 'EDGE BEAM 300W x 450D W/ 110x50 REBATE'
        - 'STRIP FOOTING 450W x 600D'
        - 'INTERNAL RIB 300W x 300D'
        """
        clean = annotation.upper().strip()

        # Type determination
        if "EDGE" in clean:
            b_type = FootingBeamType.EDGE_BEAM
        elif "STRIP" in clean:
            b_type = FootingBeamType.STRIP_FOOTING
        elif "PAD" in clean:
            b_type = FootingBeamType.PAD_FOOTING
        elif "INTERNAL" in clean or "RIB" in clean or "STIFFENER" in clean:
            b_type = FootingBeamType.INTERNAL_STIFFENER
        else:
            b_type = FootingBeamType.INTERNAL_STIFFENER

        # Dimension parsing: (\d+)\s*W\s*[xX]\s*(\d+)\s*D or (\d+)\s*[xX]\s*(\d+)
        width_mm = 300.0
        depth_mm = 400.0

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

        # Rebate parsing
        rebate = None
        if "REBATE" in clean or "REB" in clean:
            reb_match = re.search(r"(\d+)\s*[xX]\s*(\d+)\s*(?:REB|REBATE)", clean)
            if reb_match:
                rebate = BrickRebateSpec(
                    width_mm=float(reb_match.group(1)),
                    depth_mm=float(reb_match.group(2))
                )
            else:
                # Default brick rebate if mentioned but unmeasured
                rebate = BrickRebateSpec(width_mm=110.0, depth_mm=50.0)

        return b_type, width_mm, depth_mm, rebate

    @classmethod
    def evaluate_footings(
        cls,
        beams: List[FootingBeamSpec],
        drawing_scale: float = 1.0  # units in drawing points/mm to real meters conversion
    ) -> FoundationFootingExtractionResult:
        """
        Calculates centerline lengths, excavation volumes, concrete volumes,
        and outer edge formwork area.
        drawing_scale: meters per drawing point/unit.
        """
        total_length_m = 0.0
        total_excavation_m3 = 0.0
        total_concrete_m3 = 0.0
        total_edge_formwork_m2 = 0.0
        total_rebate_m = 0.0

        for b in beams:
            raw_len = cls.compute_polyline_length(b.centerline_points)
            length_m = raw_len * drawing_scale
            total_length_m += length_m

            w_m = b.width_mm / 1000.0
            d_m = b.depth_mm / 1000.0

            # Excavation is the gross rectangular trench
            excav_vol = length_m * w_m * d_m
            total_excavation_m3 += excav_vol

            # Concrete volume accounts for rebate cutout if applicable
            conc_cross_section = w_m * d_m
            if b.rebate:
                rw_m = b.rebate.width_mm / 1000.0
                rd_m = b.rebate.depth_mm / 1000.0
                rebate_cutout = rw_m * rd_m
                conc_cross_section = max(0.0, conc_cross_section - rebate_cutout)
                total_rebate_m += length_m

            total_concrete_m3 += length_m * conc_cross_section

            # Edge formwork applies to exterior vertical faces of EDGE_BEAM
            if b.beam_type == FootingBeamType.EDGE_BEAM:
                total_edge_formwork_m2 += length_m * d_m

        quantities = FoundationQuantities(
            total_centerline_length_m=round(total_length_m, 3),
            total_excavation_volume_m3=round(total_excavation_m3, 3),
            total_concrete_volume_m3=round(total_concrete_m3, 3),
            total_edge_formwork_area_m2=round(total_edge_formwork_m2, 3),
            rebate_length_m=round(total_rebate_m, 3)
        )

        return FoundationFootingExtractionResult(
            beams=beams,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"extracted_beam_count": str(len(beams))}
        )
