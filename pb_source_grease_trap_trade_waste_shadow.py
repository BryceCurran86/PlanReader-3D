"""
pb_source_grease_trap_trade_waste_shadow.py

Authoritative shadow-mode extraction and hydraulic takeoff for commercial kitchen grease traps,
trade waste interceptors, gastight access covers, and monitoring sampling points.

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


class GreaseTrapType(str, Enum):
    IN_GROUND_CONCRETE_INTERCEPTOR = "IN_GROUND_CONCRETE_INTERCEPTOR"
    ABOVE_GROUND_POLY_INTERCEPTOR = "ABOVE_GROUND_POLY_INTERCEPTOR"
    UNDER_SINK_AUTOMATIC_RECOVERY = "UNDER_SINK_AUTOMATIC_RECOVERY"


class AccessCoverLoadClass(str, Enum):
    CLASS_B_GASTIGHT = "CLASS_B_GASTIGHT"
    CLASS_D_HEAVY_DUTY_GASTIGHT = "CLASS_D_HEAVY_DUTY_GASTIGHT"
    LIGHTWEIGHT_PEDESTRIAN = "LIGHTWEIGHT_PEDESTRIAN"


@dataclass
class GreaseTrapSpec:
    trap_id: str
    trap_type: GreaseTrapType = GreaseTrapType.IN_GROUND_CONCRETE_INTERCEPTOR
    cover_class: AccessCoverLoadClass = AccessCoverLoadClass.CLASS_D_HEAVY_DUTY_GASTIGHT
    location_point: Tuple[float, float] = (0.0, 0.0)
    capacity_liters: float = 2000.0
    capacity_m3: float = 2.0
    pipe_diameter_dn: int = 100
    access_covers_count: int = 2
    sampling_pit_included: bool = True
    level_id: str = "CIVIL"
    source_callout: str = ""


@dataclass
class GreaseTrapQuantities:
    total_traps_count: int = 0
    total_capacity_liters: float = 0.0
    total_capacity_m3: float = 0.0
    total_access_covers_count: int = 0
    total_sampling_pits_count: int = 0
    traps_by_type: Dict[str, int] = field(default_factory=dict)
    traps_by_cover_class: Dict[str, int] = field(default_factory=dict)


@dataclass
class GreaseTrapExtractionResult:
    traps: List[GreaseTrapSpec] = field(default_factory=list)
    quantities: GreaseTrapQuantities = field(default_factory=GreaseTrapQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceGreaseTrapTradeWasteShadowAuthority:
    """Authoritative shadow evaluator for trade waste grease interceptors and appurtenances."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses commercial kitchen grease trap schedule callouts.
        Example strings:
          - "2000L IN-GROUND CONCRETE GREASE ARRESTOR W/ TWIN CLASS D GASTIGHT COVERS, DN100 INLET/OUTLET & SAMPLE PIT"
          - "1500L ABOVE GROUND POLYETHYLENE GREASE INTERCEPTOR CLASS B COVERS"
          - "250L UNDER-SINK AUTOMATIC GREASE RECOVERY DEVICE"
          - "5000L PRECAST CONCRETE GREASE TRAP DN150"
        """
        clean = text.upper()
        res = {
            "trap_type": GreaseTrapType.IN_GROUND_CONCRETE_INTERCEPTOR,
            "cover_class": AccessCoverLoadClass.CLASS_D_HEAVY_DUTY_GASTIGHT,
            "capacity_liters": 2000.0,
            "pipe_diameter_dn": 100,
            "access_covers_count": 2,
            "sampling_pit_included": True,
        }

        # Typology
        if "UNDER-SINK" in clean or "RECOVERY" in clean or "UNDER SINK" in clean:
            res["trap_type"] = GreaseTrapType.UNDER_SINK_AUTOMATIC_RECOVERY
            res["capacity_liters"] = 250.0
            res["cover_class"] = AccessCoverLoadClass.LIGHTWEIGHT_PEDESTRIAN
            res["access_covers_count"] = 1
            res["sampling_pit_included"] = False
        elif "POLY" in clean or "ABOVE GROUND" in clean:
            res["trap_type"] = GreaseTrapType.ABOVE_GROUND_POLY_INTERCEPTOR
            res["cover_class"] = AccessCoverLoadClass.CLASS_B_GASTIGHT
        else:
            res["trap_type"] = GreaseTrapType.IN_GROUND_CONCRETE_INTERCEPTOR

        # Capacity liters: 2000L, 1500L, 5000 LITRES, 250L
        cap_match = re.search(r'(\d{3,5})\s*(?:L\b|LITRES?|LITERS?)', clean)
        if cap_match:
            try:
                res["capacity_liters"] = float(cap_match.group(1))
            except ValueError:
                pass

        # Cover class: CLASS D, CLASS B
        if "CLASS B" in clean:
            res["cover_class"] = AccessCoverLoadClass.CLASS_B_GASTIGHT
        elif "CLASS D" in clean:
            res["cover_class"] = AccessCoverLoadClass.CLASS_D_HEAVY_DUTY_GASTIGHT

        # Access covers count: TWIN COVERS, 2x COVERS, 3 COVERS, SINGLE COVER
        if "TWIN" in clean:
            res["access_covers_count"] = 2
        elif "SINGLE" in clean:
            res["access_covers_count"] = 1
        else:
            cov_match = re.search(r'(\d+)\s*[xX]?\s*(?:GASTIGHT\s*)?COVER', clean)
            if cov_match:
                try:
                    res["access_covers_count"] = int(cov_match.group(1))
                except ValueError:
                    pass

        # Pipe diameter DN: DN100, DN150, DN80
        dn_match = re.search(r'DN\s*(\d{2,3})', clean)
        if dn_match:
            try:
                res["pipe_diameter_dn"] = int(dn_match.group(1))
            except ValueError:
                pass

        # Sampling pit: SAMPLE PIT, MONITORING PIT
        if "NO SAMPLE" in clean or "NO SAMPLING" in clean or "WITHOUT SAMPLE" in clean:
            res["sampling_pit_included"] = False
        elif "SAMPLE PIT" in clean or "SAMPLING PIT" in clean or "MONITORING" in clean:
            res["sampling_pit_included"] = True

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @classmethod
    def evaluate_traps(
        cls,
        raw_traps_data: List[Dict[str, any]],
        default_level: str = "CIVIL"
    ) -> GreaseTrapExtractionResult:
        """
        Authoritative shadow extraction for grease interceptors and trade waste appurtenances.
        """
        extracted_traps: List[GreaseTrapSpec] = []
        tot_liters = 0.0
        tot_m3 = 0.0
        tot_covers = 0
        tot_pits = 0

        traps_by_type_dict: Dict[str, int] = {}
        traps_by_cover_dict: Dict[str, int] = {}

        for item in raw_traps_data:
            trap_id = item.get("trap_id", f"GT_{len(extracted_traps)+1:02d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ttype_val = item.get("trap_type", parsed["trap_type"])
            if isinstance(ttype_val, str):
                try:
                    ttype = GreaseTrapType(ttype_val)
                except ValueError:
                    ttype = GreaseTrapType.IN_GROUND_CONCRETE_INTERCEPTOR
            else:
                ttype = ttype_val

            cclass_val = item.get("cover_class", parsed["cover_class"])
            if isinstance(cclass_val, str):
                try:
                    cclass = AccessCoverLoadClass(cclass_val)
                except ValueError:
                    cclass = AccessCoverLoadClass.CLASS_D_HEAVY_DUTY_GASTIGHT
            else:
                cclass = cclass_val

            cap_l = float(item.get("capacity_liters", parsed["capacity_liters"]))
            cap_m3 = round(cap_l / 1000.0, 4)
            dn = int(item.get("pipe_diameter_dn", parsed["pipe_diameter_dn"]))
            cov_cnt = int(item.get("access_covers_count", parsed["access_covers_count"]))
            samp_inc = bool(item.get("sampling_pit_included", parsed["sampling_pit_included"]))

            spec = GreaseTrapSpec(
                trap_id=trap_id,
                trap_type=ttype,
                cover_class=cclass,
                location_point=snapped_pt,
                capacity_liters=cap_l,
                capacity_m3=cap_m3,
                pipe_diameter_dn=dn,
                access_covers_count=cov_cnt,
                sampling_pit_included=samp_inc,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_traps.append(spec)

            tot_liters += cap_l
            tot_m3 += cap_m3
            tot_covers += cov_cnt
            if samp_inc:
                tot_pits += 1

            t_key = ttype.value
            traps_by_type_dict[t_key] = traps_by_type_dict.get(t_key, 0) + 1

            c_key = cclass.value
            traps_by_cover_dict[c_key] = traps_by_cover_dict.get(c_key, 0) + 1

        quantities = GreaseTrapQuantities(
            total_traps_count=len(extracted_traps),
            total_capacity_liters=round(tot_liters, 2),
            total_capacity_m3=round(tot_m3, 4),
            total_access_covers_count=tot_covers,
            total_sampling_pits_count=tot_pits,
            traps_by_type=traps_by_type_dict,
            traps_by_cover_class=traps_by_cover_dict,
        )

        return GreaseTrapExtractionResult(
            traps=extracted_traps,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceGreaseTrapTradeWasteShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
