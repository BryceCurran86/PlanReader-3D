"""
pb_source_firestop_collar_wrap_shadow.py

Authoritative shadow-mode extraction and passive fire protection takeoff for penetration
firestop collars, cast-in slab collars, intumescent pipe wraps, and transit pillow seals.

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


class FirestopDeviceType(str, Enum):
    CAST_IN_COLLAR = "CAST_IN_COLLAR"
    SURFACE_FIRE_COLLAR = "SURFACE_FIRE_COLLAR"
    INTUMESCENT_PIPE_WRAP = "INTUMESCENT_PIPE_WRAP"
    FIRE_PILLOW_TRANSIT = "FIRE_PILLOW_TRANSIT"


class PipeMaterialType(str, Enum):
    PVC_DWV = "PVC_DWV"
    HDPE_DRAIN = "HDPE_DRAIN"
    POLYPROPYLENE = "POLYPROPYLENE"
    COPPER_INSULATED = "COPPER_INSULATED"
    ELECTRICAL_CABLES = "ELECTRICAL_CABLES"


class PenetrationOrientation(str, Enum):
    FLOOR_PENETRATION = "FLOOR_PENETRATION"
    WALL_PENETRATION = "WALL_PENETRATION"
    CEILING_PENETRATION = "CEILING_PENETRATION"


@dataclass
class FirestopDeviceSpec:
    device_id: str
    device_type: FirestopDeviceType = FirestopDeviceType.CAST_IN_COLLAR
    pipe_material: PipeMaterialType = PipeMaterialType.PVC_DWV
    orientation: PenetrationOrientation = PenetrationOrientation.FLOOR_PENETRATION
    center_point: Tuple[float, float] = (0.0, 0.0)
    nominal_pipe_dia_mm: float = 100.0
    fire_rating_hours: int = 2
    collar_height_mm: float = 60.0
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class FirestopTakeoffQuantities:
    total_devices_count: int = 0
    devices_by_type: Dict[str, int] = field(default_factory=dict)
    devices_by_diameter: Dict[str, int] = field(default_factory=dict)
    devices_by_fire_rating: Dict[str, int] = field(default_factory=dict)
    floor_penetrations_count: int = 0
    wall_penetrations_count: int = 0


@dataclass
class FirestopExtractionResult:
    devices: List[FirestopDeviceSpec] = field(default_factory=list)
    quantities: FirestopTakeoffQuantities = field(default_factory=FirestopTakeoffQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceFirestopCollarWrapShadowAuthority:
    """Authoritative shadow evaluator for passive firestop collar and wrap penetrations."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses firestop callouts and annotations.
        Example strings:
          - "100mm DIA PVC CAST-IN SLAB FIRE COLLAR 2-HR FRL -/120/120"
          - "65mm RETROFIT SURFACE FIRE COLLAR HDPE WALL PENETRATION 3-HR"
          - "50mm INTUMESCENT PIPE WRAP 2HR"
        """
        clean = text.upper()
        res = {
            "device_type": FirestopDeviceType.CAST_IN_COLLAR,
            "pipe_material": PipeMaterialType.PVC_DWV,
            "orientation": PenetrationOrientation.FLOOR_PENETRATION,
            "nominal_pipe_dia_mm": 100.0,
            "fire_rating_hours": 2,
        }

        # Device Type
        if "CAST-IN" in clean or "CAST IN" in clean or "PRE-CAST" in clean:
            res["device_type"] = FirestopDeviceType.CAST_IN_COLLAR
        elif "SURFACE" in clean or "RETROFIT" in clean or "BOLT-ON" in clean:
            res["device_type"] = FirestopDeviceType.SURFACE_FIRE_COLLAR
        elif "WRAP" in clean or "ANNULAR" in clean:
            res["device_type"] = FirestopDeviceType.INTUMESCENT_PIPE_WRAP
        elif "PILLOW" in clean or "TRANSIT" in clean:
            res["device_type"] = FirestopDeviceType.FIRE_PILLOW_TRANSIT
        else:
            res["device_type"] = FirestopDeviceType.CAST_IN_COLLAR

        # Pipe Material
        if "HDPE" in clean or "POLYETHYLENE" in clean:
            res["pipe_material"] = PipeMaterialType.HDPE_DRAIN
        elif "POLYPROPYLENE" in clean or "PP-R" in clean or "PP " in clean:
            res["pipe_material"] = PipeMaterialType.POLYPROPYLENE
        elif "COPPER" in clean or "REFRIGERANT" in clean:
            res["pipe_material"] = PipeMaterialType.COPPER_INSULATED
        elif "CABLE" in clean or "CONDUIT" in clean:
            res["pipe_material"] = PipeMaterialType.ELECTRICAL_CABLES
        else:
            res["pipe_material"] = PipeMaterialType.PVC_DWV

        # Orientation
        if "WALL" in clean or "PARTITION" in clean:
            res["orientation"] = PenetrationOrientation.WALL_PENETRATION
        elif "CEILING" in clean:
            res["orientation"] = PenetrationOrientation.CEILING_PENETRATION
        else:
            res["orientation"] = PenetrationOrientation.FLOOR_PENETRATION

        # Nominal Pipe Diameter: 100mm, 50mm, 65mm, 150mm
        dia_match = re.search(r'(\d{2,3})\s*MM\b', clean)
        if dia_match:
            try:
                d = float(dia_match.group(1))
                if 20.0 <= d <= 500.0:
                    res["nominal_pipe_dia_mm"] = d
            except ValueError:
                pass

        # Fire rating: 2-HR, 3-HR, 4-HR, -/120/120, -/180/180
        frl_match = re.search(r'-\s*/\s*(\d{2,3})\s*/\s*\d{2,3}', clean)
        if frl_match:
            try:
                mins = int(frl_match.group(1))
                res["fire_rating_hours"] = max(1, round(mins / 60))
            except ValueError:
                pass
        else:
            hr_match = re.search(r'(\d+)\s*(?:-|HR|HOUR)', clean)
            if hr_match:
                try:
                    h = int(hr_match.group(1))
                    if 1 <= h <= 4:
                        res["fire_rating_hours"] = h
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
    def evaluate_firestops(
        cls,
        raw_firestop_data: List[Dict[str, any]],
        default_level: str = "L01"
    ) -> FirestopExtractionResult:
        """
        Authoritative shadow extraction for penetration firestop collars and wraps.
        """
        extracted_devices: List[FirestopDeviceSpec] = []
        by_type: Dict[str, int] = {}
        by_dia: Dict[str, int] = {}
        by_rating: Dict[str, int] = {}
        floor_cnt = 0
        wall_cnt = 0

        for item in raw_firestop_data:
            dev_id = item.get("device_id", f"FS_{len(extracted_devices)+1:03d}")
            raw_center = item.get("center_point", (0.0, 0.0))
            snapped_center = cls.snap_point(raw_center)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            dev_type_val = item.get("device_type", parsed["device_type"])
            if isinstance(dev_type_val, str):
                try:
                    dev_type = FirestopDeviceType(dev_type_val)
                except ValueError:
                    dev_type = FirestopDeviceType.CAST_IN_COLLAR
            else:
                dev_type = dev_type_val

            pipe_mat_val = item.get("pipe_material", parsed["pipe_material"])
            if isinstance(pipe_mat_val, str):
                try:
                    pipe_mat = PipeMaterialType(pipe_mat_val)
                except ValueError:
                    pipe_mat = PipeMaterialType.PVC_DWV
            else:
                pipe_mat = pipe_mat_val

            orient_val = item.get("orientation", parsed["orientation"])
            if isinstance(orient_val, str):
                try:
                    orient = PenetrationOrientation(orient_val)
                except ValueError:
                    orient = PenetrationOrientation.FLOOR_PENETRATION
            else:
                orient = orient_val

            pipe_dia = float(item.get("nominal_pipe_dia_mm", parsed["nominal_pipe_dia_mm"]))
            rating_hrs = int(item.get("fire_rating_hours", parsed["fire_rating_hours"]))

            spec = FirestopDeviceSpec(
                device_id=dev_id,
                device_type=dev_type,
                pipe_material=pipe_mat,
                orientation=orient,
                center_point=snapped_center,
                nominal_pipe_dia_mm=pipe_dia,
                fire_rating_hours=rating_hrs,
                collar_height_mm=float(item.get("collar_height_mm", 60.0)),
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_devices.append(spec)

            t_key = dev_type.value
            by_type[t_key] = by_type.get(t_key, 0) + 1

            dia_key = f"{int(pipe_dia)}mm"
            by_dia[dia_key] = by_dia.get(dia_key, 0) + 1

            rating_key = f"{rating_hrs}HR"
            by_rating[rating_key] = by_rating.get(rating_key, 0) + 1

            if orient == PenetrationOrientation.FLOOR_PENETRATION:
                floor_cnt += 1
            elif orient == PenetrationOrientation.WALL_PENETRATION:
                wall_cnt += 1

        quantities = FirestopTakeoffQuantities(
            total_devices_count=len(extracted_devices),
            devices_by_type=by_type,
            devices_by_diameter=by_dia,
            devices_by_fire_rating=by_rating,
            floor_penetrations_count=floor_cnt,
            wall_penetrations_count=wall_cnt,
        )

        return FirestopExtractionResult(
            devices=extracted_devices,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceFirestopCollarWrapShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
