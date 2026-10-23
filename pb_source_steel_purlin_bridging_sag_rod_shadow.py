"""
pb_source_steel_purlin_bridging_sag_rod_shadow.py

Authoritative shadow-mode extraction and structural takeoff for purlin bridging lines,
sag rod tension ties, apex bridging systems, and turnbuckle hardware.

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


class PurlinBridgingType(str, Enum):
    SOLID_BRIDGING_STRUT = "SOLID_BRIDGING_STRUT"
    SAG_ROD_TENSION_TIE = "SAG_ROD_TENSION_TIE"
    APEX_BRIDGING_SYSTEM = "APEX_BRIDGING_SYSTEM"
    FASCIA_DIAGONAL_BRACE = "FASCIA_DIAGONAL_BRACE"


@dataclass
class PurlinBridgingRunSpec:
    run_id: str
    bridging_type: PurlinBridgingType = PurlinBridgingType.SOLID_BRIDGING_STRUT
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    profile_designation: str = "PB150"
    sag_rod_diameter_mm: float = 12.0
    purlin_spacing_m: float = 1.2
    apex_ties_count: int = 1
    turnbuckles_count: int = 2
    level_id: str = "ROOF"
    source_callout: str = ""


@dataclass
class PurlinBridgingQuantities:
    total_runs_count: int = 0
    total_length_meters: float = 0.0
    total_bridging_struts_count: int = 0
    total_sag_rods_count: int = 0
    total_turnbuckles_count: int = 0
    total_apex_ties_count: int = 0
    length_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class PurlinBridgingExtractionResult:
    runs: List[PurlinBridgingRunSpec] = field(default_factory=list)
    quantities: PurlinBridgingQuantities = field(default_factory=PurlinBridgingQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSteelPurlinBridgingSagRodShadowAuthority:
    """Authoritative shadow evaluator for purlin bridging lines and sag rod hardware."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses purlin bridging schedule callouts.
        Example strings:
          - "MIDSPAN PURLIN BRIDGING PB200 W/ M12 SAG RODS & 2x TURNBUCKLES"
          - "PB150 SOLID BRIDGING STRUT W/ M16 SAG RODS"
          - "APEX BRIDGING SYSTEM W/ 2x APEX TIES"
          - "FASCIA DIAGONAL BRACE"
        """
        clean = text.upper()
        res = {
            "bridging_type": PurlinBridgingType.SOLID_BRIDGING_STRUT,
            "profile_designation": "PB150",
            "sag_rod_diameter_mm": 12.0,
            "purlin_spacing_m": 1.2,
            "apex_ties_count": 0,
            "turnbuckles_count": 2,
        }

        # Typology
        if "APEX" in clean:
            res["bridging_type"] = PurlinBridgingType.APEX_BRIDGING_SYSTEM
            res["apex_ties_count"] = 2
        elif "FASCIA" in clean or "DIAGONAL" in clean:
            res["bridging_type"] = PurlinBridgingType.FASCIA_DIAGONAL_BRACE
        elif "SAG ROD" in clean and "SOLID" not in clean and "PB" not in clean:
            res["bridging_type"] = PurlinBridgingType.SAG_ROD_TENSION_TIE
        else:
            res["bridging_type"] = PurlinBridgingType.SOLID_BRIDGING_STRUT

        # Profile designation: PB150, PB200, PB100, PB250
        prof_match = re.search(r'\b(PB\d{3})\b', clean)
        if prof_match:
            res["profile_designation"] = prof_match.group(1)

        # Sag rod diameter: M12, M16, M20, 12mm SAG ROD
        rod_match = re.search(r'(?:M|DIA\s*|Ø\s*)?(\d{2})\s*(?:MM)?\s*SAG\s*ROD', clean)
        if rod_match:
            try:
                res["sag_rod_diameter_mm"] = float(rod_match.group(1))
            except ValueError:
                pass
        elif re.search(r'\bM(12|16|20|24)\b', clean):
            m_match = re.search(r'\bM(12|16|20|24)\b', clean)
            res["sag_rod_diameter_mm"] = float(m_match.group(1))

        # Turnbuckles count: 2x TURNBUCKLES, 4 TURNBUCKLES
        tb_match = re.search(r'(\d+)\s*[xX]?\s*TURNBUCKLE', clean)
        if tb_match:
            try:
                res["turnbuckles_count"] = int(tb_match.group(1))
            except ValueError:
                res["turnbuckles_count"] = 2

        # Apex ties count: 2x APEX TIES
        apex_match = re.search(r'(\d+)\s*[xX]?\s*APEX\s*TIE', clean)
        if apex_match:
            try:
                res["apex_ties_count"] = int(apex_match.group(1))
            except ValueError:
                res["apex_ties_count"] = 1

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
    def evaluate_bridging_runs(
        cls,
        raw_runs_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "ROOF"
    ) -> PurlinBridgingExtractionResult:
        """
        Authoritative shadow extraction for purlin bridging runs and sag rod hardware.
        """
        extracted_runs: List[PurlinBridgingRunSpec] = []
        tot_length_m = 0.0
        tot_struts = 0
        tot_rods = 0
        tot_turnbuckles = 0
        tot_apex = 0

        length_by_type_dict: Dict[str, float] = {}

        for item in raw_runs_data:
            run_id = item.get("run_id", f"BR_{len(extracted_runs)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            btype_val = item.get("bridging_type", parsed["bridging_type"])
            if isinstance(btype_val, str):
                try:
                    btype = PurlinBridgingType(btype_val)
                except ValueError:
                    btype = PurlinBridgingType.SOLID_BRIDGING_STRUT
            else:
                btype = btype_val

            profile = item.get("profile_designation", parsed["profile_designation"])
            rod_dia = float(item.get("sag_rod_diameter_mm", parsed["sag_rod_diameter_mm"]))
            purlin_spc = float(item.get("purlin_spacing_m", parsed["purlin_spacing_m"]))
            tb_cnt = int(item.get("turnbuckles_count", parsed["turnbuckles_count"]))
            apx_cnt = int(item.get("apex_ties_count", parsed["apex_ties_count"]))

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            # Bridging bays calculation: number of purlin spaces along line
            bays_count = max(1, int(round(run_len_m / purlin_spc))) if purlin_spc > 0.0 else 1

            if btype == PurlinBridgingType.SOLID_BRIDGING_STRUT:
                strut_cnt = bays_count
                rod_cnt = bays_count
            elif btype == PurlinBridgingType.SAG_ROD_TENSION_TIE:
                strut_cnt = 0
                rod_cnt = bays_count
            elif btype == PurlinBridgingType.APEX_BRIDGING_SYSTEM:
                strut_cnt = bays_count
                rod_cnt = bays_count
            else:  # FASCIA_DIAGONAL_BRACE
                strut_cnt = 2
                rod_cnt = 0

            spec = PurlinBridgingRunSpec(
                run_id=run_id,
                bridging_type=btype,
                centerline_points=snapped_pts,
                profile_designation=profile,
                sag_rod_diameter_mm=rod_dia,
                purlin_spacing_m=purlin_spc,
                apex_ties_count=apx_cnt,
                turnbuckles_count=tb_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_runs.append(spec)

            tot_length_m += run_len_m
            tot_struts += strut_cnt
            tot_rods += rod_cnt
            tot_turnbuckles += tb_cnt
            tot_apex += apx_cnt

            t_key = btype.value
            length_by_type_dict[t_key] = round(length_by_type_dict.get(t_key, 0.0) + run_len_m, 4)

        quantities = PurlinBridgingQuantities(
            total_runs_count=len(extracted_runs),
            total_length_meters=round(tot_length_m, 4),
            total_bridging_struts_count=tot_struts,
            total_sag_rods_count=tot_rods,
            total_turnbuckles_count=tot_turnbuckles,
            total_apex_ties_count=tot_apex,
            length_by_type=length_by_type_dict,
        )

        return PurlinBridgingExtractionResult(
            runs=extracted_runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceSteelPurlinBridgingSagRodShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
