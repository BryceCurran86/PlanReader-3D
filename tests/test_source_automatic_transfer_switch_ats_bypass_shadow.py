"""
tests/test_source_automatic_transfer_switch_ats_bypass_shadow.py

Comprehensive test suite for electrical emergency power automatic transfer switches (ATS),
drawout bypass isolation units, closed transition synchronizers, and manual transfer switches.
"""

import pytest
from pb_source_automatic_transfer_switch_ats_bypass_shadow import (
    AutomaticTransferSwitchCandidate,
    extract_ats_candidates,
    snap_point_to_grid,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_bypass_isolation_ats_extraction():
    prims = [{
        "id": "p1",
        "text": "Bypass Isolation ATS BATS-01 800A 4-Pole 65 kA Open Transition with Generator Engine Start Contacts IP31",
        "x": 100.0,
        "y": 200.0
    }]
    results = extract_ats_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "BYPASS_ISOLATION_ATS"
    assert cand.rated_current_amperes == 800
    assert cand.num_poles == 4
    assert cand.short_circuit_withstand_ka == 65
    assert cand.transition_type == "OPEN_TRANSITION"
    assert cand.has_bypass_isolation is True
    assert cand.has_generator_start_contacts is True
    assert cand.enclosure_rating == "IP31_INDOOR"
    assert cand.tag == "BATS-01"
    assert cand.status == "CANDIDATE"
    assert cand.commercial_projection_allowed is False
    assert cand.takeoff_eligible is False


def test_standard_ats_extraction():
    prims = [{
        "id": "p2",
        "text": "Automatic Transfer Switch ATS-02 400A 4P Mains / Generator Transfer",
        "x": 50.0,
        "y": 75.0
    }]
    results = extract_ats_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "STANDARD_AUTOMATIC_TRANSFER_SWITCH"
    assert cand.rated_current_amperes == 400
    assert cand.num_poles == 4
    assert cand.has_bypass_isolation is False
    assert cand.tag == "ATS-02"


def test_closed_transition_transfer_switch():
    prims = [{
        "id": "p3",
        "text": "Closed Transition ATS CTTS-03 1250A Make-Before-Break Synchronized 85 kA",
        "x": 150.0,
        "y": 300.0
    }]
    results = extract_ats_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "CLOSED_TRANSITION_TRANSFER_SWITCH"
    assert cand.transition_type == "CLOSED_TRANSITION"
    assert cand.rated_current_amperes == 1250
    assert cand.short_circuit_withstand_ka == 85
    assert cand.tag == "CTTS-03"


def test_manual_transfer_switch():
    prims = [{
        "id": "p4",
        "text": "Manual Transfer Switch MTS-04 250A 3-Pole 3-Position Lockable",
        "x": 20.0,
        "y": 40.0
    }]
    results = extract_ats_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "MANUAL_TRANSFER_SWITCH"
    assert cand.num_poles == 3
    assert cand.rated_current_amperes == 250
    assert cand.tag == "MTS-04"


def test_load_shed_priority_controller():
    prims = [{
        "id": "p5",
        "text": "Generator Load Shed Priority Controller ATS Module",
        "x": 30.0,
        "y": 60.0
    }]
    results = extract_ats_candidates(prims)
    assert len(results) == 1
    cand = results[0]
    assert cand.element_type == "LOAD_SHED_PRIORITY_CONTROLLER"


def test_weatherproof_ip54_enclosure():
    prims = [{
        "id": "p6",
        "text": "Automatic Transfer Switch ATS-06 Weatherproof IP54 Outdoor Enclosure",
        "x": 10.0,
        "y": 20.0
    }]
    results = extract_ats_candidates(prims)
    assert len(results) == 1
    assert results[0].enclosure_rating == "IP54_WEATHERPROOF"


def test_negative_lookalike_light_switch():
    prims = [{
        "id": "neg1",
        "text": "Light Switch Plate 2-Gang 10A Architrave",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_ats_candidates(prims) == []


def test_negative_lookalike_ethernet_switch():
    prims = [{
        "id": "neg2",
        "text": "Network Switch 48-Port Gigabit Ethernet Managed",
        "x": 10.0,
        "y": 20.0
    }]
    assert extract_ats_candidates(prims) == []


def test_grid_snapping_precision():
    x, y = 14.8, 29.9
    snapped = snap_point_to_grid(x, y, SNAP_TOLERANCE_PT)
    assert snapped[0] == 15.0
    assert snapped[1] == 30.0


def test_safety_cap_exceeded():
    prims = [{"id": f"p_{i}", "text": "Transfer Switch ATS-1", "x": 0.0, "y": 0.0} for i in range(MAX_SAFETY_CAP_PRIMITIVES + 1)]
    with pytest.raises(ValueError, match="Exceeded safety cap"):
        extract_ats_candidates(prims)


def test_empty_primitives():
    assert extract_ats_candidates([]) == []


def test_unrelated_text():
    prims = [
        {"id": "b1", "text": "", "x": 0.0, "y": 0.0},
        {"id": "b2", "text": "Timber Door Frame Solid Core 2040x820mm", "x": 0.0, "y": 0.0}
    ]
    assert extract_ats_candidates(prims) == []


def test_candidate_frozen_immutability():
    prims = [{"id": "p7", "text": "Transfer Switch ATS-01", "x": 10.0, "y": 20.0}]
    cand = extract_ats_candidates(prims)[0]
    with pytest.raises(Exception):
        cand.status = "APPROVED"


def test_tag_extraction_variants():
    prims = [
        {"id": "t1", "text": "Automatic Switch ATS_10", "x": 0.0, "y": 0.0},
        {"id": "t2", "text": "Bypass ATS BATS-04", "x": 0.0, "y": 0.0},
        {"id": "t3", "text": "Manual Switch MTS_2", "x": 0.0, "y": 0.0},
    ]
    results = extract_ats_candidates(prims)
    assert len(results) == 3
    assert results[0].tag == "ATS_10"
    assert results[1].tag == "BATS-04"
    assert results[2].tag == "MTS_2"


def test_confidence_scoring():
    prims_simple = [{"id": "c1", "text": "Transfer Switch", "x": 0.0, "y": 0.0}]
    prims_rich = [{
        "id": "c2",
        "text": "Automatic Transfer Switch ATS-01 400A 4P 65 kA",
        "x": 0.0,
        "y": 0.0
    }]
    cand_simple = extract_ats_candidates(prims_simple)[0]
    cand_rich = extract_ats_candidates(prims_rich)[0]
    assert cand_rich.confidence > cand_simple.confidence


def test_default_values():
    prims = [{"id": "d1", "text": "Automatic Transfer Switch Panel", "x": 0.0, "y": 0.0}]
    cand = extract_ats_candidates(prims)[0]
    assert cand.rated_current_amperes == 400
    assert cand.num_poles == 4
    assert cand.transition_type == "OPEN_TRANSITION"
    assert cand.short_circuit_withstand_ka == 65
    assert cand.enclosure_rating == "IP31_INDOOR"
    assert cand.tag is None


def test_delayed_transition():
    prims = [{
        "id": "dt1",
        "text": "ATS with Delayed Transition Programmed Neutral Delay",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_ats_candidates(prims)[0]
    assert cand.transition_type == "DELAYED_TRANSITION"


def test_ip65_harsh_rating():
    prims = [{
        "id": "ip65",
        "text": "Transfer Switch IP65 Enclosure Heavy Industrial",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_ats_candidates(prims)[0]
    assert cand.enclosure_rating == "IP65_HARSH"


def test_candidate_id_uniqueness():
    prims = [
        {"id": "u1", "text": "Transfer Switch 1", "x": 0.0, "y": 0.0},
        {"id": "u2", "text": "Transfer Switch 2", "x": 10.0, "y": 10.0}
    ]
    results = extract_ats_candidates(prims)
    assert len(results) == 2
    assert results[0].candidate_id != results[1].candidate_id


def test_current_rating_2000a():
    prims = [{
        "id": "cr1",
        "text": "Bypass Isolation ATS 2000A BATS-20",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_ats_candidates(prims)[0]
    assert cand.rated_current_amperes == 2000


def test_changeover_switch_keyword():
    prims = [{
        "id": "cos1",
        "text": "Changeover Switch 630A 4P COS-01",
        "x": 0.0,
        "y": 0.0
    }]
    cand = extract_ats_candidates(prims)[0]
    assert cand.rated_current_amperes == 630
    assert cand.tag == "COS-01"
