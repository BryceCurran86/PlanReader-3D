"""
pb_source_lvl_glulam_timber_shadow.py

Authoritative shadow-mode extraction and structural takeoff for engineered timber framing:
Laminated Veneer Lumber (LVL), Glue-Laminated Timber (Glulam), multi-ply opening lintels,
and roof ridge beams.

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


class EngineeredTimberType(str, Enum):
    LAMINATED_VENEER_LUMBER_LVL = "LAMINATED_VENEER_LUMBER_LVL"
    GLUE_LAMINATED_TIMBER_GLULAM = "GLUE_LAMINATED_TIMBER_GLULAM"
    CROSS_LAMINATED_TIMBER_BEAM_CLT = "CROSS_LAMINATED_TIMBER_BEAM_CLT"
    SOLID_SAWN_F_GRADE = "SOLID_SAWN_F_GRADE"


class TimberFramingRole(str, Enum):
    OPENING_LINTEL = "OPENING_LINTEL"
    ROOF_RIDGE_BEAM = "ROOF_RIDGE_BEAM"
    FLOOR_BEARER_GIRDER = "FLOOR_BEARER_GIRDER"
    PORTAL_RAFTER = "PORTAL_RAFTER"
    CANTILEVER_VERANDAH_BEAM = "CANTILEVER_VERANDAH_BEAM"


@dataclass
class TimberBeamSpec:
    beam_id: str
    timber_type: EngineeredTimberType = EngineeredTimberType.LAMINATED_VENEER_LUMBER_LVL
    framing_role: TimberFramingRole = TimberFramingRole.OPENING_LINTEL
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    plies_count: int = 1
    ply_width_mm: float = 0.0
    depth_mm: float = 0.0
    stress_grade: str = ""
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class TimberBeamQuantities:
    total_beams_count: int = 0
    total_gross_linear_meters: float = 0.0
    total_equivalent_single_ply_meters: float = 0.0
    total_timber_volume_m3: float = 0.0
    lintels_linear_meters: float = 0.0
    ridge_beams_linear_meters: float = 0.0
    beams_by_type: Dict[str, int] = field(default_factory=dict)
    linear_meters_by_section: Dict[str, float] = field(default_factory=dict)


@dataclass
class TimberBeamExtractionResult:
    beams: List[TimberBeamSpec] = field(default_factory=list)
    quantities: TimberBeamQuantities = field(default_factory=TimberBeamQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceLVLGlulamTimberShadowAuthority:
    """Authoritative shadow evaluator for engineered timber beams and lintels."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses engineered timber beam schedule annotations.
        Example strings:
          - "2/300x45 LVL e14 OPENING LINTEL"
          - "GL17 GLULAM 360x65 ROOF RIDGE BEAM"
          - "hySPAN 240x45 LVL BEARER"
        """
        clean = text.upper()
        res = {
            "timber_type": EngineeredTimberType.LAMINATED_VENEER_LUMBER_LVL,
            "framing_role": TimberFramingRole.OPENING_LINTEL,
            "plies_count": 1,
            "ply_width_mm": 0.0,
            "depth_mm": 0.0,
            "stress_grade": "",
        }

        # Timber type & grade
        if "GLULAM" in clean or "GL1" in clean or "GL2" in clean:
            res["timber_type"] = EngineeredTimberType.GLUE_LAMINATED_TIMBER_GLULAM
            grade_m = re.search(r'\b(GL\d{2}[A-Z]?)\b', clean)
            if grade_m:
                res["stress_grade"] = grade_m.group(1)
            else:
                res["stress_grade"] = "GL17"
        elif "CLT" in clean:
            res["timber_type"] = EngineeredTimberType.CROSS_LAMINATED_TIMBER_BEAM_CLT
            res["stress_grade"] = "CLT"
        elif "F17" in clean or "F7" in clean or "MGP" in clean:
            res["timber_type"] = EngineeredTimberType.SOLID_SAWN_F_GRADE
            s_grade = re.search(r'\b(F\d{1,2}|MGP\d{2})\b', clean)
            if s_grade:
                res["stress_grade"] = s_grade.group(1)
        else:
            res["timber_type"] = EngineeredTimberType.LAMINATED_VENEER_LUMBER_LVL
            e_grade = re.search(r'\b(E\d{2}|HYSPAN|SMARTLVL)\b', clean)
            if e_grade:
                res["stress_grade"] = e_grade.group(1)

        # Framing Role
        if "RIDGE" in clean:
            res["framing_role"] = TimberFramingRole.ROOF_RIDGE_BEAM
        elif "BEARER" in clean or "GIRDER" in clean or "FLOOR" in clean:
            res["framing_role"] = TimberFramingRole.FLOOR_BEARER_GIRDER
        elif "RAFTER" in clean or "PORTAL" in clean:
            res["framing_role"] = TimberFramingRole.PORTAL_RAFTER
        elif "VERANDAH" in clean or "BALCONY" in clean or "CANTILEVER" in clean:
            res["framing_role"] = TimberFramingRole.CANTILEVER_VERANDAH_BEAM
        else:
            res["framing_role"] = TimberFramingRole.OPENING_LINTEL

        # Multi-ply count and dimensions: 2/300x45 or 3/240x45 or 300x65
        ply_dim_match = re.search(r'(\d+)\s*/\s*(\d{2,4})\s*[xX*]\s*(\d{2,3})', clean)
        if ply_dim_match:
            try:
                res["plies_count"] = int(ply_dim_match.group(1))
                d1 = float(ply_dim_match.group(2))
                d2 = float(ply_dim_match.group(3))
                # Depth is larger dimension, width is smaller
                res["depth_mm"] = max(d1, d2)
                res["ply_width_mm"] = min(d1, d2)
            except ValueError:
                pass
        else:
            dim_match = re.search(r'(\d{2,4})\s*[xX*]\s*(\d{2,3})', clean)
            if dim_match:
                try:
                    d1 = float(dim_match.group(1))
                    d2 = float(dim_match.group(2))
                    res["depth_mm"] = max(d1, d2)
                    res["ply_width_mm"] = min(d1, d2)
                    res["plies_count"] = 1
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
        tot = 0.0
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            tot += math.hypot(x2 - x1, y2 - y1)
        return round(tot * scale_ratio, 4)

    @classmethod
    def evaluate_timber_framing(
        cls,
        raw_beams_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> TimberBeamExtractionResult:
        """
        Authoritative shadow extraction for engineered timber framing beams.
        """
        extracted_beams: List[TimberBeamSpec] = []
        tot_gross_m = 0.0
        tot_equiv_ply_m = 0.0
        tot_volume_m3 = 0.0
        lintel_m = 0.0
        ridge_m = 0.0

        by_type: Dict[str, int] = {}
        m_by_sec: Dict[str, float] = {}

        for item in raw_beams_data:
            beam_id = item.get("beam_id", f"TB_{len(extracted_beams)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ttype_val = item.get("timber_type", parsed["timber_type"])
            if isinstance(ttype_val, str):
                try:
                    ttype = EngineeredTimberType(ttype_val)
                except ValueError:
                    ttype = EngineeredTimberType.LAMINATED_VENEER_LUMBER_LVL
            else:
                ttype = ttype_val

            role_val = item.get("framing_role", parsed["framing_role"])
            if isinstance(role_val, str):
                try:
                    frole = TimberFramingRole(role_val)
                except ValueError:
                    frole = TimberFramingRole.OPENING_LINTEL
            else:
                frole = role_val

            plies = int(item.get("plies_count", parsed["plies_count"]))
            ply_w = float(item.get("ply_width_mm", parsed["ply_width_mm"]))
            depth = float(item.get("depth_mm", parsed["depth_mm"]))
            grade = item.get("stress_grade", parsed["stress_grade"])

            spec = TimberBeamSpec(
                beam_id=beam_id,
                timber_type=ttype,
                framing_role=frole,
                centerline_points=snapped_pts,
                plies_count=plies,
                ply_width_mm=ply_w,
                depth_mm=depth,
                stress_grade=grade,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_beams.append(spec)

            beam_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            equiv_ply_m = beam_len_m * plies
            # Volume = plies * (ply_w/1000) * (depth/1000) * length
            vol_m3 = plies * (ply_w / 1000.0) * (depth / 1000.0) * beam_len_m

            tot_gross_m += beam_len_m
            tot_equiv_ply_m += equiv_ply_m
            tot_volume_m3 += vol_m3

            if frole == TimberFramingRole.OPENING_LINTEL:
                lintel_m += beam_len_m
            elif frole == TimberFramingRole.ROOF_RIDGE_BEAM:
                ridge_m += beam_len_m

            t_key = ttype.value
            by_type[t_key] = by_type.get(t_key, 0) + 1

            sec_key = f"{plies}/{int(depth)}x{int(ply_w)}" if plies > 1 else f"{int(depth)}x{int(ply_w)}"
            m_by_sec[sec_key] = round(m_by_sec.get(sec_key, 0.0) + beam_len_m, 4)

        quantities = TimberBeamQuantities(
            total_beams_count=len(extracted_beams),
            total_gross_linear_meters=round(tot_gross_m, 4),
            total_equivalent_single_ply_meters=round(tot_equiv_ply_m, 4),
            total_timber_volume_m3=round(tot_volume_m3, 4),
            lintels_linear_meters=round(lintel_m, 4),
            ridge_beams_linear_meters=round(ridge_m, 4),
            beams_by_type=by_type,
            linear_meters_by_section=m_by_sec,
        )

        return TimberBeamExtractionResult(
            beams=extracted_beams,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceLVLGlulamTimberShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
