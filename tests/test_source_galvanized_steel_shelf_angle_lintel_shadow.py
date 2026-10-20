"""Tests for Galvanized Steel Shelf Angle & Brickwork Lintel Shadow Authority."""

import pytest
from pb_source_galvanized_steel_shelf_angle_lintel_shadow import (
    SteelLintelCandidate,
    extract_steel_lintels,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_equal_angle_lintel():
    data = [{"id": "l1", "text": "100x100x6 EA HOT DIP GALVANIZED LINTEL L=1800", "coordinates": (100.2, 200.4)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].lintel_type == "EQUAL_ANGLE"
    assert res[0].leg1_mm == 100
    assert res[0].leg2_mm == 100
    assert res[0].thickness_mm == 6.0
    assert res[0].length_mm == 1800
    assert res[0].corrosion_protection == "HOT_DIP_GALVANIZED"
    assert res[0].min_bearing_mm == 150


def test_unequal_angle_lintel():
    data = [{"id": "l2", "text": "150x100x8 UA CAVITY LINTEL L=2400", "coordinates": (50.0, 75.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].lintel_type == "UNEQUAL_ANGLE"
    assert res[0].leg1_mm == 150
    assert res[0].leg2_mm == 100
    assert res[0].thickness_mm == 8.0
    assert res[0].length_mm == 2400


def test_shelf_angle_with_slotted_holes():
    data = [{"id": "l3", "text": "150x100x10 SHELF ANGLE WITH SLOTTED HOLE CONNECTIONS", "coordinates": (10.0, 20.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].lintel_type == "SHELF_ANGLE"
    assert res[0].is_slotted_connection is True
    assert res[0].leg1_mm == 150
    assert res[0].leg2_mm == 100
    assert res[0].thickness_mm == 10.0


def test_t_bar_brickwork_lintel():
    data = [{"id": "l4", "text": "GALVANISED T-BAR LINTEL 200x8 OVER WINDOW", "coordinates": (0.0, 0.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].lintel_type == "T_BAR"


def test_proprietary_galintel():
    data = [{"id": "l5", "text": "GALINTEL SOLID WEB PROFILE L=2100", "coordinates": (15.0, 15.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].lintel_type == "PROPRIETARY_LINTEL"
    assert res[0].length_mm == 2100


def test_proprietary_rendabar():
    data = [{"id": "l6", "text": "RENDABAR ANGLE LINTEL 1500 LG", "coordinates": (25.0, 25.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].lintel_type == "PROPRIETARY_LINTEL"
    assert res[0].length_mm == 1500


def test_custom_end_bearing():
    data = [{"id": "l7", "text": "100x100x6 EA LINTEL WITH 200MM MIN END BEARING", "coordinates": (30.0, 60.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].min_bearing_mm == 200


def test_stainless_steel_316_protection():
    data = [{"id": "l8", "text": "STAINLESS STEEL 316 GRADE SHELF ANGLE 150x100x8", "coordinates": (40.0, 80.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].corrosion_protection == "STAINLESS_STEEL_316"


def test_stainless_steel_304_protection():
    data = [{"id": "l9", "text": "GRADE 304 STAINLESS BRICK LINTEL", "coordinates": (50.0, 100.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].corrosion_protection == "STAINLESS_STEEL_304"


def test_painted_primer_only():
    data = [{"id": "l10", "text": "STEEL ANGLE OVER OPENING PRIMER ONLY", "coordinates": (12.0, 24.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].corrosion_protection == "STANDARD"


def test_negative_timber_lvl():
    data = [{"id": "n1", "text": "LVL 240x45 TIMBER LINTEL", "coordinates": (0.0, 0.0)}]
    assert len(extract_steel_lintels(data)) == 0


def test_negative_glulam():
    data = [{"id": "n2", "text": "GLULAM BEAM GL17 300x65", "coordinates": (0.0, 0.0)}]
    assert len(extract_steel_lintels(data)) == 0


def test_negative_precast_lintel():
    data = [{"id": "n3", "text": "PRECAST CONCRETE LINTEL 200x100", "coordinates": (0.0, 0.0)}]
    assert len(extract_steel_lintels(data)) == 0


def test_negative_curtain_wall_transom():
    data = [{"id": "n4", "text": "CURTAIN WALL TRANSOM EXTRUSION", "coordinates": (0.0, 0.0)}]
    assert len(extract_steel_lintels(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((14.9, 29.8), tolerance=2.5)
    assert pt == (15.0, 30.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "100x100x6 EA LINTEL", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_steel_lintels(items, max_primitives=40)
    assert len(res) == 40


def test_candidate_guardrails_default():
    candidate = SteelLintelCandidate(
        item_id="cand_1",
        lintel_type="EQUAL_ANGLE",
        leg1_mm=100,
        leg2_mm=100,
        thickness_mm=6.0,
        length_mm=1800,
        min_bearing_mm=150,
        corrosion_protection="HOT_DIP_GALVANIZED",
        is_slotted_connection=False,
        coordinates=(10.0, 20.0),
        raw_text="100x100x6 EA LINTEL",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = SteelLintelCandidate(
        item_id="cand_2",
        lintel_type="UNEQUAL_ANGLE",
        leg1_mm=150,
        leg2_mm=100,
        thickness_mm=8.0,
        length_mm=2100,
        min_bearing_mm=150,
        corrosion_protection="HOT_DIP_GALVANIZED",
        is_slotted_connection=False,
        coordinates=(0.0, 0.0),
        raw_text="150x100x8 UA LINTEL",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "l11", "text": "100x100x6 EA LINTEL L=1800", "coordinates": (30.0, 40.0)}]
    res = extract_steel_lintels(data)
    d = res[0].to_dict()
    assert d["lintel_type"] == "EQUAL_ANGLE"
    assert d["leg1_mm"] == 100
    assert d["thickness_mm"] == 6.0
    assert d["status"] == "CANDIDATE"


def test_decimal_thickness_parsing():
    data = [{"id": "l12", "text": "100x100x9.5 EA LINTEL L=1500", "coordinates": (10.0, 10.0)}]
    res = extract_steel_lintels(data)
    assert len(res) == 1
    assert res[0].thickness_mm == 9.5
