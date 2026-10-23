"""
test_source_cfs_stud_track_nogging_shadow.py

Unit tests for SourceCFSStudTrackNoggingShadowAuthority.
"""

import pytest
from pb_source_cfs_stud_track_nogging_shadow import (
    SourceCFSStudTrackNoggingShadowAuthority,
    CFSFramingType,
    HeadTrackType,
    CFSFramingRunSpec,
    CFSFramingExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_cfs_framing_callout_parsing():
    parsed1 = SourceCFSStudTrackNoggingShadowAuthority.parse_callout(
        "92mm x 0.75 BMT STEEL STUDS AT 450mm CTS W/ SLOTTED DEFLECTION HEAD TRACK & 2 ROWS NOGGINGS"
    )
    assert parsed1["framing_type"] == CFSFramingType.INTERNAL_NON_LOADBEARING_STUD
    assert parsed1["stud_depth_mm"] == 92.0
    assert parsed1["stud_bmt_mm"] == 0.75
    assert parsed1["stud_spacing_mm"] == 450.0
    assert parsed1["head_track_type"] == HeadTrackType.SLOTTED_DEFLECTION_TRACK
    assert parsed1["nogging_rows_count"] == 2

    parsed2 = SourceCFSStudTrackNoggingShadowAuthority.parse_callout(
        "150mm x 1.15 BMT STRUCTURAL CFS STUDS AT 400mm CTS"
    )
    assert parsed2["framing_type"] == CFSFramingType.STRUCTURAL_LOADBEARING_CFS_STUD
    assert parsed2["stud_depth_mm"] == 150.0
    assert parsed2["stud_bmt_mm"] == 1.15
    assert parsed2["stud_spacing_mm"] == 400.0

    parsed3 = SourceCFSStudTrackNoggingShadowAuthority.parse_callout(
        "64mm x 0.50 BMT NON-LOADBEARING STUDS AT 600mm CTS STANDARD TRACK"
    )
    assert parsed3["stud_depth_mm"] == 64.0
    assert parsed3["stud_bmt_mm"] == 0.50
    assert parsed3["stud_spacing_mm"] == 600.0
    assert parsed3["head_track_type"] == HeadTrackType.STANDARD_DEEP_LEG_TRACK

    parsed4 = SourceCFSStudTrackNoggingShadowAuthority.parse_callout(
        "SHAFTWALL 100mm C-H STUDS AT 600mm CTS"
    )
    assert parsed4["framing_type"] == CFSFramingType.SHAFTWALL_CH_STUD
    assert parsed4["stud_depth_mm"] == 100.0


def test_cfs_framing_point_snapping():
    pt = (92.4, 451.7)
    snapped = SourceCFSStudTrackNoggingShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (92.5, 452.5)


def test_cfs_framing_polyline_length():
    points = [(0.0, 0.0), (9000.0, 0.0)]
    length = SourceCFSStudTrackNoggingShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 9.0


def test_cfs_framing_evaluation_quantities():
    raw_data = [
        {
            "wall_id": "W-01",
            "centerline_points": [(0.0, 0.0), (9000.0, 0.0)],
            "callout": "92mm x 0.75 BMT STEEL STUDS AT 450mm CTS W/ SLOTTED DEFLECTION HEAD TRACK & 2 ROWS NOGGINGS",
            "wall_height_m": 3.0,
            "level_id": "L01",
        },
        {
            "wall_id": "W-02",
            "centerline_points": [(0.0, 3000.0), (6000.0, 3000.0)],
            "callout": "150mm x 1.15 BMT STRUCTURAL CFS STUDS AT 400mm CTS W/ 3 ROWS NOGGINGS",
            "wall_height_m": 3.5,
            "level_id": "L01",
        },
    ]

    result = SourceCFSStudTrackNoggingShadowAuthority.evaluate_cfs_runs(raw_data)
    assert len(result.runs) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_walls_count == 2
    # Length: 9.0m + 6.0m = 15.0m
    assert pytest.approx(q.total_wall_length_meters, rel=1e-3) == 15.0

    # Tracks (top + bottom = 2 * length):
    # W-01: 2 * 9 = 18m
    # W-02: 2 * 6 = 12m
    # Total tracks: 30m
    assert pytest.approx(q.total_track_length_meters, rel=1e-3) == 30.0

    # Noggings:
    # W-01: 9m * 2 rows = 18m
    # W-02: 6m * 3 rows = 18m
    # Total noggings: 36m
    assert pytest.approx(q.total_nogging_length_meters, rel=1e-3) == 36.0

    # Studs:
    # W-01: ceil(9000 / 450) + 1 = 20 + 1 = 21 studs (21 * 3.0m = 63.0m)
    # W-02: ceil(6000 / 400) + 1 = 15 + 1 = 16 studs (16 * 3.5m = 56.0m)
    # Total studs: 37 studs
    # Total stud linear meters: 63.0 + 56.0 = 119.0m
    assert q.total_studs_count == 37
    assert pytest.approx(q.total_stud_linear_meters, rel=1e-3) == 119.0

    assert CFSFramingType.INTERNAL_NON_LOADBEARING_STUD.value in q.length_by_framing_type
    assert CFSFramingType.STRUCTURAL_LOADBEARING_CFS_STUD.value in q.length_by_framing_type
    assert "92mm" in q.studs_by_depth
    assert "150mm" in q.studs_by_depth
