"""GPT MAX: a geometric wall-centre match is not a proven endpoint host.

Source-neutral regression only; producer is shadow-only and cannot authorize FIRM output.
"""
from __future__ import annotations

import math

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_structural_through_wall_aperture_host_authority import (
    ApertureHostCandidateInput,
    ContinuousThroughWallCandidate,
    StructuralThroughWallApertureHostAuthority,
    StructuralThroughWallApertureHostProducer,
)


def _authority():
    return StructuralThroughWallApertureHostAuthority(
        StructuralThroughWallApertureHostProducer(
            document_id="synthetic", revision_id="v1", source_sha256="0" * 64,
        )
    )


def _rotated(point, angle, translation):
    x, y = point
    a, b = translation
    return (
        x * math.cos(angle) - y * math.sin(angle) + a,
        x * math.sin(angle) + y * math.cos(angle) + b,
    )


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (300.0, 200.0)),
    (math.pi, (-400.0, 700.0)),
])
def test_both_outside_jambs_cannot_be_hidden_by_center_average(angle, shift):
    # 1.718 degrees is below the existing ~1.8-degree alignment gate.
    # The centre is on the wall, while BOTH jambs are 15pt from a 10pt
    # half-thickness wall, beyond the fixed 2.5pt snap limit.
    tr = lambda p: _rotated(p, angle, shift)
    wall = ContinuousThroughWallCandidate(
        wall_id="host", start_pt=tr((0.0, 0.0)), end_pt=tr((1000.0, 0.0)),
        thickness_pt=20.0,
    )
    opening = ApertureHostCandidateInput(
        physical_opening_id="oblique",
        start_pt=tr((0.0, -15.0)), end_pt=tr((1000.0, 15.0)),
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,)
    )
    assert len(records) == 1 and not piers
    assert records[0].status is S.ABSTAINED
    assert records[0].first_remaining_gate == "aperture_outside_host_wall_band"
    assert records[0].commercial_projection_allowed is False
    assert records[0].takeoff_eligible is False
    assert records[0].shadow_only is True


def test_genuine_in_band_long_oblique_opening_retains_shadow_positive():
    wall = ContinuousThroughWallCandidate(
        wall_id="host", start_pt=(0.0, 0.0), end_pt=(1000.0, 0.0),
        thickness_pt=20.0,
    )
    opening = ApertureHostCandidateInput(
        physical_opening_id="oblique", start_pt=(0.0, -10.0), end_pt=(1000.0, 10.0),
    )
    authority = _authority()
    first, _ = authority.bind_openings_to_through_wall(through_wall=wall, openings=(opening,))
    second, _ = authority.bind_openings_to_through_wall(through_wall=wall, openings=(opening,))
    assert first == second
    assert first[0].status is S.CANDIDATE
    assert first[0].first_remaining_gate == "original_source_host_unverified"
    assert first[0].commercial_projection_allowed is False


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_nonfinite_thickness_and_coordinates_never_enter_host_evidence(bad):
    with pytest.raises(ValueError):
        ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), bad)
    with pytest.raises(ValueError):
        ContinuousThroughWallCandidate("host", (bad, 0.0), (100.0, 0.0), 20.0)
    with pytest.raises(ValueError):
        ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, bad), 20.0)
    with pytest.raises(ValueError):
        ApertureHostCandidateInput("opening", (bad, 0.0), (100.0, 0.0))
    with pytest.raises(ValueError):
        ApertureHostCandidateInput("opening", (0.0, 0.0), (100.0, bad))


@pytest.mark.parametrize("bad", [-0.1, 2.500001, float("nan"), float("inf"), float("-inf"), True])
def test_untrusted_snap_tolerance_cannot_expand_or_bypass_wall_band(bad):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (1000.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (0.0, 0.0), (100.0, 0.0))
    with pytest.raises(ValueError, match="snap_tolerance_pt"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,), snap_tolerance_pt=bad,
        )
    # Empty input cannot conceal a malformed tolerance either.
    with pytest.raises(ValueError, match="snap_tolerance_pt"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=(), snap_tolerance_pt=bad,
        )


def test_zero_and_fixed_snap_are_accepted_with_explicit_difference():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (10.0, 11.0), (40.0, 11.0))
    strict, _ = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,), snap_tolerance_pt=0.0,
    )
    allowed, _ = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,), snap_tolerance_pt=2.5,
    )
    assert strict[0].status is S.ABSTAINED
    assert allowed[0].status is S.CANDIDATE


@pytest.mark.parametrize("bad_segment", [
    ((float("nan"), -30.0), (50.0, 30.0)),
    ((50.0, -30.0), (50.0, float("inf"))),
    ((50.0, float("-inf")), (50.0, 30.0)),
    ((50.0, -30.0), (50.0, -30.0)),
    ((50.0, -30.0), (50.0 + 1e-6, -30.0)),
    ((50.0, -30.0), ("50", 30.0)),
    ((50.0, -30.0), (True, 30.0)),
    ((50.0, -30.0), (10 ** 400, 30.0)),
    ((50.0, -30.0),),
    "not-a-wall-segment",
])
def test_malformed_transverse_wall_evidence_never_disappears(bad_segment):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (20.0, 0.0), (80.0, 0.0))
    authority = _authority()
    for openings in ((opening,), ()):
        with pytest.raises(ValueError, match="transverse_wall_segments"):
            authority.bind_openings_to_through_wall(
                through_wall=wall, openings=openings,
                transverse_wall_segments=(bad_segment,),
            )
    # The same immutable input still produces the original positive with no obstacle.
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    assert records[0].status is S.CANDIDATE and not piers


def test_valid_transverse_obstruction_still_vetoes_host_and_unrelated_wall_does_not():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (20.0, 0.0), (80.0, 0.0))
    authority = _authority()
    crossed = ((50.0, -30.0), (50.0, 30.0))
    unrelated = ((90.0, -30.0), (90.0, 30.0))
    for segment, expected_status, expected_gate in (
        (crossed, S.ABSTAINED, "host_through_wall_obstructed"),
        (unrelated, S.CANDIDATE, "original_source_host_unverified"),
    ):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
            transverse_wall_segments=(segment,),
        )
        assert len(records) == 1 and not piers
        assert records[0].status is expected_status
        assert records[0].first_remaining_gate == expected_gate
        assert records[0].commercial_projection_allowed is False
        assert records[0].takeoff_eligible is False


def test_unrepresentably_large_numeric_inputs_fail_closed_not_overflow():
    huge = 10 ** 400
    with pytest.raises(ValueError, match="finite"):
        ContinuousThroughWallCandidate("host", (huge, 0), (100, 0), 20.0)
    with pytest.raises(ValueError, match="finite"):
        ContinuousThroughWallCandidate("host", (0, 0), (100, 0), huge)
    with pytest.raises(ValueError, match="finite"):
        ApertureHostCandidateInput("opening", (0, 0), (huge, 0))
    wall = ContinuousThroughWallCandidate("host", (0, 0), (100, 0), 20.0)
    with pytest.raises(ValueError, match="snap_tolerance_pt"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=(), snap_tolerance_pt=huge,
        )


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (300.0, -200.0)),
    (math.pi, (-400.0, 700.0)),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_extended_finite_obstruction_crosses_opening_interior(angle, shift, reverse):
    # Both obstruction endpoint stations are OUTSIDE 20..80, yet the
    # finite segment crosses the host centre at station 50.
    tr = lambda p: _rotated(p, angle, shift)
    wall = ContinuousThroughWallCandidate("host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0)
    opening = ApertureHostCandidateInput("opening", tr((20.0, 0.0)), tr((80.0, 0.0)))
    segment = (tr((10.0, -30.0)), tr((90.0, 30.0)))
    if reverse:
        segment = segment[::-1]
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,), transverse_wall_segments=(segment,),
    )
    assert len(records) == 1 and not piers
    assert records[0].status is S.ABSTAINED
    assert records[0].first_remaining_gate == "host_through_wall_obstructed"
    assert records[0].commercial_projection_allowed is False
    assert records[0].takeoff_eligible is False
    assert records[0].shadow_only is True


@pytest.mark.parametrize("segment,expected_status", [
    (((10.0, 30.0), (90.0, 40.0)), S.CANDIDATE),  # above wall band
    (((85.0, -30.0), (95.0, 30.0)), S.CANDIDATE),  # outside opening
    (((22.5, -30.0), (22.5, 30.0)), S.CANDIDATE),  # touches excluded edge only
    (((22.50001, -30.0), (22.50001, 30.0)), S.ABSTAINED),
    (((10.0, 0.0), (90.0, 0.0)), S.ABSTAINED),  # collinear obstruction
])
def test_finite_obstruction_interior_vs_nonintersection(segment, expected_status):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (20.0, 0.0), (80.0, 0.0))
    records, _ = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,), transverse_wall_segments=(segment,),
    )
    assert records[0].status is expected_status
    assert records[0].first_remaining_gate == (
        "host_through_wall_obstructed" if expected_status is S.ABSTAINED else "original_source_host_unverified"
    )
    assert records[0].commercial_projection_allowed is False


def test_extended_obstruction_split_and_order_invariant():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (20.0, 0.0), (80.0, 0.0))
    whole = ((10.0, -30.0), (90.0, 30.0))
    split = (((10.0, -30.0), (50.0, 0.0)), ((50.0, 0.0), (90.0, 30.0)))
    unrelated = ((85.0, -30.0), (95.0, 30.0))
    authority = _authority()
    baseline, _ = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,), transverse_wall_segments=(whole,),
    )
    for segments in (split, split[::-1], (unrelated, whole), (whole, unrelated)):
        actual, _ = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,), transverse_wall_segments=segments,
        )
        assert actual == baseline
    assert baseline[0].status is S.ABSTAINED


@pytest.mark.parametrize("spans", [
    ((20.0, 60.0), (40.0, 80.0)),  # partial overlap
    ((20.0, 60.0), (20.0, 60.0)),  # identical span, different identities
    ((20.0, 80.0), (30.0, 40.0)),  # nested aperture
    ((20.0, 80.0), (70.0, 90.0)),  # overlapping end
])
@pytest.mark.parametrize("reverse", [False, True])
def test_overlapping_apertures_all_abstain_without_pier(spans, reverse):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = tuple(
        ApertureHostCandidateInput(name, (lo, 0.0), (hi, 0.0))
        for name, (lo, hi) in zip(("A", "B"), spans)
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=openings[::-1] if reverse else openings,
    )
    assert len(records) == 2 and piers == ()
    assert {r.physical_opening_id for r in records} == {"A", "B"}
    for record in records:
        assert record.status is S.ABSTAINED
        assert record.first_remaining_gate == "aperture_physical_interval_conflict"
        assert record.adjacent_pier_ids == ()
        assert record.shadow_only is True
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False


def test_overlap_chain_and_nonadjacent_nested_candidate_all_abstain():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (80.0, 0.0)),
        ApertureHostCandidateInput("B", (30.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("C", (70.0, 0.0), (90.0, 0.0)),
    )
    authority = _authority()
    baseline, baseline_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(baseline) == 3 and baseline_piers == ()
    assert all(r.status is S.ABSTAINED for r in baseline)
    for ordering in (openings[::-1], (openings[1], openings[2], openings[0])):
        actual, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordering,
        )
        assert piers == ()
        assert {r.physical_opening_id: r for r in actual} == {
            r.physical_opening_id: r for r in baseline
        }


@pytest.mark.parametrize("spans", [
    ((20.0, 40.0), (20.0, 40.0)),
    ((20.0, 40.0), (60.0, 80.0)),
])
def test_repeated_physical_identity_abstains_even_if_disjoint(spans):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = tuple(
        ApertureHostCandidateInput("same", (lo, 0.0), (hi, 0.0))
        for lo, hi in spans
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(records) == 2 and piers == ()
    assert all(r.status is S.ABSTAINED for r in records)
    assert all(r.first_remaining_gate == "aperture_physical_interval_conflict" for r in records)


def test_ambiguous_intervals_do_not_create_pier_across_their_gap():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = (
        ApertureHostCandidateInput("left", (5.0, 0.0), (15.0, 0.0)),
        ApertureHostCandidateInput("A", (20.0, 0.0), (50.0, 0.0)),
        ApertureHostCandidateInput("B", (40.0, 0.0), (60.0, 0.0)),
        ApertureHostCandidateInput("right", (65.0, 0.0), (75.0, 0.0)),
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    by_id = {r.physical_opening_id: r for r in records}
    assert by_id["left"].status is S.CANDIDATE
    assert by_id["right"].status is S.CANDIDATE
    assert by_id["A"].status is S.ABSTAINED
    assert by_id["B"].status is S.ABSTAINED
    assert piers == ()
    assert all(not r.adjacent_pier_ids for r in records)


@pytest.mark.parametrize("gap,expected_piers", [(0.0, 0), (2.0, 1)])
def test_touching_and_disjoint_apertures_preserve_shadow_positive(gap, expected_piers):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("B", (40.0 + gap, 0.0), (60.0 + gap, 0.0)),
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert all(r.status is S.CANDIDATE for r in records)
    assert all(r.first_remaining_gate == "original_source_host_unverified" for r in records)
    assert len(piers) == expected_piers
    assert all(r.shadow_only and not r.takeoff_eligible for r in records)


def test_overlap_veto_rotation_translation_invariant():
    authority = _authority()
    for angle, shift in ((0.0, (0.0, 0.0)), (math.pi / 2, (250.0, 70.0)),
                         (math.pi, (-100.0, 300.0))):
        tr = lambda p: _rotated(p, angle, shift)
        wall = ContinuousThroughWallCandidate(
            "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
        )
        openings = (
            ApertureHostCandidateInput("A", tr((20.0, 0.0)), tr((60.0, 0.0))),
            ApertureHostCandidateInput("B", tr((40.0, 0.0)), tr((80.0, 0.0))),
        )
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings,
        )
        assert piers == ()
        assert all(r.status is S.ABSTAINED for r in records)
        assert all(r.first_remaining_gate == "aperture_physical_interval_conflict"
                   for r in records)


def test_host_and_pier_ids_do_not_alias_different_source_revisions_or_host_geometry():
    """Stable shadow identities must bind original-source ownership and physical host."""
    def evaluate(revision, source_sha, *, offset=0.0, thickness=20.0, reverse=False):
        wall = ContinuousThroughWallCandidate(
            "host", (offset, 0.0), (offset + 100.0, 0.0), thickness,
        )
        openings = (
            ApertureHostCandidateInput("A", (offset + 20.0, 0.0), (offset + 40.0, 0.0)),
            ApertureHostCandidateInput("B", (offset + 50.0, 0.0), (offset + 70.0, 0.0)),
        )
        authority = StructuralThroughWallApertureHostAuthority(
            StructuralThroughWallApertureHostProducer(
                document_id="synthetic", revision_id=revision, source_sha256=source_sha,
            )
        )
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings[::-1] if reverse else openings,
        )
        assert len(records) == 2 and len(piers) == 1
        assert all(r.status is S.CANDIDATE for r in records)
        assert all(r.shadow_only and not r.takeoff_eligible
                   and not r.commercial_projection_allowed for r in records)
        return {r.physical_opening_id: r.hosting_record_id for r in records}, piers[0].pier_id

    original = evaluate("r1", "a" * 64)
    assert original == evaluate("r1", "a" * 64)
    assert original == evaluate("r1", "a" * 64, reverse=True)
    for changed in (
        evaluate("r2", "a" * 64),
        evaluate("r1", "b" * 64),
        evaluate("r1", "a" * 64, offset=1000.0),
        evaluate("r1", "a" * 64, thickness=30.0),
    ):
        assert changed[1] != original[1]  # pier must not alias
        assert set(changed[0]) == set(original[0])
        assert all(changed[0][name] != original[0][name] for name in original[0])


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (250.0, -130.0)),
    (math.pi, (-80.0, 400.0)),
])
@pytest.mark.parametrize("span", [
    (-2.0, -1.0), (101.0, 102.0),
    (-2.0, 0.0), (100.0, 102.0),
])
def test_endpoint_snap_does_not_host_wholly_external_aperture(span, angle, shift):
    # These pass the 2.5pt endpoint tolerance but have zero host overlap.
    tr = lambda p: _rotated(p, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "outside", tr((span[0], 0.0)), tr((span[1], 0.0)),
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    assert len(records) == 1 and piers == ()
    record = records[0]
    assert record.status is S.ABSTAINED
    assert record.first_remaining_gate == "aperture_no_host_wall_overlap"
    assert record.adjacent_pier_ids == ()
    assert record.shadow_only and not record.takeoff_eligible
    assert not record.commercial_projection_allowed
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    ) == (records, piers)


@pytest.mark.parametrize("span,expected", [
    ((-2.0, 10.0), (0.0, 10.0)),
    ((90.0, 102.0), (90.0, 100.0)),
])
def test_partial_endpoint_straddles_retain_real_positive_host_overlap(span, expected):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput(
        "partially-hosted", (span[0], 0.0), (span[1], 0.0),
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    assert len(records) == 1 and piers == ()
    assert records[0].status is S.CANDIDATE
    assert records[0].first_remaining_gate == "original_source_host_unverified"
    assert (records[0].u0_pt, records[0].u1_pt) == expected
    assert records[0].shadow_only and not records[0].takeoff_eligible
    assert not records[0].commercial_projection_allowed


def test_external_endpoint_candidate_cannot_be_a_pier_neighbor():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = (
        ApertureHostCandidateInput("outside", (-2.0, 0.0), (-1.0, 0.0)),
        ApertureHostCandidateInput("A", (20.0, 0.0), (30.0, 0.0)),
        ApertureHostCandidateInput("B", (40.0, 0.0), (50.0, 0.0)),
    )
    authority = _authority()
    for order in (openings, openings[::-1]):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=order,
        )
        by_id = {r.physical_opening_id: r for r in records}
        assert by_id["outside"].status is S.ABSTAINED
        assert by_id["outside"].adjacent_pier_ids == ()
        assert by_id["A"].status is S.CANDIDATE
        assert by_id["B"].status is S.CANDIDATE
        assert len(piers) == 1
        assert (piers[0].left_opening_id, piers[0].right_opening_id) == ("A", "B")
        assert "outside" not in (piers[0].left_opening_id, piers[0].right_opening_id)


@pytest.mark.parametrize("bad_points,bad_gate,obstruction", [
    (((85.0, 40.0), (95.0, 40.0)), "aperture_outside_host_wall_band", None),
    (((-2.0, 0.0), (-1.0, 0.0)), "aperture_no_host_wall_overlap", None),
    (((85.0, 0.0), (95.0, 0.0)), "host_through_wall_obstructed",
     ((90.0, -30.0), (90.0, 30.0))),
    (((85.0, 0.0), (85.0, 20.0)), "aperture_wall_axis_misaligned", None),
])
@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (300.0, -100.0)),
])
def test_repeated_physical_identity_including_abstained_candidate_vetoes_valid(
    bad_points, bad_gate, obstruction, angle, shift,
):
    """An invalid sibling cannot disappear from the physical identity universe."""
    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("A", tr((20.0, 0.0)), tr((30.0, 0.0))),
        ApertureHostCandidateInput("A", tr(bad_points[0]), tr(bad_points[1])),
        ApertureHostCandidateInput("B", tr((40.0, 0.0)), tr((50.0, 0.0))),
        ApertureHostCandidateInput("C", tr((70.0, 0.0)), tr((80.0, 0.0))),
    )
    transverse = (tuple(map(tr, obstruction)),) if obstruction else ()
    authority = _authority()
    canonical = None
    for ordered in (openings, openings[::-1]):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordered,
            transverse_wall_segments=transverse,
        )
        assert authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordered,
            transverse_wall_segments=transverse,
        ) == (records, piers)
        assert len(records) == 4
        assert sorted(r.first_remaining_gate for r in records
                      if r.physical_opening_id == "A") == sorted((
                          "aperture_physical_interval_conflict", bad_gate,
                      ))
        assert all(r.status is S.ABSTAINED for r in records
                   if r.physical_opening_id == "A")
        assert all(r.status is S.CANDIDATE for r in records
                   if r.physical_opening_id in ("B", "C"))
        assert len(piers) == 1
        assert (piers[0].left_opening_id, piers[0].right_opening_id) == ("B", "C")
        assert all(r.shadow_only and not r.takeoff_eligible
                   and not r.commercial_projection_allowed for r in records)
        normalized = sorted(
            (r.physical_opening_id, r.u0_pt, r.u1_pt,
             r.status.value, r.first_remaining_gate, r.hosting_record_id)
            for r in records
        )
        if canonical is None:
            canonical = (normalized, piers)
        else:
            assert (normalized, piers) == canonical


def test_unrelated_invalid_identity_does_not_veto_genuine_valid_pier_neighbors():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (30.0, 0.0)),
        ApertureHostCandidateInput("D", (85.0, 40.0), (95.0, 40.0)),
        ApertureHostCandidateInput("B", (40.0, 0.0), (50.0, 0.0)),
        ApertureHostCandidateInput("C", (70.0, 0.0), (80.0, 0.0)),
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    by_id = {r.physical_opening_id: r for r in records}
    assert by_id["D"].status is S.ABSTAINED
    assert by_id["D"].first_remaining_gate == "aperture_outside_host_wall_band"
    assert all(by_id[k].status is S.CANDIDATE for k in ("A", "B", "C"))
    assert len(piers) == 2
    assert [(p.left_opening_id, p.right_opening_id) for p in piers] == [
        ("A", "B"), ("B", "C"),
    ]


@pytest.mark.parametrize("width", [4.0, 5.0, 6.0, 10.0])
@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (300.0, -200.0)),
    (math.pi, (-400.0, 700.0)),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_narrow_aperture_crossing_is_never_erased_by_snap(width, angle, shift, reverse):
    """Even a 4pt opening retains a testable finite obstruction interior."""
    tr = lambda point: _rotated(point, angle, shift)
    centre = 20.0 + width / 2.0
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "narrow", tr((20.0, 0.0)), tr((20.0 + width, 0.0)),
    )
    crossing = (tr((centre, -30.0)), tr((centre, 30.0)))
    if reverse:
        crossing = crossing[::-1]
    unrelated = (tr((90.0, -30.0)), tr((90.0, 30.0)))
    split = (
        (tr((centre, -30.0)), tr((centre, 0.0))),
        (tr((centre, 0.0)), tr((centre, 30.0))),
    )
    authority = _authority()
    for snap in (0.0, 2.5):
        for segments in ((crossing,), (unrelated, crossing),
                         (crossing, unrelated), split, split[::-1]):
            records, piers = authority.bind_openings_to_through_wall(
                through_wall=wall, openings=(opening,),
                transverse_wall_segments=segments, snap_tolerance_pt=snap,
            )
            assert len(records) == 1 and piers == ()
            assert records[0].status is S.ABSTAINED
            assert records[0].first_remaining_gate == "host_through_wall_obstructed"
            assert records[0].shadow_only and not records[0].takeoff_eligible
            assert not records[0].commercial_projection_allowed
            assert authority.bind_openings_to_through_wall(
                through_wall=wall, openings=(opening,),
                transverse_wall_segments=segments, snap_tolerance_pt=snap,
            ) == (records, piers)
        for segments in ((), (unrelated,)):
            records, piers = authority.bind_openings_to_through_wall(
                through_wall=wall, openings=(opening,),
                transverse_wall_segments=segments, snap_tolerance_pt=snap,
            )
            assert len(records) == 1 and piers == ()
            assert records[0].status is S.CANDIDATE
            assert records[0].first_remaining_gate == "original_source_host_unverified"
            assert records[0].shadow_only and not records[0].takeoff_eligible
            assert not records[0].commercial_projection_allowed


@pytest.mark.parametrize("reverse", [False, True])
def test_finite_extreme_source_points_cannot_overflow_into_full_wall_host(reverse):
    # All FOUR endpoint coordinates and both individual segment lengths are
    # finite. Subtracting opposite ~1e308 origins overflows to infinity;
    # multiplying by the zero normal component then creates NaN. Without
    # projection validation, NaN skips both host-band and extent checks,
    # and min/max silently turn it into a CANDIDATE whole-wall interval.
    step = 2e292
    wall = ContinuousThroughWallCandidate(
        "huge-host", (-1e308, -1e308), (-1e308 + step, -1e308), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "distant-opening", (1e308, 1e308), (1e308 + step, 1e308),
    )
    assert math.isfinite(wall.length_pt)
    assert math.isfinite(math.dist(opening.start_pt, opening.end_pt))
    if reverse:
        wall = ContinuousThroughWallCandidate(
            wall.wall_id, wall.end_pt, wall.start_pt, wall.thickness_pt,
        )
        opening = ApertureHostCandidateInput(
            opening.physical_opening_id, opening.end_pt, opening.start_pt,
        )
    with pytest.raises(ValueError, match="aperture projection must remain finite"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
        )


def test_finite_projection_veto_preserves_normal_host_and_commercial_isolation():
    wall = ContinuousThroughWallCandidate("normal-host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("normal-opening", (20.0, 0.0), (40.0, 0.0))
    result = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    assert result == _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    records, piers = result
    assert len(records) == 1 and piers == ()
    assert records[0].status is S.CANDIDATE
    assert records[0].shadow_only is True
    assert records[0].takeoff_eligible is False
    assert records[0].commercial_projection_allowed is False


def test_source_neutral_host_and_pier_cannot_claim_original_authority():
    """A caller-provided source hash is a label, not verified source geometry."""
    wall = ContinuousThroughWallCandidate("shadow-wall", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("B", (50.0, 0.0), (70.0, 0.0)),
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(records) == 2 and len(piers) == 1
    assert all(r.status is S.CANDIDATE for r in records)
    assert all(r.first_remaining_gate == "original_source_host_unverified" for r in records)
    assert all(r.shadow_only and not r.takeoff_eligible
               and not r.commercial_projection_allowed for r in records)
    assert piers[0].is_structural_masonry_pier is None
    assert piers[0].status is S.CANDIDATE
    assert piers[0].first_remaining_gate == "original_source_structural_pier_unverified"
    reverse, reverse_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings[::-1],
    )
    assert {r.physical_opening_id: r for r in reverse} == {
        r.physical_opening_id: r for r in records
    }
    assert reverse_piers == piers


def test_source_precision_preserves_distinct_host_and_pier_hypotheses():
    """Sub-0.01pt changes must not alias identities or serialized stations."""
    authority = _authority()

    def evaluate(offset=0.0, end_a=40.0, thickness=20.0):
        wall = ContinuousThroughWallCandidate(
            "same-wall", (offset, 0.0), (100.0 + offset, 0.0), thickness,
        )
        openings = (
            ApertureHostCandidateInput("A", (20.0 + offset, 0.0), (end_a + offset, 0.0)),
            ApertureHostCandidateInput("B", (50.0 + offset, 0.0), (70.0 + offset, 0.0)),
        )
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings,
        )
        assert len(piers) == 1 and all(r.status is S.CANDIDATE for r in records)
        return records, piers[0]

    base_records, base_pier = evaluate()
    moved_records, moved_pier = evaluate(offset=0.00001)
    shifted_records, shifted_pier = evaluate(end_a=40.00001)
    thick_records, thick_pier = evaluate(thickness=20.00001)
    assert base_records[0].hosting_record_id != moved_records[0].hosting_record_id
    assert base_records[0].hosting_record_id != shifted_records[0].hosting_record_id
    assert base_records[0].hosting_record_id != thick_records[0].hosting_record_id
    assert len({base_pier.pier_id, moved_pier.pier_id,
                shifted_pier.pier_id, thick_pier.pier_id}) == 4
    assert shifted_pier.pier_width_pt != base_pier.pier_width_pt
    assert shifted_records[0].to_dict()["u1_pt"] != base_records[0].to_dict()["u1_pt"]


@pytest.mark.parametrize("bad", [2**53 + 1, -(2**53 + 1), 10**400])
def test_lossy_large_integer_source_coordinates_are_rejected(bad):
    with pytest.raises(ValueError, match="finite coordinates"):
        ContinuousThroughWallCandidate("host", (bad, 0), (100.0, 0.0), 20.0)
    with pytest.raises(ValueError, match="finite coordinates"):
        ApertureHostCandidateInput("opening", (0.0, 0.0), (bad, 0.0))


def test_transverse_shift_and_clipped_jambs_do_not_alias_host_receipts():
    authority = _authority()
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    variants = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("A", (20.0, 1.0), (40.0, 1.0)),
        ApertureHostCandidateInput("A", (-1.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("A", (0.0, 0.0), (40.0, 0.0)),
    )
    records = [
        authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
        )[0][0]
        for opening in variants
    ]
    assert all(r.status is S.CANDIDATE for r in records)
    assert records[0].u0_pt == records[1].u0_pt == 20.0
    assert records[0].u1_pt == records[1].u1_pt == 40.0
    assert records[2].u0_pt == records[3].u0_pt == 0.0
    assert records[2].u1_pt == records[3].u1_pt == 40.0
    assert len({r.hosting_record_id for r in records}) == 4
    assert records[0].to_dict()["opening_start_pt"] != records[1].to_dict()["opening_start_pt"]
    assert all(r.shadow_only and not r.takeoff_eligible
               and not r.commercial_projection_allowed for r in records)


def test_jamb_endpoint_and_observation_order_invariance_with_mutable_input_detachment():
    wall_start, wall_end = [0.0, 0.0], [100.0, 0.0]
    jamb_start, jamb_end = [20.0, 0.0], [40.0, 0.0]
    observations = ["right", "left"]
    wall = ContinuousThroughWallCandidate("host", wall_start, wall_end, 20.0)
    opening = ApertureHostCandidateInput(
        "A", jamb_start, jamb_end, observations,
    )
    assert opening.terminal_jamb_observation_ids == ("left", "right")
    assert isinstance(opening.start_pt, tuple) and isinstance(wall.start_pt, tuple)
    authority = _authority()
    first, _ = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    wall_start[0] = -500.0
    wall_end[0] = 500.0
    jamb_start[0] = -500.0
    jamb_end[0] = 500.0
    observations.append("forged")
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )[0] == first
    reversed_opening = ApertureHostCandidateInput(
        "A", (40.0, 0.0), (20.0, 0.0), ("left", "right"),
    )
    reverse, _ = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(reversed_opening,),
    )
    assert reverse == first
    assert first[0].to_dict()["terminal_jamb_observation_ids"] == ["left", "right"]


def test_distinct_transverse_pier_sources_cannot_share_pier_identity():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    authority = _authority()

    def evaluate(y, observations):
        openings = (
            ApertureHostCandidateInput("A", (20.0, y), (40.0, y), observations),
            ApertureHostCandidateInput("B", (50.0, 0.0), (70.0, 0.0)),
        )
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings,
        )
        assert len(piers) == 1 and all(r.status is S.CANDIDATE for r in records)
        return records, piers[0]

    original, first_pier = evaluate(0.0, ("jamb-left",))
    shifted, second_pier = evaluate(1.0, ("jamb-left",))
    retagged, third_pier = evaluate(0.0, ("jamb-new",))
    assert original[0].u0_pt == shifted[0].u0_pt
    assert first_pier.pier_width_pt == second_pier.pier_width_pt
    assert len({first_pier.pier_id, second_pier.pier_id, third_pier.pier_id}) == 3
    assert len({original[0].hosting_record_id, shifted[0].hosting_record_id,
                retagged[0].hosting_record_id}) == 3
    assert all(p.is_structural_masonry_pier is None
               and p.status is S.CANDIDATE
               for p in (first_pier, second_pier, third_pier))


@pytest.mark.parametrize("bad", [
    ("",), ("duplicate", "duplicate"), (True,), "not-an-observation-list",
])
def test_invalid_terminal_observation_universe_rejected(bad):
    with pytest.raises(ValueError, match="terminal_jamb_observation_ids"):
        ApertureHostCandidateInput(
            "A", (20.0, 0.0), (40.0, 0.0), bad,
        )


def test_distinct_openings_cannot_reuse_one_terminal_jamb_observation():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (500.0, 0.0), 20.0
    )
    first = ApertureHostCandidateInput(
        "opening_a", (100.0, 0.0), (200.0, 0.0),
        ("native_jamb_shared", "native_jamb_a"),
    )
    second = ApertureHostCandidateInput(
        "opening_b", (210.0, 0.0), (310.0, 0.0),
        ("native_jamb_shared", "native_jamb_b"),
    )
    authority = _authority()
    baseline = None
    for inputs in ((first, second), (second, first)):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=inputs,
        )
        assert not piers
        by_id = {record.physical_opening_id: record for record in records}
        assert set(by_id) == {"opening_a", "opening_b"}
        for record in by_id.values():
            assert record.status is S.ABSTAINED
            assert record.first_remaining_gate == "aperture_terminal_jamb_observation_conflict"
            assert not record.adjacent_pier_ids
            assert record.shadow_only and not record.takeoff_eligible
            assert not record.commercial_projection_allowed
        evidence = {key: value.to_dict() for key, value in by_id.items()}
        if baseline is None:
            baseline = evidence
        else:
            assert evidence == baseline


def test_invalid_sibling_still_vetoes_double_spent_terminal_observation():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (500.0, 0.0), 20.0
    )
    valid = ApertureHostCandidateInput(
        "opening_valid", (100.0, 0.0), (200.0, 0.0), ("native_shared",),
    )
    invalid = ApertureHostCandidateInput(
        "opening_outside", (300.0, 50.0), (400.0, 50.0), ("native_shared",),
    )
    unrelated = ApertureHostCandidateInput(
        "opening_unrelated", (250.0, 0.0), (350.0, 0.0), ("native_other",),
    )
    authority = _authority()
    for inputs in ((valid, invalid, unrelated), (unrelated, invalid, valid)):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=inputs,
        )
        by_id = {record.physical_opening_id: record for record in records}
        assert by_id["opening_valid"].status is S.ABSTAINED
        assert by_id["opening_valid"].first_remaining_gate == (
            "aperture_terminal_jamb_observation_conflict"
        )
        assert by_id["opening_outside"].status is S.ABSTAINED
        assert by_id["opening_outside"].first_remaining_gate == (
            "aperture_outside_host_wall_band"
        )
        assert by_id["opening_unrelated"].status is S.CANDIDATE
        assert by_id["opening_unrelated"].first_remaining_gate == (
            "original_source_host_unverified"
        )
        assert not piers


def test_distinct_terminal_observations_keep_geometric_pier_candidate():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (500.0, 0.0), 20.0
    )
    first = ApertureHostCandidateInput(
        "opening_a", (100.0, 0.0), (200.0, 0.0), ("native_a_left", "native_a_right"),
    )
    second = ApertureHostCandidateInput(
        "opening_b", (210.0, 0.0), (310.0, 0.0), ("native_b_left", "native_b_right"),
    )
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(first, second),
    )
    assert len(piers) == 1 and piers[0].pier_width_pt == 10.0
    assert piers[0].is_structural_masonry_pier is None
    assert piers[0].status is S.CANDIDATE
    assert all(record.status is S.CANDIDATE for record in records)
    assert all(record.first_remaining_gate == "original_source_host_unverified" for record in records)
    assert all(record.shadow_only and not record.takeoff_eligible for record in records)
