"""Tests for Precast Concrete Stair Flight & Rebated Landing Bearing Shadow Authority."""

import pytest
from pb_source_precast_concrete_stair_landing_bearing_shadow import (
    PrecastStairCandidate,
    extract_precast_stairs,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_precast_stair_flight():
    data = [{
        "id": "s1",
        "text": "ST-01 PRECAST STAIR FLIGHT 16 RISERS @ 175MM, 15 GOINGS @ 260MM, 1200MM CLEAR WIDTH",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].flight_tag == "ST-01"
    assert res[0].riser_count == 16
    assert res[0].riser_height_mm == 175.0
    assert res[0].going_count == 15
    assert res[0].going_depth_mm == 260.0
    assert res[0].flight_width_mm == 1200


def test_rebated_landing_bearing_sylomer():
    data = [{
        "id": "s2",
        "text": "PRECAST STAIR REBATED NIB BEARING 100MM REBATE WITH 10MM SYLOMER ACOUSTIC BEARING STRIP AND N16 DOWELS",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].landing_connection_type == "REBATED_NIB"
    assert res[0].rebate_depth_mm == 100
    assert res[0].acoustic_bearing == "SYLOMER"
    assert res[0].has_shear_dowels is True


def test_corbel_bearing_neoprene():
    data = [{
        "id": "s3",
        "text": "STAIR FLIGHT ON CORBEL BEARING WITH 15MM NEOPRENE BEARING PAD",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].landing_connection_type == "CORBEL_BEARING"
    assert res[0].acoustic_bearing == "NEOPRENE"


def test_integral_landing():
    data = [{
        "id": "s4",
        "text": "PRECAST FLIGHT WITH INTEGRAL LANDING SLAB",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].landing_connection_type == "INTEGRAL_LANDING"


def test_bolted_angle_bracket():
    data = [{
        "id": "s5",
        "text": "STAIR FLIGHT ON BOLTED ANGLE BRACKET SUPPORT",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].landing_connection_type == "BOLTED_ANGLE"


def test_abbreviated_r_and_g_notation():
    data = [{
        "id": "s6",
        "text": "ST-02 10R @ 170MM 9G @ 250MM",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].riser_count == 10
    assert res[0].riser_height_mm == 170.0
    assert res[0].going_count == 9
    assert res[0].going_depth_mm == 250.0


def test_shear_pins_in_grout_tubes():
    data = [{
        "id": "s7",
        "text": "PRECAST STAIR NIB BEARING WITH SHEAR PINS IN GROUT TUBES",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].has_shear_dowels is True


def test_generic_elastomeric_bearing():
    data = [{
        "id": "s8",
        "text": "PRECAST STAIR WITH ELASTOMERIC ISOLATION STRIP",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].acoustic_bearing == "ELASTOMERIC"


def test_decimal_riser_height():
    data = [{
        "id": "s9",
        "text": "PRECAST FLIGHT 17 RISERS @ 172.5MM",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].riser_height_mm == 172.5


def test_stepped_bearing_nib():
    data = [{
        "id": "s10",
        "text": "STAIR FLIGHT 75MM STEPPED BEARING NIB",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].landing_connection_type == "REBATED_NIB"
    assert res[0].rebate_depth_mm == 75


def test_negative_void_penetration():
    data = [{"id": "n1", "text": "STAIR VOID PENETRATION ONLY", "coordinates": (0.0, 0.0)}]
    assert len(extract_precast_stairs(data)) == 0


def test_negative_escalator():
    data = [{"id": "n2", "text": "ESCALATOR TIE BEAM ET-1", "coordinates": (0.0, 0.0)}]
    assert len(extract_precast_stairs(data)) == 0


def test_negative_handrail():
    data = [{"id": "n3", "text": "STAIR HANDRAIL ONLY DETAIL", "coordinates": (0.0, 0.0)}]
    assert len(extract_precast_stairs(data)) == 0


def test_negative_ladder():
    data = [{"id": "n4", "text": "LADDER ACCESS TO ROOF", "coordinates": (0.0, 0.0)}]
    assert len(extract_precast_stairs(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((34.9, 67.4), tolerance=2.5)
    assert pt == (35.0, 67.5)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "ST-1 PRECAST STAIR FLIGHT", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_precast_stairs(items, max_primitives=40)
    assert len(res) == 40


def test_candidate_guardrails_default():
    candidate = PrecastStairCandidate(
        item_id="cand_1",
        flight_tag="ST-01",
        riser_count=16,
        riser_height_mm=175.0,
        going_count=15,
        going_depth_mm=260.0,
        flight_width_mm=1200,
        landing_connection_type="REBATED_NIB",
        rebate_depth_mm=100,
        acoustic_bearing="SYLOMER",
        has_shear_dowels=True,
        coordinates=(10.0, 20.0),
        raw_text="ST-01 PRECAST STAIR FLIGHT",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = PrecastStairCandidate(
        item_id="cand_2",
        flight_tag="ST-02",
        riser_count=12,
        riser_height_mm=170.0,
        going_count=11,
        going_depth_mm=250.0,
        flight_width_mm=1100,
        landing_connection_type="STANDARD",
        rebate_depth_mm=None,
        acoustic_bearing="NONE",
        has_shear_dowels=False,
        coordinates=(0.0, 0.0),
        raw_text="ST-02 STAIR FLIGHT",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "s11", "text": "ST-03 PRECAST STAIR FLIGHT 1000MM WIDE", "coordinates": (30.0, 40.0)}]
    res = extract_precast_stairs(data)
    d = res[0].to_dict()
    assert d["flight_tag"] == "ST-03"
    assert d["flight_width_mm"] == 1000
    assert d["status"] == "CANDIDATE"


def test_flight_tag_detection():
    data = [{"id": "s12", "text": "FL-04 STAIR RISERS 14 RISERS @ 180MM", "coordinates": (15.0, 30.0)}]
    res = extract_precast_stairs(data)
    assert len(res) == 1
    assert res[0].flight_tag == "FL-04"
    assert res[0].riser_count == 14
