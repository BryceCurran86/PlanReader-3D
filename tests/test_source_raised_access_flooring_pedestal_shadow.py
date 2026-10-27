"""Tests for Raised Access Computer Flooring Pedestal & Stringer Shadow Authority."""

import pytest
from pb_source_raised_access_flooring_pedestal_shadow import (
    RaisedAccessFlooringCandidate,
    extract_raised_access_flooring_items,
    snap_point,
)


def test_snap_point_exact():
    pt = (100.0, 200.0)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 200.0)


def test_snap_point_offset():
    pt = (101.2, 203.8)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 205.0)


def test_steel_cementitious_panel():
    texts = [{
        "id": "raf_1",
        "text": "RAF-01 600x600mm Steel Cementitious Infill Access Floor Panel 300mm FFH Medium Grade",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "RAF-01"
    assert c.element_type == "PANEL"
    assert c.panel_size_desc == "600x600mm"
    assert c.panel_core_type == "STEEL_CEMENTITIOUS"
    assert c.finished_floor_height_mm == 300
    assert c.load_rating_class == "MEDIUM"


def test_adjustable_pedestal():
    texts = [{
        "id": "raf_2",
        "text": "PED-01 Adjustable Floor Pedestal Heavy Duty Base 450mm FFH",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "PEDESTAL"
    assert c.finished_floor_height_mm == 450
    assert c.load_rating_class == "HEAVY"


def test_bolted_stringer():
    texts = [{
        "id": "raf_3",
        "text": "STR-01 Bolted Grid Floor Stringer Galvanized Steel 600mm Length",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "STRINGER"
    assert c.stringer_type == "BOLTED"


def test_snap_on_stringer():
    texts = [{
        "id": "raf_4",
        "text": "RAF-02 Snap-On Stringer Raised Access Floor System",
        "coordinates": (60.0, 70.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.stringer_type == "SNAP_ON"


def test_woodcore_panel():
    texts = [{
        "id": "raf_5",
        "text": "AF-02 High Density Particleboard Woodcore Access Floor 600x600 Light Grade",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.panel_core_type == "WOODCORE"
    assert c.load_rating_class == "LIGHT"


def test_calcium_sulphate_panel():
    texts = [{
        "id": "raf_6",
        "text": "RAF-03 Calcium Sulphate Core Panel 600x600mm Extra Heavy Grade 9.0 kN",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.panel_core_type == "CALCIUM_SULPHATE"
    assert c.load_rating_class == "EXTRA_HEAVY"


def test_airflow_perforated_panel():
    texts = [{
        "id": "raf_7",
        "text": "AF-04 Perforated Airflow Panel Grille with Volume Control Damper 600x600mm",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "AIR_GRILLE"
    assert c.panel_core_type == "PERFORATED_AIRFLOW"


def test_cable_grommet():
    texts = [{
        "id": "raf_8",
        "text": "GRM-01 Airtight Brush Cable Grommet in Access Floor",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "CABLE_GROMMET"


def test_ramp_transition_step():
    texts = [{
        "id": "raf_9",
        "text": "RAF Ramp and Step Transition Fascia at Doorway 300mm FFH",
        "coordinates": (120.0, 130.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "RAMP_STEP"
    assert c.finished_floor_height_mm == 300


def test_negative_lookalike_ceramic_tile():
    texts = [{
        "id": "neg_1",
        "text": "Ceramic Floor Tile 300x300mm Non-Slip",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_carpet():
    texts = [{
        "id": "neg_2",
        "text": "Direct Stick Carpet Tile 500x500mm",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_paver_pedestal():
    texts = [{
        "id": "neg_3",
        "text": "Balcony Paver Pedestal Pod System on Waterproofing",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "raf_10",
        "text": "RAF-10 Raised Access Floor Panel",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "raf_11",
        "text": "RAF-11: Access Floor 600x600mm 150mm FFH",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "RAF-11"
    assert d["finished_floor_height_mm"] == 150
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"raf_{i}", "text": "RAF-01 Computer Floor Panel", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_raised_access_flooring_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_raised_access_flooring_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Drywall Partition 90mm Stud", "coordinates": (0.0, 0.0)}]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "raf_def",
        "text": "Raised Access Floor System",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "RAF-ITEM"
    assert c.panel_core_type == "STEEL_CEMENTITIOUS"
    assert c.stringer_type == "STANDARD"
    assert c.load_rating_class == "MEDIUM"


def test_stringerless_specification():
    texts = [{
        "id": "raf_none",
        "text": "AF-05 Stringerless Access Floor System 150mm FFH",
        "coordinates": (20.0, 30.0)
    }]
    candidates = extract_raised_access_flooring_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.stringer_type == "NONE"
