"""
pb_source_purlin_cleat_fly_brace_shadow.py

Authoritative shadow-mode extraction and structural takeoff for purlin cleats,
rafter connections, bolt sets, and diagonal fly bracing assemblies.

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


class PurlinCleatType(str, Enum):
    STANDARD_ANGLE_CLEAT = "STANDARD_ANGLE_CLEAT"
    FORMED_PLATE_CLEAT = "FORMED_PLATE_CLEAT"
    CONTINUOUS_LAP_CLEAT = "CONTINUOUS_LAP_CLEAT"


class FlyBracingType(str, Enum):
    SINGLE_ANGLE_FLY_BRACE = "SINGLE_ANGLE_FLY_BRACE"
    DOUBLE_ANGLE_FLY_BRACE = "DOUBLE_ANGLE_FLY_BRACE"
    NO_FLY_BRACE = "NO_FLY_BRACE"


@dataclass
class PurlinConnectionSpec:
    connection_id: str
    cleat_type: PurlinCleatType = PurlinCleatType.STANDARD_ANGLE_CLEAT
    fly_bracing_type: FlyBracingType = FlyBracingType.SINGLE_ANGLE_FLY_BRACE
    location_point: Tuple[float, float] = (0.0, 0.0)
    purlin_profile: str = "Z200"
    cleat_dimensions: str = "150x100x8"
    bolts_count: int = 2
    bolt_size: str = "M12"
    fly_brace_profile: str = "50x50x5 EA"
    fly_brace_length_m: float = 1.2
    level_id: str = "ROOF"
    rafter_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class PurlinConnectionQuantities:
    total_connections_count: int = 0
    total_cleats_count: int = 0
    total_bolts_count: int = 0
    total_fly_braces_count: int = 0
    total_fly_brace_length_meters: float = 0.0
    connections_by_cleat_type: Dict[str, int] = field(default_factory=dict)
    connections_by_fly_brace: Dict[str, int] = field(default_factory=dict)


@dataclass
class PurlinConnectionExtractionResult:
    connections: List[PurlinConnectionSpec] = field(default_factory=list)
    quantities: PurlinConnectionQuantities = field(default_factory=PurlinConnectionQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourcePurlinCleatFlyBraceShadowAuthority:
    """Authoritative shadow evaluator for purlin cleat connections and fly bracing."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses purlin cleat and fly bracing connection callouts.
        Example strings:
          - "Z200 PURLIN CLEAT 150x100x8 W/ 2x M12 BOLTS & 50x50x5 EA FLY BRACE"
          - "Z250 FORMED PLATE CLEAT W/ 2x M16 BOLTS DOUBLE FLY BRACE"
          - "C150 ANGLE CLEAT W/ 2x M12 BOLTS NO FLY BRACE"
          - "CONTINUOUS LAP CLEAT Z200"
        """
        clean = text.upper()
        res = {
            "cleat_type": PurlinCleatType.STANDARD_ANGLE_CLEAT,
            "fly_bracing_type": FlyBracingType.SINGLE_ANGLE_FLY_BRACE,
            "purlin_profile": "Z200",
            "cleat_dimensions": "150x100x8",
            "bolts_count": 2,
            "bolt_size": "M12",
            "fly_brace_profile": "50x50x5 EA",
            "fly_brace_length_m": 1.2,
        }

        # Cleat Typology
        if "FORMED" in clean or "PLATE CLEAT" in clean:
            res["cleat_type"] = PurlinCleatType.FORMED_PLATE_CLEAT
        elif "LAP" in clean or "CONTINUOUS" in clean:
            res["cleat_type"] = PurlinCleatType.CONTINUOUS_LAP_CLEAT
        else:
            res["cleat_type"] = PurlinCleatType.STANDARD_ANGLE_CLEAT

        # Fly Bracing Typology
        if "NO FLY" in clean or "WITHOUT FLY" in clean:
            res["fly_bracing_type"] = FlyBracingType.NO_FLY_BRACE
            res["fly_brace_length_m"] = 0.0
        elif "DOUBLE FLY" in clean:
            res["fly_bracing_type"] = FlyBracingType.DOUBLE_ANGLE_FLY_BRACE
            res["fly_brace_length_m"] = 2.4
        elif "FLY BRACE" in clean or "FLY" in clean:
            res["fly_bracing_type"] = FlyBracingType.SINGLE_ANGLE_FLY_BRACE
            res["fly_brace_length_m"] = 1.2
        else:
            res["fly_bracing_type"] = FlyBracingType.NO_FLY_BRACE
            res["fly_brace_length_m"] = 0.0

        # Purlin profile: Z150, Z200, Z250, C150, C200, C250
        prof_match = re.search(r'\b([ZC]\d{3})\b', clean)
        if prof_match:
            res["purlin_profile"] = prof_match.group(1)

        # Cleat dimensions: 150x100x8, 100x75x6
        dim_match = re.search(r'(\d{2,3}[xX]\d{2,3}[xX]\d{1,2})', clean)
        if dim_match:
            res["cleat_dimensions"] = dim_match.group(1).lower()

        # Bolts count: 2x M12, 4x M16, 2 BOLTS
        b_cnt_match = re.search(r'(\d+)\s*[xX]?\s*(?:M\d{2}|BOLTS?)', clean)
        if b_cnt_match:
            try:
                res["bolts_count"] = int(b_cnt_match.group(1))
            except ValueError:
                pass

        # Bolt size: M12, M16, M20
        b_size_match = re.search(r'\b(M\d{2})\b', clean)
        if b_size_match:
            res["bolt_size"] = b_size_match.group(1)

        # Fly brace profile: 50x50x5 EA, 65x65x5 EA
        ea_match = re.search(r'(\d{2})[xX](\d{2})[xX](\d)\s*(?:EA)?', clean)
        if ea_match:
            res["fly_brace_profile"] = f"{ea_match.group(1)}x{ea_match.group(2)}x{ea_match.group(3)} EA"

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @classmethod
    def evaluate_connections(
        cls,
        raw_conns_data: List[Dict[str, any]],
        default_level: str = "ROOF"
    ) -> PurlinConnectionExtractionResult:
        """
        Authoritative shadow extraction for purlin cleats and fly bracing connections.
        """
        extracted_conns: List[PurlinConnectionSpec] = []
        tot_cleats = 0
        tot_bolts = 0
        tot_fly_braces = 0
        tot_fly_m = 0.0

        conns_by_cleat: Dict[str, int] = {}
        conns_by_fly: Dict[str, int] = {}

        for item in raw_conns_data:
            conn_id = item.get("connection_id", f"PC_{len(extracted_conns)+1:03d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            ctype_val = item.get("cleat_type", parsed["cleat_type"])
            if isinstance(ctype_val, str):
                try:
                    ctype = PurlinCleatType(ctype_val)
                except ValueError:
                    ctype = PurlinCleatType.STANDARD_ANGLE_CLEAT
            else:
                ctype = ctype_val

            ftype_val = item.get("fly_bracing_type", parsed["fly_bracing_type"])
            if isinstance(ftype_val, str):
                try:
                    ftype = FlyBracingType(ftype_val)
                except ValueError:
                    ftype = FlyBracingType.NO_FLY_BRACE
            else:
                ftype = ftype_val

            prof = item.get("purlin_profile", parsed["purlin_profile"])
            dims = item.get("cleat_dimensions", parsed["cleat_dimensions"])
            b_cnt = int(item.get("bolts_count", parsed["bolts_count"]))
            b_sz = item.get("bolt_size", parsed["bolt_size"])
            fb_prof = item.get("fly_brace_profile", parsed["fly_brace_profile"])
            fb_len_m = float(item.get("fly_brace_length_m", parsed["fly_brace_length_m"]))

            if ftype == FlyBracingType.SINGLE_ANGLE_FLY_BRACE:
                fly_cnt = 1
            elif ftype == FlyBracingType.DOUBLE_ANGLE_FLY_BRACE:
                fly_cnt = 2
            else:
                fly_cnt = 0
                fb_len_m = 0.0

            spec = PurlinConnectionSpec(
                connection_id=conn_id,
                cleat_type=ctype,
                fly_bracing_type=ftype,
                location_point=snapped_pt,
                purlin_profile=prof,
                cleat_dimensions=dims,
                bolts_count=b_cnt,
                bolt_size=b_sz,
                fly_brace_profile=fb_prof,
                fly_brace_length_m=fb_len_m,
                level_id=item.get("level_id", default_level),
                rafter_id=item.get("rafter_id"),
                source_callout=callout,
            )
            extracted_conns.append(spec)

            tot_cleats += 1
            tot_bolts += b_cnt
            tot_fly_braces += fly_cnt
            tot_fly_m += fb_len_m

            c_key = ctype.value
            conns_by_cleat[c_key] = conns_by_cleat.get(c_key, 0) + 1

            f_key = ftype.value
            conns_by_fly[f_key] = conns_by_fly.get(f_key, 0) + 1

        quantities = PurlinConnectionQuantities(
            total_connections_count=len(extracted_conns),
            total_cleats_count=tot_cleats,
            total_bolts_count=tot_bolts,
            total_fly_braces_count=tot_fly_braces,
            total_fly_brace_length_meters=round(tot_fly_m, 4),
            connections_by_cleat_type=conns_by_cleat,
            connections_by_fly_brace=conns_by_fly,
        )

        return PurlinConnectionExtractionResult(
            connections=extracted_conns,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourcePurlinCleatFlyBraceShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
