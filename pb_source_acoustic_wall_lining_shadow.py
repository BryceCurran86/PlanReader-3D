"""
pb_source_acoustic_wall_lining_shadow.py

Authoritative shadow-mode extraction and quantification for high-performance acoustic
wall assemblies, resilient furring channel mounts, discontinuous air gaps, and
multi-leaf high-density plasterboard linings.

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


class AcousticDecouplingType(str, Enum):
    DOUBLE_STUD_DISCONTINUOUS = "DOUBLE_STUD_DISCONTINUOUS"
    RESILIENT_CHANNEL_MOUNT = "RESILIENT_CHANNEL_MOUNT"
    STAGGERED_STUD = "STAGGERED_STUD"
    DIRECT_FIXED = "DIRECT_FIXED"


@dataclass
class AcousticWallSpec:
    wall_id: str
    decoupling_type: AcousticDecouplingType
    centerline_points: List[Tuple[float, float]]
    wall_height_m: float = 3.0
    air_gap_mm: float = 25.0
    side_a_layers: int = 2
    side_b_layers: int = 2
    target_rw: int = 50
    level_id: str = "L1"
    source_tag: str = ""


@dataclass
class AcousticWallQuantities:
    total_acoustic_wall_length_m: float
    total_wall_elevation_area_m2: float
    total_side_a_board_area_m2: float
    total_side_b_board_area_m2: float
    total_acoustic_board_area_m2: float
    total_resilient_channel_length_m: float
    total_perimeter_sealant_length_m: float


@dataclass
class AcousticWallExtractionResult:
    walls: List[AcousticWallSpec]
    quantities: AcousticWallQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceAcousticWallLiningShadowAuthority:
    """Authority for analyzing high-performance acoustic partitions in shadow mode."""

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
    def parse_acoustic_wall_tag(tag: str) -> Tuple[AcousticDecouplingType, int, int, int]:
        """
        Parses tag, e.g.:
        'ACOUSTIC WALL RW55 DOUBLE STUD 2x13mm + 2x13mm' or 'WALL RW50 RC-1 MOUNT 2x16mm + 1x16mm'
        Returns (decoupling_type, side_a_layers, side_b_layers, target_rw)
        """
        clean = tag.upper().strip()

        # Decoupling type
        if "DOUBLE" in clean or "TWIN" in clean or "DISCONTINUOUS" in clean:
            decoupling = AcousticDecouplingType.DOUBLE_STUD_DISCONTINUOUS
        elif "RC" in clean or "RESILIENT" in clean or "CHANNEL" in clean:
            decoupling = AcousticDecouplingType.RESILIENT_CHANNEL_MOUNT
        elif "STAGGERED" in clean:
            decoupling = AcousticDecouplingType.STAGGERED_STUD
        else:
            decoupling = AcousticDecouplingType.DIRECT_FIXED

        # Target Rw
        rw_match = re.search(r"RW\s*(\d+)", clean)
        target_rw = int(rw_match.group(1)) if rw_match else 50

        # Layer parsing: e.g. '2x13mm + 2x13mm' or '2x13 + 1x13'
        layer_matches = re.findall(r"(\d+)\s*[xX]\s*\d+", clean)
        if len(layer_matches) >= 2:
            side_a = int(layer_matches[0])
            side_b = int(layer_matches[1])
        elif len(layer_matches) == 1:
            side_a = int(layer_matches[0])
            side_b = int(layer_matches[0])
        else:
            side_a, side_b = 2, 2

        return decoupling, side_a, side_b, target_rw

    @classmethod
    def evaluate_acoustic_walls(
        cls,
        walls: List[AcousticWallSpec],
        drawing_scale: float = 1.0  # meters per drawing coordinate unit
    ) -> AcousticWallExtractionResult:
        total_len_m = 0.0
        total_elev_m2 = 0.0
        total_side_a_m2 = 0.0
        total_side_b_m2 = 0.0
        total_rc_m = 0.0
        total_sealant_m = 0.0

        for w in walls:
            raw_len = cls.compute_polyline_length(w.centerline_points)
            len_m = raw_len * drawing_scale
            total_len_m += len_m

            elev_m2 = len_m * w.wall_height_m
            total_elev_m2 += elev_m2

            side_a_m2 = elev_m2 * w.side_a_layers
            side_b_m2 = elev_m2 * w.side_b_layers
            total_side_a_m2 += side_a_m2
            total_side_b_m2 += side_b_m2

            # Resilient channel takeoff (channels at 600mm centers if RC mounted)
            if w.decoupling_type == AcousticDecouplingType.RESILIENT_CHANNEL_MOUNT:
                channel_rows = max(1, math.ceil(w.wall_height_m / 0.60))
                total_rc_m += len_m * channel_rows

            # Perimeter acoustic sealant (top track + bottom track + vertical ends, 2 beads)
            # perimeter = 2 * (len_m + wall_height_m)
            # double bead top/bottom/ends = 2 * (2 * len_m + 2 * wall_height_m)
            total_sealant_m += 2.0 * (2.0 * len_m + 2.0 * w.wall_height_m)

        quantities = AcousticWallQuantities(
            total_acoustic_wall_length_m=round(total_len_m, 3),
            total_wall_elevation_area_m2=round(total_elev_m2, 3),
            total_side_a_board_area_m2=round(total_side_a_m2, 3),
            total_side_b_board_area_m2=round(total_side_b_m2, 3),
            total_acoustic_board_area_m2=round(total_side_a_m2 + total_side_b_m2, 3),
            total_resilient_channel_length_m=round(total_rc_m, 3),
            total_perimeter_sealant_length_m=round(total_sealant_m, 3)
        )

        return AcousticWallExtractionResult(
            walls=walls,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"acoustic_wall_count": str(len(walls))}
        )
