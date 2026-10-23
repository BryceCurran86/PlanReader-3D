"""
pb_source_acoustic_baffle_cloud_shadow.py

Authoritative shadow-mode extraction and architectural takeoff for suspended vertical acoustic baffles,
horizontal ceiling clouds/rafts, effective absorption face areas, and suspension wire drops.

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


class AcousticCeilingType(str, Enum):
    VERTICAL_SUSPENDED_BAFFLE = "VERTICAL_SUSPENDED_BAFFLE"
    HORIZONTAL_RAFT_CLOUD = "HORIZONTAL_RAFT_CLOUD"
    TIMBER_SLATTED_BAFFLE = "TIMBER_SLATTED_BAFFLE"
    DIRECT_FIX_ACOUSTIC_TILE = "DIRECT_FIX_ACOUSTIC_TILE"


@dataclass
class AcousticCeilingItemSpec:
    item_id: str
    ceiling_type: AcousticCeilingType = AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    baffle_width_mm: float = 50.0
    baffle_depth_mm: float = 200.0
    spacing_cts_mm: float = 300.0
    nrc_rating: float = 0.85
    suspension_drops_count: int = 2
    level_id: str = "L01"
    room_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class AcousticCeilingQuantities:
    total_items_count: int = 0
    total_linear_meters: float = 0.0
    total_effective_absorption_m2: float = 0.0
    total_suspension_drops_count: int = 0
    linear_by_type: Dict[str, float] = field(default_factory=dict)
    absorption_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class AcousticCeilingExtractionResult:
    items: List[AcousticCeilingItemSpec] = field(default_factory=list)
    quantities: AcousticCeilingQuantities = field(default_factory=AcousticCeilingQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceAcousticBaffleCloudShadowAuthority:
    """Authoritative shadow evaluator for architectural acoustic ceiling baffles and clouds."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses acoustic ceiling baffle schedule callouts.
        Example strings:
          - "50x200mm VERTICAL PET ACOUSTIC BAFFLE AT 300mm CTS NRC=0.85 W/ AIRCRAFT WIRE SUSPENSION"
          - "2400x1200 HORIZONTAL ACOUSTIC CLOUD RAFT NRC=0.90"
          - "30x100mm TIMBER SLATTED ACOUSTIC BAFFLE AT 150mm CTS"
          - "HEXAGONAL DIRECT FIX ACOUSTIC TILE NRC=0.75"
        """
        clean = text.upper()
        res = {
            "ceiling_type": AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE,
            "baffle_width_mm": 50.0,
            "baffle_depth_mm": 200.0,
            "spacing_cts_mm": 300.0,
            "nrc_rating": 0.85,
        }

        # Typology
        if "CLOUD" in clean or "HORIZONTAL" in clean or re.search(r'\bRAFTS?\b', clean):
            res["ceiling_type"] = AcousticCeilingType.HORIZONTAL_RAFT_CLOUD
            res["baffle_width_mm"] = 1200.0
            res["baffle_depth_mm"] = 50.0
            res["nrc_rating"] = 0.90
        elif "TIMBER" in clean or "SLAT" in clean:
            res["ceiling_type"] = AcousticCeilingType.TIMBER_SLATTED_BAFFLE
            res["baffle_width_mm"] = 30.0
            res["baffle_depth_mm"] = 100.0
            res["spacing_cts_mm"] = 150.0
        elif "DIRECT FIX" in clean or "TILE" in clean:
            res["ceiling_type"] = AcousticCeilingType.DIRECT_FIX_ACOUSTIC_TILE
            res["nrc_rating"] = 0.75
        else:
            res["ceiling_type"] = AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE

        # Dimensions: 50x200, 2400x1200, 30x100
        dim_match = re.search(r'(\d{2,4})\s*[xX*]\s*(\d{2,4})', clean)
        if dim_match:
            try:
                v1 = float(dim_match.group(1))
                v2 = float(dim_match.group(2))
                if res["ceiling_type"] == AcousticCeilingType.HORIZONTAL_RAFT_CLOUD:
                    res["baffle_width_mm"] = min(v1, v2)
                    res["baffle_depth_mm"] = 50.0
                else:
                    res["baffle_width_mm"] = min(v1, v2)
                    res["baffle_depth_mm"] = max(v1, v2)
            except ValueError:
                pass

        # Spacing: AT 300mm CTS, 150mm SPACING, 300mm CTS
        spc_match = re.search(r'(?:AT\s+(\d{2,3})\s*MM(?:\s*(?:CTS|CENTRES|CENTERS|SPACING))?|(\d{2,3})\s*MM\s*(?:CTS|CENTRES|CENTERS|SPACING))', clean)
        if spc_match:
            try:
                val = spc_match.group(1) or spc_match.group(2)
                s = float(val)
                if 50.0 <= s <= 1000.0:
                    res["spacing_cts_mm"] = s
            except ValueError:
                pass

        # NRC rating: NRC=0.85, NRC 0.90
        nrc_match = re.search(r'NRC\s*[:=]?\s*(0\.\d{2})', clean)
        if nrc_match:
            try:
                res["nrc_rating"] = float(nrc_match.group(1))
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
    def evaluate_ceilings(
        cls,
        raw_items_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> AcousticCeilingExtractionResult:
        """
        Authoritative shadow extraction for acoustic baffles and clouds.
        """
        extracted_items: List[AcousticCeilingItemSpec] = []
        tot_linear_m = 0.0
        tot_absorption_m2 = 0.0
        tot_drops = 0

        linear_by_type: Dict[str, float] = {}
        abs_by_type: Dict[str, float] = {}

        for item in raw_items_data:
            item_id = item.get("item_id", f"AB_{len(extracted_items)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ctype_val = item.get("ceiling_type", parsed["ceiling_type"])
            if isinstance(ctype_val, str):
                try:
                    ctype = AcousticCeilingType(ctype_val)
                except ValueError:
                    ctype = AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE
            else:
                ctype = ctype_val

            w_mm = float(item.get("baffle_width_mm", parsed["baffle_width_mm"]))
            d_mm = float(item.get("baffle_depth_mm", parsed["baffle_depth_mm"]))
            spc_mm = float(item.get("spacing_cts_mm", parsed["spacing_cts_mm"]))
            nrc = float(item.get("nrc_rating", parsed["nrc_rating"]))

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            if ctype in (AcousticCeilingType.VERTICAL_SUSPENDED_BAFFLE, AcousticCeilingType.TIMBER_SLATTED_BAFFLE):
                # Double-sided absorption: 2 sides * depth * length
                abs_m2 = round(2.0 * (d_mm / 1000.0) * run_len_m, 4)
                drops_cnt = max(2, 2 * int(math.ceil(run_len_m / 1.5)))
            elif ctype == AcousticCeilingType.HORIZONTAL_RAFT_CLOUD:
                # Top and bottom absorption or bottom face: bottom face + edges
                abs_m2 = round((w_mm / 1000.0) * run_len_m, 4)
                drops_cnt = 4
            else:  # DIRECT_FIX_ACOUSTIC_TILE
                abs_m2 = round((w_mm / 1000.0) * run_len_m, 4)
                drops_cnt = 0

            spec = AcousticCeilingItemSpec(
                item_id=item_id,
                ceiling_type=ctype,
                centerline_points=snapped_pts,
                baffle_width_mm=w_mm,
                baffle_depth_mm=d_mm,
                spacing_cts_mm=spc_mm,
                nrc_rating=nrc,
                suspension_drops_count=drops_cnt,
                level_id=item.get("level_id", default_level),
                room_id=item.get("room_id"),
                source_callout=callout,
            )
            extracted_items.append(spec)

            tot_linear_m += run_len_m
            tot_absorption_m2 += abs_m2
            tot_drops += drops_cnt

            t_key = ctype.value
            linear_by_type[t_key] = round(linear_by_type.get(t_key, 0.0) + run_len_m, 4)
            abs_by_type[t_key] = round(abs_by_type.get(t_key, 0.0) + abs_m2, 4)

        quantities = AcousticCeilingQuantities(
            total_items_count=len(extracted_items),
            total_linear_meters=round(tot_linear_m, 4),
            total_effective_absorption_m2=round(tot_absorption_m2, 4),
            total_suspension_drops_count=tot_drops,
            linear_by_type=linear_by_type,
            absorption_by_type=abs_by_type,
        )

        return AcousticCeilingExtractionResult(
            items=extracted_items,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceAcousticBaffleCloudShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
