"""
Unit and adversarial test suite for Source Industrial Concrete Slab Sawn Contraction Joint Polyurethane Sealant Shadow Authority.
"""

import pytest
from pb_source_slab_sawcut_sealant_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SlabSawcutSealantCallout,
    snap_point,
    parse_slab_sawcut_sealant_callout,
    evaluate_slab_sawcut_sealant_shadow,
)


def test_snap_point_basic():
    assert snap_point(0.0, 0.0) == (0.0, 0.0)
    assert snap_point(2.4, 2.6) == (2.5, 2.5)
    assert snap_point(5.1, 7.4) == (5.0, 7.5)
    assert snap_point(10.0, 20.0, snap_tol=0.0) == (10.0, 20.0)


def test_parse_sawcut_sealant_basic():
    text = "SLAB SAWCUT CONTRACTION JOINT 4MM WIDE DEPTH D/4 WITH BACKER ROD AND ELASTOMERIC POLYURETHANE JOINT SEALANT"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sawcut_width_mm"] == 4.0
    assert parsed["depth_specification"] == "DEPTH_D_OVER_4"
    assert parsed["depth_numeric_mm"] == 50.0
    assert parsed["sealant_type"] == "ELASTOMERIC_POLYURETHANE"
    assert parsed["backer_rod_required"] is True
    assert parsed["beveled_arris"] is False


def test_parse_polyurea_heavy_traffic():
    text = "SAWN JOINT 5MM WIDE 50MM DEEP WITH SEMI-RIGID POLYUREA JOINT SEALANT FOR FORKLIFT TRAFFIC AND BEVELED ARRIS"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sawcut_width_mm"] == 5.0
    assert parsed["depth_specification"] == "DEPTH_50MM"
    assert parsed["depth_numeric_mm"] == 50.0
    assert parsed["sealant_type"] == "SEMI_RIGID_POLYUREA"
    assert parsed["backer_rod_required"] is False
    assert parsed["beveled_arris"] is True


def test_parse_soff_cut_d_over_3():
    text = "SOFF-CUT EARLY ENTRY SAWCUT 3MM WIDE DEPTH D/3 WITH SILICONE SEALANT"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sawcut_width_mm"] == 3.0
    assert parsed["depth_specification"] == "DEPTH_D_OVER_3"
    assert parsed["sealant_type"] == "SILICONE_SEALANT"


def test_parse_unrelated():
    assert parse_slab_sawcut_sealant_callout("ALUMINIUM BALUSTRADE") is None
    assert parse_slab_sawcut_sealant_callout("CARPET TILES") is None


def test_evaluate_sawcut_shadow_single():
    callouts = ["SAWCUT JOINT 4MM"]
    positions = [(10.1, 20.2)]
    results = evaluate_slab_sawcut_sealant_shadow(callouts, positions=positions)
    assert len(results) == 1
    r = results[0]
    assert r.status == "CANDIDATE"
    assert not r.commercial_projection_allowed
    assert not r.takeoff_eligible
    assert r.position == (10.0, 20.0)


def test_evaluate_sawcut_shadow_dict():
    items = [{"text": "CONTRACTION JOINT SEALANT 5MM", "position": (5.0, 7.6)}]
    results = evaluate_slab_sawcut_sealant_shadow(items)
    assert len(results) == 1
    assert results[0].sawcut_width_mm == 5.0
    assert results[0].position == (5.0, 7.5)


def test_evaluate_sawcut_shadow_no_positions():
    results = evaluate_slab_sawcut_sealant_shadow(["SAWCUT SEALANT"])
    assert len(results) == 1
    assert results[0].position == (0.0, 0.0)


def test_evaluate_sawcut_shadow_safety_cap():
    huge_input = ["SAWCUT JOINT"] * (MAX_SAFETY_CAP_PRIMITIVES + 50)
    results = evaluate_slab_sawcut_sealant_shadow(huge_input)
    assert len(results) == MAX_SAFETY_CAP_PRIMITIVES


def test_constants():
    assert SNAP_TOLERANCE_PT == 2.5
    assert MAX_SAFETY_CAP_PRIMITIVES == 20_000


def test_empty_callouts():
    assert evaluate_slab_sawcut_sealant_shadow([]) == []


def test_unrelated_callout_filtering():
    items = ["DOOR D01", "WINDOW W02", "SAWCUT JOINT 4MM", "ROOM 101"]
    results = evaluate_slab_sawcut_sealant_shadow(items)
    assert len(results) == 1
    assert results[0].sawcut_width_mm == 4.0


def test_control_joint_sealant_trigger():
    text = "CONTROL JOINT SEALANT 6MM JOINT"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sawcut_width_mm"] == 6.0


def test_without_backer_negation():
    text = "SAWCUT SEALANT WITHOUT BACKER ROD"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["backer_rod_required"] is False


def test_default_values():
    text = "SAWN CONTRACTION JOINT"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sawcut_width_mm"] == 4.0
    assert parsed["depth_specification"] == "DEPTH_D_OVER_4"
    assert parsed["depth_numeric_mm"] == 50.0
    assert parsed["sealant_type"] == "ELASTOMERIC_POLYURETHANE"
    assert parsed["backer_rod_required"] is True
    assert parsed["beveled_arris"] is False


def test_snapping_precision():
    callouts = ["SAWCUT CRACK CONTROL"]
    positions = [(12.49, 13.76)]
    results = evaluate_slab_sawcut_sealant_shadow(callouts, positions)
    assert results[0].position == (12.5, 15.0)


def test_shore_a_polyurea():
    text = "SAWCUT JOINT SHORE A80 SEALANT"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sealant_type"] == "SEMI_RIGID_POLYUREA"


def test_45mm_depth():
    text = "SAWCUT JOINT 45MM DEPTH"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["depth_numeric_mm"] == 45.0


def test_chamfer_arris():
    text = "SAWCUT SEALANT WITH CHAMFER"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["beveled_arris"] is True


def test_invalid_item_types():
    results = evaluate_slab_sawcut_sealant_shadow([123, None, object()])
    assert results == []


def test_early_entry_sawcut_trigger():
    text = "EARLY ENTRY SAWCUT 3MM"
    parsed = parse_slab_sawcut_sealant_callout(text)
    assert parsed is not None
    assert parsed["sawcut_width_mm"] == 3.0
