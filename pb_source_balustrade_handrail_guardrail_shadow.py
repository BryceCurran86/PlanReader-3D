"""
pb_source_balustrade_handrail_guardrail_shadow.py

Authoritative shadow-mode extraction and quantification for safety balustrades,
edge guardrails, barrier infill panels, support post stanchions, and continuous handrails.

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


class BarrierLocationKind(str, Enum):
    BALCONY_TERRACE = "BALCONY_TERRACE"
    STAIR_FLIGHT = "STAIR_FLIGHT"
    RAMP = "RAMP"
    INTERNAL_VOID = "INTERNAL_VOID"


class BarrierInfillType(str, Enum):
    FRAMELESS_GLASS = "FRAMELESS_GLASS"
    VERTICAL_BALUSTERS = "VERTICAL_BALUSTERS"
    HORIZONTAL_WIRE_CABLE = "HORIZONTAL_WIRE_CABLE"
    PERFORATED_METAL = "PERFORATED_METAL"


@dataclass
class BalustradeRunSpec:
    run_id: str
    location_kind: BarrierLocationKind
    infill_type: BarrierInfillType
    centerline_points: List[Tuple[float, float]]
    height_mm: float = 0.0
    post_spacing_mm: float = 0.0
    has_continuous_handrail: bool = False
    handrail_extension_m: float = 0.30
    level_id: str = "L1"
    source_tag: str = ""


@dataclass
class BalustradeQuantities:
    total_balustrade_count: int
    total_linear_run_m: float
    total_barrier_face_area_m2: float
    total_handrail_length_m: float
    total_post_count: int
    non_compliant_height_count: int


@dataclass
class BalustradeExtractionResult:
    runs: List[BalustradeRunSpec]
    quantities: BalustradeQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceBalustradeHandrailGuardrailShadowAuthority:
    """Authority for analyzing balustrades, guardrails, and handrails in shadow mode."""

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
    def parse_balustrade_annotation(annotation: str) -> Tuple[BarrierLocationKind, BarrierInfillType, float, bool]:
        """
        Parses annotation, e.g.:
        'FRAMELESS GLASS BALUSTRADE 1100 HIGH W/ CONTINUOUS HANDRAIL' or 'STAIR BALUSTRADE 1000H VERTICAL PICKETS'
        Returns (location_kind, infill_type, height_mm, has_handrail)
        """
        clean = annotation.upper().strip()

        # Location kind
        if "STAIR" in clean:
            loc = BarrierLocationKind.STAIR_FLIGHT
        elif "RAMP" in clean:
            loc = BarrierLocationKind.RAMP
        elif "VOID" in clean or "ATRIUM" in clean or "MEZZANINE" in clean:
            loc = BarrierLocationKind.INTERNAL_VOID
        else:
            loc = BarrierLocationKind.BALCONY_TERRACE

        # Infill type
        if "GLASS" in clean:
            infill = BarrierInfillType.FRAMELESS_GLASS
        elif "WIRE" in clean or "CABLE" in clean:
            infill = BarrierInfillType.HORIZONTAL_WIRE_CABLE
        elif "PERF" in clean or "PERFORATED" in clean:
            infill = BarrierInfillType.PERFORATED_METAL
        else:
            infill = BarrierInfillType.VERTICAL_BALUSTERS

        # Height: (\d+)\s*(?:MM)?\s*(?:H\b|HIGH|HEIGHT)
        h_match = re.search(r"(\d+)\s*(?:MM)?\s*(?:H\b|HIGH|HEIGHT)", clean)
        height_mm = float(h_match.group(1)) if h_match else 0.0

        # Handrail presence
        has_hr = "HANDRAIL" in clean or re.search(r"\bRAIL\b", clean) is not None

        return loc, infill, height_mm, has_hr

    @classmethod
    def evaluate_balustrades(
        cls,
        runs: List[BalustradeRunSpec],
        drawing_scale: float = 1.0
    ) -> BalustradeExtractionResult:
        total_len_m = 0.0
        total_area_m2 = 0.0
        total_handrail_m = 0.0
        total_posts = 0
        non_compliant_count = 0

        for r in runs:
            raw_len = cls.compute_polyline_length(r.centerline_points)
            len_m = raw_len * drawing_scale
            total_len_m += len_m

            h_m = r.height_mm / 1000.0
            total_area_m2 += len_m * h_m

            # Compliance check: min 1100mm on balcony/terrace, min 1000mm on stairs/ramps
            min_req_h = 1100.0 if r.location_kind == BarrierLocationKind.BALCONY_TERRACE else 1000.0
            if r.height_mm > 0.0 and r.height_mm < min_req_h:
                non_compliant_count += 1

            if r.has_continuous_handrail:
                # Add 2 extensions (start and end) if on stair or ramp
                ext_m = (2.0 * r.handrail_extension_m) if r.location_kind in (BarrierLocationKind.STAIR_FLIGHT, BarrierLocationKind.RAMP) else 0.0
                total_handrail_m += len_m + ext_m

            post_sp_m = r.post_spacing_mm / 1000.0
            posts = math.ceil(len_m / post_sp_m) + 1 if len_m > 0 and post_sp_m > 0 else 0
            total_posts += posts

        quantities = BalustradeQuantities(
            total_balustrade_count=len(runs),
            total_linear_run_m=round(total_len_m, 3),
            total_barrier_face_area_m2=round(total_area_m2, 3),
            total_handrail_length_m=round(total_handrail_m, 3),
            total_post_count=total_posts,
            non_compliant_height_count=non_compliant_count
        )

        return BalustradeExtractionResult(
            runs=runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"balustrade_run_count": str(len(runs))}
        )
