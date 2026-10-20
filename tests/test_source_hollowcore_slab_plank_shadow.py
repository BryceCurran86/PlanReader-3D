"""
test_source_hollowcore_slab_plank_shadow.py

Unit tests for SourceHollowcoreSlabPlankShadowAuthority.
"""

import pytest
from pb_source_hollowcore_slab_plank_shadow import (
    SourceHollowcoreSlabPlankShadowAuthority,
    HollowcorePlankType,
    StructuralToppingType,
    HollowcorePlankSpec,
    HollowcoreSlabExtractionResult,
    SNAP_TOLERANCE_PT,
    GROUT_VOLUME_PER_LINEAR_METER_M3,
)


def test_hollowcore_callout_parsing():
    parsed1 = SourceHollowcoreSlabPlankShadowAuthority.parse_callout(
        "200mm HOLLOWCORE SLAB W/ 65mm COMPOSITE TOPPING"
    )
    assert parsed1["plank_type"] == HollowcorePlankType.STANDARD_EXTRUDED_PLANK
    assert parsed1["depth_mm"] == 200.0
    assert parsed1["topping_type"] == StructuralToppingType.COMPOSITE_TOPPING
    assert parsed1["topping_thickness_mm"] == 65.0
    assert parsed1["nominal_width_mm"] == 1200.0

    parsed2 = SourceHollowcoreSlabPlankShadowAuthority.parse_callout(
        "250mm PRECAST HOLLOWCORE PLANK UNTOPPED L=9.2m"
    )
    assert parsed2["depth_mm"] == 250.0
    assert parsed2["topping_type"] == StructuralToppingType.UNSTOPPED
    assert parsed2["topping_thickness_mm"] == 0.0

    parsed3 = SourceHollowcoreSlabPlankShadowAuthority.parse_callout(
        "HC200 NARROW CUT PLANK 600mm WIDE 65mm TOPPING"
    )
    assert parsed3["plank_type"] == HollowcorePlankType.NARROW_CUT_PLANK
    assert parsed3["depth_mm"] == 200.0
    assert parsed3["nominal_width_mm"] == 600.0


def test_hollowcore_snapping():
    pt = (123.4, 456.7)
    snapped = SourceHollowcoreSlabPlankShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_hollowcore_evaluation_quantities():
    raw_data = [
        {
            "plank_id": "HC-01",
            "boundary_polygon": [
                (0.0, 0.0),
                (1200.0, 0.0),
                (1200.0, 8000.0),
                (0.0, 8000.0),
            ],
            "callout": "200mm HOLLOWCORE SLAB W/ 65mm COMPOSITE TOPPING",
            "length_m": 8.0,
            "level_id": "L02",
        },
        {
            "plank_id": "HC-02",
            "boundary_polygon": [
                (1200.0, 0.0),
                (2400.0, 0.0),
                (2400.0, 8000.0),
                (1200.0, 8000.0),
            ],
            "callout": "200mm HOLLOWCORE SLAB W/ 65mm COMPOSITE TOPPING",
            "length_m": 8.0,
            "level_id": "L02",
        },
        {
            "plank_id": "HC-03",
            "boundary_polygon": [],
            "nominal_width_mm": 600.0,
            "length_m": 8.0,
            "callout": "HC200 NARROW CUT PLANK UNTOPPED",
            "level_id": "L02",
        },
    ]

    res = SourceHollowcoreSlabPlankShadowAuthority.evaluate_slabs(raw_data, scale_ratio=0.001)

    assert len(res.planks) == 3
    q = res.quantities
    assert q.total_planks_count == 3

    # Areas:
    # HC-01: 1.2m * 8.0m = 9.6 m2
    # HC-02: 1.2m * 8.0m = 9.6 m2
    # HC-03: 0.6m * 8.0m = 4.8 m2
    # Total = 24.0 m2
    assert pytest.approx(q.total_plank_area_m2, 0.001) == 24.0

    # Composite Topping: HC-01 + HC-02 = 19.2 m2 * 0.065m = 1.248 m3
    assert pytest.approx(q.total_topping_volume_m3, 0.001) == 1.248

    # Shear key length: 8 + 8 + 8 = 24.0m
    assert pytest.approx(q.total_shear_key_linear_meters, 0.001) == 24.0
    expected_grout_vol = 24.0 * GROUT_VOLUME_PER_LINEAR_METER_M3
    assert pytest.approx(q.total_shear_key_grout_volume_m3, 0.001) == expected_grout_vol

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
