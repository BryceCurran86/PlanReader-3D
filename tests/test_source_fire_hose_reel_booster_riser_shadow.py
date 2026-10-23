"""
test_source_fire_hose_reel_booster_riser_shadow.py

Unit tests for SourceFireHoseReelBoosterRiserShadowAuthority.
"""

import pytest
from pb_source_fire_hose_reel_booster_riser_shadow import (
    SourceFireHoseReelBoosterRiserShadowAuthority,
    FireApparatusType,
    MountingEnclosureType,
    FireApparatusSpec,
    FireApparatusExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_fire_apparatus_callout_parsing():
    parsed1 = SourceFireHoseReelBoosterRiserShadowAuthority.parse_callout(
        "36m x 19mm FIRE HOSE REEL IN RECESSED CABINET W/ DN25 ISOLATION VALVE"
    )
    assert parsed1["apparatus_type"] == FireApparatusType.FIXED_FIRE_HOSE_REEL
    assert parsed1["mounting_type"] == MountingEnclosureType.RECESSED_WALL_CABINET
    assert parsed1["hose_length_m"] == 36.0
    assert parsed1["hose_diameter_mm"] == 19.0
    assert parsed1["valve_diameter_mm"] == 25.0

    parsed2 = SourceFireHoseReelBoosterRiserShadowAuthority.parse_callout(
        "36m x 25mm SWING ARM FHR SURFACE MOUNTED"
    )
    assert parsed2["apparatus_type"] == FireApparatusType.SWINGING_ARM_FIRE_HOSE_REEL
    assert parsed2["mounting_type"] == MountingEnclosureType.SURFACE_MOUNTED_CABINET
    assert parsed2["hose_length_m"] == 36.0
    assert parsed2["hose_diameter_mm"] == 25.0

    parsed3 = SourceFireHoseReelBoosterRiserShadowAuthority.parse_callout(
        "DN65 WET RISER LANDING VALVE IN FIRE STAIR"
    )
    assert parsed3["apparatus_type"] == FireApparatusType.WET_RISER_LANDING_VALVE
    assert parsed3["valve_diameter_mm"] == 65.0

    parsed4 = SourceFireHoseReelBoosterRiserShadowAuthority.parse_callout(
        "4-WAY BREECHING BOOSTER INLET CABINET"
    )
    assert parsed4["apparatus_type"] == FireApparatusType.EXTERNAL_BREECHING_INLET
    assert parsed4["inlet_ways_count"] == 4


def test_fire_apparatus_point_snapping():
    pt = (123.4, 567.8)
    snapped = SourceFireHoseReelBoosterRiserShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 567.5)


def test_fire_apparatus_evaluation_quantities():
    raw_data = [
        {
            "apparatus_id": "FHR-01",
            "location_point": (100.0, 200.0),
            "callout": "36m x 19mm FIRE HOSE REEL IN RECESSED CABINET W/ DN25 ISOLATION VALVE",
            "level_id": "L01",
            "host_wall_id": "W-101",
        },
        {
            "apparatus_id": "LV-01",
            "location_point": (150.0, 200.0),
            "callout": "DN65 WET RISER LANDING VALVE IN FIRE STAIR",
            "level_id": "L01",
            "host_wall_id": "W-STAIR-01",
        },
        {
            "apparatus_id": "BR-01",
            "location_point": (10.0, 10.0),
            "callout": "4-WAY BREECHING BOOSTER INLET CABINET SURFACE MOUNTED",
            "level_id": "L01",
            "host_wall_id": "W-EXT-01",
        },
    ]

    result = SourceFireHoseReelBoosterRiserShadowAuthority.evaluate_apparatus(raw_data)
    assert len(result.apparatus_list) == 3
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_apparatus_count == 3
    assert q.total_hose_reels_count == 1
    assert q.total_landing_valves_count == 1
    assert q.total_breeching_inlets_count == 1

    assert q.count_by_type[FireApparatusType.FIXED_FIRE_HOSE_REEL.value] == 1
    assert q.count_by_type[FireApparatusType.WET_RISER_LANDING_VALVE.value] == 1
    assert q.count_by_type[FireApparatusType.EXTERNAL_BREECHING_INLET.value] == 1

    assert q.count_by_mounting[MountingEnclosureType.RECESSED_WALL_CABINET.value] == 2
    assert q.count_by_mounting[MountingEnclosureType.SURFACE_MOUNTED_CABINET.value] == 1
