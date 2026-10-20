"""
test_source_lvl_glulam_timber_shadow.py

Unit tests for SourceLVLGlulamTimberShadowAuthority.
"""

import pytest
from pb_source_lvl_glulam_timber_shadow import (
    SourceLVLGlulamTimberShadowAuthority,
    EngineeredTimberType,
    TimberFramingRole,
    TimberBeamSpec,
    TimberBeamExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_timber_beam_callout_parsing():
    parsed1 = SourceLVLGlulamTimberShadowAuthority.parse_callout(
        "2/300x45 LVL e14 OPENING LINTEL"
    )
    assert parsed1["timber_type"] == EngineeredTimberType.LAMINATED_VENEER_LUMBER_LVL
    assert parsed1["framing_role"] == TimberFramingRole.OPENING_LINTEL
    assert parsed1["plies_count"] == 2
    assert parsed1["depth_mm"] == 300.0
    assert parsed1["ply_width_mm"] == 45.0
    assert parsed1["stress_grade"] == "E14"

    parsed2 = SourceLVLGlulamTimberShadowAuthority.parse_callout(
        "GL17 GLULAM 360x65 ROOF RIDGE BEAM"
    )
    assert parsed2["timber_type"] == EngineeredTimberType.GLUE_LAMINATED_TIMBER_GLULAM
    assert parsed2["framing_role"] == TimberFramingRole.ROOF_RIDGE_BEAM
    assert parsed2["plies_count"] == 1
    assert parsed2["depth_mm"] == 360.0
    assert parsed2["ply_width_mm"] == 65.0
    assert parsed2["stress_grade"] == "GL17"

    parsed3 = SourceLVLGlulamTimberShadowAuthority.parse_callout(
        "hySPAN 240x45 LVL BEARER"
    )
    assert parsed3["timber_type"] == EngineeredTimberType.LAMINATED_VENEER_LUMBER_LVL
    assert parsed3["framing_role"] == TimberFramingRole.FLOOR_BEARER_GIRDER
    assert parsed3["depth_mm"] == 240.0
    assert parsed3["ply_width_mm"] == 45.0


def test_timber_beam_snapping():
    pt = (123.4, 456.7)
    snapped = SourceLVLGlulamTimberShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    assert snapped == (122.5, 457.5)


def test_timber_beam_evaluation_quantities():
    raw_data = [
        {
            "beam_id": "L-01",
            "centerline_points": [(0.0, 0.0), (4000.0, 0.0)],
            "callout": "2/300x45 LVL e14 OPENING LINTEL",
            "level_id": "L01",
        },
        {
            "beam_id": "R-01",
            "centerline_points": [(0.0, 5000.0), (6000.0, 5000.0)],
            "callout": "GL17 GLULAM 360x65 ROOF RIDGE BEAM",
            "level_id": "ROOF",
        },
    ]

    res = SourceLVLGlulamTimberShadowAuthority.evaluate_timber_framing(raw_data, scale_ratio=0.001)

    assert len(res.beams) == 2
    q = res.quantities
    assert q.total_beams_count == 2
    # L-01: 4.0m gross, 2 plies -> 8.0m single-ply equiv. Vol = 2 * (0.045 * 0.3) * 4.0 = 0.108 m3
    # R-01: 6.0m gross, 1 ply -> 6.0m single-ply equiv. Vol = 1 * (0.065 * 0.36) * 6.0 = 0.1404 m3
    assert pytest.approx(q.total_gross_linear_meters, 0.001) == 10.0
    assert pytest.approx(q.total_equivalent_single_ply_meters, 0.001) == 14.0
    assert pytest.approx(q.lintels_linear_meters, 0.001) == 4.0
    assert pytest.approx(q.ridge_beams_linear_meters, 0.001) == 6.0

    expected_vol = 0.108 + 0.1404
    assert pytest.approx(q.total_timber_volume_m3, 0.0001) == expected_vol

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False
