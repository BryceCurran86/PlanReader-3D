"""
pb_source_spider_fitting_glass_fin_shadow.py

Authoritative shadow-mode extraction and takeoff for point-supported architectural glass facades:
stainless steel spider fittings (1/2/3/4-arm), articulated rotule bolts, and structural glass fins.

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


class SpiderFittingType(str, Enum):
    FOUR_ARM = "FOUR_ARM"
    TWO_ARM_180 = "TWO_ARM_180"
    TWO_ARM_90 = "TWO_ARM_90"
    SINGLE_ARM = "SINGLE_ARM"
    THREE_ARM = "THREE_ARM"


class FinSupportType(str, Enum):
    GLASS_FIN = "GLASS_FIN"
    STEEL_COLUMN = "STEEL_COLUMN"
    TENSION_ROD_TRUSS = "TENSION_ROD_TRUSS"


ROTULE_COUNT_BY_TYPE: Dict[SpiderFittingType, int] = {
    SpiderFittingType.FOUR_ARM: 4,
    SpiderFittingType.TWO_ARM_180: 2,
    SpiderFittingType.TWO_ARM_90: 2,
    SpiderFittingType.SINGLE_ARM: 1,
    SpiderFittingType.THREE_ARM: 3,
}


@dataclass
class GlassFinSpec:
    fin_id: str
    center_point: Tuple[float, float] = (0.0, 0.0)
    height_m: float = 0.0
    depth_mm: float = 0.0
    thickness_mm: float = 0.0
    is_laminated: bool = False
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class SpiderFittingSpec:
    fitting_id: str
    fitting_type: SpiderFittingType = SpiderFittingType.FOUR_ARM
    center_point: Tuple[float, float] = (0.0, 0.0)
    rotule_dia_mm: float = 0.0
    support_type: FinSupportType = FinSupportType.GLASS_FIN
    associated_fin_id: str = ""
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class PointSupportedFacadeQuantities:
    total_spider_fittings_count: int = 0
    fittings_by_type: Dict[str, int] = field(default_factory=dict)
    total_rotule_bolts_count: int = 0
    total_glass_fins_count: int = 0
    total_fin_height_linear_meters: float = 0.0
    total_fin_area_m2: float = 0.0


@dataclass
class PointSupportedFacadeExtractionResult:
    fittings: List[SpiderFittingSpec] = field(default_factory=list)
    fins: List[GlassFinSpec] = field(default_factory=list)
    quantities: PointSupportedFacadeQuantities = field(default_factory=PointSupportedFacadeQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSpiderFittingGlassFinShadowAuthority:
    """Authoritative shadow evaluator for point-supported glass facades and fins."""

    @staticmethod
    def parse_spider_callout(text: str) -> Dict[str, any]:
        """
        Parses spider fitting callouts and annotations.
        Example strings:
          - "4-WAY SPIDER FITTING SS316 W/ M14 ROTULES"
          - "2-WAY 180 DEGREE SPIDER BRACKET"
          - "SINGLE ARM CORNER SPIDER GLASS FIN MOUNTED"
        """
        clean = text.upper()
        res = {
            "fitting_type": SpiderFittingType.FOUR_ARM,
            "rotule_dia_mm": 0.0,
            "support_type": FinSupportType.GLASS_FIN,
        }

        # Type detection
        if "4-WAY" in clean or "4-ARM" in clean or "FOUR" in clean or "4 WAY" in clean or "4 ARM" in clean:
            res["fitting_type"] = SpiderFittingType.FOUR_ARM
        elif "2-WAY 90" in clean or "90 DEG" in clean or "CORNER 2-WAY" in clean:
            res["fitting_type"] = SpiderFittingType.TWO_ARM_90
        elif "2-WAY" in clean or "2-ARM" in clean or "TWO" in clean or "2 WAY" in clean or "2 ARM" in clean:
            res["fitting_type"] = SpiderFittingType.TWO_ARM_180
        elif "3-WAY" in clean or "3-ARM" in clean or "THREE" in clean or "3 WAY" in clean or "3 ARM" in clean:
            res["fitting_type"] = SpiderFittingType.THREE_ARM
        elif "1-WAY" in clean or "1-ARM" in clean or "SINGLE" in clean or "1 WAY" in clean or "1 ARM" in clean:
            res["fitting_type"] = SpiderFittingType.SINGLE_ARM

        # Rotule diameter: M14, M16, 14mm, 16mm
        rot_match = re.search(r'\b(?:M|ROTULE\s*)(\d{2})\b', clean)
        if not rot_match:
            rot_match = re.search(r'(\d{2})\s*MM\s*ROTULE', clean)
        if rot_match:
            try:
                rd = float(rot_match.group(1))
                if 10.0 <= rd <= 30.0:
                    res["rotule_dia_mm"] = rd
            except ValueError:
                pass

        # Support type
        if "STEEL" in clean or "COLUMN" in clean or "CHS" in clean or "SHS" in clean:
            res["support_type"] = FinSupportType.STEEL_COLUMN
        elif "TRUSS" in clean or "TENSION" in clean or "ROD" in clean:
            res["support_type"] = FinSupportType.TENSION_ROD_TRUSS
        else:
            res["support_type"] = FinSupportType.GLASS_FIN

        return res

    @staticmethod
    def parse_fin_callout(text: str) -> Dict[str, any]:
        """
        Parses glass fin callouts.
        Example strings:
          - "19mm TOUGHENED GLASS FIN 300mm DEEP H=4.5m"
          - "21.52mm LAMINATED STRUCTURAL GLASS FIN 400MM DEEP"
        """
        clean = text.upper()
        res = {
            "thickness_mm": 0.0,
            "depth_mm": 0.0,
            "height_m": 0.0,
            "is_laminated": False,
        }

        # Lamination
        if "LAMINATED" in clean or "SGP" in clean or "PVB" in clean:
            res["is_laminated"] = True

        # Thickness: 19mm, 21.52mm, 25mm, 15mm
        thk_match = re.search(r'(\d+(?:\.\d+)?)\s*MM\s*(?:TOUGHENED|LAMINATED|GLASS|THICK)?', clean)
        if thk_match:
            try:
                thk = float(thk_match.group(1))
                if 10.0 <= thk <= 50.0:
                    res["thickness_mm"] = thk
            except ValueError:
                pass

        # Depth: 300mm DEEP, 400MM DEPTH, D=300
        depth_match = re.search(r'(\d{3,4})\s*MM\s*(?:DEEP|DEPTH|WIDE)', clean)
        if not depth_match:
            depth_match = re.search(r'(?:DEEP|DEPTH|D\s*[=:]?)\s*(\d{3,4})\s*MM?', clean)
        if depth_match:
            try:
                d = float(depth_match.group(1))
                if 150.0 <= d <= 1200.0:
                    res["depth_mm"] = d
            except ValueError:
                pass

        # Height: H=4.5m, 4.5M HIGH, HEIGHT 4.0M
        h_match = re.search(r'(?:H\s*[=:]?\s*|HEIGHT\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*M\b', clean)
        if not h_match:
            h_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b\s*(?:HIGH|HEIGHT)', clean)
        if h_match:
            try:
                h = float(h_match.group(1))
                if 1.0 <= h <= 30.0:
                    res["height_m"] = h
            except ValueError:
                pass

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @classmethod
    def evaluate_facade(
        cls,
        fittings_data: List[Dict[str, any]],
        fins_data: Optional[List[Dict[str, any]]] = None,
        default_level: str = "L01"
    ) -> PointSupportedFacadeExtractionResult:
        """
        Authoritative shadow extraction for point-supported facade fittings and glass fins.
        """
        if fins_data is None:
            fins_data = []

        extracted_fittings: List[SpiderFittingSpec] = []
        extracted_fins: List[GlassFinSpec] = []

        fittings_by_t: Dict[str, int] = {}
        total_rotules = 0

        for item in fittings_data:
            fid = item.get("fitting_id", f"SP_{len(extracted_fittings)+1:03d}")
            raw_pt = item.get("center_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_spider_callout(callout)

            ftype_val = item.get("fitting_type", parsed["fitting_type"])
            if isinstance(ftype_val, str):
                try:
                    ftype = SpiderFittingType(ftype_val)
                except ValueError:
                    ftype = SpiderFittingType.FOUR_ARM
            else:
                ftype = ftype_val

            stype_val = item.get("support_type", parsed["support_type"])
            if isinstance(stype_val, str):
                try:
                    stype = FinSupportType(stype_val)
                except ValueError:
                    stype = FinSupportType.GLASS_FIN
            else:
                stype = stype_val

            rot_dia = float(item.get("rotule_dia_mm", parsed["rotule_dia_mm"]))
            fin_id = item.get("associated_fin_id", "")

            spec = SpiderFittingSpec(
                fitting_id=fid,
                fitting_type=ftype,
                center_point=snapped_pt,
                rotule_dia_mm=rot_dia,
                support_type=stype,
                associated_fin_id=fin_id,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_fittings.append(spec)

            t_key = ftype.value
            fittings_by_t[t_key] = fittings_by_t.get(t_key, 0) + 1
            total_rotules += ROTULE_COUNT_BY_TYPE.get(ftype, 4)

        total_fin_height_m = 0.0
        total_fin_area = 0.0

        for fin_item in fins_data:
            fin_id = fin_item.get("fin_id", f"FIN_{len(extracted_fins)+1:03d}")
            raw_center = fin_item.get("center_point", (0.0, 0.0))
            snapped_center = cls.snap_point(raw_center)

            fin_callout = fin_item.get("callout", "")
            parsed_fin = cls.parse_fin_callout(fin_callout)

            thk = float(fin_item.get("thickness_mm", parsed_fin["thickness_mm"]))
            depth = float(fin_item.get("depth_mm", parsed_fin["depth_mm"]))
            height = float(fin_item.get("height_m", parsed_fin["height_m"]))
            is_lam = bool(fin_item.get("is_laminated", parsed_fin["is_laminated"]))

            fin_spec = GlassFinSpec(
                fin_id=fin_id,
                center_point=snapped_center,
                height_m=height,
                depth_mm=depth,
                thickness_mm=thk,
                is_laminated=is_lam,
                level_id=fin_item.get("level_id", default_level),
                source_callout=fin_callout,
            )
            extracted_fins.append(fin_spec)

            total_fin_height_m += height
            area_m2 = height * (depth / 1000.0)
            total_fin_area += area_m2

        quantities = PointSupportedFacadeQuantities(
            total_spider_fittings_count=len(extracted_fittings),
            fittings_by_type=fittings_by_t,
            total_rotule_bolts_count=total_rotules,
            total_glass_fins_count=len(extracted_fins),
            total_fin_height_linear_meters=round(total_fin_height_m, 4),
            total_fin_area_m2=round(total_fin_area, 4),
        )

        return PointSupportedFacadeExtractionResult(
            fittings=extracted_fittings,
            fins=extracted_fins,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceSpiderFittingGlassFinShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
