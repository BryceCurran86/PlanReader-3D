"""
Unit and adversarial test suite for Source Stormwater Retention Sump Submersible Grinder Pump Station Shadow Authority.
"""

import pytest
from pb_source_submersible_grinder_pump_shadow import (
    SubmersibleGrinderPumpCallout,
    SourceSubmersibleGrinderPumpShadowAuthority,
    parse_submersible_grinder_pump_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_duplex_grinder_complete():
    text = "STORMWATER PUMP STATION: DUPLEX DUTY/STANDBY SUBMERSIBLE GRINDER PUMPS, 15 L/S @ 18M TDH, 5.5KW, DUAL GUIDE RAIL AUTO-COUPLING, 1500 DIA X 2500MM DEEP PIT"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "DUPLEX_DUTY_STANDBY"
    assert res["impeller_type"] == "RADIAL_CUTTER_GRINDER"
    assert res["flow_lps"] == 15.0
    assert res["head_m"] == 18.0
    assert res["motor_power_kw"] == 5.5
    assert res["guide_rail_coupling"] == "DUAL_GUIDE_RAIL_COUPLING"
    assert res["sump_dimensions_mm"] == (1500.0, 2500.0)


def test_parse_simplex_vortex_free_standing():
    text = "SUMP PUMP: SIMPLEX SUBMERSIBLE VORTEX PUMP, 5.0 L/S, HEAD 10M, 1.5KW, FREE STANDING"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "SIMPLEX_PUMP"
    assert res["impeller_type"] == "VORTEX_IMPELLER"
    assert res["flow_lps"] == 5.0
    assert res["head_m"] == 10.0
    assert res["motor_power_kw"] == 1.5
    assert res["guide_rail_coupling"] == "FREE_STANDING"


def test_parse_triplex_shredder():
    text = "RETENTION PUMP: TRIPLEX SUBMERSIBLE SHREDDER PUMPS WITH HOSE DISCHARGE"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "TRIPLEX_SYSTEM"
    assert res["impeller_type"] == "SHREDDER_PUMP"
    assert res["guide_rail_coupling"] == "HOSE_DISCHARGE"


def test_parse_non_clog_impeller():
    text = "SUBMERSIBLE PUMP: SEMI-OPEN NON-CLOG IMPELLER, 20 L/S AT 15M HEAD"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["impeller_type"] == "SEMI_OPEN_NON_CLOG"
    assert res["flow_lps"] == 20.0
    assert res["head_m"] == 15.0


def test_parse_defaults():
    text = "SUBMERSIBLE PUMP"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "DUPLEX_DUTY_STANDBY"
    assert res["impeller_type"] == "VORTEX_IMPELLER"
    assert res["flow_lps"] == 10.0
    assert res["head_m"] == 12.0
    assert res["motor_power_kw"] == 2.2
    assert res["guide_rail_coupling"] == "DUAL_GUIDE_RAIL_COUPLING"
    assert res["sump_dimensions_mm"] == (1200.0, 2000.0)


def test_parse_unrelated_text_returns_none():
    assert parse_submersible_grinder_pump_callout("GYPROCK CEILING BOARD 13MM") is None
    assert parse_submersible_grinder_pump_callout("FIRE SPRINKLER FLOW SWITCH") is None


def test_snap_point_regular():
    pt = snap_point(22.3, 33.8, snap_tol=2.5)
    assert pt == (22.5, 35.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(22.34, 33.87, snap_tol=0.0)
    assert pt == (22.34, 33.87)


def test_authority_processing_batch():
    auth = SourceSubmersibleGrinderPumpShadowAuthority()
    candidates = [
        ("SUBMERSIBLE PUMP DUPLEX", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("GRINDER PUMP 15 L/S", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].flow_lps == 15.0


def test_safety_primitive_cap():
    auth = SourceSubmersibleGrinderPumpShadowAuthority()
    large_list = [("SUBMERSIBLE PUMP", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = SubmersibleGrinderPumpCallout(
        raw_text="SAMPLE",
        pump_configuration="DUPLEX_DUTY_STANDBY",
        impeller_type="RADIAL_CUTTER_GRINDER",
        flow_lps=10.0,
        head_m=12.0,
        motor_power_kw=2.2,
        guide_rail_coupling="DUAL_GUIDE_RAIL_COUPLING",
        sump_dimensions_mm=(1200.0, 2000.0),
    )
    with pytest.raises(Exception):
        callout.flow_lps = 20.0  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   sewage ejector submersible pump: 7.5kw, 12 l/s   "
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["flow_lps"] == 12.0
    assert res["motor_power_kw"] == 7.5


def test_lead_lag_duplex_detection():
    text = "RETENTION PUMP: LEAD / LAG SUBMERSIBLE SUMP SYSTEM"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "DUPLEX_DUTY_STANDBY"


def test_twin_pump_trigger():
    text = "TWIN PUMP SUBMERSIBLE DRAINAGE STATION"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "DUPLEX_DUTY_STANDBY"


def test_custom_snap_tolerance():
    auth = SourceSubmersibleGrinderPumpShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("SUBMERSIBLE PUMP", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceSubmersibleGrinderPumpShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_duckfoot_pedestal_coupling():
    text = "EFFLUENT PUMP SUBMERSIBLE WITH DUCKFOOT PEDESTAL COUPLING"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["guide_rail_coupling"] == "DUAL_GUIDE_RAIL_COUPLING"


def test_single_pump_simplex():
    text = "SINGLE PUMP SUBMERSIBLE PIT 900 X 1500MM"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "SIMPLEX_PUMP"
    assert res["sump_dimensions_mm"] == (900.0, 1500.0)


def test_chopper_impeller():
    text = "CHOPPER SUBMERSIBLE PUMP STATION"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["impeller_type"] == "SHREDDER_PUMP"


def test_alternate_flow_notation():
    text = "STORMWATER PUMP: 8.5 LITRES PER SEC, 14M TOTAL DYNAMIC HEAD"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["flow_lps"] == 8.5
    assert res["head_m"] == 14.0


def test_adversarial_special_characters():
    text = "SUBMERSIBLE PUMP *** [DUPLEX] +++ (15 L/S @ 20M) // 7.5KW ###"
    res = parse_submersible_grinder_pump_callout(text)
    assert res is not None
    assert res["pump_configuration"] == "DUPLEX_DUTY_STANDBY"
    assert res["flow_lps"] == 15.0
    assert res["head_m"] == 20.0
    assert res["motor_power_kw"] == 7.5
