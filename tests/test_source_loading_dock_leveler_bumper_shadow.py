"""
test_source_loading_dock_leveler_bumper_shadow.py

Unit tests for SourceLoadingDockLevelerBumperShadowAuthority.
"""

import pytest
from pb_source_loading_dock_leveler_bumper_shadow import (
    SourceLoadingDockLevelerBumperShadowAuthority,
    DockLevelerType,
    DockBumperType,
    DockLevelerPitSpec,
    DockLevelerExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_dock_leveler_callout_parsing():
    parsed1 = SourceLoadingDockLevelerBumperShadowAuthority.parse_callout(
        "1830x2440 HYDRAULIC DOCK LEVELER PIT 500mm DEEP W/ 2x LAMINATED BUMPERS & EMBED CURB ANGLES"
    )
    assert parsed1["leveler_type"] == DockLevelerType.HYDRAULIC_DOCK_LEVELER
    assert pytest.approx(parsed1["pit_width_m"], rel=1e-3) == 1.83
    assert pytest.approx(parsed1["pit_length_m"], rel=1e-3) == 2.44
    assert parsed1["pit_depth_mm"] == 500.0
    assert parsed1["bumper_type"] == DockBumperType.LAMINATED_RUBBER_BUMPER
    assert parsed1["bumpers_count"] == 2

    parsed2 = SourceLoadingDockLevelerBumperShadowAuthority.parse_callout(
        "2130x2440 AIR-POWERED DOCK LEVELER PIT 600mm DEEP 2x STEEL-FACED BUMPERS"
    )
    assert parsed2["leveler_type"] == DockLevelerType.AIR_POWERED_DOCK_LEVELER
    assert pytest.approx(parsed2["pit_width_m"], rel=1e-3) == 2.13
    assert pytest.approx(parsed2["pit_length_m"], rel=1e-3) == 2.44
    assert parsed2["pit_depth_mm"] == 600.0
    assert parsed2["bumper_type"] == DockBumperType.STEEL_FACED_BUMPER

    parsed3 = SourceLoadingDockLevelerBumperShadowAuthority.parse_callout(
        "VERTICAL STORING DOCK LEVELER PIT 300mm DEEP W/ 4x MOLDED BUMPERS"
    )
    assert parsed3["leveler_type"] == DockLevelerType.VERTICAL_STORING_LEVELER
    assert parsed3["pit_depth_mm"] == 300.0
    assert parsed3["bumper_type"] == DockBumperType.MOLDED_RUBBER_BUMPER
    assert parsed3["bumpers_count"] == 4

    parsed4 = SourceLoadingDockLevelerBumperShadowAuthority.parse_callout(
        "EDGE OF DOCK LEVELER"
    )
    assert parsed4["leveler_type"] == DockLevelerType.EDGE_OF_DOCK_LEVELER
    assert parsed4["pit_depth_mm"] == 0.0


def test_dock_leveler_point_snapping():
    pt = (182.8, 244.1)
    snapped = SourceLoadingDockLevelerBumperShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (182.5, 245.0)


def test_dock_leveler_area_and_void_volume():
    # 1830mm x 2440mm pit
    poly = [
        (0.0, 0.0),
        (1830.0, 0.0),
        (1830.0, 2440.0),
        (0.0, 2440.0),
    ]
    area = SourceLoadingDockLevelerBumperShadowAuthority.calculate_polygon_area(poly, scale_ratio=0.001)
    assert pytest.approx(area, rel=1e-3) == 4.4652


def test_dock_leveler_evaluation_quantities():
    raw_data = [
        {
            "dock_id": "DK-01",
            "boundary_polygon": [(0.0, 0.0), (1830.0, 0.0), (1830.0, 2440.0), (0.0, 2440.0)],
            "callout": "1830x2440 HYDRAULIC DOCK LEVELER PIT 500mm DEEP W/ 2x LAMINATED BUMPERS",
            "level_id": "L01",
        },
        {
            "dock_id": "DK-02",
            "boundary_polygon": [(3000.0, 0.0), (5130.0, 0.0), (5130.0, 2440.0), (3000.0, 2440.0)],
            "callout": "2130x2440 AIR-POWERED DOCK LEVELER PIT 600mm DEEP W/ 2x STEEL-FACED BUMPERS",
            "level_id": "L01",
        },
    ]

    result = SourceLoadingDockLevelerBumperShadowAuthority.evaluate_docks(raw_data)
    assert len(result.docks) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_dock_positions == 2
    # Area DK-01: 1.83 * 2.44 = 4.4652 m2
    # Area DK-02: 2.13 * 2.44 = 5.1972 m2
    # Total area: ~9.6624 m2
    assert pytest.approx(q.total_pit_area_m2, rel=1e-3) == 9.6624

    # DK-01 void volume: 4.4652 * 0.5 = 2.2326 m3
    # DK-02 void volume: 5.1972 * 0.6 = 3.1183 m3
    # Total volume: ~5.3509 m3
    assert pytest.approx(q.total_pit_void_volume_m3, rel=1e-2) == 5.3509

    # Curb angle (3-sided):
    # DK-01: 1.83 + 2 * 2.44 = 6.71 m
    # DK-02: 2.13 + 2 * 2.44 = 7.01 m
    # Total curb angle: 13.72 m
    assert pytest.approx(q.total_curb_angle_meters, rel=1e-3) == 13.72

    assert q.total_bumpers_count == 4
    assert q.positions_by_type[DockLevelerType.HYDRAULIC_DOCK_LEVELER.value] == 1
    assert q.positions_by_type[DockLevelerType.AIR_POWERED_DOCK_LEVELER.value] == 1
    assert q.bumpers_by_type[DockBumperType.LAMINATED_RUBBER_BUMPER.value] == 2
    assert q.bumpers_by_type[DockBumperType.STEEL_FACED_BUMPER.value] == 2
