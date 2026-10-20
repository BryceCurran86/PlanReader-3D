"""
test_source_firestop_collar_wrap_shadow.py

Unit tests for SourceFirestopCollarWrapShadowAuthority.
"""

import pytest
from pb_source_firestop_collar_wrap_shadow import (
    SourceFirestopCollarWrapShadowAuthority,
    FirestopDeviceType,
    PipeMaterialType,
    PenetrationOrientation,
    FirestopDeviceSpec,
    FirestopExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_firestop_callout_parsing():
    parsed1 = SourceFirestopCollarWrapShadowAuthority.parse_callout(
        "100mm DIA PVC CAST-IN SLAB FIRE COLLAR 2-HR FRL -/120/120"
    )
    assert parsed1["device_type"] == FirestopDeviceType.CAST_IN_COLLAR
    assert parsed1["pipe_material"] == PipeMaterialType.PVC_DWV
    assert parsed1["nominal_pipe_dia_mm"] == 100.0
    assert parsed1["fire_rating_hours"] == 2
    assert parsed1["orientation"] == PenetrationOrientation.FLOOR_PENETRATION

    parsed2 = SourceFirestopCollarWrapShadowAuthority.parse_callout(
        "65mm RETROFIT SURFACE FIRE COLLAR HDPE WALL PENETRATION 3-HR"
    )
    assert parsed2["device_type"] == FirestopDeviceType.SURFACE_FIRE_COLLAR
    assert parsed2["pipe_material"] == PipeMaterialType.HDPE_DRAIN
    assert parsed2["nominal_pipe_dia_mm"] == 65.0
    assert parsed2["fire_rating_hours"] == 3
    assert parsed2["orientation"] == PenetrationOrientation.WALL_PENETRATION

    parsed3 = SourceFirestopCollarWrapShadowAuthority.parse_callout(
        "50mm INTUMESCENT PIPE WRAP 2HR"
    )
    assert parsed3["device_type"] == FirestopDeviceType.INTUMESCENT_PIPE_WRAP
    assert parsed3["nominal_pipe_dia_mm"] == 50.0
    assert parsed3["fire_rating_hours"] == 2


def test_firestop_snapping():
    pt = (301.2, 598.9)
    snapped = SourceFirestopCollarWrapShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (300.0, 600.0)


def test_firestop_evaluation_quantities():
    raw_data = [
        {
            "device_id": "FS-01",
            "center_point": (100.0, 100.0),
            "callout": "100mm DIA PVC CAST-IN SLAB FIRE COLLAR 2-HR",
            "level_id": "L01",
        },
        {
            "device_id": "FS-02",
            "center_point": (100.0, 200.0),
            "callout": "100mm DIA PVC CAST-IN SLAB FIRE COLLAR 2-HR",
            "level_id": "L01",
        },
        {
            "device_id": "FS-03",
            "center_point": (250.0, 100.0),
            "callout": "65mm RETROFIT SURFACE FIRE COLLAR HDPE WALL PENETRATION 3-HR",
            "level_id": "L01",
        },
    ]

    res = SourceFirestopCollarWrapShadowAuthority.evaluate_firestops(raw_data)

    assert len(res.devices) == 3
    q = res.quantities
    assert q.total_devices_count == 3
    assert q.floor_penetrations_count == 2
    assert q.wall_penetrations_count == 1
    assert q.devices_by_type["CAST_IN_COLLAR"] == 2
    assert q.devices_by_type["SURFACE_FIRE_COLLAR"] == 1
    assert q.devices_by_diameter["100mm"] == 2
    assert q.devices_by_diameter["65mm"] == 1
    assert q.devices_by_fire_rating["2HR"] == 2
    assert q.devices_by_fire_rating["3HR"] == 1

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
