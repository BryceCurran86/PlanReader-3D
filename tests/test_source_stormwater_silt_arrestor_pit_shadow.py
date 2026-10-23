"""
Unit and adversarial test suite for Source Civil Stormwater Silt Arrestor Pit & Ductile Iron Grate Shadow Authority.
"""

import pytest
from pb_source_stormwater_silt_arrestor_pit_shadow import (
    StormwaterSiltArrestorPitCallout,
    SourceStormwaterSiltArrestorPitShadowAuthority,
    parse_stormwater_silt_arrestor_pit_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_silt_pit():
    text = "CIVIL STORMWATER: 900X900 PRECAST CONCRETE SILT ARRESTOR PIT, 450MM SUMP BELOW INVERT, CLASS D HEAVY DUTY ROADWAY DUCTILE IRON GRATE WITH SUBMERGED BAFFLE WEIR HOOD"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["pit_type"] == "PRECAST_CONCRETE_SILT_PIT"
    assert res["internal_length_mm"] == 900.0
    assert res["internal_width_mm"] == 900.0
    assert res["sump_depth_below_invert_mm"] == 450.0
    assert res["grate_load_class"] == "CLASS_D_HEAVY_DUTY_ROADWAY"
    assert res["baffle_weir_included"] is True


def test_parse_carpark_class_b():
    text = "CAR PARK DRAINAGE: 600X600 SILT PIT, 300MM SUMP, CLASS B CAR PARK GRATE"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["internal_length_mm"] == 600.0
    assert res["internal_width_mm"] == 600.0
    assert res["sump_depth_below_invert_mm"] == 300.0
    assert res["grate_load_class"] == "CLASS_B_CAR_PARK"
    assert res["baffle_weir_included"] is False


def test_parse_polyethylene_silt_trap():
    text = "POLYETHYLENE SILT TRAP 450X450 WITH PEDESTRIAN CLASS A GRATE"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["pit_type"] == "POLYETHYLENE_SILT_ARRESTOR"
    assert res["internal_length_mm"] == 450.0
    assert res["internal_width_mm"] == 450.0
    assert res["grate_load_class"] == "CLASS_A_PEDESTRIAN"


def test_parse_insitu_concrete():
    text = "IN-SITU CONCRETE SEDIMENT PIT 1200X1200, 600MM SILT STORAGE"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["pit_type"] == "CAST_IN_SITU_SEDIMENT_SUMP_PIT"
    assert res["internal_length_mm"] == 1200.0
    assert res["internal_width_mm"] == 1200.0
    assert res["sump_depth_below_invert_mm"] == 600.0


def test_parse_defaults():
    text = "STORMWATER SILT PIT"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["internal_length_mm"] == 600.0
    assert res["internal_width_mm"] == 600.0
    assert res["sump_depth_below_invert_mm"] == 300.0
    assert res["grate_load_class"] == "CLASS_D_HEAVY_DUTY_ROADWAY"


def test_parse_non_silt_pit():
    text = "SEWER GREASE INTERCEPTOR"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(35.2, 89.8, snap_tol=2.5)
    assert pt == (35.0, 90.0)


def test_authority_processing_dedup():
    auth = SourceStormwaterSiltArrestorPitShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SILT PIT 600X600", (10.0, 20.0)),
        ("SILT PIT 600X600", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceStormwaterSiltArrestorPitShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SILT PIT 600X600", (10.0, 20.0)),
        ("SILT PIT 600X600", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceStormwaterSiltArrestorPitShadowAuthority()
    oversized = [("SILT PIT", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceStormwaterSiltArrestorPitShadowAuthority()
    res = auth.process_callouts([("SILT PIT", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_stormwater_silt_arrestor_pit_callout("") is None


def test_zero_tolerance_snap():
    pt = snap_point(18.18, 36.36, snap_tol=0.0)
    assert pt == (18.18, 36.36)


def test_frozen_dataclass_immutability():
    callout = StormwaterSiltArrestorPitCallout(
        raw_text="text",
        pit_type="PRECAST",
        internal_length_mm=600.0,
        internal_width_mm=600.0,
        sump_depth_below_invert_mm=300.0,
        grate_load_class="CLASS_D",
        baffle_weir_included=True,
    )
    with pytest.raises(Exception):
        callout.internal_length_mm = 900.0  # type: ignore


def test_different_classes_same_point():
    auth = SourceStormwaterSiltArrestorPitShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SILT PIT 600X600 CLASS B", (10.0, 20.0)),
        ("SILT PIT 600X600 CLASS D", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_silt_box_trigger():
    text = "SEDIMENT TRAP 450X450 WITH TRASH SCREEN"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["internal_length_mm"] == 450.0
    assert res["baffle_weir_included"] is True


def test_sump_pit_trigger():
    text = "STORMWATER SUMP PIT 900X900, 500MM SUMP"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["sump_depth_below_invert_mm"] == 500.0


def test_oil_trap_baffle():
    text = "SILT ARRESTOR PIT WITH OIL TRAP HOOD"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["baffle_weir_included"] is True


def test_class_c_maps_to_b():
    text = "SILT PIT 600X600 CLASS C"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["grate_load_class"] == "CLASS_B_CAR_PARK"


def test_light_duty_grate():
    text = "SEDIMENT PIT 450X450 LIGHT DUTY"
    res = parse_stormwater_silt_arrestor_pit_callout(text)
    assert res is not None
    assert res["grate_load_class"] == "CLASS_B_CAR_PARK"
