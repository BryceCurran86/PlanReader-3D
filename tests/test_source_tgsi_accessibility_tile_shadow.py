"""
test_source_tgsi_accessibility_tile_shadow.py

Unit tests for SourceTGSIAccessibilityTileShadowAuthority.
"""

import pytest
from pb_source_tgsi_accessibility_tile_shadow import (
    SourceTGSIAccessibilityTileShadowAuthority,
    TGSIType,
    TGSIFormat,
    TGSILocationContext,
    TGSIZoneSpec,
    TGSIAccessibilityExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_tgsi_callout_parsing():
    parsed1 = SourceTGSIAccessibilityTileShadowAuthority.parse_callout(
        "600x1200 HAZARD WARNING TACTILE PADS DISCRETE STAINLESS STEEL STUDS AT TOP OF STAIRS"
    )
    assert parsed1["indicator_type"] == TGSIType.HAZARD_WARNING
    assert parsed1["indicator_format"] == TGSIFormat.INDIVIDUAL_STUDS
    assert parsed1["location_context"] == TGSILocationContext.STAIR_TOP
    assert parsed1["depth_m"] == 0.6
    assert parsed1["width_m"] == 1.2

    parsed2 = SourceTGSIAccessibilityTileShadowAuthority.parse_callout(
        "DIRECTIONAL LEADING TACTILE TILES 300x300 COMPOSITE RAMP APPROACH"
    )
    assert parsed2["indicator_type"] == TGSIType.DIRECTIONAL_LEADING
    assert parsed2["indicator_format"] == TGSIFormat.INTEGRATED_TILE
    assert parsed2["location_context"] == TGSILocationContext.RAMP_TOP_BOTTOM

    parsed3 = SourceTGSIAccessibilityTileShadowAuthority.parse_callout(
        "HAZARD TACTILE MAT BOTTOM OF STAIRS 600MM DEEP"
    )
    assert parsed3["indicator_type"] == TGSIType.HAZARD_WARNING
    assert parsed3["indicator_format"] == TGSIFormat.PEEL_AND_STICK_MAT
    assert parsed3["location_context"] == TGSILocationContext.STAIR_BOTTOM
    assert parsed3["depth_m"] == 0.6


def test_tgsi_snapping():
    pt = (100.8, 201.7)
    snapped = SourceTGSIAccessibilityTileShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (100.0, 202.5)


def test_tgsi_evaluation_quantities():
    raw_data = [
        {
            "zone_id": "TGSI-01",
            "boundary_polygon": [
                (0.0, 0.0),
                (1200.0, 0.0),
                (1200.0, 600.0),
                (0.0, 600.0),
            ],
            "callout": "600x1200 HAZARD WARNING STUDS TOP OF STAIRS",
            "level_id": "L01",
        },
        {
            "zone_id": "TGSI-02",
            "boundary_polygon": [],
            "width_m": 2.0,
            "depth_m": 0.6,
            "callout": "DIRECTIONAL LEADING TACTILE TILES",
            "level_id": "L01",
        },
    ]

    res = SourceTGSIAccessibilityTileShadowAuthority.evaluate_zones(raw_data, scale_ratio=0.001)

    assert len(res.zones) == 2
    q = res.quantities
    assert q.total_zones_count == 2
    # TGSI-01: 1.2m * 0.6m = 0.72 m2. Studs = 0.72 * 400 = 288 studs
    # TGSI-02: 2.0m * 0.6m = 1.20 m2. Tiles = ceil(1.20 / 0.09) = 14 tiles
    assert pytest.approx(q.total_area_m2, 0.001) == 1.92
    assert pytest.approx(q.hazard_area_m2, 0.001) == 0.72
    assert pytest.approx(q.directional_area_m2, 0.001) == 1.20
    assert q.total_individual_studs_count == 288
    assert q.total_tile_units_count == 14

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
