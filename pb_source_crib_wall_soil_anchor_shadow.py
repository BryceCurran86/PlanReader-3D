"""
pb_source_crib_wall_soil_anchor_shadow.py

Authoritative shadow-mode extraction and civil takeoff for precast concrete crib retaining walls,
granular rockfill aggregate volume, modular header/stretcher units, and subsoil AG drainage.

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


class RetainingWallType(str, Enum):
    PRECAST_CONCRETE_CRIB_WALL = "PRECAST_CONCRETE_CRIB_WALL"
    TIMBER_CRIB_WALL = "TIMBER_CRIB_WALL"
    REINFORCED_SOIL_NAIL_WALL = "REINFORCED_SOIL_NAIL_WALL"
    SOLDIER_PILE_PANEL_WALL = "SOLDIER_PILE_PANEL_WALL"


class SoilAnchorType(str, Enum):
    SELF_DRILLING_GROUTED_ANCHOR = "SELF_DRILLING_GROUTED_ANCHOR"
    DRIVEN_HELICAL_TIEBACK = "DRIVEN_HELICAL_TIEBACK"
    NO_ANCHORS = "NO_ANCHORS"


@dataclass
class RetainingWallRunSpec:
    wall_id: str
    wall_type: RetainingWallType = RetainingWallType.PRECAST_CONCRETE_CRIB_WALL
    anchor_type: SoilAnchorType = SoilAnchorType.NO_ANCHORS
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    wall_height_m: float = 3.0
    cell_depth_m: float = 1.8
    batter_ratio: str = "1:4"
    ag_drain_included: bool = True
    soil_anchors_count: int = 0
    level_id: str = "SITE"
    source_callout: str = ""


@dataclass
class RetainingWallQuantities:
    total_walls_count: int = 0
    total_wall_length_meters: float = 0.0
    total_face_area_m2: float = 0.0
    total_rockfill_volume_m3: float = 0.0
    total_precast_units_count: int = 0
    total_ag_drain_meters: float = 0.0
    total_soil_anchors_count: int = 0
    length_by_type: Dict[str, float] = field(default_factory=dict)
    rockfill_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class RetainingWallExtractionResult:
    runs: List[RetainingWallRunSpec] = field(default_factory=list)
    quantities: RetainingWallQuantities = field(default_factory=RetainingWallQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceCribWallSoilAnchorShadowAuthority:
    """Authoritative shadow evaluator for precast crib retaining walls and soil anchors."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses civil retaining crib wall schedule callouts.
        Example strings:
          - "3.0m HIGH PRECAST CONCRETE CRIB RETAINING WALL 1:4 BATTER 1.8m HEADER DEPTH W/ CRUSHED ROCKFILL & DN100 AG DRAIN"
          - "2.5m TIMBER CRIB WALL 1.2m DEPTH"
          - "4.0m REINFORCED SOIL NAIL WALL W/ 10x SOIL ANCHORS"
          - "SOLDIER PILE WALL 3.5m HIGH"
        """
        clean = text.upper()
        res = {
            "wall_type": RetainingWallType.PRECAST_CONCRETE_CRIB_WALL,
            "anchor_type": SoilAnchorType.NO_ANCHORS,
            "wall_height_m": 3.0,
            "cell_depth_m": 1.8,
            "batter_ratio": "1:4",
            "ag_drain_included": True,
            "soil_anchors_count": 0,
        }

        # Typology
        if "TIMBER" in clean:
            res["wall_type"] = RetainingWallType.TIMBER_CRIB_WALL
            res["cell_depth_m"] = 1.2
        elif "SOIL NAIL" in clean or "NAILED" in clean:
            res["wall_type"] = RetainingWallType.REINFORCED_SOIL_NAIL_WALL
            res["anchor_type"] = SoilAnchorType.SELF_DRILLING_GROUTED_ANCHOR
            res["cell_depth_m"] = 0.3
        elif "SOLDIER PILE" in clean:
            res["wall_type"] = RetainingWallType.SOLDIER_PILE_PANEL_WALL
            res["cell_depth_m"] = 0.25
        else:
            res["wall_type"] = RetainingWallType.PRECAST_CONCRETE_CRIB_WALL

        # Anchors
        if "HELICAL" in clean or "TIEBACK" in clean:
            res["anchor_type"] = SoilAnchorType.DRIVEN_HELICAL_TIEBACK
        elif "SOIL ANCHOR" in clean or "GROUTED ANCHOR" in clean:
            res["anchor_type"] = SoilAnchorType.SELF_DRILLING_GROUTED_ANCHOR

        # Wall height: 3.0m, 2.5m, 4.0m HIGH
        h_match = re.search(r'(\d+(?:\.\d+)?)\s*M\s*(?:HIGH|H\b)?', clean)
        if h_match:
            try:
                h = float(h_match.group(1))
                if 0.5 <= h <= 15.0:
                    res["wall_height_m"] = h
            except ValueError:
                pass

        # Cell / header depth: 1.8m HEADER, 1.2m DEPTH, 2.4m CELL
        d_match = re.search(r'(\d+(?:\.\d+)?)\s*M\s*(?:HEADER|DEPTH|CELL)', clean)
        if d_match:
            try:
                d = float(d_match.group(1))
                if 0.2 <= d <= 5.0:
                    res["cell_depth_m"] = d
            except ValueError:
                pass

        # Batter ratio: 1:4, 1:6, 1:8
        bat_match = re.search(r'1\s*:\s*(\d)', clean)
        if bat_match:
            res["batter_ratio"] = f"1:{bat_match.group(1)}"

        # AG drain: AG DRAIN, AG PIPE, NO AG DRAIN
        if "NO AG" in clean or "WITHOUT AG" in clean:
            res["ag_drain_included"] = False
        else:
            res["ag_drain_included"] = True

        # Soil anchors count: 10x SOIL ANCHORS, 6 ANCHORS
        anc_match = re.search(r'(\d+)\s*[xX]?\s*(?:SOIL\s*)?ANCHOR', clean)
        if anc_match:
            try:
                res["soil_anchors_count"] = int(anc_match.group(1))
                if res["anchor_type"] == SoilAnchorType.NO_ANCHORS:
                    res["anchor_type"] = SoilAnchorType.SELF_DRILLING_GROUTED_ANCHOR
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
    def evaluate_walls(
        cls,
        raw_walls_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "SITE"
    ) -> RetainingWallExtractionResult:
        """
        Authoritative shadow extraction for crib retaining walls and soil anchors.
        """
        extracted_walls: List[RetainingWallRunSpec] = []
        tot_length_m = 0.0
        tot_face_m2 = 0.0
        tot_rock_m3 = 0.0
        tot_units = 0
        tot_ag_m = 0.0
        tot_anchors = 0

        len_by_type: Dict[str, float] = {}
        rock_by_type: Dict[str, float] = {}

        for item in raw_walls_data:
            wall_id = item.get("wall_id", f"RW_{len(extracted_walls)+1:02d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            wtype_val = item.get("wall_type", parsed["wall_type"])
            if isinstance(wtype_val, str):
                try:
                    wtype = RetainingWallType(wtype_val)
                except ValueError:
                    wtype = RetainingWallType.PRECAST_CONCRETE_CRIB_WALL
            else:
                wtype = wtype_val

            atype_val = item.get("anchor_type", parsed["anchor_type"])
            if isinstance(atype_val, str):
                try:
                    atype = SoilAnchorType(atype_val)
                except ValueError:
                    atype = SoilAnchorType.NO_ANCHORS
            else:
                atype = atype_val

            h_m = float(item.get("wall_height_m", parsed["wall_height_m"]))
            d_cell_m = float(item.get("cell_depth_m", parsed["cell_depth_m"]))
            bat = item.get("batter_ratio", parsed["batter_ratio"])
            ag_inc = bool(item.get("ag_drain_included", parsed["ag_drain_included"]))
            anc_cnt = int(item.get("soil_anchors_count", parsed["soil_anchors_count"]))

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            face_m2 = round(run_len_m * h_m, 4)
            rock_vol_m3 = round(run_len_m * h_m * d_cell_m, 4)

            # Precast units: ~3.3 modular headers/stretchers per m2 face elevation
            if wtype in (RetainingWallType.PRECAST_CONCRETE_CRIB_WALL, RetainingWallType.TIMBER_CRIB_WALL):
                units_cnt = int(math.ceil(face_m2 * 3.333))
            else:
                units_cnt = 0

            ag_len_m = run_len_m if ag_inc else 0.0

            spec = RetainingWallRunSpec(
                wall_id=wall_id,
                wall_type=wtype,
                anchor_type=atype,
                centerline_points=snapped_pts,
                wall_height_m=h_m,
                cell_depth_m=d_cell_m,
                batter_ratio=bat,
                ag_drain_included=ag_inc,
                soil_anchors_count=anc_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_walls.append(spec)

            tot_length_m += run_len_m
            tot_face_m2 += face_m2
            tot_rock_m3 += rock_vol_m3
            tot_units += units_cnt
            tot_ag_m += ag_len_m
            tot_anchors += anc_cnt

            t_key = wtype.value
            len_by_type[t_key] = round(len_by_type.get(t_key, 0.0) + run_len_m, 4)
            rock_by_type[t_key] = round(rock_by_type.get(t_key, 0.0) + rock_vol_m3, 4)

        quantities = RetainingWallQuantities(
            total_walls_count=len(extracted_walls),
            total_wall_length_meters=round(tot_length_m, 4),
            total_face_area_m2=round(tot_face_m2, 4),
            total_rockfill_volume_m3=round(tot_rock_m3, 4),
            total_precast_units_count=tot_units,
            total_ag_drain_meters=round(tot_ag_m, 4),
            total_soil_anchors_count=tot_anchors,
            length_by_type=len_by_type,
            rockfill_by_type=rock_by_type,
        )

        return RetainingWallExtractionResult(
            runs=extracted_walls,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceCribWallSoilAnchorShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
