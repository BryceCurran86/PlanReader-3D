"""
pb_source_bored_pile_pier_shadow.py

Authoritative shadow-mode extraction and geotechnical takeoff for deep foundation systems:
circular bored piers, Continuous Flight Auger (CFA) piles, rock socket keys, and displacement concrete volumes.

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


class PileType(str, Enum):
    BORED_CAST_IN_PLACE = "BORED_CAST_IN_PLACE"
    CONTINUOUS_FLIGHT_AUGER = "CONTINUOUS_FLIGHT_AUGER"
    DRIVEN_PRECAST_CONCRETE = "DRIVEN_PRECAST_CONCRETE"
    STEEL_SCREW_PILE = "STEEL_SCREW_PILE"
    MICROPILE = "MICROPILE"


class GeotechnicalStratum(str, Enum):
    CLAY_SILT = "CLAY_SILT"
    SAND_GRAVEL = "SAND_GRAVEL"
    WEATHERED_ROCK = "WEATHERED_ROCK"
    SOLID_BEDROCK = "SOLID_BEDROCK"


@dataclass
class BoredPileSpec:
    pile_id: str
    pile_type: PileType = PileType.BORED_CAST_IN_PLACE
    center_point: Tuple[float, float] = (0.0, 0.0)
    diameter_mm: float = 0.0
    design_depth_m: float = 8.0
    rock_socket_length_m: float = 0.0
    stratum: GeotechnicalStratum = GeotechnicalStratum.WEATHERED_ROCK
    pile_cap_id: str = ""
    level_id: str = "FOUNDATION"
    source_callout: str = ""


@dataclass
class BoredPileQuantities:
    total_piles_count: int = 0
    total_drilled_linear_meters: float = 0.0
    total_concrete_volume_m3: float = 0.0
    total_rock_socket_meters: float = 0.0
    piles_by_diameter: Dict[str, int] = field(default_factory=dict)
    linear_meters_by_diameter: Dict[str, float] = field(default_factory=dict)
    concrete_volume_by_diameter: Dict[str, float] = field(default_factory=dict)


@dataclass
class BoredPileExtractionResult:
    piles: List[BoredPileSpec] = field(default_factory=list)
    quantities: BoredPileQuantities = field(default_factory=BoredPileQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceBoredPilePierShadowAuthority:
    """Authoritative shadow evaluator for deep foundation piles and bored piers."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses pile schedule annotations and callouts.
        Example strings:
          - "600mm DIA BORED PILE DEPTH=12.0m ROCK SOCKET=1.5m"
          - "P450 CFA PILE 8.5M DEEP"
          - "Ø900 PIER 15M SOCKET 2.0M INTO BEDROCK"
        """
        clean = text.upper()
        res = {
            "pile_type": PileType.BORED_CAST_IN_PLACE,
            "diameter_mm": 0.0,
            "design_depth_m": 8.0,
            "rock_socket_length_m": 0.0,
            "stratum": GeotechnicalStratum.WEATHERED_ROCK,
            "pile_cap_id": "",
        }

        # Type detection
        if "CFA" in clean or "CONTINUOUS FLIGHT" in clean:
            res["pile_type"] = PileType.CONTINUOUS_FLIGHT_AUGER
        elif "PRECAST" in clean or "DRIVEN" in clean:
            res["pile_type"] = PileType.DRIVEN_PRECAST_CONCRETE
        elif "SCREW" in clean or "HELICAL" in clean:
            res["pile_type"] = PileType.STEEL_SCREW_PILE
        elif "MICRO" in clean or "MINI-PILE" in clean:
            res["pile_type"] = PileType.MICROPILE
        else:
            res["pile_type"] = PileType.BORED_CAST_IN_PLACE

        # Diameter detection: Ø600, 600 DIA, 600MM DIA, P600, etc.
        dia_match = re.search(r'(?:[ØP]|\bDIA\s*|\bDIAMETER\s*)?(\d{3,4})(?:\s*MM)?(?:\s*(?:DIA|DIAMETER|Ø))?', clean)
        if dia_match:
            try:
                dia = float(dia_match.group(1))
                if 150.0 <= dia <= 3000.0:
                    res["diameter_mm"] = dia
            except ValueError:
                pass

        # Rock socket detection first: ROCK SOCKET=1.5M, SOCKET=2.0M, or 1.5M ROCK SOCKET
        clean_for_depth = clean
        socket_match = re.search(r'(?:ROCK\s*SOCKET|SOCKET)\s*[=:]?\s*(\d+(?:\.\d+)?)\s*M\b', clean)
        if not socket_match:
            socket_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b\s*(?:ROCK\s*SOCKET|SOCKET)', clean)
        if socket_match:
            try:
                s = float(socket_match.group(1))
                if 0.0 <= s <= 20.0:
                    res["rock_socket_length_m"] = s
                    clean_for_depth = clean[:socket_match.start()] + clean[socket_match.end():]
            except ValueError:
                pass

        # Depth detection on clean_for_depth: DEPTH=12.0m, 8.5M DEEP, L=10M, or 15M
        depth_match = re.search(r'(?:DEPTH\s*[=:]?\s*|L\s*[=:]?\s*)(\d+(?:\.\d+)?)\s*(?:M\b|METERS?)?', clean_for_depth)
        if not depth_match:
            depth_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b\s*(?:DEEP|DEPTH|LONG)', clean_for_depth)
        if not depth_match:
            depth_match = re.search(r'(\d+(?:\.\d+)?)\s*M\b', clean_for_depth)
        if depth_match:
            try:
                d = float(depth_match.group(1))
                if 1.0 <= d <= 100.0:
                    res["design_depth_m"] = d
            except ValueError:
                pass

        # Stratum
        if "BEDROCK" in clean or "SOLID ROCK" in clean:
            res["stratum"] = GeotechnicalStratum.SOLID_BEDROCK
        elif "WEATHERED" in clean:
            res["stratum"] = GeotechnicalStratum.WEATHERED_ROCK
        elif "CLAY" in clean or "SILT" in clean:
            res["stratum"] = GeotechnicalStratum.CLAY_SILT
        elif "SAND" in clean or "GRAVEL" in clean:
            res["stratum"] = GeotechnicalStratum.SAND_GRAVEL

        # Pile Cap ID (e.g. PC-1, PC02, CAP-A)
        cap_match = re.search(r'\b(PC[-\s]?\d+|CAP[-\s]?[A-Z0-9]+)\b', clean)
        if cap_match:
            res["pile_cap_id"] = cap_match.group(1).replace(" ", "")

        return res

    @staticmethod
    def snap_point(pt: Tuple[float, float], tolerance: float = SNAP_TOLERANCE_PT) -> Tuple[float, float]:
        x, y = pt
        snapped_x = round(x / tolerance) * tolerance
        snapped_y = round(y / tolerance) * tolerance
        return (round(snapped_x, 4), round(snapped_y, 4))

    @staticmethod
    def calculate_pile_volume(diameter_mm: float, depth_m: float) -> float:
        radius_m = (diameter_mm / 1000.0) / 2.0
        return round(math.pi * (radius_m ** 2) * depth_m, 4)

    @classmethod
    def evaluate_piles(
        cls,
        raw_pile_data: List[Dict[str, any]],
        default_level: str = "FOUNDATION"
    ) -> BoredPileExtractionResult:
        """
        Authoritative shadow extraction for foundation piles and piers.
        """
        extracted_piles: List[BoredPileSpec] = []
        total_drilled_m = 0.0
        total_concrete_vol = 0.0
        total_socket_m = 0.0

        piles_by_dia: Dict[str, int] = {}
        linear_m_by_dia: Dict[str, float] = {}
        vol_by_dia: Dict[str, float] = {}

        for item in raw_pile_data:
            pile_id = item.get("pile_id", f"P_{len(extracted_piles)+1:03d}")
            raw_center = item.get("center_point", (0.0, 0.0))
            snapped_center = cls.snap_point(raw_center)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            diameter_mm = float(item.get("diameter_mm", parsed["diameter_mm"]))
            depth_m = float(item.get("design_depth_m", parsed["design_depth_m"]))
            socket_m = float(item.get("rock_socket_length_m", parsed["rock_socket_length_m"]))

            pile_type_val = item.get("pile_type", parsed["pile_type"])
            if isinstance(pile_type_val, str):
                try:
                    p_type = PileType(pile_type_val)
                except ValueError:
                    p_type = PileType.BORED_CAST_IN_PLACE
            else:
                p_type = pile_type_val

            stratum_val = item.get("stratum", parsed["stratum"])
            if isinstance(stratum_val, str):
                try:
                    stratum = GeotechnicalStratum(stratum_val)
                except ValueError:
                    stratum = GeotechnicalStratum.WEATHERED_ROCK
            else:
                stratum = stratum_val

            pile_cap_id = item.get("pile_cap_id", parsed["pile_cap_id"])

            spec = BoredPileSpec(
                pile_id=pile_id,
                pile_type=p_type,
                center_point=snapped_center,
                diameter_mm=diameter_mm,
                design_depth_m=depth_m,
                rock_socket_length_m=socket_m,
                stratum=stratum,
                pile_cap_id=pile_cap_id,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_piles.append(spec)

            vol = cls.calculate_pile_volume(diameter_mm, depth_m)
            total_drilled_m += depth_m
            total_concrete_vol += vol
            total_socket_m += socket_m

            dia_key = f"{int(diameter_mm)}mm"
            piles_by_dia[dia_key] = piles_by_dia.get(dia_key, 0) + 1
            linear_m_by_dia[dia_key] = round(linear_m_by_dia.get(dia_key, 0.0) + depth_m, 4)
            vol_by_dia[dia_key] = round(vol_by_dia.get(dia_key, 0.0) + vol, 4)

        quantities = BoredPileQuantities(
            total_piles_count=len(extracted_piles),
            total_drilled_linear_meters=round(total_drilled_m, 4),
            total_concrete_volume_m3=round(total_concrete_vol, 4),
            total_rock_socket_meters=round(total_socket_m, 4),
            piles_by_diameter=piles_by_dia,
            linear_meters_by_diameter=linear_m_by_dia,
            concrete_volume_by_diameter=vol_by_dia,
        )

        return BoredPileExtractionResult(
            piles=extracted_piles,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceBoredPilePierShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
