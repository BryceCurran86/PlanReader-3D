"""
Tests for Source Compressed Air Ring Main Aluminum Piping Drop Leg & Filter Regulator Shadow Authority.
"""

import pytest
from pb_source_compressed_air_ring_main_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    CompressedAirRingMainCallout,
    snap_point,
    parse_compressed_air_ring_main_callout,
    extract_compressed_air_ring_main_candidates,
    validate_compressed_air_ring_main_system,
)


def test_snap_point_regular():
    pt = snap_point(35.3, 58.7, snap_tol=2.5)
    assert pt == (35.0, 57.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(35.3, 58.7, snap_tol=0.0)
    assert pt == (35.3, 58.7)


def test_parse_none_on_irrelevant_text():
    assert parse_compressed_air_ring_main_callout("ALUMINUM DOOR THRESHOLD") is None
    assert parse_compressed_air_ring_main_callout("CARPET TILES OVER SCREED") is None
    assert parse_compressed_air_ring_main_callout("ACOUSTIC CEILING PANEL") is None


def test_parse_transair_aluminum_ring_main():
    text = "TRANSAIR ALUMINUM COMPRESSED AIR RING MAIN 63MM 8 BAR WITH AUTOMATIC DRAIN"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["piping_system_type"] == "ALUMINUM_COMPRESSED_AIR_RING_MAIN"
    assert parsed["pipe_diameter_mm"] == 63.0
    assert parsed["operating_pressure_bar"] == 8.0
    assert parsed["condensate_drain"] == "AUTOMATIC_FLOAT_DRAIN"


def test_parse_swan_neck_drop_leg_frl_combo():
    text = "SWAN-NECK COMPRESSED AIR DROP LEG 25MM WITH FRL COMBO AND VENTING SAFETY QUICK COUPLING"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["piping_system_type"] == "SWAN_NECK_DROP_LEG"
    assert parsed["pipe_diameter_mm"] == 25.0
    assert parsed["point_of_use_frl"] == "FILTER_REGULATOR_LUBRICATOR_COMBO"
    assert parsed["quick_coupling_safety"] == "VENTING_SAFETY_QUICK_COUPLING"


def test_parse_coalescing_filter_instrument_air():
    text = "INSTRUMENT AIR HEADER 40MM WITH COALESCING OIL REMOVAL FILTER 0.01 MICRON 10 BAR"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["service_designation"] == "INSTRUMENT_AIR"
    assert parsed["point_of_use_frl"] == "COALESCING_OIL_REMOVAL_FILTER"
    assert parsed["pipe_diameter_mm"] == 40.0
    assert parsed["operating_pressure_bar"] == 10.0


def test_parse_zero_loss_electronic_drain():
    text = "AIRNET PNEUMATIC RING MAIN 50MM WITH ZERO LOSS ELECTRONIC DRAIN"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["piping_system_type"] == "ALUMINUM_COMPRESSED_AIR_RING_MAIN"
    assert parsed["pipe_diameter_mm"] == 50.0
    assert parsed["condensate_drain"] == "ZERO_LOSS_ELECTRONIC_DRAIN"


def test_parse_kpa_pressure_conversion():
    text = "WORKSHOP AIR DROPPER 20MM 700 KPA WITH FILTER REGULATOR"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["operating_pressure_bar"] == 7.0
    assert parsed["pipe_diameter_mm"] == 20.0
    assert parsed["point_of_use_frl"] == "FILTER_REGULATOR_ONLY"
    assert parsed["service_designation"] == "WORKSHOP_PNEUMATIC_TOOL"


def test_parse_psi_pressure_conversion():
    text = "COMPRESSED AIR DROP 150 PSI WITH NITTO HI-CUPLA"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["operating_pressure_bar"] == round(150.0 * 0.0689476, 1)
    assert parsed["quick_coupling_safety"] == "NITTO_STYLE_PLUG"


def test_parse_euro_high_flow_coupling():
    text = "FRL UNIT WORKSTATION 25MM WITH EURO HIGH FLOW COUPLER"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["piping_system_type"] == "FRL_UNIT_WORKSTATION"
    assert parsed["quick_coupling_safety"] == "EURO_HIGH_FLOW_COUPLING"
    assert parsed["pipe_diameter_mm"] == 25.0


def test_extract_compressed_air_ring_main_candidates():
    items = [
        ("TRANSAIR ALUMINUM COMPRESSED AIR RING MAIN 63MM", (120.2, 240.3)),
        ("VINYL COVE SKIRTING", (50.0, 50.0)),
        ("SWAN-NECK COMPRESSED AIR DROP LEG 25MM WITH FRL", (300.0, 400.0)),
    ]
    candidates = extract_compressed_air_ring_main_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (120.0, 240.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"COMPRESSED AIR RING MAIN {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_compressed_air_ring_main_candidates(items, max_cap=13)
    assert len(candidates) == 13


def test_system_validation_summary():
    items = [
        ("TRANSAIR ALUMINUM COMPRESSED AIR RING MAIN 63MM 8 BAR", (10.0, 20.0)),
        ("SWAN-NECK COMPRESSED AIR DROP LEG 25MM WITH FRL", (30.0, 40.0)),
        ("WORKSHOP AIR DROPPER 20MM WITH FILTER REGULATOR", (50.0, 60.0)),
    ]
    candidates = extract_compressed_air_ring_main_candidates(items)
    summary = validate_compressed_air_ring_main_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["frl_count"] == 2
    assert summary["sized_pipe_count"] == 3
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = CompressedAirRingMainCallout(
        raw_text="SAMPLE",
        piping_system_type="ALUMINUM_COMPRESSED_AIR_RING_MAIN",
        pipe_diameter_mm=63.0,
        operating_pressure_bar=8.0,
        point_of_use_frl="FILTER_REGULATOR_LUBRICATOR_COMBO",
        condensate_drain="AUTOMATIC_FLOAT_DRAIN",
        quick_coupling_safety="VENTING_SAFETY_QUICK_COUPLING",
        service_designation="PLANT_COMPRESSED_AIR",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_compressed_air_ring_main_candidates([])
    assert len(candidates) == 0
    summary = validate_compressed_air_ring_main_system([])
    assert summary["total_candidates"] == 0
    assert summary["frl_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_compressed_air_ring_main_callout("HOT WATER COPPER PIPE 25MM") is None
    assert parse_compressed_air_ring_main_callout("FIRE SPRINKLER WET PIPE DN50") is None
    assert parse_compressed_air_ring_main_callout("NATURAL GAS PIPE DN40") is None


def test_breathing_air_service():
    text = "BREATHING AIR COMPRESSED AIR LINE 20MM 10 BAR"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["service_designation"] == "BREATHING_AIR"
    assert parsed["operating_pressure_bar"] == 10.0


def test_dn50_mapping():
    text = "COMPRESSED AIR HEADER DN50"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["pipe_diameter_mm"] == 63.0


def test_iso_4414_safety():
    text = "AIR DROP LEG 25MM WITH ISO 4414 SAFETY COUPLING"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["quick_coupling_safety"] == "VENTING_SAFETY_QUICK_COUPLING"


def test_manual_drain_valve():
    text = "COMPRESSED AIR DROPPER WITH MANUAL BALL VALVE DRAIN"
    parsed = parse_compressed_air_ring_main_callout(text)
    assert parsed is not None
    assert parsed["condensate_drain"] == "MANUAL_DRAIN_VALVE"
