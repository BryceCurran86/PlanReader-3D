"""
pb_source_cable_tray_conduit_racking_shadow.py

Authoritative shadow-mode extraction and electrical takeoff for cable containment systems:
heavy-duty cable ladders, perforated trays, wire mesh basket trays, and unistrut trapeze racks.

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


class CableSupportSystemType(str, Enum):
    HEAVY_DUTY_CABLE_LADDER = "HEAVY_DUTY_CABLE_LADDER"
    PERFORATED_CABLE_TRAY = "PERFORATED_CABLE_TRAY"
    WIRE_MESH_BASKET_TRAY = "WIRE_MESH_BASKET_TRAY"
    UNISTRUT_CONDUIT_TRAPEZE_RACK = "UNISTRUT_CONDUIT_TRAPEZE_RACK"


@dataclass
class CableTrayRunSpec:
    run_id: str
    system_type: CableSupportSystemType = CableSupportSystemType.PERFORATED_CABLE_TRAY
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    tray_width_mm: float = 300.0
    side_rail_depth_mm: float = 75.0
    support_spacing_m: float = 2.0
    fittings_count: int = 0
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class CableTrayContainmentQuantities:
    total_runs_count: int = 0
    total_linear_meters: float = 0.0
    ladder_linear_meters: float = 0.0
    tray_linear_meters: float = 0.0
    basket_linear_meters: float = 0.0
    total_trapeze_supports_count: int = 0
    total_fittings_count: int = 0
    linear_meters_by_width: Dict[str, float] = field(default_factory=dict)
    linear_meters_by_system: Dict[str, float] = field(default_factory=dict)


@dataclass
class CableTrayContainmentExtractionResult:
    runs: List[CableTrayRunSpec] = field(default_factory=list)
    quantities: CableTrayContainmentQuantities = field(default_factory=CableTrayContainmentQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceCableTrayConduitRackingShadowAuthority:
    """Authoritative shadow evaluator for electrical cable trays, ladders, and racking."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses electrical cable containment schedule callouts.
        Example strings:
          - "600mm WIDE HEAVY DUTY CABLE LADDER 100mm DEEP SUPPORTS AT 2.0m W/ 2x 90 BENDS"
          - "300mm PERFORATED CABLE TRAY SUPPORTS AT 1.5m"
          - "150mm WIRE MESH BASKET TRAY"
          - "UNISTRUT CONDUIT TRAPEZE RACK 450mm WIDE"
        """
        clean = text.upper()
        res = {
            "system_type": CableSupportSystemType.PERFORATED_CABLE_TRAY,
            "tray_width_mm": 300.0,
            "side_rail_depth_mm": 75.0,
            "support_spacing_m": 2.0,
            "fittings_count": 0,
        }

        # System Typology
        if "LADDER" in clean:
            res["system_type"] = CableSupportSystemType.HEAVY_DUTY_CABLE_LADDER
            res["tray_width_mm"] = 600.0
            res["side_rail_depth_mm"] = 100.0
        elif "BASKET" in clean or "WIRE MESH" in clean or "MESH TRAY" in clean:
            res["system_type"] = CableSupportSystemType.WIRE_MESH_BASKET_TRAY
            res["tray_width_mm"] = 150.0
            res["side_rail_depth_mm"] = 50.0
        elif "UNISTRUT" in clean or "CONDUIT RACK" in clean or "TRAPEZE" in clean:
            res["system_type"] = CableSupportSystemType.UNISTRUT_CONDUIT_TRAPEZE_RACK
            res["tray_width_mm"] = 450.0
        else:
            res["system_type"] = CableSupportSystemType.PERFORATED_CABLE_TRAY
            res["tray_width_mm"] = 300.0
            res["side_rail_depth_mm"] = 75.0

        # Tray Width: 150mm, 300mm, 450mm, 600mm, 750mm, 900mm
        w_match = re.search(r'(\d{3,4})\s*MM\s*(?:WIDE|WIDTH)?', clean)
        if w_match:
            try:
                w_val = float(w_match.group(1))
                if 50.0 <= w_val <= 1200.0:
                    res["tray_width_mm"] = w_val
            except ValueError:
                pass

        # Side Rail Depth: 50mm, 75mm, 100mm, 150mm DEEP
        d_match = re.search(r'(\d{2,3})\s*MM\s*(?:DEEP|DEPTH|RAIL)', clean)
        if d_match:
            try:
                d_val = float(d_match.group(1))
                if 25.0 <= d_val <= 200.0:
                    res["side_rail_depth_mm"] = d_val
            except ValueError:
                pass

        # Support Spacing: SUPPORTS AT 2.0m, 1.5M CTS, 2.0M SPACING
        sp_match = re.search(r'(?:SUPPORTS?\s*(?:AT)?\s*|SPACING\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*M', clean)
        if sp_match:
            try:
                sp_val = float(sp_match.group(1))
                if 0.5 <= sp_val <= 5.0:
                    res["support_spacing_m"] = sp_val
            except ValueError:
                pass

        # Fittings: 2x 90 BENDS, 1x TEE, 2 FITTINGS
        fit_match = re.search(r'(\d+)\s*[xX]?\s*(?:(?:90\s*)?BEND|TEE|CROSS|RISER|FITTING)', clean)
        if fit_match:
            try:
                res["fittings_count"] = int(fit_match.group(1))
            except ValueError:
                res["fittings_count"] = 1
        elif "BEND" in clean or "TEE" in clean or "FITTING" in clean:
            res["fittings_count"] = 1

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
    def evaluate_containment_runs(
        cls,
        raw_runs_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> CableTrayContainmentExtractionResult:
        """
        Authoritative shadow extraction for electrical cable containment runs.
        """
        extracted_runs: List[CableTrayRunSpec] = []
        tot_linear_m = 0.0
        ladder_m = 0.0
        tray_m = 0.0
        basket_m = 0.0
        tot_supports = 0
        tot_fittings = 0

        m_by_width: Dict[str, float] = {}
        m_by_sys: Dict[str, float] = {}

        for item in raw_runs_data:
            run_id = item.get("run_id", f"CT_{len(extracted_runs)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            stype_val = item.get("system_type", parsed["system_type"])
            if isinstance(stype_val, str):
                try:
                    stype = CableSupportSystemType(stype_val)
                except ValueError:
                    stype = CableSupportSystemType.PERFORATED_CABLE_TRAY
            else:
                stype = stype_val

            w_mm = float(item.get("tray_width_mm", parsed["tray_width_mm"]))
            d_mm = float(item.get("side_rail_depth_mm", parsed["side_rail_depth_mm"]))
            sp_m = float(item.get("support_spacing_m", parsed["support_spacing_m"]))
            fittings_cnt = int(item.get("fittings_count", parsed["fittings_count"]))

            spec = CableTrayRunSpec(
                run_id=run_id,
                system_type=stype,
                centerline_points=snapped_pts,
                tray_width_mm=w_mm,
                side_rail_depth_mm=d_mm,
                support_spacing_m=sp_m,
                fittings_count=fittings_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_runs.append(spec)

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            supports_cnt = int(math.ceil(run_len_m / sp_m)) + 1 if run_len_m > 0 else 0

            tot_linear_m += run_len_m
            tot_supports += supports_cnt
            tot_fittings += fittings_cnt

            if stype == CableSupportSystemType.HEAVY_DUTY_CABLE_LADDER:
                ladder_m += run_len_m
            elif stype == CableSupportSystemType.PERFORATED_CABLE_TRAY:
                tray_m += run_len_m
            elif stype == CableSupportSystemType.WIRE_MESH_BASKET_TRAY:
                basket_m += run_len_m

            w_key = f"{int(w_mm)}mm"
            m_by_width[w_key] = round(m_by_width.get(w_key, 0.0) + run_len_m, 4)

            sys_key = stype.value
            m_by_sys[sys_key] = round(m_by_sys.get(sys_key, 0.0) + run_len_m, 4)

        quantities = CableTrayContainmentQuantities(
            total_runs_count=len(extracted_runs),
            total_linear_meters=round(tot_linear_m, 4),
            ladder_linear_meters=round(ladder_m, 4),
            tray_linear_meters=round(tray_m, 4),
            basket_linear_meters=round(basket_m, 4),
            total_trapeze_supports_count=tot_supports,
            total_fittings_count=tot_fittings,
            linear_meters_by_width=m_by_width,
            linear_meters_by_system=m_by_sys,
        )

        return CableTrayContainmentExtractionResult(
            runs=extracted_runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceCableTrayConduitRackingShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
