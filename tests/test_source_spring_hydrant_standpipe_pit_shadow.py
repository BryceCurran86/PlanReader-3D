"""
Unit and adversarial test suite for Source Underground Fire Hydrant Spring Hydrant & Standpipe Pit Shadow Authority.
"""

import pytest
from pb_source_spring_hydrant_standpipe_pit_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SpringHydrantStandpipePitCallout,
    snap_point,
    parse_spring_hydrant_standpipe_pit_callout,
    evaluate_spring_hydrant_standpipe_pit_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_spring_hydrant_basic():
    text = "CIVIL UNDERGROUND FIRE HYDRANT PIT DN100 SPRING VALVE AS 3952 IN PRECAST CONCRETE PIT WITH CLASS D ROADWAY COVER AND GRAVEL SOAKAWAY"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["hydrant_valve_type"] == "SPRING_VALVE_AS3952"
    assert parsed["main_diameter_mm"] == 100.0
    assert parsed["pit_box_material"] == "PRECAST_CONCRETE"
    assert parsed["surface_cover_class"] == "CLASS_D_ROADWAY"
    assert parsed["drainage_type"] == "GRAVEL_SOAKAWAY"
    assert parsed["cover_marking"] == "FH_FIRE_HYDRANT"


def test_parse_screw_down_polymer():
    text = "FH PIT SCREW DOWN HYDRANT DN150 POLYMER COMPOSITE PIT WITH CLASS B FOOTWAY COVER"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["hydrant_valve_type"] == "SCREW_DOWN_HYDRANT"
    assert parsed["main_diameter_mm"] == 150.0
    assert parsed["pit_box_material"] == "POLYMER_COMPOSITE"
    assert parsed["surface_cover_class"] == "CLASS_B_FOOTWAY"


def test_parse_sluice_valve_sump():
    text = "STANDPIPE PIT SLUICE VALVE HYDRANT 150MM WITH DRAINAGE SUMP"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["hydrant_valve_type"] == "SLUICE_VALVE_HYDRANT"
    assert parsed["main_diameter_mm"] == 150.0
    assert parsed["drainage_type"] == "SUMP_DRAIN"


def test_parse_unrelated():
    assert parse_spring_hydrant_standpipe_pit_callout("SANITARY SEWER MANHOLE") is None
    assert parse_spring_hydrant_standpipe_pit_callout("ELECTRICAL CABLE TRENCH") is None


def test_evaluate_spring_hydrant_shadow_single():
    callouts = ["UNDERGROUND HYDRANT DN100"]
    positions = [(10.1, 20.2)]
    results = evaluate_spring_hydrant_standpipe_pit_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_spring_hydrant_shadow_dict():
    items = [{"text": "SPRING HYDRANT DN150", "position": (5.0, 7.6)}]
    results = evaluate_spring_hydrant_standpipe_pit_shadow(items)
    assert len(results) == 1
    assert results[0].main_diameter_mm == 150.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_spring_hydrant_shadow_no_positions():
    results = evaluate_spring_hydrant_standpipe_pit_shadow(["FH IN PIT"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_spring_hydrant_shadow_safety_cap():
    huge_input = ["SPRING HYDRANT"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_spring_hydrant_standpipe_pit_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_spring_hydrant_standpipe_pit_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "SPRING HYDRANT DN100", "ROOM 101"]
    results = evaluate_spring_hydrant_standpipe_pit_shadow(items)
    assert len(results) == 1
    assert results[0].main_diameter_mm == 100.0


def test_millcock_hydrant_trigger():
    text = "MILLCOCK HYDRANT IN ROADWAY"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["surface_cover_class"] == "CLASS_D_ROADWAY"


def test_ground_hydrant_trigger():
    text = "GROUND HYDRANT DN100 IN VERGE"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["surface_cover_class"] == "CLASS_B_FOOTWAY"


def test_default_values():
    text = "STANDPIPE HYDRANT"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["hydrant_valve_type"] == "SPRING_VALVE_AS3952"
    assert parsed["main_diameter_mm"] == 100.0
    assert parsed["pit_box_material"] == "CAST_IRON_SURROUND"
    assert parsed["surface_cover_class"] == "CLASS_D_ROADWAY"
    assert parsed["drainage_type"] == "GRAVEL_SOAKAWAY"


def test_snapping_precision():
    callouts = ["FIRE HYDRANT PIT"]
    positions = [(12.49, 13.76)]
    results = evaluate_spring_hydrant_standpipe_pit_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_dn80_hydrant():
    text = "SPRING HYDRANT DN80"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["main_diameter_mm"] == 80.0


def test_trafficable_carpark():
    text = "FH PIT CARPARK TRAFFICABLE"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["surface_cover_class"] == "CLASS_D_ROADWAY"


def test_diameter_symbol():
    text = "SPRING HYDRANT Ø150"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["main_diameter_mm"] == 150.0


def test_invalid_item_types():
    results = evaluate_spring_hydrant_standpipe_pit_shadow([123, None, object()])
    assert results == []


def test_in_ground_hydrant_trigger():
    text = "IN-GROUND HYDRANT DN100"
    parsed = parse_spring_hydrant_standpipe_pit_callout(text)
    assert parsed is not None
    assert parsed["hydrant_valve_type"] == "SPRING_VALVE_AS3952"
