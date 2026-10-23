"""
pb_source_masonry_joint_helical_reinforcement_shadow.py

Authoritative shadow-mode extraction and takeoff for masonry vertical expansion joints,
debonded slip dowels, elastomeric sealant beads, and helical bed joint reinforcement.

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


class MasonryMovementJointType(str, Enum):
    VERTICAL_CONTROL_EXPANSION_JOINT = "VERTICAL_CONTROL_EXPANSION_JOINT"
    ARTICULATION_SETTLEMENT_JOINT = "ARTICULATION_SETTLEMENT_JOINT"
    CAVITY_VENEER_EXPANSION_JOINT = "CAVITY_VENEER_EXPANSION_JOINT"


class BedJointReinforcementType(str, Enum):
    HELICAL_STAINLESS_BAR = "HELICAL_STAINLESS_BAR"
    TRUSS_LADDER_WIRE_MESH = "TRUSS_LADDER_WIRE_MESH"
    NO_BED_REINFORCEMENT = "NO_BED_REINFORCEMENT"


@dataclass
class MasonryJointSpec:
    joint_id: str
    joint_type: MasonryMovementJointType = MasonryMovementJointType.VERTICAL_CONTROL_EXPANSION_JOINT
    location_point: Tuple[float, float] = (0.0, 0.0)
    wall_height_m: float = 3.0
    joint_width_mm: float = 15.0
    slip_dowel_spacing_mm: float = 400.0
    slip_dowel_diameter_mm: float = 12.0
    slip_dowels_count: int = 8
    bed_reinforcement_type: BedJointReinforcementType = BedJointReinforcementType.HELICAL_STAINLESS_BAR
    bed_reinforcement_diameter_mm: float = 6.0
    wall_run_length_m: float = 6.0
    reinforced_courses_count: int = 4
    level_id: str = "L01"
    host_wall_id: Optional[str] = None
    source_callout: str = ""


@dataclass
class MasonryJointQuantities:
    total_joints_count: int = 0
    total_joint_length_meters: float = 0.0
    total_sealant_meters: float = 0.0
    total_slip_dowels_count: int = 0
    total_helical_bed_wire_meters: float = 0.0
    joints_by_type: Dict[str, int] = field(default_factory=dict)
    bed_wire_by_type: Dict[str, float] = field(default_factory=dict)


@dataclass
class MasonryJointExtractionResult:
    joints: List[MasonryJointSpec] = field(default_factory=list)
    quantities: MasonryJointQuantities = field(default_factory=MasonryJointQuantities)
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourceMasonryJointHelicalReinforcementShadowAuthority:
    """Authoritative shadow evaluator for masonry expansion joints and bed reinforcement."""

    @staticmethod
    def parse_callout(text: str) -> Dict[str, any]:
        """
        Parses masonry movement joint callouts.
        Example strings:
          - "15mm VERTICAL MASONRY EXPANSION JOINT W/ R12 DEBONDED SLIP DOWELS AT 400mm CTS & 6mm HELICAL BED REINFORCEMENT"
          - "10mm ARTICULATION JOINT W/ R10 DOWELS AT 450mm CTS"
          - "20mm CAVITY VENEER EXPANSION JOINT W/ TRUSS LADDER WIRE"
          - "VERTICAL CONTROL JOINT NO BED REINFORCEMENT"
        """
        clean = text.upper()
        res = {
            "joint_type": MasonryMovementJointType.VERTICAL_CONTROL_EXPANSION_JOINT,
            "joint_width_mm": 15.0,
            "slip_dowel_spacing_mm": 400.0,
            "slip_dowel_diameter_mm": 12.0,
            "bed_reinforcement_type": BedJointReinforcementType.HELICAL_STAINLESS_BAR,
            "bed_reinforcement_diameter_mm": 6.0,
            "reinforced_courses_count": 4,
        }

        # Typology
        if "ARTICULATION" in clean or "SETTLEMENT" in clean:
            res["joint_type"] = MasonryMovementJointType.ARTICULATION_SETTLEMENT_JOINT
        elif "CAVITY" in clean or "VENEER" in clean:
            res["joint_type"] = MasonryMovementJointType.CAVITY_VENEER_EXPANSION_JOINT
        else:
            res["joint_type"] = MasonryMovementJointType.VERTICAL_CONTROL_EXPANSION_JOINT

        # Bed reinforcement
        if "NO BED" in clean or "WITHOUT BED" in clean:
            res["bed_reinforcement_type"] = BedJointReinforcementType.NO_BED_REINFORCEMENT
            res["reinforced_courses_count"] = 0
        elif "TRUSS" in clean or "LADDER" in clean or "MURFOR" in clean:
            res["bed_reinforcement_type"] = BedJointReinforcementType.TRUSS_LADDER_WIRE_MESH
            res["bed_reinforcement_diameter_mm"] = 4.0
        else:
            res["bed_reinforcement_type"] = BedJointReinforcementType.HELICAL_STAINLESS_BAR

        # Joint width: 10mm, 15mm, 20mm
        w_match = re.search(r'(\d{1,2})\s*MM\s*(?:VERTICAL|EXPANSION|CONTROL|JOINT)?', clean)
        if w_match:
            try:
                w = float(w_match.group(1))
                if 5.0 <= w <= 50.0:
                    res["joint_width_mm"] = w
            except ValueError:
                pass

        # Slip dowel diameter: R10, R12, R16, 12mm DOWEL
        dowel_match = re.search(r'R\s*(\d{2})|(\d{1,2})\s*MM\s*(?:SLIP\s*)?DOWEL', clean)
        if dowel_match:
            try:
                val = float(dowel_match.group(1) or dowel_match.group(2))
                res["slip_dowel_diameter_mm"] = val
            except ValueError:
                pass

        # Slip dowel spacing: AT 400mm CTS, 450mm CTS
        spc_match = re.search(r'(?:AT\s*)?(\d{3})\s*MM\s*(?:CTS|CENTRES|CENTERS|SPACING)?', clean)
        if spc_match:
            try:
                s = float(spc_match.group(1))
                if 200.0 <= s <= 1000.0:
                    res["slip_dowel_spacing_mm"] = s
            except ValueError:
                pass

        # Helical bar diameter: 6mm, 8mm HELICAL
        hel_match = re.search(r'(\d)\s*MM\s*HELICAL', clean)
        if hel_match:
            try:
                res["bed_reinforcement_diameter_mm"] = float(hel_match.group(1))
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
    def evaluate_joints(
        cls,
        raw_joints_data: List[Dict[str, any]],
        default_level: str = "L01",
        default_wall_height_m: float = 3.0
    ) -> MasonryJointExtractionResult:
        """
        Authoritative shadow extraction for masonry expansion joints and bed reinforcement.
        """
        extracted_joints: List[MasonryJointSpec] = []
        tot_joint_m = 0.0
        tot_dowels = 0
        tot_bed_m = 0.0

        joints_by_type_dict: Dict[str, int] = {}
        bed_wire_by_type_dict: Dict[str, float] = {}

        for item in raw_joints_data:
            joint_id = item.get("joint_id", f"MJ_{len(extracted_joints)+1:03d}")
            raw_pt = item.get("location_point", (0.0, 0.0))
            snapped_pt = cls.snap_point(raw_pt)

            callout = item.get("callout", "")
            parsed = cls.parse_callout(callout)

            jtype_val = item.get("joint_type", parsed["joint_type"])
            if isinstance(jtype_val, str):
                try:
                    jtype = MasonryMovementJointType(jtype_val)
                except ValueError:
                    jtype = MasonryMovementJointType.VERTICAL_CONTROL_EXPANSION_JOINT
            else:
                jtype = jtype_val

            btype_val = item.get("bed_reinforcement_type", parsed["bed_reinforcement_type"])
            if isinstance(btype_val, str):
                try:
                    btype = BedJointReinforcementType(btype_val)
                except ValueError:
                    btype = BedJointReinforcementType.HELICAL_STAINLESS_BAR
            else:
                btype = btype_val

            h_wall_m = float(item.get("wall_height_m", default_wall_height_m))
            w_joint_mm = float(item.get("joint_width_mm", parsed["joint_width_mm"]))
            dowel_spc_mm = float(item.get("slip_dowel_spacing_mm", parsed["slip_dowel_spacing_mm"]))
            dowel_dia_mm = float(item.get("slip_dowel_diameter_mm", parsed["slip_dowel_diameter_mm"]))
            bar_dia_mm = float(item.get("bed_reinforcement_diameter_mm", parsed["bed_reinforcement_diameter_mm"]))
            wall_run_m = float(item.get("wall_run_length_m", 6.0))
            courses_cnt = int(item.get("reinforced_courses_count", parsed["reinforced_courses_count"]))

            # Dowel counts: ceil(wall_height_mm / dowel_spc_mm)
            if dowel_spc_mm > 0.0:
                dowels_cnt = int(math.ceil((h_wall_m * 1000.0) / dowel_spc_mm))
            else:
                dowels_cnt = 4

            # Helical wire total run
            bed_run_m = round(wall_run_m * courses_cnt, 4) if btype != BedJointReinforcementType.NO_BED_REINFORCEMENT else 0.0

            spec = MasonryJointSpec(
                joint_id=joint_id,
                joint_type=jtype,
                location_point=snapped_pt,
                wall_height_m=h_wall_m,
                joint_width_mm=w_joint_mm,
                slip_dowel_spacing_mm=dowel_spc_mm,
                slip_dowel_diameter_mm=dowel_dia_mm,
                slip_dowels_count=dowels_cnt,
                bed_reinforcement_type=btype,
                bed_reinforcement_diameter_mm=bar_dia_mm,
                wall_run_length_m=wall_run_m,
                reinforced_courses_count=courses_cnt,
                level_id=item.get("level_id", default_level),
                host_wall_id=item.get("host_wall_id"),
                source_callout=callout,
            )
            extracted_joints.append(spec)

            tot_joint_m += h_wall_m
            tot_dowels += dowels_cnt
            tot_bed_m += bed_run_m

            t_key = jtype.value
            joints_by_type_dict[t_key] = joints_by_type_dict.get(t_key, 0) + 1

            b_key = btype.value
            bed_wire_by_type_dict[b_key] = round(bed_wire_by_type_dict.get(b_key, 0.0) + bed_run_m, 4)

        quantities = MasonryJointQuantities(
            total_joints_count=len(extracted_joints),
            total_joint_length_meters=round(tot_joint_m, 4),
            total_sealant_meters=round(tot_joint_m, 4),
            total_slip_dowels_count=tot_dowels,
            total_helical_bed_wire_meters=round(tot_bed_m, 4),
            joints_by_type=joints_by_type_dict,
            bed_wire_by_type=bed_wire_by_type_dict,
        )

        return MasonryJointExtractionResult(
            joints=extracted_joints,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "authority": "SourceMasonryJointHelicalReinforcementShadowAuthority",
                "version": "1.0.0",
                "snap_tolerance_pt": str(SNAP_TOLERANCE_PT),
            },
        )
