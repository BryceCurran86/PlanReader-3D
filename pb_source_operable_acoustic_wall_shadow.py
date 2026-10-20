"""
pb_source_operable_acoustic_wall_shadow.py

Authoritative shadow-mode extraction and interior architectural takeoff for operable acoustic
folding walls, multi-directional overhead tracks, stacking parking pockets, and plenum sound baffles.

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


class OperableWallSystemType(str, Enum):
    INDIVIDUAL_OMNI_DIRECTIONAL_PANELS = "INDIVIDUAL_OMNI_DIRECTIONAL_PANELS"
    CENTER_HUNG_PAIRED_PANELS = "CENTER_HUNG_PAIRED_PANELS"
    CONTINUOUSLY_HINGED_TRAIN = "CONTINUOUSLY_HINGED_TRAIN"
    VERTICAL_LIFT_RETRACTABLE_WALL = "VERTICAL_LIFT_RETRACTABLE_WALL"


@dataclass
class OperableWallSpec:
    wall_id: str
    system_type: OperableWallSystemType = OperableWallSystemType.INDIVIDUAL_OMNI_DIRECTIONAL_PANELS
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    wall_height_m: float = 0.0
    panel_width_mm: float = 0.0
    acoustic_rating_rw_db: int = 0
    has_retractable_seals: bool = False
    parking_stack_track_length_m: float = 2.5
    has_plenum_baffle: bool = True
    plenum_height_m: float = 0.9
    pass_doors_count: int = 0
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class OperableWallQuantities:
    total_walls_count: int = 0
    total_wall_linear_meters: float = 0.0
    total_wall_area_m2: float = 0.0
    total_overhead_track_meters: float = 0.0
    total_panels_count: int = 0
    total_plenum_baffle_area_m2: float = 0.0
    total_pass_doors_count: int = 0
    linear_meters_by_system: Dict[str, float] = field(default_factory=dict)
    linear_meters_by_rw: Dict[str, float] = field(default_factory=dict)


@dataclass
class OperableWallExtractionResult:
    walls: List[OperableWallSpec] = field(default_factory=list)
    quantities: OperableWallQuantities = field(default_factory=OperableWallQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceOperableAcousticWallShadowAuthority:
    """Authoritative shadow evaluator for operable acoustic walls, tracks, and plenum baffles."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses operable movable wall schedule annotations.
        Example strings:
          - "OPERABLE ACOUSTIC WALL RW 50 INDIVIDUAL OMNI-DIRECTIONAL PANELS H=3.6m W/ 1x PASS DOOR & CEILING BAFFLE"
          - "PAIRED PANEL MOVABLE WALL RW 45 H=3.0m"
          - "VERTICAL LIFT RETRACTABLE WALL RW 53"
        """
        clean = text.upper()
        res = {
            "system_type": OperableWallSystemType.INDIVIDUAL_OMNI_DIRECTIONAL_PANELS,
            "wall_height_m": 0.0,
            "panel_width_mm": 0.0,
            "acoustic_rating_rw_db": 0,
            "has_retractable_seals": False,
            "parking_stack_track_length_m": 2.5,
            "has_plenum_baffle": False,
            "plenum_height_m": 0.9,
            "pass_doors_count": 0,
        }

        # System Typology
        if "PAIRED" in clean or "CENTER HUNG" in clean or "CENTER-HUNG" in clean:
            res["system_type"] = OperableWallSystemType.CENTER_HUNG_PAIRED_PANELS
        elif "VERTICAL LIFT" in clean or "SKYFOLD" in clean:
            res["system_type"] = OperableWallSystemType.VERTICAL_LIFT_RETRACTABLE_WALL
        elif "CONTINUOUS" in clean or "HINGED TRAIN" in clean or "ACCORDION" in clean:
            res["system_type"] = OperableWallSystemType.CONTINUOUSLY_HINGED_TRAIN
        else:
            res["system_type"] = OperableWallSystemType.INDIVIDUAL_OMNI_DIRECTIONAL_PANELS

        # Acoustic Rating: RW 50, RW 45, 52dB, RW53
        rw_match = re.search(r'\b(?:RW|STC)?\s*(\d{2})\s*(?:DB|RW|STC)?\b', clean)
        if rw_match:
            try:
                rw_val = int(rw_match.group(1))
                if 35 <= rw_val <= 65:
                    res["acoustic_rating_rw_db"] = rw_val
            except ValueError:
                pass

        # Wall Height: H=3.6m, 3.6M HIGH, 3000 HIGH
        h_match = re.search(r'(?:H\s*[=:]?\s*|HEIGHT\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*M\b', clean)
        if not h_match:
            h_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b\s*(?:HIGH|HEIGHT)', clean)
        if h_match:
            try:
                h_val = float(h_match.group(1))
                if 2.0 <= h_val <= 15.0:
                    res["wall_height_m"] = h_val
            except ValueError:
                pass

        # Panel width: 1000mm, 1200mm, W=1000
        p_match = re.search(r'(\d{3,4})\s*MM\s*(?:PANEL|WIDTH)?', clean)
        if p_match:
            try:
                pw = float(p_match.group(1))
                if 600.0 <= pw <= 1500.0:
                    res["panel_width_mm"] = pw
            except ValueError:
                pass

        # Parking stack track length: 2.5m STACK, PARKING=3.0m
        stack_match = re.search(r'(?:STACK|PARKING\s*(?:TRACK)?)\s*[=:]?\s*(\d+(?:\.\d+)?)\s*M\b', clean)
        if stack_match:
            try:
                stk = float(stack_match.group(1))
                if 0.5 <= stk <= 10.0:
                    res["parking_stack_track_length_m"] = stk
            except ValueError:
                pass

        # Plenum baffle
        if "BAFFLE" in clean or "PLENUM" in clean or "FLANKING" in clean:
            res["has_plenum_baffle"] = True

        # Pass doors: 1x PASS DOOR, 2 PASS DOORS
        door_match = re.search(r'(\d+)\s*[xX]?\s*PASS\s*DOOR', clean)
        if door_match:
            try:
                res["pass_doors_count"] = int(door_match.group(1))
            except ValueError:
                res["pass_doors_count"] = 1
        elif "PASS DOOR" in clean:
            res["pass_doors_count"] = 1

        if re.search(r"RETRACTABLE\s+SEAL|\bSEALS\b", clean):
            res["has_retractable_seals"] = True

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
    def evaluate_operable_walls(
        cls,
        raw_walls_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> OperableWallExtractionResult:
        """
        Authoritative shadow extraction for operable acoustic walls, tracks, and plenum baffles.
        """
        extracted_walls: List[OperableWallSpec] = []
        tot_wall_m = 0.0
        tot_wall_area_m2 = 0.0
        tot_track_m = 0.0
        tot_panels = 0
        tot_baffle_area_m2 = 0.0
        tot_pass_doors = 0

        m_by_sys: Dict[str, float] = {}
        m_by_rw: Dict[str, float] = {}

        for item in raw_walls_data:
            wall_id = item.get("wall_id", f"OW_{len(extracted_walls)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            stype_val = item.get("system_type", parsed["system_type"])
            if isinstance(stype_val, str):
                try:
                    stype = OperableWallSystemType(stype_val)
                except ValueError:
                    stype = OperableWallSystemType.INDIVIDUAL_OMNI_DIRECTIONAL_PANELS
            else:
                stype = stype_val

            wall_h = float(item.get("wall_height_m", parsed["wall_height_m"]))
            panel_w = float(item.get("panel_width_mm", parsed["panel_width_mm"]))
            rw_val = int(item.get("acoustic_rating_rw_db", parsed["acoustic_rating_rw_db"]))
            stack_len = float(item.get("parking_stack_track_length_m", parsed["parking_stack_track_length_m"]))
            has_baffle = bool(item.get("has_plenum_baffle", parsed["has_plenum_baffle"]))
            plenum_h = float(item.get("plenum_height_m", parsed["plenum_height_m"]))
            doors_cnt = int(item.get("pass_doors_count", parsed["pass_doors_count"]))
            has_seals = bool(item.get("has_retractable_seals", parsed["has_retractable_seals"]))

            spec = OperableWallSpec(
                wall_id=wall_id,
                system_type=stype,
                centerline_points=snapped_pts,
                wall_height_m=wall_h,
                panel_width_mm=panel_w,
                acoustic_rating_rw_db=rw_val,
                has_retractable_seals=has_seals,
                parking_stack_track_length_m=stack_len,
                has_plenum_baffle=has_baffle,
                plenum_height_m=plenum_h,
                pass_doors_count=doors_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_walls.append(spec)

            clear_wall_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            wall_area = clear_wall_m * wall_h
            track_m = clear_wall_m + stack_len
            panels_cnt = (
                int(math.ceil(clear_wall_m / (panel_w / 1000.0)))
                if clear_wall_m > 0 and panel_w > 0
                else 0
            )

            tot_wall_m += clear_wall_m
            tot_wall_area_m2 += wall_area
            tot_track_m += track_m
            tot_panels += panels_cnt
            tot_pass_doors += doors_cnt

            if has_baffle:
                tot_baffle_area_m2 += clear_wall_m * plenum_h

            sys_key = stype.value
            m_by_sys[sys_key] = round(m_by_sys.get(sys_key, 0.0) + clear_wall_m, 4)

            rw_key = f"Rw{rw_val}"
            m_by_rw[rw_key] = round(m_by_rw.get(rw_key, 0.0) + clear_wall_m, 4)

        quantities = OperableWallQuantities(
            total_walls_count=len(extracted_walls),
            total_wall_linear_meters=round(tot_wall_m, 4),
            total_wall_area_m2=round(tot_wall_area_m2, 4),
            total_overhead_track_meters=round(tot_track_m, 4),
            total_panels_count=tot_panels,
            total_plenum_baffle_area_m2=round(tot_baffle_area_m2, 4),
            total_pass_doors_count=tot_pass_doors,
            linear_meters_by_system=m_by_sys,
            linear_meters_by_rw=m_by_rw,
        )

        return OperableWallExtractionResult(
            walls=extracted_walls,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceOperableAcousticWallShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
