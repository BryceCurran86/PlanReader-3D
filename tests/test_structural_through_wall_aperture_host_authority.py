"""Tests for Milestone 3: Source-authenticated structural through-wall aperture host authority."""

import math
from dataclasses import fields

import pytest

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_structural_through_wall_aperture_host_authority import (
    ApertureHostCandidateInput,
    ContinuousThroughWallCandidate,
    InterAperturePierRecord,
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
    assert all(r.status is EvidenceResolutionStatus.CANDIDATE for r in records)
    assert all(r.first_remaining_gate == "original_source_host_unverified" for r in records)

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
    assert all(r.status is EvidenceResolutionStatus.CANDIDATE for r in records)
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
    # A rigid coordinate transform preserves the geometric verdict, but it
    # changes the physical host's source-page coordinates. The identity is
    # source-and-host-geometry-bound: aliasing these two source observations
    # would hide a moved/rotated wall in a later receipt.
    assert r1[0].status is r2[0].status
    assert r1[0].first_remaining_gate == r2[0].first_remaining_gate
    assert r1[0].hosting_record_id != r2[0].hosting_record_id
    for wall, opening, original in ((w1, op1, r1[0]), (w2, op2, r2[0])):
        replay, _ = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,)
        )
        assert replay[0].hosting_record_id == original.hosting_record_id
        assert replay[0].shadow_only and not replay[0].takeoff_eligible
        assert not replay[0].commercial_projection_allowed


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
    assert r_single[0].status is EvidenceResolutionStatus.CANDIDATE
    assert p_single == ()  # No adjacent piers with single opening

def _construct_pier_with_reissued_identity(
    original: InterAperturePierRecord, **changes,
) -> InterAperturePierRecord:
    """Adversarial direct constructor: recompute ID to isolate geometry guard."""
    values = {field.name: getattr(original, field.name) for field in fields(original)}
    values.update(changes)
    payload = {
        "document_id": values["document_id"],
        "revision_id": values["revision_id"],
        "source_sha256": values["source_sha256"],
        "host_wall_id": values["host_wall_id"],
        "host_start_pt": tuple(float(v).hex() for v in values["host_start_pt"]),
        "host_end_pt": tuple(float(v).hex() for v in values["host_end_pt"]),
        "host_thickness_pt": float(values["host_thickness_pt"]).hex(),
        "snap_tolerance_pt": float(values["snap_tolerance_pt"]).hex(),
        "left_opening_id": values["left_opening_id"],
        "right_opening_id": values["right_opening_id"],
        "left_jamb_endpoints": tuple(sorted(
            tuple(float(v).hex() for v in point)
            for point in values["left_jamb_endpoints"]
        )),
        "right_jamb_endpoints": tuple(sorted(
            tuple(float(v).hex() for v in point)
            for point in values["right_jamb_endpoints"]
        )),
        "left_jamb_observations": values["left_jamb_observations"],
        "right_jamb_observations": values["right_jamb_observations"],
        "start_station": float(values["pier_start_station"]).hex(),
        "end_station": float(values["pier_end_station"]).hex(),
        "width_pt": float(values["pier_width_pt"]).hex(),
    }
    values["pier_id"] = stable_contract_id(
        "inter_aperture_pier", payload, digest_chars=32,
    )
    return InterAperturePierRecord(**values)


def test_frozen_pier_reproves_hosted_jamb_geometry(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    """A forged re-keyed pier cannot use off-wall, oblique or overlong jambs."""
    wall = ContinuousThroughWallCandidate(
        "pier_host", (0.0, 0.0), (200.0, 0.0), 10.0,
    )
    openings = (
        ApertureHostCandidateInput("left", (20.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("right", (45.0, 0.0), (65.0, 0.0)),
    )
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(piers) == 1
    pier = piers[0]
    assert pier.status is EvidenceResolutionStatus.CANDIDATE
    assert pier.is_structural_masonry_pier is None
    assert pier.pier_width_pt == 5.0
    assert all(not rec.takeoff_eligible and not rec.commercial_projection_allowed
               for rec in records)
    original = pier

    # Each forged pair preserves the original projected pier start station
    # (40pt), and each gets its own freshly computed stable ID. Before the
    # guard, all three could pass the frozen record constructor.
    for forged_jambs in (
        ((20.0, 100.0), (40.0, 100.0)),  # displaced from host wall band
        ((20.0, 0.0), (40.0, 3.0)),      # oblique, but inside wall band
        ((-100.0, 0.0), (40.0, 0.0)),    # outside wall extent
    ):
        with pytest.raises(ValueError, match="pier jamb geometry"):
            _construct_pier_with_reissued_identity(
                pier, left_jamb_endpoints=forged_jambs,
            )
    assert pier == original
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=tuple(reversed(openings)),
    )[1] == piers
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    ) == (records, piers)

    # A rigid rotation preserves the valid physical candidate decision.
    rotated_wall = ContinuousThroughWallCandidate(
        "pier_host_rotated", (100.0, 0.0), (100.0, 200.0), 10.0,
    )
    rotated_openings = (
        ApertureHostCandidateInput("left", (100.0, 20.0), (100.0, 40.0)),
        ApertureHostCandidateInput("right", (100.0, 45.0), (100.0, 65.0)),
    )
    rotated_records, rotated_piers = authority.bind_openings_to_through_wall(
        through_wall=rotated_wall, openings=rotated_openings,
    )
    assert len(rotated_piers) == 1
    assert rotated_piers[0].pier_width_pt == pier.pier_width_pt
    assert rotated_piers[0].status is EvidenceResolutionStatus.CANDIDATE
    assert rotated_piers[0].is_structural_masonry_pier is None
    assert all(rec.shadow_only and not rec.takeoff_eligible
               for rec in rotated_records)

def test_frozen_pier_binds_exact_per_run_snap_receipt(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    """A smaller caller snap cannot silently become the 2.5pt maximum."""
    from dataclasses import replace

    wall = ContinuousThroughWallCandidate(
        "pier_snap_host", (0.0, 0.0), (200.0, 0.0), 10.0,
    )
    openings = (
        ApertureHostCandidateInput("left", (20.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("right", (45.0, 0.0), (65.0, 0.0)),
    )
    strict_records, strict_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings, snap_tolerance_pt=0.1,
    )
    loose_records, loose_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings, snap_tolerance_pt=2.5,
    )
    assert len(strict_piers) == len(loose_piers) == 1
    strict, loose = strict_piers[0], loose_piers[0]
    assert strict.snap_tolerance_pt == 0.1
    assert loose.snap_tolerance_pt == 2.5
    assert strict.pier_id != loose.pier_id
    assert strict.status is EvidenceResolutionStatus.CANDIDATE
    assert strict.is_structural_masonry_pier is None
    assert all(not rec.takeoff_eligible and not rec.commercial_projection_allowed
               for rec in strict_records + loose_records)
    assert replace(strict) == strict
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=tuple(reversed(openings)),
        snap_tolerance_pt=0.1,
    )[1] == strict_piers

    # 5.5pt from the wall axis exceeds half-thickness (5pt) + 0.1pt,
    # but not half-thickness + the global 2.5pt cap. Re-keying the
    # complete record cannot bypass the caller's narrower receipt.
    with pytest.raises(ValueError, match="pier jamb geometry"):
        _construct_pier_with_reissued_identity(
            strict, left_jamb_endpoints=((20.0, 5.5), (40.0, 5.5)),
        )
    with pytest.raises(ValueError, match="pier stable identity"):
        replace(strict, snap_tolerance_pt=2.5)
    for invalid_snap in (-0.1, 2.500001, float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="pier host geometry"):
            _construct_pier_with_reissued_identity(
                strict, snap_tolerance_pt=invalid_snap,
            )
    assert strict_piers == authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings, snap_tolerance_pt=0.1,
    )[1]


def test_frozen_pier_rejects_cross_opening_shared_jamb_observations(
    authority: StructuralThroughWallApertureHostAuthority,
) -> None:
    """Re-keyed frozen piers cannot recycle one source jamb for two openings."""
    wall = ContinuousThroughWallCandidate(
        "pier_shared_observation_host", (0.0, 0.0), (200.0, 0.0), 10.0,
    )
    left = ApertureHostCandidateInput(
        "left", (20.0, 0.0), (40.0, 0.0),
        terminal_jamb_observation_ids=("left_obs",),
    )
    right = ApertureHostCandidateInput(
        "right", (45.0, 0.0), (65.0, 0.0),
        terminal_jamb_observation_ids=("right_obs",),
    )
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(left, right),
    )
    assert len(piers) == 1
    pier = piers[0]
    assert pier.status is EvidenceResolutionStatus.CANDIDATE
    assert pier.is_structural_masonry_pier is None
    assert all(rec.shadow_only and not rec.takeoff_eligible
               and not rec.commercial_projection_allowed for rec in records)

    # Both tuples are individually sorted, unique, native and identity-bound.
    # Their cross-opening overlap is nevertheless not independent evidence.
    for left_ids, right_ids in (
        (("shared_obs",), ("shared_obs",)),
        (("left_obs", "shared_obs"), ("right_obs", "shared_obs")),
        (("left_obs",), ("left_obs", "right_obs")),
    ):
        with pytest.raises(ValueError, match="pier jamb observations"):
            _construct_pier_with_reissued_identity(
                pier, left_jamb_observations=left_ids,
                right_jamb_observations=right_ids,
            )

    # The complete producer universe already vetoes the same conflict,
    # including both traversal orders; no invented pier or count survives.
    conflicting_left = ApertureHostCandidateInput(
        "left", (20.0, 0.0), (40.0, 0.0),
        terminal_jamb_observation_ids=("left_obs", "shared_obs"),
    )
    conflicting_right = ApertureHostCandidateInput(
        "right", (45.0, 0.0), (65.0, 0.0),
        terminal_jamb_observation_ids=("right_obs", "shared_obs"),
    )
    for universe in (
        (conflicting_left, conflicting_right),
        (conflicting_right, conflicting_left),
    ):
        rejected, rejected_piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=universe,
        )
        assert rejected_piers == ()
        assert len(rejected) == 2
        assert all(rec.status is EvidenceResolutionStatus.ABSTAINED
                   and rec.first_remaining_gate
                   == "aperture_terminal_jamb_observation_conflict"
                   for rec in rejected)
        assert all(rec.shadow_only and not rec.takeoff_eligible
                   and not rec.commercial_projection_allowed for rec in rejected)

    # Independent observation receipts remain valid source-neutral geometry.
    distinct = _construct_pier_with_reissued_identity(
        pier, left_jamb_observations=("left_obs", "left_obs_2"),
        right_jamb_observations=("right_obs", "right_obs_2"),
    )
    assert distinct.status is EvidenceResolutionStatus.CANDIDATE
    assert distinct.is_structural_masonry_pier is None
    assert distinct.pier_id != pier.pier_id
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(right, left),
    )[1] == piers
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(left, right),
    ) == (records, piers)
