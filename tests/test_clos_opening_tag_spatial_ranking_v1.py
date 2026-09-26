"""Adversarial tests for pb_clos_opening_tag_spatial_ranking.py (Item 35
Phase A / part of Phase G).

Reuses make_candidate / make_tag_obs from the existing #539 opening-
candidate-authority test suite for consistent fixture conventions. All
geometry here is synthetic -- no project coordinates, no expected counts.
"""
from __future__ import annotations

import math

import pytest

from pb_clos_opening_tag_spatial_ranking import (
    CLOSVisibilityState,
    WallSegment,
    clos_passing_tag_observations,
    has_line_of_sight,
    rank_clos_candidates,
)
from pb_source_opening_candidate_authority import (
    IdentityState,
    OpeningIdentityResolver,
)
from tests.test_source_opening_universe_evidence_v1 import make_candidate, make_tag_obs


# ---------------------------------------------------------------------------
# Core geometry: segment intersection / line of sight
# ---------------------------------------------------------------------------


def test_line_of_sight_clear_with_no_walls() -> None:
    visible, blockers = has_line_of_sight((0, 0), (100, 0), [], frozenset())
    assert visible is True
    assert blockers == ()


def test_line_of_sight_blocked_by_crossing_wall() -> None:
    wall = WallSegment("w1", (50, -50), (50, 50))
    visible, blockers = has_line_of_sight((0, 0), (100, 0), [wall], frozenset())
    assert visible is False
    assert blockers == ("w1",)


def test_line_of_sight_not_blocked_by_parallel_non_crossing_wall() -> None:
    wall = WallSegment("w1", (0, 100), (100, 100))
    visible, blockers = has_line_of_sight((0, 0), (100, 0), [wall], frozenset())
    assert visible is True
    assert blockers == ()


def test_line_of_sight_ignores_candidates_own_host_wall() -> None:
    """A door aperture is a break IN its host wall -- the anchor-to-tag
    line will often cross that same wall's run near the break. That must
    not count as an obstruction."""
    host_wall = WallSegment("host", (50, -50), (50, 50))
    visible, blockers = has_line_of_sight((0, 0), (100, 0), [host_wall], frozenset({"host"}))
    assert visible is True
    assert blockers == ()


def test_line_of_sight_blocked_by_other_wall_even_when_host_wall_also_present() -> None:
    host_wall = WallSegment("host", (50, -50), (50, 50))
    other_wall = WallSegment("other", (75, -50), (75, 50))
    visible, blockers = has_line_of_sight(
        (0, 0), (100, 0), [host_wall, other_wall], frozenset({"host"})
    )
    assert visible is False
    assert blockers == ("other",)


# ---------------------------------------------------------------------------
# Phase G #1: OCR tag in Room A visible but nearest aperture is in Room B
# ---------------------------------------------------------------------------


def test_geometrically_nearer_tag_across_a_wall_ranks_below_a_farther_visible_one() -> None:
    """A tag physically closer to the candidate opening, but on the far
    side of an intervening wall (a different room), must not out-rank a
    farther tag that genuinely has clear line of sight. This is the exact
    failure mode a pure nearest-distance rule cannot avoid.

    Geometry: the "wrong room" tag sits up and across a horizontal dividing
    wall (its straight-line path from the candidate crosses that wall);
    the "correct room" tag sits farther away but along the candidate's own
    row, y=0, where the dividing wall (which only spans a limited x-range
    at y=15) is never crossed.
    """
    candidate = make_candidate(geometry=(0.0, -5.0, 10.0, 5.0))  # centered at (5, 0)
    near_wrong_room_tag = make_tag_obs(
        observation_id="tag_near_wrong_room", center=(20.0, 30.0)
    )
    far_correct_room_tag = make_tag_obs(
        observation_id="tag_far_correct_room", center=(80.0, 0.0)
    )
    blocking_wall = WallSegment("dividing_wall", (5.0, 15.0), (30.0, 15.0))

    ranked = rank_clos_candidates(
        candidate,
        [near_wrong_room_tag, far_correct_room_tag],
        [blocking_wall],
        frozenset(),
    )
    by_id = {r.tag_observation_id: r for r in ranked}
    assert by_id["tag_near_wrong_room"].state == CLOSVisibilityState.NOT_VISIBLE
    assert by_id["tag_far_correct_room"].state == CLOSVisibilityState.POSSIBLE_BINDING

    passing = clos_passing_tag_observations(
        candidate, [near_wrong_room_tag, far_correct_room_tag], [blocking_wall], frozenset()
    )
    assert [t.observation_id for t in passing] == ["tag_far_correct_room"]


# ---------------------------------------------------------------------------
# Phase G #2: clear CLOS but no explicit identity relation -> candidate
# only, never PROVEN_SAME. Integration with the real, unmodified resolver.
# ---------------------------------------------------------------------------


def test_clos_pass_alone_never_becomes_proven_same_without_relation_evidence() -> None:
    candidate = make_candidate(
        revision_id="rev_clos_1",
        source_sha256="b" * 64,
        snapshot_id="snap_clos_1",
        geometry=(0.0, -5.0, 10.0, 5.0),
    )
    tag = make_tag_obs(
        observation_id="tag_clos_only",
        tag_text="D1",
        center=(30.0, 0.0),
        revision_id="rev_clos_1",
        source_sha256="b" * 64,
        snapshot_id="snap_clos_1",
    )
    passing = clos_passing_tag_observations(candidate, [tag], [], frozenset())
    assert [t.observation_id for t in passing] == ["tag_clos_only"]

    # Hand the CLOS-passing tag straight to the REAL, unmodified resolver
    # with no binding_evidences at all -- CLOS visibility must not be
    # mistaken for the typed relation evidence identity actually requires.
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=passing,
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag != "D1"


# ---------------------------------------------------------------------------
# Phase G #3: two equally plausible apertures -> ambiguity surfaced, not
# forced to a single winner by CLOS itself.
# ---------------------------------------------------------------------------


def test_two_equally_visible_candidates_for_one_tag_both_report_possible_binding() -> None:
    """CLOS is evaluated per-candidate. When the same tag is genuinely
    visible to two different candidates, CLOS must report POSSIBLE_BINDING
    for both independently -- it must not silently award the tag to
    whichever candidate happens to be nearer, since that would be exactly
    the Hungarian/nearest-neighbour-as-identity pattern this module exists
    to avoid. Arbitration (if any) belongs to a later, explicit-evidence
    stage, not to this ranking layer."""
    tag = make_tag_obs(observation_id="ambiguous_tag", center=(50.0, 0.0))
    candidate_a = make_candidate(geometry=(0.0, -5.0, 10.0, 5.0))  # center (5, 0), dist 45
    candidate_b = make_candidate(geometry=(80.0, -5.0, 90.0, 5.0))  # center (85, 0), dist 35

    passing_a = clos_passing_tag_observations(candidate_a, [tag], [], frozenset())
    passing_b = clos_passing_tag_observations(candidate_b, [tag], [], frozenset())

    assert [t.observation_id for t in passing_a] == ["ambiguous_tag"]
    assert [t.observation_id for t in passing_b] == ["ambiguous_tag"]


def test_multiple_clos_passing_tags_are_all_returned_ranked_not_truncated_to_one() -> None:
    candidate = make_candidate(geometry=(0.0, -5.0, 10.0, 5.0))
    near = make_tag_obs(observation_id="near", center=(20.0, 0.0))
    far = make_tag_obs(observation_id="far", center=(60.0, 0.0))

    ranked = rank_clos_candidates(candidate, [far, near], [], frozenset())
    assert [r.tag_observation_id for r in ranked] == ["near", "far"]
    assert all(r.state == CLOSVisibilityState.POSSIBLE_BINDING for r in ranked)


# ---------------------------------------------------------------------------
# Distance is only computed/compared for visibility-passing tags
# ---------------------------------------------------------------------------


def test_blocked_tag_never_wins_on_distance_alone() -> None:
    """A very close but blocked tag must never rank ahead of, or replace,
    a farther visible one -- distance is not consulted for blocked tags
    at all. The farther tag sits in the opposite direction (negative x)
    from the wall, so its path never approaches the wall's x-position at
    all -- distinct from merely being farther along the same ray."""
    candidate = make_candidate(geometry=(0.0, -5.0, 10.0, 5.0))
    very_close_blocked = make_tag_obs(observation_id="close_blocked", center=(6.0, 0.0))
    farther_visible = make_tag_obs(observation_id="far_visible", center=(-60.0, 0.0))
    wall = WallSegment("blocker", (5.5, -20.0), (5.5, 20.0))

    passing = clos_passing_tag_observations(
        candidate, [very_close_blocked, farther_visible], [wall], frozenset()
    )
    assert [t.observation_id for t in passing] == ["far_visible"]
