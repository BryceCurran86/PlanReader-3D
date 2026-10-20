"""
Unit and adversarial test suite for Source Commercial Kitchen Exhaust Canopy Hood & Baffle Filter Shadow Authority.
"""

import pytest
from pb_source_kitchen_exhaust_hood_shadow import (
    KitchenExhaustHoodCallout,
    SourceKitchenExhaustHoodShadowAuthority,
    parse_kitchen_exhaust_hood_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_exhaust_hood():
    text = "COOKING LINE: WALL MOUNTED KITCHEN EXHAUST HOOD 3000X1400MM, 1350 L/S, 6 BAFFLE FILTERS, COMPENSATING MAKEUP AIR PLENUM, 304 STAINLESS STEEL"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["hood_type"] == "WALL_MOUNTED_CANOPY"
    assert res["length_mm"] == 3000.0
    assert res["width_mm"] == 1400.0
    assert res["exhaust_airflow_lps"] == 1350.0
    assert res["filter_count"] == 6
    assert res["makeup_air_included"] is True
    assert res["material_grade"] == "STAINLESS_STEEL_304_NO4_FINISH"


def test_parse_island_v_bank():
    text = "ISLAND V-BANK CANOPY HOOD 4000X2000, 2200 LPS, 8 BAFFLE FILTERS, GRADE 316 SS"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["hood_type"] == "ISLAND_V_BANK_CANOPY"
    assert res["length_mm"] == 4000.0
    assert res["width_mm"] == 2000.0
    assert res["exhaust_airflow_lps"] == 2200.0
    assert res["filter_count"] == 8
    assert res["material_grade"] == "STAINLESS_STEEL_316"


def test_parse_backshelf_hood():
    text = "LOW PROXIMITY BACKSHELF EXHAUST HOOD 1800X900, 800 L/S"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["hood_type"] == "LOW_PROXIMITY_BACKSHELF_HOOD"
    assert res["length_mm"] == 1800.0
    assert res["width_mm"] == 900.0
    assert res["exhaust_airflow_lps"] == 800.0


def test_parse_defaults():
    text = "EXHAUST CANOPY"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["hood_type"] == "WALL_MOUNTED_CANOPY"
    assert res["length_mm"] == 2400.0
    assert res["width_mm"] == 1200.0
    assert res["filter_count"] == 4


def test_parse_non_kitchen_hood():
    text = "FIRE HOSE REEL"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(74.4, 188.7, snap_tol=2.5)
    assert pt == (75.0, 187.5)


def test_authority_processing_dedup():
    auth = SourceKitchenExhaustHoodShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("EXHAUST HOOD 2400X1200", (10.0, 20.0)),
        ("EXHAUST HOOD 2400X1200", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceKitchenExhaustHoodShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("EXHAUST HOOD 2400X1200", (10.0, 20.0)),
        ("EXHAUST HOOD 2400X1200", (90.0, 100.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceKitchenExhaustHoodShadowAuthority()
    oversized = [("EXHAUST HOOD", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceKitchenExhaustHoodShadowAuthority()
    res = auth.process_callouts([("EXHAUST HOOD", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_kitchen_exhaust_hood_callout("") is None


def test_m3_hour_conversion():
    text = "CANOPY HOOD 3000X1200, 3600 M3/HR"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["exhaust_airflow_lps"] == 1000.0


def test_zero_tolerance_snap():
    pt = snap_point(12.34, 56.78, snap_tol=0.0)
    assert pt == (12.34, 56.78)


def test_frozen_dataclass_immutability():
    callout = KitchenExhaustHoodCallout(
        raw_text="text",
        hood_type="WALL",
        length_mm=2400.0,
        width_mm=1200.0,
        exhaust_airflow_lps=1000.0,
        filter_count=4,
        makeup_air_included=True,
        material_grade="304",
    )
    with pytest.raises(Exception):
        callout.length_mm = 3000.0  # type: ignore


def test_different_dims_same_point():
    auth = SourceKitchenExhaustHoodShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("EXHAUST HOOD 2400X1200", (10.0, 20.0)),
        ("EXHAUST HOOD 3000X1200", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_range_hood_trigger():
    text = "COMMERCIAL RANGE HOOD 2000X1000 WITH 4 GREASE FILTERS"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["length_mm"] == 2000.0
    assert res["filter_count"] == 4


def test_grease_hood_trigger():
    text = "GREASE HOOD 1800X1100, 750 LPS"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["exhaust_airflow_lps"] == 750.0


def test_cooking_canopy_trigger():
    text = "COOKING CANOPY 3600X1500 WITH INDUCTION MAKEUP AIR"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["makeup_air_included"] is True


def test_baffle_filter_trigger():
    text = "KITCHEN CANOPY WITH STAINLESS STEEL BAFFLE FILTERS"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["material_grade"] == "STAINLESS_STEEL_304_NO4_FINISH"


def test_default_airflow_rule_of_thumb():
    text = "CANOPY HOOD 2000X1000"
    res = parse_kitchen_exhaust_hood_callout(text)
    assert res is not None
    assert res["exhaust_airflow_lps"] == 900.0  # 2000 * 0.45
