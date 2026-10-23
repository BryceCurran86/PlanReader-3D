"""
Unit and adversarial test suite for Source Precast Concrete Corbel & Elastomeric Bearing Pad Shadow Authority.
"""

import pytest
from pb_source_corbel_bearing_pad_shadow import (
    CorbelBearingPadCallout,
    SourceCorbelBearingPadShadowAuthority,
    parse_corbel_bearing_pad_callout,
    snap_point,
    MAX_SAFETY_CAP_PRIMITIVES,
    SNAP_TOLERANCE_PT,
)


def test_parse_complete_corbel():
    text = "PRECAST COLUMN C4: 350MM PROJECTION X 600MM DEEP CORBEL WITH STEEL REINFORCED LAMINATED BEARING PAD 20MM THICK, SHORE A 60, DESIGN SHEAR 450 KN"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["corbel_projection_mm"] == 350.0
    assert res["corbel_depth_mm"] == 600.0
    assert res["bearing_pad_material"] == "STEEL_REINFORCED_LAMINATED_BEARING"
    assert res["pad_thickness_mm"] == 20.0
    assert res["shore_a_hardness"] == 60
    assert res["design_shear_kn"] == 450.0


def test_parse_ptfe_sliding():
    text = "EXPANSION BEAM SEAT: PTFE SLIDING BEARING PAD 12MM THICK ON CORBEL, 300 KN"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["bearing_pad_material"] == "PTFE_SLIDING_PAD"
    assert res["pad_thickness_mm"] == 12.0
    assert res["design_shear_kn"] == 300.0


def test_parse_neoprene_pad_durometer():
    text = "COLUMN BRACKET: NEOPRENE PAD 15MM, 70 DUROMETER, 200 KN"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["bearing_pad_material"] == "PLAIN_ELASTOMERIC_NEOPRENE_PAD"
    assert res["shore_a_hardness"] == 70
    assert res["pad_thickness_mm"] == 15.0


def test_parse_defaults():
    text = "CONCRETE CORBEL SEAT"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["corbel_projection_mm"] == 300.0
    assert res["corbel_depth_mm"] == 500.0
    assert res["bearing_pad_material"] == "PLAIN_ELASTOMERIC_NEOPRENE_PAD"
    assert res["shore_a_hardness"] == 60


def test_parse_non_corbel():
    text = "SUSPENDED POST TENSIONED SLAB 200MM"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is None


def test_snap_point():
    pt = snap_point(62.4, 114.8, snap_tol=2.5)
    assert pt == (62.5, 115.0)


def test_authority_processing_dedup():
    auth = SourceCorbelBearingPadShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("CORBEL SEAT 350MM PROJ", (10.0, 20.0)),
        ("CORBEL SEAT 350MM PROJ", (10.2, 20.1)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 1


def test_authority_multiple():
    auth = SourceCorbelBearingPadShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("CORBEL SEAT 350MM PROJ", (10.0, 20.0)),
        ("CORBEL SEAT 350MM PROJ", (70.0, 80.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2


def test_safety_cap():
    auth = SourceCorbelBearingPadShadowAuthority()
    oversized = [("CORBEL SEAT", (float(i), float(i))) for i in range(MAX_SAFETY_CAP_PRIMITIVES + 10)]
    res = auth.process_callouts(oversized)
    assert len(res) <= MAX_SAFETY_CAP_PRIMITIVES


def test_shadow_guarantees():
    auth = SourceCorbelBearingPadShadowAuthority()
    res = auth.process_callouts([("CORBEL SEAT", (10.0, 10.0))])
    assert len(res) == 1
    assert res[0].status == "CANDIDATE"
    assert res[0].commercial_projection_allowed is False
    assert res[0].takeoff_eligible is False


def test_empty_string():
    assert parse_corbel_bearing_pad_callout("") is None


def test_teflon_keyword():
    text = "TEFLON SLIDING BEARING PAD ON CORBEL"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["bearing_pad_material"] == "PTFE_SLIDING_PAD"


def test_steel_shim_bearing():
    text = "ELASTOMERIC BEARING WITH INTERNAL STEEL SHIM PLATES, CORBEL 400MM DEEP"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["bearing_pad_material"] == "STEEL_REINFORCED_LAMINATED_BEARING"
    assert res["corbel_depth_mm"] == 400.0


def test_shore_50():
    text = "CORBEL BEARING PAD SHORE 50"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["shore_a_hardness"] == 50


def test_zero_tolerance_snap():
    pt = snap_point(9.99, 8.88, snap_tol=0.0)
    assert pt == (9.99, 8.88)


def test_frozen_dataclass_immutability():
    callout = CorbelBearingPadCallout(
        raw_text="text",
        corbel_projection_mm=300.0,
        corbel_depth_mm=500.0,
        bearing_pad_material="NEOPRENE",
        pad_thickness_mm=15.0,
        shore_a_hardness=60,
        design_shear_kn=250.0,
    )
    with pytest.raises(Exception):
        callout.design_shear_kn = 500.0  # type: ignore


def test_large_corbel():
    text = "HEAVY PRECAST CORBEL: 500MM PROJECTION X 800MM DEEP, 800 KN"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["corbel_projection_mm"] == 500.0
    assert res["corbel_depth_mm"] == 800.0
    assert res["design_shear_kn"] == 800.0


def test_beam_seat_trigger():
    text = "PRECAST BEAM SEAT WITH 10MM ELASTOMERIC PAD"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["pad_thickness_mm"] == 10.0


def test_column_bracket_trigger():
    text = "STEEL COLUMN BRACKET CORBEL 250MM PROJ"
    res = parse_corbel_bearing_pad_callout(text)
    assert res is not None
    assert res["corbel_projection_mm"] == 250.0


def test_different_materials_same_point():
    auth = SourceCorbelBearingPadShadowAuthority(snap_tolerance=2.5)
    raw = [
        ("CORBEL WITH NEOPRENE PAD", (10.0, 20.0)),
        ("CORBEL WITH PTFE SLIDING PAD", (10.0, 20.0)),
    ]
    res = auth.process_callouts(raw)
    assert len(res) == 2
