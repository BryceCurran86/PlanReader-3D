"""Tests for Curtain Wall Perimeter Slab-Edge Firestop & Smoke Seal Shadow Authority."""

import pytest
from pb_source_curtain_wall_perimeter_fire_smoke_curtain_shadow import (
    PerimeterFirestopCandidate,
    extract_perimeter_firestops,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_perimeter_firestop():
    data = [{"id": "f1", "text": "100MM PERIMETER FIRESTOP JOINT WITH MINERAL WOOL SAFING AND ELASTOMERIC SPRAY", "coordinates": (100.2, 200.4)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].gap_width_mm == 100
    assert res[0].safing_type == "MINERAL_WOOL_SAFING"
    assert res[0].smoke_seal_type == "ELASTOMERIC_SPRAY"


def test_frl_fire_rating_extraction():
    data = [{"id": "f2", "text": "PERIMETER FIRESTOP FRL -/120/120 WITH 50MM GAP", "coordinates": (50.0, 75.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].gap_width_mm == 50
    assert res[0].fire_rating_minutes == 120


def test_hour_fire_rating_extraction():
    data = [{"id": "f3", "text": "SLAB-EDGE FIRESTOP 2 HR FIRE RATING 75MM GAP", "coordinates": (10.0, 20.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].fire_rating_minutes == 120
    assert res[0].gap_width_mm == 75


def test_safing_clips_detection():
    data = [{"id": "f4", "text": "CURTAIN WALL FIRESTOP WITH GALV STEEL SAFING CLIPS AT 600 CRS", "coordinates": (0.0, 0.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].has_safing_clips is True


def test_z_bracket_detection():
    data = [{"id": "f5", "text": "SAFING INSULATION SUPPORTED ON Z-BRACKET 150MM VOID", "coordinates": (15.0, 15.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].has_safing_clips is True
    assert res[0].gap_width_mm == 150


def test_silicone_smoke_seal():
    data = [{"id": "f6", "text": "SLAB EDGE FIRESTOP WITH SILICONE SEALANT SMOKE SEAL", "coordinates": (25.0, 25.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].smoke_seal_type == "SILICONE_SEALANT"


def test_intumescent_sealant():
    data = [{"id": "f7", "text": "PERIMETER FIRE BARRIER WITH INTUMESCENT SEALANT", "coordinates": (30.0, 60.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].smoke_seal_type == "INTUMESCENT_SEALANT"


def test_foil_smoke_barrier():
    data = [{"id": "f8", "text": "PERIMETER FIRESTOP WITH SMOKE SEAL FOIL BARRIER", "coordinates": (40.0, 80.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].smoke_seal_type == "FOIL_BARRIER"


def test_ceramic_blanket_safing():
    data = [{"id": "f9", "text": "EDGE OF SLAB FIRE BARRIER CERAMIC BLANKET 3 HR", "coordinates": (50.0, 100.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].safing_type == "CERAMIC_BLANKET"
    assert res[0].fire_rating_minutes == 180


def test_seismic_movement_capability():
    data = [{"id": "f10", "text": "SEISMIC CURTAIN WALL FIRESTOP 100MM GAP", "coordinates": (12.0, 24.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].movement_capability == "SEISMIC"


def test_class_ii_movement():
    data = [{"id": "f11", "text": "SLAB-EDGE FIRESTOP CLASS II MOVEMENT CAPABILITY", "coordinates": (5.0, 10.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].movement_capability == "CLASS_II"


def test_class_iii_movement():
    data = [{"id": "f12", "text": "PERIMETER FIRESTOP CLASS III CYCLIC MOVEMENT", "coordinates": (15.0, 30.0)}]
    res = extract_perimeter_firestops(data)
    assert len(res) == 1
    assert res[0].movement_capability == "CLASS_III"


def test_negative_pipe_penetration():
    data = [{"id": "n1", "text": "PIPE PENETRATION FIRESTOP COLLAR", "coordinates": (0.0, 0.0)}]
    assert len(extract_perimeter_firestops(data)) == 0


def test_negative_cable_tray_collar():
    data = [{"id": "n2", "text": "CABLE TRAY COLLAR FIRESTOP PILLOWS", "coordinates": (0.0, 0.0)}]
    assert len(extract_perimeter_firestops(data)) == 0


def test_negative_masonry_control_joint():
    data = [{"id": "n3", "text": "MASONRY CONTROL JOINT SEALANT", "coordinates": (0.0, 0.0)}]
    assert len(extract_perimeter_firestops(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((22.4, 45.1), tolerance=2.5)
    assert pt == (22.5, 45.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "100MM PERIMETER FIRESTOP", "coordinates": (float(i), float(i))} for i in range(150)]
    res = extract_perimeter_firestops(items, max_primitives=45)
    assert len(res) == 45


def test_candidate_guardrails_default():
    candidate = PerimeterFirestopCandidate(
        item_id="cand_1",
        gap_width_mm=100,
        fire_rating_minutes=120,
        safing_type="MINERAL_WOOL_SAFING",
        smoke_seal_type="ELASTOMERIC_SPRAY",
        has_safing_clips=True,
        movement_capability="CLASS_II",
        coordinates=(10.0, 20.0),
        raw_text="100MM PERIMETER FIRESTOP",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = PerimeterFirestopCandidate(
        item_id="cand_2",
        gap_width_mm=75,
        fire_rating_minutes=60,
        safing_type="MINERAL_WOOL_SAFING",
        smoke_seal_type="STANDARD",
        has_safing_clips=False,
        movement_capability="STANDARD",
        coordinates=(0.0, 0.0),
        raw_text="75MM SLAB EDGE FIRESTOP",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "f13", "text": "100MM PERIMETER FIRESTOP 2 HR", "coordinates": (30.0, 40.0)}]
    res = extract_perimeter_firestops(data)
    d = res[0].to_dict()
    assert d["gap_width_mm"] == 100
    assert d["fire_rating_minutes"] == 120
    assert d["status"] == "CANDIDATE"
