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
    assert first[0].status is S.CORROBORATED
    assert first[0].first_remaining_gate == "none"
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
    assert allowed[0].status is S.CORROBORATED


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
    assert records[0].status is S.CORROBORATED and not piers


def test_valid_transverse_obstruction_still_vetoes_host_and_unrelated_wall_does_not():
    wall = ContinuousThroughWallCandidate("host", (0.0, 0.0), (100.0, 0.0), 20.0)
    opening = ApertureHostCandidateInput("opening", (20.0, 0.0), (80.0, 0.0))
    authority = _authority()
    crossed = ((50.0, -30.0), (50.0, 30.0))
    unrelated = ((90.0, -30.0), (90.0, 30.0))
    for segment, expected_status, expected_gate in (
        (crossed, S.ABSTAINED, "host_through_wall_obstructed"),
        (unrelated, S.CORROBORATED, "none"),
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
    (((10.0, 30.0), (90.0, 40.0)), S.CORROBORATED),  # above wall band
    (((85.0, -30.0), (95.0, 30.0)), S.CORROBORATED),  # outside opening
    (((22.5, -30.0), (22.5, 30.0)), S.CORROBORATED),  # touches excluded edge only
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
        "host_through_wall_obstructed" if expected_status is S.ABSTAINED else "none"
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
    assert by_id["left"].status is S.CORROBORATED
    assert by_id["right"].status is S.CORROBORATED
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
    assert all(r.status is S.CORROBORATED for r in records)
    assert all(r.first_remaining_gate == "none" for r in records)
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
        assert all(r.status is S.CORROBORATED for r in records)
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
    assert records[0].status is S.CORROBORATED
    assert records[0].first_remaining_gate == "none"
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
        assert by_id["A"].status is S.CORROBORATED
        assert by_id["B"].status is S.CORROBORATED
        assert len(piers) == 1
        assert (piers[0].left_opening_id, piers[0].right_opening_id) == ("A", "B")
        assert "outside" not in (piers[0].left_opening_id, piers[0].right_opening_id)
