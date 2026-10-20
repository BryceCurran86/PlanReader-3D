"""
test_source_fire_shutter_smoke_baffle_shadow.py

Unit tests for SourceFireShutterSmokeBaffleShadowAuthority.
"""

import pytest
from pb_source_fire_shutter_smoke_baffle_shadow import (
    SourceFireShutterSmokeBaffleShadowAuthority,
    FireShutterType,
    ShutterReleaseMechanism,
    FireShutterSpec,
    FireShutterExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_fire_shutter_callout_parsing():
    parsed1 = SourceFireShutterSmokeBaffleShadowAuthority.parse_callout(
        "4500x3000 MOTORIZED FIRE SHUTTER FRL -/120/- W/ FIRE ALARM AUTO-DESCENT & 450x450 HOOD"
    )
    assert parsed1["shutter_type"] == FireShutterType.MOTORIZED_FIRE_COILING_SHUTTER
    assert parsed1["clear_width_mm"] == 4500.0
    assert parsed1["clear_height_mm"] == 3000.0
    assert parsed1["fire_rating_frl"] == "-/120/-"
    assert parsed1["hood_height_mm"] == 450.0
    assert parsed1["release_mechanism"] == ShutterReleaseMechanism.FIRE_ALARM_SIGNAL_DROP

    parsed2 = SourceFireShutterSmokeBaffleShadowAuthority.parse_callout(
        "6000x2500 SMOKE CONTAINMENT CURTAIN FRL -/60/-"
    )
    assert parsed2["shutter_type"] == FireShutterType.SMOKE_CONTAINMENT_CURTAIN
    assert parsed2["clear_width_mm"] == 6000.0
    assert parsed2["clear_height_mm"] == 2500.0
    assert parsed2["fire_rating_frl"] == "-/60/-"

    parsed3 = SourceFireShutterSmokeBaffleShadowAuthority.parse_callout(
        "2000x1200 COUNTER FIRE SHUTTER FRL -/120/- FUSIBLE LINK"
    )
    assert parsed3["shutter_type"] == FireShutterType.COUNTER_FIRE_SHUTTER
    assert parsed3["clear_width_mm"] == 2000.0
    assert parsed3["clear_height_mm"] == 1200.0
    assert parsed3["release_mechanism"] == ShutterReleaseMechanism.FUSIBLE_LINK_GRAVITY_DROP

    parsed4 = SourceFireShutterSmokeBaffleShadowAuthority.parse_callout(
        "OVERHEAD SECTIONAL INSULATED DOOR 4000x4500"
    )
    assert parsed4["shutter_type"] == FireShutterType.OVERHEAD_SECTIONAL_INSULATED_DOOR


def test_fire_shutter_point_snapping():
    pt = (4501.3, 3000.8)
    snapped = SourceFireShutterSmokeBaffleShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (4502.5, 3000.0)


def test_fire_shutter_evaluation_quantities():
    raw_data = [
        {
            "shutter_id": "FS-01",
            "location_point": (5000.0, 0.0),
            "callout": "4500x3000 MOTORIZED FIRE SHUTTER FRL -/120/- & 450x450 HOOD",
            "side_guide_width_mm": 100.0,
            "hood_height_mm": 450.0,
            "level_id": "L01",
            "host_opening_id": "OP-101",
        },
        {
            "shutter_id": "FS-02",
            "location_point": (12000.0, 0.0),
            "callout": "6000x2500 SMOKE CONTAINMENT CURTAIN FRL -/60/-",
            "side_guide_width_mm": 100.0,
            "hood_height_mm": 300.0,
            "level_id": "L01",
            "host_opening_id": "OP-102",
        },
    ]

    result = SourceFireShutterSmokeBaffleShadowAuthority.evaluate_shutters(raw_data)
    assert len(result.shutters) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_shutters_count == 2

    # Clear areas:
    # FS-01: 4.5 * 3.0 = 13.5 m2
    # FS-02: 6.0 * 2.5 = 15.0 m2
    # Total: 28.5 m2
    assert pytest.approx(q.total_clear_area_m2, rel=1e-3) == 28.5

    # Curtain areas:
    # FS-01: (4.5 + 0.2) * (3.0 + 0.45) = 4.7 * 3.45 = 16.215 m2
    # FS-02: (6.0 + 0.2) * (2.5 + 0.3) = 6.2 * 2.8 = 17.36 m2
    # Total: 16.215 + 17.36 = 33.575 m2
    assert pytest.approx(q.total_curtain_area_m2, rel=1e-3) == 33.575

    # Guide tracks (2 * height):
    # FS-01: 2 * 3.0 = 6.0m
    # FS-02: 2 * 2.5 = 5.0m
    # Total: 11.0m
    assert pytest.approx(q.total_guide_track_meters, rel=1e-3) == 11.0

    # Hood lengths:
    # FS-01: 4.7m
    # FS-02: 6.2m
    # Total: 10.9m
    assert pytest.approx(q.total_hood_enclosure_meters, rel=1e-3) == 10.9

    assert q.shutters_by_type[FireShutterType.MOTORIZED_FIRE_COILING_SHUTTER.value] == 1
    assert q.shutters_by_type[FireShutterType.SMOKE_CONTAINMENT_CURTAIN.value] == 1
    assert q.shutters_by_frl["-/120/-"] == 1
    assert q.shutters_by_frl["-/60/-"] == 1
