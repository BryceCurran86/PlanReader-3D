"""Tests for Emergency Exit Photoluminescent & Egress Signage Shadow Authority."""

import pytest
from pb_source_photoluminescent_exit_signage_shadow import (
    ExitSignCandidate,
    extract_exit_signs,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_photoluminescent_exit_sign():
    data = [{
        "id": "e1",
        "text": "EX-01 PHOTOLUMINESCENT RUNNING MAN LEFT 24M VIEWING DISTANCE CLASS C WALL MOUNTED",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].sign_type == "PHOTOLUMINESCENT"
    assert res[0].tag == "EX-01"
    assert res[0].direction == "RUNNING_MAN_LEFT"
    assert res[0].viewing_distance_m == 24
    assert res[0].luminance_class == "CLASS_C"
    assert res[0].mounting == "WALL_MOUNTED"
    assert res[0].is_double_sided is False


def test_self_luminous_tritium():
    data = [{
        "id": "e2",
        "text": "ES-02 SELF-LUMINOUS TRITIUM EXIT SIGN RIGHT ARROW 16M CEILING SUSPENDED",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].sign_type == "SELF_LUMINOUS"
    assert res[0].direction == "RUNNING_MAN_RIGHT"
    assert res[0].viewing_distance_m == 16
    assert res[0].mounting == "CEILING_SUSPENDED"


def test_double_sided_flag_mounted():
    data = [{
        "id": "e3",
        "text": "PL-01 DOUBLE-SIDED PHOTOLUMINESCENT EXIT SIGN FLAG MOUNTED",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].is_double_sided is True
    assert res[0].direction == "DOUBLE_SIDED"
    assert res[0].mounting == "FLAG_MOUNTED"


def test_ul924_listed_led_sign():
    data = [{
        "id": "e4",
        "text": "EMX-1 LED ILLUMINATED EXIT SIGN UL924 LISTED RECESSED",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].sign_type == "LED_ILLUMINATED"
    assert res[0].luminance_class == "UL924"
    assert res[0].mounting == "RECESSED"


def test_class_d_photoluminescent():
    data = [{
        "id": "e5",
        "text": "PHOTOLUMINESCENT EXIT SIGN CLASS D HIGH LUMINANCE 32M",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].luminance_class == "CLASS_D"
    assert res[0].viewing_distance_m == 32


def test_class_b_photoluminescent():
    data = [{
        "id": "e6",
        "text": "PHOTOLUMINESCENT RUNNING MAN CLASS B",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].luminance_class == "CLASS_B"


def test_class_a_photoluminescent():
    data = [{
        "id": "e7",
        "text": "GLOW IN THE DARK EXIT SIGN CLASS A",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].luminance_class == "CLASS_A"
    assert res[0].sign_type == "PHOTOLUMINESCENT"


def test_running_man_straight():
    data = [{
        "id": "e8",
        "text": "EX-04 RUNNING MAN STRAIGHT FORWARD ARROW",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].direction == "RUNNING_MAN_STRAIGHT"


def test_pendant_mounting():
    data = [{
        "id": "e9",
        "text": "EXIT SIGN PENDANT SUSPENDED",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].mounting == "CEILING_SUSPENDED"


def test_cantilever_bracket():
    data = [{
        "id": "e10",
        "text": "EXIT SIGN ON CANTILEVER BRACKET",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].mounting == "FLAG_MOUNTED"


def test_negative_fire_extinguisher():
    data = [{"id": "n1", "text": "FIRE EXTINGUISHER ONLY", "coordinates": (0.0, 0.0)}]
    assert len(extract_exit_signs(data)) == 0


def test_negative_hose_reel():
    data = [{"id": "n2", "text": "FIRE HOSE REEL ONLY", "coordinates": (0.0, 0.0)}]
    assert len(extract_exit_signs(data)) == 0


def test_negative_smoke_alarm():
    data = [{"id": "n3", "text": "SMOKE ALARM OPTICAL", "coordinates": (0.0, 0.0)}]
    assert len(extract_exit_signs(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((29.9, 59.8), tolerance=2.5)
    assert pt == (30.0, 60.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "EX-1 EXIT SIGN", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_exit_signs(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = ExitSignCandidate(
        item_id="cand_1",
        sign_type="PHOTOLUMINESCENT",
        tag="EX-01",
        direction="RUNNING_MAN_LEFT",
        viewing_distance_m=24,
        luminance_class="CLASS_C",
        mounting="WALL_MOUNTED",
        is_double_sided=False,
        coordinates=(10.0, 20.0),
        raw_text="EX-01 EXIT SIGN",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = ExitSignCandidate(
        item_id="cand_2",
        sign_type="SELF_LUMINOUS",
        tag="ES-02",
        direction="RUNNING_MAN_RIGHT",
        viewing_distance_m=16,
        luminance_class="STANDARD",
        mounting="CEILING_SUSPENDED",
        is_double_sided=True,
        coordinates=(0.0, 0.0),
        raw_text="ES-02 SIGN",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "e11",
        "text": "EX-05 EXIT SIGN WALL MOUNTED",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_exit_signs(data)
    d = res[0].to_dict()
    assert d["tag"] == "EX-05"
    assert d["mounting"] == "WALL_MOUNTED"
    assert d["status"] == "CANDIDATE"


def test_arrow_symbol_detection():
    data = [{
        "id": "e12",
        "text": "EXIT SIGN <- EGRESS ROUTE",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].direction == "RUNNING_MAN_LEFT"


def test_rms_tag_detection():
    data = [{
        "id": "e13",
        "text": "RMS-01 RUNNING MAN SIGN RIGHT",
        "coordinates": (20.0, 40.0)
    }]
    res = extract_exit_signs(data)
    assert len(res) == 1
    assert res[0].tag == "RMS-01"
    assert res[0].direction == "RUNNING_MAN_RIGHT"
