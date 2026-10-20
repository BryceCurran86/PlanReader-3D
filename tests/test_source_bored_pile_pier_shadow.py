"""
test_source_bored_pile_pier_shadow.py

Unit tests for SourceBoredPilePierShadowAuthority.
"""

import math
import pytest
from pb_source_bored_pile_pier_shadow import (
    SourceBoredPilePierShadowAuthority,
    PileType,
    GeotechnicalStratum,
    BoredPileSpec,
    BoredPileExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_bored_pile_callout_parsing():
    parsed1 = SourceBoredPilePierShadowAuthority.parse_callout(
        "600mm DIA BORED PILE DEPTH=12.0m ROCK SOCKET=1.5m PC-1"
    )
    assert parsed1["pile_type"] == PileType.BORED_CAST_IN_PLACE
    assert parsed1["diameter_mm"] == 600.0
    assert parsed1["design_depth_m"] == 12.0
    assert parsed1["rock_socket_length_m"] == 1.5
    assert parsed1["pile_cap_id"] == "PC-1"

    parsed2 = SourceBoredPilePierShadowAuthority.parse_callout(
        "P450 CFA PILE 8.5M DEEP CAP-B"
    )
    assert parsed2["pile_type"] == PileType.CONTINUOUS_FLIGHT_AUGER
    assert parsed2["diameter_mm"] == 450.0
    assert parsed2["design_depth_m"] == 8.5
    assert parsed2["pile_cap_id"] == "CAP-B"

    parsed3 = SourceBoredPilePierShadowAuthority.parse_callout(
        "Ø900 PIER 15M SOCKET 2.0M INTO BEDROCK"
    )
    assert parsed3["diameter_mm"] == 900.0
    assert parsed3["design_depth_m"] == 15.0
    assert parsed3["rock_socket_length_m"] == 2.0
    assert parsed3["stratum"] == GeotechnicalStratum.SOLID_BEDROCK


def test_bored_pile_snapping():
    pt = (123.4, 456.7)
    snapped = SourceBoredPilePierShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    # 123.4 / 2.5 = 49.36 -> 49 * 2.5 = 122.5
    # 456.7 / 2.5 = 182.68 -> 183 * 2.5 = 457.5
    assert snapped == (122.5, 457.5)


def test_bored_pile_volume_calculation():
    # 600mm dia, 10m depth: r = 0.3m, Area = pi * 0.09 = 0.282743 m2
    # Vol = 0.282743 * 10 = 2.8274 m3
    vol = SourceBoredPilePierShadowAuthority.calculate_pile_volume(600.0, 10.0)
    expected = math.pi * (0.3 ** 2) * 10.0
    assert pytest.approx(vol, 0.001) == expected


def test_bored_pile_evaluation_quantities():
    raw_data = [
        {
            "pile_id": "P-01",
            "center_point": (100.0, 100.0),
            "callout": "600mm DIA BORED PILE 10.0M DEEP 1.5M ROCK SOCKET",
            "level_id": "FOUNDATION",
        },
        {
            "pile_id": "P-02",
            "center_point": (100.0, 300.0),
            "callout": "600mm DIA BORED PILE 10.0M DEEP 1.5M ROCK SOCKET",
            "level_id": "FOUNDATION",
        },
        {
            "pile_id": "P-03",
            "center_point": (500.0, 500.0),
            "callout": "900mm DIA BORED PILE 12.0M DEEP 2.0M ROCK SOCKET",
            "level_id": "FOUNDATION",
        },
    ]

    res = SourceBoredPilePierShadowAuthority.evaluate_piles(raw_data)

    assert len(res.piles) == 3
    q = res.quantities
    assert q.total_piles_count == 3
    assert q.total_drilled_linear_meters == 32.0  # 10 + 10 + 12
    assert q.total_rock_socket_meters == 5.0  # 1.5 + 1.5 + 2.0

    # Volume: 2 * (pi * 0.3^2 * 10) + (pi * 0.45^2 * 12)
    # 2 * 2.82743 + 7.63407 = 5.65486 + 7.63407 = 13.2889 m3
    expected_vol = 2 * (math.pi * 0.09 * 10.0) + (math.pi * 0.2025 * 12.0)
    assert pytest.approx(q.total_concrete_volume_m3, 0.01) == expected_vol

    assert q.piles_by_diameter["600mm"] == 2
    assert q.piles_by_diameter["900mm"] == 1

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
