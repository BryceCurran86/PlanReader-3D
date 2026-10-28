"""Tests for Post-Installed Mechanical Undercut & Chemical Epoxy Anchor Stud Shadow Authority."""

import pytest
from pb_source_post_installed_undercut_chemical_anchor_shadow import (
    PostInstalledAnchorCandidate,
    extract_post_installed_anchor_items,
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


def test_pure_epoxy_chemical_anchor():
    texts = [{
        "id": "anc_1",
        "text": "CA-01 M20 Chemical Anchor Stud Pure Epoxy Adhesive Embedment Depth 170mm Grade 8.8 Galvanized Seismic C2 Approved for Cracked Concrete",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "CA-01"
    assert c.anchor_type == "CHEMICAL_EPOXY_STUD"
    assert c.thread_size == "M20"
    assert c.embedment_depth_mm == 170
    assert c.steel_material == "GRADE_8_8_GALV"
    assert c.seismic_category == "SEISMIC_C2"
    assert c.cracked_concrete_approved is True


def test_mechanical_undercut_anchor():
    texts = [{
        "id": "anc_2",
        "text": "UA-02 M24 Heavy Duty Mechanical Undercut Anchor HDA Hef=190mm Stainless Steel A4 316",
        "coordinates": (30.0, 40.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "UA-02"
    assert c.anchor_type == "MECHANICAL_UNDERCUT"
    assert c.thread_size == "M24"
    assert c.embedment_depth_mm == 190
    assert c.steel_material == "STAINLESS_A4_316"
    assert c.cracked_concrete_approved is True


def test_concrete_screw_anchor():
    texts = [{
        "id": "anc_3",
        "text": "SA-03 M12 Concrete Screw Bolt Titen HD Hef=100mm Zinc Plated Seismic C1",
        "coordinates": (50.0, 60.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_type == "CONCRETE_SCREW_BOLT"
    assert c.thread_size == "M12"
    assert c.embedment_depth_mm == 100
    assert c.steel_material == "CARBON_STEEL_ZINC"
    assert c.seismic_category == "SEISMIC_C1"


def test_torque_controlled_wedge_expansion():
    texts = [{
        "id": "anc_4",
        "text": "WA-04 M16 Wedge Anchor HST3 Through Bolt Embedment 125mm Cracked Concrete",
        "coordinates": (70.0, 80.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_type == "EXPANSION_ANCHOR"
    assert c.thread_size == "M16"
    assert c.embedment_depth_mm == 125
    assert c.cracked_concrete_approved is True


def test_drop_in_internal_thread_anchor():
    texts = [{
        "id": "anc_5",
        "text": "FA-05 M10 Drop-In Anchor HKD Flush Mount in Concrete Slab Soffit",
        "coordinates": (80.0, 90.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_type == "DROP_IN_ANCHOR"
    assert c.thread_size == "M10"


def test_hcr_corrosion_resistant():
    texts = [{
        "id": "anc_6",
        "text": "ANC-06 M16 Chemical Anchor High Corrosion Resistance HCR Steel for Swimming Pool Atmosphere",
        "coordinates": (90.0, 100.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.steel_material == "HCR_CORROSION"
    assert c.thread_size == "M16"


def test_hit_re_adhesive_injection():
    texts = [{
        "id": "anc_7",
        "text": "CA-07 HIT-RE 500 Epoxy Adhesive Anchor with M30 Threaded Rod Hef=300mm",
        "coordinates": (110.0, 120.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_type == "CHEMICAL_EPOXY_STUD"
    assert c.thread_size == "M30"
    assert c.embedment_depth_mm == 300


def test_negative_lookalike_starter_bar():
    texts = [{
        "id": "neg_1",
        "text": "N16 Starter Bar with 600mm Lap Length into Foundation",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_drywall():
    texts = [{
        "id": "neg_2",
        "text": "Drywall Anchor Spring Toggle in Plasterboard Ceiling",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 0


def test_negative_lookalike_brick_tie():
    texts = [{
        "id": "neg_3",
        "text": "Cavity Brick Tie Stainless Steel to Timber Stud",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 0


def test_candidate_contract_immutability():
    texts = [{
        "id": "anc_8",
        "text": "ANC-08 Post-Installed Anchor M16",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    c = candidates[0]
    assert c.status == "CANDIDATE"
    assert c.commercial_projection_allowed is False
    assert c.takeoff_eligible is False
    with pytest.raises(Exception):
        c.status = "FIRM"


def test_candidate_to_dict():
    texts = [{
        "id": "anc_9",
        "text": "ANC-09: Chemical Anchor M20",
        "coordinates": (15.0, 25.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    d = candidates[0].to_dict()
    assert d["tag"] == "ANC-09"
    assert d["thread_size"] == "M20"
    assert d["status"] == "CANDIDATE"
    assert d["commercial_projection_allowed"] is False


def test_max_safety_primitives_cap():
    texts = [
        {"id": f"anc_{i}", "text": "ANC-01 Chemical Anchor", "coordinates": (0.0, 0.0)}
        for i in range(50)
    ]
    candidates = extract_post_installed_anchor_items(texts, max_primitives=15)
    assert len(candidates) == 15


def test_empty_drawing_texts():
    candidates = extract_post_installed_anchor_items([])
    assert len(candidates) == 0


def test_unmatched_generic_text():
    texts = [{"id": "gen_1", "text": "Granite floor pavers 400x400", "coordinates": (0.0, 0.0)}]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 0


def test_default_fallbacks():
    texts = [{
        "id": "anc_def",
        "text": "Post-Installed Chemical Anchor Stud",
        "coordinates": (10.0, 20.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.tag == "ANC-ITEM"
    assert c.anchor_type == "CHEMICAL_EPOXY_STUD"
    assert c.steel_material == "GRADE_8_8_GALV"
    assert c.cracked_concrete_approved is False


def test_hus_4_screw_anchor():
    texts = [{
        "id": "anc_hus",
        "text": "HA-10 HUS-4 Screw Anchor M16 Hef=120mm Cracked Concrete",
        "coordinates": (12.0, 22.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_type == "CONCRETE_SCREW_BOLT"
    assert c.thread_size == "M16"
    assert c.embedment_depth_mm == 120
    assert c.cracked_concrete_approved is True


def test_m36_large_size():
    texts = [{
        "id": "anc_large",
        "text": "UA-11 Undercut Anchor M36 Hef=400mm Grade 8.8",
        "coordinates": (5.0, 10.0)
    }]
    candidates = extract_post_installed_anchor_items(texts)
    assert len(candidates) == 1
    c = candidates[0]
    assert c.anchor_type == "MECHANICAL_UNDERCUT"
    assert c.thread_size == "M36"
    assert c.embedment_depth_mm == 400
