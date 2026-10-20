"""
test_source_cfs_purlin_girt_shadow.py

Unit tests for SourceCFSPurlinGirtShadowAuthority.
"""

import pytest
from pb_source_cfs_purlin_girt_shadow import (
    SourceCFSPurlinGirtShadowAuthority,
    CFSRole,
    CFSSectionProfile,
    CFSMemberSpec,
    CFSExtractionResult,
    SNAP_TOLERANCE_PT,
)


def test_cfs_callout_parsing():
    parsed1 = SourceCFSPurlinGirtShadowAuthority.parse_callout(
        "Z20019 ROOF PURLIN CONTINUOUS W/ 900mm LAPS 1 ROW BRIDGING"
    )
    assert parsed1["role"] == CFSRole.ROOF_PURLIN
    assert parsed1["section_profile"] == CFSSectionProfile.Z_SECTION
    assert parsed1["section_designation"] == "Z20019"
    assert parsed1["lap_count"] == 1
    assert parsed1["lap_length_mm"] == 900.0
    assert parsed1["bridging_rows_count"] == 1
    assert parsed1["linear_mass_kg_m"] == 4.54

    parsed2 = SourceCFSPurlinGirtShadowAuthority.parse_callout(
        "C15015 WALL GIRT SPAN=6.0m"
    )
    assert parsed2["role"] == CFSRole.WALL_GIRT
    assert parsed2["section_profile"] == CFSSectionProfile.C_SECTION
    assert parsed2["section_designation"] == "C15015"
    assert parsed2["linear_mass_kg_m"] == 2.89

    parsed3 = SourceCFSPurlinGirtShadowAuthority.parse_callout(
        "EAVES STRUT C20024 2 ROWS BRIDGING"
    )
    assert parsed3["role"] == CFSRole.EAVES_STRUT
    assert parsed3["section_profile"] == CFSSectionProfile.C_SECTION
    assert parsed3["section_designation"] == "C20024"
    assert parsed3["bridging_rows_count"] == 2
    assert parsed3["linear_mass_kg_m"] == 5.70

    omitted = SourceCFSPurlinGirtShadowAuthority.parse_callout("PURLIN")
    assert omitted["section_designation"] == ""
    assert omitted["linear_mass_kg_m"] == 0.0

    omitted_role = SourceCFSPurlinGirtShadowAuthority.parse_callout("CFS MEMBER")
    assert omitted_role["role"] == CFSRole.UNKNOWN

    omitted_lap = SourceCFSPurlinGirtShadowAuthority.parse_callout(
        "Z20019 ROOF PURLIN CONTINUOUS"
    )
    assert omitted_lap["lap_length_mm"] == 0.0


def test_cfs_snapping():
    pt = (301.2, 598.9)
    snapped = SourceCFSPurlinGirtShadowAuthority.snap_point(pt, SNAP_TOLERANCE_PT)
    # 301.2 / 2.5 = 120.48 -> 120 * 2.5 = 300.0
    # 598.9 / 2.5 = 239.56 -> 240 * 2.5 = 600.0
    assert snapped == (300.0, 600.0)


def test_cfs_evaluation_quantities():
    raw_data = [
        {
            "member_id": "P-01",
            "centerline_points": [(0.0, 0.0), (12000.0, 0.0)],
            "callout": "Z20019 ROOF PURLIN CONTINUOUS W/ 900mm LAPS 1 ROW BRIDGING",
            "level_id": "ROOF",
        },
        {
            "member_id": "G-01",
            "centerline_points": [(0.0, 0.0), (6000.0, 0.0)],
            "callout": "C15015 WALL GIRT",
            "level_id": "WALL",
        },
    ]

    res = SourceCFSPurlinGirtShadowAuthority.evaluate_members(raw_data, scale_ratio=0.001)

    assert len(res.members) == 2
    q = res.quantities
    assert q.total_members_count == 2
    # P-01: net 12.0m, lap 1 * 0.9m = 12.9m gross. mass = 12.9 * 4.54 = 58.566 kg
    # G-01: net 6.0m, lap 0m = 6.0m gross. mass = 6.0 * 2.89 = 17.34 kg
    assert pytest.approx(q.total_net_linear_meters, 0.001) == 18.0
    assert pytest.approx(q.total_gross_linear_meters, 0.001) == 18.9
    assert pytest.approx(q.purlin_net_linear_meters, 0.001) == 12.0
    assert pytest.approx(q.girt_net_linear_meters, 0.001) == 6.0
    assert q.total_bridging_rows_count == 1

    expected_mass = (12.9 * 4.54) + (6.0 * 2.89)
    assert pytest.approx(q.total_mass_kg, 0.01) == expected_mass

    assert res.status == "CANDIDATE"
    assert res.commercial_projection_allowed is False
    assert res.takeoff_eligible is False

    omitted_spec = CFSMemberSpec(member_id="P-OMIT")
    assert omitted_spec.section_designation == ""
    assert omitted_spec.linear_mass_kg_m == 0.0
    assert omitted_spec.role == CFSRole.UNKNOWN
    omitted_res = SourceCFSPurlinGirtShadowAuthority.evaluate_members(
        [{"member_id": "P-OMIT", "centerline_points": [(0.0, 0.0), (12000.0, 0.0)], "callout": "PURLIN"}],
        scale_ratio=0.001,
    )
    assert omitted_res.members[0].section_designation == ""
    assert omitted_res.quantities.total_mass_kg == 0.0
