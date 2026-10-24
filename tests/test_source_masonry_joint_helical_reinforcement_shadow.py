"""
test_source_masonry_joint_helical_reinforcement_shadow.py

Unit tests for SourceMasonryJointHelicalReinforcementShadowAuthority.
"""

import pytest
from pb_source_masonry_joint_helical_reinforcement_shadow import (
    SourceMasonryJointHelicalReinforcementShadowAuthority,
    MasonryMovementJointType,
    BedJointReinforcementType,
    MasonryJointSpec,
    MasonryJointExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_masonry_joint_callout_parsing():
    parsed1 = SourceMasonryJointHelicalReinforcementShadowAuthority.parse_callout(
        "15mm VERTICAL MASONRY EXPANSION JOINT W/ R12 DEBONDED SLIP DOWELS AT 400mm CTS & 6mm HELICAL BED REINFORCEMENT"
    )
    assert parsed1["joint_type"] == MasonryMovementJointType.VERTICAL_CONTROL_EXPANSION_JOINT
    assert parsed1["joint_width_mm"] == 15.0
    assert parsed1["slip_dowel_diameter_mm"] == 12.0
    assert parsed1["slip_dowel_spacing_mm"] == 400.0
    assert parsed1["bed_reinforcement_type"] == BedJointReinforcementType.HELICAL_STAINLESS_BAR
    assert parsed1["bed_reinforcement_diameter_mm"] == 6.0

    parsed2 = SourceMasonryJointHelicalReinforcementShadowAuthority.parse_callout(
        "10mm ARTICULATION JOINT W/ R10 DOWELS AT 450mm CTS NO BED REINFORCEMENT"
    )
    assert parsed2["joint_type"] == MasonryMovementJointType.ARTICULATION_SETTLEMENT_JOINT
    assert parsed2["joint_width_mm"] == 10.0
    assert parsed2["slip_dowel_diameter_mm"] == 10.0
    assert parsed2["slip_dowel_spacing_mm"] == 450.0
    assert parsed2["bed_reinforcement_type"] == BedJointReinforcementType.NO_BED_REINFORCEMENT

    parsed3 = SourceMasonryJointHelicalReinforcementShadowAuthority.parse_callout(
        "20mm CAVITY VENEER EXPANSION JOINT W/ TRUSS LADDER WIRE"
    )
    assert parsed3["joint_type"] == MasonryMovementJointType.CAVITY_VENEER_EXPANSION_JOINT
    assert parsed3["joint_width_mm"] == 20.0
    assert parsed3["bed_reinforcement_type"] == BedJointReinforcementType.TRUSS_LADDER_WIRE_MESH


def test_masonry_joint_point_snapping():
    pt = (123.4, 567.8)
    snapped = SourceMasonryJointHelicalReinforcementShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 567.5)


def test_masonry_joint_evaluation_quantities():
    raw_data = [
        {
            "joint_id": "MJ-01",
            "location_point": (6000.0, 0.0),
            "wall_height_m": 3.2,
            "wall_run_length_m": 6.0,
            "callout": "15mm VERTICAL MASONRY EXPANSION JOINT W/ R12 DEBONDED SLIP DOWELS AT 400mm CTS & 6mm HELICAL BED REINFORCEMENT",
            "level_id": "L01",
            "host_wall_id": "W-BRICK-01",
        },
        {
            "joint_id": "MJ-02",
            "location_point": (12000.0, 0.0),
            "wall_height_m": 3.2,
            "wall_run_length_m": 6.0,
            "callout": "10mm ARTICULATION JOINT W/ R10 DOWELS AT 450mm CTS NO BED REINFORCEMENT",
            "level_id": "L01",
            "host_wall_id": "W-BRICK-01",
        },
    ]

    result = SourceMasonryJointHelicalReinforcementShadowAuthority.evaluate_joints(raw_data)
    assert len(result.joints) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_joints_count == 2
    # Joint linear meters: 3.2 + 3.2 = 6.4m
    assert pytest.approx(q.total_joint_length_meters, rel=1e-3) == 6.4
    assert pytest.approx(q.total_sealant_meters, rel=1e-3) == 6.4

    # Dowels:
    # MJ-01: ceil(3200 / 400) = 8 dowels
    # MJ-02: ceil(3200 / 450) = 8 dowels
    # Total: 16 dowels
    assert q.total_slip_dowels_count == 16

    # Helical bed wire:
    # MJ-01: 6.0m * 4 courses = 24.0m
    # MJ-02: NO BED = 0.0m
    # Total: 24.0m
    assert pytest.approx(q.total_helical_bed_wire_meters, rel=1e-3) == 24.0

    assert q.joints_by_type[MasonryMovementJointType.VERTICAL_CONTROL_EXPANSION_JOINT.value] == 1
    assert q.joints_by_type[MasonryMovementJointType.ARTICULATION_SETTLEMENT_JOINT.value] == 1
    assert BedJointReinforcementType.HELICAL_STAINLESS_BAR.value in q.bed_wire_by_type
