"""Unit tests for Source Acoustic Floating Floor Isolator Jack-Up Mount Shadow Authority."""

import pytest
from pb_source_acoustic_floating_floor_isolator_shadow import (
    AcousticFloatingFloorCandidate,
    snap_point,
    parse_acoustic_floating_floor_callout,
    evaluate_acoustic_floating_floor_isolator_shadow,
    SNAP_TOLERANCE_PT,
    MAX_PRIMITIVES_SAFETY_CAP,
)


def test_snap_point_basic():
    assert snap_point((2.4, 4.9)) == (2.5, 5.0)
    assert snap_point((0.0, 0.0)) == (0.0, 0.0)


def test_parse_acoustic_floating_floor_callout_spring_canister():
    text = "ACOUSTIC FLOATING SLAB 150MM CONCRETE WITH JACK-UP SPRING CANISTER 50MM AIR GAP @ 1200 CTS 3.5 HZ"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "JACK_UP_SPRING_CANISTER"
    assert parsed["floating_slab_thickness_mm"] == 150.0
    assert parsed["air_cavity_height_mm"] == 50.0
    assert parsed["grid_spacing_mm"] == 1200.0
    assert parsed["natural_frequency_hz"] == 3.5


def test_parse_acoustic_floating_floor_callout_neoprene_pad():
    text = "FLOATING FLOOR NEOPRENE FLOOR MOUNT 100MM SLAB 20MM PERIMETER BOARD 8.0 HZ"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "ELASTOMERIC_NEOPRENE_PAD"
    assert parsed["floating_slab_thickness_mm"] == 100.0
    assert parsed["perimeter_isolation_thickness_mm"] == 20.0
    assert parsed["natural_frequency_hz"] == 8.0


def test_parse_acoustic_floating_floor_callout_sylomer_mat():
    text = "FLOATING FLOOR WITH SYLOMER MAT UNDERLAY 200MM SLAB"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "POLYURETHANE_FOAM_MAT"
    assert parsed["floating_slab_thickness_mm"] == 200.0


def test_parse_acoustic_floating_floor_callout_perimeter_isolation():
    text = "PERIMETER ISOLATION BOARD 15MM FLANKING STRIP AT FLOATING SLAB"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["perimeter_isolation_thickness_mm"] == 15.0


def test_parse_acoustic_floating_floor_callout_unrelated():
    assert parse_acoustic_floating_floor_callout("CARPET TILES ON PLYWOOD UNDERLAY") is None


def test_evaluate_acoustic_floating_floor_isolator_shadow_single():
    callouts = ["JACK-UP ISOLATOR FLOATING SLAB 150MM @ 1200 CTS"]
    positions = [(120.2, 240.4)]
    res = evaluate_acoustic_floating_floor_isolator_shadow("A-601", callouts, positions)
    assert len(res) == 1
    c = res[0]
    assert c.candidate_id == "A-601_aff_001"
    assert c.sheet_id == "A-601"
    assert c.position == (120.0, 240.0)
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False


def test_evaluate_acoustic_floating_floor_isolator_shadow_dict():
    c = AcousticFloatingFloorCandidate(
        candidate_id="A-602_aff_001",
        sheet_id="A-602",
        isolator_type="JACK_UP_SPRING_CANISTER",
        floating_slab_thickness_mm=150.0,
        air_cavity_height_mm=50.0,
        perimeter_isolation_thickness_mm=20.0,
        grid_spacing_mm=1200.0,
        natural_frequency_hz=4.5,
        position=(100.0, 100.0),
    )
    d = c.to_dict()
    assert d["candidate_id"] == "A-602_aff_001"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False
    assert d["takeoff_eligible"] is False
    assert d["isolator_type"] == "JACK_UP_SPRING_CANISTER"


def test_evaluate_acoustic_floating_floor_isolator_shadow_no_positions():
    callouts = ["FLOATING SLAB ISOLATOR"]
    res = evaluate_acoustic_floating_floor_isolator_shadow("A-603", callouts)
    assert len(res) == 1
    assert res[0].position is None


def test_evaluate_acoustic_floating_floor_isolator_shadow_safety_cap():
    callouts = ["FLOATING SLAB ISOLATOR"] * 10
    res = evaluate_acoustic_floating_floor_isolator_shadow("A-604", callouts, max_primitives=4)
    assert len(res) == 4


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_PRIMITIVES_SAFETY_CAP == 20000


def test_empty_callouts():
    assert evaluate_acoustic_floating_floor_isolator_shadow("A-605", []) == []


def test_unrelated_callout_filtering():
    callouts = ["TIMBER STUD WALL", "JACK-UP MOUNT FLOATING FLOOR"]
    res = evaluate_acoustic_floating_floor_isolator_shadow("A-606", callouts)
    assert len(res) == 1
    assert res[0].candidate_id == "A-606_aff_002"


def test_regupol_underlay_trigger():
    text = "FLOATING FLOOR WITH REGUPOL MAT"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "POLYURETHANE_FOAM_MAT"


def test_spring_isolator_canister_trigger():
    text = "SPRING ISOLATOR CANISTER WITH 75MM AIR CAVITY"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["isolator_type"] == "JACK_UP_SPRING_CANISTER"
    assert parsed["air_cavity_height_mm"] == 75.0


def test_default_values():
    text = "FLOATING FLOOR"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["floating_slab_thickness_mm"] == 150.0
    assert parsed["air_cavity_height_mm"] == 50.0
    assert parsed["perimeter_isolation_thickness_mm"] == 20.0
    assert parsed["grid_spacing_mm"] == 1200.0


def test_snapping_precision():
    callouts = ["JACK-UP MOUNT"]
    positions = [(4.9, 10.1)]
    res = evaluate_acoustic_floating_floor_isolator_shadow("A-607", callouts, positions)
    assert res[0].position == (5.0, 10.0)


def test_c_slash_c_grid_spacing():
    text = "FLOATING SLAB ISOLATOR @ 1000 C/C"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["grid_spacing_mm"] == 1000.0


def test_flanking_strip_keyword():
    text = "PERIMETER ISOLATION BOARD 25MM FLANKING"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["perimeter_isolation_thickness_mm"] == 25.0


def test_void_keyword():
    text = "JACK-UP ISOLATOR 100MM VOID"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["air_cavity_height_mm"] == 100.0


def test_natural_frequency_decimal():
    text = "JACK-UP MOUNT 4.2 HZ"
    parsed = parse_acoustic_floating_floor_callout(text)
    assert parsed is not None
    assert parsed["natural_frequency_hz"] == 4.2
