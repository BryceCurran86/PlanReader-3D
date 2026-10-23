"""
test_source_plant_screen_acoustic_enclosure_shadow.py

Unit tests for SourcePlantScreenAcousticEnclosureShadowAuthority.
"""

import pytest
from pb_source_plant_screen_acoustic_enclosure_shadow import (
    SourcePlantScreenAcousticEnclosureShadowAuthority,
    PlantScreenType,
    ScreenSupportType,
    PlantScreenSpec,
    PlantScreenExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_plant_screen_callout_parsing():
    parsed1 = SourcePlantScreenAcousticEnclosureShadowAuthority.parse_callout(
        "2.4m HIGH ARCHITECTURAL SIGHT SCREEN 100x100 SHS POSTS AT 2.0m CTS W/ 1x LOUVER ACCESS DOOR"
    )
    assert parsed1["screen_type"] == PlantScreenType.ARCHITECTURAL_SIGHT_SCREEN
    assert parsed1["support_type"] == ScreenSupportType.STRUCTURAL_STEEL_SHS
    assert parsed1["screen_height_m"] == 2.4
    assert parsed1["post_spacing_m"] == 2.0
    assert parsed1["integrated_doors_count"] == 1

    parsed2 = SourcePlantScreenAcousticEnclosureShadowAuthority.parse_callout(
        "CONTINUOUS ACOUSTIC LOUVER ENCLOSURE H=3.0m RW 20dB ALUMINIUM BOX MULLIONS"
    )
    assert parsed2["screen_type"] == PlantScreenType.CONTINUOUS_ACOUSTIC_LOUVER
    assert parsed2["support_type"] == ScreenSupportType.ALUMINIUM_BOX_MULLIONS
    assert parsed2["screen_height_m"] == 3.0

    parsed3 = SourcePlantScreenAcousticEnclosureShadowAuthority.parse_callout(
        "WEATHERPROOF PLANT ENCLOSURE 2.0M HIGH DOUBLE DOOR"
    )
    assert parsed3["screen_type"] == PlantScreenType.WEATHERPROOF_PLANT_ENCLOSURE
    assert parsed3["screen_height_m"] == 2.0
    assert parsed3["integrated_doors_count"] == 2
    assert parsed3["post_spacing_m"] == 0.0

    omitted = SourcePlantScreenAcousticEnclosureShadowAuthority.parse_callout("PLANT SCREEN")
    assert omitted["screen_height_m"] == 0.0
    assert omitted["post_spacing_m"] == 0.0
    omitted_spec = PlantScreenSpec(screen_id="PS-OMIT")
    assert omitted_spec.screen_height_m == 0.0
    assert omitted_spec.post_spacing_m == 0.0


def test_plant_screen_snapping():
    pt = (123.4, 456.7)
    snapped = SourcePlantScreenAcousticEnclosureShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_plant_screen_evaluation_quantities():
    raw_data = [
        {
            "screen_id": "PS-01",
            "centerline_points": [(0.0, 0.0), (10000.0, 0.0)],
            "callout": "2.4m HIGH ARCHITECTURAL SIGHT SCREEN POSTS AT 2.0m W/ 1x DOOR",
            "level_id": "ROOF",
        },
        {
            "screen_id": "PS-02",
            "centerline_points": [(0.0, 5000.0), (6000.0, 5000.0)],
            "callout": "CONTINUOUS ACOUSTIC LOUVER H=3.0m POSTS AT 2.0m",
            "level_id": "ROOF",
        },
    ]

    res = SourcePlantScreenAcousticEnclosureShadowAuthority.evaluate_screens(raw_data, scale_ratio=0.001)

    assert len(res.screens) == 2
    q = res.quantities
    assert q.total_screens_count == 2
    # PS-01: 10.0m len, H=2.4m -> Area = 24.0 m2, posts = ceil(10/2) + 1 = 6 posts, 1 door
    # PS-02: 6.0m len, H=3.0m -> Area = 18.0 m2, posts = ceil(6/2) + 1 = 4 posts, 0 doors
    assert pytest.approx(q.total_linear_meters, 0.001) == 16.0
    assert pytest.approx(q.total_elevation_area_m2, 0.001) == 42.0
    assert pytest.approx(q.sight_screen_linear_meters, 0.001) == 10.0
    assert pytest.approx(q.acoustic_screen_linear_meters, 0.001) == 6.0
    assert q.total_support_posts_count == 10  # 6 + 4
    assert q.total_integrated_doors_count == 1

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
