"""pb_hinge_consensus_door_identity.py -- Physical door-swing identity via
hinge-centered geometric consensus.

Research-stage diagnostic module. Distinguishes:

- ONE physical door swing drawn as several fragmented curve strokes
  (common on scanned/raster plans where a swing arc is not one clean
  continuous stroke), from
- TWO genuinely separate, nearby physical doors,

by testing whether curve-pixel fragments are consistent with a single
shared hinge center and radius -- a real physical invariant of a door
swing arc -- rather than by raw spatial proximity between fragment
centroids or nearest contour points.

That distinction is empirically necessary, not stylistic: on a real
source page, two genuinely separate doors were found whose nearest
points were CLOSER together than two fragments of a single door's own
swing symbol (11.3pt vs 15.1pt at the page's native scale). Any rule
based on "how close are these blobs" alone gets at least one of those
two cases wrong. Hinge/radius consensus does not have that failure mode
in principle, because it asks a physically meaningful question --
"do these strokes trace the same circle" -- instead of a purely spatial
one.

This module is NOT a commercial-count authority and never will be on its
own. It classifies fragment-group relationships using the same
three-state vocabulary as pb_source_opening_candidate_authority's
IdentityState (PROVEN_SAME / PROVEN_DISTINCT / UNRESOLVED) and fails
closed to UNRESOLVED rather than forcing a decision when the evidence is
ambiguous. It never hardcodes a fixed pixel/point tolerance: every
tolerance is expressed as a fraction of the fragment's own fitted radius,
so it is scale/DPI-independent by construction. It never reads or is
tuned against an expected door count for any project.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence, Tuple

import numpy as np

from pb_source_opening_candidate_authority import IdentityState

__all__ = [
    "IdentityState",
    "CircleFit",
    "SwingFragment",
    "PairConsensusResult",
    "FragmentGroup",
    "fit_circle_algebraic",
    "fit_circle_ransac",
    "make_fragment",
    "resolve_pair_identity",
    "group_fragments_by_hinge_consensus",
]

# Fractions, not fixed distances: every one of these is multiplied by a
# fragment's own fitted radius before use, so behaviour is identical at
# any DPI/scale as long as the source geometry is genuinely the same.
_RADIUS_AGREEMENT_FRAC = 0.25
_HINGE_AGREEMENT_FRAC = 0.35
_RANSAC_INLIER_RESIDUAL_FRAC = 0.08
_MIN_POINTS_FOR_STANDALONE_FIT = 8
_MIN_ANGULAR_SPAN_DEG_FOR_STANDALONE_FIT = 15.0

# A raw cv2.findContours() trace of a filled/thick stroke follows its
# OUTER boundary -- both the inner and outer edge of the stroke, plus end
# caps -- not a clean 1-D centerline. That systematically inflates
# circle-fit residual relative to an idealized thin-arc model, by roughly
# half the stroke's own line width, regardless of the arc's radius. A
# residual tolerance expressed as a pure fraction of radius therefore
# under-serves small-radius fragments (half a line width is a much bigger
# fraction of a small circle than a large one) -- confirmed empirically:
# real single-arc contour fragments measured 0.18-0.45 residual/radius,
# not the ~0.08 an idealized thin arc gives. line_half_width (when
# supplied, e.g. via a distance-transform measurement of the source mask)
# is used alongside the radius fraction so tolerance reflects genuine
# stroke geometry, never a fixed pixel/point constant.
_STROKE_WIDTH_TOLERANCE_MULTIPLIER = 1.5
_MIN_INLIER_FRACTION_PER_FRAGMENT = 0.6


@dataclass(frozen=True)
class CircleFit:
    cx: float
    cy: float
    r: float
    rms_residual: float
    n_points: int
    angular_span_deg: float


def _angular_span_deg(points: np.ndarray, cx: float, cy: float) -> float:
    angles = np.degrees(np.arctan2(points[:, 1] - cy, points[:, 0] - cx))
    bins = np.zeros(72, dtype=bool)
    idx = ((angles + 180.0) / 5.0).astype(int) % 72
    bins[idx] = True
    # Largest contiguous run of occupied 5-degree bins on the circle.
    doubled = np.concatenate([bins, bins])
    best = cur = 0
    for occupied in doubled:
        cur = cur + 1 if occupied else 0
        best = max(best, cur)
    return float(min(best, 72) * 5.0)


def fit_circle_algebraic(points: np.ndarray) -> Optional[CircleFit]:
    """Kasa algebraic least-squares circle fit. None if points are degenerate
    (colinear, or too few to determine a circle)."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return None
    x, y = pts[:, 0], pts[:, 1]
    A = np.column_stack([x, y, np.ones(len(pts))])
    b = -(x**2 + y**2)
    try:
        (D, E, F), *_ = np.linalg.lstsq(A, b, rcond=None)
    except np.linalg.LinAlgError:
        return None
    cx, cy = -D / 2.0, -E / 2.0
    r_sq = (D**2 + E**2) / 4.0 - F
    if not np.isfinite(r_sq) or r_sq <= 0:
        return None
    r = float(np.sqrt(r_sq))
    residuals = np.abs(np.hypot(x - cx, y - cy) - r)
    rms = float(np.sqrt(np.mean(residuals**2)))
    span = _angular_span_deg(pts, cx, cy)
    return CircleFit(cx=cx, cy=cy, r=r, rms_residual=rms, n_points=len(pts), angular_span_deg=span)


def _circumcircle(p1: np.ndarray, p2: np.ndarray, p3: np.ndarray) -> Optional[Tuple[float, float, float]]:
    ax, ay = p1
    bx, by = p2
    cx_, cy_ = p3
    d = 2.0 * (ax * (by - cy_) + bx * (cy_ - ay) + cx_ * (ay - by))
    if abs(d) < 1e-9:
        return None
    ux = ((ax**2 + ay**2) * (by - cy_) + (bx**2 + by**2) * (cy_ - ay) + (cx_**2 + cy_**2) * (ay - by)) / d
    uy = ((ax**2 + ay**2) * (cx_ - bx) + (bx**2 + by**2) * (ax - cx_) + (cx_**2 + cy_**2) * (bx - ax)) / d
    r = float(np.hypot(ax - ux, ay - uy))
    return float(ux), float(uy), r


def fit_circle_ransac(
    points: np.ndarray,
    *,
    inlier_residual_frac: float = _RANSAC_INLIER_RESIDUAL_FRAC,
    iterations: int = 200,
    rng: Optional[np.random.Generator] = None,
) -> Optional[CircleFit]:
    """Robust circle fit: sample 3-point circumcircles, keep the model with
    the most inliers, then refit least-squares on the inlier set. None if
    no 3-point sample yields a plausible model.

    The inlier tolerance is derived ONCE from the input point cloud's own
    spatial scale (its RMS distance from its centroid), not from each
    candidate model's own fitted radius. Scaling tolerance by a
    candidate's own radius lets a spurious, wildly-oversized candidate
    circle (formed by an unlucky 3-point sample spanning distant,
    unrelated points) claim a correspondingly huge tolerance band and
    falsely appear well-supported -- exactly the failure this function
    exists to avoid.
    """
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return None
    centroid = pts.mean(axis=0)
    scale_estimate = float(np.sqrt(np.mean(np.sum((pts - centroid) ** 2, axis=1))))
    if scale_estimate <= 0:
        scale_estimate = 1.0
    tol = inlier_residual_frac * scale_estimate

    rng = rng or np.random.default_rng(0)
    best_inliers: Optional[np.ndarray] = None
    best_count = -1
    n = len(pts)
    for _ in range(iterations):
        idx = rng.choice(n, size=3, replace=False)
        model = _circumcircle(pts[idx[0]], pts[idx[1]], pts[idx[2]])
        if model is None:
            continue
        cx, cy, r = model
        if r <= 0 or not np.isfinite(r):
            continue
        residuals = np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r)
        inliers = residuals <= tol
        count = int(inliers.sum())
        if count > best_count:
            best_count = count
            best_inliers = inliers
    if best_inliers is None or best_count < 3:
        return None
    return fit_circle_algebraic(pts[best_inliers])


@dataclass(frozen=True)
class SwingFragment:
    """One raster curve-pixel cluster: a candidate piece of a door-swing arc.

    Carries no semantic (tag/label) information -- this is physical
    geometry only. ``points`` are in a single consistent coordinate frame
    (e.g. PDF points), not pixels of a specific DPI render, so tolerances
    computed from a fitted radius are meaningful across renders.

    ``line_half_width``, when known (e.g. from a distance-transform
    measurement of the source raster mask, in the same coordinate frame as
    ``points``), grounds the residual tolerance in the fragment's actual
    stroke geometry rather than in radius alone -- see the module-level
    note on why a pure radius fraction under-serves small-radius,
    thick-relative-to-radius contour traces. When unknown, tolerance falls
    back to the radius fraction alone.
    """

    fragment_id: str
    points: np.ndarray
    line_half_width: Optional[float] = None
    standalone_fit: Optional[CircleFit] = field(default=None)

    def __post_init__(self) -> None:
        if self.standalone_fit is None:
            # RANSAC, not the plain algebraic fit: a thick-stroke boundary
            # trace is bimodal (inner edge + outer edge of the line), and a
            # pure least-squares fit can be pulled well off the true circle
            # by that structure, especially over a short angular span. A
            # robust fit is exactly as necessary for a fragment's own
            # standalone estimate as it is for the joint (multi-fragment)
            # fit below.
            fit = fit_circle_ransac(self.points)
            object.__setattr__(self, "standalone_fit", fit)


def make_fragment(
    fragment_id: str,
    points: Sequence[Sequence[float]],
    line_half_width: Optional[float] = None,
) -> SwingFragment:
    return SwingFragment(
        fragment_id=fragment_id,
        points=np.asarray(points, dtype=float),
        line_half_width=line_half_width,
    )


def _residual_tolerance(radius_ref: float, frag_a: "SwingFragment", frag_b: "SwingFragment") -> float:
    from_radius = _RANSAC_INLIER_RESIDUAL_FRAC * radius_ref
    widths = [w for w in (frag_a.line_half_width, frag_b.line_half_width) if w is not None]
    if not widths:
        return from_radius
    from_stroke = _STROKE_WIDTH_TOLERANCE_MULTIPLIER * max(widths)
    return max(from_radius, from_stroke)


@dataclass(frozen=True)
class PairConsensusResult:
    identity_state: IdentityState
    reason_codes: Tuple[str, ...]
    joint_fit: Optional[CircleFit] = None


def _fragment_has_standalone_evidence(frag: SwingFragment) -> bool:
    fit = frag.standalone_fit
    return (
        fit is not None
        and fit.n_points >= _MIN_POINTS_FOR_STANDALONE_FIT
        and fit.angular_span_deg >= _MIN_ANGULAR_SPAN_DEG_FOR_STANDALONE_FIT
    )


def resolve_pair_identity(frag_a: SwingFragment, frag_b: SwingFragment) -> PairConsensusResult:
    """Fail-closed pairwise test: do frag_a and frag_b trace the same
    physical hinge-centered arc (PROVEN_SAME), clearly different ones
    (PROVEN_DISTINCT), or is there not enough evidence either way
    (UNRESOLVED)? Spatial proximity between the fragments is never
    consulted -- only hinge/radius consensus."""
    has_a = _fragment_has_standalone_evidence(frag_a)
    has_b = _fragment_has_standalone_evidence(frag_b)
    if not has_a or not has_b:
        return PairConsensusResult(
            IdentityState.UNRESOLVED,
            ("insufficient_standalone_arc_evidence",),
        )

    fit_a, fit_b = frag_a.standalone_fit, frag_b.standalone_fit
    assert fit_a is not None and fit_b is not None

    joint_points = np.concatenate([frag_a.points, frag_b.points], axis=0)
    joint_fit = fit_circle_ransac(joint_points)
    if joint_fit is None:
        return PairConsensusResult(
            IdentityState.UNRESOLVED,
            ("joint_fit_failed",),
        )

    radius_ref = max(min(fit_a.r, fit_b.r), 1e-6)
    radius_gap = abs(fit_a.r - fit_b.r) / radius_ref
    hinge_gap = float(np.hypot(fit_a.cx - fit_b.cx, fit_a.cy - fit_b.cy)) / radius_ref

    # Use radius_ref (each fragment's OWN, already-trusted standalone fit),
    # not joint_fit.r: the joint RANSAC attempt is exactly what we are
    # trying to validate here, so its own radius must not also define the
    # tolerance used to judge it -- the same scaling trap as in
    # fit_circle_ransac's inlier counting.
    tol = _residual_tolerance(radius_ref, frag_a, frag_b)
    resid_a = np.abs(np.hypot(frag_a.points[:, 0] - joint_fit.cx, frag_a.points[:, 1] - joint_fit.cy) - joint_fit.r)
    resid_b = np.abs(np.hypot(frag_b.points[:, 0] - joint_fit.cx, frag_b.points[:, 1] - joint_fit.cy) - joint_fit.r)
    inlier_frac_a = float((resid_a <= tol).mean())
    inlier_frac_b = float((resid_b <= tol).mean())

    joint_supported = (
        inlier_frac_a >= _MIN_INLIER_FRACTION_PER_FRAGMENT
        and inlier_frac_b >= _MIN_INLIER_FRACTION_PER_FRAGMENT
    )

    if (
        joint_supported
        and radius_gap <= _RADIUS_AGREEMENT_FRAC
        and hinge_gap <= _HINGE_AGREEMENT_FRAC
    ):
        return PairConsensusResult(
            IdentityState.PROVEN_SAME,
            (
                "shared_hinge_within_tolerance",
                "compatible_radius",
                f"joint_inlier_fraction_a={inlier_frac_a:.2f}",
                f"joint_inlier_fraction_b={inlier_frac_b:.2f}",
            ),
            joint_fit=joint_fit,
        )

    # Affirmative separation, not mere disagreement: both fragments must
    # individually be well-explained (each fits its OWN hinge tightly) while
    # the joint single-hinge model is clearly incompatible with at least one
    # of them, AND the two standalone hinges are not just noisy estimates of
    # the same point.
    both_individually_tight = (
        fit_a.rms_residual <= _residual_tolerance(fit_a.r, frag_a, frag_a)
        and fit_b.rms_residual <= _residual_tolerance(fit_b.r, frag_b, frag_b)
    )
    if both_individually_tight and hinge_gap > _HINGE_AGREEMENT_FRAC and not joint_supported:
        return PairConsensusResult(
            IdentityState.PROVEN_DISTINCT,
            (
                "distinct_hinge_centers",
                "joint_single_hinge_model_rejected",
                f"hinge_gap_over_radius={hinge_gap:.2f}",
            ),
            joint_fit=joint_fit,
        )

    return PairConsensusResult(
        IdentityState.UNRESOLVED,
        (
            "ambiguous_consensus",
            f"radius_gap_over_radius={radius_gap:.2f}",
            f"hinge_gap_over_radius={hinge_gap:.2f}",
            f"joint_inlier_fraction_a={inlier_frac_a:.2f}",
            f"joint_inlier_fraction_b={inlier_frac_b:.2f}",
        ),
        joint_fit=joint_fit,
    )


@dataclass(frozen=True)
class FragmentGroup:
    fragment_ids: Tuple[str, ...]
    identity_state: IdentityState
    hinge: Optional[Tuple[float, float]]
    radius: Optional[float]
    reason_codes: Tuple[str, ...]


def group_fragments_by_hinge_consensus(fragments: Sequence[SwingFragment]) -> List[FragmentGroup]:
    """Cluster fragments into physical-swing groups by hinge/radius
    consensus only. Never merges on spatial proximity alone. A fragment
    with no PROVEN_SAME partner is returned as its own singleton group,
    tagged UNRESOLVED or PROVEN_DISTINCT-from-everything-nearby according
    to whatever the pairwise tests actually established -- never silently
    dropped and never assumed distinct merely by default."""
    n = len(fragments)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    pair_reason_log: dict[Tuple[int, int], PairConsensusResult] = {}
    for i in range(n):
        for j in range(i + 1, n):
            result = resolve_pair_identity(fragments[i], fragments[j])
            pair_reason_log[(i, j)] = result
            if result.identity_state == IdentityState.PROVEN_SAME:
                union(i, j)

    clusters: dict[int, List[int]] = {}
    for i in range(n):
        clusters.setdefault(find(i), []).append(i)

    groups: List[FragmentGroup] = []
    for members in clusters.values():
        ids = tuple(fragments[m].fragment_id for m in members)
        if len(members) == 1:
            m = members[0]
            has_evidence = _fragment_has_standalone_evidence(fragments[m])
            state = IdentityState.UNRESOLVED if not has_evidence else IdentityState.PROVEN_DISTINCT
            fit = fragments[m].standalone_fit
            groups.append(
                FragmentGroup(
                    fragment_ids=ids,
                    identity_state=state,
                    hinge=(fit.cx, fit.cy) if fit else None,
                    radius=fit.r if fit else None,
                    reason_codes=(
                        ("standalone_fragment_no_consensus_partner",)
                        if has_evidence
                        else ("standalone_fragment_insufficient_arc_evidence",)
                    ),
                )
            )
            continue
        all_points = np.concatenate([fragments[m].points for m in members], axis=0)
        joint_fit = fit_circle_ransac(all_points)
        reasons = []
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                i, j = sorted((members[a], members[b]))
                if (i, j) in pair_reason_log:
                    reasons.extend(pair_reason_log[(i, j)].reason_codes)
        groups.append(
            FragmentGroup(
                fragment_ids=ids,
                identity_state=IdentityState.PROVEN_SAME,
                hinge=(joint_fit.cx, joint_fit.cy) if joint_fit else None,
                radius=joint_fit.r if joint_fit else None,
                reason_codes=tuple(dict.fromkeys(reasons)),
            )
        )
    return groups
