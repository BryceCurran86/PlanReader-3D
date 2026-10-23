"""
pb_source_precast_panel_joint_sealant_shadow.py

Authoritative shadow-mode extraction and multi-component takeoff for precast concrete wall
panels, vertical/horizontal movement joints, closed-cell foam backing rods, and
elastomeric weather-sealant beads.

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


class PrecastJointType(str, Enum):
    VERTICAL_BUTT_JOINT = "VERTICAL_BUTT_JOINT"
    HORIZONTAL_SHIPLAP_JOINT = "HORIZONTAL_SHIPLAP_JOINT"
    CORNER_MITER_JOINT = "CORNER_MITER_JOINT"


class JointSealantConfig(str, Enum):
    UNKNOWN = "UNKNOWN"
    SINGLE_BEAD = "SINGLE_BEAD"
    DOUBLE_BEAD = "DOUBLE_BEAD"
    FIRE_RATED_SEAL = "FIRE_RATED_SEAL"


@dataclass
class PrecastPanelSpec:
    panel_id: str
    boundary_polygon: List[Tuple[float, float]]
    thickness_mm: float = 0.0
    is_insulated_sandwich: bool = False
    level_id: str = "ELEV"
    source_tag: str = ""


@dataclass
class PrecastJointSpec:
    joint_id: str
    joint_type: PrecastJointType
    centerline_points: List[Tuple[float, float]]
    joint_width_mm: float = 0.0
    sealant_depth_mm: float = 0.0
    backing_rod_dia_mm: float = 0.0
    sealant_config: JointSealantConfig = JointSealantConfig.UNKNOWN
    source_callout: str = ""


@dataclass
class PrecastEnvelopeQuantities:
    total_panel_count: int
    total_panel_face_area_m2: float
    total_panel_concrete_volume_m3: float
    total_joint_length_m: float
    total_backing_rod_length_m: float
    total_sealant_volume_liters: float


@dataclass
class PrecastEnvelopeExtractionResult:
    panels: List[PrecastPanelSpec]
    joints: List[PrecastJointSpec]
    quantities: PrecastEnvelopeQuantities
    status: str = "CANDIDATE"
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    metadata: Dict[str, str] = field(default_factory=dict)


class SourcePrecastPanelJointSealantShadowAuthority:
    """Authority for analyzing precast panels, joints, backing rods, and sealants in shadow mode."""

    @staticmethod
    def snap_point(pt: Tuple[float, float], reference_points: List[Tuple[float, float]]) -> Tuple[float, float]:
        for ref in reference_points:
            dist = math.hypot(pt[0] - ref[0], pt[1] - ref[1])
            if dist <= SNAP_TOLERANCE_PT:
                return ref
        return pt

    @staticmethod
    def compute_polygon_area(points: List[Tuple[float, float]]) -> float:
        n = len(points)
        if n < 3:
            return 0.0
        area = 0.0
        for i in range(n):
            j = (i + 1) % n
            area += points[i][0] * points[j][1]
            area -= points[j][0] * points[i][1]
        return abs(area) / 2.0

    @staticmethod
    def compute_polyline_length(points: List[Tuple[float, float]]) -> float:
        if len(points) < 2:
            return 0.0
        total = 0.0
        for i in range(len(points) - 1):
            total += math.hypot(points[i + 1][0] - points[i][0], points[i + 1][1] - points[i][1])
        return total

    @staticmethod
    def parse_joint_annotation(annotation: str) -> Tuple[PrecastJointType, float, float, float, JointSealantConfig]:
        """
        Parses annotation, e.g.:
        '20mm VERTICAL CONTROL JOINT W/ 25 DIA PE ROD & DOUBLE POLYURETHANE SEALANT'
        Returns (joint_type, joint_width_mm, sealant_depth_mm, backing_rod_dia_mm, sealant_config)
        """
        clean = annotation.upper().strip()

        # Joint type
        if "HORIZONTAL" in clean or "SHIPLAP" in clean:
            j_type = PrecastJointType.HORIZONTAL_SHIPLAP_JOINT
        elif "CORNER" in clean or "MITER" in clean:
            j_type = PrecastJointType.CORNER_MITER_JOINT
        else:
            j_type = PrecastJointType.VERTICAL_BUTT_JOINT

        # Sealant config
        if "FIRE" in clean:
            cfg = JointSealantConfig.FIRE_RATED_SEAL
        elif "DOUBLE" in clean:
            cfg = JointSealantConfig.DOUBLE_BEAD
        elif "SINGLE" in clean:
            cfg = JointSealantConfig.SINGLE_BEAD
        else:
            cfg = JointSealantConfig.UNKNOWN

        # Joint width
        w_match = re.search(r"(\d+)\s*(?:MM)?\s*(?:GAP|JOINT|WIDTH|WIDE)", clean)
        if w_match is None:
            w_match = re.search(r"(\d+)\s*MM", clean)
        joint_w = float(w_match.group(1)) if w_match else 0.0

        # Backing rod diameter
        rod_match = re.search(r"(\d+)\s*(?:MM)?\s*(?:DIA|ROD)", clean)
        rod_dia = float(rod_match.group(1)) if rod_match else 0.0

        # Sealant depth
        d_match = re.search(r"(\d+)\s*(?:MM)?\s*(?:DEPTH|DEEP)", clean)
        seal_depth = float(d_match.group(1)) if d_match else 0.0

        return j_type, joint_w, seal_depth, rod_dia, cfg

    @classmethod
    def evaluate_precast_envelope(
        cls,
        panels: List[PrecastPanelSpec],
        joints: List[PrecastJointSpec],
        drawing_scale: float = 1.0  # meters per drawing coordinate unit
    ) -> PrecastEnvelopeExtractionResult:
        total_panel_area_m2 = 0.0
        total_conc_vol_m3 = 0.0

        for p in panels:
            raw_area = cls.compute_polygon_area(p.boundary_polygon)
            area_m2 = raw_area * (drawing_scale ** 2)
            total_panel_area_m2 += area_m2

            t_m = p.thickness_mm / 1000.0
            total_conc_vol_m3 += area_m2 * t_m

        total_joint_len_m = 0.0
        total_rod_len_m = 0.0
        total_sealant_vol_l = 0.0

        for j in joints:
            raw_len = cls.compute_polyline_length(j.centerline_points)
            len_m = raw_len * drawing_scale
            total_joint_len_m += len_m

            if j.sealant_config == JointSealantConfig.DOUBLE_BEAD:
                num_beads = 2
            elif j.sealant_config == JointSealantConfig.SINGLE_BEAD:
                num_beads = 1
            else:
                num_beads = 0
            total_rod_len_m += len_m * num_beads

            # Sealant cross section (m2) = (W_m * D_m) * num_beads
            w_m = j.joint_width_mm / 1000.0
            d_m = j.sealant_depth_mm / 1000.0
            bead_cross_section_m2 = w_m * d_m * num_beads
            vol_m3 = len_m * bead_cross_section_m2
            total_sealant_vol_l += vol_m3 * 1000.0  # 1 m3 = 1000 L

        quantities = PrecastEnvelopeQuantities(
            total_panel_count=len(panels),
            total_panel_face_area_m2=round(total_panel_area_m2, 3),
            total_panel_concrete_volume_m3=round(total_conc_vol_m3, 3),
            total_joint_length_m=round(total_joint_len_m, 3),
            total_backing_rod_length_m=round(total_rod_len_m, 3),
            total_sealant_volume_liters=round(total_sealant_vol_l, 2)
        )

        return PrecastEnvelopeExtractionResult(
            panels=panels,
            joints=joints,
            quantities=quantities,
            status="CANDIDATE",
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            metadata={
                "panel_count": str(len(panels)),
                "joint_count": str(len(joints))
            }
        )
