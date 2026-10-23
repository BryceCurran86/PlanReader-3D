"""
Unit and adversarial test suite for Source Stormwater Retention OSD Orifice Plate & Trash Screen Shadow Authority.
"""

import pytest
from pb_source_osd_orifice_trash_screen_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    OSDOrificeTrashScreenCallout,
    snap_point,
    parse_osd_orifice_trash_screen_callout,
    evaluate_osd_orifice_trash_screen_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_osd_orifice_basic():
    text = "CIVIL STORMWATER OSD DISCHARGE CONTROL PIT 75MM ORIFICE STAINLESS STEEL 316 PLATE WITH 20MM APERTURE GALV TRASH SCREEN AND OVERFLOW WEIR CLASS D ROADWAY"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 75.0
    assert parsed["orifice_plate_material"] == "STAINLESS_STEEL_316"
    assert parsed["trash_screen_type"] == "GALVANISED_MAX_20MM_APERTURE"
    assert parsed["overflow_weir_included"] is True
    assert parsed["cover_class"] == "CLASS_D_ROADWAY"
    assert parsed["anti_vortex_plate"] is False


def test_parse_wedge_wire_brass():
    text = "DCP PIT 125MM ORIFICE BRASS WITH WEDGE WIRE TRASH SCREEN AND ANTI-VORTEX BAFFLE CLASS B FOOTWAY"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 125.0
    assert parsed["orifice_plate_material"] == "BRASS"
    assert parsed["trash_screen_type"] == "STAINLESS_STEEL_WEDGE_WIRE"
    assert parsed["cover_class"] == "CLASS_B_FOOTWAY"
    assert parsed["anti_vortex_plate"] is True


def test_parse_galv_plate_perforated():
    text = "RETENTION ORIFICE 50MM DIA GALV STEEL PLATE WITH PERFORATED TRASH SCREEN"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 50.0
    assert parsed["orifice_plate_material"] == "GALVANISED_STEEL"
    assert parsed["trash_screen_type"] == "PERFORATED_PLATE"


def test_parse_unrelated():
    assert parse_osd_orifice_trash_screen_callout("DRY FIRE RISER INLET") is None
    assert parse_osd_orifice_trash_screen_callout("GAS METER ENCLOSURE") is None


def test_evaluate_osd_orifice_shadow_single():
    callouts = ["ORIFICE PLATE 100MM"]
    positions = [(10.1, 20.2)]
    results = evaluate_osd_orifice_trash_screen_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_osd_orifice_shadow_dict():
    items = [{"text": "OSD PIT 75MM ORIFICE", "position": (5.0, 7.6)}]
    results = evaluate_osd_orifice_trash_screen_shadow(items)
    assert len(results) == 1
    assert results[0].orifice_diameter_mm == 75.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_osd_orifice_shadow_no_positions():
    results = evaluate_osd_orifice_trash_screen_shadow(["DCP PIT"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_osd_orifice_shadow_safety_cap():
    huge_input = ["ORIFICE PLATE"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_osd_orifice_trash_screen_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_osd_orifice_trash_screen_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "ORIFICE PLATE 100MM", "ROOM 101"]
    results = evaluate_osd_orifice_trash_screen_shadow(items)
    assert len(results) == 1
    assert results[0].orifice_diameter_mm == 100.0


def test_on_site_detention_trigger():
    text = "ON-SITE DETENTION PIT 150MM"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 150.0


def test_no_weir_negation():
    text = "ORIFICE PLATE 100MM WITHOUT WEIR"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["overflow_weir_included"] is False


def test_default_values():
    text = "TRASH SCREEN"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 100.0
    assert parsed["orifice_plate_material"] == "STAINLESS_STEEL_316"
    assert parsed["trash_screen_type"] == "GALVANISED_MAX_20MM_APERTURE"
    assert parsed["overflow_weir_included"] is True
    assert parsed["cover_class"] == "CLASS_D_ROADWAY"
    assert parsed["anti_vortex_plate"] is False


def test_snapping_precision():
    callouts = ["OSD DISCHARGE"]
    positions = [(12.49, 13.76)]
    results = evaluate_osd_orifice_trash_screen_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_diameter_symbol():
    text = "DCP ORIFICE Ø80MM"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 80.0


def test_light_duty_cover():
    text = "OSD PIT LIGHT DUTY"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["cover_class"] == "LIGHT_DUTY"


def test_emergency_weir_keyword():
    text = "OSD WEIR WITH EMERGENCY CREST"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["overflow_weir_included"] is True


def test_invalid_item_types():
    results = evaluate_osd_orifice_trash_screen_shadow([123, None, object()])
    assert results == []


def test_detention_orifice_trigger():
    text = "DETENTION ORIFICE 60MM"
    parsed = parse_osd_orifice_trash_screen_callout(text)
    assert parsed is not None
    assert parsed["orifice_diameter_mm"] == 60.0
