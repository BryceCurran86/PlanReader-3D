"""
Unit and adversarial test suite for Source Hydronic Heating Chilled Water Air Dirt Separator Magnetic Filter Shadow Authority.
"""

import pytest
from pb_source_hydronic_air_dirt_separator_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    HydronicAirDirtSeparatorCallout,
    snap_point,
    parse_hydronic_air_dirt_separator_callout,
    evaluate_hydronic_air_dirt_separator_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_chw_air_dirt_separator_basic():
    text = "MECHANICAL PLANTROOM CHW AIR DIRT SEPARATOR DN150 FLANGED WITH NEODYMIUM MAGNETIC DIRT FILTER AND REMOVABLE INSULATION JACKET PN16"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["service_system"] == "CHILLED_WATER_CHW"
    assert parsed["connection_diameter_mm"] == 150.0
    assert parsed["separation_technology"] == "COMBINED_MICROBUBBLE_AND_DIRT"
    assert parsed["magnetic_core_included"] is True
    assert parsed["pressure_rating"] == "PN16"
    assert parsed["insulation_jacket_type"] == "REMOVABLE_INSULATION_JACKET"


def test_parse_hhw_air_separator_high_pressure():
    text = "BOILER HHW AIR SEPARATOR DN100 PN25 WITH PRE-INSULATED JACKET"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["service_system"] == "HEATING_HOT_WATER_HHW"
    assert parsed["connection_diameter_mm"] == 100.0
    assert parsed["pressure_rating"] == "PN25"
    assert parsed["insulation_jacket_type"] == "PRE_INSULATED_FACTORY"


def test_parse_cw_sludge_filter():
    text = "COOLING TOWER CONDENSER WATER DIRT SEPARATOR DN200 PN10 BARE VESSEL WITHOUT MAGNET"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["service_system"] == "CONDENSER_WATER_CW"
    assert parsed["connection_diameter_mm"] == 200.0
    assert parsed["pressure_rating"] == "PN10"
    assert parsed["insulation_jacket_type"] == "BARE_VESSEL"
    assert parsed["magnetic_core_included"] is False


def test_parse_unrelated():
    assert parse_hydronic_air_dirt_separator_callout("ALUMINIUM BALCONY HANDRAIL") is None
    assert parse_hydronic_air_dirt_separator_callout("CARPET TILES") is None


def test_evaluate_air_dirt_shadow_single():
    callouts = ["AIR DIRT SEPARATOR DN100"]
    positions = [(10.1, 20.2)]
    results = evaluate_hydronic_air_dirt_separator_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_air_dirt_shadow_dict():
    items = [{"text": "SPIROVENT DN150", "position": (5.0, 7.6)}]
    results = evaluate_hydronic_air_dirt_separator_shadow(items)
    assert len(results) == 1
    assert results[0].connection_diameter_mm == 150.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_air_dirt_shadow_no_positions():
    results = evaluate_hydronic_air_dirt_separator_shadow(["MAGNETIC DIRT FILTER"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_air_dirt_shadow_safety_cap():
    huge_input = ["AIR DIRT SEPARATOR"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_hydronic_air_dirt_separator_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_hydronic_air_dirt_separator_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "AIR DIRT SEPARATOR DN100", "ROOM 101"]
    results = evaluate_hydronic_air_dirt_separator_shadow(items)
    assert len(results) == 1
    assert results[0].connection_diameter_mm == 100.0


def test_microbubble_deaerator_trigger():
    text = "MICROBUBBLE DEAERATOR DN80"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["connection_diameter_mm"] == 80.0


def test_dirt_only_technology():
    text = "HYDRONIC SEPARATOR DIRT ONLY DN100"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["separation_technology"] == "MAGNETIC_DIRT_ONLY"


def test_default_values():
    text = "AIR & DIRT SEPARATOR"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["service_system"] == "CHILLED_WATER_CHW"
    assert parsed["connection_diameter_mm"] == 100.0
    assert parsed["separation_technology"] == "COMBINED_MICROBUBBLE_AND_DIRT"
    assert parsed["magnetic_core_included"] is True
    assert parsed["pressure_rating"] == "PN16"
    assert parsed["insulation_jacket_type"] == "REMOVABLE_INSULATION_JACKET"


def test_snapping_precision():
    callouts = ["MAGNETIC SLUDGE FILTER"]
    positions = [(12.49, 13.76)]
    results = evaluate_hydronic_air_dirt_separator_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_dn50_connection():
    text = "CHW AIR SEPARATOR DN50"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["connection_diameter_mm"] == 50.0


def test_air_only_deaerator():
    text = "SPIROVENT AIR ONLY DN65"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["separation_technology"] == "AIR_DEAERATOR_ONLY"
    assert parsed["connection_diameter_mm"] == 65.0


def test_diameter_symbol():
    text = "AIR DIRT SEPARATOR Ø125"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["connection_diameter_mm"] == 125.0


def test_invalid_item_types():
    results = evaluate_hydronic_air_dirt_separator_shadow([123, None, object()])
    assert results == []


def test_hydronic_air_dirt_trigger():
    text = "HYDRONIC AIR DIRT DN100"
    parsed = parse_hydronic_air_dirt_separator_callout(text)
    assert parsed is not None
    assert parsed["connection_diameter_mm"] == 100.0
