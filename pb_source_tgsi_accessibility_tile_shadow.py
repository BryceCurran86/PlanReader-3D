"""
pb_source_tgsi_accessibility_tile_shadow.py

Authoritative shadow-mode extraction and accessibility takeoff for Tactile Ground Surface
Indicators (TGSIs): hazard warning cones, directional guidance bars, discrete stainless studs,
and integrated surface-mounted tiles.

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
STUDS_PER_SQUARE_METER: int = 400
TILE_MODULE_AREA_M2: float = 0.09  # standard 300mm x 300mm tile


class TGSIType(str, Enum):
    HAZARD_WARNING = "HAZARD_WARNING"
    DIRECTIONAL_LEADING = "DIRECTIONAL_LEADING"


class TGSIFormat(str, Enum):
    INDIVIDUAL_STUDS = "INDIVIDUAL_STUDS"
    INTEGRATED_TILE = "INTEGRATED_TILE"
    PEEL_AND_STICK_MAT = "PEEL_AND_STICK_MAT"


class TGSILocationContext(str, Enum):
    STAIR_TOP = "STAIR_TOP"
    STAIR_BOTTOM = "STAIR_BOTTOM"
    RAMP_TOP_BOTTOM = "RAMP_TOP_BOTTOM"
    ESCALATOR_APPROACH = "ESCALATOR_APPROACH"
    PEDESTRIAN_CROSSING = "PEDESTRIAN_CROSSING"
    GENERAL_ACCESSIBILITY = "GENERAL_ACCESSIBILITY"


@dataclass
class TGSIZoneSpec:
    zone_id: str
    indicator_type: TGSIType = TGSIType.HAZARD_WARNING
    indicator_format: TGSIFormat = TGSIFormat.INDIVIDUAL_STUDS
    location_context: TGSILocationContext = TGSILocationContext.STAIR_TOP
    boundary_polygon: List[Tuple[float, float]] = field(default_factory=list)
    width_m: float = 1.0
    depth_m: float = 0.6
    area_m2: float = 0.6
    stud_count: int = 240
    tile_units_count: int = 0
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class TGSIAccessibilityQuantities:
    total_zones_count: int = 0
    total_area_m2: float = 0.0
    hazard_area_m2: float = 0.0
    directional_area_m2: float = 0.0
    total_individual_studs_count: int = 0
    total_tile_units_count: int = 0
    zones_by_context: Dict[str, int] = field(default_factory=dict)


@dataclass
class TGSIAccessibilityExtractionResult:
    zones: List[TGSIZoneSpec] = field(default_factory=list)
    quantities: TGSIAccessibilityQuantities = field(default_factory=TGSIAccessibilityQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceTGSIAccessibilityTileShadowAuthority:
    """Authoritative shadow evaluator for tactile indicators and accessibility pads."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses TGSI callouts and annotations.
        Example strings:
          - "600x1200 HAZARD WARNING TACTILE PADS DISCRETE STAINLESS STEEL STUDS AT TOP OF STAIRS"
          - "DIRECTIONAL LEADING TACTILE TILES 300x300 COMPOSITE"
          - "TACTILE GROUND SURFACE INDICATORS TO AS1428.4 RAMP APPROACH"
        """
        clean = text.upper()
        res = {
            "indicator_type": TGSIType.HAZARD_WARNING,
            "indicator_format": TGSIFormat.INDIVIDUAL_STUDS,
            "location_context": TGSILocationContext.GENERAL_ACCESSIBILITY,
            "width_m": 1.0,
            "depth_m": 0.6,
        }

        # Indicator profile type
        if "DIRECTIONAL" in clean or "LEADING" in clean or "BARS" in clean or "STRIP" in clean:
            res["indicator_type"] = TGSIType.DIRECTIONAL_LEADING
        else:
            res["indicator_type"] = TGSIType.HAZARD_WARNING

        # Format: avoid matching "TACTILE" when searching for "TILE"
        if re.search(r'\bTILE[S]?\b', clean) or "PAVER" in clean or "COMPOSITE" in clean or "PORCELAIN" in clean or "CERAMIC" in clean:
            res["indicator_format"] = TGSIFormat.INTEGRATED_TILE
        elif "MAT" in clean or "STICK" in clean or "PEEL" in clean:
            res["indicator_format"] = TGSIFormat.PEEL_AND_STICK_MAT
        else:
            res["indicator_format"] = TGSIFormat.INDIVIDUAL_STUDS

        # Location context
        if "STAIR" in clean and ("TOP" in clean or "LANDING" in clean):
            res["location_context"] = TGSILocationContext.STAIR_TOP
        elif "STAIR" in clean and ("BOTTOM" in clean or "BASE" in clean or "GROUND" in clean):
            res["location_context"] = TGSILocationContext.STAIR_BOTTOM
        elif "STAIR" in clean:
            res["location_context"] = TGSILocationContext.STAIR_TOP
        elif "RAMP" in clean:
            res["location_context"] = TGSILocationContext.RAMP_TOP_BOTTOM
        elif "ESCALATOR" in clean:
            res["location_context"] = TGSILocationContext.ESCALATOR_APPROACH
        elif "CROSSING" in clean or "CURB" in clean or "KERB" in clean:
            res["location_context"] = TGSILocationContext.PEDESTRIAN_CROSSING
        else:
            res["location_context"] = TGSILocationContext.GENERAL_ACCESSIBILITY

        # Dimensions: 600x1200 or 1200x600 or 600mm DEEP
        dim_match = re.search(r'(\d{3,4})\s*[xX*]\s*(\d{3,4})', clean)
        if dim_match:
            try:
                d1 = float(dim_match.group(1)) / 1000.0
                d2 = float(dim_match.group(2)) / 1000.0
                # Depth is usually <= 0.9m, width >= 0.6m
                res["depth_m"] = min(d1, d2)
                res["width_m"] = max(d1, d2)
            except ValueError:
                pass
        else:
            deep_match = re.search(r'(\d{3,4})\s*MM\s*DEEP', clean)
            if deep_match:
                try:
                    res["depth_m"] = float(deep_match.group(1)) / 1000.0
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
    def calculate_polygon_area(poly: List[Tuple[float, float]], scale_ratio: float = 0.001) -> float:
        """
        Calculates area in square meters using Shoelace formula.
        scale_ratio converts coordinates to meters (e.g. 0.001 for mm).
        """
        if len(poly) < 3:
            return 0.0
        n = len(poly)
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            xi, yi = poly[i]
            xj, yj = poly[j]
            area += (xi * yj) - (xj * yi)
        area_m2 = abs(area) * 0.5 * (scale_ratio ** 2)
        return round(area_m2, 4)

    @classmethod
    def evaluate_zones(
        cls,
        raw_zone_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> TGSIAccessibilityExtractionResult:
        """
        Authoritative shadow extraction for tactile ground indicators and accessibility pads.
        """
        extracted_zones: List[TGSIZoneSpec] = []
        tot_area = 0.0
        hazard_area = 0.0
        directional_area = 0.0
        tot_studs = 0
        tot_tiles = 0
        by_context: Dict[str, int] = {}

        for item in raw_zone_data:
            zone_id = item.get("zone_id", f"TGSI_{len(extracted_zones)+1:03d}")
            raw_poly = item.get("boundary_polygon", [])
            snapped_poly = [cls.snap_point(pt) for pt in raw_poly]

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            itype_val = item.get("indicator_type", parsed["indicator_type"])
            if isinstance(itype_val, str):
                try:
                    itype = TGSIType(itype_val)
                except ValueError:
                    itype = TGSIType.HAZARD_WARNING
            else:
                itype = itype_val

            iformat_val = item.get("indicator_format", parsed["indicator_format"])
            if isinstance(iformat_val, str):
                try:
                    iformat = TGSIFormat(iformat_val)
                except ValueError:
                    iformat = TGSIFormat.INDIVIDUAL_STUDS
            else:
                iformat = iformat_val

            lcontext_val = item.get("location_context", parsed["location_context"])
            if isinstance(lcontext_val, str):
                try:
                    lcontext = TGSILocationContext(lcontext_val)
                except ValueError:
                    lcontext = TGSILocationContext.GENERAL_ACCESSIBILITY
            else:
                lcontext = lcontext_val

            # Compute area: from polygon if available, else from width * depth
            poly_area = cls.calculate_polygon_area(snapped_poly, scale_ratio)
            if poly_area > 0.0:
                area_m2 = poly_area
                width_m = item.get("width_m", parsed["width_m"])
                depth_m = item.get("depth_m", parsed["depth_m"])
            else:
                width_m = float(item.get("width_m", parsed["width_m"]))
                depth_m = float(item.get("depth_m", parsed["depth_m"]))
                area_m2 = round(width_m * depth_m, 4)

            # Compute stud or tile takeoff
            stud_cnt = 0
            tile_cnt = 0
            if iformat == TGSIFormat.INDIVIDUAL_STUDS:
                stud_cnt = int(round(area_m2 * STUDS_PER_SQUARE_METER))
            elif iformat in (TGSIFormat.INTEGRATED_TILE, TGSIFormat.PEEL_AND_STICK_MAT):
                tile_cnt = int(math.ceil(area_m2 / TILE_MODULE_AREA_M2))

            spec = TGSIZoneSpec(
                zone_id=zone_id,
                indicator_type=itype,
                indicator_format=iformat,
                location_context=lcontext,
                boundary_polygon=snapped_poly,
                width_m=width_m,
                depth_m=depth_m,
                area_m2=area_m2,
                stud_count=stud_cnt,
                tile_units_count=tile_cnt,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_zones.append(spec)

            tot_area += area_m2
            tot_studs += stud_cnt
            tot_tiles += tile_cnt

            if itype == TGSIType.HAZARD_WARNING:
                hazard_area += area_m2
            elif itype == TGSIType.DIRECTIONAL_LEADING:
                directional_area += area_m2

            ctx_key = lcontext.value
            by_context[ctx_key] = by_context.get(ctx_key, 0) + 1

        quantities = TGSIAccessibilityQuantities(
            total_zones_count=len(extracted_zones),
            total_area_m2=round(tot_area, 4),
            hazard_area_m2=round(hazard_area, 4),
            directional_area_m2=round(directional_area, 4),
            total_individual_studs_count=tot_studs,
            total_tile_units_count=tot_tiles,
            zones_by_context=by_context,
        )

        return TGSIAccessibilityExtractionResult(
            zones=extracted_zones,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceTGSIAccessibilityTileShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
