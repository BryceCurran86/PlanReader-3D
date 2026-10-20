"""
pb_source_auto_sliding_entrance_door_shadow.py

Authoritative shadow-mode extraction and architectural takeoff for automatic sliding entrance doors,
telescopic operators, microwave sensors, and pocket barrier rails.

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


class AutomaticDoorType(str, Enum):
    BI_PARTING_SLIDING_DOOR = "BI_PARTING_SLIDING_DOOR"
    SINGLE_SLIDE_DOOR = "SINGLE_SLIDE_DOOR"
    TELESCOPIC_SLIDING_DOOR = "TELESCOPIC_SLIDING_DOOR"
    AUTOMATIC_REVOLVING_DOOR = "AUTOMATIC_REVOLVING_DOOR"
    AUTOMATIC_SWING_OPERATOR = "AUTOMATIC_SWING_OPERATOR"


class ActivationSensorType(str, Enum):
    RADAR_MICROWAVE_AND_IR = "RADAR_MICROWAVE_AND_IR"
    PUSH_PAD_ACTUATOR = "PUSH_PAD_ACTUATOR"
    ACCESS_CONTROL_READER = "ACCESS_CONTROL_READER"


@dataclass
class AutomaticDoorSpec:
    door_id: str
    door_type: AutomaticDoorType = AutomaticDoorType.BI_PARTING_SLIDING_DOOR
    location_point: Tuple[float, float] = (0.0, 0.0)
    clear_width_mm: float = 2000.0
    clear_height_mm: float = 2400.0
    frame_width_mm: float = 4200.0
    frame_height_mm: float = 2600.0
    active_leaves_count: int = 2
    fixed_sidelites_count: int = 2
    sensor_type: ActivationSensorType = ActivationSensorType.RADAR_MICROWAVE_AND_IR
    barrier_rails_count: int = 2
    level_id: str = "L01"
    host_wall_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class AutomaticDoorQuantities:
    total_doors_count: int = 0
    total_clear_area_m2: float = 0.0
    total_frame_elevation_area_m2: float = 0.0
    total_active_leaves_count: int = 0
    total_barrier_rails_count: int = 0
    doors_by_type: Dict[str, int] = field(default_factory=dict)
    doors_by_sensor: Dict[str, int] = field(default_factory=dict)


@dataclass
class AutomaticDoorExtractionResult:
    doors: List[AutomaticDoorSpec] = field(default_factory=list)
    quantities: AutomaticDoorQuantities = field(default_factory=AutomaticDoorQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceAutomaticSlidingEntranceDoorShadowAuthority:
    """Authoritative shadow evaluator for commercial automatic sliding entrance doors."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses automatic sliding door schedule callouts.
        Example strings:
          - "BI-PARTING AUTOMATIC SLIDING DOOR 2000x2400 CLEAR OP W/ DUAL MICROWAVE/IR SENSORS & 2x BARRIER RAILS"
          - "SINGLE SLIDE AUTO DOOR 1200x2200 CLEAR OP"
          - "4-LEAF TELESCOPIC AUTOMATIC SLIDING DOOR 3000x2500 CLEAR"
          - "3-WING AUTOMATIC REVOLVING DOOR 2400mm DIA"
          - "AUTOMATIC SWING OPERATOR ON DOOR D-104"
        """
        clean = text.upper()
        res = {
            "door_type": AutomaticDoorType.BI_PARTING_SLIDING_DOOR,
            "clear_width_mm": 2000.0,
            "clear_height_mm": 2400.0,
            "frame_width_mm": 4200.0,
            "frame_height_mm": 2600.0,
            "active_leaves_count": 2,
            "fixed_sidelites_count": 2,
            "sensor_type": ActivationSensorType.RADAR_MICROWAVE_AND_IR,
            "barrier_rails_count": 2,
        }

        # Typology
        if "REVOLVING" in clean:
            res["door_type"] = AutomaticDoorType.AUTOMATIC_REVOLVING_DOOR
            res["active_leaves_count"] = 3
            res["fixed_sidelites_count"] = 0
            res["barrier_rails_count"] = 0
        elif "TELESCOPIC" in clean:
            res["door_type"] = AutomaticDoorType.TELESCOPIC_SLIDING_DOOR
            res["active_leaves_count"] = 4 if "4-LEAF" in clean or "4 LEAF" in clean else 2
            res["fixed_sidelites_count"] = 2
        elif "SWING" in clean and "SLID" not in clean:
            res["door_type"] = AutomaticDoorType.AUTOMATIC_SWING_OPERATOR
            res["active_leaves_count"] = 1
            res["fixed_sidelites_count"] = 0
            res["barrier_rails_count"] = 0
        elif "SINGLE" in clean or "SINGLE SLIDE" in clean:
            res["door_type"] = AutomaticDoorType.SINGLE_SLIDE_DOOR
            res["active_leaves_count"] = 1
            res["fixed_sidelites_count"] = 1
            res["barrier_rails_count"] = 1
        else:
            res["door_type"] = AutomaticDoorType.BI_PARTING_SLIDING_DOOR
            res["active_leaves_count"] = 2
            res["fixed_sidelites_count"] = 2
            res["barrier_rails_count"] = 2

        # Sensor type
        if "PUSH PAD" in clean or "PUSH BUTTON" in clean:
            res["sensor_type"] = ActivationSensorType.PUSH_PAD_ACTUATOR
        elif "ACCESS CONTROL" in clean or "CARD READER" in clean:
            res["sensor_type"] = ActivationSensorType.ACCESS_CONTROL_READER
        else:
            res["sensor_type"] = ActivationSensorType.RADAR_MICROWAVE_AND_IR

        # Dimensions: 2000x2400, 1200x2200, 3000x2500
        dim_match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', clean)
        if dim_match:
            try:
                w = float(dim_match.group(1))
                h = float(dim_match.group(2))
                res["clear_width_mm"] = w
                res["clear_height_mm"] = h
            except ValueError:
                pass

        # Frame width/height derivation if not given
        if res["door_type"] == AutomaticDoorType.BI_PARTING_SLIDING_DOOR:
            res["frame_width_mm"] = res["clear_width_mm"] * 2.0 + 200.0
            res["frame_height_mm"] = res["clear_height_mm"] + 200.0
        elif res["door_type"] == AutomaticDoorType.SINGLE_SLIDE_DOOR:
            res["frame_width_mm"] = res["clear_width_mm"] * 2.0 + 100.0
            res["frame_height_mm"] = res["clear_height_mm"] + 200.0
        elif res["door_type"] == AutomaticDoorType.TELESCOPIC_SLIDING_DOOR:
            res["frame_width_mm"] = res["clear_width_mm"] * 1.5 + 200.0
            res["frame_height_mm"] = res["clear_height_mm"] + 200.0
        else:
            res["frame_width_mm"] = res["clear_width_mm"]
            res["frame_height_mm"] = res["clear_height_mm"]

        # Barrier rails count
        br_match = re.search(r'(\d+)\s*[xX]?\s*BARRIER\s*RAIL', clean)
        if br_match:
            try:
                res["barrier_rails_count"] = int(br_match.group(1))
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
    def evaluate_doors(
        cls,
        raw_doors_data: List[Dict[str, any]],
        default_level: str = "L01"
    ) -> AutomaticDoorExtractionResult:
        """
        Authoritative shadow extraction for automatic sliding entrance doors.
        """
        extracted_doors: List[AutomaticDoorSpec] = []
        tot_clear_area = 0.0
        tot_frame_area = 0.0
        tot_leaves = 0
        tot_rails = 0

        doors_by_type_dict: Dict[str, int] = {}
        doors_by_sens_dict: Dict[str, int] = {}

        for item in raw_doors_data:
            door_id = item.get("door_id", f"AD_{len(extracted_doors)+1:02d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            dtype_val = item.get("door_type", parsed["door_type"])
            if isinstance(dtype_val, str):
                try:
                    dtype = AutomaticDoorType(dtype_val)
                except ValueError:
                    dtype = AutomaticDoorType.BI_PARTING_SLIDING_DOOR
            else:
                dtype = dtype_val

            stype_val = item.get("sensor_type", parsed["sensor_type"])
            if isinstance(stype_val, str):
                try:
                    stype = ActivationSensorType(stype_val)
                except ValueError:
                    stype = ActivationSensorType.RADAR_MICROWAVE_AND_IR
            else:
                stype = stype_val

            cw_mm = float(item.get("clear_width_mm", parsed["clear_width_mm"]))
            ch_mm = float(item.get("clear_height_mm", parsed["clear_height_mm"]))
            fw_mm = float(item.get("frame_width_mm", parsed["frame_width_mm"]))
            fh_mm = float(item.get("frame_height_mm", parsed["frame_height_mm"]))
            lvs_cnt = int(item.get("active_leaves_count", parsed["active_leaves_count"]))
            sides_cnt = int(item.get("fixed_sidelites_count", parsed["fixed_sidelites_count"]))
            rails_cnt = int(item.get("barrier_rails_count", parsed["barrier_rails_count"]))

            clear_m2 = round((cw_mm / 1000.0) * (ch_mm / 1000.0), 4)
            frame_m2 = round((fw_mm / 1000.0) * (fh_mm / 1000.0), 4)

            spec = AutomaticDoorSpec(
                door_id=door_id,
                door_type=dtype,
                location_point=snapped_pt,
                clear_width_mm=cw_mm,
                clear_height_mm=ch_mm,
                frame_width_mm=fw_mm,
                frame_height_mm=fh_mm,
                active_leaves_count=lvs_cnt,
                fixed_sidelites_count=sides_cnt,
                sensor_type=stype,
                barrier_rails_count=rails_cnt,
                level_id=item.get("level_id", default_level),
                host_wall_id=item.get("host_wall_id"),
                source_callout=callout,
            )
            extracted_doors.append(spec)

            tot_clear_area += clear_m2
            tot_frame_area += frame_m2
            tot_leaves += lvs_cnt
            tot_rails += rails_cnt

            t_key = dtype.value
            doors_by_type_dict[t_key] = doors_by_type_dict.get(t_key, 0) + 1

            s_key = stype.value
            doors_by_sens_dict[s_key] = doors_by_sens_dict.get(s_key, 0) + 1

        quantities = AutomaticDoorQuantities(
            total_doors_count=len(extracted_doors),
            total_clear_area_m2=round(tot_clear_area, 4),
            total_frame_elevation_area_m2=round(tot_frame_area, 4),
            total_active_leaves_count=tot_leaves,
            total_barrier_rails_count=tot_rails,
            doors_by_type=doors_by_type_dict,
            doors_by_sensor=doors_by_sens_dict,
        )

        return AutomaticDoorExtractionResult(
            doors=extracted_doors,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceAutomaticSlidingEntranceDoorShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
