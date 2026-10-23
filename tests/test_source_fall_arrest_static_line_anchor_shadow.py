"""
test_source_fall_arrest_static_line_anchor_shadow.py

Unit tests for SourceFallArrestStaticLineAnchorShadowAuthority.
"""

import pytest
from pb_source_fall_arrest_static_line_anchor_shadow import (
    SourceFallArrestStaticLineAnchorShadowAuthority,
    FallProtectionType,
    AnchorMountingSubstrate,
    FallProtectionItemSpec,
    FallProtectionExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_fall_protection_callout_parsing():
    parsed1 = SourceFallArrestStaticLineAnchorShadowAuthority.parse_callout(
        "8mm SS HORIZONTAL STATIC LINE ON PURLIN MOUNT BRACKETS AT 8.0m CTS W/ 2x ENERGY ABSORBERS"
    )
    assert parsed1["protection_type"] == FallProtectionType.HORIZONTAL_STATIC_LIFELINE
    assert parsed1["mounting_substrate"] == AnchorMountingSubstrate.PURLIN_METAL_DECK_MOUNT
    assert parsed1["cable_diameter_mm"] == 8.0
    assert parsed1["load_rating_kn"] == 15.0
    assert parsed1["intermediate_spacing_m"] == 8.0
    assert parsed1["energy_absorbers_count"] == 2

    parsed2 = SourceFallArrestStaticLineAnchorShadowAuthority.parse_callout(
        "15kN SINGLE POINT FALL ARREST ANCHOR CONCRETE MOUNT"
    )
    assert parsed2["protection_type"] == FallProtectionType.SINGLE_POINT_FALL_ARREST_ANCHOR
    assert parsed2["mounting_substrate"] == AnchorMountingSubstrate.CONCRETE_STRUCTURE_MOUNT
    assert parsed2["load_rating_kn"] == 15.0

    parsed3 = SourceFallArrestStaticLineAnchorShadowAuthority.parse_callout(
        "22kN ROPE ACCESS ABSEIL ANCHOR STEEL BEAM CLAMP"
    )
    assert parsed3["protection_type"] == FallProtectionType.ROPE_ACCESS_ABSEIL_ANCHOR
    assert parsed3["mounting_substrate"] == AnchorMountingSubstrate.STEEL_BEAM_CLAMP_MOUNT
    assert parsed3["load_rating_kn"] == 22.0


def test_fall_protection_point_snapping():
    pt = (800.3, 1500.8)
    snapped = SourceFallArrestStaticLineAnchorShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (800.0, 1500.0)


def test_fall_protection_polyline_length():
    points = [(0.0, 0.0), (32000.0, 0.0)]
    length = SourceFallArrestStaticLineAnchorShadowAuthority.calculate_polyline_length(points, scale_ratio=0.001)
    assert pytest.approx(length, rel=1e-3) == 32.0


def test_fall_protection_evaluation_quantities():
    raw_data = [
        {
            "item_id": "SL-01",
            "centerline_points": [(0.0, 0.0), (32000.0, 0.0)],
            "callout": "8mm SS HORIZONTAL STATIC LINE ON PURLIN MOUNT BRACKETS AT 8.0m CTS W/ 2x ENERGY ABSORBERS",
            "level_id": "ROOF",
        },
        {
            "item_id": "ANC-01",
            "location_point": (5000.0, 5000.0),
            "callout": "15kN SINGLE POINT FALL ARREST ANCHOR CONCRETE MOUNT",
            "level_id": "ROOF",
        },
        {
            "item_id": "ANC-02",
            "location_point": (10000.0, 5000.0),
            "callout": "22kN ROPE ACCESS ABSEIL ANCHOR STEEL BEAM CLAMP",
            "level_id": "ROOF",
        },
    ]

    result = SourceFallArrestStaticLineAnchorShadowAuthority.evaluate_systems(raw_data)
    assert len(result.items) == 3
    assert result.status == "CANDIDATE"
    assert result.commercial_projection_allowed is False
    assert result.takeoff_eligible is False

    q = result.quantities
    assert q.total_systems_count == 3
    # Cable length: 32m
    assert pytest.approx(q.total_cable_length_meters, rel=1e-3) == 32.0

    # Intermediate brackets: ceil(32 / 8) - 1 = 4 - 1 = 3 brackets
    assert q.total_intermediate_brackets_count == 3

    # Anchors: 2 end anchors (SL-01) + 1 single anchor (ANC-01) + 1 rope anchor (ANC-02) = 4 total
    assert q.total_anchor_points_count == 4

    # Energy absorbers: 2 on SL-01
    assert q.total_energy_absorbers_count == 2

    assert q.anchors_by_substrate[AnchorMountingSubstrate.PURLIN_METAL_DECK_MOUNT.value] == 2
    assert q.anchors_by_substrate[AnchorMountingSubstrate.CONCRETE_STRUCTURE_MOUNT.value] == 1
    assert q.anchors_by_substrate[AnchorMountingSubstrate.STEEL_BEAM_CLAMP_MOUNT.value] == 1
