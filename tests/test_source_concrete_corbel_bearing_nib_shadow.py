"""Unit tests for Source Structural Concrete Corbels & Precast Beam Bearing Nibs Shadow Authority."""

import pytest
from pb_source_concrete_corbel_bearing_nib_shadow import (
    ConcreteCorbelCandidate,
    snap_point,
    parse_concrete_corbel_callout,
    evaluate_concrete_corbel_bearing_nib_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((12.4, 14.9)) == (12.5, 15.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_concrete_corbel_callout_column_elastomeric():
    text = "COLUMN CORBEL 350MM PROJECTION 500MM DEEP 350MM WIDE 3-N24 TIE N10 @ 100 CTS ELASTOMERIC PAD"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["corbel_configuration"] == "COLUMN_CORBEL"
    assert parsed["projection_length_mm"] == 350.0
    assert parsed["root_depth_mm"] == 500.0
    assert parsed["width_mm"] == 350.0
    assert parsed["primary_tie_reinforcement"] == "3-N24"
    assert parsed["bearing_pad_type"] == "ELASTOMERIC_PAD"


def test_parse_concrete_corbel_callout_dapped_beam_nib_steel():
    text = "PRECAST DAPPED END BEAM NIB 300MM PROJ 400MM DEPTH 4-N20 STEEL BEARING PLATE"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["corbel_configuration"] == "DAPPED_BEAM_NIB"
    assert parsed["projection_length_mm"] == 300.0
    assert parsed["root_depth_mm"] == 400.0
    assert parsed["primary_tie_reinforcement"] == "4-N20"
    assert parsed["bearing_pad_type"] == "STEEL_BEARING_PLATE"


def test_parse_concrete_corbel_callout_wall_bracket_ptfe():
    text = "WALL BRACKET CONCRETE CORBEL PTFE SLIDING PAD 400MM PROJECTION"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["corbel_configuration"] == "WALL_CORBEL"
    assert parsed["projection_length_mm"] == 400.0
    assert parsed["bearing_pad_type"] == "PTFE_SLIDING_PAD"


def test_parse_concrete_corbel_callout_precast_bearing_nib():
    text = "PRECAST BEARING NIB DETAIL"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["corbel_configuration"] == "DAPPED_BEAM_NIB"


def test_parse_concrete_corbel_callout_unrelated():
    assert parse_concrete_corbel_callout("PRECAST HOLLOWCORE FLOOR SLAB 200MM") is None


def test_evaluate_concrete_corbel_bearing_nib_shadow_single():
    callouts = ["COLUMN CORBEL 350MM PROJECTION 500MM DEEP 3-N24"]
    positions = [(100.2, 200.4)]
    res = evaluate_concrete_corbel_bearing_nib_shadow("S-401", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "S-401_cbn_001"
    assert c.sheet_id == "S-401"
    assert c.position == (100.0, 200.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_concrete_corbel_bearing_nib_shadow_dict():
    c = ConcreteCorbelCandidate(
        candidate_id="S-402_cbn_001",
        sheet_id="S-402",
        corbel_configuration="COLUMN_CORBEL",
        projection_length_mm=350.0,
        root_depth_mm=500.0,
        width_mm=350.0,
        primary_tie_reinforcement="3-N24",
        horizontal_stirrups_description="N10 @ 100 CTS",
        bearing_pad_type="ELASTOMERIC_PAD",
        position=(10.0, 20.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "S-402_cbn_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["corbel_configuration"] == "COLUMN_CORBEL"


def test_evaluate_concrete_corbel_bearing_nib_shadow_no_positions():
    callouts = ["CONCRETE CORBEL"]
    res = evaluate_concrete_corbel_bearing_nib_shadow("S-403", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_concrete_corbel_bearing_nib_shadow_safety_cap():
    callouts = ["CONCRETE CORBEL"] * 10
    res = evaluate_concrete_corbel_bearing_nib_shadow("S-404", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_concrete_corbel_bearing_nib_shadow("S-405", []) == []


def test_unrelated_callout_filtering():
    callouts = ["TIMBER STUD", "COLUMN CORBEL 300MM"]
    res = evaluate_concrete_corbel_bearing_nib_shadow("S-406", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "S-406_cbn_002"


def test_outstand_keyword():
    text = "CONCRETE CORBEL 300MM OUTSTAND"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["projection_length_mm"] == 300.0


def test_root_depth_keyword():
    text = "CONCRETE CORBEL 600MM ROOT DEPTH"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["root_depth_mm"] == 600.0


def test_default_values():
    text = "CONCRETE CORBEL"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["corbel_configuration"] == "COLUMN_CORBEL"
    assert parsed["projection_length_mm"] == 300.0
    assert parsed["root_depth_mm"] == 450.0
    assert parsed["width_mm"] == 350.0
    assert parsed["primary_tie_reinforcement"] == "3-N24"
    assert parsed["bearing_pad_type"] == "ELASTOMERIC_PAD"


def test_snapping_precision():
    callouts = ["CONCRETE CORBEL"]
    positions = [(4.8, 9.9)]
    res = evaluate_concrete_corbel_bearing_nib_shadow("S-407", callouts, positions)
    assert res[0].position == (5.0, 10.0)


def test_precast_corbel_trigger():
    text = "PRECAST CORBEL WITH 4-N28"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["primary_tie_reinforcement"] == "4-N28"


def test_corbel_detail_trigger():
    text = "CORBEL DETAIL 350MM PROJECTION"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["projection_length_mm"] == 350.0


def test_stirrup_at_keyword():
    text = "CONCRETE CORBEL N12 @ 120"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert "N12" in parsed["horizontal_stirrups_description"]
    assert "120" in parsed["horizontal_stirrups_description"]


def test_sliding_pad_keyword():
    text = "CONCRETE CORBEL WITH SLIDING PAD"
    parsed = parse_concrete_corbel_callout(text)
    assert parsed is not None
    assert parsed["bearing_pad_type"] == "PTFE_SLIDING_PAD"
