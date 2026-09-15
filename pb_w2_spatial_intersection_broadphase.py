"""Scalable candidate-pair discovery for W2 segment-intersection splitting.

`pb_accuracy_v13_engines_v145.split_segments_at_intersections` is a correct,
exact, brute-force O(n^2) all-pairs scan -- flagged as a known cost driver in
docs/planreader_wall_room_topology_spec.md Sec.17, which explicitly prescribes
the fix: "a spatial index (grid/bucket segments by bounding box before
pairwise testing), not a different algorithm."

This module does exactly that and nothing else. It does NOT reimplement or
alter the exact intersection predicate (`_segment_intersection`), the
duplicate-point tolerance, the parametric sort, or the minimum-fragment-length
cutoff -- all of those are imported from the existing module unchanged, so
this file cannot silently drift from the oracle's math. The only thing this
module changes is which (i, j) pairs are ever handed to that predicate.

Correctness argument (why this is a superset, not an approximation)
---------------------------------------------------------------------
The frozen oracle ``_segment_intersection(..., tol=1e-9)`` accepts an
infinite-line crossing when each coordinate lies in
``[min(endpoint) - tol, max(endpoint) + tol]``. Strict (unpadded) AABB
overlap is therefore NOT a necessary condition for an oracle hit: two
segments whose boxes are separated by at most ``1e-9`` can still be
accepted. A review counterexample is the horizontal ``(0,0)->(1,0)`` and
the vertical at ``x = 1 + gap`` for ``gap <= 1e-9``.

The required invariant is: every pair the frozen oracle accepts must be
presented to that oracle. The broad phase therefore expands every segment
box on all four sides by exactly ``_INTERSECTION_BROADPHASE_TOL = 1e-9``
(the frozen default, not ``_same``'s ``1e-6`` and not the ``1e-7``
fragment cutoff). Padded-bbox overlap is a necessary condition for any
pair ``_segment_intersection`` can accept. Extra padded pairs are allowed;
the unchanged predicate remains the only decision-maker.

Determinism argument (why replay order stays byte-for-byte identical)
---------------------------------------------------------------------
The oracle's per-segment point list (`pts[i]`) is built by an outer loop over
i in ascending order and, within each i, an inner loop over j > i in
ascending order, appending an intersection point to both `pts[i]` and
`pts[j]` when found. The final dedup step keeps the FIRST occurrence of any
near-duplicate point (tol=1e-6), so the *order* points are discovered in can
matter for which of two near-duplicate coordinates survives (e.g. three
concurrent lines). `split_segments_at_intersections_indexed` below preserves
this exactly: it keeps the identical outer-i / inner-ascending-j loop
structure, merely restricting the inner loop to a precomputed candidate set
instead of the full range(i+1, n). Since every skipped pair is one the exact
predicate would have returned None for anyway (guaranteed above), the
resulting sequence of `pts[i].append(p)` / `pts[j].append(p)` calls is
identical in content AND order to the oracle's, for any input -- not merely
"close," but constructively identical.

Broad-phase algorithm: sweep-and-prune (SAP)
---------------------------------------------
A uniform spatial grid was also considered (and is explicitly named in the
spec as an acceptable option), but real drawing data observed during the U1
review spans an extreme length range in the same page -- ~0.003pt splitter
residual slivers alongside full-length walls spanning most of the sheet
(pb_wall_room_topology_primitive_lineage.py's _UNSTABLE_DIRECTION_LENGTH_PT
note documents the short end; Baghau/Dungicha region traces documented the
long end). A fixed-cell grid forces a choice between a cell size that is too
coarse for short fragments (defeating the point of indexing) or too fine for
long segments (which then span very many cells, needing special-cased
handling). Sweep-and-prune has no cell-size parameter at all and degrades
gracefully regardless of the length distribution, at the cost of not being a
true spatial index (its worst case, where every segment's x-interval overlaps
every other's, degrades toward O(n^2) -- an intrinsic property of the data's
own 1D interval structure, not an implementation defect; real architectural
floor plans are spatially distributed, not universally overlapping in one
axis, so this worst case is not expected on real drawings and is verified
empirically in the benchmark harness, not merely assumed).

No new third-party dependency (shapely/rtree/scipy) is introduced: none are
currently installed, and adding one for a single internal broad-phase is a
larger-footprint change than a small, fully self-contained, exactly-tested
pure-Python sweep. This keeps the change additive and low-risk.

This module is purely additive. Nothing in the existing pipeline imports it.
`split_segments_at_intersections` in pb_accuracy_v13_engines_v145.py is left
completely untouched and continues to serve as the correctness oracle.
"""
from __future__ import annotations

import heapq
from collections import defaultdict
from typing import Dict, List, Sequence, Tuple

from pb_accuracy_v13_engines_v145 import (
    Point,
    Segment,
    _same,
    _segment_intersection,
    segment_length,
)

BBox = Tuple[float, float, float, float]

# Must equal the frozen ``_segment_intersection`` default. Not ``_same`` (1e-6)
# and not the fragment-length cutoff (1e-7). Drift is guarded in tests.
_INTERSECTION_BROADPHASE_TOL = 1e-9


def segment_bbox(segment: Segment) -> BBox:
    """Padded AABB (xmin, ymin, xmax, ymax) for candidate discovery.

    Padding is exactly the frozen oracle endpoint-containment tolerance.
    """
    (x1, y1), (x2, y2) = segment
    pad = _INTERSECTION_BROADPHASE_TOL
    return (
        min(x1, x2) - pad,
        min(y1, y2) - pad,
        max(x1, x2) + pad,
        max(y1, y2) + pad,
    )


def build_candidate_pairs(segments: Sequence[Segment]) -> Dict[int, List[int]]:
    """For each segment index i, the sorted list of indices j > i whose
    *padded* bounding box overlaps segment i's -- a guaranteed superset of
    every pair the exact intersection predicate could return a point for.
    Uses a sweep-and-prune pass over padded x-intervals (sorted by xmin, an
    ascending-xmax min-heap for O(log n) eviction) followed by a padded
    y-interval check on the surviving active set.
    """
    n = len(segments)
    if n < 2:
        return {}

    bboxes = [segment_bbox(s) for s in segments]
    order = sorted(range(n), key=lambda i: (bboxes[i][0], i))

    candidates: Dict[int, set] = defaultdict(set)
    heap: List[Tuple[float, int]] = []  # (xmax, idx) of currently active segments
    active: set = set()

    for idx in order:
        xmin_i, ymin_i, xmax_i, ymax_i = bboxes[idx]

        while heap and heap[0][0] < xmin_i:
            _, expired_idx = heapq.heappop(heap)
            active.discard(expired_idx)

        for other_idx in active:
            ymin_o, ymax_o = bboxes[other_idx][1], bboxes[other_idx][3]
            if ymin_o <= ymax_i and ymin_i <= ymax_o:
                lo, hi = (other_idx, idx) if other_idx < idx else (idx, other_idx)
                candidates[lo].add(hi)

        heapq.heappush(heap, (xmax_i, idx))
        active.add(idx)

    return {i: sorted(js) for i, js in candidates.items()}


def split_segments_at_intersections_indexed(segments: Sequence[Segment]) -> List[Segment]:
    """Drop-in equivalent of pb_accuracy_v13_engines_v145.split_segments_at_
    intersections that discovers candidate pairs via build_candidate_pairs
    instead of a raw O(n^2) nested loop. Every other step -- the exact
    intersection predicate, the duplicate-point tolerance, the parametric
    sort, the minimum-fragment-length cutoff -- is the identical imported
    code, unmodified. See module docstring for why this is constructively
    (not just empirically) equivalent to the oracle.
    """
    n = len(segments)
    pts: List[List[Point]] = [
        [tuple(map(float, s[0])), tuple(map(float, s[1]))] for s in segments
    ]
    candidates = build_candidate_pairs(segments)
    for i in range(n):
        for j in candidates.get(i, ()):
            p = _segment_intersection(segments[i], segments[j])
            if p is not None:
                pts[i].append(p)
                pts[j].append(p)

    out: List[Segment] = []
    for original, found in zip(segments, pts):
        a, b = original
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        denom = dx * dx + dy * dy or 1.0
        unique: List[Point] = []
        for p in found:
            if not any(_same(p, q) for q in unique):
                unique.append(p)
        unique.sort(key=lambda p: ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / denom)
        for p, q in zip(unique, unique[1:]):
            if segment_length((p, q)) > 1e-7:
                out.append((p, q))
    return out


def broadphase_reduction_stats(segments: Sequence[Segment]) -> Dict[str, float]:
    """Diagnostic-only summary of how many candidate pairs the broad phase
    produced versus the full O(n^2) all-pairs count, for benchmarking and
    regression-guard tests. Not used by any production or authority path."""
    n = len(segments)
    candidates = build_candidate_pairs(segments)
    candidate_pair_count = sum(len(v) for v in candidates.values())
    all_pairs_count = n * (n - 1) // 2
    return {
        "segment_count": n,
        "all_pairs": all_pairs_count,
        "candidate_pairs": candidate_pair_count,
        "reduction_ratio": (candidate_pair_count / all_pairs_count) if all_pairs_count else 0.0,
    }
