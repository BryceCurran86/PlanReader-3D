"""
pb_source_pt_slab_tendon_anchorage_shadow.py

Authoritative shadow-mode extraction and quantification for post-tensioned (PT)
concrete slab tendon bands, distributed strands, live stressing pockets, and
grout infill volumes.

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
STRAND_12_7_KG_M: float = 0.785
STRAND_15_2_KG_M: float = 1.101


class TendonArrangementType(str, Enum):
    BANDED = "BANDED"
    DISTRIBUTED = "DISTRIBUTED"


class AnchorageType(str, Enum):
    LIVE_END_STRESSING = "LIVE_END_STRESSING"
    DEAD_END_BLIND = "DEAD_END_BLIND"
    COUPLER = "COUPLER"


@dataclass
class AnchoragePocketSpec:
    pocket_id: str
    anchorage_type: AnchorageType
    location: Tuple[float, float]
    width_mm: float = 0.0
    height_mm: float = 0.0
    depth_mm: float = 0.0


@dataclass
class TendonRunSpec:
    tendon_id: str
    arrangement_type: TendonArrangementType
    centerline_points: List[Tuple[float, float]]
    strand_count: int = 0
    strand_diameter_mm: float = 0.0
    anchor_start: Optional[AnchoragePocketSpec] = None
    anchor_end: Optional[AnchoragePocketSpec] = None
    level_id: str = "L1"
    source_callout: str = ""


@dataclass
class PTSystemQuantities:
    total_tendon_run_count: int
    total_tendon_path_length_m: float
    total_strand_length_m: float
    total_prestressing_steel_mass_kg: float
    total_live_anchorage_count: int
    total_dead_anchorage_count: int
    total_pocket_grout_volume_m3: float


@dataclass
class PTSystemExtractionResult:
    tendons: List[TendonRunSpec]
    quantities: PTSystemQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourcePTSlabTendonAnchorageShadowAuthority:
    """Authority for analyzing post-tensioned slab tendons and stressing anchorages in shadow mode."""

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
    def parse_tendon_annotation(annotation: str) -> Tuple[TendonArrangementType, int, float]:
        """
        Parses annotation, e.g.:
        'BANDED TENDON 5S12.7' or 'DISTRIBUTED 4S12.7 @ 1500 CTS'
        Returns (arrangement_type, strand_count, strand_diameter_mm)
        """
        clean = annotation.upper().strip()

        # Arrangement type
        if "BAND" in clean:
            arr_type = TendonArrangementType.BANDED
        else:
            arr_type = TendonArrangementType.DISTRIBUTED

        # Strand count & diameter: (\d+)\s*S\s*(\d+(?:\.\d+)?)
        s_match = re.search(r"(\d+)\s*S\s*(\d+(?:\.\d+)?)", clean)
        if s_match:
            strand_cnt = int(s_match.group(1))
            strand_dia = float(s_match.group(2))
        else:
            cnt_match = re.search(r"(\d+)\s*(?:STRAND|STR)", clean)
            strand_cnt = int(cnt_match.group(1)) if cnt_match else 0
            strand_dia = 0.0

        return arr_type, strand_cnt, strand_dia

    @classmethod
    def evaluate_pt_system(
        cls,
        tendons: List[TendonRunSpec],
        drawing_scale: float = 1.0  # meters per coordinate unit
    ) -> PTSystemExtractionResult:
        total_path_len_m = 0.0
        total_strand_len_m = 0.0
        total_steel_mass_kg = 0.0
        live_anchors = 0
        dead_anchors = 0
        total_grout_vol_m3 = 0.0

        for t in tendons:
            raw_len = cls.compute_polyline_length(t.centerline_points)
            path_len_m = raw_len * drawing_scale
            total_path_len_m += path_len_m

            strand_len_m = path_len_m * t.strand_count
            total_strand_len_m += strand_len_m

            if t.strand_diameter_mm <= 0.0 or t.strand_count <= 0:
                unit_mass = 0.0
            elif t.strand_diameter_mm > 14.0:
                unit_mass = STRAND_15_2_KG_M
            else:
                unit_mass = STRAND_12_7_KG_M
            total_steel_mass_kg += strand_len_m * unit_mass

            # Check start and end anchorages
            for anc in (t.anchor_start, t.anchor_end):
                if anc:
                    if anc.anchorage_type == AnchorageType.LIVE_END_STRESSING:
                        live_anchors += 1
                        # Pocket grout volume
                        pw_m = anc.width_mm / 1000.0
                        ph_m = anc.height_mm / 1000.0
                        pd_m = anc.depth_mm / 1000.0
                        total_grout_vol_m3 += pw_m * ph_m * pd_m
                    elif anc.anchorage_type == AnchorageType.DEAD_END_BLIND:
                        dead_anchors += 1

        quantities = PTSystemQuantities(
            total_tendon_run_count=len(tendons),
            total_tendon_path_length_m=round(total_path_len_m, 3),
            total_strand_length_m=round(total_strand_len_m, 3),
            total_prestressing_steel_mass_kg=round(total_steel_mass_kg, 2),
            total_live_anchorage_count=live_anchors,
            total_dead_anchorage_count=dead_anchors,
            total_pocket_grout_volume_m3=round(total_grout_vol_m3, 4)
        )

        return PTSystemExtractionResult(
            tendons=tendons,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"tendon_count": str(len(tendons))}
        )
