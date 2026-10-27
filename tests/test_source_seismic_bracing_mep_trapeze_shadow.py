"""Tests for Seismic Bracing for Suspended MEP Services & Trapeze Shadow Authority."""

import pytest
from pb_source_seismic_bracing_mep_trapeze_shadow import (
    SeismicBraceCandidate,
    extract_seismic_braces,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_transverse_seismic_brace():
    data = [{
        "id": "sb1",
        "text": "SB-01 TRANSVERSE SEISMIC BRACE FOR DUCTWORK TRAPEZE 41x41 STRUT M12 DROP ROD AS 1170.4",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].tag == "SB-01"
    assert res[0].brace_orientation == "TRANSVERSE"
    assert res[0].brace_mechanism == "RIGID_STRUT"
    assert res[0].mep_service == "DUCTWORK"
    assert res[0].channel_size_mm == "41x41"
    assert res[0].drop_rod_mm == 12
    assert res[0].design_standard == "AS1170_4"


def test_longitudinal_cable_sway_brace():
    data = [{
        "id": "sb2",
        "text": "SWAY-02 LONGITUDINAL CABLE SWAY BRACE FOR CABLE TRAY NZS 4219",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].tag == "SWAY-02"
    assert res[0].brace_orientation == "LONGITUDINAL"
    assert res[0].brace_mechanism == "CABLE_SWAY"
    assert res[0].mep_service == "CABLE_TRAY"
    assert res[0].design_standard == "NZS4219"


def test_four_way_seismic_brace():
    data = [{
        "id": "sb3",
        "text": "SEIS-03 4-WAY SEISMIC RESTRAINT FOR PIPE RACK WITH M16 DROP ROD SMACNA",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].brace_orientation == "FOUR_WAY"
    assert res[0].mep_service == "PIPE_RACK"
    assert res[0].drop_rod_mm == 16
    assert res[0].design_standard == "SMACNA"


def test_busduct_seismic_trapeze():
    data = [{
        "id": "sb4",
        "text": "TR-04 SEISMIC TRAPEZE FOR BUSDUCT 41x82 DOUBLE STRUT",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].mep_service == "BUSDUCT"
    assert res[0].channel_size_mm == "41x82"


def test_rod_stiffener_brace():
    data = [{
        "id": "sb5",
        "text": "SEISMIC RESTRAINT WITH ROD STIFFENER ANGLE",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].brace_mechanism == "ROD_STIFFENER"


def test_41x21_shallow_strut():
    data = [{
        "id": "sb6",
        "text": "SEISMIC BRACE UNISTRUT 41x21 FOR LIGHTWEIGHT DUCT",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].channel_size_mm == "41x21"


def test_m10_drop_rod():
    data = [{
        "id": "sb7",
        "text": "SEISMIC TRAPEZE WITH M10 THREADED DROP ROD",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].drop_rod_mm == 10


def test_asce_7_standard():
    data = [{
        "id": "sb8",
        "text": "TRANSVERSE SEISMIC BRACE PER ASCE 7-16",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].design_standard == "ASCE7"


def test_aircraft_cable():
    data = [{
        "id": "sb9",
        "text": "AIRCRAFT CABLE SEISMIC RESTRAINT FOR CABLE TRAY",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].brace_mechanism == "CABLE_SWAY"


def test_ladder_tray_mep_service():
    data = [{
        "id": "sb10",
        "text": "SEISMIC BRACE FOR LADDER TRAY",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].mep_service == "CABLE_TRAY"


def test_negative_roof_truss():
    data = [{"id": "n1", "text": "ROOF TRUSS TIE DOWN ONLY", "coordinates": (0.0, 0.0)}]
    assert len(extract_seismic_braces(data)) == 0


def test_negative_wall_tie():
    data = [{"id": "n2", "text": "CAVITY MASONRY WALL TIE", "coordinates": (0.0, 0.0)}]
    assert len(extract_seismic_braces(data)) == 0


def test_negative_expansion_joint():
    data = [{"id": "n3", "text": "SEISMIC EXPANSION JOINT ONLY FLOOR COVER", "coordinates": (0.0, 0.0)}]
    assert len(extract_seismic_braces(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((29.9, 59.8), tolerance=2.5)
    assert pt == (30.0, 60.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "SB-1 SEISMIC BRACE", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_seismic_braces(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = SeismicBraceCandidate(
        item_id="cand_1",
        brace_orientation="TRANSVERSE",
        brace_mechanism="RIGID_STRUT",
        mep_service="DUCTWORK",
        tag="SB-01",
        drop_rod_mm=12,
        channel_size_mm="41x41",
        design_standard="AS1170_4",
        coordinates=(10.0, 20.0),
        raw_text="SB-01 SEISMIC BRACE",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = SeismicBraceCandidate(
        item_id="cand_2",
        brace_orientation="LONGITUDINAL",
        brace_mechanism="CABLE_SWAY",
        mep_service="CABLE_TRAY",
        tag="SWAY-02",
        drop_rod_mm=None,
        channel_size_mm=None,
        design_standard="STANDARD",
        coordinates=(0.0, 0.0),
        raw_text="SWAY-02 BRACE",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "sb11",
        "text": "SB-05 SEISMIC BRACE TRANSVERSE",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_seismic_braces(data)
    d = res[0].to_dict()
    assert d["tag"] == "SB-05"
    assert d["brace_orientation"] == "TRANSVERSE"
    assert d["status"] == "CANDIDATE"


def test_sr_tag_detection():
    data = [{
        "id": "sb12",
        "text": "SR-03 SEISMIC RESTRAINT WITH 41x41 STRUT",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].tag == "SR-03"
    assert res[0].channel_size_mm == "41x41"


def test_four_way_spelling_variants():
    data = [{
        "id": "sb13",
        "text": "FOUR-WAY SEISMIC BRACING ON PIPE RACK",
        "coordinates": (20.0, 40.0)
    }]
    res = extract_seismic_braces(data)
    assert len(res) == 1
    assert res[0].brace_orientation == "FOUR_WAY"
    assert res[0].mep_service == "PIPE_RACK"
