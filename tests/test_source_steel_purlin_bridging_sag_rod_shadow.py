"""
test_source_steel_purlin_bridging_sag_rod_shadow.py

Unit tests for SourceSteelPurlinBridgingSagRodShadowAuthority.
"""

import pytest
from pb_source_steel_purlin_bridging_sag_rod_shadow import (
    SourceSteelPurlinBridgingSagRodShadowAuthority,
    PurlinBridgingType,
    PurlinBridgingRunSpec,
    PurlinBridgingExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_purlin_bridging_callout_parsing():
    parsed1 = SourceSteelPurlinBridgingSagRodShadowAuthority.parse_callout(
        "MIDSPAN PURLIN BRIDGING PB200 W/ M12 SAG RODS & 2x TURNBUCKLES"
    )
    assert parsed1["bridging_type"] == PurlinBridgingType.SOLID_BRIDGING_STRUT
    assert parsed1["profile_designation"] == "PB200"
    assert parsed1["sag_rod_diameter_mm"] == 12.0
    assert parsed1["turnbuckles_count"] == 2

    parsed2 = SourceSteelPurlinBridgingSagRodShadowAuthority.parse_callout(
        "PB150 SOLID BRIDGING STRUT W/ M16 SAG RODS"
    )
    assert parsed2["bridging_type"] == PurlinBridgingType.SOLID_BRIDGING_STRUT
    assert parsed2["profile_designation"] == "PB150"
    assert parsed2["sag_rod_diameter_mm"] == 16.0

    parsed3 = SourceSteelPurlinBridgingSagRodShadowAuthority.parse_callout(
        "APEX BRIDGING SYSTEM W/ 2x APEX TIES"
    )
    assert parsed3["bridging_type"] == PurlinBridgingType.APEX_BRIDGING_SYSTEM
    assert parsed3["apex_ties_count"] == 2

    parsed4 = SourceSteelPurlinBridgingSagRodShadowAuthority.parse_callout(
        "FASCIA DIAGONAL BRACE"
    )
    assert parsed4["bridging_type"] == PurlinBridgingType.FASCIA_DIAGONAL_BRACE


def test_purlin_bridging_point_snapping():
    pt = (120.3, 450.8)
    snapped = SourceSteelPurlinBridgingSagRodShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (120.0, 450.0)


def test_purlin_bridging_length():
    points = [(0.0, 0.0), (12000.0, 0.0)]
    length = SourceSteelPurlinBridgingSagRodShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 12.0


def test_purlin_bridging_evaluation_quantities():
    raw_data = [
        {
            "run_id": "BR-01",
            "centerline_points": [(0.0, 0.0), (12000.0, 0.0)],
            "callout": "MIDSPAN PURLIN BRIDGING PB200 W/ M12 SAG RODS & 2x TURNBUCKLES",
            "purlin_spacing_m": 1.2,
            "level_id": "ROOF",
        },
        {
            "run_id": "BR-02",
            "centerline_points": [(0.0, 1000.0), (6000.0, 1000.0)],
            "callout": "APEX BRIDGING SYSTEM W/ 2x APEX TIES",
            "purlin_spacing_m": 1.2,
            "level_id": "ROOF",
        },
    ]

    result = SourceSteelPurlinBridgingSagRodShadowAuthority.evaluate_bridging_runs(raw_data)
    assert len(result.runs) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_runs_count == 2
    # BR-01 length = 12.0m, BR-02 length = 6.0m. Total = 18.0m
    assert pytest.approx(q.total_length_meters, rel=1e-3) == 18.0

    # Bays count:
    # BR-01: 12.0 / 1.2 = 10 bays -> 10 struts, 10 rods, 2 turnbuckles, 0 apex
    # BR-02: 6.0 / 1.2 = 5 bays -> 5 struts, 5 rods, 2 turnbuckles, 2 apex
    assert q.total_bridging_struts_count == 15
    assert q.total_sag_rods_count == 15
    assert q.total_turnbuckles_count == 4
    assert q.total_apex_ties_count == 2

    assert PurlinBridgingType.SOLID_BRIDGING_STRUT.value in q.length_by_type
    assert PurlinBridgingType.APEX_BRIDGING_SYSTEM.value in q.length_by_type
