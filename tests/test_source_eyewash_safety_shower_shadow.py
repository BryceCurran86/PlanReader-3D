"""
Unit and adversarial test suite for Source Emergency Eyewash & Safety Shower Station Shadow Authority.
"""

import pytest
from pb_source_eyewash_safety_shower_shadow import (
    EyewashSafetyShowerCallout,
    SourceEyewashSafetyShowerShadowAuthority,
    parse_eyewash_safety_shower_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_combination_shower():
    text = "LABORATORY: DN32 COMBINATION SHOWER & EYEWASH, STAINLESS STEEL BOWL, 80 L/MIN SHOWER, 14 L/MIN EYEWASH, TEPID WATER TMV, FLOW SWITCH WITH STROBE BEACON ALARM"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["station_type"] == "COMBINATION_SHOWER_AND_EYEWASH"
    assert res["supply_pipe_dn"] == "DN32"
    assert res["bowl_material"] == "STAINLESS_STEEL_316"
    assert res["drench_shower_flow_lpm"] == 80.0
    assert res["eyewash_flow_lpm"] == 14.0
    assert res["tepid_water_tmv_included"] is True
    assert res["flow_switch_alarm"] == "FLOW_SWITCH_WITH_BEACON_ALARM"


def test_parse_pedestal_eyewash():
    text = "WORKSHOP: PEDESTAL EYEWASH DN25, HIGH VISIBILITY YELLOW ABS PLASTIC BOWL"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["station_type"] == "PEDESTAL_EYEWASH_STATION"
    assert res["supply_pipe_dn"] == "DN25"
    assert res["bowl_material"] == "HIGH_VISIBILITY_ABS_PLASTIC"
    assert res["drench_shower_flow_lpm"] == 0.0
    assert res["eyewash_flow_lpm"] == 12.0
    assert res["tepid_water_tmv_included"] is False


def test_parse_wall_mounted_eyewash():
    text = "WALL MOUNTED EMERGENCY EYEWASH DN25 WITH TEMPERING VALVE"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["station_type"] == "WALL_MOUNTED_EYEWASH"
    assert res["supply_pipe_dn"] == "DN25"
    assert res["tepid_water_tmv_included"] is True


def test_parse_overhead_drench():
    text = "OVERHEAD DRENCH SHOWER DN40, 76 LPM"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["station_type"] == "OVERHEAD_DRENCH_SHOWER"
    assert res["supply_pipe_dn"] == "DN40"
    assert res["drench_shower_flow_lpm"] == 76.0
    assert res["eyewash_flow_lpm"] == 0.0


def test_parse_defaults():
    text = "SAFETY SHOWER"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["supply_pipe_dn"] == "DN25"
    assert res["bowl_material"] == "STAINLESS_STEEL_316"
    assert res["flow_switch_alarm"] == "NONE"


def test_parse_non_eyewash():
    text = "DOMESTIC EN-SUITE SHOWER MIXER"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(41.1, 88.9, snap_tol=2.5)
    assert pt == (40.0, 90.0)


def test_authority_processing_dedup():
    auth = SourceEyewashSafetyShowerShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SAFETY SHOWER DN25", (10.0, 20.0)),
        ("SAFETY SHOWER DN25", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceEyewashSafetyShowerShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("SAFETY SHOWER DN25", (10.0, 20.0)),
        ("SAFETY SHOWER DN25", (90.0, 100.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceEyewashSafetyShowerShadowAuthority()
    oversized = [("SAFETY SHOWER DN25", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceEyewashSafetyShowerShadowAuthority()
    res = auth.process_callouts([("SAFETY SHOWER DN25", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_eyewash_safety_shower_callout("") is None


def test_tepid_water_variations():
    text1 = "EMERGENCY EYEWASH WITH TMV"
    text2 = "EMERGENCY EYEWASH WITH WARM WATER"
    assert parse_eyewash_safety_shower_callout(text1)["tepid_water_tmv_included"] is True
    assert parse_eyewash_safety_shower_callout(text2)["tepid_water_tmv_included"] is True


def test_alarm_beacon_audio():
    text = "SAFETY SHOWER WITH HORN AND SIREN"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["flow_switch_alarm"] == "FLOW_SWITCH_WITH_BEACON_ALARM"


def test_plastic_bowl_variants():
    text = "EMERGENCY EYE WASH WITH ABS BOWL"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["bowl_material"] == "HIGH_VISIBILITY_ABS_PLASTIC"


def test_stainless_304():
    text = "EMERGENCY EYEWASH 304 SS BOWL"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["bowl_material"] == "STAINLESS_STEEL_316"


def test_zero_tolerance_snap():
    pt = snap_point(5.67, 8.91, snap_tol=0.0)
    assert pt == (5.67, 8.91)


def test_frozen_dataclass_immutability():
    callout = EyewashSafetyShowerCallout(
        raw_text="text",
        station_type="SHOWER",
        supply_pipe_dn="DN25",
        bowl_material="SS",
        drench_shower_flow_lpm=76.0,
        eyewash_flow_lpm=12.0,
        tepid_water_tmv_included=True,
        flow_switch_alarm="ALARM",
    )
    with pytest.raises(Exception):
        callout.eyewash_flow_lpm = 20.0  # type: ignore


def test_combination_slash_trigger():
    text = "COMBINATION SHOWER/EYEWASH DN32"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["station_type"] == "COMBINATION_SHOWER_AND_EYEWASH"


def test_single_high_flow_override():
    text = "EMERGENCY SHOWER DN32, 90 L/MIN"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["drench_shower_flow_lpm"] == 90.0


def test_single_low_flow_override():
    text = "EMERGENCY EYEWASH DN25, 15 L/MIN"
    res = parse_eyewash_safety_shower_callout(text)
    assert res is not None
    assert res["eyewash_flow_lpm"] == 15.0
