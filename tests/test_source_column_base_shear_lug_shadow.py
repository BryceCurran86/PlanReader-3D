import pytest
from pb_source_column_base_shear_lug_shadow import (
    parse_shear_lug_callout,
    snap_point,
    snap_polyline,
    calculate_polyline_length,
    evaluate_column_base_shear_lug_shadow,
    SNAP_TOLERANCE_PT,
)


def test_shear_lug_callout_parsing():
    c1 = "COLUMN BASEPLATE WITH 150X150X12 SHS SHEAR LUG 100MM PROJECTION IN 200X200 GROUT KEY 70 MPA"
    p1 = parse_shear_lug_callout(c1)
    assert p1 is not None
    assert p1["lug_type"] == "SHS_BOX_LUG"
    assert p1["lug_section"] == "150x150x12SHS"
    assert p1["lug_projection_mm"] == 100.0
    assert p1["grout_key_size_mm"] == "200X200"
    assert p1["grout_strength_mpa"] == 70.0

    c2 = "WELDED 25MM THICK PL SHEAR LUG 150MM PROJECTION INTO PEDESTAL GROUT KEY"
    p2 = parse_shear_lug_callout(c2)
    assert p2 is not None
    assert p2["lug_type"] == "PLATE_SHEAR_LUG"
    assert p2["lug_section"] == "25MM PL"
    assert p2["lug_projection_mm"] == 150.0

    c3 = "SHEAR LUG 150UB14"
    p3 = parse_shear_lug_callout(c3)
    assert p3 is not None
    assert p3["lug_type"] == "UB_SECTION_LUG"
    assert p3["lug_section"] == "150UB14"

    c4 = "PLASTER FINISH WALL"
    assert parse_shear_lug_callout(c4) is None


def test_shear_lug_snapping():
    pt = (12.3, 24.8)
    snapped = snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (12.5, 25.0)

    line = [(0.0, 0.0), (0.2, 0.1), (30.0, 0.0)]
    snapped_line = snap_polyline(line, SNAP_TOLERANCE_PT)
    assert len(snapped_line) == 2
    assert snapped_line[0] == (0.0, 0.0)
    assert snapped_line[1] == (30.0, 0.0)


def test_shear_lug_polyline_length():
    pts = [(0.0, 0.0), (30.0, 40.0)]
    length = calculate_polyline_length(pts)
    assert length == pytest.approx(50.0, rel=1e-3)


def test_shear_lug_evaluation_quantities():
    callouts = [
        "SHEAR LUG 20MM PL IN 200X200 GROUT KEY",
        "BASEPLATE SHEAR LUG 150x150x12 SHS",
    ]
    polylines = [
        [(0.0, 0.0), (50.0, 0.0)],
        [(100.0, 100.0)],
    ]
    candidates = evaluate_column_base_shear_lug_shadow("SHT-STR-S401", callouts, polylines)
    assert len(candidates) == 2
    assert candidates[0].candidate_id == "SHT-STR-S401_csl_001"
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible
    assert candidates[0].lug_type == "PLATE_SHEAR_LUG"
    assert candidates[1].lug_type == "SHS_BOX_LUG"

    d = candidates[0].to_dict()
    assert d["length_pt"] == 50.0
