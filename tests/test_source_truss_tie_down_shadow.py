"""
Unit and adversarial test suite for Source Structural Timber Roof Truss Tie-Down & Framing Anchor Shadow Authority.
"""

import pytest
from pb_source_truss_tie_down_shadow import (
    TrussTieDownCallout,
    SourceTrussTieDownShadowAuthority,
    parse_truss_tie_down_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_triple_grip():
    text = "TRUSS TIE-DOWN T1: TRIPLE GRIP FRAMING ANCHOR, WIND CLASS N3, 4 NAILS PER LEG, 4.2 KN UPLIFT, 1.2MM GAUGE"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "TRIPLE_GRIP_FRAMING_ANCHOR"
    assert res["wind_rating"] == "WIND_CLASS_N2_N3"
    assert res["fastener_description"] == "4_NAILS_30X2_8MM_PER_LEG"
    assert res["characteristic_uplift_kn"] == 4.2
    assert res["strap_gauge_mm"] == 1.2


def test_parse_cyclone_strap():
    text = "CYCLONIC TIE DOWN: CYCLONE STRAP OVER TRUSS TOP CHORD, WIND CLASS C2, 8.5 KN"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "CYCLONE_TIE_DOWN_STRAP"
    assert res["wind_rating"] == "WIND_CLASS_C2_C3_CYCLONIC"
    assert res["characteristic_uplift_kn"] == 8.5


def test_parse_multigrip_screws():
    text = "RAFTER TIE: MULTIGRIP BRACKET WITH TEK SCREWS, WIND RATING N4, 5.0 KN"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "MULTI_GRIP_UNIVERSAL_BRACKET"
    assert res["fastener_description"] == "TEK_SCREWS_10_16_TYPE_17"
    assert res["wind_rating"] == "WIND_CLASS_N4_C1"
    assert res["characteristic_uplift_kn"] == 5.0


def test_parse_truss_boot():
    text = "GIRDER TRUSS BOOT INTERNAL BRACKET, 14.5 KN UPLIFT, 1.6MM BMT"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "TRUSS_BOOT_INTERNAL_BRACKET"
    assert res["characteristic_uplift_kn"] == 14.5
    assert res["strap_gauge_mm"] == 1.6


def test_parse_defaults():
    text = "TRUSS TIE DOWN"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "TRIPLE_GRIP_FRAMING_ANCHOR"
    assert res["wind_rating"] == "WIND_CLASS_N2_N3"


def test_parse_non_truss():
    text = "CERAMIC FLOOR TILING"
    res = parse_truss_tie_down_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(18.2, 44.8, snap_tol=2.5)
    assert pt == (17.5, 45.0)


def test_authority_processing_dedup():
    auth = SourceTrussTieDownShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("TRIPLE GRIP TIE-DOWN", (10.0, 20.0)),
        ("TRIPLE GRIP TIE-DOWN", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceTrussTieDownShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("TRIPLE GRIP TIE-DOWN", (10.0, 20.0)),
        ("TRIPLE GRIP TIE-DOWN", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceTrussTieDownShadowAuthority()
    oversized = [("TRIPLE GRIP", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceTrussTieDownShadowAuthority()
    res = auth.process_callouts([("TRIPLE GRIP TIE DOWN", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_truss_tie_down_callout("") is None


def test_framing_anchor_trigger():
    text = "FRAMING ANCHOR BRACKET ON WALL TOP PLATE"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "TRIPLE_GRIP_FRAMING_ANCHOR"


def test_6_nails_option():
    text = "TRIPLE GRIP WITH 6 NAILS PER LEG"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["fastener_description"] == "6_NAILS_30X2_8MM_PER_LEG"


def test_cyclonic_c3():
    text = "CYCLONE STRAP WIND CLASS C3"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["wind_rating"] == "WIND_CLASS_C2_C3_CYCLONIC"


def test_zero_tolerance_snap():
    pt = snap_point(3.14, 2.71, snap_tol=0.0)
    assert pt == (3.14, 2.71)


def test_frozen_dataclass_immutability():
    callout = TrussTieDownCallout(
        raw_text="text",
        bracket_type="GRIP",
        wind_rating="N3",
        fastener_description="NAILS",
        characteristic_uplift_kn=4.2,
        strap_gauge_mm=1.2,
    )
    with pytest.raises(Exception):
        callout.characteristic_uplift_kn = 10.0  # type: ignore


def test_different_wind_ratings_same_point():
    auth = SourceTrussTieDownShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("TRIPLE GRIP WIND CLASS N2", (10.0, 20.0)),
        ("TRIPLE GRIP WIND CLASS C2", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_trip_l_grip_synonym():
    text = "TRIP-L-GRIP TRUSS TIE-DOWN 4.2 KN"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["bracket_type"] == "TRIPLE_GRIP_FRAMING_ANCHOR"


def test_wind_class_n4():
    text = "TIE-DOWN WIND CLASS N4"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["wind_rating"] == "WIND_CLASS_N4_C1"


def test_wind_class_c1():
    text = "CYCLONE STRAP WIND CLASS C1"
    res = parse_truss_tie_down_callout(text)
    assert res is not None
    assert res["wind_rating"] == "WIND_CLASS_N4_C1"
