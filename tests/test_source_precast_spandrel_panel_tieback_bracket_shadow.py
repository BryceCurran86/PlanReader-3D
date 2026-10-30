"""Tests for Precast Concrete Spandrel Panel Tieback & Gravity Bracket Connection Shadow Authority."""

import pytest
from pb_source_precast_spandrel_panel_tieback_bracket_shadow import (
    PrecastSpandrelBracketCandidate,
    extract_precast_spandrel_bracket_items,
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


def test_gravity_bearing_bracket():
    texts = [{
        "id": "spb_1",
        "text": "GB-01 Precast Gravity Bracket Heavy Duty HDG Fixed into Cast-in Channel with M24 T-Bolts for 200mm Panel",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "GB-01"
    assert c.element_type == "GRAVITY_BRACKET"
    assert c.bracket_material == "HOT_DIP_GALVANIZED"
    assert c.fixing_method == "CAST_IN_CHANNEL"
    assert c.anchor_bolt_size == "M24"
    assert c.panel_thickness_mm == 200
    assert c.has_slotted_hole_deflection is False


def test_slotted_wind_tieback_bracket():
    texts = [{
        "id": "spb_2",
        "text": "TB-02 Wind Tieback Bracket with Vertically Slotted Hole for Deflection M20 Bolt Stainless Steel 316",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "TB-02"
    assert c.element_type == "TIEBACK_BRACKET"
    assert c.has_slotted_hole_deflection is True
    assert c.bracket_material == "STAINLESS_STEEL"
    assert c.anchor_bolt_size == "M20"


def test_precast_spandrel_panel():
    texts = [{
        "id": "spb_3",
        "text": "SP-03 Precast Spandrel Panel 175mm Thk with Cast-In Embed Plates",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SP-03"
    assert c.element_type == "SPANDREL_PANEL"
    assert c.panel_thickness_mm == 175
    assert c.fixing_method == "CAST_IN_PLATE"


def test_chemical_anchor_fixing():
    texts = [{
        "id": "spb_4",
        "text": "GB-04 Precast Shelf Angle Bracket with Post-Installed Chemical Epoxy Anchor M20",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.fixing_method == "CHEMICAL_ANCHOR"
    assert c.anchor_bolt_size == "M20"


def test_through_bolt_fixing():
    texts = [{
        "id": "spb_5",
        "text": "TB-05 Tieback Bracket with Through Bolt M16 fixing to slab edge",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.fixing_method == "THROUGH_BOLT"
    assert c.anchor_bolt_size == "M16"


def test_alignment_dowel_pin():
    texts = [{
        "id": "spb_6",
        "text": "PC-06 Precast Spandrel Inter-Panel Alignment Dowel Pin Stainless Steel",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "ALIGNMENT_DOWEL"
    assert c.bracket_material == "STAINLESS_STEEL"


def test_shim_pack():
    texts = [{
        "id": "spb_7",
        "text": "BRK-07 Precast Spandrel Leveling Shim Pack under bearing bracket",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.element_type == "SHIM_PACK"


def test_negative_lookalike_stud_track():
    texts = [{
        "id": "neg_1",
        "text": "Steel Stud Deflection Track 92mm with Slotted Deflection Track",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_truss():
    texts = [{
        "id": "neg_2",
        "text": "Truss Tie-Down Hurricane Clip to Wall Plate",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_curtain_wall():
    texts = [{
        "id": "neg_3",
        "text": "Mullion Bracket Curtain Wall Transom Connection",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "spb_8",
        "text": "GB-08 Precast Gravity Bracket",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "spb_9",
        "text": "TB-09: Wind Tieback Bracket M20",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "TB-09"
    assert d["anchor_bolt_size"] == "M20"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"spb_{i}", "text": "GB-01 Precast Bracket HDG", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_precast_spandrel_bracket_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_precast_spandrel_bracket_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Plaster ceiling lining 13mm", "coordinates": (0.0, 0.0)}]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "spb_def",
        "text": "Precast Spandrel Bracket Connection",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "SPB-ITEM"
    assert c.bracket_material == "HOT_DIP_GALVANIZED"
    assert c.fixing_method == "CAST_IN_CHANNEL"
    assert c.has_slotted_hole_deflection is False


def test_halfen_channel_callout():
    texts = [{
        "id": "spb_halfen",
        "text": "GB-10 Precast Bracket Fixed into Halfen Channel HTA 50/30 with M20 Bolts",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.fixing_method == "CAST_IN_CHANNEL"
    assert c.anchor_bolt_size == "M20"


def test_m30_large_bolt():
    texts = [{
        "id": "spb_large",
        "text": "GB-11 Heavy Precast Gravity Bracket M30 Cast-In Bolt 250mm Panel",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_precast_spandrel_bracket_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_bolt_size == "M30"
    assert c.panel_thickness_mm == 250
