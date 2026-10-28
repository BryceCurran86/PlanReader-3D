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
