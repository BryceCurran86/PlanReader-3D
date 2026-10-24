"""
pb_source_steel_bracing_gusset_plate_shadow.py

Authoritative shadow-mode extraction and quantification for structural steel lateral bracing
members, 3D diagonal geometric lengths, gusset plate connections, and turnbuckle hardware.

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
STEEL_DENSITY_KG_M3: float = 7850.0


class BracingConfigType(str, Enum):
    UNKNOWN = "UNKNOWN"
    X_BRACE = "X_BRACE"
    CHEVRON_V = "CHEVRON_V"
    K_BRACE = "K_BRACE"
    SINGLE_DIAGONAL = "SINGLE_DIAGONAL"


@dataclass
class GussetPlateSpec:
    gusset_id: str
    location: Tuple[float, float, float]
    width_mm: float = 0.0
    height_mm: float = 0.0
    thickness_mm: float = 0.0


@dataclass
class BracingMemberSpec:
    member_id: str
    config_type: BracingConfigType
    start_point: Tuple[float, float, float]
    end_point: Tuple[float, float, float]
    section_name: str = ""
    linear_mass_kg_m: float = 0.0
    start_gusset: Optional[GussetPlateSpec] = None
    end_gusset: Optional[GussetPlateSpec] = None
    has_turnbuckle: bool = False
    level_id: str = "ELEV"
    source_tag: str = ""


@dataclass
class SteelBracingQuantities:
    total_bracing_member_count: int
    total_bracing_linear_length_m: float
    total_member_steel_mass_kg: float
    total_gusset_plate_count: int
    total_gusset_plate_mass_kg: float
    total_system_steel_mass_kg: float
    total_turnbuckle_count: int


@dataclass
class SteelBracingExtractionResult:
    members: List[BracingMemberSpec]
    quantities: SteelBracingQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceSteelBracingGussetPlateShadowAuthority:
    """Authority for analyzing structural steel bracing members and gusset plates in shadow mode."""

    @staticmethod
    def snap_point_3d(pt: Tuple[float, float, float], reference_points: List[Tuple[float, float, float]]) -> Tuple[float, float, float]:
        for ref in reference_points:
            dist = math.sqrt((pt[0] - ref[0]) ** 2 + (pt[1] - ref[1]) ** 2 + (pt[2] - ref[2]) ** 2)
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def compute_3d_distance(pt1: Tuple[float, float, float], pt2: Tuple[float, float, float]) -> float:
        return math.sqrt((pt2[0] - pt1[0]) ** 2 + (pt2[1] - pt1[1]) ** 2 + (pt2[2] - pt1[2]) ** 2)

    @staticmethod
    def parse_bracing_annotation(annotation: str) -> Tuple[BracingConfigType, str, float, bool]:
        """
        Parses annotation, e.g.:
        'X-BRACING 75x75x6 EA W/ 12THK GUSSETS' or '20 DIA TIE ROD W/ TURNBUCKLE'
        Returns (config_type, section_name, linear_mass_kg_m, has_turnbuckle)
        """
        clean = annotation.upper().strip()

        # Config type
        if "X-BRAC" in clean or "X BRAC" in clean or "CROSS" in clean:
            cfg = BracingConfigType.X_BRACE
        elif "CHEVRON" in clean or "V-BRACE" in clean:
            cfg = BracingConfigType.CHEVRON_V
        elif "K-BRACE" in clean:
            cfg = BracingConfigType.K_BRACE
        elif "TIE" in clean or "DIAGONAL" in clean or "SINGLE" in clean:
            cfg = BracingConfigType.SINGLE_DIAGONAL
        else:
            cfg = BracingConfigType.UNKNOWN

        # Turnbuckle
        has_tb = "TURNBUCKLE" in clean or "CLEVIS" in clean or "TIE ROD" in clean

        # Section & mass
        if "75X75X6" in clean or "75X6" in clean:
            sec = "75x75x6 EA"
            mass = 6.81
        elif "90X90X8" in clean or "90X8" in clean:
            sec = "90x90x8 EA"
            mass = 10.6
        elif "100X100X6" in clean:
            sec = "100x100x6 SHS"
            mass = 17.5
        elif "88.9" in clean or "CHS" in clean:
            sec = "88.9x4.0 CHS"
            mass = 8.38
        elif "ROD" in clean or "ROUND" in clean:
            sec = "20mm Round Bar"
            mass = 2.47
        else:
            sec = ""
            mass = 0.0

        return cfg, sec, mass, has_tb

    @classmethod
    def evaluate_bracing_system(cls, members: List[BracingMemberSpec]) -> SteelBracingExtractionResult:
        total_len_m = 0.0
        total_member_mass_kg = 0.0
        turnbuckles = 0
        seen_gusset_ids = set()
        total_gusset_mass_kg = 0.0
        gusset_count = 0

        for m in members:
            diag_len = cls.compute_3d_distance(m.start_point, m.end_point)
            total_len_m += diag_len

            m_mass = diag_len * m.linear_mass_kg_m
            total_member_mass_kg += m_mass

            if m.has_turnbuckle:
                turnbuckles += 1

            for g in (m.start_gusset, m.end_gusset):
                if g and g.gusset_id not in seen_gusset_ids:
                    seen_gusset_ids.add(g.gusset_id)
                    gusset_count += 1
                    gw_m = g.width_mm / 1000.0
                    gh_m = g.height_mm / 1000.0
                    gt_m = g.thickness_mm / 1000.0
                    g_vol_m3 = gw_m * gh_m * gt_m
                    g_mass = g_vol_m3 * STEEL_DENSITY_KG_M3
                    total_gusset_mass_kg += g_mass

        total_system_mass_kg = total_member_mass_kg + total_gusset_mass_kg

        quantities = SteelBracingQuantities(
            total_bracing_member_count=len(members),
            total_bracing_linear_length_m=round(total_len_m, 3),
            total_member_steel_mass_kg=round(total_member_mass_kg, 2),
            total_gusset_plate_count=gusset_count,
            total_gusset_plate_mass_kg=round(total_gusset_mass_kg, 2),
            total_system_steel_mass_kg=round(total_system_mass_kg, 2),
            total_turnbuckle_count=turnbuckles
        )

        return SteelBracingExtractionResult(
            members=members,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={"bracing_member_count": str(len(members))}
        )
