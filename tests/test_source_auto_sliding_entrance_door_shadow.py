"""
test_source_auto_sliding_entrance_door_shadow.py

Unit tests for SourceAutomaticSlidingEntranceDoorShadowAuthority.
"""

import pytest
from pb_source_auto_sliding_entrance_door_shadow import (
    SourceAutomaticSlidingEntranceDoorShadowAuthority,
    AutomaticDoorType,
    ActivationSensorType,
    AutomaticDoorSpec,
    AutomaticDoorExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_auto_door_callout_parsing():
    parsed1 = SourceAutomaticSlidingEntranceDoorShadowAuthority.parse_callout(
        "BI-PARTING AUTOMATIC SLIDING DOOR 2000x2400 CLEAR OP W/ DUAL MICROWAVE/IR SENSORS & 2x BARRIER RAILS"
    )
    assert parsed1["door_type"] == AutomaticDoorType.BI_PARTING_SLIDING_DOOR
    assert parsed1["clear_width_mm"] == 2000.0
    assert parsed1["clear_height_mm"] == 2400.0
    assert parsed1["frame_width_mm"] == 4200.0  # 2000 * 2 + 200
    assert parsed1["frame_height_mm"] == 2600.0  # 2400 + 200
    assert parsed1["sensor_type"] == ActivationSensorType.RADAR_MICROWAVE_AND_IR
    assert parsed1["barrier_rails_count"] == 2
    assert parsed1["active_leaves_count"] == 2

    parsed2 = SourceAutomaticSlidingEntranceDoorShadowAuthority.parse_callout(
        "SINGLE SLIDE AUTO DOOR 1200x2200 CLEAR OP W/ PUSH PAD ACTUATOR"
    )
    assert parsed2["door_type"] == AutomaticDoorType.SINGLE_SLIDE_DOOR
    assert parsed2["clear_width_mm"] == 1200.0
    assert parsed2["clear_height_mm"] == 2200.0
    assert parsed2["sensor_type"] == ActivationSensorType.PUSH_PAD_ACTUATOR
    assert parsed2["active_leaves_count"] == 1

    parsed3 = SourceAutomaticSlidingEntranceDoorShadowAuthority.parse_callout(
        "4-LEAF TELESCOPIC AUTOMATIC SLIDING DOOR 3000x2500 CLEAR"
    )
    assert parsed3["door_type"] == AutomaticDoorType.TELESCOPIC_SLIDING_DOOR
    assert parsed3["clear_width_mm"] == 3000.0
    assert parsed3["clear_height_mm"] == 2500.0
    assert parsed3["active_leaves_count"] == 4

    parsed4 = SourceAutomaticSlidingEntranceDoorShadowAuthority.parse_callout(
        "3-WING AUTOMATIC REVOLVING DOOR 2400mm DIA"
    )
    assert parsed4["door_type"] == AutomaticDoorType.AUTOMATIC_REVOLVING_DOOR
    assert parsed4["active_leaves_count"] == 3


def test_auto_door_point_snapping():
    pt = (2001.3, 2400.8)
    snapped = SourceAutomaticSlidingEntranceDoorShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (2002.5, 2400.0)


def test_auto_door_evaluation_quantities():
    raw_data = [
        {
            "door_id": "AD-01",
            "location_point": (5000.0, 0.0),
            "callout": "BI-PARTING AUTOMATIC SLIDING DOOR 2000x2400 CLEAR OP W/ DUAL MICROWAVE/IR SENSORS & 2x BARRIER RAILS",
            "level_id": "L01",
            "host_wall_id": "W-LOBBY-01",
        },
        {
            "door_id": "AD-02",
            "location_point": (10000.0, 0.0),
            "callout": "SINGLE SLIDE AUTO DOOR 1200x2200 CLEAR OP W/ PUSH PAD ACTUATOR",
            "level_id": "L01",
            "host_wall_id": "W-LOBBY-02",
        },
    ]

    result = SourceAutomaticSlidingEntranceDoorShadowAuthority.evaluate_doors(raw_data)
    assert len(result.doors) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_doors_count == 2
    # AD-01 clear: 2.0 * 2.4 = 4.8 m2
    # AD-02 clear: 1.2 * 2.2 = 2.64 m2
    # Total clear area: 7.44 m2
    assert pytest.approx(q.total_clear_area_m2, rel=1e-3) == 7.44

    # AD-01 frame: 4.2 * 2.6 = 10.92 m2
    # AD-02 frame: 2.5 * 2.4 = 6.0 m2
    # Total frame area: 16.92 m2
    assert pytest.approx(q.total_frame_elevation_area_m2, rel=1e-3) == 16.92

    # Active leaves: 2 + 1 = 3
    assert q.total_active_leaves_count == 3

    # Barrier rails: 2 + 1 = 3
    assert q.total_barrier_rails_count == 3

    assert q.doors_by_type[AutomaticDoorType.BI_PARTING_SLIDING_DOOR.value] == 1
    assert q.doors_by_type[AutomaticDoorType.SINGLE_SLIDE_DOOR.value] == 1

    assert q.doors_by_sensor[ActivationSensorType.RADAR_MICROWAVE_AND_IR.value] == 1
    assert q.doors_by_sensor[ActivationSensorType.PUSH_PAD_ACTUATOR.value] == 1
