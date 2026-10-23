"""
Unit and adversarial test suite for Source Fire Smoke Damper Fusible Link & Microswitch Actuator Shadow Authority.
"""

import pytest
from pb_source_fire_smoke_damper_microswitch_shadow import (
    FireSmokeDamperMicroswitchCallout,
    SourceFireSmokeDamperMicroswitchShadowAuthority,
    parse_fire_smoke_damper_microswitch_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_combination_fire_smoke_damper_complete():
    text = "FSD: COMBINATION FIRE/SMOKE DAMPER 800X500MM, 24V MOTORISED SPRING RETURN ACTUATOR, 71°C FUSIBLE LINK, DUAL AUXILIARY MICROSWITCHES, -/120/- FRL"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["damper_type"] == "COMBINATION_FIRE_SMOKE_DAMPER"
    assert res["actuator_control"] == "MOTORISED_SPRING_RETURN_24V"
    assert res["fusible_link_rating_deg_c"] == 71.0
    assert res["auxiliary_microswitch"] == "OPEN_AND_CLOSED_MICROSWITCHES"
    assert res["duct_dimensions_mm"] == (800.0, 500.0)
    assert res["frl_minutes"] == 120


def test_parse_240v_actuator():
    text = "FIRE SMOKE DAMPER: 240V SPRING RETURN ACTUATOR, 600X300MM, 74 DEG C FUSIBLE LINK"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["actuator_control"] == "MOTORISED_SPRING_RETURN_240V"
    assert res["fusible_link_rating_deg_c"] == 74.0
    assert res["duct_dimensions_mm"] == (600.0, 300.0)


def test_parse_curtain_fire_damper_gravity():
    text = "FIRE DAMPER: CURTAIN TYPE WITH FUSIBLE LINK ONLY, 93°C THERMAL RELEASE, 4 HOUR FIRE RATED"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["damper_type"] == "CURTAIN_FIRE_DAMPER"
    assert res["actuator_control"] == "THERMAL_FUSIBLE_LINK_GRAVITY"
    assert res["fusible_link_rating_deg_c"] == 93.0
    assert res["frl_minutes"] == 240


def test_parse_intumescent_fire_damper():
    text = "INTUMESCENT FIRE DAMPER IN 200MM DIA DUCT PENETRATION"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["damper_type"] == "INTUMESCENT_FIRE_DAMPER"
    assert res["duct_dimensions_mm"] == (200.0, 200.0)


def test_parse_smoke_control_damper():
    text = "SMOKE CONTROL DAMPER: 1200X600MM WITH BELIMO 24V ACTUATOR"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["damper_type"] == "SMOKE_CONTROL_DAMPER"
    assert res["actuator_control"] == "MOTORISED_SPRING_RETURN_24V"
    assert res["duct_dimensions_mm"] == (1200.0, 600.0)


def test_parse_defaults():
    text = "FIRE DAMPER"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["damper_type"] == "COMBINATION_FIRE_SMOKE_DAMPER"
    assert res["actuator_control"] == "MOTORISED_SPRING_RETURN_24V"
    assert res["fusible_link_rating_deg_c"] == 71.0
    assert res["auxiliary_microswitch"] == "OPEN_AND_CLOSED_MICROSWITCHES"
    assert res["duct_dimensions_mm"] == (600.0, 400.0)
    assert res["frl_minutes"] == 120


def test_parse_unrelated_text_returns_none():
    assert parse_fire_smoke_damper_microswitch_callout("CARPET TILES INTERFACE") is None
    assert parse_fire_smoke_damper_microswitch_callout("ALUMINUM SKIRTING 100MM") is None


def test_snap_point_regular():
    pt = snap_point(21.3, 34.8, snap_tol=2.5)
    assert pt == (22.5, 35.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(21.34, 34.87, snap_tol=0.0)
    assert pt == (21.34, 34.87)


def test_authority_processing_batch():
    auth = SourceFireSmokeDamperMicroswitchShadowAuthority()
    candidates = [
        ("FIRE SMOKE DAMPER 800X400", (10.1, 20.2)),
        ("UNRELATED NOTE", (30.0, 40.0)),
        ("FSD 24V ACTUATOR", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].actuator_control == "MOTORISED_SPRING_RETURN_24V"


def test_safety_primitive_cap():
    auth = SourceFireSmokeDamperMicroswitchShadowAuthority()
    large_list = [("FIRE DAMPER", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = FireSmokeDamperMicroswitchCallout(
        raw_text="SAMPLE",
        damper_type="COMBINATION_FIRE_SMOKE_DAMPER",
        actuator_control="MOTORISED_SPRING_RETURN_24V",
        fusible_link_rating_deg_c=71.0,
        auxiliary_microswitch="OPEN_AND_CLOSED_MICROSWITCHES",
        duct_dimensions_mm=(600.0, 400.0),
        frl_minutes=120,
    )
    with pytest.raises(Exception):
        callout.frl_minutes = 240  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   fsd: motorized fire smoke damper 500x300mm, 71 deg c thermal release   "
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["duct_dimensions_mm"] == (500.0, 300.0)
    assert res["fusible_link_rating_deg_c"] == 71.0


def test_no_microswitch_negation():
    text = "FIRE DAMPER WITHOUT MICROSWITCH"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["auxiliary_microswitch"] == "NONE"


def test_closed_only_microswitch():
    text = "FSD WITH CLOSED ONLY MICROSWITCH"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["auxiliary_microswitch"] == "CLOSED_ONLY_MICROSWITCH"


def test_high_temp_fusible_link():
    text = "FIRE DAMPER WITH 141°C FUSIBLE LINK"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["fusible_link_rating_deg_c"] == 141.0


def test_custom_snap_tolerance():
    auth = SourceFireSmokeDamperMicroswitchShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("FIRE DAMPER", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceFireSmokeDamperMicroswitchShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_mvd_motorized_damper():
    text = "MVD MOTORIZED VOLUME SMOKE DAMPER 24V"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["actuator_control"] == "MOTORISED_SPRING_RETURN_24V"


def test_dotted_fsd_acronym():
    text = "F.S.D. LOCATED IN RISER SHAFT WALL"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["damper_type"] == "COMBINATION_FIRE_SMOKE_DAMPER"


def test_adversarial_special_characters():
    text = "FIRE DAMPER @@@ [FSD] +++ (750X450MM) // 24V *** 71°C ### -/120/-"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["duct_dimensions_mm"] == (750.0, 450.0)
    assert res["actuator_control"] == "MOTORISED_SPRING_RETURN_24V"
    assert res["fusible_link_rating_deg_c"] == 71.0
    assert res["frl_minutes"] == 120


def test_round_duct_diameter():
    text = "FSD IN 350MM DIA ROUND SPIRAL DUCT"
    res = parse_fire_smoke_damper_microswitch_callout(text)
    assert res is not None
    assert res["duct_dimensions_mm"] == (350.0, 350.0)

