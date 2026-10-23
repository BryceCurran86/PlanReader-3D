"""Tests for HVAC Ductwork In-Line Sound Attenuator Silencer Shadow Authority."""

import pytest
from pb_source_acoustic_attenuator_silencer_ductwork_shadow import (
    SoundAttenuatorCandidate,
    extract_sound_attenuators,
    snap_point,
    SNAP_TOLERANCE_PT,
    MAX_SAFETY_CAP_PRIMITIVES,
)


def test_standard_rectangular_attenuator():
    data = [{"id": "a1", "text": "ATT-01 SUPPLY AIR SOUND ATTENUATOR 600x300 L=1200", "coordinates": (100.2, 200.4)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].tag == "ATT-01"
    assert res[0].shape_profile == "RECTANGULAR"
    assert res[0].system_service == "SUPPLY_AIR"
    assert res[0].width_mm == 600
    assert res[0].height_mm == 300
    assert res[0].length_mm == 1200


def test_circular_silencer():
    data = [{"id": "a2", "text": "SIL-02 CIRCULAR ACOUSTIC SILENCER Ø350 L=900", "coordinates": (50.0, 75.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].tag == "SIL-02"
    assert res[0].shape_profile == "CIRCULAR"
    assert res[0].diameter_mm == 350
    assert res[0].length_mm == 900


def test_crosstalk_attenuator():
    data = [{"id": "a3", "text": "CT-1 CROSS-TALK SILENCER 300x200 600 LG", "coordinates": (10.0, 20.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].tag == "CT-1"
    assert res[0].shape_profile == "CROSSTALK"
    assert res[0].width_mm == 300
    assert res[0].height_mm == 200
    assert res[0].length_mm == 600


def test_packless_silencer_classification():
    data = [{"id": "a4", "text": "SILENCER PACKLESS NO MEDIA 900x600 L=1500", "coordinates": (0.0, 0.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].media_type == "PACKLESS"
    assert res[0].width_mm == 900
    assert res[0].height_mm == 600


def test_hygienic_mylar_faced():
    data = [{"id": "a5", "text": "HOSPITAL HYGIENIC MYLAR FACED ATTENUATOR 800x400", "coordinates": (15.0, 15.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].media_type == "HYGIENIC_MYLAR"
    assert res[0].width_mm == 800
    assert res[0].height_mm == 400


def test_dissipative_mineral_wool():
    data = [{"id": "a6", "text": "DISSIPATIVE SOUND ATTENUATOR MINERAL WOOL 500x500", "coordinates": (25.0, 25.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].media_type == "DISSIPATIVE"


def test_return_air_service():
    data = [{"id": "a7", "text": "ATT-03 RETURN AIR ATTENUATOR 1000x500", "coordinates": (30.0, 60.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].system_service == "RETURN_AIR"


def test_exhaust_air_service():
    data = [{"id": "a8", "text": "EA DUCT IN-LINE SILENCER 400x400", "coordinates": (40.0, 80.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].system_service == "EXHAUST_AIR"


def test_outside_air_service():
    data = [{"id": "a9", "text": "OA FRESH AIR ATTENUATOR 1200x800", "coordinates": (50.0, 100.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].system_service == "OUTSIDE_AIR"


def test_elbow_attenuator():
    data = [{"id": "a10", "text": "ELBOW SOUND ATTENUATOR 600x600", "coordinates": (12.0, 24.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].shape_profile == "ELBOW"


def test_round_dia_suffix_extraction():
    data = [{"id": "a11", "text": "ATTENUATOR 250 DIA L=900", "coordinates": (5.0, 10.0)}]
    res = extract_sound_attenuators(data)
    assert len(res) == 1
    assert res[0].shape_profile == "CIRCULAR"
    assert res[0].diameter_mm == 250
    assert res[0].length_mm == 900


def test_negative_fire_damper():
    data = [{"id": "n1", "text": "FD-01 MOTORIZED FIRE DAMPER 600x300", "coordinates": (0.0, 0.0)}]
    assert len(extract_sound_attenuators(data)) == 0


def test_negative_vav_box():
    data = [{"id": "n2", "text": "VAV BOX 02 WITH REHEAT COIL", "coordinates": (0.0, 0.0)}]
    assert len(extract_sound_attenuators(data)) == 0


def test_negative_diffuser():
    data = [{"id": "n3", "text": "SUPPLY AIR SWIRL DIFFUSER 600x600", "coordinates": (0.0, 0.0)}]
    assert len(extract_sound_attenuators(data)) == 0


def test_negative_exhaust_hood():
    data = [{"id": "n4", "text": "KITCHEN EXHAUST CANOPY HOOD 2400x1200", "coordinates": (0.0, 0.0)}]
    assert len(extract_sound_attenuators(data)) == 0


def test_grid_snapping_precision():
    pt = snap_point((12.4, 25.1), tolerance=2.5)
    assert pt == (12.5, 25.0)


def test_safety_primitive_cap():
    items = [{"id": f"cap_{i}", "text": "ATT-1 SOUND ATTENUATOR 600x300", "coordinates": (float(i), float(i))} for i in range(120)]
    res = extract_sound_attenuators(items, max_primitives=40)
    assert len(res) == 40


def test_candidate_guardrails_default():
    candidate = SoundAttenuatorCandidate(
        item_id="cand_1",
        tag="ATT-01",
        shape_profile="RECTANGULAR",
        system_service="SUPPLY_AIR",
        media_type="DISSIPATIVE",
        width_mm=600,
        height_mm=300,
        diameter_mm=None,
        length_mm=1200,
        coordinates=(10.0, 20.0),
        raw_text="ATT-01 SUPPLY AIR SOUND ATTENUATOR",
    )
    assert candidate.status == "CANDIDATE"
    assert candidate.commercial_projection_allowed is False
    assert candidate.takeoff_eligible is False


def test_frozen_immutability():
    candidate = SoundAttenuatorCandidate(
        item_id="cand_2",
        tag="ATT-02",
        shape_profile="CIRCULAR",
        system_service="RETURN_AIR",
        media_type="STANDARD",
        width_mm=None,
        height_mm=None,
        diameter_mm=300,
        length_mm=900,
        coordinates=(0.0, 0.0),
        raw_text="SILENCER 300 DIA",
    )
    with pytest.raises(Exception):
        candidate.status = "PROMOTED"  # type: ignore


def test_to_dict_serialization():
    data = [{"id": "a12", "text": "ATT-05 SOUND ATTENUATOR 800x400 L=1500", "coordinates": (30.0, 40.0)}]
    res = extract_sound_attenuators(data)
    d = res[0].to_dict()
    assert d["tag"] == "ATT-05"
    assert d["width_mm"] == 800
    assert d["height_mm"] == 400
    assert d["length_mm"] == 1500
    assert d["status"] == "CANDIDATE"
