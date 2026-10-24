"""
pb_source_trench_drain_grate_shadow.py

Authoritative shadow-mode extraction and civil takeoff for heavy-duty linear trench drains,
load-rated cast iron/stainless grates, concrete bedding haunches, and in-line silt sumps.

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


class TrenchGrateType(str, Enum):
    DUCTILE_IRON_SLOTTED_GRATE = "DUCTILE_IRON_SLOTTED_GRATE"
    HEELGUARD_STAINLESS_WEDGE_WIRE = "HEELGUARD_STAINLESS_WEDGE_WIRE"
    GALVANIZED_STEEL_BAR_GRATE = "GALVANIZED_STEEL_BAR_GRATE"
    SOLID_DUCTILE_IRON_COVER = "SOLID_DUCTILE_IRON_COVER"


class TrenchLoadClass(str, Enum):
    CLASS_B_LIGHT_TRAFFIC = "CLASS_B_LIGHT_TRAFFIC"
    CLASS_C_COMMERCIAL = "CLASS_C_COMMERCIAL"
    CLASS_D_HEAVY_DUTY = "CLASS_D_HEAVY_DUTY"
    CLASS_E_INDUSTRIAL = "CLASS_E_INDUSTRIAL"


@dataclass
class TrenchDrainRunSpec:
    run_id: str
    grate_type: TrenchGrateType = TrenchGrateType.DUCTILE_IRON_SLOTTED_GRATE
    load_class: TrenchLoadClass = TrenchLoadClass.CLASS_D_HEAVY_DUTY
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    internal_width_mm: float = 200.0
    invert_depth_mm: float = 250.0
    bedding_thickness_mm: float = 150.0
    inline_sumps_count: int = 1
    level_id: str = "CIVIL"
    source_callout: str = ""


@dataclass
class TrenchDrainQuantities:
    total_runs_count: int = 0
    total_length_meters: float = 0.0
    total_grating_meters: float = 0.0
    total_concrete_encasement_m3: float = 0.0
    total_inline_sumps_count: int = 0
    length_by_grate_type: Dict[str, float] = field(default_factory=dict)
    length_by_load_class: Dict[str, float] = field(default_factory=dict)


@dataclass
class TrenchDrainExtractionResult:
    runs: List[TrenchDrainRunSpec] = field(default_factory=list)
    quantities: TrenchDrainQuantities = field(default_factory=TrenchDrainQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceTrenchDrainGrateShadowAuthority:
    """Authoritative shadow evaluator for linear trench drains and load-rated grates."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses civil/hydraulic trench drain schedule callouts.
        Example strings:
          - "200mm INTERNAL POLYMER CONCRETE TRENCH DRAIN CLASS D DUCTILE IRON SLOTTED GRATE W/ 1x IN-LINE SILT BASKET"
          - "150mm HEELGUARD STAINLESS STEEL WEDGE WIRE TRENCH DRAIN CLASS C"
          - "100mm GALVANIZED STEEL BAR GRATE TRENCH DRAIN CLASS B"
          - "300mm SOLID DUCTILE IRON COVER CLASS E INDUSTRIAL"
        """
        clean = text.upper()
        res = {
            "grate_type": TrenchGrateType.DUCTILE_IRON_SLOTTED_GRATE,
            "load_class": TrenchLoadClass.CLASS_D_HEAVY_DUTY,
            "internal_width_mm": 200.0,
            "invert_depth_mm": 250.0,
            "inline_sumps_count": 1,
        }

        # Grate Typology
        if "HEELGUARD" in clean or "WEDGE WIRE" in clean or "STAINLESS" in clean:
            res["grate_type"] = TrenchGrateType.HEELGUARD_STAINLESS_WEDGE_WIRE
            res["load_class"] = TrenchLoadClass.CLASS_C_COMMERCIAL
        elif "SOLID" in clean or "COVER" in clean:
            res["grate_type"] = TrenchGrateType.SOLID_DUCTILE_IRON_COVER
        elif "GALV" in clean or "BAR GRATE" in clean:
            res["grate_type"] = TrenchGrateType.GALVANIZED_STEEL_BAR_GRATE
            res["load_class"] = TrenchLoadClass.CLASS_B_LIGHT_TRAFFIC
        else:
            res["grate_type"] = TrenchGrateType.DUCTILE_IRON_SLOTTED_GRATE
            res["load_class"] = TrenchLoadClass.CLASS_D_HEAVY_DUTY

        # Load Class: CLASS A, B, C, D, E, F
        if "CLASS E" in clean:
            res["load_class"] = TrenchLoadClass.CLASS_E_INDUSTRIAL
        elif "CLASS D" in clean:
            res["load_class"] = TrenchLoadClass.CLASS_D_HEAVY_DUTY
        elif "CLASS C" in clean:
            res["load_class"] = TrenchLoadClass.CLASS_C_COMMERCIAL
        elif "CLASS B" in clean:
            res["load_class"] = TrenchLoadClass.CLASS_B_LIGHT_TRAFFIC

        # Width: 100mm, 150mm, 200mm, 300mm INTERNAL
        w_match = re.search(r'(\d{2,3})\s*MM\s*(?:INTERNAL|WIDE|WIDTH)?', clean)
        if w_match:
            try:
                w = float(w_match.group(1))
                if 50.0 <= w <= 600.0:
                    res["internal_width_mm"] = w
            except ValueError:
                pass

        # Invert depth: 200mm, 250mm, 300mm DEEP
        d_match = re.search(r'(\d{2,3})\s*MM\s*(?:DEEP|DEPTH|INVERT)', clean)
        if d_match:
            try:
                d = float(d_match.group(1))
                if 100.0 <= d <= 1000.0:
                    res["invert_depth_mm"] = d
            except ValueError:
                pass

        # Sump / silt basket count: 1x IN-LINE SILT BASKET, 2 SILT PITS
        sump_match = re.search(r'(\d+)\s*[xX]?\s*(?:IN-LINE\s*)?(?:SILT|SUMP)', clean)
        if sump_match:
            try:
                res["inline_sumps_count"] = int(sump_match.group(1))
            except ValueError:
                res["inline_sumps_count"] = 1

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
    def evaluate_trench_runs(
        cls,
        raw_runs_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "CIVIL"
    ) -> TrenchDrainExtractionResult:
        """
        Authoritative shadow extraction for trench drains, grates, and concrete bedding.
        """
        extracted_runs: List[TrenchDrainRunSpec] = []
        tot_length_m = 0.0
        tot_conc_m3 = 0.0
        tot_sumps = 0

        len_by_grate: Dict[str, float] = {}
        len_by_load: Dict[str, float] = {}

        for item in raw_runs_data:
            run_id = item.get("run_id", f"TD_{len(extracted_runs)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            gtype_val = item.get("grate_type", parsed["grate_type"])
            if isinstance(gtype_val, str):
                try:
                    gtype = TrenchGrateType(gtype_val)
                except ValueError:
                    gtype = TrenchGrateType.DUCTILE_IRON_SLOTTED_GRATE
            else:
                gtype = gtype_val

            lclass_val = item.get("load_class", parsed["load_class"])
            if isinstance(lclass_val, str):
                try:
                    lclass = TrenchLoadClass(lclass_val)
                except ValueError:
                    lclass = TrenchLoadClass.CLASS_D_HEAVY_DUTY
            else:
                lclass = lclass_val

            w_int_mm = float(item.get("internal_width_mm", parsed["internal_width_mm"]))
            d_inv_mm = float(item.get("invert_depth_mm", parsed["invert_depth_mm"]))
            bed_thk_mm = float(item.get("bedding_thickness_mm", 150.0))
            sumps_cnt = int(item.get("inline_sumps_count", parsed["inline_sumps_count"]))

            run_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)

            # Concrete surround volume:
            # W_ext = (w_int + 2 * bed_thk) / 1000.0
            # D_ext = (d_inv + bed_thk) / 1000.0
            # V_conc = L * (W_ext * D_ext - (w_int/1000) * (d_inv/1000))
            w_ext_m = (w_int_mm + 2.0 * bed_thk_mm) / 1000.0
            d_ext_m = (d_inv_mm + bed_thk_mm) / 1000.0
            w_int_m = w_int_mm / 1000.0
            d_inv_m = d_inv_mm / 1000.0
            net_conc_area_m2 = (w_ext_m * d_ext_m) - (w_int_m * d_inv_m)
            conc_vol_m3 = round(run_len_m * net_conc_area_m2, 4)

            spec = TrenchDrainRunSpec(
                run_id=run_id,
                grate_type=gtype,
                load_class=lclass,
                centerline_points=snapped_pts,
                internal_width_mm=w_int_mm,
                invert_depth_mm=d_inv_mm,
                bedding_thickness_mm=bed_thk_mm,
                inline_sumps_count=sumps_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_runs.append(spec)

            tot_length_m += run_len_m
            tot_conc_m3 += conc_vol_m3
            tot_sumps += sumps_cnt

            g_key = gtype.value
            len_by_grate[g_key] = round(len_by_grate.get(g_key, 0.0) + run_len_m, 4)

            l_key = lclass.value
            len_by_load[l_key] = round(len_by_load.get(l_key, 0.0) + run_len_m, 4)

        quantities = TrenchDrainQuantities(
            total_runs_count=len(extracted_runs),
            total_length_meters=round(tot_length_m, 4),
            total_grating_meters=round(tot_length_m, 4),
            total_concrete_encasement_m3=round(tot_conc_m3, 4),
            total_inline_sumps_count=tot_sumps,
            length_by_grate_type=len_by_grate,
            length_by_load_class=len_by_load,
        )

        return TrenchDrainExtractionResult(
            runs=extracted_runs,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceTrenchDrainGrateShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
