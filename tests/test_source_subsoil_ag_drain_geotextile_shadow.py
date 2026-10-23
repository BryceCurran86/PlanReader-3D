"""
Unit and adversarial test suite for Source Underground Subsoil Ag Drain & Geotextile Sock Shadow Authority.
"""

import pytest
from pb_source_subsoil_ag_drain_geotextile_shadow import (
    SubsoilAgDrainGeotextileCallout,
    SourceSubsoilAgDrainGeotextileShadowAuthority,
    parse_subsoil_ag_drain_geotextile_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_ag_pipe():
    text = "BASEMENT PERIMETER: DN100 SLOTTED CORRUGATED AG-PIPE CLASS 1000 WITH NON-WOVEN GEOTEXTILE FILTER SOCK, 400MM GRAVEL SURROUND"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["pipe_profile"] == "SLOTTED_PERFORATED_CORRUGATED"
    assert res["class_stiffness"] == "CLASS_1000_HEAVY_DUTY"
    assert res["geotextile_filter_sock"] == "NON_WOVEN_GEOTEXTILE_FILTER_SOCK"
    assert res["gravel_backfill_depth_mm"] == 400.0


def test_parse_unslotted_carrier():
    text = "SUBSOIL DRAIN DISCHARGE: DN160 UNSLOTTED SOLID CARRIER PIPE CLASS 400"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN160"
    assert res["pipe_profile"] == "UNSLOTTED_CARRIER"
    assert res["class_stiffness"] == "CLASS_400_STANDARD"


def test_parse_polyester_sleeve():
    text = "AGRICULTURAL DRAIN DN65 WITH SEAMLESS KNITTED POLYESTER SLEEVE"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN65"
    assert res["geotextile_filter_sock"] == "SEAMLESS_KNITTED_POLYESTER_SLEEVE"


def test_parse_no_sock():
    text = "SUBSOIL PIPE DN100 BARE WITHOUT SOCK, 300MM AGGREGATE BED"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["geotextile_filter_sock"] == "NONE_GRAVEL_SURROUND_ONLY"
    assert res["gravel_backfill_depth_mm"] == 300.0


def test_parse_defaults():
    text = "PERFORATED DRAIN"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN100"
    assert res["pipe_profile"] == "SLOTTED_PERFORATED_CORRUGATED"
    assert res["class_stiffness"] == "CLASS_400_STANDARD"


def test_parse_non_ag_pipe():
    text = "HOT WATER SUPPLY COPPER PIPE DN20"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(31.2, 78.8, snap_tol=2.5)
    assert pt == (30.0, 80.0)


def test_authority_processing_dedup():
    auth = SourceSubsoilAgDrainGeotextileShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("AG DRAIN DN100", (10.0, 20.0)),
        ("AG DRAIN DN100", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceSubsoilAgDrainGeotextileShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("AG DRAIN DN100", (10.0, 20.0)),
        ("AG DRAIN DN100", (80.0, 90.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceSubsoilAgDrainGeotextileShadowAuthority()
    oversized = [("AG DRAIN DN100", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceSubsoilAgDrainGeotextileShadowAuthority()
    res = auth.process_callouts([("AG DRAIN DN100", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_subsoil_ag_drain_geotextile_callout("") is None


def test_smooth_bore_profile():
    text = "SMOOTH BORE PERFORATED SUBSOIL DRAIN DN100"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["pipe_profile"] == "SMOOTH_BORE_PERFORATED"


def test_zero_tolerance_snap():
    pt = snap_point(15.15, 30.30, snap_tol=0.0)
    assert pt == (15.15, 30.30)


def test_frozen_dataclass_immutability():
    callout = SubsoilAgDrainGeotextileCallout(
        raw_text="text",
        pipe_diameter_dn="DN100",
        pipe_profile="SLOTTED",
        class_stiffness="400",
        geotextile_filter_sock="SOCK",
        gravel_backfill_depth_mm=300.0,
    )
    with pytest.raises(Exception):
        callout.gravel_backfill_depth_mm = 500.0  # type: ignore


def test_filter_sock_keyword():
    text = "FILTER SOCK ON SLOTTED AG PIPE DN100"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["geotextile_filter_sock"] == "NON_WOVEN_GEOTEXTILE_FILTER_SOCK"


def test_dn65_small_ag_pipe():
    text = "DN65 AG DRAIN BEHIND RETAINING WALL"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["pipe_diameter_dn"] == "DN65"


def test_different_socks_same_location():
    auth = SourceSubsoilAgDrainGeotextileShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("AG DRAIN DN100 WITH FILTER SOCK", (10.0, 20.0)),
        ("AG DRAIN DN100 WITHOUT SOCK", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_slotted_drain_trigger():
    text = "SLOTTED DRAIN DN100 WITH GRAVEL BEDDING 250MM"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["gravel_backfill_depth_mm"] == 250.0


def test_class_1000_heavy_duty():
    text = "HEAVY DUTY SUBSOIL DRAIN DN160"
    res = parse_subsoil_ag_drain_geotextile_callout(text)
    assert res is not None
    assert res["class_stiffness"] == "CLASS_1000_HEAVY_DUTY"
    assert res["pipe_diameter_dn"] == "DN160"
