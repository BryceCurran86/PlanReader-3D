"""
test_source_trench_drain_grate_shadow.py

Unit tests for SourceTrenchDrainGrateShadowAuthority.
"""

import pytest
from pb_source_trench_drain_grate_shadow import (
    SourceTrenchDrainGrateShadowAuthority,
    TrenchGrateType,
    TrenchLoadClass,
    TrenchDrainRunSpec,
    TrenchDrainExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_trench_drain_callout_parsing():
    parsed1 = SourceTrenchDrainGrateShadowAuthority.parse_callout(
        "200mm INTERNAL POLYMER CONCRETE TRENCH DRAIN CLASS D DUCTILE IRON SLOTTED GRATE W/ 1x IN-LINE SILT BASKET"
    )
    assert parsed1["grate_type"] == TrenchGrateType.DUCTILE_IRON_SLOTTED_GRATE
    assert parsed1["load_class"] == TrenchLoadClass.CLASS_D_HEAVY_DUTY
    assert parsed1["internal_width_mm"] == 200.0
    assert parsed1["inline_sumps_count"] == 1

    parsed2 = SourceTrenchDrainGrateShadowAuthority.parse_callout(
        "150mm HEELGUARD STAINLESS STEEL WEDGE WIRE TRENCH DRAIN CLASS C"
    )
    assert parsed2["grate_type"] == TrenchGrateType.HEELGUARD_STAINLESS_WEDGE_WIRE
    assert parsed2["load_class"] == TrenchLoadClass.CLASS_C_COMMERCIAL
    assert parsed2["internal_width_mm"] == 150.0

    parsed3 = SourceTrenchDrainGrateShadowAuthority.parse_callout(
        "100mm GALVANIZED STEEL BAR GRATE TRENCH DRAIN CLASS B"
    )
    assert parsed3["grate_type"] == TrenchGrateType.GALVANIZED_STEEL_BAR_GRATE
    assert parsed3["load_class"] == TrenchLoadClass.CLASS_B_LIGHT_TRAFFIC
    assert parsed3["internal_width_mm"] == 100.0

    parsed4 = SourceTrenchDrainGrateShadowAuthority.parse_callout(
        "300mm SOLID DUCTILE IRON COVER CLASS E INDUSTRIAL"
    )
    assert parsed4["grate_type"] == TrenchGrateType.SOLID_DUCTILE_IRON_COVER
    assert parsed4["load_class"] == TrenchLoadClass.CLASS_E_INDUSTRIAL
    assert parsed4["internal_width_mm"] == 300.0


def test_trench_drain_point_snapping():
    pt = (200.3, 400.8)
    snapped = SourceTrenchDrainGrateShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (200.0, 400.0)


def test_trench_drain_polyline_length():
    points = [(0.0, 0.0), (20000.0, 0.0)]
    length = SourceTrenchDrainGrateShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 20.0


def test_trench_drain_evaluation_quantities():
    raw_data = [
        {
            "run_id": "TD-01",
            "centerline_points": [(0.0, 0.0), (20000.0, 0.0)],
            "callout": "200mm INTERNAL POLYMER CONCRETE TRENCH DRAIN CLASS D DUCTILE IRON SLOTTED GRATE W/ 1x IN-LINE SILT BASKET",
            "internal_width_mm": 200.0,
            "invert_depth_mm": 250.0,
            "bedding_thickness_mm": 150.0,
            "level_id": "CIVIL",
        },
        {
            "run_id": "TD-02",
            "centerline_points": [(0.0, 5000.0), (10000.0, 5000.0)],
            "callout": "150mm HEELGUARD STAINLESS STEEL WEDGE WIRE TRENCH DRAIN CLASS C W/ 2x SILT PITS",
            "internal_width_mm": 150.0,
            "invert_depth_mm": 200.0,
            "bedding_thickness_mm": 150.0,
            "level_id": "CIVIL",
        },
    ]

    result = SourceTrenchDrainGrateShadowAuthority.evaluate_trench_runs(raw_data)
    assert len(result.runs) == 2
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_runs_count == 2
    # TD-01: 20m, TD-02: 10m -> total = 30m
    assert pytest.approx(q.total_length_meters, rel=1e-3) == 30.0
    assert pytest.approx(q.total_grating_meters, rel=1e-3) == 30.0

    # Sump pits: 1 + 2 = 3
    assert q.total_inline_sumps_count == 3

    # Concrete volume:
    # TD-01: W_ext = 0.2 + 2*0.15 = 0.5m. D_ext = 0.25 + 0.15 = 0.4m.
    # Gross area = 0.5 * 0.4 = 0.2 m2. Void area = 0.2 * 0.25 = 0.05 m2.
    # Net concrete area = 0.15 m2. Volume (20m) = 20 * 0.15 = 3.0 m3.
    # TD-02: W_ext = 0.15 + 2*0.15 = 0.45m. D_ext = 0.2 + 0.15 = 0.35m.
    # Gross area = 0.45 * 0.35 = 0.1575 m2. Void area = 0.15 * 0.2 = 0.03 m2.
    # Net concrete area = 0.1275 m2. Volume (10m) = 10 * 0.1275 = 1.275 m3.
    # Total concrete volume: 3.0 + 1.275 = 4.275 m3.
    assert pytest.approx(q.total_concrete_encasement_m3, rel=1e-3) == 4.275

    assert TrenchGrateType.DUCTILE_IRON_SLOTTED_GRATE.value in q.length_by_grate_type
    assert TrenchGrateType.HEELGUARD_STAINLESS_WEDGE_WIRE.value in q.length_by_grate_type
    assert TrenchLoadClass.CLASS_D_HEAVY_DUTY.value in q.length_by_load_class
    assert TrenchLoadClass.CLASS_C_COMMERCIAL.value in q.length_by_load_class
