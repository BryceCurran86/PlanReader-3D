"""
test_source_cable_tray_conduit_racking_shadow.py

Unit tests for SourceCableTrayConduitRackingShadowAuthority.
"""

import pytest
from pb_source_cable_tray_conduit_racking_shadow import (
    SourceCableTrayConduitRackingShadowAuthority,
    CableSupportSystemType,
    CableTrayRunSpec,
    CableTrayContainmentExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_cable_tray_callout_parsing():
    parsed1 = SourceCableTrayConduitRackingShadowAuthority.parse_callout(
        "600mm WIDE HEAVY DUTY CABLE LADDER 100mm DEEP SUPPORTS AT 2.0m W/ 2x 90 BENDS"
    )
    assert parsed1["system_type"] == CableSupportSystemType.HEAVY_DUTY_CABLE_LADDER
    assert parsed1["tray_width_mm"] == 600.0
    assert parsed1["side_rail_depth_mm"] == 100.0
    assert parsed1["support_spacing_m"] == 2.0
    assert parsed1["fittings_count"] == 2

    parsed2 = SourceCableTrayConduitRackingShadowAuthority.parse_callout(
        "300mm PERFORATED CABLE TRAY SUPPORTS AT 1.5m"
    )
    assert parsed2["system_type"] == CableSupportSystemType.PERFORATED_CABLE_TRAY
    assert parsed2["tray_width_mm"] == 300.0
    assert parsed2["support_spacing_m"] == 1.5

    parsed3 = SourceCableTrayConduitRackingShadowAuthority.parse_callout(
        "150mm WIRE MESH BASKET TRAY"
    )
    assert parsed3["system_type"] == CableSupportSystemType.WIRE_MESH_BASKET_TRAY
    assert parsed3["tray_width_mm"] == 150.0


def test_cable_tray_snapping():
    pt = (123.4, 456.7)
    snapped = SourceCableTrayConduitRackingShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_cable_tray_evaluation_quantities():
    raw_data = [
        {
            "run_id": "CT-01",
            "centerline_points": [(0.0, 0.0), (10000.0, 0.0)],
            "callout": "600mm HEAVY DUTY CABLE LADDER SUPPORTS AT 2.0m W/ 2x BENDS",
            "level_id": "L01",
        },
        {
            "run_id": "CT-02",
            "centerline_points": [(0.0, 5000.0), (6000.0, 5000.0)],
            "callout": "300mm PERFORATED CABLE TRAY SUPPORTS AT 1.5m",
            "level_id": "L01",
        },
    ]

    res = SourceCableTrayConduitRackingShadowAuthority.evaluate_containment_runs(
        raw_data, scale_ratio=0.001
    )

    assert len(res.runs) == 2
    q = res.quantities
    assert q.total_runs_count == 2
    # CT-01: 10.0m ladder, 600mm wide, supports = ceil(10/2) + 1 = 6, 2 fittings
    # CT-02: 6.0m tray, 300mm wide, supports = ceil(6/1.5) + 1 = 5, 0 fittings
    assert pytest.approx(q.total_linear_meters, 0.001) == 16.0
    assert pytest.approx(q.ladder_linear_meters, 0.001) == 10.0
    assert pytest.approx(q.tray_linear_meters, 0.001) == 6.0
    assert q.total_trapeze_supports_count == 11  # 6 + 5
    assert q.total_fittings_count == 2

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
