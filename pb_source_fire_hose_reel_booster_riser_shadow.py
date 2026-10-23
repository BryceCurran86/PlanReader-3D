"""
pb_source_fire_hose_reel_booster_riser_shadow.py

Authoritative shadow-mode extraction and takeoff for fire hose reels, wet/dry riser landing valves,
and external breeching booster inlets.

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


class FireApparatusType(str, Enum):
    FIXED_FIRE_HOSE_REEL = "FIXED_FIRE_HOSE_REEL"
    SWINGING_ARM_FIRE_HOSE_REEL = "SWINGING_ARM_FIRE_HOSE_REEL"
    WET_RISER_LANDING_VALVE = "WET_RISER_LANDING_VALVE"
    DRY_RISER_LANDING_VALVE = "DRY_RISER_LANDING_VALVE"
    EXTERNAL_BREECHING_INLET = "EXTERNAL_BREECHING_INLET"


class MountingEnclosureType(str, Enum):
    RECESSED_WALL_CABINET = "RECESSED_WALL_CABINET"
    SURFACE_MOUNTED_CABINET = "SURFACE_MOUNTED_CABINET"
    OPEN_WALL_BRACKET = "OPEN_WALL_BRACKET"


@dataclass
class FireApparatusSpec:
    apparatus_id: str
    apparatus_type: FireApparatusType = FireApparatusType.FIXED_FIRE_HOSE_REEL
    mounting_type: MountingEnclosureType = MountingEnclosureType.RECESSED_WALL_CABINET
    location_point: Tuple[float, float] = (0.0, 0.0)
    hose_length_m: float = 36.0
    hose_diameter_mm: float = 19.0
    valve_diameter_mm: float = 25.0
    inlet_ways_count: int = 1
    level_id: str = "L01"
    host_wall_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class FireApparatusQuantities:
    total_apparatus_count: int = 0
    total_hose_reels_count: int = 0
    total_landing_valves_count: int = 0
    total_breeching_inlets_count: int = 0
    count_by_type: Dict[str, int] = field(default_factory=dict)
    count_by_mounting: Dict[str, int] = field(default_factory=dict)


@dataclass
class FireApparatusExtractionResult:
    apparatus_list: List[FireApparatusSpec] = field(default_factory=list)
    quantities: FireApparatusQuantities = field(default_factory=FireApparatusQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceFireHoseReelBoosterRiserShadowAuthority:
    """Authoritative shadow evaluator for fire hose reels, risers, and breeching inlets."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses fire service apparatus schedule callouts.
        Example strings:
          - "36m x 19mm FIRE HOSE REEL IN RECESSED CABINET W/ DN25 ISOLATION VALVE"
          - "36m x 25mm SWING ARM FHR SURFACE MOUNTED"
          - "DN65 WET RISER LANDING VALVE IN FIRE STAIR"
          - "DN65 DRY RISER LANDING VALVE"
          - "4-WAY BREECHING BOOSTER INLET CABINET"
        """
        clean = text.upper()
        res = {
            "apparatus_type": FireApparatusType.FIXED_FIRE_HOSE_REEL,
            "mounting_type": MountingEnclosureType.RECESSED_WALL_CABINET,
            "hose_length_m": 36.0,
            "hose_diameter_mm": 19.0,
            "valve_diameter_mm": 25.0,
            "inlet_ways_count": 1,
        }

        # Typology
        if "BREECHING" in clean or "BOOSTER INLET" in clean:
            res["apparatus_type"] = FireApparatusType.EXTERNAL_BREECHING_INLET
            res["inlet_ways_count"] = 4 if "4-WAY" in clean or "4 WAY" in clean else 2
            res["valve_diameter_mm"] = 65.0
        elif "WET RISER" in clean or "WET LANDING" in clean:
            res["apparatus_type"] = FireApparatusType.WET_RISER_LANDING_VALVE
            res["valve_diameter_mm"] = 65.0
        elif "DRY RISER" in clean or "DRY LANDING" in clean:
            res["apparatus_type"] = FireApparatusType.DRY_RISER_LANDING_VALVE
            res["valve_diameter_mm"] = 65.0
        elif "LANDING VALVE" in clean or "LV" in clean.split():
            res["apparatus_type"] = FireApparatusType.WET_RISER_LANDING_VALVE
            res["valve_diameter_mm"] = 65.0
        elif "SWING" in clean or "SWINGING" in clean:
            res["apparatus_type"] = FireApparatusType.SWINGING_ARM_FIRE_HOSE_REEL
        else:
            res["apparatus_type"] = FireApparatusType.FIXED_FIRE_HOSE_REEL

        # Mounting
        if "SURFACE" in clean or "WALL MOUNTED" in clean:
            res["mounting_type"] = MountingEnclosureType.SURFACE_MOUNTED_CABINET
        elif "OPEN" in clean or "BRACKET" in clean:
            res["mounting_type"] = MountingEnclosureType.OPEN_WALL_BRACKET
        else:
            res["mounting_type"] = MountingEnclosureType.RECESSED_WALL_CABINET

        # Hose length & diameter: 36m x 19mm, 30m x 25mm, 36m 19mm
        dim_match = re.search(r'(\d{2})\s*M\s*(?:[xX*]\s*|\s+)?(\d{2})\s*MM', clean)
        if dim_match:
            try:
                res["hose_length_m"] = float(dim_match.group(1))
                res["hose_diameter_mm"] = float(dim_match.group(2))
            except ValueError:
                pass

        # Valve diameter: DN25, DN65, DN100
        valv_match = re.search(r'DN\s*(\d{2,3})', clean)
        if valv_match:
            try:
                res["valve_diameter_mm"] = float(valv_match.group(1))
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
    def evaluate_apparatus(
        cls,
        raw_items_data: List[Dict[str, any]],
        default_level: str = "L01"
    ) -> FireApparatusExtractionResult:
        """
        Authoritative shadow extraction for fire hose reels, risers, and booster inlets.
        """
        extracted_list: List[FireApparatusSpec] = []
        tot_fhr = 0
        tot_lv = 0
        tot_inlet = 0

        cnt_by_type: Dict[str, int] = {}
        cnt_by_mount: Dict[str, int] = {}

        for item in raw_items_data:
            item_id = item.get("apparatus_id", f"FHR_{len(extracted_list)+1:03d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            atype_val = item.get("apparatus_type", parsed["apparatus_type"])
            if isinstance(atype_val, str):
                try:
                    atype = FireApparatusType(atype_val)
                except ValueError:
                    atype = FireApparatusType.FIXED_FIRE_HOSE_REEL
            else:
                atype = atype_val

            mtype_val = item.get("mounting_type", parsed["mounting_type"])
            if isinstance(mtype_val, str):
                try:
                    mtype = MountingEnclosureType(mtype_val)
                except ValueError:
                    mtype = MountingEnclosureType.RECESSED_WALL_CABINET
            else:
                mtype = mtype_val

            h_len = float(item.get("hose_length_m", parsed["hose_length_m"]))
            h_dia = float(item.get("hose_diameter_mm", parsed["hose_diameter_mm"]))
            v_dia = float(item.get("valve_diameter_mm", parsed["valve_diameter_mm"]))
            inlets = int(item.get("inlet_ways_count", parsed["inlet_ways_count"]))

            spec = FireApparatusSpec(
                apparatus_id=item_id,
                apparatus_type=atype,
                mounting_type=mtype,
                location_point=snapped_pt,
                hose_length_m=h_len,
                hose_diameter_mm=h_dia,
                valve_diameter_mm=v_dia,
                inlet_ways_count=inlets,
                level_id=item.get("level_id", default_level),
                host_wall_id=item.get("host_wall_id"),
                source_callout=callout,
            )
            extracted_list.append(spec)

            if atype in (FireApparatusType.FIXED_FIRE_HOSE_REEL, FireApparatusType.SWINGING_ARM_FIRE_HOSE_REEL):
                tot_fhr += 1
            elif atype in (FireApparatusType.WET_RISER_LANDING_VALVE, FireApparatusType.DRY_RISER_LANDING_VALVE):
                tot_lv += 1
            elif atype == FireApparatusType.EXTERNAL_BREECHING_INLET:
                tot_inlet += 1

            t_key = atype.value
            cnt_by_type[t_key] = cnt_by_type.get(t_key, 0) + 1

            m_key = mtype.value
            cnt_by_mount[m_key] = cnt_by_mount.get(m_key, 0) + 1

        quantities = FireApparatusQuantities(
            total_apparatus_count=len(extracted_list),
            total_hose_reels_count=tot_fhr,
            total_landing_valves_count=tot_lv,
            total_breeching_inlets_count=tot_inlet,
            count_by_type=cnt_by_type,
            count_by_mounting=cnt_by_mount,
        )

        return FireApparatusExtractionResult(
            apparatus_list=extracted_list,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceFireHoseReelBoosterRiserShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
