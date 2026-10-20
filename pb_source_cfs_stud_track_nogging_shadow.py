"""
pb_source_cfs_stud_track_nogging_shadow.py

Authoritative shadow-mode extraction and structural takeoff for cold-formed steel (CFS)
stud wall framing, top deflection track, bottom runner track, and horizontal noggings.

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


class CFSFramingType(str, Enum):
    INTERNAL_NON_LOADBEARING_STUD = "INTERNAL_NON_LOADBEARING_STUD"
    STRUCTURAL_LOADBEARING_CFS_STUD = "STRUCTURAL_LOADBEARING_CFS_STUD"
    ACOUSTIC_STAGGERED_STUD = "ACOUSTIC_STAGGERED_STUD"
    SHAFTWALL_CH_STUD = "SHAFTWALL_CH_STUD"


class HeadTrackType(str, Enum):
    SLOTTED_DEFLECTION_TRACK = "SLOTTED_DEFLECTION_TRACK"
    STANDARD_DEEP_LEG_TRACK = "STANDARD_DEEP_LEG_TRACK"


@dataclass
class CFSFramingRunSpec:
    wall_id: str
    framing_type: CFSFramingType = CFSFramingType.INTERNAL_NON_LOADBEARING_STUD
    head_track_type: HeadTrackType = HeadTrackType.SLOTTED_DEFLECTION_TRACK
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    stud_depth_mm: float = 92.0
    stud_bmt_mm: float = 0.75
    stud_spacing_mm: float = 450.0
    wall_height_m: float = 3.0
    nogging_rows_count: int = 2
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class CFSFramingQuantities:
    total_walls_count: int = 0
    total_wall_length_meters: float = 0.0
    total_track_length_meters: float = 0.0
    total_nogging_length_meters: float = 0.0
    total_studs_count: int = 0
    total_stud_linear_meters: float = 0.0
    length_by_framing_type: Dict[str, float] = field(default_factory=dict)
    studs_by_depth: Dict[str, int] = field(default_factory=dict)


@dataclass
class CFSFramingExtractionResult:
    runs: List[CFSFramingRunSpec] = field(default_factory=list)
    quantities: CFSFramingQuantities = field(default_factory=CFSFramingQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceCFSStudTrackNoggingShadowAuthority:
    """Authoritative shadow evaluator for light-gauge steel stud wall framing components."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses CFS stud wall schedule callouts.
        Example strings:
          - "92mm x 0.75 BMT STEEL STUDS AT 450mm CTS W/ SLOTTED DEFLECTION HEAD TRACK & 2 ROWS NOGGINGS"
          - "150mm x 1.15 BMT STRUCTURAL CFS STUDS AT 400mm CTS"
          - "64mm x 0.50 BMT NON-LOADBEARING STUDS AT 600mm CTS"
          - "SHAFTWALL 100mm C-H STUDS AT 600mm CTS"
        """
        clean = text.upper()
        res = {
            "framing_type": CFSFramingType.INTERNAL_NON_LOADBEARING_STUD,
            "head_track_type": HeadTrackType.SLOTTED_DEFLECTION_TRACK,
            "stud_depth_mm": 92.0,
            "stud_bmt_mm": 0.75,
            "stud_spacing_mm": 450.0,
            "nogging_rows_count": 2,
        }

        # Typology
        if "SHAFTWALL" in clean or "C-H" in clean:
            res["framing_type"] = CFSFramingType.SHAFTWALL_CH_STUD
            res["stud_depth_mm"] = 100.0
            res["stud_spacing_mm"] = 600.0
        elif "STRUCTURAL" in clean or "LOADBEARING" in clean:
            res["framing_type"] = CFSFramingType.STRUCTURAL_LOADBEARING_CFS_STUD
            res["stud_depth_mm"] = 150.0
            res["stud_bmt_mm"] = 1.15
            res["stud_spacing_mm"] = 400.0
        elif "STAGGERED" in clean or "ACOUSTIC" in clean:
            res["framing_type"] = CFSFramingType.ACOUSTIC_STAGGERED_STUD
        else:
            res["framing_type"] = CFSFramingType.INTERNAL_NON_LOADBEARING_STUD

        # Head track type
        if "SLOTTED" in clean or "DEFLECTION" in clean:
            res["head_track_type"] = HeadTrackType.SLOTTED_DEFLECTION_TRACK
        else:
            res["head_track_type"] = HeadTrackType.STANDARD_DEEP_LEG_TRACK

        # Stud depth: 64mm, 76mm, 92mm, 100mm, 150mm
        d_match = re.search(r'(\d{2,3})\s*MM\s*(?:x|[xX*])?', clean)
        if d_match:
            try:
                d = float(d_match.group(1))
                if 50.0 <= d <= 300.0:
                    res["stud_depth_mm"] = d
            except ValueError:
                pass

        # BMT thickness: 0.50, 0.55, 0.75, 1.15 BMT
        bmt_match = re.search(r'(\d\.\d{2})\s*(?:BMT|MM\s*BMT)?', clean)
        if bmt_match:
            try:
                res["stud_bmt_mm"] = float(bmt_match.group(1))
            except ValueError:
                pass

        # Spacing: AT 450mm CTS, 600mm CTS, 400mm CTS
        spc_match = re.search(r'(?:AT\s*)?(\d{3})\s*MM\s*(?:CTS|CENTRES|CENTERS|SPACING)?', clean)
        if spc_match:
            try:
                s = float(spc_match.group(1))
                if 200.0 <= s <= 900.0:
                    res["stud_spacing_mm"] = s
            except ValueError:
                pass

        # Nogging rows count: 2 ROWS NOGGINGS, 1 ROW NOGGING, 3 NOGGINGS
        nog_match = re.search(r'(\d+)\s*(?:ROWS?\s*)?NOGGING', clean)
        if nog_match:
            try:
                res["nogging_rows_count"] = int(nog_match.group(1))
            except ValueError:
                pass

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
    def evaluate_cfs_runs(
        cls,
        raw_runs_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01",
        default_height_m: float = 3.0
    ) -> CFSFramingExtractionResult:
        """
        Authoritative shadow extraction for cold-formed steel stud wall framing.
        """
        extracted_runs: List[CFSFramingRunSpec] = []
        tot_wall_len_m = 0.0
        tot_track_len_m = 0.0
        tot_nog_len_m = 0.0
        tot_studs = 0
        tot_stud_m = 0.0

        len_by_type: Dict[str, float] = {}
        studs_by_d: Dict[str, int] = {}

        for item in raw_runs_data:
            wall_id = item.get("wall_id", f"W_CFS_{len(extracted_runs)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ftype_val = item.get("framing_type", parsed["framing_type"])
            if isinstance(ftype_val, str):
                try:
                    ftype = CFSFramingType(ftype_val)
                except ValueError:
                    ftype = CFSFramingType.INTERNAL_NON_LOADBEARING_STUD
            else:
                ftype = ftype_val

            htrack_val = item.get("head_track_type", parsed["head_track_type"])
            if isinstance(htrack_val, str):
                try:
                    htrack = HeadTrackType(htrack_val)
                except ValueError:
                    htrack = HeadTrackType.SLOTTED_DEFLECTION_TRACK
            else:
                htrack = htrack_val

            d_mm = float(item.get("stud_depth_mm", parsed["stud_depth_mm"]))
            bmt_mm = float(item.get("stud_bmt_mm", parsed["stud_bmt_mm"]))
            spc_mm = float(item.get("stud_spacing_mm", parsed["stud_spacing_mm"]))
            h_m = float(item.get("wall_height_m", default_height_m))
            nog_rows = int(item.get("nogging_rows_count", parsed["nogging_rows_count"]))

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            # Track length: top track + bottom track = 2 * length
            track_m = round(2.0 * run_len_m, 4)

            # Nogging length: length * rows
            nog_m = round(run_len_m * nog_rows, 4)

            # Stud count: ceil(length_mm / spacing_mm) + 1
            if run_len_m > 0.0 and spc_mm > 0.0:
                studs_cnt = int(math.ceil((run_len_m * 1000.0) / spc_mm)) + 1
            else:
                studs_cnt = 2

            stud_linear_m = round(studs_cnt * h_m, 4)

            spec = CFSFramingRunSpec(
                wall_id=wall_id,
                framing_type=ftype,
                head_track_type=htrack,
                centerline_points=snapped_pts,
                stud_depth_mm=d_mm,
                stud_bmt_mm=bmt_mm,
                stud_spacing_mm=spc_mm,
                wall_height_m=h_m,
                nogging_rows_count=nog_rows,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_runs.append(spec)

            tot_wall_len_m += run_len_m
            tot_track_len_m += track_m
            tot_nog_len_m += nog_m
            tot_studs += studs_cnt
            tot_stud_m += stud_linear_m

            t_key = ftype.value
            len_by_type[t_key] = round(len_by_type.get(t_key, 0.0) + run_len_m, 4)

            d_key = f"{int(d_mm)}mm"
            studs_by_d[d_key] = studs_by_d.get(d_key, 0) + studs_cnt

        quantities = CFSFramingQuantities(
            total_walls_count=len(extracted_runs),
            total_wall_length_meters=round(tot_wall_len_m, 4),
            total_track_length_meters=round(tot_track_len_m, 4),
            total_nogging_length_meters=round(tot_nog_len_m, 4),
            total_studs_count=tot_studs,
            total_stud_linear_meters=round(tot_stud_m, 4),
            length_by_framing_type=len_by_type,
            studs_by_depth=studs_by_d,
        )

        return CFSFramingExtractionResult(
            runs=extracted_runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceCFSStudTrackNoggingShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
