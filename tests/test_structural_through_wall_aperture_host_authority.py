"""Tests for Milestone 3: Source-authenticated structural through-wall aperture host authority."""

import math

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_through_wall_aperture_host_authority import (
    ApertureHostCandidateInput,
    ContinuousThroughWallCandidate,
    StructuralThroughWallApertureHostAuthority,
    StructuralThroughWallApertureHostProducer,
)


@pytest.fixture
def producer() -> StructuralThroughWallApertureHostProducer:
    return StructuralThroughWallApertureHostProducer(
        document_id="doc_maryborough_p7",
        revision_id="rev_maryborough_p7",
        source_sha256="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007",
    )


@pytest.fixture
def authority(
    producer: StructuralThroughWallApertureHostProducer,
) -> StructuralThroughWallApertureHostAuthority:
    return StructuralThroughWallApertureHostAuthority(producer)


def test_sealed_permission_boundaries(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    wall = ContinuousThroughWallCandidate(
        wall_id="wall_test_1",
        start_pt=(100.0, 100.0),
        end_pt=(500.0, 100.0),
        thickness_pt=15.0,
    )
    op = ApertureHostCandidateInput(
        physical_opening_id="opening_1",
        start_pt=(150.0, 100.0),
        end_pt=(250.0, 100.0),
    )
    records, _piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(op,)
    )
    assert len(records) == 1
    assert records[0].commercial_projection_allowed is False
    assert records[0].takeoff_eligible is False
    assert records[0].shadow_only is True
    assert records[0].hosting_record_id.startswith("through_wall_hosted_opening_")

    # Invalid constructors must raise ValueError
    with pytest.raises(ValueError, match="wall_id required"):
        ContinuousThroughWallCandidate(
            wall_id="", start_pt=(0, 0), end_pt=(10, 0), thickness_pt=10.0
        )

    with pytest.raises(ValueError, match="thickness_pt must be positive"):
        ContinuousThroughWallCandidate(
            wall_id="w1", start_pt=(0, 0), end_pt=(10, 0), thickness_pt=0.0
        )

    with pytest.raises(ValueError, match="start and end points must be distinct"):
        ContinuousThroughWallCandidate(
            wall_id="w1", start_pt=(10, 10), end_pt=(10, 10), thickness_pt=10.0
        )

    with pytest.raises(ValueError, match="physical_opening_id required"):
        ApertureHostCandidateInput(
            physical_opening_id="", start_pt=(0, 0), end_pt=(10, 0)
        )


def test_synthetic_positive_multi_opening_through_wall_facade(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    # 1000 pt long horizontal wall (say 25m) with 3 openings
    wall = ContinuousThroughWallCandidate(
        wall_id="wall_facade_continuous",
        start_pt=(0.0, 200.0),
        end_pt=(1000.0, 200.0),
        thickness_pt=20.0,
    )
    op1 = ApertureHostCandidateInput(
        "op_win_1", start_pt=(100.0, 200.0), end_pt=(250.0, 200.0)
    )
    op2 = ApertureHostCandidateInput(
        "op_win_2", start_pt=(260.0, 200.0), end_pt=(400.0, 200.0)
    )
    op3 = ApertureHostCandidateInput(
        "op_win_3", start_pt=(420.0, 200.0), end_pt=(600.0, 200.0)
    )

    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(op1, op2, op3)
    )
    assert len(records) == 3
    assert all(r.status is EvidenceResolutionStatus.CORROBORATED for r in records)
    assert all(r.first_remaining_gate == "none" for r in records)

    # Check two inter-aperture piers discovered
    assert len(piers) == 2
    # Pier 1 between op1 (end=250) and op2 (start=260): width = 10 pt
    assert math.isclose(piers[0].pier_width_pt, 10.0, abs_tol=1e-3)
    assert piers[0].left_opening_id == "op_win_1"
    assert piers[0].right_opening_id == "op_win_2"
    # Pier 2 between op2 (end=400) and op3 (start=420): width = 20 pt
    assert math.isclose(piers[1].pier_width_pt, 20.0, abs_tol=1e-3)


def test_maryborough_p7_east_wall_regression(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    # Maryborough Page 7 East Wall: vertical wall running y=558.08 to 1959.92 along x=1120.00
    wall = ContinuousThroughWallCandidate(
        wall_id="wall_mary_east_facade",
        start_pt=(1120.00, 558.08),
        end_pt=(1120.00, 1959.92),
        thickness_pt=16.32,
    )
    # W05: y=646.40..1076.48 (span = 430.08 pt)
    w05 = ApertureHostCandidateInput(
        "aperture_W05", start_pt=(1120.00, 646.40), end_pt=(1120.00, 1076.48)
    )
    # W03: y=1343.12..1550.00 (span = 206.88 pt)
    w03 = ApertureHostCandidateInput(
        "aperture_W03", start_pt=(1120.00, 1343.12), end_pt=(1120.00, 1550.00)
    )
    # W02: y=1557.44..1789.76 (span = 232.32 pt)
    w02 = ApertureHostCandidateInput(
        "aperture_W02", start_pt=(1120.00, 1557.44), end_pt=(1120.00, 1789.76)
    )

    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall,
        openings=(w05, w03, w02),
    )
    assert len(records) == 3
    assert all(r.status is EvidenceResolutionStatus.CORROBORATED for r in records)
    assert all(r.host_wall_id == "wall_mary_east_facade" for r in records)

    # Check stations
    # Wall start is y=558.08
    rec_by_id = {r.physical_opening_id: r for r in records}
    # W05: u0 = 646.40 - 558.08 = 88.32 pt, u1 = 1076.48 - 558.08 = 518.40 pt
    assert math.isclose(rec_by_id["aperture_W05"].u0_pt, 88.32, abs_tol=0.01)
    assert math.isclose(rec_by_id["aperture_W05"].u1_pt, 518.40, abs_tol=0.01)

    # Masonry dividing pier between W03 (end=1550.00) and W02 (start=1557.44)
    # Pier width = 1557.44 - 1550.00 = 7.44 pt
    assert len(piers) == 1
    pier = piers[0]
    assert math.isclose(pier.pier_width_pt, 7.44, abs_tol=0.01)
    assert pier.left_opening_id == "aperture_W03"
    assert pier.right_opening_id == "aperture_W02"


def test_negative_angular_misalignment(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    wall = ContinuousThroughWallCandidate(
        wall_id="wall_horizontal",
        start_pt=(0.0, 100.0),
        end_pt=(500.0, 100.0),
        thickness_pt=20.0,
    )
    # Opening tilted by 10 degrees
    angle_rad = math.radians(10.0)
    dx = 100.0 * math.cos(angle_rad)
    dy = 100.0 * math.sin(angle_rad)
    tilted_op = ApertureHostCandidateInput(
        "op_tilted", start_pt=(100.0, 100.0), end_pt=(100.0 + dx, 100.0 + dy)
    )

    records, _ = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(tilted_op,)
    )
    assert len(records) == 1
    assert records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert records[0].first_remaining_gate == "aperture_wall_axis_misaligned"


def test_negative_transverse_displacement_outside_band(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    wall = ContinuousThroughWallCandidate(
        wall_id="wall_horizontal",
        start_pt=(0.0, 100.0),
        end_pt=(500.0, 100.0),
        thickness_pt=20.0,  # half thickness = 10.0 pt
    )
    # Opening displaced to y=150 (50 pt away from wall centerline)
    displaced_op = ApertureHostCandidateInput(
        "op_displaced", start_pt=(100.0, 150.0), end_pt=(200.0, 150.0)
    )

    records, _ = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(displaced_op,)
    )
    assert len(records) == 1
    assert records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert records[0].first_remaining_gate == "aperture_outside_host_wall_band"


def test_negative_transverse_wall_obstruction(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    wall = ContinuousThroughWallCandidate(
        wall_id="wall_horizontal",
        start_pt=(0.0, 100.0),
        end_pt=(500.0, 100.0),
        thickness_pt=20.0,
    )
    op = ApertureHostCandidateInput(
        "op_obstructed", start_pt=(100.0, 100.0), end_pt=(200.0, 100.0)
    )
    # Transverse wall crossing x=150 from y=50 to y=150
    transverse_wall = ((150.0, 50.0), (150.0, 150.0))

    records, _ = authority.bind_openings_to_through_wall(
        through_wall=wall,
        openings=(op,),
        transverse_wall_segments=(transverse_wall,),
    )
    assert len(records) == 1
    assert records[0].status is EvidenceResolutionStatus.ABSTAINED
    assert records[0].first_remaining_gate == "host_through_wall_obstructed"


def test_metamorphic_rotation_and_translation_invariance(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    # Original horizontal wall
    w1 = ContinuousThroughWallCandidate(
        "w_meta", start_pt=(100.0, 100.0), end_pt=(500.0, 100.0), thickness_pt=20.0
    )
    op1 = ApertureHostCandidateInput(
        "op_meta", start_pt=(200.0, 100.0), end_pt=(350.0, 100.0)
    )

    # Rotated 90 degrees and translated to (500, 200)
    # (x, y) -> (-y + 600, x + 100)
    w2 = ContinuousThroughWallCandidate(
        "w_meta", start_pt=(500.0, 200.0), end_pt=(500.0, 600.0), thickness_pt=20.0
    )
    op2 = ApertureHostCandidateInput(
        "op_meta", start_pt=(500.0, 300.0), end_pt=(500.0, 450.0)
    )

    r1, _ = authority.bind_openings_to_through_wall(through_wall=w1, openings=(op1,))
    r2, _ = authority.bind_openings_to_through_wall(through_wall=w2, openings=(op2,))

    assert math.isclose(r1[0].u0_pt, r2[0].u0_pt, abs_tol=1e-3)
    assert math.isclose(r1[0].u1_pt, r2[0].u1_pt, abs_tol=1e-3)
    assert math.isclose(
        r1[0].whole_wall_length_pt, r2[0].whole_wall_length_pt, abs_tol=1e-3
    )
    assert r1[0].hosting_record_id == r2[0].hosting_record_id


def test_input_ordering_invariance(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    wall = ContinuousThroughWallCandidate(
        "w_order", start_pt=(0.0, 100.0), end_pt=(600.0, 100.0), thickness_pt=20.0
    )
    op_a = ApertureHostCandidateInput(
        "op_a", start_pt=(100.0, 100.0), end_pt=(200.0, 100.0)
    )
    op_b = ApertureHostCandidateInput(
        "op_b", start_pt=(210.0, 100.0), end_pt=(350.0, 100.0)
    )

    r1, p1 = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(op_a, op_b)
    )
    r2, p2 = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(op_b, op_a)
    )

    rec1_by_id = {r.physical_opening_id: r for r in r1}
    rec2_by_id = {r.physical_opening_id: r for r in r2}
    assert rec1_by_id == rec2_by_id
    assert p1 == p2


def test_empty_and_single_opening_handling(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    wall = ContinuousThroughWallCandidate(
        "w_single", start_pt=(0.0, 100.0), end_pt=(400.0, 100.0), thickness_pt=20.0
    )
    # Empty
    r_empty, p_empty = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=()
    )
    assert r_empty == ()
    assert p_empty == ()

    # Single opening
    op = ApertureHostCandidateInput(
        "op_solo", start_pt=(50.0, 100.0), end_pt=(150.0, 100.0)
    )
    r_single, p_single = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(op,)
    )
    assert len(r_single) == 1
    assert r_single[0].status is EvidenceResolutionStatus.CORROBORATED
    assert p_single == ()  # No adjacent piers with single opening
