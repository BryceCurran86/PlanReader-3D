"""
Unit and adversarial test suite for Source Headed Concrete Shear Stud & Composite Decking Shadow Authority.
"""

import pytest
from pb_source_shear_stud_composite_deck_shadow import (
    ShearStudCompositeDeckCallout,
    SourceShearStudCompositeDeckShadowAuthority,
    parse_shear_stud_composite_deck_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_shear_stud_callout():
    text = "COMPOSITE BEAM B12: 19X100MM SHEAR STUDS WELDED THROUGH BONDEK 0.75MM BMT, 1 STUD PER PAN"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["stud_diameter_mm"] == 19.0
    assert res["stud_length_mm"] == 100.0
    assert res["studs_per_trough"] == 1
    assert res["decking_profile"] == "PROFILED_COMPOSITE_STEEL_DECKING_BONDEK"
    assert res["deck_bmt_mm"] == 0.75


def test_parse_double_studs_condeck():
    text = "CONDECK HP COMPOSITE DECK 1.0MM BMT: 2 STUDS PER RIB 19X125MM HEADED STUDS"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["stud_diameter_mm"] == 19.0
    assert res["stud_length_mm"] == 125.0
    assert res["studs_per_trough"] == 2
    assert res["decking_profile"] == "CONDECK_HP_PROFILE"
    assert res["deck_bmt_mm"] == 1.0


def test_parse_nelson_stud():
    text = "NELSON STUD 22X125 ON PRIMARY GIRDER, PAIRS OF STUDS"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["stud_diameter_mm"] == 22.0
    assert res["stud_length_mm"] == 125.0
    assert res["studs_per_trough"] == 2


def test_parse_defaults():
    text = "COMPOSITE DECK SHEAR CONNECTOR"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["stud_diameter_mm"] == 19.0
    assert res["stud_length_mm"] == 100.0
    assert res["studs_per_trough"] == 1


def test_parse_non_shear_stud():
    text = "DRYWALL TRACK 92MM"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(66.2, 128.8, snap_tol=2.5)
    assert pt == (65.0, 130.0)


def test_authority_processing_dedup():
    auth = SourceShearStudCompositeDeckShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("19X100 SHEAR STUDS", (10.0, 20.0)),
        ("19X100 SHEAR STUDS", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceShearStudCompositeDeckShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("19X100 SHEAR STUDS", (10.0, 20.0)),
        ("19X100 SHEAR STUDS", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceShearStudCompositeDeckShadowAuthority()
    oversized = [("19X100 SHEAR STUDS", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceShearStudCompositeDeckShadowAuthority()
    res = auth.process_callouts([("19X100 SHEAR STUDS", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_shear_stud_composite_deck_callout("") is None


def test_kingflor_profile():
    text = "KINGFLOR COMPOSITE DECK 0.9MM BMT WITH SHEAR STUDS"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["decking_profile"] == "DOVETAIL_RE-ENTRANT_DECKING"


def test_zero_tolerance_snap():
    pt = snap_point(14.14, 28.28, snap_tol=0.0)
    assert pt == (14.14, 28.28)


def test_frozen_dataclass_immutability():
    callout = ShearStudCompositeDeckCallout(
        raw_text="text",
        stud_diameter_mm=19.0,
        stud_length_mm=100.0,
        studs_per_trough=1,
        decking_profile="BONDEK",
        deck_bmt_mm=0.75,
        characteristic_shear_kn=85.5,
    )
    with pytest.raises(Exception):
        callout.stud_diameter_mm = 22.0  # type: ignore


def test_different_per_trough_same_point():
    auth = SourceShearStudCompositeDeckShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("19X100 SHEAR STUDS 1 PER PAN", (10.0, 20.0)),
        ("19X100 SHEAR STUDS 2 PER PAN", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_headed_stud_trigger():
    text = "HEADED STUD 19MM DIA X 100MM LONG"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["stud_diameter_mm"] == 19.0
    assert res["stud_length_mm"] == 100.0


def test_shear_connector_trigger():
    text = "SHEAR CONNECTOR 19X125MM ON STEEL BEAM"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["stud_diameter_mm"] == 19.0
    assert res["stud_length_mm"] == 125.0


def test_comflor_profile():
    text = "COMFLOR COMPOSITE SLAB 1.0MM BMT WITH 19X100 SHEAR STUDS"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["decking_profile"] == "DOVETAIL_RE-ENTRANT_DECKING"


def test_characteristic_shear_calc():
    text = "22X125MM SHEAR STUDS"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["characteristic_shear_kn"] == 99.0  # 22 * 4.5


def test_trapezoidal_profile():
    text = "TRAPEZOIDAL COMPOSITE DECK WITH SHEAR CONNECTOR"
    res = parse_shear_stud_composite_deck_callout(text)
    assert res is not None
    assert res["decking_profile"] == "PROFILED_COMPOSITE_STEEL_DECKING_BONDEK"
