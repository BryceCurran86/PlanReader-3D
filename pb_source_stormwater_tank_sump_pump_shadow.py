"""
pb_source_stormwater_tank_sump_pump_shadow.py

Authoritative shadow-mode extraction and civil/hydraulic takeoff for On-Site Detention (OSD) tanks,
basement stormwater sump pits, duplex submersible pumps, and concrete structure volumes.

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


class StormwaterFacilityType(str, Enum):
    ON_SITE_DETENTION_OSD_TANK = "ON_SITE_DETENTION_OSD_TANK"
    RAINWATER_RETENTION_REUSE_TANK = "RAINWATER_RETENTION_REUSE_TANK"
    BASEMENT_DRAINAGE_SUMP_PIT = "BASEMENT_DRAINAGE_SUMP_PIT"
    SURFACE_STORMWATER_CATCH_PIT = "SURFACE_STORMWATER_CATCH_PIT"


class PumpingEquipmentConfig(str, Enum):
    DUPLEX_SUBMERSIBLE_PUMPS = "DUPLEX_SUBMERSIBLE_PUMPS"
    SIMPLEX_SUMP_PUMP = "SIMPLEX_SUMP_PUMP"
    GRAVITY_DISCHARGE = "GRAVITY_DISCHARGE"


class GrateCoverClass(str, Enum):
    CLASS_D_HEAVY_DUTY = "CLASS_D_HEAVY_DUTY"
    CLASS_B_LIGHT_VEHICLE = "CLASS_B_LIGHT_VEHICLE"
    SOLID_ALUMINIUM_GAS_TIGHT = "SOLID_ALUMINIUM_GAS_TIGHT"


@dataclass
class StormwaterFacilitySpec:
    facility_id: str
    facility_type: StormwaterFacilityType = StormwaterFacilityType.BASEMENT_DRAINAGE_SUMP_PIT
    pumping_config: PumpingEquipmentConfig = PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS
    cover_class: GrateCoverClass = GrateCoverClass.CLASS_D_HEAVY_DUTY
    center_point: Tuple[float, float] = (0.0, 0.0)
    internal_length_m: float = 1.2
    internal_width_m: float = 1.2
    internal_depth_m: float = 1.5
    wall_thickness_mm: float = 200.0
    base_thickness_mm: float = 250.0
    level_id: str = "BASEMENT"
    source_callout: str = ""


@dataclass
class StormwaterFacilityQuantities:
    total_facilities_count: int = 0
    total_storage_capacity_m3: float = 0.0
    total_structure_concrete_volume_m3: float = 0.0
    total_submersible_pumps_count: int = 0
    osd_tanks_count: int = 0
    sump_pits_count: int = 0
    facilities_by_type: Dict[str, int] = field(default_factory=dict)


@dataclass
class StormwaterFacilityExtractionResult:
    facilities: List[StormwaterFacilitySpec] = field(default_factory=list)
    quantities: StormwaterFacilityQuantities = field(default_factory=StormwaterFacilityQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceStormwaterTankSumpPumpShadowAuthority:
    """Authoritative shadow evaluator for stormwater detention tanks, sump pits, and pump equipment."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses stormwater civil and hydraulic callouts.
        Example strings:
          - "1200x1200x1500 DEEP BASEMENT SUMP PIT W/ DUPLEX SUBMERSIBLE PUMPS CLASS D GRATE"
          - "50m3 ON-SITE DETENTION (OSD) TANK 5.0x4.0x2.5m DEEP"
          - "600x600 SURFACE CATCH PIT GRAVITY OUTLET"
        """
        clean = text.upper()
        res = {
            "facility_type": StormwaterFacilityType.BASEMENT_DRAINAGE_SUMP_PIT,
            "pumping_config": PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS,
            "cover_class": GrateCoverClass.CLASS_D_HEAVY_DUTY,
            "internal_length_m": 1.2,
            "internal_width_m": 1.2,
            "internal_depth_m": 1.5,
            "wall_thickness_mm": 200.0,
            "base_thickness_mm": 250.0,
        }

        # Facility Typology
        if "OSD" in clean or "DETENTION" in clean:
            res["facility_type"] = StormwaterFacilityType.ON_SITE_DETENTION_OSD_TANK
            res["internal_length_m"] = 5.0
            res["internal_width_m"] = 4.0
            res["internal_depth_m"] = 2.5
            res["pumping_config"] = PumpingEquipmentConfig.GRAVITY_DISCHARGE
        elif "RETENTION" in clean or "HARVEST" in clean or "REUSE" in clean:
            res["facility_type"] = StormwaterFacilityType.RAINWATER_RETENTION_REUSE_TANK
            res["internal_length_m"] = 4.0
            res["internal_width_m"] = 3.0
            res["internal_depth_m"] = 2.0
            res["pumping_config"] = PumpingEquipmentConfig.SIMPLEX_SUMP_PUMP
        elif "CATCH PIT" in clean or "INLET PIT" in clean or "JUNCTION PIT" in clean:
            res["facility_type"] = StormwaterFacilityType.SURFACE_STORMWATER_CATCH_PIT
            res["internal_length_m"] = 0.6
            res["internal_width_m"] = 0.6
            res["internal_depth_m"] = 0.9
            res["pumping_config"] = PumpingEquipmentConfig.GRAVITY_DISCHARGE
        else:
            res["facility_type"] = StormwaterFacilityType.BASEMENT_DRAINAGE_SUMP_PIT
            res["pumping_config"] = PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS

        # Pumping Config override
        if "DUPLEX" in clean or "DUAL PUMP" in clean or "2x PUMPS" in clean:
            res["pumping_config"] = PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS
        elif "SIMPLEX" in clean or "SINGLE PUMP" in clean or "1x PUMP" in clean:
            res["pumping_config"] = PumpingEquipmentConfig.SIMPLEX_SUMP_PUMP
        elif "GRAVITY" in clean or "NON-PUMPED" in clean:
            res["pumping_config"] = PumpingEquipmentConfig.GRAVITY_DISCHARGE

        # Grate/Cover Class
        if "CLASS B" in clean or "LIGHT" in clean:
            res["cover_class"] = GrateCoverClass.CLASS_B_LIGHT_VEHICLE
        elif "GAS TIGHT" in clean or "SOLID" in clean or "ALUMINIUM" in clean:
            res["cover_class"] = GrateCoverClass.SOLID_ALUMINIUM_GAS_TIGHT
        else:
            res["cover_class"] = GrateCoverClass.CLASS_D_HEAVY_DUTY

        # 3D Dimensions: 1200x1200x1500 or 5.0x4.0x2.5
        dim_3d_match = re.search(r'(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)\s*[xX*]\s*(\d+(?:\.\d+)?)', clean)
        if dim_3d_match:
            try:
                v1 = float(dim_3d_match.group(1))
                v2 = float(dim_3d_match.group(2))
                v3 = float(dim_3d_match.group(3))
                # Check if millimeters (> 50) or meters
                if v1 > 50.0:
                    v1 /= 1000.0
                    v2 /= 1000.0
                    v3 /= 1000.0
                res["internal_length_m"] = max(v1, v2)
                res["internal_width_m"] = min(v1, v2)
                res["internal_depth_m"] = v3
            except ValueError:
                pass
        else:
            # 2D Dimensions e.g. 600x600
            dim_2d_match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', clean)
            if dim_2d_match:
                try:
                    d1 = float(dim_2d_match.group(1)) / 1000.0
                    d2 = float(dim_2d_match.group(2)) / 1000.0
                    res["internal_length_m"] = max(d1, d2)
                    res["internal_width_m"] = min(d1, d2)
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
    def calculate_concrete_volume(
        length_m: float,
        width_m: float,
        depth_m: float,
        wall_thk_mm: float,
        base_thk_mm: float
    ) -> float:
        """
        Calculates hollow rectangular concrete box volume: outer volume - inner cavity.
        """
        tw = wall_thk_mm / 1000.0
        tb = base_thk_mm / 1000.0
        outer_l = length_m + (2.0 * tw)
        outer_w = width_m + (2.0 * tw)
        outer_d = depth_m + tb
        outer_vol = outer_l * outer_w * outer_d
        inner_vol = length_m * width_m * depth_m
        return round(outer_vol - inner_vol, 4)

    @classmethod
    def evaluate_facilities(
        cls,
        raw_facilities_data: List[Dict[str, any]],
        default_level: str = "BASEMENT"
    ) -> StormwaterFacilityExtractionResult:
        """
        Authoritative shadow extraction for stormwater detention tanks and basement sump pits.
        """
        extracted_facilities: List[StormwaterFacilitySpec] = []
        tot_storage_m3 = 0.0
        tot_concrete_m3 = 0.0
        tot_pumps = 0
        osd_cnt = 0
        sump_cnt = 0
        by_type: Dict[str, int] = {}

        for item in raw_facilities_data:
            fac_id = item.get("facility_id", f"ST_{len(extracted_facilities)+1:03d}")
            raw_center = item.get("center_point", (0.0, 0.0))
            snapped_center = cls.snap_point(raw_center)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ftype_val = item.get("facility_type", parsed["facility_type"])
            if isinstance(ftype_val, str):
                try:
                    ftype = StormwaterFacilityType(ftype_val)
                except ValueError:
                    ftype = StormwaterFacilityType.BASEMENT_DRAINAGE_SUMP_PIT
            else:
                ftype = ftype_val

            pconfig_val = item.get("pumping_config", parsed["pumping_config"])
            if isinstance(pconfig_val, str):
                try:
                    pconfig = PumpingEquipmentConfig(pconfig_val)
                except ValueError:
                    pconfig = PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS
            else:
                pconfig = pconfig_val

            cclass_val = item.get("cover_class", parsed["cover_class"])
            if isinstance(cclass_val, str):
                try:
                    cclass = GrateCoverClass(cclass_val)
                except ValueError:
                    cclass = GrateCoverClass.CLASS_D_HEAVY_DUTY
            else:
                cclass = cclass_val

            l_m = float(item.get("internal_length_m", parsed["internal_length_m"]))
            w_m = float(item.get("internal_width_m", parsed["internal_width_m"]))
            d_m = float(item.get("internal_depth_m", parsed["internal_depth_m"]))
            tw_mm = float(item.get("wall_thickness_mm", parsed["wall_thickness_mm"]))
            tb_mm = float(item.get("base_thickness_mm", parsed["base_thickness_mm"]))

            spec = StormwaterFacilitySpec(
                facility_id=fac_id,
                facility_type=ftype,
                pumping_config=pconfig,
                cover_class=cclass,
                center_point=snapped_center,
                internal_length_m=l_m,
                internal_width_m=w_m,
                internal_depth_m=d_m,
                wall_thickness_mm=tw_mm,
                base_thickness_mm=tb_mm,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_facilities.append(spec)

            storage_m3 = l_m * w_m * d_m
            conc_vol = cls.calculate_concrete_volume(l_m, w_m, d_m, tw_mm, tb_mm)

            tot_storage_m3 += storage_m3
            tot_concrete_m3 += conc_vol

            if pconfig == PumpingEquipmentConfig.DUPLEX_SUBMERSIBLE_PUMPS:
                tot_pumps += 2
            elif pconfig == PumpingEquipmentConfig.SIMPLEX_SUMP_PUMP:
                tot_pumps += 1

            if ftype == StormwaterFacilityType.ON_SITE_DETENTION_OSD_TANK:
                osd_cnt += 1
            elif ftype == StormwaterFacilityType.BASEMENT_DRAINAGE_SUMP_PIT:
                sump_cnt += 1

            t_key = ftype.value
            by_type[t_key] = by_type.get(t_key, 0) + 1

        quantities = StormwaterFacilityQuantities(
            total_facilities_count=len(extracted_facilities),
            total_storage_capacity_m3=round(tot_storage_m3, 4),
            total_structure_concrete_volume_m3=round(tot_concrete_m3, 4),
            total_submersible_pumps_count=tot_pumps,
            osd_tanks_count=osd_cnt,
            sump_pits_count=sump_cnt,
            facilities_by_type=by_type,
        )

        return StormwaterFacilityExtractionResult(
            facilities=extracted_facilities,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceStormwaterTankSumpPumpShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
