"""
pb_source_crane_runway_girder_rail_shadow.py

Authoritative shadow-mode extraction and structural takeoff for crane runway girders,
crane rails, resilient pads, adjustable clips, and buffer end stops.

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


class CraneRunwayType(str, Enum):
    OVERHEAD_BRIDGE_CRANE_RUNWAY = "OVERHEAD_BRIDGE_CRANE_RUNWAY"
    MONORAIL_HOIST_BEAM = "MONORAIL_HOIST_BEAM"
    GANTRY_PORTAL_RAIL = "GANTRY_PORTAL_RAIL"
    WALL_JIB_CRANE_TRACK = "WALL_JIB_CRANE_TRACK"


class CraneRailMountingType(str, Enum):
    RESILIENT_ELASTOMERIC_PAD = "RESILIENT_ELASTOMERIC_PAD"
    DIRECT_STEEL_BEARING = "DIRECT_STEEL_BEARING"


@dataclass
class CraneRunwayRunSpec:
    run_id: str
    runway_type: CraneRunwayType = CraneRunwayType.OVERHEAD_BRIDGE_CRANE_RUNWAY
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    girder_section: str = "610UB125"
    rail_section: str = "CR50"
    mounting_type: CraneRailMountingType = CraneRailMountingType.RESILIENT_ELASTOMERIC_PAD
    clip_spacing_m: float = 0.6
    buffer_stops_count: int = 2
    level_id: str = "CRANE_LEVEL"
    source_callout: str = ""


@dataclass
class CraneRunwayQuantities:
    total_runs_count: int = 0
    total_girder_length_meters: float = 0.0
    total_rail_length_meters: float = 0.0
    total_resilient_pad_meters: float = 0.0
    total_rail_clips_count: int = 0
    total_buffer_stops_count: int = 0
    length_by_type: Dict[str, float] = field(default_factory=dict)
    girders_by_section: Dict[str, float] = field(default_factory=dict)


@dataclass
class CraneRunwayExtractionResult:
    runs: List[CraneRunwayRunSpec] = field(default_factory=list)
    quantities: CraneRunwayQuantities = field(default_factory=CraneRunwayQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceCraneRunwayGirderRailShadowAuthority:
    """Authoritative shadow evaluator for crane runway girders, rails, and clips."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses crane runway schedule callouts.
        Example strings:
          - "610UB125 CRANE RUNWAY GIRDER W/ CR50 RAIL ON RESILIENT PAD & CLIPS AT 600mm CTS W/ 2x BUFFERS"
          - "700WB150 RUNWAY BEAM W/ CR60 RAIL CLIPS AT 0.5m"
          - "310UB40.4 MONORAIL HOIST BEAM"
          - "GANTRY PORTAL RAIL 50KG/M DIRECT BEARING"
        """
        clean = text.upper()
        res = {
            "runway_type": CraneRunwayType.OVERHEAD_BRIDGE_CRANE_RUNWAY,
            "girder_section": "610UB125",
            "rail_section": "CR50",
            "mounting_type": CraneRailMountingType.RESILIENT_ELASTOMERIC_PAD,
            "clip_spacing_m": 0.6,
            "buffer_stops_count": 2,
        }

        # Typology
        if "MONORAIL" in clean or "HOIST BEAM" in clean:
            res["runway_type"] = CraneRunwayType.MONORAIL_HOIST_BEAM
            res["rail_section"] = "BOTTOM_FLANGE_TROLLEY"
            res["girder_section"] = "310UB40.4"
        elif "GANTRY" in clean:
            res["runway_type"] = CraneRunwayType.GANTRY_PORTAL_RAIL
        elif "JIB" in clean:
            res["runway_type"] = CraneRunwayType.WALL_JIB_CRANE_TRACK
        else:
            res["runway_type"] = CraneRunwayType.OVERHEAD_BRIDGE_CRANE_RUNWAY

        # Mounting
        if "DIRECT" in clean or "STEEL BEARING" in clean:
            res["mounting_type"] = CraneRailMountingType.DIRECT_STEEL_BEARING
        else:
            res["mounting_type"] = CraneRailMountingType.RESILIENT_ELASTOMERIC_PAD

        # Girder section: 610UB125, 700WB150, 310UB40.4, 460UB
        girder_match = re.search(r'\b(\d{3}(?:UB|WB|UC|PFC)\d+(?:\.\d+)?)\b', clean)
        if girder_match:
            res["girder_section"] = girder_match.group(1)

        # Rail section: CR50, CR60, CR73, CR100, 50KG/M, 60KG/M
        rail_match = re.search(r'\b(CR\s*\d{2,3}|\d{2}\s*KG/M)\b', clean)
        if rail_match:
            res["rail_section"] = rail_match.group(1).replace(" ", "")

        # Clip spacing: CLIPS AT 600mm CTS, 0.5m CTS
        clip_match = re.search(r'CLIPS\s*(?:AT\s*)?(\d+(?:\.\d+)?)\s*(MM|M)?', clean)
        if clip_match:
            try:
                val = float(clip_match.group(1))
                unit = clip_match.group(2) or "MM"
                if unit == "MM" and val > 10.0:
                    val /= 1000.0
                if 0.2 <= val <= 2.0:
                    res["clip_spacing_m"] = val
            except ValueError:
                pass

        # Buffer stops count: 2x BUFFERS, 2 BUFFERS, 4 BUFFERS
        buf_match = re.search(r'(\d+)\s*[xX]?\s*BUFFER', clean)
        if buf_match:
            try:
                res["buffer_stops_count"] = int(buf_match.group(1))
            except ValueError:
                res["buffer_stops_count"] = 2

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @staticmethod
    def calculate_polyline_length(points: List[Tuple[float, float]], scale_ratio: float = 0.001) -> float:
        if len(points) < 2:
            return 0.0
        tot_len = 0.0
        for i in range(len(points) - 1):
            p1 = points[i]
            p2 = points[i + 1]
            tot_len += math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        return round(tot_len * scale_ratio, 4)

    @classmethod
    def evaluate_runway_runs(
        cls,
        raw_runs_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "CRANE_LEVEL"
    ) -> CraneRunwayExtractionResult:
        """
        Authoritative shadow extraction for crane runway girders, rails, and hardware.
        """
        extracted_runs: List[CraneRunwayRunSpec] = []
        tot_girder_m = 0.0
        tot_rail_m = 0.0
        tot_pad_m = 0.0
        tot_clips = 0
        tot_buffers = 0

        len_by_type: Dict[str, float] = {}
        girders_by_sec: Dict[str, float] = {}

        for item in raw_runs_data:
            run_id = item.get("run_id", f"CR_{len(extracted_runs)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            rtype_val = item.get("runway_type", parsed["runway_type"])
            if isinstance(rtype_val, str):
                try:
                    rtype = CraneRunwayType(rtype_val)
                except ValueError:
                    rtype = CraneRunwayType.OVERHEAD_BRIDGE_CRANE_RUNWAY
            else:
                rtype = rtype_val

            mtype_val = item.get("mounting_type", parsed["mounting_type"])
            if isinstance(mtype_val, str):
                try:
                    mtype = CraneRailMountingType(mtype_val)
                except ValueError:
                    mtype = CraneRailMountingType.RESILIENT_ELASTOMERIC_PAD
            else:
                mtype = mtype_val

            girder_sec = item.get("girder_section", parsed["girder_section"])
            rail_sec = item.get("rail_section", parsed["rail_section"])
            spc_m = float(item.get("clip_spacing_m", parsed["clip_spacing_m"]))
            bufs_cnt = int(item.get("buffer_stops_count", parsed["buffer_stops_count"]))

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            if rtype == CraneRunwayType.MONORAIL_HOIST_BEAM:
                rail_len_m = 0.0
                pad_len_m = 0.0
                clips_cnt = 0
            else:
                rail_len_m = run_len_m
                pad_len_m = run_len_m if mtype == CraneRailMountingType.RESILIENT_ELASTOMERIC_PAD else 0.0
                # 2 clips (pair) per spacing interval
                if run_len_m > 0.0 and spc_m > 0.0:
                    clips_cnt = 2 * (int(math.ceil(run_len_m / spc_m)) + 1)
                else:
                    clips_cnt = 4

            spec = CraneRunwayRunSpec(
                run_id=run_id,
                runway_type=rtype,
                centerline_points=snapped_pts,
                girder_section=girder_sec,
                rail_section=rail_sec,
                mounting_type=mtype,
                clip_spacing_m=spc_m,
                buffer_stops_count=bufs_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_runs.append(spec)

            tot_girder_m += run_len_m
            tot_rail_m += rail_len_m
            tot_pad_m += pad_len_m
            tot_clips += clips_cnt
            tot_buffers += bufs_cnt

            t_key = rtype.value
            len_by_type[t_key] = round(len_by_type.get(t_key, 0.0) + run_len_m, 4)

            girders_by_sec[girder_sec] = round(girders_by_sec.get(girder_sec, 0.0) + run_len_m, 4)

        quantities = CraneRunwayQuantities(
            total_runs_count=len(extracted_runs),
            total_girder_length_meters=round(tot_girder_m, 4),
            total_rail_length_meters=round(tot_rail_m, 4),
            total_resilient_pad_meters=round(tot_pad_m, 4),
            total_rail_clips_count=tot_clips,
            total_buffer_stops_count=tot_buffers,
            length_by_type=len_by_type,
            girders_by_section=girders_by_sec,
        )

        return CraneRunwayExtractionResult(
            runs=extracted_runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceCraneRunwayGirderRailShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
