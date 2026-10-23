"""
Unit and adversarial test suite for Source Acoustic Gypsum Plasterboard Resilient Mount Wall Furring Channel Shadow Authority.
"""

import pytest
from pb_source_resilient_mount_furring_channel_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    ResilientMountFurringChannelCallout,
    snap_point,
    parse_resilient_mount_furring_channel_callout,
    evaluate_resilient_mount_furring_channel_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_resilmount_basic():
    text = "INTER-TENANCY WALL RESILMOUNT ACOUSTIC CLIP WITH 28MM FURRING CHANNEL AT 600MM CTS 25MM CAVITY GLASSWOOL BATTS 2X13MM SOUNDSTOP"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "THERMOPLASTIC_RUBBER_CLIP"
    assert parsed["furring_channel_depth_mm"] == 28.0
    assert parsed["channel_spacing_cts_mm"] == 600.0
    assert parsed["cavity_depth_mm"] == 25.0
    assert parsed["insulation_type"] == "GLASSWOOL_ACOUSTIC_BATTS"
    assert "2x13mm" in parsed["lining_configuration"]


def test_parse_spring_mount_rockwool():
    text = "CINEMA PARTITION STEEL SPRING MOUNT 16MM HAT TRACK AT 450MM CTS 50MM CAVITY ROCKWOOL BATTS 2X16MM FYRCHEK"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "STEEL_SPRING_MOUNT"
    assert parsed["furring_channel_depth_mm"] == 16.0
    assert parsed["channel_spacing_cts_mm"] == 450.0
    assert parsed["cavity_depth_mm"] == 50.0
    assert parsed["insulation_type"] == "ROCKWOOL_ACOUSTIC_BATTS"
    assert "2x16mm" in parsed["lining_configuration"]


def test_parse_resilient_channel_direct():
    text = "ACOUSTIC WALL RESILIENT CHANNEL RC-1 16MM WITH POLYESTER BATTS"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "DIRECT_RESILIENT_CHANNEL"
    assert parsed["insulation_type"] == "POLYESTER_ACOUSTIC_BATTS"


def test_parse_unrelated():
    assert parse_resilient_mount_furring_channel_callout("ALUMINIUM BALUSTRADE POST") is None
    assert parse_resilient_mount_furring_channel_callout("TIMBER ROOF TRUSS") is None


def test_evaluate_resilient_mount_shadow_single():
    callouts = ["RESILMOUNT ACOUSTIC CLIP 28MM"]
    positions = [(10.1, 20.2)]
    results = evaluate_resilient_mount_furring_channel_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_resilient_mount_shadow_dict():
    items = [{"text": "FURRING CHANNEL CLIP 16MM", "position": (5.0, 7.6)}]
    results = evaluate_resilient_mount_furring_channel_shadow(items)
    assert len(results) == 1
    assert results[0].furring_channel_depth_mm == 16.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_resilient_mount_shadow_no_positions():
    results = evaluate_resilient_mount_furring_channel_shadow(["SOUND ISOLATION CLIP"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_resilient_mount_shadow_safety_cap():
    huge_input = ["RESILMOUNT"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_resilient_mount_furring_channel_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_resilient_mount_furring_channel_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "RESILMOUNT CLIP", "ROOM 101"]
    results = evaluate_resilient_mount_furring_channel_shadow(items)
    assert len(results) == 1
    assert results[0].mount_type == "THERMOPLASTIC_RUBBER_CLIP"


def test_rc1_mount_trigger():
    text = "WALL WITH RC1 RESILIENT CHANNEL"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "DIRECT_RESILIENT_CHANNEL"


def test_mineral_insulation():
    text = "ACOUSTIC WALL FURRING WITH MINERAL FIBRE"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["insulation_type"] == "ROCKWOOL_ACOUSTIC_BATTS"


def test_default_values():
    text = "RESILIENT WALL ISOLATOR"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["mount_type"] == "THERMOPLASTIC_RUBBER_CLIP"
    assert parsed["furring_channel_depth_mm"] == 28.0
    assert parsed["channel_spacing_cts_mm"] == 600.0
    assert parsed["cavity_depth_mm"] == 25.0
    assert parsed["insulation_type"] == "GLASSWOOL_ACOUSTIC_BATTS"


def test_snapping_precision():
    callouts = ["HAT CHANNEL CLIP"]
    positions = [(12.49, 13.76)]
    results = evaluate_resilient_mount_furring_channel_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_acoustic_furring_trigger():
    text = "ACOUSTIC FURRING 16MM"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["furring_channel_depth_mm"] == 16.0


def test_20mm_cavity():
    text = "RESILMOUNT WITH 20MM CAVITY"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["cavity_depth_mm"] == 20.0


def test_450_cts():
    text = "ISOLATION CLIP AT 450 CTS"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert parsed["channel_spacing_cts_mm"] == 450.0


def test_invalid_item_types():
    results = evaluate_resilient_mount_furring_channel_shadow([123, None, object()])
    assert results == []


def test_fyrchek_lining_trigger():
    text = "RESILIENT MOUNT WITH 2X16MM FYRCHEK"
    parsed = parse_resilient_mount_furring_channel_callout(text)
    assert parsed is not None
    assert "2x16mm" in parsed["lining_configuration"]
