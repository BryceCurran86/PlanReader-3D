"""Tests for Precast Insulated Sandwich Concrete Panel & Composite Tie Shadow Authority."""

import pytest
from pb_source_insulated_sandwich_concrete_panel_tie_shadow import (
    SandwichPanelCandidate,
    extract_sandwich_panels,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_insulated_sandwich_panel():
    data = [{
        "id": "s1",
        "text": "SWP-01 PRECAST INSULATED SANDWICH PANEL 75/50/150MM WITH XPS INSULATION AND GFRP FIBERGLASS COMPOSITE TIES",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].panel_tag == "SWP-01"
    assert res[0].outer_wythe_mm == 75
    assert res[0].insulation_core_mm == 50
    assert res[0].inner_wythe_mm == 150
    assert res[0].total_thickness_mm == 275
    assert res[0].insulation_type == "XPS"
    assert res[0].connector_tie_type == "FIBERGLASS_GFRP"
    assert res[0].is_non_conductive is True


def test_thermomass_composite_pins():
    data = [{
        "id": "s2",
        "text": "ISP-02 THERMOMASS INSULATED PRECAST 100-75-175 PIR INSULATION",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].panel_tag == "ISP-02"
    assert res[0].outer_wythe_mm == 100
    assert res[0].insulation_core_mm == 75
    assert res[0].inner_wythe_mm == 175
    assert res[0].total_thickness_mm == 350
    assert res[0].insulation_type == "PIR"
    assert res[0].is_non_conductive is True


def test_basalt_fiber_tie():
    data = [{
        "id": "s3",
        "text": "PCW-01 PRECAST SANDWICH WALL WITH BASALT BFRP CONNECTOR TIES 80/60/160",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].connector_tie_type == "BASALT_BFRP"
    assert res[0].is_non_conductive is True
    assert res[0].total_thickness_mm == 300


def test_carbon_fiber_grid():
    data = [{
        "id": "s4",
        "text": "SWP-03 INSULATED PRECAST PANEL WITH CARBON GRID CFRP CONNECTOR EPS INSULATION",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].connector_tie_type == "CARBON_CFRP"
    assert res[0].insulation_type == "EPS"
    assert res[0].is_non_conductive is True


def test_stainless_steel_truss_tie():
    data = [{
        "id": "s5",
        "text": "SANDWICH PANEL 75/50/150 WITH STAINLESS STEEL TRUSS TIES",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].connector_tie_type == "STAINLESS_STEEL"
    assert res[0].is_non_conductive is False


def test_phenolic_foam_insulation():
    data = [{
        "id": "s6",
        "text": "INSULATED WALL PANEL WITH PHENOLIC FOAM CORE 75/40/150",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].insulation_type == "PHENOLIC"
    assert res[0].insulation_core_mm == 40


def test_total_thickness_fallback():
    data = [{
        "id": "s7",
        "text": "SP-04 320MM TOTAL PANEL THICKNESS INSULATED PRECAST",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].total_thickness_mm == 320
    assert res[0].panel_tag == "SP-04"


def test_three_layer_panel():
    data = [{
        "id": "s8",
        "text": "THREE-LAYER PANEL WITH NON-CONDUCTIVE COMPOSITE PINS",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].is_non_conductive is True
    assert res[0].connector_tie_type == "FIBERGLASS_GFRP"


def test_extruded_polystyrene_spelling():
    data = [{
        "id": "s9",
        "text": "PRECAST SANDWICH WITH EXTRUDED POLYSTYRENE CORE 70/60/150",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].insulation_type == "XPS"


def test_polyisocyanurate_spelling():
    data = [{
        "id": "s10",
        "text": "INSULATED PRECAST WITH POLYISOCYANURATE 80/80/160",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].insulation_type == "PIR"
    assert res[0].total_thickness_mm == 320


def test_negative_drywall_partition():
    data = [{"id": "n1", "text": "DRYWALL PARTITION 92MM STUD", "coordinates": (0.0, 0.0)}]
    assert len(extract_sandwich_panels(data)) == 0


def test_negative_timber_stud_wall():
    data = [{"id": "n2", "text": "TIMBER STUD WALL 90x45", "coordinates": (0.0, 0.0)}]
    assert len(extract_sandwich_panels(data)) == 0


def test_negative_curtain_wall_transom():
    data = [{"id": "n3", "text": "CURTAIN WALL TRANSOM 150MM", "coordinates": (0.0, 0.0)}]
    assert len(extract_sandwich_panels(data)) == 0


def test_negative_masonry_cavity_tie():
    data = [{"id": "n4", "text": "MASONRY CAVITY TIE ONLY", "coordinates": (0.0, 0.0)}]
    assert len(extract_sandwich_panels(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((24.9, 49.8), tolerance=2.5)
    assert pt == (25.0, 50.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "SWP-1 SANDWICH PANEL", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_sandwich_panels(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = SandwichPanelCandidate(
        item_id="cand_1",
        panel_tag="SWP-01",
        outer_wythe_mm=75,
        insulation_core_mm=50,
        inner_wythe_mm=150,
        total_thickness_mm=275,
        insulation_type="XPS",
        connector_tie_type="FIBERGLASS_GFRP",
        is_non_conductive=True,
        coordinates=(10.0, 20.0),
        raw_text="SWP-01 PANEL",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = SandwichPanelCandidate(
        item_id="cand_2",
        panel_tag="SWP-02",
        outer_wythe_mm=80,
        insulation_core_mm=60,
        inner_wythe_mm=160,
        total_thickness_mm=300,
        insulation_type="PIR",
        connector_tie_type="STANDARD",
        is_non_conductive=False,
        coordinates=(0.0, 0.0),
        raw_text="SWP-02 PANEL",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "s11",
        "text": "SWP-05 PRECAST SANDWICH PANEL 75/50/150",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_sandwich_panels(data)
    d = res[0].to_dict()
    assert d["panel_tag"] == "SWP-05"
    assert d["total_thickness_mm"] == 275
    assert d["status"] == "CANDIDATE"


def test_panel_tag_detection():
    data = [{
        "id": "s12",
        "text": "PANEL-03 INSULATED PRECAST WALL 80/70/150",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_sandwich_panels(data)
    assert len(res) == 1
    assert res[0].panel_tag == "PANEL-03"
    assert res[0].total_thickness_mm == 300
