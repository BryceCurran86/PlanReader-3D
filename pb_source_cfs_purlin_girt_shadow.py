"""
pb_source_cfs_purlin_girt_shadow.py

Authoritative shadow-mode extraction and structural takeoff for cold-formed steel (CFS)
C and Z roof purlins, perimeter wall girts, eaves struts, laps, and bridging lines.

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

# Standard cold-formed C/Z section mass lookup (kg/m)
STANDARD_CFS_MASS_TABLE: Dict[str, float] = {
    "Z10015": 2.21,
    "Z10019": 2.76,
    "Z15012": 2.34,
    "Z15015": 2.89,
    "Z15019": 3.59,
    "Z15024": 4.50,
    "Z20015": 3.65,
    "Z20019": 4.54,
    "Z20024": 5.70,
    "Z25019": 5.48,
    "Z25024": 6.87,
    "Z30024": 8.05,
    "Z30030": 10.02,
    "C10015": 2.21,
    "C10019": 2.76,
    "C15012": 2.34,
    "C15015": 2.89,
    "C15019": 3.59,
    "C15024": 4.50,
    "C20015": 3.65,
    "C20019": 4.54,
    "C20024": 5.70,
    "C25019": 5.48,
    "C25024": 6.87,
    "C30024": 8.05,
    "C30030": 10.02,
    "TH64": 1.45,
    "TH120": 2.65,
}


class CFSRole(str, Enum):
    UNKNOWN = "UNKNOWN"
    ROOF_PURLIN = "ROOF_PURLIN"
    WALL_GIRT = "WALL_GIRT"
    EAVES_STRUT = "EAVES_STRUT"
    FACIA_PURLIN = "FACIA_PURLIN"


class CFSSectionProfile(str, Enum):
    Z_SECTION = "Z_SECTION"
    C_SECTION = "C_SECTION"
    TOP_HAT = "TOP_HAT"


@dataclass
class CFSMemberSpec:
    member_id: str
    role: CFSRole = CFSRole.UNKNOWN
    section_profile: CFSSectionProfile = CFSSectionProfile.Z_SECTION
    section_designation: str = ""
    centerline_points: List[Tuple[float, float]] = field(default_factory=list)
    lap_count: int = 0
    lap_length_mm: float = 0.0
    bridging_rows_count: int = 0
    linear_mass_kg_m: float = 0.0
    level_id: str = "ROOF"
    source_callout: str = ""


@dataclass
class CFSStructuralQuantities:
    total_members_count: int = 0
    total_net_linear_meters: float = 0.0
    total_gross_linear_meters: float = 0.0
    total_mass_kg: float = 0.0
    purlin_net_linear_meters: float = 0.0
    girt_net_linear_meters: float = 0.0
    total_bridging_rows_count: int = 0
    linear_meters_by_designation: Dict[str, float] = field(default_factory=dict)
    mass_kg_by_designation: Dict[str, float] = field(default_factory=dict)


@dataclass
class CFSExtractionResult:
    members: List[CFSMemberSpec] = field(default_factory=list)
    quantities: CFSStructuralQuantities = field(default_factory=CFSStructuralQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceCFSPurlinGirtShadowAuthority:
    """Authoritative shadow evaluator for cold-formed steel purlins and girts."""

    @staticmethod
    def get_linear_mass(designation: str) -> float:
        clean_des = designation.strip().upper()
        if clean_des in STANDARD_CFS_MASS_TABLE:
            return STANDARD_CFS_MASS_TABLE[clean_des]

        # Estimation based on designation: e.g. Z20020 (depth 200mm, thickness 2.0mm)
        # Girth is approximately ~ (depth + 2*flange(~65) + 2*lip(~15)) = depth + 160 mm
        match = re.search(r'([CZ])(\d{3})(\d{2})', clean_des)
        if match:
            depth = float(match.group(2))
            thickness = float(match.group(3)) / 10.0  # e.g. 20 -> 2.0mm
            girth_m = (depth + 160.0) / 1000.0
            # density of steel 7850 kg/m3
            mass = girth_m * (thickness / 1000.0) * 7850.0
            return round(mass, 2)

        return 0.0

    @classmethod
    def parse_callout(cls, text: str) -> Dict[str, any]:
        """
        Extracts member section designation, role, lap length, and bridging rows.
        Example strings:
          - "Z20019 ROOF PURLIN CONTINUOUS W/ 900mm LAPS 1 ROW BRIDGING"
          - "C15015 WALL GIRT SPAN=6.0m"
          - "EAVES STRUT C20024"
        """
        clean = text.upper()
        res = {
            "role": CFSRole.UNKNOWN,
            "section_profile": CFSSectionProfile.Z_SECTION,
            "section_designation": "",
            "lap_count": 0,
            "lap_length_mm": 0.0,
            "bridging_rows_count": 0,
            "linear_mass_kg_m": 0.0,
        }

        # Role
        if "GIRT" in clean or "WALL" in clean:
            res["role"] = CFSRole.WALL_GIRT
        elif "EAVES" in clean or "STRUT" in clean:
            res["role"] = CFSRole.EAVES_STRUT
        elif "FACIA" in clean or "FASCIA" in clean:
            res["role"] = CFSRole.FACIA_PURLIN
        elif "ROOF" in clean or "PURLIN" in clean:
            res["role"] = CFSRole.ROOF_PURLIN
        else:
            res["role"] = CFSRole.UNKNOWN

        # Designation
        des_match = re.search(r'\b([CZ]\d{5}|TH\d{2,3})\b', clean)
        if des_match:
            des = des_match.group(1)
            res["section_designation"] = des
            if des.startswith("C"):
                res["section_profile"] = CFSSectionProfile.C_SECTION
            elif des.startswith("TH"):
                res["section_profile"] = CFSSectionProfile.TOP_HAT
            else:
                res["section_profile"] = CFSSectionProfile.Z_SECTION
        elif "TOP HAT" in clean or "TOP-HAT" in clean:
            res["section_designation"] = "TH64"
            res["section_profile"] = CFSSectionProfile.TOP_HAT
        elif "C-PURLIN" in clean or "C PURLIN" in clean or "CHANNEL" in clean:
            res["section_designation"] = "C20019"
            res["section_profile"] = CFSSectionProfile.C_SECTION
        else:
            res["section_designation"] = ""

        res["linear_mass_kg_m"] = cls.get_linear_mass(res["section_designation"])

        # Laps: 900mm LAPS, LAPPED 900MM, 2 LAPS
        lap_len_match = re.search(r'(\d{3,4})\s*MM\s*(?:LAP|LAPPED|OVERLAP)', clean)
        if not lap_len_match:
            lap_len_match = re.search(r'(?:LAP|LAPPED|OVERLAP)\s*(\d{3,4})\s*MM', clean)
        if lap_len_match:
            try:
                res["lap_length_mm"] = float(lap_len_match.group(1))
                res["lap_count"] = 1
            except ValueError:
                pass
        elif "LAPPED" in clean or "CONTINUOUS" in clean:
            res["lap_length_mm"] = 900.0
            res["lap_count"] = 1

        lap_cnt_match = re.search(r'(\d+)\s*(?:LAPS|OVERLAPS)', clean)
        if lap_cnt_match:
            try:
                res["lap_count"] = int(lap_cnt_match.group(1))
            except ValueError:
                pass

        # Bridging: 1 ROW BRIDGING, 2 ROWS BRIDGING, SAG RODS
        bridging_match = re.search(r'(\d+)\s*ROW[S]?\s*(?:BRIDGING|SAG\s*ROD)', clean)
        if bridging_match:
            try:
                res["bridging_rows_count"] = int(bridging_match.group(1))
            except ValueError:
                pass
        elif "BRIDGING" in clean or "SAG ROD" in clean:
            res["bridging_rows_count"] = 1

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
        total_len = 0.0
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            total_len += math.hypot(x2 - x1, y2 - y1)
        return round(total_len * scale_ratio, 4)

    @classmethod
    def evaluate_members(
        cls,
        raw_member_data: List[Dict[str, any]],
        scale_ratio: float = 0.001,
        default_level: str = "ROOF"
    ) -> CFSExtractionResult:
        """
        Authoritative shadow extraction for cold-formed steel purlins and girts.
        """
        extracted_members: List[CFSMemberSpec] = []
        tot_net_m = 0.0
        tot_gross_m = 0.0
        tot_mass = 0.0
        purlin_net_m = 0.0
        girt_net_m = 0.0
        tot_bridging_rows = 0

        linear_m_by_des: Dict[str, float] = {}
        mass_by_des: Dict[str, float] = {}

        for item in raw_member_data:
            member_id = item.get("member_id", f"CFS_{len(extracted_members)+1:03d}")
            raw_pts = item.get("centerline_points", [])
            if len(raw_pts) < 2:
                continue

            snapped_pts = [cls.snap_point(pt) for pt in raw_pts]
            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            role_val = item.get("role", parsed["role"])
            if isinstance(role_val, str):
                try:
                    role = CFSRole(role_val)
                except ValueError:
                    role = CFSRole.UNKNOWN
            else:
                role = role_val

            prof_val = item.get("section_profile", parsed["section_profile"])
            if isinstance(prof_val, str):
                try:
                    prof = CFSSectionProfile(prof_val)
                except ValueError:
                    prof = CFSSectionProfile.Z_SECTION
            else:
                prof = prof_val

            desig = item.get("section_designation", parsed["section_designation"])
            lap_cnt = int(item.get("lap_count", parsed["lap_count"]))
            lap_len_mm = float(item.get("lap_length_mm", parsed["lap_length_mm"]))
            bridging_rows = int(item.get("bridging_rows_count", parsed["bridging_rows_count"]))
            lin_mass = float(item.get("linear_mass_kg_m", parsed["linear_mass_kg_m"]))

            spec = CFSMemberSpec(
                member_id=member_id,
                role=role,
                section_profile=prof,
                section_designation=desig,
                centerline_points=snapped_pts,
                lap_count=lap_cnt,
                lap_length_mm=lap_len_mm,
                bridging_rows_count=bridging_rows,
                linear_mass_kg_m=lin_mass,
                level_id=item.get("level_id", default_level),
                source_callout=callout,
            )
            extracted_members.append(spec)

            net_len_m = cls.calculate_polyline_length(snapped_pts, scale_ratio)
            lap_allowance_m = (lap_cnt * lap_len_mm) / 1000.0
            gross_len_m = net_len_m + lap_allowance_m
            member_mass = gross_len_m * lin_mass

            tot_net_m += net_len_m
            tot_gross_m += gross_len_m
            tot_mass += member_mass
            tot_bridging_rows += bridging_rows

            if role in (CFSRole.ROOF_PURLIN, CFSRole.FACIA_PURLIN):
                purlin_net_m += net_len_m
            elif role in (CFSRole.WALL_GIRT, CFSRole.EAVES_STRUT):
                girt_net_m += net_len_m

            linear_m_by_des[desig] = round(linear_m_by_des.get(desig, 0.0) + gross_len_m, 4)
            mass_by_des[desig] = round(mass_by_des.get(desig, 0.0) + member_mass, 4)

        quantities = CFSStructuralQuantities(
            total_members_count=len(extracted_members),
            total_net_linear_meters=round(tot_net_m, 4),
            total_gross_linear_meters=round(tot_gross_m, 4),
            total_mass_kg=round(tot_mass, 4),
            purlin_net_linear_meters=round(purlin_net_m, 4),
            girt_net_linear_meters=round(girt_net_m, 4),
            total_bridging_rows_count=tot_bridging_rows,
            linear_meters_by_designation=linear_m_by_des,
            mass_kg_by_designation=mass_by_des,
        )

        return CFSExtractionResult(
            members=extracted_members,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceCFSPurlinGirtShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
