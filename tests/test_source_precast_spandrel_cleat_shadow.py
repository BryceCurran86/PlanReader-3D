"""
test_source_precast_spandrel_cleat_shadow.py

Unit tests for SourcePrecastSpandrelCleatShadowAuthority.
"""

import pytest
from pb_source_precast_spandrel_cleat_shadow import (
    SourcePrecastSpandrelCleatShadowAuthority,
    SpandrelPanelType,
    CleatConnectionType,
    PrecastSpandrelSpec,
    PrecastSpandrelExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_spandrel_callout_parsing():
    parsed1 = SourcePrecastSpandrelCleatShadowAuthority.parse_callout(
        "6000x1200 PRECAST SPANDREL PANEL 175mm THICK W/ 2x GRAVITY BRACKETS & 2x TIE-BACK CLEATS"
    )
    assert parsed1["panel_type"] == SpandrelPanelType.SOLID_PRECAST_SPANDREL
    assert parsed1["panel_length_m"] == 6.0
    assert parsed1["panel_height_m"] == 1.2
    assert parsed1["thickness_mm"] == 175.0
    assert parsed1["gravity_brackets_count"] == 2
    assert parsed1["tieback_cleats_count"] == 2

    parsed2 = SourcePrecastSpandrelCleatShadowAuthority.parse_callout(
        "7200x1500 INSULATED SANDWICH PRECAST SPANDREL 225mm THICK 4x TIE-BACKS"
    )
    assert parsed2["panel_type"] == SpandrelPanelType.INSULATED_SANDWICH_SPANDREL
    assert parsed2["panel_length_m"] == 7.2
    assert parsed2["panel_height_m"] == 1.5
    assert parsed2["thickness_mm"] == 225.0
    assert parsed2["tieback_cleats_count"] == 4

    parsed3 = SourcePrecastSpandrelCleatShadowAuthority.parse_callout(
        "INTEGRATED WINDOW SILL SPANDREL PANEL"
    )
    assert parsed3["panel_type"] == SpandrelPanelType.INTEGRATED_WINDOW_SILL_SPANDREL

    parsed4 = SourcePrecastSpandrelCleatShadowAuthority.parse_callout(
        "CURVED RADIUS SPANDREL PANEL 200mm THK"
    )
    assert parsed4["panel_type"] == SpandrelPanelType.CURVED_RADIUS_SPANDREL
    assert parsed4["thickness_mm"] == 200.0


def test_spandrel_point_snapping():
    pt = (12.3, 45.7)
    snapped = SourcePrecastSpandrelCleatShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 45.0)


def test_spandrel_polygon_area_calculation():
    # 6000mm x 1200mm rectangle
    poly = [
        (0.0, 0.0),
        (6000.0, 0.0),
        (6000.0, 1200.0),
        (0.0, 1200.0),
    ]
    area = SourcePrecastSpandrelCleatShadowAuthority.calculate_polygon_area(poly, scale_ratio=0.001)
    assert pytest.approx(area, rel=1e-3) == 7.2


def test_spandrel_evaluation_quantities():
    raw_data = [
        {
            "panel_id": "SP-01",
            "boundary_polygon": [(0.0, 0.0), (6000.0, 0.0), (6000.0, 1200.0), (0.0, 1200.0)],
            "callout": "6000x1200 PRECAST SPANDREL PANEL 175mm THICK W/ 2x GRAVITY BRACKETS & 2x TIE-BACK CLEATS",
            "level_id": "L02",
        },
        {
            "panel_id": "SP-02",
            "boundary_polygon": [(6000.0, 0.0), (13200.0, 0.0), (13200.0, 1500.0), (6000.0, 1500.0)],
            "callout": "7200x1500 INSULATED SANDWICH PRECAST SPANDREL 225mm THICK W/ 2x GRAVITY & 4x TIE-BACKS",
            "level_id": "L02",
        },
    ]

    result = SourcePrecastSpandrelCleatShadowAuthority.evaluate_spandrels(raw_data)
    assert len(result.panels) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_panels_count == 2
    # Area: 6.0*1.2 = 7.2m2; 7.2*1.5 = 10.8m2. Total area = 18.0 m2
    assert pytest.approx(q.total_elevation_area_m2, rel=1e-3) == 18.0

    # Concrete volume:
    # SP-01: 7.2 m2 * 0.175 m = 1.26 m3
    # SP-02: 10.8 m2 * 0.175 m (net concrete for insulated sandwich) = 1.89 m3
    # Total volume = 3.15 m3
    assert pytest.approx(q.total_concrete_volume_m3, rel=1e-3) == 3.15

    # Connections:
    # SP-01: 2 gravity, 2 tie-back
    # SP-02: 2 gravity, 4 tie-back
    assert q.total_gravity_brackets_count == 4
    assert q.total_tieback_cleats_count == 6

    # Area by type
    assert SpandrelPanelType.SOLID_PRECAST_SPANDREL.value in q.area_by_type
    assert SpandrelPanelType.INSULATED_SANDWICH_SPANDREL.value in q.area_by_type
