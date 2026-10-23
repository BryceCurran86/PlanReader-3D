"""
test_source_sprinkler_head_pipe_shadow.py

Unit tests for SourceSprinklerHeadPipeShadowAuthority.
"""

import pytest
from pb_source_sprinkler_head_pipe_shadow import (
    SourceSprinklerHeadPipeShadowAuthority,
    SprinklerOrientation,
    SprinklerHeadSpec,
    SprinklerPipeSpec,
    SprinklerHydraulicExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_sprinkler_head_callout_parsing():
    parsed1 = SourceSprinklerHeadPipeShadowAuthority.parse_head_callout(
        "CONCEALED PENDENT SPRINKLER HEAD K80 QR 68C"
    )
    assert parsed1["orientation"] == SprinklerOrientation.PENDENT_CONCEALED
    assert parsed1["k_factor_metric"] == 80.0
    assert parsed1["temperature_rating_c"] == 68
    assert parsed1["is_quick_response"] is True

    parsed2 = SourceSprinklerHeadPipeShadowAuthority.parse_head_callout(
        "UPRIGHT SPRINKLER K115 79C OPEN CEILING"
    )
    assert parsed2["orientation"] == SprinklerOrientation.UPRIGHT
    assert parsed2["k_factor_metric"] == 115.0
    assert parsed2["temperature_rating_c"] == 79

    parsed3 = SourceSprinklerHeadPipeShadowAuthority.parse_head_callout(
        "ESFR PENDENT HEAD K360 93C HIGH BAY"
    )
    assert parsed3["orientation"] == SprinklerOrientation.ESFR_HIGH_BAY
    assert parsed3["k_factor_metric"] == 360.0
    assert parsed3["temperature_rating_c"] == 93

    parsed4 = SourceSprinklerHeadPipeShadowAuthority.parse_head_callout(
        "SIDEWALL SPRINKLER HEAD K80 68C"
    )
    assert parsed4["orientation"] == SprinklerOrientation.SIDEWALL_HORIZONTAL


def test_sprinkler_pipe_callout_parsing():
    parsed_p1 = SourceSprinklerHeadPipeShadowAuthority.parse_pipe_callout(
        "DN25 SPRINKLER RANGE PIPE"
    )
    assert parsed_p1["nominal_dia_dn"] == 25
    assert parsed_p1["is_branch_main"] is False

    parsed_p2 = SourceSprinklerHeadPipeShadowAuthority.parse_pipe_callout(
        "DN50 DISTRIBUTION BRANCH MAIN"
    )
    assert parsed_p2["nominal_dia_dn"] == 50
    assert parsed_p2["is_branch_main"] is True


def test_sprinkler_snapping():
    pt = (123.4, 456.7)
    snapped = SourceSprinklerHeadPipeShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_sprinkler_evaluation_quantities():
    heads_data = [
        {
            "head_id": "SH-01",
            "location_point": (3000.0, 3000.0),
            "callout": "CONCEALED PENDENT SPRINKLER HEAD K80 68C",
            "level_id": "L01",
        },
        {
            "head_id": "SH-02",
            "location_point": (6000.0, 3000.0),
            "callout": "CONCEALED PENDENT SPRINKLER HEAD K80 68C",
            "level_id": "L01",
        },
        {
            "head_id": "SH-03",
            "location_point": (3000.0, 6000.0),
            "callout": "UPRIGHT SPRINKLER K115 79C",
            "level_id": "L01",
        },
    ]

    pipes_data = [
        {
            "pipe_id": "P-01",
            "centerline_points": [(0.0, 3000.0), (8000.0, 3000.0)],
            "callout": "DN25 SPRINKLER RANGE PIPE",
            "level_id": "L01",
        },
        {
            "pipe_id": "P-02",
            "centerline_points": [(0.0, 0.0), (0.0, 10000.0)],
            "callout": "DN50 DISTRIBUTION BRANCH MAIN",
            "level_id": "L01",
        },
    ]

    res = SourceSprinklerHeadPipeShadowAuthority.evaluate_sprinkler_network(
        heads_data, pipes_data, scale_ratio=0.001
    )

    assert len(res.heads) == 3
    assert len(res.pipes) == 2
    q = res.quantities
    assert q.total_heads_count == 3
    assert q.heads_by_orientation["PENDENT_CONCEALED"] == 2
    assert q.heads_by_orientation["UPRIGHT"] == 1
    assert q.heads_by_k_factor["K80"] == 2
    assert q.heads_by_k_factor["K115"] == 1

    # Pipes: P-01 is 8.0m of DN25, P-02 is 10.0m of DN50 -> total = 18.0m
    assert pytest.approx(q.total_pipe_linear_meters, 0.001) == 18.0
    assert pytest.approx(q.pipe_linear_meters_by_dn["DN25"], 0.001) == 8.0
    assert pytest.approx(q.pipe_linear_meters_by_dn["DN50"], 0.001) == 10.0

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
