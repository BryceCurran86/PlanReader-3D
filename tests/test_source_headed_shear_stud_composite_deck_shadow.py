"""Tests for Structural Steel Welded Headed Shear Stud Connector & Composite Decking Shadow Authority."""

import pytest
from pb_source_headed_shear_stud_composite_deck_shadow import (
    HeadedShearStudCandidate,
    extract_headed_shear_stud_items,
    snap_point,
)


def test_snap_point_exact():
    pt = (100.0, 50.0)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 50.0)


def test_snap_point_offset():
    pt = (101.1, 51.9)
    snapped = snap_point(pt, tolerance=2.5)
    assert snapped == (100.0, 52.5)


def test_through_deck_welded_studs():
    texts = [{
        "id": "stud_1",
        "text": "HSS-01 19x100mm Headed Shear Studs Thru-Deck Welded 1 per trough on ComFlor 80 Trapezoidal Composite Deck",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "HSS-01"
    assert c.element_type == "SHEAR_STUD_GROUP"
    assert c.stud_diameter_mm == 19
    assert c.stud_length_mm == 100
    assert c.welding_method == "THROUGH_DECK_WELD"
    assert c.stud_layout == "ONE_PER_TROUGH"
    assert c.deck_profile_type == "TRAPEZOIDAL"


def test_two_studs_per_trough():
    texts = [{
        "id": "stud_2",
        "text": "SS-02 19x125mm Headed Studs 2 per trough Through-Deck Welded on Bondek Decking",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SS-02"
    assert c.stud_diameter_mm == 19
    assert c.stud_length_mm == 125
    assert c.stud_layout == "TWO_PER_TROUGH"
    assert c.deck_profile_type == "RE_ENTRANT"


def test_staggered_pairs_nelson_studs():
    texts = [{
        "id": "stud_3",
        "text": "STUD-03 Nelson Studs 22x150mm Staggered Pairs Direct to Flange Weld on Transfer Beam",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.stud_diameter_mm == 22
    assert c.stud_length_mm == 150
    assert c.stud_layout == "STAGGERED_PAIRS"
    assert c.welding_method == "DIRECT_TO_FLANGE_WELD"


def test_composite_deck_element():
    texts = [{
        "id": "stud_4",
        "text": "DECK-04 Bondek 0.75mm BMT Galvanized Composite Metal Decking",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "COMPOSITE_DECK"
    assert c.deck_profile_type == "RE_ENTRANT"


def test_edge_form_trim_pour_stop():
    texts = [{
        "id": "stud_5",
        "text": "EF-05 Galvanized Steel Edge Form Trim Pour Stop 150mm Slab Edge",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "EDGE_FORM_TRIM"


def test_continuous_pitch_layout():
    texts = [{
        "id": "stud_6",
        "text": "HSS-06 19x100mm Shear Studs Welded at 150mm Continuous Pitch",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.stud_layout == "CONTINUOUS_PITCH"


def test_large_stud_25mm():
    texts = [{
        "id": "stud_7",
        "text": "SS-07 25x150mm Headed Shear Studs Shop Welded to Bare Flange",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.stud_diameter_mm == 25
    assert c.stud_length_mm == 150
    assert c.welding_method == "DIRECT_TO_FLANGE_WELD"


def test_negative_lookalike_wall_stud():
    texts = [{
        "id": "neg_1",
        "text": "Steel Wall Stud 92mm LGS Drywall Stud Framing at 450 centres",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_timber_stud():
    texts = [{
        "id": "neg_2",
        "text": "Timber Stud 90x45 MGP10 Wall Framing",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_chemical_anchor():
    texts = [{
        "id": "neg_3",
        "text": "Chemical Anchor Stud M16 Epoxy Stud into Concrete",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "stud_8",
        "text": "HSS-08 Headed Shear Studs",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "stud_9",
        "text": "SS-09: 19x100mm Shear Studs",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "SS-09"
    assert d["stud_diameter_mm"] == 19
    assert d["stud_length_mm"] == 100
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"stud_{i}", "text": "HSS-01 Headed Shear Stud", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_headed_shear_stud_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_headed_shear_stud_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Acoustic insulation batts 75mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "stud_def",
        "text": "Welded Headed Shear Studs on Composite Beam",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "STUD-ITEM"
    assert c.element_type == "SHEAR_STUD_GROUP"
    assert c.stud_layout == "ONE_PER_TROUGH"
    assert c.welding_method == "THROUGH_DECK_WELD"


def test_condek_reentrant_deck():
    texts = [{
        "id": "stud_condek",
        "text": "DECK-10 Condek Re-entrant Profile Metal Deck",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.deck_profile_type == "RE_ENTRANT"


def test_16mm_diameter_stud():
    texts = [{
        "id": "stud_16",
        "text": "HSS-11 16x75mm Headed Shear Studs Through-Deck Welded",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_headed_shear_stud_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.stud_diameter_mm == 16
    assert c.stud_length_mm == 75
