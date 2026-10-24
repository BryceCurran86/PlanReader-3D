"""
Unit and adversarial test suite for Source Fire Hose Reel Cabinet Recessed Thermally Insulated Door Shadow Authority.
"""

import pytest
from pb_source_fhr_recessed_cabinet_shadow import (
    FhrRecessedCabinetCallout,
    SourceFhrRecessedCabinetShadowAuthority,
    parse_fhr_recessed_cabinet_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_recessed_insulated_cabinet():
    text = "FHR CABINET: FULLY RECESSED, THERMAL ROCKWOOL INSULATION CORE, -/120/120 FRL, 36M HOSE, 800X1050X300MM"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "FULLY_RECESSED"
    assert res["insulation_core"] == "ROCKWOOL_MINERAL_FIBER"
    assert res["frl_minutes"] == 120
    assert res["hose_length_m"] == 36.0
    assert res["dimensions_mm"] == (800.0, 1050.0, 300.0)


def test_parse_semi_recessed_glazed_door():
    text = "FIRE HOSE REEL: SEMI-RECESSED CABINET WITH GLAZED VISION PANEL, 2 HOUR FIRE RATED"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "SEMI_RECESSED"
    assert res["door_type"] == "GLAZED_DOOR"
    assert res["frl_minutes"] == 120


def test_parse_surface_mounted_break_glass():
    text = "FHR: SURFACE MOUNTED CABINET, BREAK GLASS DOOR, 50M HOSE"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "SURFACE_MOUNTED"
    assert res["door_type"] == "BREAK_GLASS_DOOR"
    assert res["hose_length_m"] == 50.0


def test_parse_stainless_steel_door():
    text = "FHR CABINET: RECESSED STAINLESS STEEL DOOR WITH 60 MIN FIRE RATING"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["door_type"] == "STAINLESS_STEEL_DOOR"
    assert res["frl_minutes"] == 60


def test_parse_ceramic_insulation():
    text = "FIRE HOSE REEL ENCLOSURE: CERAMIC BLANKET INSULATION CORE, -/60/60"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["insulation_core"] == "CERAMIC_BLANKET"
    assert res["frl_minutes"] == 60


def test_parse_uninsulated_negation():
    text = "FHR: RECESSED CABINET UNINSULATED SHEET METAL DOOR"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["insulation_core"] == "NONE"


def test_parse_defaults():
    text = "FIRE HOSE REEL"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "FULLY_RECESSED"
    assert res["door_type"] == "SOLID_FLUSH_DOOR"
    assert res["insulation_core"] == "NONE"
    assert res["frl_minutes"] == 0
    assert res["hose_length_m"] == 36.0
    assert res["dimensions_mm"] == (800.0, 1050.0, 300.0)


def test_parse_unrelated_text_returns_none():
    assert parse_fhr_recessed_cabinet_callout("ALUMINIUM SLIDING DOOR 2100X900") is None
    assert parse_fhr_recessed_cabinet_callout("DISTRIBUTION BOARD DB-01") is None


def test_snap_point_regular():
    pt = snap_point(15.2, 22.8, snap_tol=2.5)
    assert pt == (15.0, 22.5)


def test_snap_point_zero_tolerance():
    pt = snap_point(15.24, 22.87, snap_tol=0.0)
    assert pt == (15.24, 22.87)


def test_authority_processing_batch():
    auth = SourceFhrRecessedCabinetShadowAuthority()
    candidates = [
        ("FHR CABINET: FULLY RECESSED, 36M HOSE", (10.1, 20.2)),
        ("UNRELATED TEXT NOTE", (30.0, 40.0)),
        ("FIRE HOSE REEL: SURFACE MOUNTED", (50.3, 60.7)),
    ]
    results = auth.process_raw_candidates(candidates)
    assert len(results) == 2
    assert results[0].position == (10.0, 20.0)
    assert results[0].status == "CANDIDATE"
    assert results[0].commercial_projection_allowed is False
    assert results[0].takeoff_eligible is False
    assert results[1].position == (50.0, 60.0)
    assert results[1].mounting == "SURFACE_MOUNTED"


def test_safety_primitive_cap():
    auth = SourceFhrRecessedCabinetShadowAuthority()
    large_list = [("FHR CABINET RECESSED", (float(i), float(i))) for i in range(25000)]
    results = auth.process_raw_candidates(large_list)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_frozen_callout_dataclass():
    callout = FhrRecessedCabinetCallout(
        raw_text="SAMPLE",
        mounting="FULLY_RECESSED",
        door_type="SOLID_FLUSH_DOOR",
        insulation_core="ROCKWOOL_MINERAL_FIBER",
        frl_minutes=60,
        hose_length_m=36.0,
        dimensions_mm=(800.0, 1050.0, 300.0),
    )
    with pytest.raises(Exception):
        callout.frl_minutes = 120  # frozen dataclass


def test_case_insensitivity_and_whitespace():
    text = "   fhr cabinet: fully recessed, mineral wool insulated, -/60/60   "
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "FULLY_RECESSED"
    assert res["insulation_core"] == "ROCKWOOL_MINERAL_FIBER"
    assert res["frl_minutes"] == 60


def test_adversarial_semi_recessed_substring_guard():
    # SEMI RECESSED must never be misclassified as FULLY RECESSED
    text = "FHR: SEMI RECESSED CAVITY ENCLOSURE"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "SEMI_RECESSED"


def test_custom_snap_tolerance():
    auth = SourceFhrRecessedCabinetShadowAuthority(snap_tolerance_pt=5.0)
    res = auth.process_raw_candidates([("FHR RECESSED", (12.3, 17.8))])
    assert len(res) == 1
    assert res[0].position == (10.0, 20.0)


def test_empty_candidates_list():
    auth = SourceFhrRecessedCabinetShadowAuthority()
    res = auth.process_raw_candidates([])
    assert res == []


def test_custom_dimensions():
    text = "FIRE HOSE REEL CABINET 900*1200*350MM"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["dimensions_mm"] == (900.0, 1200.0, 350.0)


def test_dotted_fhr_acronym():
    text = "F.H.R. RECESSED IN FIRE WALL"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "FULLY_RECESSED"


def test_acrylic_window_door():
    text = "FHR WITH ACRYLIC WINDOW"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["door_type"] == "GLAZED_DOOR"


def test_adversarial_special_characters():
    text = "FHR @@@ [FULLY RECESSED] +++ (36M HOSE) // -/90/90 ***"
    res = parse_fhr_recessed_cabinet_callout(text)
    assert res is not None
    assert res["mounting"] == "FULLY_RECESSED"
    assert res["frl_minutes"] == 90
    assert res["hose_length_m"] == 36.0
