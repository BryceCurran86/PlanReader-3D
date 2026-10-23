"""
Unit and adversarial test suite for Source Mechanical Vibration Spring Isolator & Inertia Base Shadow Authority.
"""

import pytest
from pb_source_vibration_spring_isolator_inertia_base_shadow import (
    VibrationSpringIsolatorCallout,
    SourceVibrationSpringIsolatorInertiaBaseShadowAuthority,
    parse_vibration_spring_isolator_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_spring_inertia_base():
    text = "PRIMARY CHW PUMP: SEISMIC RESTRAINED SPRING MOUNT, 50MM STATIC DEFLECTION, 1200 KG CAPACITY, WITH 200MM DEEP REINFORCED CONCRETE INERTIA BASE, 15MM NEOPRENE ACOUSTIC PAD"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["isolator_type"] == "SEISMIC_RESTRAINED_SPRING_MOUNT"
    assert res["static_deflection_mm"] == 50.0
    assert res["load_capacity_kg"] == 1200.0
    assert res["inertia_base_included"] is True
    assert res["inertia_base_depth_mm"] == 200.0
    assert res["neoprene_pad_thickness_mm"] == 15.0


def test_parse_housed_spring():
    text = "CHILLER ISOLATION: HOUSED SPRING ISOLATOR WITH SNUBBER, 25MM DEFLECTION, 2500 KG"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["isolator_type"] == "HOUSED_SPRING_ISOLATOR_WITH_SNUBBER"
    assert res["static_deflection_mm"] == 25.0
    assert res["load_capacity_kg"] == 2500.0
    assert res["inertia_base_included"] is False


def test_parse_open_spring_kn():
    text = "COOLING TOWER: OPEN SPRING ISOLATOR 75MM STATIC DEFLECTION, 15 KN"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["isolator_type"] == "OPEN_SPRING_ISOLATOR"
    assert res["static_deflection_mm"] == 75.0
    assert abs(res["load_capacity_kg"] - 1529.5) < 0.5


def test_parse_defaults():
    text = "SPRING ISOLATOR"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["isolator_type"] == "OPEN_SPRING_ISOLATOR"
    assert res["static_deflection_mm"] == 25.0
    assert res["load_capacity_kg"] == 500.0


def test_parse_non_isolator():
    text = "LIGHTING TRACK SURFACE MOUNTED"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(81.1, 144.9, snap_tol=2.5)
    assert pt == (80.0, 145.0)


def test_authority_processing_dedup():
    auth = SourceVibrationSpringIsolatorInertiaBaseShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SPRING ISOLATOR 500 KG", (10.0, 20.0)),
        ("SPRING ISOLATOR 500 KG", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceVibrationSpringIsolatorInertiaBaseShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SPRING ISOLATOR 500 KG", (10.0, 20.0)),
        ("SPRING ISOLATOR 500 KG", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceVibrationSpringIsolatorInertiaBaseShadowAuthority()
    oversized = [("SPRING ISOLATOR", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceVibrationSpringIsolatorInertiaBaseShadowAuthority()
    res = auth.process_callouts([("SPRING ISOLATOR", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_vibration_spring_isolator_callout("") is None


def test_zero_tolerance_snap():
    pt = snap_point(12.34, 56.78, snap_tol=0.0)
    assert pt == (12.34, 56.78)


def test_frozen_dataclass_immutability():
    callout = VibrationSpringIsolatorCallout(
        raw_text="text",
        isolator_type="SPRING",
        static_deflection_mm=25.0,
        load_capacity_kg=500.0,
        inertia_base_included=False,
        inertia_base_depth_mm=0.0,
        neoprene_pad_thickness_mm=10.0,
    )
    with pytest.raises(Exception):
        callout.load_capacity_kg = 1000.0  # type: ignore


def test_different_capacities_same_point():
    auth = SourceVibrationSpringIsolatorInertiaBaseShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SPRING ISOLATOR 500 KG", (10.0, 20.0)),
        ("SPRING ISOLATOR 1500 KG", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_inertia_frame_trigger():
    text = "VIBRATION ISOLATOR WITH C-CHANNEL INERTIA FRAME 150MM"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["inertia_base_included"] is True
    assert res["inertia_base_depth_mm"] == 150.0


def test_vibration_mount_trigger():
    text = "VIBRATION MOUNT 350 KG WITH 10MM RUBBER PAD"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["load_capacity_kg"] == 350.0
    assert res["neoprene_pad_thickness_mm"] == 10.0


def test_seismic_spring_trigger():
    text = "SEISMIC SPRING 800 KG"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["isolator_type"] == "SEISMIC_RESTRAINED_SPRING_MOUNT"
    assert res["load_capacity_kg"] == 800.0


def test_static_deflection_trigger():
    text = "SPRING MOUNT WITH 50MM STATIC DEFLECTION"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["static_deflection_mm"] == 50.0


def test_snubber_in_text():
    text = "VIBRATION ISOLATOR WITH SEISMIC SNUBBER 600 KG"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["isolator_type"] == "SEISMIC_RESTRAINED_SPRING_MOUNT"


def test_c_channel_frame():
    text = "INERTIA BASE WITH 250MM C-CHANNEL FRAME"
    res = parse_vibration_spring_isolator_callout(text)
    assert res is not None
    assert res["inertia_base_depth_mm"] == 250.0
