"""Tests for Concrete Slab Polished Finish & Penetrating Silicate Densifier Shadow Authority."""

import pytest
from pb_source_polished_concrete_densifier_finish_shadow import (
    PolishedConcreteCandidate,
    extract_polished_concrete,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_honed_satin_finish():
    data = [{
        "id": "p1",
        "text": "PC-01 HONED CONCRETE 800 GRIT SALT AND PEPPER FINISH WITH LITHIUM SILICATE DENSIFIER AND PENETRATING SEALER P3",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].finish_tag == "PC-01"
    assert res[0].sheen_level == "HONED_SATIN"
    assert res[0].aggregate_exposure == "CLASS_B_SALT_PEPPER"
    assert res[0].densifier_type == "LITHIUM_SILICATE"
    assert res[0].has_penetrating_guard is True
    assert res[0].grit_level == 800
    assert res[0].slip_rating == "P3"


def test_high_gloss_polished_finish():
    data = [{
        "id": "p2",
        "text": "POL-02 HIGH GLOSS POLISHED CONCRETE 3000 GRIT WITH COLLOIDAL SILICA DENSIFIER",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].sheen_level == "HIGH_GLOSS"
    assert res[0].grit_level == 3000
    assert res[0].densifier_type == "COLLOIDAL_SILICA"


def test_semi_gloss_1500_grit():
    data = [{
        "id": "p3",
        "text": "PC-03 SEMI-GLOSS DIAMOND POLISH 1500 GRIT FULL EXPOSURE",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].sheen_level == "SEMI_GLOSS"
    assert res[0].aggregate_exposure == "CLASS_D_FULL"
    assert res[0].grit_level == 1500


def test_burnished_slab_finish():
    data = [{
        "id": "p4",
        "text": "FIN-01 BURNISHED CONCRETE SLAB WITH SODIUM SILICATE HARDENER",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].sheen_level == "BURNISHED"
    assert res[0].densifier_type == "SODIUM_SILICATE"


def test_ground_matte_200_grit():
    data = [{
        "id": "p5",
        "text": "GROUND MATTE POLISHED CONCRETE 200 GRIT R10 SLIP RATING",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].sheen_level == "GROUND_MATTE"
    assert res[0].grit_level == 200
    assert res[0].slip_rating == "R10"


def test_cream_polish_class_a():
    data = [{
        "id": "p6",
        "text": "POLISHED CONCRETE SURFACE CREAM POLISH ZERO EXPOSURE",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].aggregate_exposure == "CLASS_A_CREAM"


def test_medium_aggregate_class_c():
    data = [{
        "id": "p7",
        "text": "POLISHED CONCRETE MEDIUM AGGREGATE EXPOSURE",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].aggregate_exposure == "CLASS_C_MEDIUM"


def test_potassium_silicate():
    data = [{
        "id": "p8",
        "text": "CONCRETE DENSIFIER POTASSIUM SILICATE APPLICATION",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].densifier_type == "POTASSIUM_SILICATE"


def test_stain_shield_guard():
    data = [{
        "id": "p9",
        "text": "HONED CONCRETE SLAB FINISH WITH STAIN SHIELD GUARD",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].has_penetrating_guard is True


def test_cf_tag_detection():
    data = [{
        "id": "p10",
        "text": "CF-02 POLISHED CONCRETE SLAB FINISH 400 GRIT",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].finish_tag == "CF-02"
    assert res[0].grit_level == 400


def test_negative_carpet():
    data = [{"id": "n1", "text": "CARPET TILE FINISH TO LEVEL 1", "coordinates": (0.0, 0.0)}]
    assert len(extract_polished_concrete(data)) == 0


def test_negative_vinyl():
    data = [{"id": "n2", "text": "SHEET VINYL COVED SKIRTING", "coordinates": (0.0, 0.0)}]
    assert len(extract_polished_concrete(data)) == 0


def test_negative_ceramic_tile():
    data = [{"id": "n3", "text": "CERAMIC TILE 600x600 WET AREA", "coordinates": (0.0, 0.0)}]
    assert len(extract_polished_concrete(data)) == 0


def test_negative_paint_to_wall():
    data = [{"id": "n4", "text": "PAINT FINISH TO WALL P1", "coordinates": (0.0, 0.0)}]
    assert len(extract_polished_concrete(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((29.9, 59.8), tolerance=2.5)
    assert pt == (30.0, 60.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "PC-1 POLISHED CONCRETE", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_polished_concrete(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = PolishedConcreteCandidate(
        item_id="cand_1",
        finish_tag="PC-01",
        sheen_level="HONED_SATIN",
        aggregate_exposure="CLASS_B_SALT_PEPPER",
        densifier_type="LITHIUM_SILICATE",
        has_penetrating_guard=True,
        grit_level=800,
        slip_rating="P3",
        coordinates=(10.0, 20.0),
        raw_text="PC-01 HONED CONCRETE",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = PolishedConcreteCandidate(
        item_id="cand_2",
        finish_tag="POL-02",
        sheen_level="HIGH_GLOSS",
        aggregate_exposure="STANDARD",
        densifier_type="STANDARD",
        has_penetrating_guard=False,
        grit_level=3000,
        slip_rating=None,
        coordinates=(0.0, 0.0),
        raw_text="POL-02 GLOSS",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "p11",
        "text": "PC-05 POLISHED CONCRETE 800 GRIT",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_polished_concrete(data)
    d = res[0].to_dict()
    assert d["finish_tag"] == "PC-05"
    assert d["grit_level"] == 800
    assert d["status"] == "CANDIDATE"


def test_p4_slip_rating():
    data = [{
        "id": "p12",
        "text": "HONED CONCRETE SLIP RATING P4",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_polished_concrete(data)
    assert len(res) == 1
    assert res[0].slip_rating == "P4"
