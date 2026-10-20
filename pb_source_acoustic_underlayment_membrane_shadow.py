"""
pb_source_acoustic_underlayment_membrane_shadow.py

Authoritative shadow-mode extraction and takeoff for acoustic underlayments,
resilient isolation membranes, and perimeter flanking strips.

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


class AcousticUnderlaymentType(str, Enum):
    RECYCLED_RUBBER_CRUMB = "RECYCLED_RUBBER_CRUMB"
    CROSSLINKED_PE_FOAM = "CROSSLINKED_PE_FOAM"
    CORK_ELASTOMER_COMPOSITE = "CORK_ELASTOMER_COMPOSITE"
    RESILIENT_CRADLE_BATTEN = "RESILIENT_CRADLE_BATTEN"
    UNCOUPLING_ACOUSTIC_MAT = "UNCOUPLING_ACOUSTIC_MAT"


@dataclass
class AcousticUnderlaymentSpec:
    region_id: str
    underlayment_type: AcousticUnderlaymentType = AcousticUnderlaymentType.RECYCLED_RUBBER_CRUMB
    boundary_polygon: List[Tuple[float, float]] = field(default_factory=list)
    thickness_mm: float = 5.0
    impact_rating_iic: Optional[int] = 55
    flanking_strip_required: bool = True
    flanking_strip_height_mm: float = 100.0
    waste_allowance_percent: float = 8.0
    level_id: str = "L02"
    source_callout: str = ""


@dataclass
class AcousticUnderlaymentQuantities:
    total_regions_count: int = 0
    total_net_area_m2: float = 0.0
    total_gross_area_m2: float = 0.0
    total_perimeter_flanking_meters: float = 0.0
    area_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class AcousticUnderlaymentExtractionResult:
    regions: List[AcousticUnderlaymentSpec] = field(default_factory=list)
    quantities: AcousticUnderlaymentQuantities = field(default_factory=AcousticUnderlaymentQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceAcousticUnderlaymentMembraneShadowAuthority:
    """Authoritative shadow evaluator for acoustic floor underlayments and isolation strips."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses acoustic underlayment schedule callouts.
        Example strings:
          - "5mm RECYCLED RUBBER CRUMB ACOUSTIC UNDERLAYMENT W/ 100mm PERIMETER FLANKING STRIP IIC=62"
          - "8mm CROSSLINKED PE FOAM MEMBRANE W/ VAPOUR BARRIER"
          - "3mm CORK ELASTOMER COMPOSITE UNDERLAY IIC=58"
          - "RESILIENT ACOUSTIC CRADLE AND BATTEN SYSTEM"
          - "UNCOUPLING ACOUSTIC WATERPROOF MATTING"
        """
        clean = text.upper()
        res = {
            "underlayment_type": AcousticUnderlaymentType.RECYCLED_RUBBER_CRUMB,
            "thickness_mm": 5.0,
            "impact_rating_iic": 55,
            "flanking_strip_required": True,
            "flanking_strip_height_mm": 100.0,
        }

        # Typology
        if "CORK" in clean or "ELASTOMER" in clean:
            res["underlayment_type"] = AcousticUnderlaymentType.CORK_ELASTOMER_COMPOSITE
            res["thickness_mm"] = 3.0
        elif "PE FOAM" in clean or "CROSSLINKED" in clean or "IXPE" in clean:
            res["underlayment_type"] = AcousticUnderlaymentType.CROSSLINKED_PE_FOAM
            res["thickness_mm"] = 5.0
        elif "CRADLE" in clean or "BATTEN" in clean:
            res["underlayment_type"] = AcousticUnderlaymentType.RESILIENT_CRADLE_BATTEN
            res["thickness_mm"] = 45.0
        elif "UNCOUPLING" in clean or "DECOUPLING" in clean:
            res["underlayment_type"] = AcousticUnderlaymentType.UNCOUPLING_ACOUSTIC_MAT
            res["thickness_mm"] = 4.0
        else:
            res["underlayment_type"] = AcousticUnderlaymentType.RECYCLED_RUBBER_CRUMB
            res["thickness_mm"] = 5.0

        # Thickness: 3mm, 5mm, 8mm, 10mm, 45mm THK
        thk_match = re.search(r'(\d+(?:\.\d+)?)\s*MM\s*(?:THICK|THK|DEPTH)?', clean)
        if thk_match:
            try:
                t = float(thk_match.group(1))
                if 1.0 <= t <= 100.0:
                    res["thickness_mm"] = t
            except ValueError:
                pass

        # Impact Rating IIC: IIC=62, IIC 58
        iic_match = re.search(r'IIC\s*[:=]?\s*(\d{2,3})', clean)
        if iic_match:
            try:
                res["impact_rating_iic"] = int(iic_match.group(1))
            except ValueError:
                pass

        # Flanking strip: 100mm PERIMETER FLANKING, NO FLANKING
        if "NO FLANKING" in clean:
            res["flanking_strip_required"] = False
        else:
            res["flanking_strip_required"] = True
            flank_match = re.search(r'(\d{2,3})\s*MM\s*(?:PERIMETER\s*)?FLANKING', clean)
            if flank_match:
                try:
                    res["flanking_strip_height_mm"] = float(flank_match.group(1))
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
    def calculate_polygon_area_and_perimeter(
        poly: List[Tuple[float, float]],
        scale_ratio: float = 0.001
    ) -> Tuple[float, float]:
        if len(poly) < 3:
            return 0.0, 0.0
        n = len(poly)
        area = 0.0
        perim = 0.0
        for i in range(n):
            j = (i + 1) % n
            xi, yi = poly[i]
            xj, yj = poly[j]
            area += (xi * yj) - (xj * yi)
            edge_len = math.hypot(xj - xi, yj - yi) * scale_ratio
            perim += edge_len
        area_m2 = abs(area) * 0.5 * (scale_ratio ** 2)
        return round(area_m2, 4), round(perim, 4)

    @classmethod
    def evaluate_underlayments(
        cls,
        raw_regions_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L02"
    ) -> AcousticUnderlaymentExtractionResult:
        """
        Authoritative shadow extraction for acoustic floor underlayments and isolation strips.
        """
        extracted_regions: List[AcousticUnderlaymentSpec] = []
        tot_net_m2 = 0.0
        tot_gross_m2 = 0.0
        tot_flanking_m = 0.0

        area_by_type_dict: Dict[str, float] = {}

        for item in raw_regions_data:
            reg_id = item.get("region_id", f"AC_{len(extracted_regions)+1:03d}")
            raw_poly = item.get("boundary_polygon", [])
            snapped_poly = [cls.snap_point(pt) for pt in raw_poly]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            utype_val = item.get("underlayment_type", parsed["underlayment_type"])
            if isinstance(utype_val, str):
                try:
                    utype = AcousticUnderlaymentType(utype_val)
                except ValueError:
                    utype = AcousticUnderlaymentType.RECYCLED_RUBBER_CRUMB
            else:
                utype = utype_val

            thk_mm = float(item.get("thickness_mm", parsed["thickness_mm"]))
            iic = item.get("impact_rating_iic", parsed["impact_rating_iic"])
            flank_req = item.get("flanking_strip_required", parsed["flanking_strip_required"])
            flank_h_mm = float(item.get("flanking_strip_height_mm", parsed["flanking_strip_height_mm"]))
            waste_pct = float(item.get("waste_allowance_percent", 8.0))

            net_area, perim_m = cls.calculate_polygon_area_and_perimeter(snapped_poly, scale_ratio)
            gross_area = round(net_area * (1.0 + waste_pct / 100.0), 4)

            flanking_m = perim_m if flank_req else 0.0

            spec = AcousticUnderlaymentSpec(
                region_id=reg_id,
                underlayment_type=utype,
                boundary_polygon=snapped_poly,
                thickness_mm=thk_mm,
                impact_rating_iic=iic,
                flanking_strip_required=flank_req,
                flanking_strip_height_mm=flank_h_mm,
                waste_allowance_percent=waste_pct,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_regions.append(spec)

            tot_net_m2 += net_area
            tot_gross_m2 += gross_area
            tot_flanking_m += flanking_m

            t_key = utype.value
            area_by_type_dict[t_key] = round(area_by_type_dict.get(t_key, 0.0) + net_area, 4)

        quantities = AcousticUnderlaymentQuantities(
            total_regions_count=len(extracted_regions),
            total_net_area_m2=round(tot_net_m2, 4),
            total_gross_area_m2=round(tot_gross_m2, 4),
            total_perimeter_flanking_meters=round(tot_flanking_m, 4),
            area_by_type=area_by_type_dict,
        )

        return AcousticUnderlaymentExtractionResult(
            regions=extracted_regions,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceAcousticUnderlaymentMembraneShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
