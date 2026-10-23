"""
pb_source_perimeter_fencing_mesh_shadow.py

Authoritative shadow-mode extraction and civil takeoff for perimeter security fencing,
anti-climb mesh, structural posts, and bored pier footings.

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


class SecurityFencingType(str, Enum):
    ANTI_CLIMB_358_WELDED_MESH = "ANTI_CLIMB_358_WELDED_MESH"
    CHAIN_LINK_FABRIC = "CHAIN_LINK_FABRIC"
    STEEL_PALISADE = "STEEL_PALISADE"
    EXPANDED_METAL_MESH = "EXPANDED_METAL_MESH"
    TUBULAR_PICKET = "TUBULAR_PICKET"


class FencingToppingType(str, Enum):
    BARBED_WIRE_3_STRANDS = "BARBED_WIRE_3_STRANDS"
    RAZOR_WIRE_CONCERTINA = "RAZOR_WIRE_CONCERTINA"
    NO_TOPPING = "NO_TOPPING"


@dataclass
class SecurityFenceRunSpec:
    run_id: str
    fencing_type: SecurityFencingType = SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    fence_height_m: float = 2.4
    post_spacing_m: float = 2.5
    post_section: str = "75x75 SHS"
    footing_diameter_mm: float = 300.0
    footing_depth_mm: float = 800.0
    topping_type: FencingToppingType = FencingToppingType.NO_TOPPING
    level_id: str = "SITE"
    source_callout: str = ""


@dataclass
class SecurityFencingQuantities:
    total_runs_count: int = 0
    total_fence_length_meters: float = 0.0
    total_mesh_area_m2: float = 0.0
    total_posts_count: int = 0
    total_footing_concrete_m3: float = 0.0
    length_by_type: Dict[str, float] = field(default_factory=dict)
    posts_by_section: Dict[str, int] = field(default_factory=dict)


@dataclass
class SecurityFencingExtractionResult:
    runs: List[SecurityFenceRunSpec] = field(default_factory=list)
    quantities: SecurityFencingQuantities = field(default_factory=SecurityFencingQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourcePerimeterFencingMeshShadowAuthority:
    """Authoritative shadow evaluator for site perimeter security fencing and posts."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses perimeter fencing schedule callouts.
        Example strings:
          - "2.4m HIGH 358 ANTI-CLIMB WELDED MESH FENCING ON 75x75 SHS POSTS AT 2.5m CTS W/ 3 STRANDS BARBED WIRE"
          - "2.1m CHAIN LINK FABRIC FENCE ON 65 NB POSTS AT 3.0m CTS"
          - "2.4m STEEL PALISADE SECURITY FENCE ON 100x100 SHS"
          - "1.8m TUBULAR PICKET BALUSTRADE"
        """
        clean = text.upper()
        res = {
            "fencing_type": SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH,
            "fence_height_m": 2.4,
            "post_spacing_m": 2.5,
            "post_section": "75x75 SHS",
            "footing_diameter_mm": 300.0,
            "footing_depth_mm": 800.0,
            "topping_type": FencingToppingType.NO_TOPPING,
        }

        # Typology
        if "358" in clean or "ANTI-CLIMB" in clean or "WELDED MESH" in clean:
            res["fencing_type"] = SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH
        elif "CHAIN LINK" in clean or "CHAINWIRE" in clean:
            res["fencing_type"] = SecurityFencingType.CHAIN_LINK_FABRIC
            res["post_section"] = "65 NB PIPE"
            res["fence_height_m"] = 2.1
            res["post_spacing_m"] = 3.0
        elif "PALISADE" in clean:
            res["fencing_type"] = SecurityFencingType.STEEL_PALISADE
            res["post_section"] = "100x100 SHS"
            res["post_spacing_m"] = 2.75
        elif "EXPANDED" in clean:
            res["fencing_type"] = SecurityFencingType.EXPANDED_METAL_MESH
        elif "PICKET" in clean or "TUBULAR" in clean:
            res["fencing_type"] = SecurityFencingType.TUBULAR_PICKET
            res["fence_height_m"] = 1.8
            res["post_section"] = "50x50 SHS"
        else:
            res["fencing_type"] = SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH

        # Height: 2.4m, 2.1m, 1.8m, 3.0m HIGH
        h_match = re.search(r'(\d+(?:\.\d+)?)\s*M\s*(?:HIGH|H)?', clean)
        if h_match:
            try:
                h = float(h_match.group(1))
                if 1.0 <= h <= 6.0:
                    res["fence_height_m"] = h
            except ValueError:
                pass

        # Post spacing: AT 2.5m CTS, 3.0m SPACING
        spc_match = re.search(r'(?:AT\s*)?(\d+(?:\.\d+)?)\s*M\s*(?:CTS|CENTRES|CENTERS|SPACING)', clean)
        if spc_match:
            try:
                s = float(spc_match.group(1))
                if 1.0 <= s <= 5.0:
                    res["post_spacing_m"] = s
            except ValueError:
                pass

        # Post section: 75x75 SHS, 100x100 SHS, 65 NB
        sec_match = re.search(r'(\d{2,3})[xX](\d{2,3})\s*(SHS|RHS)|(\d{2,3}\s*NB\s*(?:PIPE|CHS)?)', clean)
        if sec_match:
            if sec_match.group(1):
                res["post_section"] = f"{sec_match.group(1)}x{sec_match.group(2)} {sec_match.group(3)}"
            else:
                res["post_section"] = sec_match.group(4).strip()

        # Topping: BARBED WIRE, RAZOR WIRE
        if "RAZOR" in clean or "CONCERTINA" in clean:
            res["topping_type"] = FencingToppingType.RAZOR_WIRE_CONCERTINA
        elif "BARBED" in clean:
            res["topping_type"] = FencingToppingType.BARBED_WIRE_3_STRANDS
        else:
            res["topping_type"] = FencingToppingType.NO_TOPPING

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
    def evaluate_fencing_runs(
        cls,
        raw_runs_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "SITE"
    ) -> SecurityFencingExtractionResult:
        """
        Authoritative shadow extraction for perimeter fencing, posts, and footings.
        """
        extracted_runs: List[SecurityFenceRunSpec] = []
        tot_len_m = 0.0
        tot_mesh_m2 = 0.0
        tot_posts = 0
        tot_conc_m3 = 0.0

        len_by_type: Dict[str, float] = {}
        posts_by_sec: Dict[str, int] = {}

        for item in raw_runs_data:
            run_id = item.get("run_id", f"FN_{len(extracted_runs)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ftype_val = item.get("fencing_type", parsed["fencing_type"])
            if isinstance(ftype_val, str):
                try:
                    ftype = SecurityFencingType(ftype_val)
                except ValueError:
                    ftype = SecurityFencingType.ANTI_CLIMB_358_WELDED_MESH
            else:
                ftype = ftype_val

            h_m = float(item.get("fence_height_m", parsed["fence_height_m"]))
            s_m = float(item.get("post_spacing_m", parsed["post_spacing_m"]))
            p_sec = item.get("post_section", parsed["post_section"])
            f_dia_mm = float(item.get("footing_diameter_mm", parsed["footing_diameter_mm"]))
            f_dep_mm = float(item.get("footing_depth_mm", parsed["footing_depth_mm"]))

            top_val = item.get("topping_type", parsed["topping_type"])
            if isinstance(top_val, str):
                try:
                    top_type = FencingToppingType(top_val)
                except ValueError:
                    top_type = FencingToppingType.NO_TOPPING
            else:
                top_type = top_val

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            mesh_area_m2 = round(run_len_m * h_m, 4)

            # Post count: ceil(L / S) + 1
            if run_len_m > 0.0 and s_m > 0.0:
                posts_count = int(math.ceil(run_len_m / s_m)) + 1
            else:
                posts_count = 2

            # Footing concrete per post: pi * r^2 * h
            r_m = (f_dia_mm / 1000.0) / 2.0
            dep_m = f_dep_mm / 1000.0
            vol_per_post = math.pi * (r_m ** 2) * dep_m
            run_conc_m3 = round(posts_count * vol_per_post, 4)

            spec = SecurityFenceRunSpec(
                run_id=run_id,
                fencing_type=ftype,
                centerline_points=snapped_pts,
                fence_height_m=h_m,
                post_spacing_m=s_m,
                post_section=p_sec,
                footing_diameter_mm=f_dia_mm,
                footing_depth_mm=f_dep_mm,
                topping_type=top_type,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_runs.append(spec)

            tot_len_m += run_len_m
            tot_mesh_m2 += mesh_area_m2
            tot_posts += posts_count
            tot_conc_m3 += run_conc_m3

            t_key = ftype.value
            len_by_type[t_key] = round(len_by_type.get(t_key, 0.0) + run_len_m, 4)

            posts_by_sec[p_sec] = posts_by_sec.get(p_sec, 0) + posts_count

        quantities = SecurityFencingQuantities(
            total_runs_count=len(extracted_runs),
            total_fence_length_meters=round(tot_len_m, 4),
            total_mesh_area_m2=round(tot_mesh_m2, 4),
            total_posts_count=tot_posts,
            total_footing_concrete_m3=round(tot_conc_m3, 4),
            length_by_type=len_by_type,
            posts_by_section=posts_by_sec,
        )

        return SecurityFencingExtractionResult(
            runs=extracted_runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourcePerimeterFencingMeshShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
