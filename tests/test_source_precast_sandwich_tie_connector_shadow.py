"""Unit tests for Source Precast Concrete Insulated Sandwich Panel Tie Connector Shadow Authority."""

import pytest
from pb_source_precast_sandwich_tie_connector_shadow import (
    SandwichTieConnectorCandidate,
    snap_point,
    parse_sandwich_tie_callout,
    evaluate_precast_sandwich_tie_connector_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 14.9)) == (12.5, 15.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_sandwich_tie_callout_gfrp_tri_format():
    text = "PRECAST INSULATED PANEL TIE GFRP CONNECTOR 75/50/150 @ 400 CTS"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["connector_type"] == "GFRP_PIN_CONNECTOR"
    assert parsed["outer_wythe_thickness_mm"] == 75.0
    assert parsed["insulation_thickness_mm"] == 50.0
    assert parsed["inner_wythe_thickness_mm"] == 150.0
    assert parsed["spacing_mm"] == 400.0
    assert parsed["insulation_type"] == "PIR"


def test_parse_sandwich_tie_callout_stainless_truss_xps():
    text = "SANDWICH PANEL TIE STAINLESS STEEL TRUSS TIE WITH 80MM XPS INSULATION @ 600MM C/C"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["connector_type"] == "STAINLESS_TRUSS_TIE"
    assert parsed["insulation_type"] == "XPS"
    assert parsed["insulation_thickness_mm"] == 80.0
    assert parsed["spacing_mm"] == 600.0


def test_parse_sandwich_tie_callout_carbon_fiber_eps():
    text = "SANDWICH PANEL TIE CARBON FIBER C-GRID 100MM EPS @ 500 CTS"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["connector_type"] == "CARBON_FIBER_GRID"
    assert parsed["insulation_type"] == "EPS"
    assert parsed["insulation_thickness_mm"] == 100.0
    assert parsed["spacing_mm"] == 500.0


def test_parse_sandwich_tie_callout_thermomass():
    text = "THERMOMASS COMPOSITE TIE 80-75-175"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["connector_type"] == "GFRP_PIN_CONNECTOR"
    assert parsed["outer_wythe_thickness_mm"] == 80.0
    assert parsed["insulation_thickness_mm"] == 75.0
    assert parsed["inner_wythe_thickness_mm"] == 175.0


def test_parse_sandwich_tie_callout_cylinder_sleeve_mineral_wool():
    text = "WYTHE CONNECTOR CYLINDER SLEEVE WITH MINERAL WOOL CORE"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["connector_type"] == "CYLINDER_SLEEVE_PIN"
    assert parsed["insulation_type"] == "MINERAL_WOOL"


def test_parse_sandwich_tie_callout_unrelated():
    assert parse_sandwich_tie_callout("PRECAST HOLLOWCORE FLOOR SLAB 200MM") is None


def test_evaluate_precast_sandwich_tie_connector_shadow_single():
    callouts = ["THERMOMASS SANDWICH PANEL TIE 75/50/150 @ 400 CTS"]
    positions = [(100.2, 200.4)]
    res = evaluate_precast_sandwich_tie_connector_shadow("S-301", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "S-301_spt_001"
    assert c.sheet_id == "S-301"
    assert c.position == (100.0, 200.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_precast_sandwich_tie_connector_shadow_to_dict():
    c = SandwichTieConnectorCandidate(
        candidate_id="S-001",
        sheet_id="S-100",
        connector_type="GFRP_PIN_CONNECTOR",
        insulation_type="PIR",
        insulation_thickness_mm=50.0,
        outer_wythe_thickness_mm=75.0,
        inner_wythe_thickness_mm=150.0,
        spacing_mm=400.0,
        position=(10.0, 20.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "S-001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["position"] == (10.0, 20.0)


def test_evaluate_precast_sandwich_tie_connector_shadow_no_positions():
    callouts = ["GFRP CONNECTOR INSULATED PANEL TIE"]
    res = evaluate_precast_sandwich_tie_connector_shadow("S-302", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_precast_sandwich_tie_connector_shadow_safety_cap():
    callouts = ["SANDWICH PANEL TIE @ 400 CTS"] * 10
    res = evaluate_precast_sandwich_tie_connector_shadow("S-303", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_parse_sandwich_tie_individual_wythe_callouts():
    text = "SANDWICH WALL TIE 85MM OUTER WYTHE 60MM PIR INSULATION 180MM INNER WYTHE @ 450MM CTS"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["outer_wythe_thickness_mm"] == 85.0
    assert parsed["insulation_thickness_mm"] == 60.0
    assert parsed["inner_wythe_thickness_mm"] == 180.0
    assert parsed["spacing_mm"] == 450.0


def test_empty_callouts():
    assert evaluate_precast_sandwich_tie_connector_shadow("S-304", []) == []


def test_unrelated_callout_filtering():
    callouts = ["STRUCTURAL BEAM 310UB", "SANDWICH PANEL TIE GFRP"]
    res = evaluate_precast_sandwich_tie_connector_shadow("S-305", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "S-305_spt_002"


def test_rockwool_insulation_trigger():
    text = "SANDWICH PANEL TIE ROCKWOOL CORE @ 400 CTS"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["insulation_type"] == "MINERAL_WOOL"


def test_extruded_polystyrene_trigger():
    text = "SANDWICH PANEL TIE EXTRUDED POLYSTYRENE CORE"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["insulation_type"] == "XPS"


def test_expanded_polystyrene_trigger():
    text = "SANDWICH PANEL TIE EXPANDED POLYSTYRENE CORE"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["insulation_type"] == "EPS"


def test_fiberglass_pin_trigger():
    text = "FIBERGLASS PIN WYTHE CONNECTOR"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["connector_type"] == "GFRP_PIN_CONNECTOR"


def test_default_wythe_dimensions():
    text = "COMPOSITE TIE FOR INSULATED WALL"
    parsed = parse_sandwich_tie_callout(text)
    assert parsed is not None
    assert parsed["outer_wythe_thickness_mm"] == 75.0
    assert parsed["insulation_thickness_mm"] == 50.0
    assert parsed["inner_wythe_thickness_mm"] == 150.0
    assert parsed["spacing_mm"] == 400.0


def test_coordinate_snapping_precision():
    callouts = ["SANDWICH PANEL TIE"]
    positions = [(5.1, 7.4)]
    res = evaluate_precast_sandwich_tie_connector_shadow("S-306", callouts, positions)
    assert res[0].position == (5.0, 7.5)
