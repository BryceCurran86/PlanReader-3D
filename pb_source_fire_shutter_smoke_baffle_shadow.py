"""
pb_source_fire_shutter_smoke_baffle_shadow.py

Authoritative shadow-mode extraction and architectural takeoff for overhead coiling fire shutters,
smoke containment baffles, barrel hoods, and structural guide tracks.

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


class FireShutterType(str, Enum):
    MOTORIZED_FIRE_COILING_SHUTTER = "MOTORIZED_FIRE_COILING_SHUTTER"
    SMOKE_CONTAINMENT_CURTAIN = "SMOKE_CONTAINMENT_CURTAIN"
    OVERHEAD_SECTIONAL_INSULATED_DOOR = "OVERHEAD_SECTIONAL_INSULATED_DOOR"
    COUNTER_FIRE_SHUTTER = "COUNTER_FIRE_SHUTTER"


class ShutterReleaseMechanism(str, Enum):
    FIRE_ALARM_SIGNAL_DROP = "FIRE_ALARM_SIGNAL_DROP"
    FUSIBLE_LINK_GRAVITY_DROP = "FUSIBLE_LINK_GRAVITY_DROP"
    MANUAL_CHAIN_HOIST = "MANUAL_CHAIN_HOIST"


@dataclass
class FireShutterSpec:
    shutter_id: str
    shutter_type: FireShutterType = FireShutterType.MOTORIZED_FIRE_COILING_SHUTTER
    release_mechanism: ShutterReleaseMechanism = ShutterReleaseMechanism.FIRE_ALARM_SIGNAL_DROP
    location_point: Tuple[float, float] = (0.0, 0.0)
    clear_width_mm: float = 4000.0
    clear_height_mm: float = 3000.0
    side_guide_width_mm: float = 100.0
    hood_height_mm: float = 450.0
    fire_rating_frl: str = "-/120/-"
    level_id: str = "L01"
    host_opening_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class FireShutterQuantities:
    total_shutters_count: int = 0
    total_clear_area_m2: float = 0.0
    total_curtain_area_m2: float = 0.0
    total_guide_track_meters: float = 0.0
    total_hood_enclosure_meters: float = 0.0
    shutters_by_type: Dict[str, int] = field(default_factory=dict)
    shutters_by_frl: Dict[str, int] = field(default_factory=dict)


@dataclass
class FireShutterExtractionResult:
    shutters: List[FireShutterSpec] = field(default_factory=list)
    quantities: FireShutterQuantities = field(default_factory=FireShutterQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceFireShutterSmokeBaffleShadowAuthority:
    """Authoritative shadow evaluator for overhead coiling fire shutters and smoke curtains."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses overhead fire shutter schedule callouts.
        Example strings:
          - "4500x3000 MOTORIZED FIRE SHUTTER FRL -/120/- W/ FIRE ALARM AUTO-DESCENT & 450x450 HOOD"
          - "6000x2500 SMOKE CONTAINMENT CURTAIN FRL -/60/-"
          - "2000x1200 COUNTER FIRE SHUTTER FRL -/120/- FUSIBLE LINK"
          - "OVERHEAD SECTIONAL INSULATED DOOR 4000x4500"
        """
        clean = text.upper()
        res = {
            "shutter_type": FireShutterType.MOTORIZED_FIRE_COILING_SHUTTER,
            "release_mechanism": ShutterReleaseMechanism.FIRE_ALARM_SIGNAL_DROP,
            "clear_width_mm": 4000.0,
            "clear_height_mm": 3000.0,
            "side_guide_width_mm": 100.0,
            "hood_height_mm": 450.0,
            "fire_rating_frl": "-/120/-",
        }

        # Typology
        if "SMOKE" in clean or "CURTAIN" in clean:
            res["shutter_type"] = FireShutterType.SMOKE_CONTAINMENT_CURTAIN
            res["fire_rating_frl"] = "-/60/-"
            res["hood_height_mm"] = 300.0
        elif "COUNTER" in clean or "SERVER" in clean:
            res["shutter_type"] = FireShutterType.COUNTER_FIRE_SHUTTER
            res["clear_width_mm"] = 2000.0
            res["clear_height_mm"] = 1200.0
            res["hood_height_mm"] = 300.0
        elif "SECTIONAL" in clean:
            res["shutter_type"] = FireShutterType.OVERHEAD_SECTIONAL_INSULATED_DOOR
            res["fire_rating_frl"] = "NON-RATED"
        else:
            res["shutter_type"] = FireShutterType.MOTORIZED_FIRE_COILING_SHUTTER

        # Release mechanism
        if "FUSIBLE" in clean or "GRAVITY" in clean:
            res["release_mechanism"] = ShutterReleaseMechanism.FUSIBLE_LINK_GRAVITY_DROP
        elif "CHAIN" in clean or "MANUAL" in clean:
            res["release_mechanism"] = ShutterReleaseMechanism.MANUAL_CHAIN_HOIST
        else:
            res["release_mechanism"] = ShutterReleaseMechanism.FIRE_ALARM_SIGNAL_DROP

        # Dimensions: 4500x3000, 6000x2500, etc.
        dim_match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', clean)
        if dim_match:
            try:
                res["clear_width_mm"] = float(dim_match.group(1))
                res["clear_height_mm"] = float(dim_match.group(2))
            except ValueError:
                pass

        # FRL Rating: -/120/-, -/240/-, -/60/-, 2 HR
        frl_match = re.search(r'(-/\d{2,3}/-|\d{2,3}/\d{2,3}/\d{2,3})', clean)
        if frl_match:
            res["fire_rating_frl"] = frl_match.group(1)
        elif "240" in clean:
            res["fire_rating_frl"] = "-/240/-"
        elif "120" in clean or "2 HR" in clean:
            res["fire_rating_frl"] = "-/120/-"
        elif "60" in clean or "1 HR" in clean:
            res["fire_rating_frl"] = "-/60/-"

        # Hood height: 450x450 HOOD, 500mm HOOD
        hood_match = re.search(r'(\d{3})\s*(?:x\d{3})?\s*(?:MM\s*)?HOOD', clean)
        if hood_match:
            try:
                res["hood_height_mm"] = float(hood_match.group(1))
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
    def evaluate_shutters(
        cls,
        raw_shutters_data: List[Dict[str, any]],
        default_level: str = "L01"
    ) -> FireShutterExtractionResult:
        """
        Authoritative shadow extraction for coiling fire shutters and smoke curtains.
        """
        extracted_shutters: List[FireShutterSpec] = []
        tot_clear_area = 0.0
        tot_curtain_area = 0.0
        tot_guide_m = 0.0
        tot_hood_m = 0.0

        shutters_by_type_dict: Dict[str, int] = {}
        shutters_by_frl_dict: Dict[str, int] = {}

        for item in raw_shutters_data:
            shutter_id = item.get("shutter_id", f"FS_{len(extracted_shutters)+1:02d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            stype_val = item.get("shutter_type", parsed["shutter_type"])
            if isinstance(stype_val, str):
                try:
                    stype = FireShutterType(stype_val)
                except ValueError:
                    stype = FireShutterType.MOTORIZED_FIRE_COILING_SHUTTER
            else:
                stype = stype_val

            rmech_val = item.get("release_mechanism", parsed["release_mechanism"])
            if isinstance(rmech_val, str):
                try:
                    rmech = ShutterReleaseMechanism(rmech_val)
                except ValueError:
                    rmech = ShutterReleaseMechanism.FIRE_ALARM_SIGNAL_DROP
            else:
                rmech = rmech_val

            cw_mm = float(item.get("clear_width_mm", parsed["clear_width_mm"]))
            ch_mm = float(item.get("clear_height_mm", parsed["clear_height_mm"]))
            gw_mm = float(item.get("side_guide_width_mm", parsed["side_guide_width_mm"]))
            hh_mm = float(item.get("hood_height_mm", parsed["hood_height_mm"]))
            frl = item.get("fire_rating_frl", parsed["fire_rating_frl"])

            clear_m2 = round((cw_mm / 1000.0) * (ch_mm / 1000.0), 4)
            curtain_w_m = (cw_mm + 2.0 * gw_mm) / 1000.0
            curtain_h_m = (ch_mm + hh_mm) / 1000.0
            curtain_m2 = round(curtain_w_m * curtain_h_m, 4)

            guide_m = round(2.0 * (ch_mm / 1000.0), 4)
            hood_m = round(curtain_w_m, 4)

            spec = FireShutterSpec(
                shutter_id=shutter_id,
                shutter_type=stype,
                release_mechanism=rmech,
                location_point=snapped_pt,
                clear_width_mm=cw_mm,
                clear_height_mm=ch_mm,
                side_guide_width_mm=gw_mm,
                hood_height_mm=hh_mm,
                fire_rating_frl=frl,
                level_id=item.get("level_id", default_level),
                host_opening_id=item.get("host_opening_id"),
                source_callout=callout,
            )
            extracted_shutters.append(spec)

            tot_clear_area += clear_m2
            tot_curtain_area += curtain_m2
            tot_guide_m += guide_m
            tot_hood_m += hood_m

            t_key = stype.value
            shutters_by_type_dict[t_key] = shutters_by_type_dict.get(t_key, 0) + 1

            shutters_by_frl_dict[frl] = shutters_by_frl_dict.get(frl, 0) + 1

        quantities = FireShutterQuantities(
            total_shutters_count=len(extracted_shutters),
            total_clear_area_m2=round(tot_clear_area, 4),
            total_curtain_area_m2=round(tot_curtain_area, 4),
            total_guide_track_meters=round(tot_guide_m, 4),
            total_hood_enclosure_meters=round(tot_hood_m, 4),
            shutters_by_type=shutters_by_type_dict,
            shutters_by_frl=shutters_by_frl_dict,
        )

        return FireShutterExtractionResult(
            shutters=extracted_shutters,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceFireShutterSmokeBaffleShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
