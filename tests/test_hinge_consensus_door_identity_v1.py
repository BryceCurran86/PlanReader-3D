"""Adversarial/generic tests for pb_hinge_consensus_door_identity.

Every fixture here is synthetic, parametrically generated geometry --
no project coordinates, no expected door counts, nothing derived from or
checked against Murera or any other benchmark project. These tests exist
to validate the *method* (hinge/radius consensus) generically before it
is ever pointed at a real source page.
"""
from __future__ import annotations

import numpy as np
import pytest

from pb_hinge_consensus_door_identity import (
    IdentityState,
    fit_circle_algebraic,
    fit_circle_ransac,
    group_fragments_by_hinge_consensus,
    make_fragment,
    resolve_pair_identity,
)

_RNG = np.random.default_rng(42)


def _arc_points(
    cx: float,
    cy: float,
    r: float,
    theta_start_deg: float,
    theta_end_deg: float,
    n: int = 60,
    noise_std: float = 0.0,
) -> np.ndarray:
    thetas = np.radians(np.linspace(theta_start_deg, theta_end_deg, n))
    x = cx + r * np.cos(thetas)
    y = cy + r * np.sin(thetas)
    if noise_std:
        x = x + _RNG.normal(0, noise_std, size=n)
        y = y + _RNG.normal(0, noise_std, size=n)
    return np.column_stack([x, y])


# ---------------------------------------------------------------------------
# Circle fitting primitives
# ---------------------------------------------------------------------------


def test_algebraic_fit_recovers_known_circle() -> None:
    pts = _arc_points(100.0, 200.0, 40.0, 10.0, 170.0)
    fit = fit_circle_algebraic(pts)
    assert fit is not None
    assert fit.cx == pytest.approx(100.0, abs=0.5)
    assert fit.cy == pytest.approx(200.0, abs=0.5)
    assert fit.r == pytest.approx(40.0, abs=0.5)


def test_ransac_fit_robust_to_outlier_points() -> None:
    pts = _arc_points(0.0, 0.0, 50.0, 0.0, 150.0, n=40)
    outliers = np.array([[500.0, 500.0], [-300.0, 200.0], [0.0, -900.0]])
    pts_with_outliers = np.concatenate([pts, outliers])
    fit = fit_circle_ransac(pts_with_outliers)
    assert fit is not None
    assert fit.cx == pytest.approx(0.0, abs=2.0)
    assert fit.cy == pytest.approx(0.0, abs=2.0)
    assert fit.r == pytest.approx(50.0, abs=2.0)


# ---------------------------------------------------------------------------
# Case 1: clean single swing (one fragment) -- trivially its own group
# ---------------------------------------------------------------------------


def test_clean_single_swing_is_one_group() -> None:
    frag = make_fragment("f1", _arc_points(0, 0, 45, 0, 90))
    groups = group_fragments_by_hinge_consensus([frag])
    assert len(groups) == 1
    assert groups[0].fragment_ids == ("f1",)


# ---------------------------------------------------------------------------
# Case 2: one swing split into 2 fragments -> PROVEN_SAME, one group
# ---------------------------------------------------------------------------


def test_one_swing_split_into_two_fragments_merges() -> None:
    a = make_fragment("a", _arc_points(50, 50, 40, 0, 40))
    b = make_fragment("b", _arc_points(50, 50, 40, 45, 90))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_SAME

    groups = group_fragments_by_hinge_consensus([a, b])
    assert len(groups) == 1
    assert set(groups[0].fragment_ids) == {"a", "b"}
    assert groups[0].identity_state == IdentityState.PROVEN_SAME
    assert groups[0].hinge is not None
    assert groups[0].hinge[0] == pytest.approx(50, abs=3)
    assert groups[0].hinge[1] == pytest.approx(50, abs=3)


# ---------------------------------------------------------------------------
# Case 3: one swing split into 4+ fragments -> still merges to one group
# ---------------------------------------------------------------------------


def test_one_swing_split_into_four_fragments_merges() -> None:
    hinge = (10.0, -20.0)
    r = 60.0
    spans = [(0, 20), (25, 45), (50, 70), (75, 90)]
    frags = [
        make_fragment(f"p{i}", _arc_points(hinge[0], hinge[1], r, s0, s1))
        for i, (s0, s1) in enumerate(spans)
    ]
    groups = group_fragments_by_hinge_consensus(frags)
    assert len(groups) == 1
    assert len(groups[0].fragment_ids) == 4
    assert groups[0].identity_state == IdentityState.PROVEN_SAME


# ---------------------------------------------------------------------------
# Case 4: two doors close together -> stay PROVEN_DISTINCT / two groups
# ---------------------------------------------------------------------------


def test_two_separate_doors_close_together_stay_distinct() -> None:
    # Two independent swings with different hinge centers, positioned close
    # in absolute space -- this is the exact failure mode that made raw
    # spatial-proximity clustering unsafe on the real source page (a
    # genuinely-separate-door pair had SMALLER nearest-point distance than
    # a genuinely-same-door fragment pair).
    door_a = make_fragment("door_a", _arc_points(0.0, 0.0, 35.0, 0.0, 90.0))
    door_b = make_fragment("door_b", _arc_points(40.0, 0.0, 35.0, 90.0, 180.0))
    # Confirm they really are spatially close (nearest points), to prove
    # this is a genuine proximity trap and not a strawman.
    nearest = min(
        np.hypot(px - qx, py - qy)
        for px, py in door_a.points
        for qx, qy in door_b.points
    )
    assert nearest < 10.0, "fixture must be a genuine close-proximity trap"

    result = resolve_pair_identity(door_a, door_b)
    assert result.identity_state == IdentityState.PROVEN_DISTINCT

    groups = group_fragments_by_hinge_consensus([door_a, door_b])
    assert len(groups) == 2
    assert {g.identity_state for g in groups} == {IdentityState.PROVEN_DISTINCT}


def test_opposing_adjacent_doors_across_corridor_stay_distinct() -> None:
    door_a = make_fragment("left", _arc_points(0.0, 0.0, 40.0, -45.0, 45.0))
    door_b = make_fragment("right", _arc_points(60.0, 0.0, 40.0, 135.0, 225.0))
    groups = group_fragments_by_hinge_consensus([door_a, door_b])
    assert len(groups) == 2
    assert all(g.identity_state == IdentityState.PROVEN_DISTINCT for g in groups)


# ---------------------------------------------------------------------------
# Case: true double door (two hinges, mirrored) -- must NOT be collapsed
# into one hinge merely because the two arcs are visually adjacent.
# ---------------------------------------------------------------------------


def test_true_double_door_keeps_two_distinct_hinges() -> None:
    left_hinge = (0.0, 0.0)
    right_hinge = (80.0, 0.0)
    r = 45.0
    left_leaf = make_fragment("left_leaf", _arc_points(*left_hinge, r, 0.0, 90.0))
    right_leaf = make_fragment("right_leaf", _arc_points(*right_hinge, r, 90.0, 180.0))
    groups = group_fragments_by_hinge_consensus([left_leaf, right_leaf])
    # Two real hinges must remain two groups -- collapsing a true double
    # door into a single hinge would misrepresent the physical structure
    # even though downstream "how many commercial door leaves" is a
    # separate question from "how many hinges/openings are physically here".
    assert len(groups) == 2
    hinges = {g.hinge for g in groups}
    assert len(hinges) == 2


# ---------------------------------------------------------------------------
# Case: partial arc / insufficient evidence -> UNRESOLVED, never guessed
# ---------------------------------------------------------------------------


def test_partial_arc_with_tiny_angular_span_is_unresolved_alone() -> None:
    tiny = make_fragment("tiny", _arc_points(0, 0, 50, 0, 8, n=5))
    groups = group_fragments_by_hinge_consensus([tiny])
    assert len(groups) == 1
    assert groups[0].identity_state == IdentityState.UNRESOLVED


def test_pairing_a_tiny_fragment_with_a_real_arc_is_unresolved_not_forced() -> None:
    real = make_fragment("real", _arc_points(0, 0, 50, 0, 80))
    tiny = make_fragment("tiny", _arc_points(200, 200, 50, 0, 6, n=4))
    result = resolve_pair_identity(real, tiny)
    assert result.identity_state == IdentityState.UNRESOLVED


# ---------------------------------------------------------------------------
# Case: noisy curve -- must tolerate realistic raster/anti-aliasing noise
# ---------------------------------------------------------------------------


def test_noisy_fragments_of_one_swing_still_merge() -> None:
    a = make_fragment("a", _arc_points(0, 0, 50, 0, 40, noise_std=0.6))
    b = make_fragment("b", _arc_points(0, 0, 50, 45, 90, noise_std=0.6))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_SAME


def test_noisy_separate_doors_still_kept_distinct() -> None:
    a = make_fragment("a", _arc_points(0, 0, 40, 0, 90, noise_std=0.6))
    b = make_fragment("b", _arc_points(45, 0, 40, 90, 180, noise_std=0.6))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_DISTINCT


# ---------------------------------------------------------------------------
# Case: same radius, unrelated, far apart -- radius match alone is not enough
# ---------------------------------------------------------------------------


def test_same_radius_unrelated_curve_far_away_stays_distinct() -> None:
    a = make_fragment("a", _arc_points(0, 0, 45, 0, 90))
    b = make_fragment("b", _arc_points(5000, 5000, 45, 0, 90))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_DISTINCT


# ---------------------------------------------------------------------------
# Case: scale/DPI invariance -- tolerances are radius-relative, not fixed
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0, 8.0])
def test_fragment_merge_decision_is_scale_invariant(scale: float) -> None:
    a = make_fragment("a", _arc_points(0, 0, 40 * scale, 0, 40))
    b = make_fragment("b", _arc_points(0, 0, 40 * scale, 45, 90))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_SAME


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0, 8.0])
def test_distinct_door_decision_is_scale_invariant(scale: float) -> None:
    a = make_fragment("a", _arc_points(0, 0, 35 * scale, 0, 90))
    b = make_fragment("b", _arc_points(40 * scale, 0, 35 * scale, 90, 180))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_DISTINCT


# ---------------------------------------------------------------------------
# Case: rotation invariance -- absolute orientation must not matter
# ---------------------------------------------------------------------------


def _rotate(points: np.ndarray, deg: float) -> np.ndarray:
    theta = np.radians(deg)
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    return points @ rot.T


@pytest.mark.parametrize("rotation_deg", [17.0, 90.0, 200.0])
def test_fragment_merge_decision_is_rotation_invariant(rotation_deg: float) -> None:
    a = make_fragment("a", _rotate(_arc_points(0, 0, 40, 0, 40), rotation_deg))
    b = make_fragment("b", _rotate(_arc_points(0, 0, 40, 45, 90), rotation_deg))
    result = resolve_pair_identity(a, b)
    assert result.identity_state == IdentityState.PROVEN_SAME


# ---------------------------------------------------------------------------
# Never merges purely because it would produce a convenient total: an
# explicit regression guard against tuning to a target count.
# ---------------------------------------------------------------------------


def test_five_independent_unrelated_arcs_never_collapse_to_fewer_groups() -> None:
    """A generic sanity net: five clearly-independent swings (all different
    hinges, well separated) must resolve to five groups. This is not a
    Murera-derived expectation -- it is a check that the algorithm cannot
    be satisfied by merely producing *some* small number of groups; it must
    keep genuinely independent evidence separate no matter what number of
    groups that implies."""
    hinges = [(0, 0), (200, 0), (400, 0), (0, 300), (400, 300)]
    frags = [
        make_fragment(f"d{i}", _arc_points(hx, hy, 30, 0, 90))
        for i, (hx, hy) in enumerate(hinges)
    ]
    groups = group_fragments_by_hinge_consensus(frags)
    assert len(groups) == 5
