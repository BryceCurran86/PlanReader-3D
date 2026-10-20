"""
Unit and adversarial test suite for Source Post-Tensioned Concrete Monostrand Dead End Onion Anchor Shadow Authority.
"""

import pytest
from pb_source_pt_monostrand_dead_end_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    PTMonostrandDeadEndCallout,
    snap_point,
    parse_pt_monostrand_dead_end_callout,
    evaluate_pt_monostrand_dead_end_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_pt_dead_end_basic():
    text = "SLAB INTERNAL DEAD END ONION ANCHOR 12.7MM STRAND 750MM EMBEDMENT WITH SPIRAL SPRING CLIP AND N12 HAIRPIN TIES 40MM COVER"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7
    assert parsed["anchor_type"] == "HYDRAULIC_ONION_BULB"
    assert parsed["embedment_length_mm"] == 750.0
    assert parsed["restraint_support"] == "SPIRAL_SPRING_CLIP"
    assert parsed["bursting_reinforcement"] == "N12_HAIRPIN_TIES"
    assert parsed["min_cover_mm"] == 40.0


def test_parse_swaged_barrel_large():
    text = "PT DEAD END SWAGED ANCHOR 15.2MM 1000MM EMBEDMENT CHAIR SUPPORT WITH HELICAL SPIRAL 50MM COVER"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 15.2
    assert parsed["anchor_type"] == "SWAGED_BARREL_SLEEVE"
    assert parsed["embedment_length_mm"] == 1000.0
    assert parsed["restraint_support"] == "CHAIR_SUPPORT"
    assert parsed["bursting_reinforcement"] == "HELICAL_SPIRAL"
    assert parsed["min_cover_mm"] == 50.0


def test_parse_bearing_plate_dead_end():
    text = "BLIND ANCHOR WITH BEARING PLATE 600MM DEV"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["anchor_type"] == "PLATE_DEAD_END"
    assert parsed["embedment_length_mm"] == 600.0


def test_parse_unrelated():
    assert parse_pt_monostrand_dead_end_callout("BRICK CAVITY TIE") is None
    assert parse_pt_monostrand_dead_end_callout("ALUMINIUM BALCONY POST") is None


def test_evaluate_pt_dead_end_shadow_single():
    callouts = ["DEAD END ONION ANCHOR 12.7MM"]
    positions = [(10.1, 20.2)]
    results = evaluate_pt_monostrand_dead_end_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_pt_dead_end_shadow_dict():
    items = [{"text": "BULB ANCHOR 15.2MM", "position": (5.0, 7.6)}]
    results = evaluate_pt_monostrand_dead_end_shadow(items)
    assert len(results) == 1
    assert results[0].strand_diameter_mm == 15.2
    assert results[0].position == (5.0, 7.5)


def test_evaluate_pt_dead_end_shadow_no_positions():
    results = evaluate_pt_monostrand_dead_end_shadow(["NON-STRESSING END"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_pt_dead_end_shadow_safety_cap():
    huge_input = ["DEAD END ANCHOR"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_pt_monostrand_dead_end_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_pt_monostrand_dead_end_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "DEAD END ONION ANCHOR", "ROOM 101"]
    results = evaluate_pt_monostrand_dead_end_shadow(items)
    assert len(results) == 1
    assert results[0].strand_diameter_mm == 12.7


def test_passive_anchor_trigger():
    text = "PASSIVE ANCHOR 12.7MM"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7


def test_mesh_tie_support():
    text = "DEAD-END ONION WITH MESH TIE"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["restraint_support"] == "MESH_TIE"


def test_default_values():
    text = "INTERNAL ANCHORAGE"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7
    assert parsed["anchor_type"] == "HYDRAULIC_ONION_BULB"
    assert parsed["embedment_length_mm"] == 750.0
    assert parsed["restraint_support"] == "SPIRAL_SPRING_CLIP"
    assert parsed["bursting_reinforcement"] == "N12_HAIRPIN_TIES"
    assert parsed["min_cover_mm"] == 40.0


def test_snapping_precision():
    callouts = ["PT DEAD END"]
    positions = [(12.49, 13.76)]
    results = evaluate_pt_monostrand_dead_end_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_half_inch_strand():
    text = "DEAD END 0.5\" STRAND"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7


def test_custom_cover():
    text = "ONION ANCHOR 30MM COVER"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["min_cover_mm"] == 30.0


def test_compression_sleeve_trigger():
    text = "DEAD END WITH COMPRESSION SLEEVE"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["anchor_type"] == "SWAGED_BARREL_SLEEVE"


def test_invalid_item_types():
    results = evaluate_pt_monostrand_dead_end_shadow([123, None, object()])
    assert results == []


def test_dead_end_anchorage_trigger():
    text = "DEAD END ANCHORAGE 800MM EMBEDMENT"
    parsed = parse_pt_monostrand_dead_end_callout(text)
    assert parsed is not None
    assert parsed["embedment_length_mm"] == 800.0
