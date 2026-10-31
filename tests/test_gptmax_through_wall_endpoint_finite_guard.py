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
    # The source-coordinate identity bound rejects these extreme native
    # endpoints before any host projection. Reversal cannot bypass it.
    step = 2e292
    wall_points = ((-1e308, -1e308), (-1e308 + step, -1e308))
    opening_points = ((1e308, 1e308), (1e308 + step, 1e308))
    if reverse:
        wall_points = wall_points[::-1]
        opening_points = opening_points[::-1]
    with pytest.raises(ValueError, match="Through-wall endpoints must have finite coordinates"):
        ContinuousThroughWallCandidate("huge-host", *wall_points, 20.0)
    with pytest.raises(ValueError, match="Aperture endpoints must have finite coordinates"):
        ApertureHostCandidateInput("distant-opening", *opening_points)


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


def test_host_receipt_id_changes_with_geometric_pier_adjacency():
    """A changed pier neighborhood must never reuse the isolated host receipt ID.

    A pier remains source-unverified in every case; this is identity integrity
    for shadow evidence, not an original-source physical-host promotion.
    """
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (200.0, 0.0), 20.0,
    )
    opening_a = ApertureHostCandidateInput(
        "A", (20.0, 0.0), (40.0, 0.0), ("native_a_left", "native_a_right"),
    )
    opening_b = ApertureHostCandidateInput(
        "B", (50.0, 0.0), (70.0, 0.0), ("native_b_left", "native_b_right"),
    )
    opening_b_reobserved = ApertureHostCandidateInput(
        "B", (50.0, 0.0), (70.0, 0.0), ("native_b_new_left", "native_b_new_right"),
    )
    distant = ApertureHostCandidateInput(
        "C", (120.0, 0.0), (140.0, 0.0), ("native_c_left", "native_c_right"),
    )
    authority = _authority()

    def bind(openings):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings,
        )
        return {record.physical_opening_id: record for record in records}, piers

    isolated, no_piers = bind((opening_a,))
    distant_pair, distant_piers = bind((opening_a, distant))
    neighbors, piers = bind((opening_a, opening_b))
    reversed_neighbors, reversed_piers = bind((opening_b, opening_a))
    changed_neighbors, changed_piers = bind((opening_a, opening_b_reobserved))
    assert not no_piers and not distant_piers
    assert len(piers) == len(reversed_piers) == len(changed_piers) == 1
    assert isolated["A"].adjacent_pier_ids == distant_pair["A"].adjacent_pier_ids == ()
    assert isolated["A"].hosting_record_id == distant_pair["A"].hosting_record_id
    assert neighbors["A"].hosting_record_id != isolated["A"].hosting_record_id
    assert neighbors["A"].adjacent_pier_ids == (piers[0].pier_id,)
    assert neighbors["A"].hosting_record_id == reversed_neighbors["A"].hosting_record_id
    assert neighbors["B"].hosting_record_id == reversed_neighbors["B"].hosting_record_id
    assert piers == reversed_piers
    # A's native jamb geometry and physical ID are unchanged, but B's
    # source observation changed, so A's adjacent pier lineage changed.
    assert neighbors["A"].opening_start_pt == changed_neighbors["A"].opening_start_pt
    assert neighbors["A"].opening_end_pt == changed_neighbors["A"].opening_end_pt
    assert piers[0].pier_id != changed_piers[0].pier_id
    assert neighbors["A"].hosting_record_id != changed_neighbors["A"].hosting_record_id
    assert neighbors["A"].to_dict()["adjacent_pier_ids"] != (
        changed_neighbors["A"].to_dict()["adjacent_pier_ids"]
    )
    for rows in (isolated, distant_pair, neighbors, reversed_neighbors, changed_neighbors):
        assert all(record.status is S.CANDIDATE for record in rows.values())
        assert all(record.first_remaining_gate == "original_source_host_unverified"
                   for record in rows.values())
        assert all(record.shadow_only and not record.takeoff_eligible
                   and not record.commercial_projection_allowed
                   for record in rows.values())
    assert all(pier.is_structural_masonry_pier is None for pier in (*piers, *changed_piers))
    assert opening_a.terminal_jamb_observation_ids == ("native_a_left", "native_a_right")


def test_conflicting_neighbor_cannot_change_isolated_host_identity_or_create_pier():
    """An overlap-conflicted neighbor cannot mint a pier or change A's receipt."""
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (200.0, 0.0), 20.0,
    )
    a = ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0))
    b = ApertureHostCandidateInput("B", (50.0, 0.0), (70.0, 0.0))
    conflict = ApertureHostCandidateInput("D", (55.0, 0.0), (75.0, 0.0))
    authority = _authority()
    isolated, _ = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(a,),
    )
    for openings in ((a, b, conflict), (conflict, b, a)):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings,
        )
        assert piers == ()
        by_id = {record.physical_opening_id: record for record in records}
        assert by_id["A"].status is S.CANDIDATE
        assert by_id["A"].adjacent_pier_ids == ()
        assert by_id["A"].hosting_record_id == isolated[0].hosting_record_id
        assert all(by_id[key].status is S.ABSTAINED for key in ("B", "D"))
        assert all(by_id[key].first_remaining_gate == "aperture_physical_interval_conflict"
                   for key in ("B", "D"))
        assert all(record.shadow_only and not record.takeoff_eligible
                   and not record.commercial_projection_allowed
                   for record in records)


@pytest.mark.parametrize("mode,gate,expected_piers", [
    ("misaligned", "aperture_wall_axis_misaligned", 0),
    ("obstructed", "host_through_wall_obstructed", 0),
    ("far_off_band", "aperture_outside_host_wall_band", 1),
])
@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (250.0, -130.0)),
])
def test_rejected_in_band_opening_cannot_be_skipped_for_pier_adjacency(
    mode, gate, expected_piers, angle, shift,
):
    """An unreviewed footprint between hosts cannot prove a physical pier."""
    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    a = ApertureHostCandidateInput("A", tr((20.0, 0.0)), tr((30.0, 0.0)))
    c = ApertureHostCandidateInput("C", tr((40.0, 0.0)), tr((50.0, 0.0)))
    if mode == "misaligned":
        middle = ApertureHostCandidateInput(
            "unreviewed", tr((34.0, 0.0)), tr((36.0, 4.0)),
        )
        transverse = ()
    elif mode == "obstructed":
        middle = ApertureHostCandidateInput(
            "unreviewed", tr((33.0, 0.0)), tr((37.0, 0.0)),
        )
        transverse = ((tr((35.0, -30.0)), tr((35.0, 30.0))),)
    else:
        middle = ApertureHostCandidateInput(
            "unreviewed", tr((34.0, 40.0)), tr((36.0, 40.0)),
        )
        transverse = ()

    authority = _authority()
    canonical = None
    for openings in ((a, middle, c), (c, middle, a)):
        original_points = tuple((op.start_pt, op.end_pt) for op in openings)
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall,
            openings=openings,
            transverse_wall_segments=transverse,
        )
        assert tuple((op.start_pt, op.end_pt) for op in openings) == original_points
        assert len(records) == 3
        by_id = {record.physical_opening_id: record for record in records}
        assert by_id["unreviewed"].status is S.ABSTAINED
        assert by_id["unreviewed"].first_remaining_gate == gate
        assert all(by_id[k].status is S.CANDIDATE for k in ("A", "C"))
        assert len(piers) == expected_piers
        assert all(p.status is S.CANDIDATE and p.is_structural_masonry_pier is None
                   for p in piers)
        assert all(record.shadow_only and not record.takeoff_eligible
                   and not record.commercial_projection_allowed
                   for record in records)
        assert all(len(by_id[k].adjacent_pier_ids) == expected_piers
                   for k in ("A", "C"))
        observed = (
            {key: (record.hosting_record_id, record.status, record.first_remaining_gate,
                   record.adjacent_pier_ids) for key, record in by_id.items()},
            tuple(piers),
        )
        if canonical is None:
            canonical = observed
        else:
            assert observed == canonical
        assert authority.bind_openings_to_through_wall(
            through_wall=wall, openings=openings,
            transverse_wall_segments=transverse,
        ) == (records, piers)


def test_dense_unreviewed_wall_band_universe_never_mints_false_piers():
    """Thousands of rejected in-band candidates must not cause pairwise scans."""
    count = 2048
    wall = ContinuousThroughWallCandidate(
        "dense-host", (0.0, 0.0), (count * 10.0 + 10.0, 0.0), 20.0,
    )
    openings = []
    for i in range(count):
        station = i * 10.0
        openings.append(ApertureHostCandidateInput(
            f"valid-{i}", (station + 1.0, 0.0), (station + 3.0, 0.0),
        ))
        if i < count - 1:
            # In-band but misaligned, strictly inside the 8pt proposed gap.
            openings.append(ApertureHostCandidateInput(
                f"rejected-{i}", (station + 5.0, 0.0),
                (station + 6.0, 4.0),
            ))
    originals = tuple((op.start_pt, op.end_pt) for op in openings)
    authority = _authority()
    canonical = None
    for ordered in (tuple(openings), tuple(reversed(openings))):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordered,
        )
        assert len(records) == 2 * count - 1
        assert piers == ()
        by_id = {record.physical_opening_id: record for record in records}
        assert len(by_id) == len(records)
        assert all(by_id[f"valid-{i}"].status is S.CANDIDATE
                   for i in range(count))
        assert all(by_id[f"rejected-{i}"].status is S.ABSTAINED
                   and by_id[f"rejected-{i}"].first_remaining_gate
                   == "aperture_wall_axis_misaligned"
                   for i in range(count - 1))
        assert all(not r.adjacent_pier_ids and r.shadow_only
                   and not r.takeoff_eligible and not r.commercial_projection_allowed
                   for r in records)
        observed = {key: (rec.hosting_record_id, rec.first_remaining_gate)
                    for key, rec in by_id.items()}
        if canonical is None:
            canonical = observed
        else:
            assert observed == canonical
    assert tuple((op.start_pt, op.end_pt) for op in openings) == originals


def test_rejected_wall_band_interval_edge_touch_does_not_veto_pier():
    """Retain strict overlap semantics: touching a boundary is not crossing."""
    wall = ContinuousThroughWallCandidate(
        "edge-host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    a = ApertureHostCandidateInput("A", (20.0, 0.0), (30.0, 0.0))
    b = ApertureHostCandidateInput("B", (40.0, 0.0), (50.0, 0.0))
    left_touch = ApertureHostCandidateInput(
        "left-touch", (29.0, 0.0), (30.0, 4.0),
    )
    right_touch = ApertureHostCandidateInput(
        "right-touch", (40.0, 0.0), (41.0, 4.0),
    )
    authority = _authority()
    canonical = None
    for ordered in (
        (a, b, left_touch, right_touch),
        (right_touch, left_touch, b, a),
    ):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordered,
        )
        by_id = {r.physical_opening_id: r for r in records}
        assert len(piers) == 1
        assert piers[0].pier_width_pt == 10.0
        assert piers[0].is_structural_masonry_pier is None
        assert all(by_id[key].status is S.CANDIDATE for key in ("A", "B"))
        assert all(by_id[key].status is S.ABSTAINED
                   and by_id[key].first_remaining_gate == "aperture_wall_axis_misaligned"
                   for key in ("left-touch", "right-touch"))
        assert all(r.shadow_only and not r.takeoff_eligible
                   and not r.commercial_projection_allowed for r in records)
        evidence = ({key: r.to_dict() for key, r in by_id.items()}, piers)
        if canonical is None:
            canonical = evidence
        else:
            assert evidence == canonical


@pytest.mark.parametrize("bad", [
    "", " ", " jamb-1", "jamb-1 ", "jamb-1\n", "jamb-1\t",
    1, True, None, ["jamb-1"], {"id": "jamb-1"},
])
def test_source_identity_boundaries_reject_aliases_without_coercion(bad):
    """Native source ownership is not a trimmed or stringified caller label."""
    with pytest.raises(ValueError, match="wall_id required"):
        ContinuousThroughWallCandidate(bad, (0.0, 0.0), (100.0, 0.0), 20.0)
    with pytest.raises(ValueError, match="physical_opening_id required"):
        ApertureHostCandidateInput(bad, (20.0, 0.0), (30.0, 0.0))
    with pytest.raises(ValueError, match="terminal_jamb_observation_ids"):
        ApertureHostCandidateInput(
            "A", (20.0, 0.0), (30.0, 0.0),
            terminal_jamb_observation_ids=("jamb-2", bad),
        )
    for field in ("document_id", "revision_id", "source_sha256"):
        kwargs = dict(document_id="doc", revision_id="v1", source_sha256="0" * 64)
        kwargs[field] = bad
        with pytest.raises(ValueError, match=f"{field} required"):
            StructuralThroughWallApertureHostProducer(**kwargs)


def test_exact_native_jamb_ownership_cannot_be_double_spent_by_distinct_apertures():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    # A padded alias must be rejected at the input boundary rather than
    # evading the complete-universe reused-observation conflict check.
    with pytest.raises(ValueError, match="terminal_jamb_observation_ids"):
        ApertureHostCandidateInput(
            "B", (40.0, 0.0), (50.0, 0.0),
            terminal_jamb_observation_ids=(" jamb-shared ",),
        )
    a = ApertureHostCandidateInput(
        "A", (20.0, 0.0), (30.0, 0.0),
        terminal_jamb_observation_ids=("jamb-shared",),
    )
    b = ApertureHostCandidateInput(
        "B", (40.0, 0.0), (50.0, 0.0),
        terminal_jamb_observation_ids=("jamb-shared",),
    )
    authority = _authority()
    for ordered in ((a, b), (b, a)):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordered,
        )
        assert piers == ()
        assert {r.physical_opening_id for r in records} == {"A", "B"}
        assert all(
            r.status is S.ABSTAINED
            and r.first_remaining_gate == "aperture_terminal_jamb_observation_conflict"
            and r.shadow_only
            and not r.takeoff_eligible
            and not r.commercial_projection_allowed
            for r in records
        )


def test_clean_distinct_source_observations_preserve_shadow_replay_and_no_mutation():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    original_observations = ["jamb-A"]
    a = ApertureHostCandidateInput(
        "A", (20.0, 0.0), (30.0, 0.0),
        terminal_jamb_observation_ids=original_observations,
    )
    original_observations.append("injected")
    b = ApertureHostCandidateInput(
        "B", (40.0, 0.0), (50.0, 0.0),
        terminal_jamb_observation_ids=("jamb-B",),
    )
    assert a.terminal_jamb_observation_ids == ("jamb-A",)
    authority = _authority()
    first, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(a, b),
    )
    replay, reversed_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(b, a),
    )
    assert len(piers) == len(reversed_piers) == 1
    assert piers == reversed_piers
    assert {r.physical_opening_id: r for r in first} == {
        r.physical_opening_id: r for r in replay
    }
    assert all(
        r.status is S.CANDIDATE
        and r.first_remaining_gate == "original_source_host_unverified"
        and r.shadow_only
        and not r.takeoff_eligible
        and not r.commercial_projection_allowed
        for r in first
    )

@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (300.0, -250.0)),
    (math.pi, (-400.0, 600.0)),
])
@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("mode,expected_piers", [
    ("crosses-band", 0),
    ("off-band", 1),
    ("boundary-touch", 1),
    ("crosses-away-from-gap", 1),
])
def test_rejected_aperture_segment_band_clipping_preserves_pier_uncertainty(
    angle, shift, reverse, mode, expected_piers,
):
    """A rejected oblique aperture crossing the host band is not absent evidence."""
    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    left = ApertureHostCandidateInput(
        "left", tr((20.0, 0.0)), tr((30.0, 0.0)),
    )
    right = ApertureHostCandidateInput(
        "right", tr((40.0, 0.0)), tr((50.0, 0.0)),
    )
    rejected_segments = {
        "crosses-band": ((33.0, 0.0), (37.0, 30.0)),
        "off-band": ((33.0, 30.0), (37.0, 35.0)),
        "boundary-touch": ((33.0, 30.0), (37.0, 12.5)),
        "crosses-away-from-gap": ((0.0, 0.0), (20.0, 30.0)),
    }
    p0, p1 = rejected_segments[mode]
    unreviewed = ApertureHostCandidateInput(
        "unreviewed", tr(p0), tr(p1),
    )
    openings = (left, unreviewed, right)
    if reverse:
        openings = tuple(reversed(openings))
    original = tuple((op.start_pt, op.end_pt) for op in openings)
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    by_id = {record.physical_opening_id: record for record in records}
    assert tuple((op.start_pt, op.end_pt) for op in openings) == original
    assert by_id["unreviewed"].status is S.ABSTAINED
    assert by_id["unreviewed"].first_remaining_gate == "aperture_wall_axis_misaligned"
    assert all(by_id[name].status is S.CANDIDATE for name in ("left", "right"))
    assert len(piers) == expected_piers
    assert all(p.status is S.CANDIDATE and p.is_structural_masonry_pier is None
               for p in piers)
    assert all(len(by_id[name].adjacent_pier_ids) == expected_piers
               for name in ("left", "right"))
    assert all(r.shadow_only and not r.takeoff_eligible
               and not r.commercial_projection_allowed for r in records)
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    ) == (records, piers)


def test_dense_oblique_rejected_candidates_cannot_mint_unproven_piers():
    """The clipped interval index stays deterministic without pairwise gap scans."""
    count = 512
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (count * 10.0 + 10.0, 0.0), 20.0,
    )
    openings = []
    for i in range(count):
        station = i * 10.0
        openings.append(ApertureHostCandidateInput(
            f"valid-{i}", (station + 1.0, 0.0), (station + 3.0, 0.0),
        ))
        if i < count - 1:
            openings.append(ApertureHostCandidateInput(
                f"oblique-{i}", (station + 5.0, 0.0),
                (station + 7.0, 30.0),
            ))
    authority = _authority()
    baseline = None
    for ordered in (tuple(openings), tuple(reversed(openings))):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=ordered,
        )
        assert len(records) == 2 * count - 1 and piers == ()
        by_id = {r.physical_opening_id: r for r in records}
        assert all(by_id[f"valid-{i}"].status is S.CANDIDATE
                   and not by_id[f"valid-{i}"].adjacent_pier_ids
                   for i in range(count))
        assert all(by_id[f"oblique-{i}"].status is S.ABSTAINED
                   for i in range(count - 1))
        assert all(r.shadow_only and not r.takeoff_eligible
                   and not r.commercial_projection_allowed for r in records)
        evidence = {key: (rec.hosting_record_id, rec.first_remaining_gate)
                    for key, rec in by_id.items()}
        if baseline is None:
            baseline = evidence
        else:
            assert evidence == baseline


def test_single_pass_transverse_obstruction_cannot_disappear_after_validation():
    """Validation must not consume the only copy of a real crossing."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0))
    crossing = ((30.0, -30.0), (30.0, 30.0))
    one_shot = iter((crossing,))
    with pytest.raises(ValueError, match="transverse_wall_segments must be a complete"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
            transverse_wall_segments=one_shot,
        )
    # Reject before consuming or silently losing any source obstruction.
    assert next(one_shot) == crossing
    for replayable in ((crossing,), [list(map(list, crossing))]):
        records, piers = _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=[opening],
            transverse_wall_segments=replayable,
        )
        assert len(records) == 1 and not piers
        assert records[0].status is S.ABSTAINED
        assert records[0].first_remaining_gate == "host_through_wall_obstructed"
        assert records[0].shadow_only and not records[0].takeoff_eligible
        assert not records[0].commercial_projection_allowed


def test_single_pass_opening_universe_cannot_hide_competing_native_jambs():
    """The ownership pass must see every opening that geometry already saw."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    a = ApertureHostCandidateInput("A", (20.0, 0.0), (30.0, 0.0), ("shared",))
    b = ApertureHostCandidateInput("B", (40.0, 0.0), (50.0, 0.0), ("shared",))
    one_shot = iter((a, b))
    with pytest.raises(ValueError, match="openings must be a complete"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=one_shot,
        )
    assert next(one_shot) is a
    for replayable in ((a, b), [a, b]):
        records, piers = _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=replayable,
        )
        assert len(records) == 2 and not piers
        assert all(r.status is S.ABSTAINED for r in records)
        assert all(r.first_remaining_gate ==
                   "aperture_terminal_jamb_observation_conflict" for r in records)
        assert all(r.shadow_only and not r.takeoff_eligible
                   and not r.commercial_projection_allowed for r in records)


@pytest.mark.parametrize("bad_openings", [None, "A", {"A": "B"}, (None,), ["raw"]])
def test_incomplete_or_untyped_opening_universe_fails_before_projection(bad_openings):
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    with pytest.raises(ValueError, match="openings must"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=bad_openings,
        )


def test_transverse_obstruction_snapshot_detaches_mutable_endpoint_lists():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0))
    mutable_crossing = [[30.0, -30.0], [30.0, 30.0]]
    before = [point.copy() for point in mutable_crossing]
    first, first_piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=[opening],
        transverse_wall_segments=[mutable_crossing],
    )
    assert mutable_crossing == before
    assert first[0].first_remaining_gate == "host_through_wall_obstructed"
    assert not first_piers
    second, second_piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
        transverse_wall_segments=((tuple(before[0]), tuple(before[1])),),
    )
    assert (first, first_piers) == (second, second_piers)


def test_dense_transverse_obstruction_budget_fails_before_shadow_records():
    """A complete valid universe cannot require hundreds of millions of scans."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (2000.0, 0.0), 20.0)
    openings = tuple(
        ApertureHostCandidateInput(f"opening-{i}", (4.0 * i, 0.0), (4.0 * i + 1.0, 0.0))
        for i in range(501)
    )
    # Each valid transverse segment is unrelated to the wall band. A naive
    # implementation still loops through all 250,500 pairs before finding none.
    transverse = tuple(
        ((float(i), 100.0), (float(i), 120.0)) for i in range(500)
    )
    authority = _authority()
    original_openings = tuple(openings)
    original_transverse = tuple(transverse)
    for candidates in (openings, openings[::-1]):
        with pytest.raises(ValueError, match="transverse_wall_intersection_budget_exceeded"):
            authority.bind_openings_to_through_wall(
                through_wall=wall, openings=candidates,
                transverse_wall_segments=transverse,
            )
    assert openings == original_openings and transverse == original_transverse
    # No partial CANDIDATE/ABSTAINED record or invented pier is returned.


def test_transverse_work_budget_boundary_and_small_positive_are_fail_closed():
    """Exact budget is accepted; budget is not a physical geometry tolerance."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (2000.0, 0.0), 20.0)
    # All openings are outside the wall band, so the exact 500x500 boundary
    # exercises the preflight without spending 250k geometric intersections.
    invalid_openings = tuple(
        ApertureHostCandidateInput(f"far-{i}", (4.0 * i, 100.0), (4.0 * i + 1.0, 100.0))
        for i in range(500)
    )
    transverse = tuple(
        ((float(i), 100.0), (float(i), 120.0)) for i in range(500)
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=invalid_openings,
        transverse_wall_segments=transverse,
    )
    assert len(records) == 500 and piers == ()
    assert all(record.status is S.ABSTAINED for record in records)
    assert all(record.first_remaining_gate == "aperture_outside_host_wall_band"
               for record in records)
    assert all(record.shadow_only and not record.takeoff_eligible
               and not record.commercial_projection_allowed for record in records)
    # A small actual transverse obstruction still blocks the same physical
    # candidate, and an unrelated one cannot silently erase that veto.
    opening = ApertureHostCandidateInput("real", (20.0, 0.0), (40.0, 0.0))
    crossing = ((30.0, -30.0), (30.0, 30.0))
    unrelated = ((50.0, 100.0), (50.0, 120.0))
    for obstructions in ((crossing,), (unrelated, crossing), (crossing, unrelated)):
        actual, actual_piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
            transverse_wall_segments=obstructions,
        )
        assert len(actual) == 1 and not actual_piers
        assert actual[0].status is S.ABSTAINED
        assert actual[0].first_remaining_gate == "host_through_wall_obstructed"
        assert not actual[0].commercial_projection_allowed


def test_complete_primitive_cap_rejects_opening_only_overflow_before_shadow():
    """A zero transverse product cannot bypass the repository's 20k cap."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    openings = tuple(
        ApertureHostCandidateInput(f"native-{i}", (20.0, 0.0), (30.0, 0.0))
        for i in range(20_000)
    )
    original = openings
    authority = _authority()
    for order in (openings, openings[::-1]):
        with pytest.raises(ValueError, match="through_wall_primitive_limit_exceeded"):
            authority.bind_openings_to_through_wall(
                through_wall=wall, openings=order,
                transverse_wall_segments=(),
            )
    assert openings == original
    # No partial candidate, inferred pier, FIRM authority or commercial row.


def test_complete_primitive_cap_rejects_transverse_only_overflow_and_keeps_boundary():
    """A zero opening product also requires a complete, bounded obstruction universe."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    transverse = tuple(
        ((float(i), 100.0), (float(i), 120.0))
        for i in range(20_000)
    )
    original = transverse
    authority = _authority()
    with pytest.raises(ValueError, match="through_wall_primitive_limit_exceeded"):
        authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(),
            transverse_wall_segments=transverse,
        )
    # Exactly 20,000 total primitives: 1 host + 19,999 obstructions.
    # The empty opening universe must not emit a fabricated host or pier.
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(),
        transverse_wall_segments=transverse[:-1],
    ) == ((), ())
    assert transverse == original


def test_complete_primitive_cap_counts_host_and_both_universes():
    """The 20k cap is independent of the separate 250k pairwise-work budget."""
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("A", (20.0, 0.0), (30.0, 0.0))
    # 1 host + 1 opening + 19,999 segments exceeds 20k while the
    # 19,999 potential crossing checks remain BELOW the 250k budget.
    transverse = tuple(
        ((float(i), 100.0), (float(i), 120.0))
        for i in range(19_999)
    )
    with pytest.raises(ValueError, match="through_wall_primitive_limit_exceeded"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
            transverse_wall_segments=transverse,
        )
    # Small ordinary geometry retains the original shadow-only contract.
    records, piers = _authority().bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
        transverse_wall_segments=transverse[:1],
    )
    assert len(records) == 1 and piers == ()
    assert records[0].status is S.CANDIDATE
    assert records[0].first_remaining_gate == "original_source_host_unverified"
    assert records[0].shadow_only and not records[0].takeoff_eligible
    assert not records[0].commercial_projection_allowed


def test_complete_transverse_projection_rejects_hidden_overflow_in_both_orders():
    # An extreme obstruction cannot hide behind an earlier genuine crossing.
    # It now fails at the earliest native-coordinate gate in either order.
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "opening", (20.0, 0.0), (40.0, 0.0),
    )
    crossing = ((30.0, -30.0), (30.0, 30.0))
    distant = ((1e308, -30.0), (1e308, 30.0))
    authority = _authority()
    for segments in ((crossing, distant), (distant, crossing)):
        original = tuple(segments)
        with pytest.raises(ValueError, match="transverse_wall_segments require finite endpoint pairs"):
            authority.bind_openings_to_through_wall(
                through_wall=wall, openings=(opening,),
                transverse_wall_segments=segments,
            )
        assert segments == original

    # The legitimate crossing alone still vetoes an opening in shadow scope.
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
        transverse_wall_segments=(crossing,),
    )
    assert len(records) == 1 and piers == ()
    assert records[0].status is S.ABSTAINED
    assert records[0].first_remaining_gate == "host_through_wall_obstructed"
    assert records[0].shadow_only
    assert not records[0].takeoff_eligible
    assert not records[0].commercial_projection_allowed


def test_empty_opening_universe_still_validates_all_host_relative_obstructions():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    distant = ((1e308, -30.0), (1e308, 30.0))
    authority = _authority()
    for segments in ((distant,), [distant]):
        with pytest.raises(ValueError, match="transverse_wall_segments require finite endpoint pairs"):
            authority.bind_openings_to_through_wall(
                through_wall=wall, openings=(),
                transverse_wall_segments=segments,
            )
    # Empty and valid obstruction universes remain clean shadow-only empties.
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(), transverse_wall_segments=(),
    ) == ((), ())


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("empty_openings", [False, True])
def test_projected_transverse_overflow_cannot_hide_real_crossing(reverse, empty_openings):
    """Unrepresentable native endpoints are rejected before projection work."""
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "opening", (20.0, 0.0), (30.0, 0.0),
    )
    # The real crossing is at x=25, but native y coordinates exceed
    # the binary64 source-identity bound. Reject at the earliest source
    # gate rather than relying on the later projected-delta defense.
    extreme = ((25.0, -1e308), (25.0, 1e308))
    ordinary_crossing = ((25.0, -30.0), (25.0, 30.0))
    assert all(math.isfinite(v) for p in extreme for v in p)
    assert not math.isfinite(extreme[1][1] - extreme[0][1])
    segments = (ordinary_crossing, extreme)
    if reverse:
        segments = segments[::-1]
    before = tuple(tuple(tuple(p) for p in segment) for segment in segments)
    with pytest.raises(
        ValueError, match="transverse_wall_segments require finite endpoint pairs"
    ):
        _authority().bind_openings_to_through_wall(
            through_wall=wall,
            openings=() if empty_openings else (opening,),
            transverse_wall_segments=segments,
        )
    assert segments == before


def test_projected_transverse_overflow_guard_preserves_ordinary_shadow_results():
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "opening", (20.0, 0.0), (30.0, 0.0),
    )
    authority = _authority()
    normal = ((90.0, -30.0), (90.0, 30.0))
    crossing = ((25.0, -30.0), (25.0, 30.0))
    for segments, expected_status, expected_gate in (
        ((normal,), S.CANDIDATE, "original_source_host_unverified"),
        ((crossing,), S.ABSTAINED, "host_through_wall_obstructed"),
        ((normal, crossing), S.ABSTAINED, "host_through_wall_obstructed"),
        ((crossing, normal), S.ABSTAINED, "host_through_wall_obstructed"),
    ):
        records, piers = authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
            transverse_wall_segments=segments,
        )
        assert len(records) == 1 and not piers
        assert records[0].status is expected_status
        assert records[0].first_remaining_gate == expected_gate
        assert records[0].shadow_only and not records[0].takeoff_eligible
        assert not records[0].commercial_projection_allowed
        assert authority.bind_openings_to_through_wall(
            through_wall=wall, openings=(opening,),
            transverse_wall_segments=segments,
        ) == (records, piers)


@pytest.mark.parametrize("bad", [
    float(2**53 + 2), -float(2**53 + 2),
    float(2**60), -float(2**60),
])
@pytest.mark.parametrize("axis", [0, 1])
def test_lossy_large_float_source_coordinates_are_rejected_everywhere(bad, axis):
    """Native float endpoints have the same lossless identity limit as ints."""
    point = (bad, 0.0) if axis == 0 else (0.0, bad)
    with pytest.raises(ValueError, match="finite coordinates"):
        ContinuousThroughWallCandidate("host", point, (100.0, 0.0), 20.0)
    with pytest.raises(ValueError, match="finite coordinates"):
        ContinuousThroughWallCandidate("host", (0.0, 0.0), point, 20.0)
    with pytest.raises(ValueError, match="finite coordinates"):
        ApertureHostCandidateInput("opening", point, (100.0, 0.0))
    with pytest.raises(ValueError, match="finite coordinates"):
        ApertureHostCandidateInput("opening", (0.0, 0.0), point)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("empty_openings", [False, True])
@pytest.mark.parametrize("axis", [0, 1])
def test_lossy_float_transverse_coordinate_vetoes_entire_universe(
    reverse, empty_openings, axis,
):
    """An unrelated valid segment must not hide an aliased native endpoint."""
    bad = float(2**53 + 2)
    point = [bad, 0.0] if axis == 0 else [0.0, -bad]
    other = [bad, 10.0] if axis == 0 else [10.0, -bad]
    invalid = [point, other]
    valid = [[90.0, -30.0], [90.0, 30.0]]
    segments = [valid, invalid]
    if reverse:
        segments.reverse()
    before = [[p.copy() for p in segment] for segment in segments]
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "opening", (20.0, 0.0), (40.0, 0.0),
    )
    with pytest.raises(ValueError, match="finite endpoint pairs"):
        _authority().bind_openings_to_through_wall(
            through_wall=wall,
            openings=() if empty_openings else (opening,),
            transverse_wall_segments=segments,
        )
    assert segments == before


def test_source_coordinate_boundary_and_independent_scalar_validation():
    """The existing inclusive 2**53 boundary is not a thickness restriction."""
    bound = float(2**53)
    wall = ContinuousThroughWallCandidate(
        "host", (bound - 128.0, 0.0), (bound, 0.0), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "opening", (bound - 96.0, 0.0), (bound - 64.0, 0.0),
    )
    authority = _authority()
    first, first_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    second, second_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    assert (first, first_piers) == (second, second_piers)
    assert not first_piers
    assert first[0].status is S.CANDIDATE
    assert first[0].first_remaining_gate == "original_source_host_unverified"
    assert first[0].shadow_only and not first[0].takeoff_eligible
    assert not first[0].commercial_projection_allowed
    # Coordinate identity rules must not silently rewrite scalar semantics.
    large_thickness = ContinuousThroughWallCandidate(
        "scalar-only", (0.0, 0.0), (100.0, 0.0), float(2**53 + 2),
    )
    assert large_thickness.thickness_pt == float(2**53 + 2)


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (250.0, -130.0)),
])
def test_transverse_wall_inside_inter_aperture_gap_vetoes_unproved_pier(angle, shift):
    """A crossing between two valid openings is not an uninterrupted pier."""
    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    a = ApertureHostCandidateInput("A", tr((20.0, 0.0)), tr((30.0, 0.0)))
    b = ApertureHostCandidateInput("B", tr((50.0, 0.0)), tr((60.0, 0.0)))
    crossing = (tr((40.0, -30.0)), tr((40.0, 30.0)))
    unrelated = (tr((90.0, -30.0)), tr((90.0, 30.0)))
    authority = _authority()
    for openings in ((a, b), (b, a)):
        for obstructions in ((crossing, unrelated), (unrelated, crossing)):
            records, piers = authority.bind_openings_to_through_wall(
                through_wall=wall, openings=openings,
                transverse_wall_segments=obstructions,
            )
            assert piers == ()
            assert {r.physical_opening_id for r in records} == {"A", "B"}
            assert all(r.status is S.CANDIDATE
                       and r.first_remaining_gate == "original_source_host_unverified"
                       and r.adjacent_pier_ids == ()
                       and r.shadow_only and not r.takeoff_eligible
                       and not r.commercial_projection_allowed for r in records)
            assert authority.bind_openings_to_through_wall(
                through_wall=wall, openings=openings,
                transverse_wall_segments=obstructions,
            ) == (records, piers)
    # A crossing outside the proposed gap does not erase a shadow pier.
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(a, b),
        transverse_wall_segments=(unrelated,),
    )
    assert len(piers) == 1 and piers[0].status is S.CANDIDATE
    assert piers[0].is_structural_masonry_pier is None
    assert all(r.status is S.CANDIDATE and len(r.adjacent_pier_ids) == 1
               for r in records)


@pytest.mark.parametrize("obstruction,expect_pier", [
    (((40.0, -30.0), (40.0, 30.0)), False),  # gap interior crossing
    (((35.0, -30.0), (45.0, 30.0)), False),  # oblique gap crossing
    (((30.0, -30.0), (30.0, 30.0)), True),   # left edge only
    (((50.0, -30.0), (50.0, 30.0)), True),   # right edge only
    (((35.0, 10.0), (45.0, 10.0)), True),    # wall-band tangent
    (((40.0, 100.0), (40.0, 120.0)), True), # outside wall band
])
def test_pier_gap_crossing_is_strict_and_preserves_mutable_input(
    obstruction, expect_pier,
):
    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (30.0, 0.0)),
        ApertureHostCandidateInput("B", (50.0, 0.0), (60.0, 0.0)),
    )
    mutable = [[list(p) for p in obstruction]]
    before = [[p.copy() for p in segment] for segment in mutable]
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
        transverse_wall_segments=mutable,
    )
    assert mutable == before
    assert bool(piers) is expect_pier
    assert all(r.status is S.CANDIDATE and r.shadow_only
               and not r.takeoff_eligible and not r.commercial_projection_allowed
               for r in records)
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
        transverse_wall_segments=mutable,
    ) == (records, piers)


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2, (250.0, -130.0)),
])
def test_rejected_perpendicular_point_station_blocks_pier_but_band_tangent_does_not(
    angle, shift,
):
    """A transverse candidate has physical wall-band extent even at one station.

    Rejecting its aperture alignment must not erase that station from the
    complete unresolved source universe. Mere outer-band tangency does not
    cross the physical wall interior and must not suppress a valid gap.
    """
    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    left = ApertureHostCandidateInput(
        "left", tr((20.0, 0.0)), tr((30.0, 0.0)),
    )
    right = ApertureHostCandidateInput(
        "right", tr((40.0, 0.0)), tr((50.0, 0.0)),
    )
    through_band = ApertureHostCandidateInput(
        "unresolved", tr((35.0, -15.0)), tr((35.0, 15.0)),
    )
    outer_tangent = ApertureHostCandidateInput(
        "unresolved", tr((35.0, 12.5)), tr((35.0, 16.0)),
    )
    authority = _authority()
    for rejected, expected_piers in ((through_band, 0), (outer_tangent, 1)):
        original = (left.start_pt, left.end_pt, right.start_pt, right.end_pt,
                    rejected.start_pt, rejected.end_pt)
        canonical = None
        for openings in ((left, rejected, right), (right, left, rejected)):
            records, piers = authority.bind_openings_to_through_wall(
                through_wall=wall, openings=openings,
            )
            by_id = {record.physical_opening_id: record for record in records}
            assert set(by_id) == {"left", "right", "unresolved"}
            assert by_id["unresolved"].status is S.ABSTAINED
            assert by_id["unresolved"].first_remaining_gate == (
                "aperture_wall_axis_misaligned"
            )
            assert by_id["left"].status is S.CANDIDATE
            assert by_id["right"].status is S.CANDIDATE
            assert len(piers) == expected_piers
            assert all(pier.status is S.CANDIDATE
                       and pier.is_structural_masonry_pier is None for pier in piers)
            assert all(record.shadow_only and not record.takeoff_eligible
                       and not record.commercial_projection_allowed
                       for record in records)
            evidence = (
                {key: record.to_dict() for key, record in by_id.items()},
                piers,
            )
            if canonical is None:
                canonical = evidence
            else:
                assert evidence == canonical
            assert authority.bind_openings_to_through_wall(
                through_wall=wall, openings=openings,
            ) == (records, piers)
        assert original == (left.start_pt, left.end_pt, right.start_pt,
                            right.end_pt, rejected.start_pt, rejected.end_pt)


def test_terminal_jamb_reference_universe_fails_closed_at_existing_work_cap():
    # The geometric universe is only one host plus three apertures. Its
    # independent source-observation universe must not grow without bound.
    observations = tuple(f"jamb-ref-{i:05d}" for i in range(20_001))
    with pytest.raises(ValueError, match="terminal_jamb_observation_ids"):
        ApertureHostCandidateInput(
            "oversized", (10.0, 0.0), (20.0, 0.0), observations,
        )

    wall = ContinuousThroughWallCandidate(
        "host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    left = ApertureHostCandidateInput(
        "left", (10.0, 0.0), (20.0, 0.0), observations[:10_000],
    )
    right = ApertureHostCandidateInput(
        "right", (40.0, 0.0), (50.0, 0.0), observations[10_000:20_000],
    )
    extra = ApertureHostCandidateInput(
        "extra", (70.0, 0.0), (80.0, 0.0), observations[20_000:],
    )
    authority = _authority()
    first, first_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(left, right),
    )
    second, second_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(left, right),
    )
    assert (first, first_piers) == (second, second_piers)
    assert len(first) == 2 and len(first_piers) == 1
    assert all(record.status is S.CANDIDATE for record in first)
    assert all(record.shadow_only and not record.takeoff_eligible
               and not record.commercial_projection_allowed for record in first)
    assert first_piers[0].is_structural_masonry_pier is None
    for candidate_order in ((left, right, extra), (extra, right, left)):
        with pytest.raises(
            ValueError, match="terminal_jamb_observation_reference_limit_exceeded",
        ):
            authority.bind_openings_to_through_wall(
                through_wall=wall, openings=candidate_order,
            )
    assert len(observations) == 20_001
    assert len(left.terminal_jamb_observation_ids) == 10_000
    assert len(right.terminal_jamb_observation_ids) == 10_000


def test_public_frozen_host_and_pier_records_cannot_be_replaced_with_authority():
    """A direct dataclass replacement must not bypass the source-neutral issuer fence."""
    from dataclasses import replace

    wall = ContinuousThroughWallCandidate(
        "typed-host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("A", (20.0, 0.0), (40.0, 0.0)),
        ApertureHostCandidateInput("B", (50.0, 0.0), (70.0, 0.0)),
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(records) == 2 and len(piers) == 1
    host, pier = records[0], piers[0]
    assert replace(host) == host and replace(pier) == pier
    for changes in (
        {"commercial_projection_allowed": True},
        {"commercial_projection_allowed": 1},
        {"takeoff_eligible": True},
        {"shadow_only": False},
        {"status": S.CORROBORATED},
        {"status": "candidate"},
    ):
        with pytest.raises(ValueError, match="cannot grant commercial or source authority"):
            replace(host, **changes)
    for changes in (
        {"first_remaining_gate": "none"},
        {"first_remaining_gate": ""},
        {"first_remaining_gate": "caller_asserted_source_verified"},
    ):
        with pytest.raises(ValueError, match="requires unresolved source authority gate"):
            replace(host, **changes)
    for changes in (
        {"is_structural_masonry_pier": True},
        {"is_structural_masonry_pier": False},
        {"status": S.CORROBORATED},
        {"status": S.ABSTAINED},
        {"first_remaining_gate": "none"},
    ):
        with pytest.raises(ValueError, match="cannot assert structural source authority"):
            replace(pier, **changes)

    # Ordinary abstentions still carry their first failing geometry gate,
    # and neither candidate nor abstained output can enter commercial takeoff.
    rejected = ApertureHostCandidateInput("off-band", (20.0, 30.0), (40.0, 30.0))
    abstained, no_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(rejected,),
    )
    assert no_piers == ()
    assert abstained[0].status is S.ABSTAINED
    assert abstained[0].first_remaining_gate == "aperture_outside_host_wall_band"
    assert replace(abstained[0]) == abstained[0]
    for record in (*records, *abstained):
        assert record.shadow_only is True
        assert record.takeoff_eligible is False
        assert record.commercial_projection_allowed is False
    assert pier.is_structural_masonry_pier is None
    assert pier.status is S.CANDIDATE
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings[::-1],
    ) == (tuple(reversed(records)), piers)


def test_public_through_wall_numeric_record_replacements_fail_closed():
    from dataclasses import replace

    wall = ContinuousThroughWallCandidate(
        "host-numeric", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("left", (10.0, 0.0), (30.0, 0.0)),
        ApertureHostCandidateInput("right", (40.0, 0.0), (60.0, 0.0)),
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(records) == 2 and len(piers) == 1
    host, pier = records[0], piers[0]
    assert replace(host) == host and replace(pier) == pier
    for field in ("pier_start_station", "pier_end_station", "pier_width_pt"):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(pier, **{field: bad})
    for changes in (
        {"pier_width_pt": -1.0},
        {"pier_end_station": pier.pier_start_station},
        {"pier_width_pt": pier.pier_width_pt + 1.0},
    ):
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(pier, **changes)
    for field in ("u0_pt", "u1_pt", "whole_wall_length_pt", "wall_thickness_pt"):
        for bad in (float("nan"), float("inf")):
            with pytest.raises(ValueError, match="numeric evidence"):
                replace(host, **{field: bad})
    for changes in (
        {"u0_pt": host.u1_pt + 1.0},
        {"whole_wall_length_pt": 0.0},
        {"wall_thickness_pt": -1.0},
        {"opening_start_pt": (float("nan"), 0.0)},
        {"origin_pt": (float(2**53) + 2.0, 0.0)},
        {"axis_unit": (float("inf"), 0.0)},
        {"normal_unit": (2.0, 0.0)},
    ):
        with pytest.raises(ValueError, match="numeric evidence"):
            replace(host, **changes)
    with pytest.raises(ValueError, match="evidence references"):
        replace(host, terminal_jamb_observation_ids=("duplicate", "duplicate"))
    rejected = ApertureHostCandidateInput(
        "off-band", (20.0, 30.0), (40.0, 30.0),
    )
    abstained, no_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(rejected,),
    )
    assert no_piers == () and abstained[0].status is S.ABSTAINED
    assert replace(abstained[0]) == abstained[0]
    assert all(not r.takeoff_eligible and not r.commercial_projection_allowed
               and r.shadow_only for r in (*records, *abstained))
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings[::-1],
    )[1] == piers


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 3.0, (250.0, -130.0)),
    (math.pi / 2.0, (-100.0, 300.0)),
    (math.pi, (300.0, -100.0)),
])
def test_public_host_frame_replacement_requires_oriented_orthonormal_basis(angle, shift):
    """A frozen shadow record cannot be forged with a nonphysical wall frame."""
    from dataclasses import replace

    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "rotated-host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    valid = ApertureHostCandidateInput(
        "valid", tr((20.0, 0.0)), tr((40.0, 0.0)),
    )
    rejected = ApertureHostCandidateInput(
        "off-band", tr((20.0, 30.0)), tr((40.0, 30.0)),
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(valid, rejected),
    )
    assert not piers
    assert records[0].status is S.CANDIDATE
    assert records[1].status is S.ABSTAINED
    for record in records:
        assert replace(record) == record
        assert math.isclose(math.hypot(*record.axis_unit), 1.0, abs_tol=1e-12)
        assert math.isclose(math.hypot(*record.normal_unit), 1.0, abs_tol=1e-12)
        assert not record.takeoff_eligible and not record.commercial_projection_allowed
        assert record.shadow_only
        ax, ay = record.axis_unit
        nx, ny = record.normal_unit
        for changes in (
            {"axis_unit": (0.0, 0.0)},
            {"axis_unit": (0.5, 0.0)},
            {"axis_unit": (1.0, 1.0)},
            {"axis_unit": (nx, ny)},  # unit but parallel to the original normal
            {"normal_unit": (0.0, 0.0)},
            {"normal_unit": (0.5, 0.5)},
            {"normal_unit": (ax, ay)},  # unit but parallel to axis
            {"normal_unit": (-nx, -ny)},  # unit but opposite orientation
        ):
            with pytest.raises(ValueError, match="numeric evidence|orthonormal"):
                replace(record, **changes)
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(valid, rejected),
    ) == (records, piers)


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 3.0, (250.0, -130.0)),
    (math.pi, (-400.0, 700.0)),
])
def test_frozen_host_station_identity_rejects_finite_forged_intervals(angle, shift):
    """Direct record replacement cannot move a physical jamb along its host."""
    from dataclasses import replace

    tr = lambda p: _rotated(p, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "station-host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("valid", tr((20.0, 0.0)), tr((40.0, 0.0))),
        ApertureHostCandidateInput("off-band", tr((60.0, 30.0)), tr((70.0, 30.0))),
        ApertureHostCandidateInput("out-of-extent", tr((95.0, 0.0)), tr((110.0, 0.0))),
        ApertureHostCandidateInput("clipped", tr((-1.0, 0.0)), tr((10.0, 0.0))),
    )
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    )
    assert len(records) == 4
    assert records[0].status is S.CANDIDATE
    assert records[1].status is S.ABSTAINED
    assert records[2].status is S.ABSTAINED
    assert records[3].status is S.CANDIDATE
    assert records[3].u0_pt == 0.0
    assert records[2].u1_pt > records[2].whole_wall_length_pt
    for record in records:
        assert replace(record) == record
        ax, ay = record.axis_unit
        x, y = record.opening_start_pt
        ox, oy = record.origin_pt
        for changes in (
            {"u0_pt": record.u0_pt + 1.0},
            {"u1_pt": record.u1_pt + 1.0},
            {"opening_start_pt": (x + 3.0 * ax, y + 3.0 * ay)},
            {"origin_pt": (ox + 2.0 * ax, oy + 2.0 * ay)},
        ):
            # The earlier geometry veto may reject before station-identity validation.
            with pytest.raises(ValueError, match="owned jamb stations|first failing gate"):
                replace(record, **changes)
        assert not record.commercial_projection_allowed
        assert not record.takeoff_eligible
        assert record.shadow_only
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings,
    ) == (records, piers)
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=tuple(reversed(openings)),
    )[0] == tuple(reversed(records))


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 3.0, (250.0, -130.0)),
    (math.pi / 2.0, (-100.0, 300.0)),
])
def test_frozen_candidate_rechecks_normal_band_alignment_and_exact_snap_receipt(angle, shift):
    """Frozen shadow host cannot inherit valid stations from a displaced jamb."""
    from dataclasses import replace

    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "normal-band-host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    openings = (
        ApertureHostCandidateInput("valid", tr((20.0, 0.0)), tr((40.0, 0.0))),
        ApertureHostCandidateInput("off-band", tr((60.0, 30.0)), tr((70.0, 30.0))),
        ApertureHostCandidateInput("misaligned", tr((75.0, 0.0)), tr((75.0, 5.0))),
        ApertureHostCandidateInput("clipped", tr((-0.25, 0.0)), tr((10.0, 0.0))),
    )
    authority = _authority()
    original = (wall, openings)
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings, snap_tolerance_pt=0.5,
    )
    assert [r.status for r in records] == [
        S.CANDIDATE, S.ABSTAINED, S.ABSTAINED, S.CANDIDATE,
    ]
    host, rejected_band, rejected_angle, clipped = records
    assert host.snap_tolerance_pt == 0.5
    assert host.to_dict()["snap_tolerance_pt"] == 0.5
    assert clipped.u0_pt == 0.0
    assert all(r.snap_tolerance_pt == 0.5 for r in records)
    assert replace(host) == host
    assert replace(rejected_band) == rejected_band
    assert replace(rejected_angle) == rejected_angle
    assert replace(clipped) == clipped

    nx, ny = host.normal_unit

    def move(point, offset):
        return (point[0] + nx * offset, point[1] + ny * offset)

    # Normal translations preserve the along-axis station identity, which
    # alone is insufficient to establish physical wall-band membership.
    for changes in (
        {"opening_start_pt": move(host.opening_start_pt, 30.0),
         "opening_end_pt": move(host.opening_end_pt, 30.0)},
        {"opening_start_pt": move(host.opening_start_pt, 30.0)},
        {"origin_pt": move(host.origin_pt, 30.0)},
        # 2pt at one jamb is within the 10.5pt wall band but exceeds
        # the existing angular-alignment gate for a 20pt aperture.
        {"opening_end_pt": move(host.opening_end_pt, 2.0)},
    ):
        with pytest.raises(ValueError, match="candidate host geometry|owned jamb stations"):
            replace(host, **changes)
    for invalid_snap in (float("nan"), float("inf"), -1.0, 2.50001, True):
        with pytest.raises(ValueError, match="host numeric evidence"):
            replace(host, snap_tolerance_pt=invalid_snap)

    # Preserve source-neutral rejected geometry and complete original input
    # evidence; never reinterpret an ABSTAINED aperture as a proven host.
    assert rejected_band.first_remaining_gate == "aperture_outside_host_wall_band"
    assert rejected_angle.first_remaining_gate == "aperture_wall_axis_misaligned"
    assert (wall, openings) == original
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=openings, snap_tolerance_pt=0.5,
    ) == (records, piers)
    reversed_records, reversed_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=tuple(reversed(openings)), snap_tolerance_pt=0.5,
    )
    assert reversed_records == tuple(reversed(records))
    assert reversed_piers == piers
    assert all(r.shadow_only and not r.takeoff_eligible
               and not r.commercial_projection_allowed for r in records)


def test_frozen_host_identity_refuses_jointly_valid_snap_and_jamb_replacement():
    """A geometrically valid new observation must never inherit the old host ID."""
    from dataclasses import replace

    wall = ContinuousThroughWallCandidate(
        "receipt-host", (0.0, 0.0), (100.0, 0.0), 20.0,
    )
    original_opening = ApertureHostCandidateInput(
        "receipt-opening", (20.0, 0.0), (40.0, 0.0),
        ("jamb-left", "jamb-right"),
    )
    authority = _authority()
    baseline, baseline_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(original_opening,),
        snap_tolerance_pt=0.5,
    )
    assert baseline_piers == ()
    host = baseline[0]
    assert host.status is S.CANDIDATE
    assert replace(host) == host
    assert host.host_start_pt == wall.start_pt
    assert host.host_end_pt == wall.end_pt
    assert host.document_id and host.revision_id and host.source_sha256

    # Both modified records are still perfectly valid geometric candidates:
    # a 0.25pt transverse move remains inside the wall band and 2.5pt cap.
    # The old source-bound stable ID must NOT survive their joint replacement.
    with pytest.raises(ValueError, match="host stable identity"):
        replace(
            host, snap_tolerance_pt=2.5,
            opening_start_pt=(20.0, 0.25),
            opening_end_pt=(40.0, 0.25),
        )
    with pytest.raises(ValueError, match="host stable identity"):
        replace(host, snap_tolerance_pt=2.5)
    with pytest.raises(ValueError, match="host stable identity"):
        replace(host, wall_thickness_pt=22.0)
    with pytest.raises(ValueError, match="host stable identity"):
        replace(host, document_id="different-document")
    with pytest.raises(ValueError, match="host stable identity"):
        replace(host, revision_id="different-revision")
    with pytest.raises(ValueError, match="host stable identity"):
        replace(host, source_sha256="different-source")
    with pytest.raises(ValueError, match="host stable identity"):
        replace(host, adjacent_pier_ids=("forged-pier",))
    with pytest.raises(ValueError, match="host stable identity"):
        replace(
            host, host_end_pt=(120.0, 0.0),
            whole_wall_length_pt=120.0,
        )
    with pytest.raises(ValueError, match="owned wall frame"):
        replace(host, host_start_pt=(1.0, 0.0))
    for bad in ("", " padded ", 17, None):
        with pytest.raises(ValueError, match="host source identity receipt"):
            replace(host, document_id=bad)

    alternative, alternative_piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(original_opening,),
        snap_tolerance_pt=2.5,
    )
    assert alternative_piers == ()
    assert alternative[0].status is S.CANDIDATE
    assert alternative[0].hosting_record_id != host.hosting_record_id
    assert replace(alternative[0]) == alternative[0]
    assert (host.snap_tolerance_pt, host.opening_start_pt) == (0.5, (20.0, 0.0))
    assert authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(original_opening,),
        snap_tolerance_pt=0.5,
    ) == (baseline, baseline_piers)
    assert all(r.shadow_only and not r.takeoff_eligible
               and not r.commercial_projection_allowed for r in (*baseline, *alternative))


@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 3.0, (250.0, -130.0)),
    (math.pi, (-200.0, 300.0)),
])
def test_frozen_host_source_geometry_receipt_rotates_without_id_drift(angle, shift):
    from dataclasses import replace

    tr = lambda point: _rotated(point, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "receipt-rotated", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    opening = ApertureHostCandidateInput(
        "receipt-rotated-opening", tr((20.0, 0.0)), tr((40.0, 0.0)),
    )
    authority = _authority()
    first = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    second = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(opening,),
    )
    assert first == second
    assert first[1] == ()
    assert first[0][0].status is S.CANDIDATE
    assert replace(first[0][0]) == first[0][0]
    assert first[0][0].host_start_pt == wall.start_pt
    assert first[0][0].host_end_pt == wall.end_pt
    assert not first[0][0].takeoff_eligible
    assert not first[0][0].commercial_projection_allowed

@pytest.mark.parametrize("angle,shift", [
    (0.0, (0.0, 0.0)),
    (math.pi / 2.0, (250.0, -120.0)),
    (math.pi / 3.0, (-300.0, 80.0)),
])
def test_frozen_pier_source_and_jamb_receipt_refuses_stale_identity(angle, shift):
    """A jointly coherent new pier gap cannot inherit the previous source-bound ID."""
    from dataclasses import replace

    tr = lambda p: _rotated(p, angle, shift)
    wall = ContinuousThroughWallCandidate(
        "pier-host", tr((0.0, 0.0)), tr((100.0, 0.0)), 20.0,
    )
    left = ApertureHostCandidateInput(
        "pier-left", tr((10.0, 0.0)), tr((30.0, 0.0)),
        ("left-jamb-a", "left-jamb-b"),
    )
    right = ApertureHostCandidateInput(
        "pier-right", tr((45.0, 0.0)), tr((65.0, 0.0)),
        ("right-jamb-a", "right-jamb-b"),
    )
    original = (wall, left, right)
    authority = _authority()
    records, piers = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(left, right),
    )
    assert len(piers) == 1
    pier = piers[0]
    assert pier.status is S.CANDIDATE
    assert pier.is_structural_masonry_pier is None
    assert replace(pier) == pier
    assert pier.document_id == "synthetic"
    assert pier.host_start_pt == wall.start_pt
    assert pier.host_end_pt == wall.end_pt
    assert pier.left_jamb_observations == left.terminal_jamb_observation_ids
    assert pier.right_jamb_observations == right.terminal_jamb_observation_ids
    with pytest.raises(ValueError, match="owned jamb stations"):
        replace(pier, pier_start_station=pier.pier_start_station + 1.0,
                pier_end_station=pier.pier_end_station + 1.0)
    with pytest.raises(ValueError, match="owned jamb stations"):
        replace(pier, pier_start_station=pier.pier_start_station + 1.0,
                pier_width_pt=pier.pier_width_pt - 1.0)

    # Both modified jamb and matching gap are geometric candidates, but
    # their original-source-neutral identity must differ.
    new_left = tuple(sorted((tr((11.0, 0.0)), tr((31.0, 0.0)))))
    ax, ay = wall.axis_unit
    new_start = max(
        (p[0] - wall.start_pt[0]) * ax + (p[1] - wall.start_pt[1]) * ay
        for p in new_left
    )
    with pytest.raises(ValueError, match="pier stable identity"):
        replace(pier, left_jamb_endpoints=new_left,
                pier_start_station=new_start,
                pier_width_pt=pier.pier_end_station - new_start)
    for changes in (
        {"left_opening_id": "different-opening"},
        {"right_opening_id": "different-opening"},
        {"document_id": "different-document"},
        {"revision_id": "different-revision"},
        {"source_sha256": "different-source"},
        {"host_wall_id": "different-wall"},
        {"host_thickness_pt": 22.0},
        {"left_jamb_observations": ("new-left-jamb",)},
        {"right_jamb_observations": ("new-right-jamb",)},
    ):
        with pytest.raises(ValueError, match="pier stable identity"):
            replace(pier, **changes)
    for bad in ("", " padded ", None, 123):
        with pytest.raises(ValueError, match="pier source identity"):
            replace(pier, document_id=bad)
    for bad in (float("nan"), float("inf"), True):
        with pytest.raises(ValueError, match="pier host geometry"):
            replace(pier, host_thickness_pt=bad)
    with pytest.raises(ValueError, match="pier jamb geometry"):
        replace(pier, left_jamb_endpoints=((0.0, 0.0), (float("nan"), 0.0)))
    with pytest.raises(ValueError, match="pier jamb observation"):
        replace(pier, left_jamb_observations=("duplicate", "duplicate"))

    again = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(left, right),
    )
    reversed_order = authority.bind_openings_to_through_wall(
        through_wall=wall, openings=(right, left),
    )
    assert again == (records, piers)
    assert reversed_order == (tuple(reversed(records)), piers)
    assert (wall, left, right) == original
    assert all(r.shadow_only and not r.takeoff_eligible
               and not r.commercial_projection_allowed for r in records)
