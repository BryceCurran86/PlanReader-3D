"""Tests for Architectural Acoustic Louver & Plantroom Screen Shadow Authority."""

import pytest
from pb_source_acoustic_louver_plantroom_screen_shadow import (
    AcousticLouverCandidate,
    extract_acoustic_louvers,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_single_bank_acoustic_louver():
    data = [{
        "id": "l1",
        "text": "AL-01 150MM DEEP SINGLE BANK ACOUSTIC LOUVER 1800x1200 RW 18DB 45% FREE AREA WITH BIRD MESH",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].louver_type == "SINGLE_BANK_ACOUSTIC"
    assert res[0].tag == "AL-01"
    assert res[0].frame_depth_mm == 150
    assert res[0].width_mm == 1800
    assert res[0].height_mm == 1200
    assert res[0].acoustic_rw_db == 18
    assert res[0].free_area_percent == 45.0
    assert res[0].has_bird_mesh is True


def test_double_bank_acoustic_louver():
    data = [{
        "id": "l2",
        "text": "AL-02 300MM DEEP DOUBLE BANK ACOUSTIC LOUVRE RW 24DB 40% FREE AREA",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].louver_type == "DOUBLE_BANK_ACOUSTIC"
    assert res[0].frame_depth_mm == 300
    assert res[0].acoustic_rw_db == 24
    assert res[0].free_area_percent == 40.0


def test_rooftop_plantroom_screen():
    data = [{
        "id": "l3",
        "text": "PS-01 ROOFTOP PLANTROOM SCREEN WALL 2400x1800",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].louver_type == "PLANTROOM_SCREEN"
    assert res[0].tag == "PS-01"
    assert res[0].width_mm == 2400
    assert res[0].height_mm == 1800


def test_weather_louver():
    data = [{
        "id": "l4",
        "text": "LV-01 WEATHER LOUVER 1200x900 50% FREE AREA WITH INSECT MESH",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].louver_type == "WEATHER_LOUVER"
    assert res[0].has_bird_mesh is True


def test_insertion_loss_rating():
    data = [{
        "id": "l5",
        "text": "ACOUSTIC LOUVER INSERTION LOSS = 15DB 200MM DEPTH",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].acoustic_rw_db == 15
    assert res[0].frame_depth_mm == 200


def test_600mm_deep_acoustic_louver():
    data = [{
        "id": "l6",
        "text": "SOUND ATTENUATING LOUVER 600MM DEEP",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].frame_depth_mm == 600
    assert res[0].louver_type == "DOUBLE_BANK_ACOUSTIC"


def test_wire_mesh_screen():
    data = [{
        "id": "l7",
        "text": "ACOUSTIC LOUVRE WITH STAINLESS STEEL WIRE MESH",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].has_bird_mesh is True


def test_screen_wall():
    data = [{
        "id": "l8",
        "text": "SCREEN-1 LOUVERED SCREEN WALL 3000x2100",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].tag == "SCREEN-1"
    assert res[0].width_mm == 3000
    assert res[0].height_mm == 2100


def test_decimal_free_area():
    data = [{
        "id": "l9",
        "text": "ACOUSTIC LOUVER 48.5% OPEN AREA",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].free_area_percent == 48.5


def test_negative_window_glazing():
    data = [{"id": "n1", "text": "WINDOW GLAZING DOUBLE GLAZED", "coordinates": (0.0, 0.0)}]
    assert len(extract_acoustic_louvers(data)) == 0


def test_negative_fire_damper():
    data = [{"id": "n2", "text": "FIRE DAMPER 600x300", "coordinates": (0.0, 0.0)}]
    assert len(extract_acoustic_louvers(data)) == 0


def test_negative_door_leaf():
    data = [{"id": "n3", "text": "DOOR LEAF TIMBER SOLID CORE", "coordinates": (0.0, 0.0)}]
    assert len(extract_acoustic_louvers(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((29.9, 59.8), tolerance=2.5)
    assert pt == (30.0, 60.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "AL-1 ACOUSTIC LOUVER", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_acoustic_louvers(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = AcousticLouverCandidate(
        item_id="cand_1",
        louver_type="SINGLE_BANK_ACOUSTIC",
        tag="AL-01",
        frame_depth_mm=150,
        width_mm=1800,
        height_mm=1200,
        acoustic_rw_db=18,
        free_area_percent=45.0,
        has_bird_mesh=True,
        coordinates=(10.0, 20.0),
        raw_text="AL-01 LOUVER",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = AcousticLouverCandidate(
        item_id="cand_2",
        louver_type="DOUBLE_BANK_ACOUSTIC",
        tag="AL-02",
        frame_depth_mm=300,
        width_mm=None,
        height_mm=None,
        acoustic_rw_db=24,
        free_area_percent=40.0,
        has_bird_mesh=False,
        coordinates=(0.0, 0.0),
        raw_text="AL-02 LOUVER",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "l10",
        "text": "AL-05 ACOUSTIC LOUVER 1500x1000",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_acoustic_louvers(data)
    d = res[0].to_dict()
    assert d["tag"] == "AL-05"
    assert d["width_mm"] == 1500
    assert d["height_mm"] == 1000
    assert d["status"] == "CANDIDATE"


def test_ls_tag_detection():
    data = [{
        "id": "l11",
        "text": "LS-02 ROOFTOP SCREEN 2000x1500",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].tag == "LS-02"
    assert res[0].louver_type == "PLANTROOM_SCREEN"


def test_spelling_louvre():
    data = [{
        "id": "l12",
        "text": "ACOUSTIC LOUVRE 300MM DEEP",
        "coordinates": (20.0, 40.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].frame_depth_mm == 300
    assert res[0].louver_type == "DOUBLE_BANK_ACOUSTIC"


def test_lv_tag_detection():
    data = [{
        "id": "l13",
        "text": "LV-03 WEATHER LOUVER 1000x800",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_acoustic_louvers(data)
    assert len(res) == 1
    assert res[0].tag == "LV-03"
    assert res[0].louver_type == "WEATHER_LOUVER"
