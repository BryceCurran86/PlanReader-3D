"""
Tests for Source Stormwater Siphon Roof Drainage Primus Baffle & Air Baffle Shadow Authority.
"""

import pytest
from pb_source_siphonic_roof_drain_baffle_shadow import (
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
    SiphonicRoofDrainBaffleCallout,
    snap_point,
    parse_siphonic_roof_drain_baffle_callout,
    extract_siphonic_roof_drain_baffle_candidates,
    validate_siphonic_roof_drain_baffle_system,
)


def test_snap_point_regular():
    pt = snap_point(14.8, 29.3, snap_tol=2.5)
    assert pt == (15.0, 30.0)


def test_snap_point_zero_tolerance():
    pt = snap_point(14.8, 29.3, snap_tol=0.0)
    assert pt == (14.8, 29.3)


def test_parse_none_on_irrelevant_text():
    assert parse_siphonic_roof_drain_baffle_callout("ALUMINUM SKIRTING 100MM") is None
    assert parse_siphonic_roof_drain_baffle_callout("FIRE RATED PLASTERBOARD WALL") is None
    assert parse_siphonic_roof_drain_baffle_callout("LIGHT FITTING LED TROFFER") is None


def test_parse_siphonic_outlet_primus_baffle():
    text = "SIPHONIC ROOF DRAIN WITH PRIMUS BAFFLE 18.5 L/S DN75 STAINLESS STEEL 316 LEAF GUARD BASKET AND CLAMPING FLANGE"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["outlet_type"] == "SIPHONIC_OUTLET_PRIMUS_BAFFLE"
    assert parsed["design_flow_lps"] == 18.5
    assert parsed["tailpipe_dn"] == "DN75"
    assert parsed["baffle_material"] == "STAINLESS_STEEL_316"
    assert parsed["grate_guard_type"] == "LEAF_GUARD_BASKET"
    assert parsed["membrane_flange_connection"] == "STAINLESS_CLAMPING_FLANGE"
    assert parsed["drainage_system"] == "SIPHONIC_STORMWATER"


def test_parse_anti_vortex_air_plate_overflow():
    text = "SECONDARY OVERFLOW SIPHON DRAIN WITH ANTI-VORTEX AIR BAFFLE PLATE 25 L/S DN110 AND GRAVEL GUARD COLLAR"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["outlet_type"] == "ANTI_VORTEX_AIR_PLATE"
    assert parsed["drainage_system"] == "SECONDARY_OVERFLOW_SIPHON"
    assert parsed["design_flow_lps"] == 25.0
    assert parsed["tailpipe_dn"] == "DN110"
    assert parsed["grate_guard_type"] == "GRAVEL_GRATE_COLLAR"


def test_parse_box_gutter_siphon_drain():
    text = "BOX GUTTER SUMP SIPHON DRAIN 12 L/S DN50 WITH UV STABILIZED POLYPROPYLENE AIR BAFFLE"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["outlet_type"] == "GUTTER_SUMP_SIPHON_DRAIN"
    assert parsed["tailpipe_dn"] == "DN50"
    assert parsed["design_flow_lps"] == 12.0
    assert parsed["baffle_material"] == "UV_STABILIZED_POLYPROPYLENE"


def test_parse_parapet_scupper_siphon():
    text = "PARAPET SCUPPER SIPHONIC ROOF OUTLET 14 L/S DN90 WITH CAST ALUMINIUM AIR BAFFLE"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["outlet_type"] == "PARAPET_SCUPPER_SIPHON_OUTLET"
    assert parsed["baffle_material"] == "CAST_ALUMINUM"
    assert parsed["tailpipe_dn"] == "DN90"
    assert parsed["design_flow_lps"] == 14.0


def test_parse_terrace_flat_grate():
    text = "PLUVIA SIPHONIC ROOF OUTLET WITH FLAT TERRACE GRATE AND EPDM WATERPROOFING COLLAR"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["grate_guard_type"] == "FLAT_TERRACE_GRATE"
    assert parsed["membrane_flange_connection"] == "EPDM_WATERPROOFING_COLLAR"


def test_parse_bituminous_torch_on_flange():
    text = "FASTFLOW SYPHONIC DRAIN DN125 WITH TORCH-ON BITUMINOUS FLANGE"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["membrane_flange_connection"] == "BITUMINOUS_FLANGE"
    assert parsed["tailpipe_dn"] == "DN125"


def test_parse_mm_dropper_diameter():
    text = "SYFON SIPHONIC ROOF SUMP 160 MM DROPPER 35 LPS"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["tailpipe_dn"] == "DN160"
    assert parsed["design_flow_lps"] == 35.0


def test_extract_siphonic_roof_drain_baffle_candidates():
    items = [
        ("SIPHONIC ROOF DRAIN WITH PRIMUS BAFFLE 18.5 L/S DN75", (100.2, 200.3)),
        ("MASONRY BLOCK WALL", (40.0, 50.0)),
        ("SECONDARY OVERFLOW SIPHON DRAIN WITH ANTI-VORTEX AIR BAFFLE 25 L/S", (300.0, 400.0)),
    ]
    candidates = extract_siphonic_roof_drain_baffle_candidates(items)
    assert len(candidates) == 2
    assert candidates[0].position == (100.0, 200.0)
    assert candidates[0].status == "CANDIDATE"
    assert not candidates[0].commercial_projection_allowed
    assert not candidates[0].takeoff_eligible


def test_max_safety_cap():
    items = [
        (f"SIPHONIC ROOF DRAIN {i}", (float(i), float(i)))
        for i in range(50)
    ]
    candidates = extract_siphonic_roof_drain_baffle_candidates(items, max_cap=11)
    assert len(candidates) == 11


def test_system_validation_summary():
    items = [
        ("SIPHONIC ROOF DRAIN WITH PRIMUS BAFFLE 18.5 L/S DN75", (10.0, 20.0)),
        ("SECONDARY OVERFLOW SIPHON DRAIN WITH ANTI-VORTEX AIR BAFFLE 25 L/S", (30.0, 40.0)),
        ("BOX GUTTER SUMP SIPHON DRAIN 12 L/S DN50", (50.0, 60.0)),
    ]
    candidates = extract_siphonic_roof_drain_baffle_candidates(items)
    summary = validate_siphonic_roof_drain_baffle_system(candidates)
    assert summary["total_candidates"] == 3
    assert summary["overflow_count"] == 1
    assert summary["rated_flow_count"] == 3
    assert summary["all_shadow_status"] is True
    assert summary["all_projection_disallowed"] is True
    assert summary["all_takeoff_disallowed"] is True


def test_candidate_dataclass_immutability():
    cand = SiphonicRoofDrainBaffleCallout(
        raw_text="SAMPLE",
        outlet_type="SIPHONIC_OUTLET_PRIMUS_BAFFLE",
        baffle_material="STAINLESS_STEEL_316",
        design_flow_lps=18.5,
        tailpipe_dn="DN75",
        grate_guard_type="LEAF_GUARD_BASKET",
        membrane_flange_connection="STAINLESS_CLAMPING_FLANGE",
        drainage_system="SIPHONIC_STORMWATER",
    )
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_empty_input_handling():
    candidates = extract_siphonic_roof_drain_baffle_candidates([])
    assert len(candidates) == 0
    summary = validate_siphonic_roof_drain_baffle_system([])
    assert summary["total_candidates"] == 0
    assert summary["overflow_count"] == 0


def test_adversarial_partial_substrings():
    assert parse_siphonic_roof_drain_baffle_callout("GRAVITY ROOF DRAIN 100MM PVC") is None
    assert parse_siphonic_roof_drain_baffle_callout("FLOOR WASTE GULLY TRAP") is None
    assert parse_siphonic_roof_drain_baffle_callout("PLUVIA CHEMICAL STORAGE TANK") is None


def test_emergency_siphon_overflow():
    text = "EMERGENCY SIPHON ROOF OUTLET DN110 30 L/SEC"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["drainage_system"] == "SECONDARY_OVERFLOW_SIPHON"
    assert parsed["design_flow_lps"] == 30.0
    assert parsed["tailpipe_dn"] == "DN110"


def test_vortex_baffle_trigger():
    text = "VORTEX BAFFLE ROOF DRAIN 15 L/S DN75"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["outlet_type"] == "ANTI_VORTEX_AIR_PLATE"
    assert parsed["design_flow_lps"] == 15.0


def test_dn200_dropper():
    text = "SIPHONIC ROOF OUTLET DN200 65 L/S"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["tailpipe_dn"] == "DN200"
    assert parsed["design_flow_lps"] == 65.0


def test_cast_alloy_baffle_material():
    text = "SYPHONIC DRAIN WITH CAST ALLOY AIR BAFFLE"
    parsed = parse_siphonic_roof_drain_baffle_callout(text)
    assert parsed is not None
    assert parsed["baffle_material"] == "CAST_ALUMINUM"
