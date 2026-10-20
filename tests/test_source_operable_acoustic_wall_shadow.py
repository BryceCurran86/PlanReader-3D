"""
test_source_operable_acoustic_wall_shadow.py

Unit tests for SourceOperableAcousticWallShadowAuthority.
"""

import pytest
from pb_source_operable_acoustic_wall_shadow import (
    SourceOperableAcousticWallShadowAuthority,
    OperableWallSystemType,
    OperableWallSpec,
    OperableWallExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_operable_wall_callout_parsing():
    parsed1 = SourceOperableAcousticWallShadowAuthority.parse_callout(
        "OPERABLE ACOUSTIC WALL RW 50 INDIVIDUAL OMNI-DIRECTIONAL PANELS H=3.6m W/ 1x PASS DOOR & CEILING BAFFLE"
    )
    assert parsed1["system_type"] == OperableWallSystemType.INDIVIDUAL_OMNI_DIRECTIONAL_PANELS
    assert parsed1["acoustic_rating_rw_db"] == 50
    assert parsed1["wall_height_m"] == 3.6
    assert parsed1["has_plenum_baffle"] is True
    assert parsed1["pass_doors_count"] == 1

    parsed2 = SourceOperableAcousticWallShadowAuthority.parse_callout(
        "PAIRED PANEL MOVABLE WALL RW 45 H=3.0m"
    )
    assert parsed2["system_type"] == OperableWallSystemType.CENTER_HUNG_PAIRED_PANELS
    assert parsed2["acoustic_rating_rw_db"] == 45
    assert parsed2["wall_height_m"] == 3.0

    parsed3 = SourceOperableAcousticWallShadowAuthority.parse_callout(
        "VERTICAL LIFT RETRACTABLE WALL RW 53"
    )
    assert parsed3["system_type"] == OperableWallSystemType.VERTICAL_LIFT_RETRACTABLE_WALL
    assert parsed3["acoustic_rating_rw_db"] == 53
    assert parsed3["wall_height_m"] == 0.0
    omitted = SourceOperableAcousticWallShadowAuthority.parse_callout("OPERABLE WALL")
    assert omitted["wall_height_m"] == 0.0
    omitted_spec = OperableWallSpec(wall_id="OW-OMIT")
    assert omitted_spec.wall_height_m == 0.0


def test_operable_wall_snapping():
    pt = (123.4, 456.7)
    snapped = SourceOperableAcousticWallShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_operable_wall_evaluation_quantities():
    raw_data = [
        {
            "wall_id": "OW-01",
            "centerline_points": [(0.0, 0.0), (12000.0, 0.0)],
            "callout": "OPERABLE ACOUSTIC WALL RW 50 H=3.5m 1000mm PANEL W/ 1x PASS DOOR & CEILING BAFFLE",
            "parking_stack_track_length_m": 3.0,
            "plenum_height_m": 0.8,
            "level_id": "L01",
        },
        {
            "wall_id": "OW-02",
            "centerline_points": [(0.0, 5000.0), (8000.0, 5000.0)],
            "callout": "PAIRED PANEL MOVABLE WALL RW 45 H=3.0m 1000mm PANEL",
            "parking_stack_track_length_m": 2.0,
            "level_id": "L01",
        },
    ]

    res = SourceOperableAcousticWallShadowAuthority.evaluate_operable_walls(raw_data, scale_ratio=0.001)

    assert len(res.walls) == 2
    q = res.quantities
    assert q.total_walls_count == 2

    # OW-01: 12.0m len, H=3.5m -> Area = 42.0 m2, Track = 12 + 3 = 15m, Panels = 12, Baffle = 12 * 0.8 = 9.6 m2, 1 door
    # OW-02: 8.0m len, H=3.0m -> Area = 24.0 m2, Track = 8 + 2 = 10m, Panels = 8, No baffle, 0 doors
    assert pytest.approx(q.total_wall_linear_meters, 0.001) == 20.0
    assert pytest.approx(q.total_wall_area_m2, 0.001) == 66.0
    assert pytest.approx(q.total_overhead_track_meters, 0.001) == 25.0
    assert q.total_panels_count == 20
    assert pytest.approx(q.total_plenum_baffle_area_m2, 0.001) == 9.6
    assert q.total_pass_doors_count == 1

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
