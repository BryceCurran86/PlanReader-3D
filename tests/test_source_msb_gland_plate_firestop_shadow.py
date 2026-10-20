"""
Unit and adversarial test suite for Source Electrical Main Switchboard Cable Entry Gland Plate & Firestop Shadow Authority.
"""

import pytest
from pb_source_msb_gland_plate_firestop_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    MSBGlandPlateFirestopCallout,
    snap_point,
    parse_msb_gland_plate_firestop_callout,
    evaluate_msb_gland_plate_firestop_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_msb_gland_plate_basic():
    text = "ELECTRICAL MSB CABLE ENTRY 5MM ALUMINIUM NON-MAGNETIC GLAND PLATE BOTTOM ENTRY WITH ROXTEC CABLE TRANSIT FRAME IP54"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["gland_plate_material"] == "ALUMINIUM_NON_MAGNETIC"
    assert parsed["plate_thickness_mm"] == 5.0
    assert parsed["entry_orientation"] == "BOTTOM_CABLE_ENTRY"
    assert parsed["firestop_transit_type"] == "MODULAR_TRANSIT_FRAME"
    assert parsed["ip_rating"] == "IP54"
    assert parsed["eddy_current_slots_required"] is False


def test_parse_brass_top_entry_ip65():
    text = "MDB GLAND PLATE 3MM BRASS TOP ENTRY WITH CABLE GLANDS IP65"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["gland_plate_material"] == "BRASS_NON_MAGNETIC"
    assert parsed["plate_thickness_mm"] == 3.0
    assert parsed["entry_orientation"] == "TOP_CABLE_ENTRY"
    assert parsed["firestop_transit_type"] == "CABLE_GLANDS_IP65"
    assert parsed["ip_rating"] == "IP65"


def test_parse_mild_steel_slotted():
    text = "SWITCHBOARD CABLE ENTRY 4MM MILD STEEL GLAND PLATE WITH EDDY CURRENT SLOTS AND INTUMESCENT PILLOWS"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["gland_plate_material"] == "MILD_STEEL_MAGNETIC"
    assert parsed["eddy_current_slots_required"] is True
    assert parsed["firestop_transit_type"] == "INTUMESCENT_FIRESTOP_PILLOWS"


def test_parse_unrelated():
    assert parse_msb_gland_plate_firestop_callout("ALUMINIUM BALCONY SCREEN") is None
    assert parse_msb_gland_plate_firestop_callout("CONCRETE STAIR NOSING") is None


def test_evaluate_msb_gland_shadow_single():
    callouts = ["GLAND PLATE 5MM ALUMINIUM"]
    positions = [(10.1, 20.2)]
    results = evaluate_msb_gland_plate_firestop_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_msb_gland_shadow_dict():
    items = [{"text": "MSB CABLE ENTRY ROXTEC", "position": (5.0, 7.6)}]
    results = evaluate_msb_gland_plate_firestop_shadow(items)
    assert len(results) == 1
    assert results[0].firestop_transit_type == "MODULAR_TRANSIT_FRAME"
    assert results[0].position == (5.0, 7.5)


def test_evaluate_msb_gland_shadow_no_positions():
    results = evaluate_msb_gland_plate_firestop_shadow(["SWITCHBOARD FIRESTOP"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_msb_gland_shadow_safety_cap():
    huge_input = ["GLAND PLATE"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_msb_gland_plate_firestop_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_msb_gland_plate_firestop_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "GLAND PLATE 5MM", "ROOM 101"]
    results = evaluate_msb_gland_plate_firestop_shadow(items)
    assert len(results) == 1
    assert results[0].gland_plate_material == "ALUMINIUM_NON_MAGNETIC"


def test_composite_bakelite_material():
    text = "SWITCHBOARD GLAND 6MM BAKELITE COMPOSITE"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["gland_plate_material"] == "COMPOSITE_BAKELITE"
    assert parsed["plate_thickness_mm"] == 6.0


def test_mct_frame_trigger():
    text = "CABLE ENTRY GLAND WITH MCT FRAME"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["firestop_transit_type"] == "MODULAR_TRANSIT_FRAME"


def test_default_values():
    text = "NON-MAGNETIC GLAND"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["gland_plate_material"] == "ALUMINIUM_NON_MAGNETIC"
    assert parsed["plate_thickness_mm"] == 5.0
    assert parsed["entry_orientation"] == "BOTTOM_CABLE_ENTRY"
    assert parsed["ip_rating"] == "IP54"


def test_snapping_precision():
    callouts = ["CABLE TRANSIT"]
    positions = [(12.49, 13.76)]
    results = evaluate_msb_gland_plate_firestop_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_overhead_entry():
    text = "GLAND PLATE OVERHEAD CABLE ENTRY"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["entry_orientation"] == "TOP_CABLE_ENTRY"


def test_ip56_rating():
    text = "MSB CABLE ENTRY IP56"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["ip_rating"] == "IP56"


def test_firestop_mortar_trigger():
    text = "SWITCHBOARD CABLE ENTRY WITH FIRESTOP MORTAR"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["firestop_transit_type"] == "INTUMESCENT_FIRESTOP_PILLOWS"


def test_invalid_item_types():
    results = evaluate_msb_gland_plate_firestop_shadow([123, None, object()])
    assert results == []


def test_eddy_current_gland_trigger():
    text = "EDDY CURRENT GLAND 6MM ALUM"
    parsed = parse_msb_gland_plate_firestop_callout(text)
    assert parsed is not None
    assert parsed["plate_thickness_mm"] == 6.0
