"""Tests for Civil Stormwater Gross Pollutant Trap (GPT) & CDS Unit Shadow Authority."""

import pytest
from pb_source_stormwater_gross_pollutant_trap_cds_shadow import (
    GrossPollutantTrapCandidate,
    extract_gross_pollutant_traps,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_cds_unit():
    data = [{
        "id": "g1",
        "text": "CDS-01 CONTINUOUS DEFLECTIVE SEPARATION UNIT 150 L/S TREATABLE FLOW DN450 PIPE 2.4MM SCREEN CLASS D COVER",
        "coordinates": (100.2, 200.4)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].element_type == "CDS_UNIT"
    assert res[0].tag == "CDS-01"
    assert res[0].treatable_flow_lps == 150.0
    assert res[0].pipe_size_mm == 450
    assert res[0].screen_aperture_mm == 2.4
    assert res[0].cover_class == "CLASS_D"


def test_gross_pollutant_trap_basket():
    data = [{
        "id": "g2",
        "text": "GPT-01 GROSS POLLUTANT TRAP DROP-IN BASKET DN375 PIPE WITH INTERNAL WEIR BYPASS",
        "coordinates": (50.0, 75.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].element_type == "BASKET_GPT"
    assert res[0].tag == "GPT-01"
    assert res[0].pipe_size_mm == 375
    assert res[0].bypass_type == "INTERNAL_WEIR"


def test_hydrodynamic_vortex_separator():
    data = [{
        "id": "g3",
        "text": "HDS-02 HYDRODYNAMIC VORTEX SEPARATOR 250 LPS TREATABLE FLOW 3.5M3 SEDIMENT SUMP",
        "coordinates": (10.0, 20.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].element_type == "HYDRODYNAMIC_SEPARATOR"
    assert res[0].tag == "HDS-02"
    assert res[0].treatable_flow_lps == 250.0
    assert res[0].sediment_storage_m3 == 3.5


def test_baffle_box():
    data = [{
        "id": "g4",
        "text": "STORMWATER BAFFLE BOX WITH 5.0 M3 SEDIMENT STORAGE CLASS B COVER",
        "coordinates": (0.0, 0.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].element_type == "BAFFLE_BOX"
    assert res[0].sediment_storage_m3 == 5.0
    assert res[0].cover_class == "CLASS_B"


def test_micron_screen_conversion():
    data = [{
        "id": "g5",
        "text": "CDS UNIT WITH 1200 MICRON SCREEN DN300",
        "coordinates": (15.0, 15.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].screen_aperture_mm == 1.2
    assert res[0].pipe_size_mm == 300


def test_external_bypass_arrangement():
    data = [{
        "id": "g6",
        "text": "GPT-03 GROSS POLLUTANT TRAP WITH EXTERNAL BYPASS PIT",
        "coordinates": (25.0, 25.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].bypass_type == "EXTERNAL_BYPASS"


def test_offline_sqid_configuration():
    data = [{
        "id": "g7",
        "text": "SQID-1 OFFLINE STORMWATER FILTER CHAMBER 50 L/S",
        "coordinates": (30.0, 60.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].bypass_type == "OFFLINE"
    assert res[0].treatable_flow_lps == 50.0


def test_large_pipe_dn600():
    data = [{
        "id": "g8",
        "text": "CONTINUOUS DEFLECTIVE SEPARATOR DN600 PIPE 400 L/S",
        "coordinates": (40.0, 80.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].pipe_size_mm == 600
    assert res[0].treatable_flow_lps == 400.0


def test_heavy_duty_traffic_cover():
    data = [{
        "id": "g9",
        "text": "GPT-04 GROSS POLLUTANT TRAP WITH HEAVY DUTY TRAFFIC RATED COVER",
        "coordinates": (50.0, 100.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].cover_class == "CLASS_D"


def test_inch_pipe_size():
    data = [{
        "id": "g10",
        "text": "POLLUTANT INTERCEPTOR 18 INCH PIPE 100 L/S",
        "coordinates": (12.0, 24.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].pipe_size_mm == 457


def test_negative_grease_trap():
    data = [{"id": "n1", "text": "TRADE WASTE GREASE TRAP 2000L", "coordinates": (0.0, 0.0)}]
    assert len(extract_gross_pollutant_traps(data)) == 0


def test_negative_sewage_pump():
    data = [{"id": "n2", "text": "SEWAGE PUMP STATION DN100 DISCHARGE", "coordinates": (0.0, 0.0)}]
    assert len(extract_gross_pollutant_traps(data)) == 0


def test_negative_septic_tank():
    data = [{"id": "n3", "text": "SEPTIC TANK 3000L WITH SOAKAWAY", "coordinates": (0.0, 0.0)}]
    assert len(extract_gross_pollutant_traps(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((24.9, 49.8), tolerance=2.5)
    assert pt == (25.0, 50.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "GPT-1 GROSS POLLUTANT TRAP", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_gross_pollutant_traps(items, max_primitives=30)
    assert len(res) == 30


def test_candidate_guardrails_default():
    candidate = GrossPollutantTrapCandidate(
        item_id="cand_1",
        element_type="CDS_UNIT",
        tag="CDS-01",
        treatable_flow_lps=150.0,
        pipe_size_mm=450,
        sediment_storage_m3=2.5,
        screen_aperture_mm=2.4,
        bypass_type="INTERNAL_WEIR",
        cover_class="CLASS_D",
        coordinates=(10.0, 20.0),
        raw_text="CDS-01 UNIT",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = GrossPollutantTrapCandidate(
        item_id="cand_2",
        element_type="BASKET_GPT",
        tag="GPT-02",
        treatable_flow_lps=None,
        pipe_size_mm=300,
        sediment_storage_m3=None,
        screen_aperture_mm=None,
        bypass_type="STANDARD",
        cover_class="STANDARD",
        coordinates=(0.0, 0.0),
        raw_text="GPT-02 BASKET",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{
        "id": "g11",
        "text": "GPT-05 GROSS POLLUTANT TRAP DN375",
        "coordinates": (30.0, 40.0)
    }]
    res = extract_gross_pollutant_traps(data)
    d = res[0].to_dict()
    assert d["tag"] == "GPT-05"
    assert d["pipe_size_mm"] == 375
    assert d["status"] == "CANDIDATE"


def test_wsud_tag_detection():
    data = [{
        "id": "g12",
        "text": "WSUD-01 STORMWATER FILTER CHAMBER 80 L/S",
        "coordinates": (15.0, 30.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].tag == "WSUD-01"
    assert res[0].treatable_flow_lps == 80.0


def test_litres_per_sec_spelling():
    data = [{
        "id": "g13",
        "text": "CDS UNIT 125 LITRES/SEC TREATABLE FLOW",
        "coordinates": (20.0, 40.0)
    }]
    res = extract_gross_pollutant_traps(data)
    assert len(res) == 1
    assert res[0].treatable_flow_lps == 125.0
