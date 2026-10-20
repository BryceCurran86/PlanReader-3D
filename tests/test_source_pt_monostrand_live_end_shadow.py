"""
Unit and adversarial test suite for Source Post-Tensioned Monostrand Live End Anchorage Pocket Shadow Authority.
"""

import pytest
from pb_source_pt_monostrand_live_end_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    PTMonostrandLiveEndCallout,
    snap_point,
    parse_pt_monostrand_live_end_callout,
    evaluate_pt_monostrand_live_end_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_pt_monostrand_live_end_callout_basic():
    text = "SLAB EDGE LIVE END STRESSING POCKET 12.7MM UNBONDED MONOSTRAND 120X70MM POCKET WITH R10 SPIRAL NON-SHRINK GROUT 65MM COVER"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7
    assert parsed["tendon_type"] == "UNBONDED_MONOSTRAND"
    assert parsed["pocket_width_mm"] == 120.0
    assert parsed["pocket_depth_mm"] == 70.0
    assert parsed["bursting_reinforcement"] == "HELICAL_SPIRAL"
    assert parsed["grout_infill_type"] == "NON_SHRINK_GROUT"
    assert parsed["edge_cover_mm"] == 65.0


def test_parse_pt_monostrand_live_end_bonded_large():
    text = "PT ANCHORAGE 15.2MM BONDED FLAT DUCT 150X75 BLOCKOUT WITH HAIRPIN STIRRUP EPOXY GROUT 75MM COVER"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 15.2
    assert parsed["tendon_type"] == "BONDED_FLAT_DUCT"
    assert parsed["pocket_width_mm"] == 150.0
    assert parsed["pocket_depth_mm"] == 75.0
    assert parsed["bursting_reinforcement"] == "HAIRPIN_STIRRUP"
    assert parsed["grout_infill_type"] == "EPOXY_GROUT"
    assert parsed["edge_cover_mm"] == 75.0


def test_parse_pt_monostrand_imperial_dia():
    text = "MONOSTRAND ANCHOR 0.6 IN STRAND DRY-PACK MORTAR"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 15.2
    assert parsed["grout_infill_type"] == "DRY_PACK_MORTAR"


def test_parse_unrelated():
    assert parse_pt_monostrand_live_end_callout("STANDARD REINFORCING BAR SLAB") is None
    assert parse_pt_monostrand_live_end_callout("ALUMINIUM BALUSTRADE") is None


def test_evaluate_pt_monostrand_live_end_shadow_single():
    callouts = ["LIVE END STRESSING POCKET 12.7MM 120X70"]
    positions = [(10.1, 20.2)]
    results = evaluate_pt_monostrand_live_end_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_pt_monostrand_live_end_shadow_dict():
    items = [{"text": "PT STRESSING RECESS 15.2MM", "position": (5.0, 7.6)}]
    results = evaluate_pt_monostrand_live_end_shadow(items)
    assert len(results) == 1
    assert results[0].strand_diameter_mm == 15.2
    assert results[0].position == (5.0, 7.5)


def test_evaluate_pt_monostrand_live_end_shadow_no_positions():
    results = evaluate_pt_monostrand_live_end_shadow(["LIVE-END ANCHOR"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_pt_monostrand_live_end_shadow_safety_cap():
    huge_input = ["LIVE END STRESSING POCKET"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_pt_monostrand_live_end_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_pt_monostrand_live_end_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "LIVE END ANCHOR", "ROOM 101"]
    results = evaluate_pt_monostrand_live_end_shadow(items)
    assert len(results) == 1
    assert results[0].raw_text == "LIVE END ANCHOR"


def test_bursting_u_bar():
    text = "STRESSING POCKET WITH U-BAR BURSTING REINFORCEMENT"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["bursting_reinforcement"] == "HAIRPIN_STIRRUP"


def test_bursting_spiral():
    text = "ANCHORAGE POCKET WITH HELICAL SPIRAL"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["bursting_reinforcement"] == "HELICAL_SPIRAL"


def test_default_values():
    text = "SLAB EDGE ANCHORAGE"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7
    assert parsed["tendon_type"] == "UNBONDED_MONOSTRAND"
    assert parsed["pocket_width_mm"] == 120.0
    assert parsed["pocket_depth_mm"] == 70.0
    assert parsed["bursting_reinforcement"] == "HELICAL_SPIRAL"
    assert parsed["grout_infill_type"] == "NON_SHRINK_GROUT"
    assert parsed["edge_cover_mm"] == 65.0


def test_snapping_precision():
    callouts = ["TENDON ANCHORAGE"]
    positions = [(12.49, 13.76)]
    results = evaluate_pt_monostrand_live_end_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_half_inch_strand():
    text = "LIVE END 1/2\" STRAND"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["strand_diameter_mm"] == 12.7


def test_epoxy_grout_trigger():
    text = "LIVE END STRESSING RECESS WITH EPOXY GROUT"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["grout_infill_type"] == "EPOXY_GROUT"


def test_custom_cover():
    text = "STRESSING POCKET 50MM COVER"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["edge_cover_mm"] == 50.0


def test_invalid_item_types():
    results = evaluate_pt_monostrand_live_end_shadow([123, None, object()])
    assert results == []


def test_recess_dimensions_pattern():
    text = "LIVE END POCKET 100X60 BLOCKOUT"
    parsed = parse_pt_monostrand_live_end_callout(text)
    assert parsed is not None
    assert parsed["pocket_width_mm"] == 100.0
    assert parsed["pocket_depth_mm"] == 60.0
