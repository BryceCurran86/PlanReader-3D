"""
test_source_crane_runway_girder_rail_shadow.py

Unit tests for SourceCraneRunwayGirderRailShadowAuthority.
"""

import pytest
from pb_source_crane_runway_girder_rail_shadow import (
    SourceCraneRunwayGirderRailShadowAuthority,
    CraneRunwayType,
    CraneRailMountingType,
    CraneRunwayRunSpec,
    CraneRunwayExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_crane_runway_callout_parsing():
    parsed1 = SourceCraneRunwayGirderRailShadowAuthority.parse_callout(
        "610UB125 CRANE RUNWAY GIRDER W/ CR50 RAIL ON RESILIENT PAD & CLIPS AT 600mm CTS W/ 2x BUFFERS"
    )
    assert parsed1["runway_type"] == CraneRunwayType.OVERHEAD_BRIDGE_CRANE_RUNWAY
    assert parsed1["girder_section"] == "610UB125"
    assert parsed1["rail_section"] == "CR50"
    assert parsed1["mounting_type"] == CraneRailMountingType.RESILIENT_ELASTOMERIC_PAD
    assert parsed1["clip_spacing_m"] == 0.6
    assert parsed1["buffer_stops_count"] == 2

    parsed2 = SourceCraneRunwayGirderRailShadowAuthority.parse_callout(
        "700WB150 RUNWAY BEAM W/ CR60 RAIL DIRECT BEARING CLIPS AT 0.5m"
    )
    assert parsed2["girder_section"] == "700WB150"
    assert parsed2["rail_section"] == "CR60"
    assert parsed2["mounting_type"] == CraneRailMountingType.DIRECT_STEEL_BEARING
    assert parsed2["clip_spacing_m"] == 0.5

    parsed3 = SourceCraneRunwayGirderRailShadowAuthority.parse_callout(
        "310UB40.4 MONORAIL HOIST BEAM"
    )
    assert parsed3["runway_type"] == CraneRunwayType.MONORAIL_HOIST_BEAM
    assert parsed3["girder_section"] == "310UB40.4"


def test_crane_runway_point_snapping():
    pt = (610.3, 125.8)
    snapped = SourceCraneRunwayGirderRailShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (610.0, 125.0)


def test_crane_runway_polyline_length():
    points = [(0.0, 0.0), (30000.0, 0.0)]
    length = SourceCraneRunwayGirderRailShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 30.0


def test_crane_runway_evaluation_quantities():
    raw_data = [
        {
            "run_id": "CR-01",
            "centerline_points": [(0.0, 0.0), (30000.0, 0.0)],
            "callout": "610UB125 CRANE RUNWAY GIRDER W/ CR50 RAIL ON RESILIENT PAD & CLIPS AT 600mm CTS W/ 2x BUFFERS",
            "level_id": "CRANE_LEVEL",
        },
        {
            "run_id": "CR-02",
            "centerline_points": [(0.0, 15000.0), (30000.0, 15000.0)],
            "callout": "610UB125 CRANE RUNWAY GIRDER W/ CR50 RAIL ON RESILIENT PAD & CLIPS AT 600mm CTS W/ 2x BUFFERS",
            "level_id": "CRANE_LEVEL",
        },
    ]

    result = SourceCraneRunwayGirderRailShadowAuthority.evaluate_runway_runs(raw_data)
    assert len(result.runs) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_runs_count == 2
    # 2 runs of 30.0m = 60.0m
    assert pytest.approx(q.total_girder_length_meters, rel=1e-3) == 60.0
    assert pytest.approx(q.total_rail_length_meters, rel=1e-3) == 60.0
    assert pytest.approx(q.total_resilient_pad_meters, rel=1e-3) == 60.0

    # Clips: each 30m run at 0.6m spacing -> ceil(30/0.6) + 1 = 51 positions * 2 = 102 clips
    # Total for 2 runs: 204 clips
    assert q.total_rail_clips_count == 204

    # Buffers: 2 per run -> 4 total
    assert q.total_buffer_stops_count == 4

    assert CraneRunwayType.OVERHEAD_BRIDGE_CRANE_RUNWAY.value in q.length_by_type
    assert "610UB125" in q.girders_by_section
