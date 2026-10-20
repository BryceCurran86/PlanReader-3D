"""
test_source_skylight_smoke_vent_shadow.py

Unit tests for SourceSkylightSmokeVentShadowAuthority.
"""

import pytest
from pb_source_skylight_smoke_vent_shadow import (
    SourceSkylightSmokeVentShadowAuthority,
    RoofVentSkylightType,
    CurbConstructionType,
    SkylightVentSpec,
    SkylightVentExtractionResult,
    SNAP_TOLERANCE_PT,
    DEFAULT_CV_DISCHARGE,
)


def test_skylight_smoke_vent_callout_parsing():
    parsed1 = SourceSkylightSmokeVentShadowAuthority.parse_callout(
        "1200x2400 AUTOMATIC SMOKE & HEAT EXHAUST VENT 200mm INSULATED STEEL CURB W/ SAFETY MESH"
    )
    assert parsed1["unit_type"] == RoofVentSkylightType.AUTOMATIC_SMOKE_HEAT_VENT
    assert parsed1["curb_type"] == CurbConstructionType.INSULATED_STEEL_UPSTAND
    assert parsed1["opening_width_mm"] == 1200.0
    assert parsed1["opening_length_mm"] == 2400.0
    assert parsed1["curb_height_mm"] == 200.0
    assert parsed1["has_safety_mesh"] is True

    parsed2 = SourceSkylightSmokeVentShadowAuthority.parse_callout(
        "1000x1500 DOUBLE GLAZED SKYLIGHT TIMBER KERB H=150"
    )
    assert parsed2["unit_type"] == RoofVentSkylightType.FIXED_SKYLIGHT_DOME
    assert parsed2["curb_type"] == CurbConstructionType.STRUCTURAL_TIMBER_KERB
    assert parsed2["opening_width_mm"] == 1000.0
    assert parsed2["opening_length_mm"] == 1500.0
    assert parsed2["curb_height_mm"] == 150.0

    parsed3 = SourceSkylightSmokeVentShadowAuthority.parse_callout(
        "ROOF ACCESS HATCH 900x900 INSULATED"
    )
    assert parsed3["unit_type"] == RoofVentSkylightType.ROOF_ACCESS_HATCH
    assert parsed3["opening_width_mm"] == 900.0
    assert parsed3["opening_length_mm"] == 900.0

    omitted = SourceSkylightSmokeVentShadowAuthority.parse_callout("SKYLIGHT")
    assert omitted["opening_width_mm"] == 0.0
    assert omitted["opening_length_mm"] == 0.0
    omitted_spec = SkylightVentSpec(unit_id="SK-OMIT")
    assert omitted_spec.opening_width_mm == 0.0
    assert omitted_spec.opening_length_mm == 0.0
    assert omitted_spec.curb_height_mm == 0.0
    assert omitted["curb_height_mm"] == 0.0


def test_skylight_smoke_vent_snapping():
    pt = (301.2, 598.9)
    snapped = SourceSkylightSmokeVentShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (300.0, 600.0)


def test_skylight_smoke_vent_evaluation_quantities():
    raw_data = [
        {
            "unit_id": "SV-01",
            "center_point": (100.0, 100.0),
            "callout": "1200x2400 AUTOMATIC SMOKE VENT 200mm CURB",
            "level_id": "ROOF",
        },
        {
            "unit_id": "SK-01",
            "center_point": (300.0, 100.0),
            "callout": "1000x1500 SKYLIGHT DOME TIMBER KERB H=150",
            "level_id": "ROOF",
        },
    ]

    res = SourceSkylightSmokeVentShadowAuthority.evaluate_roof_penetrations(raw_data)

    assert len(res.units) == 2
    q = res.quantities
    assert q.total_units_count == 2
    assert q.smoke_vents_count == 1
    assert q.skylights_count == 1

    # SV-01: 1.2m * 2.4m = 2.88 m2, perimeter = 2 * (1.2 + 2.4) = 7.2m
    # SK-01: 1.0m * 1.5m = 1.50 m2, perimeter = 2 * (1.0 + 1.5) = 5.0m
    # Total throat area = 4.38 m2, Total curb perimeter = 12.2m
    assert pytest.approx(q.total_throat_area_m2, 0.001) == 4.38
    assert pytest.approx(q.total_curb_perimeter_meters, 0.001) == 12.2

    # Aerodynamic area for smoke vent: 2.88 * 0.65 = 1.872 m2
    assert pytest.approx(q.total_aerodynamic_free_area_m2, 0.001) == 1.872

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
