"""
pb_source_sprinkler_head_pipe_shadow.py

Authoritative shadow-mode extraction and hydraulic takeoff for fire sprinkler heads,
concealed pendent covers, upright heads, ESFR warehouse heads, and distribution range pipework.

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


class SprinklerOrientation(str, Enum):
    PENDENT_CONCEALED = "PENDENT_CONCEALED"
    PENDENT_STANDARD = "PENDENT_STANDARD"
    UPRIGHT = "UPRIGHT"
    SIDEWALL_HORIZONTAL = "SIDEWALL_HORIZONTAL"
    ESFR_HIGH_BAY = "ESFR_HIGH_BAY"


@dataclass
class SprinklerHeadSpec:
    head_id: str
    orientation: SprinklerOrientation = SprinklerOrientation.PENDENT_CONCEALED
    location_point: Tuple[float, float] = (0.0, 0.0)
    k_factor_metric: float = 80.0
    temperature_rating_c: int = 68
    is_quick_response: bool = True
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class SprinklerPipeSpec:
    pipe_id: str
    nominal_dia_dn: int = 25
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    is_branch_main: bool = False
    level_id: str = "L01"
    source_callout: str = ""


@dataclass
class SprinklerHydraulicQuantities:
    total_heads_count: int = 0
    heads_by_orientation: Dict[str, int] = field(default_factory=dict)
    heads_by_k_factor: Dict[str, int] = field(default_factory=dict)
    total_pipe_linear_meters: float = 0.0
    pipe_linear_meters_by_dn: Dict[str, float] = field(default_factory=dict)


@dataclass
class SprinklerHydraulicExtractionResult:
    heads: List[SprinklerHeadSpec] = field(default_factory=list)
    pipes: List[SprinklerPipeSpec] = field(default_factory=list)
    quantities: SprinklerHydraulicQuantities = field(default_factory=SprinklerHydraulicQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSprinklerHeadPipeShadowAuthority:
    """Authoritative shadow evaluator for fire sprinkler heads and hydraulic range pipes."""

    @staticmethod
    def parse_head_callout(text: str) -> Dict[str, any]:
        """
        Parses automatic sprinkler head annotations.
        Example strings:
          - "CONCEALED PENDENT SPRINKLER HEAD K80 QR 68C"
          - "UPRIGHT SPRINKLER K115 79C OPEN CEILING"
          - "ESFR PENDENT HEAD K360 93C HIGH BAY"
          - "SIDEWALL SPRINKLER HEAD K80"
        """
        clean = text.upper()
        res = {
            "orientation": SprinklerOrientation.PENDENT_CONCEALED,
            "k_factor_metric": 80.0,
            "temperature_rating_c": 68,
            "is_quick_response": True,
        }

        # Orientation
        if "ESFR" in clean or "EARLY SUPPRESSION" in clean or "HIGH BAY" in clean:
            res["orientation"] = SprinklerOrientation.ESFR_HIGH_BAY
            res["k_factor_metric"] = 360.0
        elif "SIDEWALL" in clean or "HORIZONTAL" in clean:
            res["orientation"] = SprinklerOrientation.SIDEWALL_HORIZONTAL
        elif "UPRIGHT" in clean:
            res["orientation"] = SprinklerOrientation.UPRIGHT
        elif "CONCEALED" in clean or "FLUSH" in clean:
            res["orientation"] = SprinklerOrientation.PENDENT_CONCEALED
        elif "PENDENT" in clean or "DROPPED" in clean:
            res["orientation"] = SprinklerOrientation.PENDENT_STANDARD
        else:
            res["orientation"] = SprinklerOrientation.PENDENT_CONCEALED

        # K-Factor: K80, K115, K160, K202, K360 or imperial K5.6, K8.0, K25.2
        k_match = re.search(r'\bK\s*(\d+(?:\.\d+)?)\b', clean)
        if k_match:
            try:
                k_val = float(k_match.group(1))
                if k_val < 30.0:  # Imperial conversion e.g. 5.6 -> ~80, 8.0 -> ~115
                    res["k_factor_metric"] = round(k_val * 14.28, 1)
                else:
                    res["k_factor_metric"] = k_val
            except ValueError:
                pass

        # Temperature: 68C, 79C, 93C, 141C
        temp_match = re.search(r'(\d{2,3})\s*(?:DEG|°)?\s*C\b', clean)
        if temp_match:
            try:
                t_val = int(temp_match.group(1))
                if 50 <= t_val <= 260:
                    res["temperature_rating_c"] = t_val
            except ValueError:
                pass

        # Quick response
        if "STANDARD RESPONSE" in clean or " SR " in clean:
            res["is_quick_response"] = False
        else:
            res["is_quick_response"] = True

        return res

    @staticmethod
    def parse_pipe_callout(text: str) -> Dict[str, any]:
        """
        Parses sprinkler range pipe annotations.
        Example strings:
          - "DN25 SPRINKLER RANGE PIPE"
          - "DN50 DISTRIBUTION BRANCH MAIN"
          - "DN32 SCHEDULE 40 BLACK STEEL"
        """
        clean = text.upper()
        res = {
            "nominal_dia_dn": 25,
            "is_branch_main": False,
        }

        # Main vs range
        if "MAIN" in clean or "HEADER" in clean:
            res["is_branch_main"] = True

        # Diameter: DN25, DN32, DN40, DN50, DN65, DN80, DN100
        dn_match = re.search(r'\bDN(\d{2,3})\b', clean)
        if dn_match:
            try:
                dn = int(dn_match.group(1))
                if 20 <= dn <= 300:
                    res["nominal_dia_dn"] = dn
            except ValueError:
                pass
        else:
            mm_match = re.search(r'(\d{2,3})\s*MM\b', clean)
            if mm_match:
                try:
                    d = int(mm_match.group(1))
                    if 20 <= d <= 300:
                        res["nominal_dia_dn"] = d
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
    def evaluate_sprinkler_network(
        cls,
        heads_data: List[Dict[str, any]],
        pipes_data: Optional[List[Dict[str, any]]] = None,
        scale_ratio: float = 0.001,
        default_level: str = "L01"
    ) -> SprinklerHydraulicExtractionResult:
        """
        Authoritative shadow extraction for sprinkler heads and distribution range pipework.
        """
        if pipes_data is None:
            pipes_data = []

        extracted_heads: List[SprinklerHeadSpec] = []
        extracted_pipes: List[SprinklerPipeSpec] = []

        heads_by_orient: Dict[str, int] = {}
        heads_by_k: Dict[str, int] = {}

        for item in heads_data:
            head_id = item.get("head_id", f"SH_{len(extracted_heads)+1:03d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_head_callout(callout)

            orient_val = item.get("orientation", parsed["orientation"])
            if isinstance(orient_val, str):
                try:
                    orient = SprinklerOrientation(orient_val)
                except ValueError:
                    orient = SprinklerOrientation.PENDENT_CONCEALED
            else:
                orient = orient_val

            k_val = float(item.get("k_factor_metric", parsed["k_factor_metric"]))
            temp_c = int(item.get("temperature_rating_c", parsed["temperature_rating_c"]))
            qr = bool(item.get("is_quick_response", parsed["is_quick_response"]))

            spec = SprinklerHeadSpec(
                head_id=head_id,
                orientation=orient,
                location_point=snapped_pt,
                k_factor_metric=k_val,
                temperature_rating_c=temp_c,
                is_quick_response=qr,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_heads.append(spec)

            o_key = orient.value
            heads_by_orient[o_key] = heads_by_orient.get(o_key, 0) + 1

            k_key = f"K{int(k_val)}"
            heads_by_k[k_key] = heads_by_k.get(k_key, 0) + 1

        tot_pipe_m = 0.0
        pipe_m_by_dn: Dict[str, float] = {}

        for p_item in pipes_data:
            pipe_id = p_item.get("pipe_id", f"SP_{len(extracted_pipes)+1:03d}")
            raw_pts = p_item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = p_item.get("callout", "")
            parsed_p = cls.parse_pipe_callout(callout)

            dn = int(p_item.get("nominal_dia_dn", parsed_p["nominal_dia_dn"]))
            is_main = bool(p_item.get("is_branch_main", parsed_p["is_branch_main"]))

            pipe_spec = SprinklerPipeSpec(
                pipe_id=pipe_id,
                nominal_dia_dn=dn,
                centerline_points=snapped_pts,
                is_branch_main=is_main,
                level_id=p_item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_pipes.append(pipe_spec)

            p_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            tot_pipe_m += p_len_m

            dn_key = f"DN{dn}"
            pipe_m_by_dn[dn_key] = round(pipe_m_by_dn.get(dn_key, 0.0) + p_len_m, 4)

        quantities = SprinklerHydraulicQuantities(
            total_heads_count=len(extracted_heads),
            heads_by_orientation=heads_by_orient,
            heads_by_k_factor=heads_by_k,
            total_pipe_linear_meters=round(tot_pipe_m, 4),
            pipe_linear_meters_by_dn=pipe_m_by_dn,
        )

        return SprinklerHydraulicExtractionResult(
            heads=extracted_heads,
            pipes=extracted_pipes,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceSprinklerHeadPipeShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
