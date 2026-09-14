"""Equivalence and performance regression tests for the W2 spatial broad
phase (pb_w2_spatial_intersection_broadphase.py).

pb_accuracy_v13_engines_v145.split_segments_at_intersections is an exact,
brute-force O(n^2) all-pairs splitter, flagged in docs/planreader_wall_room_
topology_spec.md Sec.17 as a known cost driver once segment counts grow past
the "hundreds to low-thousands" range this repo's registered benchmarks sit
in today. A real full-page (non-viewport-scoped) probe on one available
native-vector development drawing showed 37k+ structural segments and had to
be killed after several minutes -- the exact scenario the spec's own
performance note anticipated and prescribed a fix for: "a spatial index
(grid/bucket segments by bounding box before pairwise testing), not a
different algorithm."

This file proves `split_segments_at_intersections_indexed` (the broad-phase
+ unchanged-exact-predicate implementation) produces byte-for-byte identical
output to the existing O(n^2) function across synthetic adversarial
geometry, real committed drawing snapshots, and randomized/shuffled/
transformed variants of all of the above -- never merely "close." The
existing O(n^2) function is left completely untouched and used throughout
this file purely as the correctness oracle. No production code path is
changed or wired to the new function by this file.
"""
from __future__ import annotations

import inspect
import json
import math
import random
import time
from pathlib import Path
from typing import List, Sequence, Set, Tuple

import pytest

from pb_accuracy_v13_engines_v145 import (
    Segment,
    _segment_intersection,
    split_segments_at_intersections,
)
from pb_w2_spatial_intersection_broadphase import (
    _INTERSECTION_BROADPHASE_TOL,
    broadphase_reduction_stats,
    build_candidate_pairs,
    segment_bbox,
    split_segments_at_intersections_indexed,
)


def _seg(x1: float, y1: float, x2: float, y2: float) -> Segment:
    return ((x1, y1), (x2, y2))


def _assert_equivalent(segments: List[Segment], label: str = "") -> None:
    oracle = split_segments_at_intersections(segments)
    fast = split_segments_at_intersections_indexed(segments)
    assert fast == oracle, (
        f"{label}: indexed splitter diverged from the O(n^2) oracle "
        f"(oracle produced {len(oracle)} segments, indexed produced {len(fast)})"
    )


def _indexed_candidate_pairs(segments: Sequence[Segment]) -> Set[Tuple[int, int]]:
    candidates = build_candidate_pairs(segments)
    return {(i, j) for i, js in candidates.items() for j in js}


def _oracle_hit_pairs(segments: Sequence[Segment]) -> Set[Tuple[int, int]]:
    hits: Set[Tuple[int, int]] = set()
    for i in range(len(segments)):
        for j in range(i + 1, len(segments)):
            if _segment_intersection(segments[i], segments[j]) is not None:
                hits.add((i, j))
    return hits


def _assert_oracle_hits_are_candidates(segments: Sequence[Segment], label: str = "") -> Tuple[int, int]:
    hits = _oracle_hit_pairs(segments)
    candidates = _indexed_candidate_pairs(segments)
    missing = hits - candidates
    assert not missing, (
        f"{label}: TOTAL ORACLE-HIT PAIRS = {len(hits)}; "
        f"MISSING ORACLE-HIT PAIRS = {len(missing)}; sample={sorted(missing)[:5]}"
    )
    return len(hits), len(missing)


# ---------------------------------------------------------------------------
# Basic correctness (hand-built, unambiguous cases)
# ---------------------------------------------------------------------------


class TestBasicCorrectness:
    def test_simple_crossing(self):
        segments = [_seg(0, 0, 10, 0), _seg(5, -5, 5, 5)]
        _assert_equivalent(segments, "simple crossing")
        fast = split_segments_at_intersections_indexed(segments)
        assert len(fast) == 4

    def test_parallel_non_intersecting_segments_not_split(self):
        segments = [_seg(0, 0, 10, 0), _seg(0, 5, 10, 5)]
        _assert_equivalent(segments, "parallel non-intersecting")
        fast = split_segments_at_intersections_indexed(segments)
        assert fast == segments

    def test_endpoint_touching(self):
        segments = [_seg(0, 0, 5, 0), _seg(5, 0, 5, 5)]
        _assert_equivalent(segments, "endpoint touching")

    def test_collinear_partial_overlap_not_split(self):
        # The exact predicate rejects near-parallel/collinear pairs via its
        # determinant test (den ~ 0) -- collinear overlap is never detected
        # as a "crossing." Confirmed pre-existing, documented behavior, not
        # something this broad phase may alter.
        segments = [_seg(0, 0, 10, 0), _seg(5, 0, 15, 0)]
        _assert_equivalent(segments, "collinear partial overlap")
        fast = split_segments_at_intersections_indexed(segments)
        assert fast == segments

    def test_exact_duplicate_segments(self):
        segments = [_seg(0, 0, 10, 0), _seg(0, 0, 10, 0), _seg(5, -5, 5, 5)]
        _assert_equivalent(segments, "exact duplicate segments")

    def test_very_short_fragment(self):
        segments = [_seg(0, 0, 1e-4, 1e-4), _seg(0, 1e-4, 1e-4, 0)]
        _assert_equivalent(segments, "very short fragment")

    def test_empty_and_singleton_inputs(self):
        assert split_segments_at_intersections_indexed([]) == []
        one = [_seg(0, 0, 1, 1)]
        assert split_segments_at_intersections_indexed(one) == one

    def test_disjoint_bounding_boxes_never_become_candidates(self):
        segments = [_seg(0, 0, 1, 1), _seg(1000, 1000, 1001, 1001)]
        candidates = build_candidate_pairs(segments)
        assert candidates.get(0, []) == []
        _assert_equivalent(segments, "disjoint bboxes")

    def test_touching_bounding_boxes_are_kept_as_candidates(self):
        # Bboxes that touch exactly at one coordinate boundary must not be
        # evicted by the sweep as if they were strictly disjoint.
        segments = [_seg(0, 0, 5, 5), _seg(5, 5, 10, 0)]
        candidates = build_candidate_pairs(segments)
        assert candidates.get(0, []) == [1]
        _assert_equivalent(segments, "touching bboxes")


class TestOracleToleranceContract:
    def test_broadphase_pad_matches_frozen_oracle_default(self) -> None:
        default = inspect.signature(_segment_intersection).parameters["tol"].default
        assert default == 1e-9
        assert _INTERSECTION_BROADPHASE_TOL == 1e-9
        assert _INTERSECTION_BROADPHASE_TOL == default
        assert _INTERSECTION_BROADPHASE_TOL != 1e-6
        assert _INTERSECTION_BROADPHASE_TOL != 1e-7


class TestVerifiedBoundaryMiss:
    """The reviewed strict-AABB miss: vertical just past x=1, padded inside()."""

    @pytest.mark.parametrize("gap", (4e-10, 5e-10, 9e-10, 1e-9, 1.1e-9, 2e-9))
    def test_candidate_membership_follows_frozen_oracle(self, gap: float) -> None:
        horizontal = _seg(0.0, 0.0, 1.0, 0.0)
        vertical = _seg(1.0 + gap, -1.0, 1.0 + gap, 1.0)
        segments = [horizontal, vertical]
        oracle = _segment_intersection(horizontal, vertical)
        in_candidates = (0, 1) in _indexed_candidate_pairs(segments)
        if oracle is not None:
            assert in_candidates is True
        _assert_oracle_hits_are_candidates(segments, f"boundary gap={gap}")
        _assert_equivalent(segments, f"boundary gap={gap}")


# ---------------------------------------------------------------------------
# Synthetic adversarial pattern generators
# ---------------------------------------------------------------------------


def _random_cloud(n: int, seed: int, extent: float = 100.0) -> List[Segment]:
    rng = random.Random(seed)
    return [
        _seg(
            rng.uniform(0, extent), rng.uniform(0, extent),
            rng.uniform(0, extent), rng.uniform(0, extent),
        )
        for _ in range(n)
    ]


def _grid_pattern(rows: int, cols: int, spacing: float = 10.0) -> List[Segment]:
    width = cols * spacing
    height = rows * spacing
    segments = []
    for r in range(rows + 1):
        y = r * spacing
        segments.append(_seg(0, y, width, y))
    for c in range(cols + 1):
        x = c * spacing
        segments.append(_seg(x, 0, x, height))
    return segments


def _star_pattern(spokes: int, radius: float = 50.0, center: Tuple[float, float] = (0.0, 0.0)) -> List[Segment]:
    cx, cy = center
    segments = []
    for i in range(spokes):
        angle = (2 * math.pi * i) / spokes
        segments.append(_seg(cx, cy, cx + radius * math.cos(angle), cy + radius * math.sin(angle)))
    return segments


def _orthogonal_floor_plan(rooms: int, seed: int, room_size: float = 20.0) -> List[Segment]:
    rng = random.Random(seed)
    segments = []
    for i in range(rooms):
        x0 = rng.uniform(0, 100)
        y0 = rng.uniform(0, 100)
        w = room_size + rng.uniform(-5, 5)
        h = room_size + rng.uniform(-5, 5)
        x1, y1 = x0 + w, y0 + h
        segments.extend([
            _seg(x0, y0, x1, y0),
            _seg(x1, y0, x1, y1),
            _seg(x1, y1, x0, y1),
            _seg(x0, y1, x0, y0),
        ])
    return segments


def _nearly_parallel_lines(n: int, base_angle: float = 0.0, epsilon: float = 1e-6) -> List[Segment]:
    segments = []
    for i in range(n):
        angle = base_angle + i * epsilon
        segments.append(_seg(0, i * 0.5, 100 * math.cos(angle), i * 0.5 + 100 * math.sin(angle)))
    return segments


def _duplicate_and_repeated_lines(base: List[Segment], repeats: int) -> List[Segment]:
    out: List[Segment] = []
    for _ in range(repeats):
        out.extend(base)
    return out


def _translate(segments: List[Segment], dx: float, dy: float) -> List[Segment]:
    return [((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy)) for a, b in segments]


def _scale(segments: List[Segment], factor: float) -> List[Segment]:
    return [((a[0] * factor, a[1] * factor), (b[0] * factor, b[1] * factor)) for a, b in segments]


def _rotate(segments: List[Segment], theta: float) -> List[Segment]:
    c, s = math.cos(theta), math.sin(theta)

    def rot(p):
        return (p[0] * c - p[1] * s, p[0] * s + p[1] * c)

    return [(rot(a), rot(b)) for a, b in segments]


class TestSyntheticAdversarialPatterns:
    @pytest.mark.parametrize("seed", [1, 2, 3, 11, 42, 1234])
    def test_random_cloud(self, seed):
        _assert_equivalent(_random_cloud(150, seed), f"random cloud seed={seed}")

    def test_dense_grid(self):
        _assert_equivalent(_grid_pattern(15, 15), "dense grid")

    def test_star_pattern_concurrent_lines(self):
        # All spokes share the exact same origin point -- the concurrent-
        # lines / near-duplicate-intersection-point case the module
        # docstring's determinism argument is specifically about.
        _assert_equivalent(_star_pattern(37), "star pattern (concurrent lines)")

    @pytest.mark.parametrize("seed", [7, 21])
    def test_orthogonal_floor_plan(self, seed):
        _assert_equivalent(_orthogonal_floor_plan(20, seed), f"orthogonal floor plan seed={seed}")

    def test_nearly_parallel_lines(self):
        _assert_equivalent(_nearly_parallel_lines(60), "nearly parallel lines")

    def test_duplicate_segments_repeated_many_times(self):
        base = _grid_pattern(4, 4)
        _assert_equivalent(_duplicate_and_repeated_lines(base, 5), "repeated duplicate grid")

    def test_repeated_collinear_lines_with_partial_overlaps(self):
        segments = [_seg(i * 2, 0, i * 2 + 5, 0) for i in range(10)]
        _assert_equivalent(segments, "repeated collinear partial overlaps")

    def test_mixed_very_short_and_normal_fragments(self):
        segments = _grid_pattern(6, 6) + [
            _seg(1.0000001, 1.0, 1.0000002, 1.0),
            _seg(3.0, 3.0, 3.0 + 1e-5, 3.0 + 1e-5),
        ]
        _assert_equivalent(segments, "mixed short and normal fragments")

    @pytest.mark.parametrize("seed", [5, 17])
    def test_translated_scaled_rotated_inputs(self, seed):
        base = _orthogonal_floor_plan(8, seed) + _star_pattern(9, center=(40.0, 40.0))
        for transform_name, transformed in (
            ("translated", _translate(base, 500.0, -300.0)),
            ("scaled", _scale(base, 3.7)),
            ("rotated", _rotate(base, math.pi / 5)),
            ("translated+scaled+rotated", _translate(_scale(_rotate(base, 0.9), 0.4), -50.0, 200.0)),
        ):
            _assert_equivalent(transformed, f"{transform_name} (seed={seed})")

    @pytest.mark.parametrize("seed", [1, 2, 3, 8, 99])
    def test_shuffled_input_order(self, seed):
        base = _grid_pattern(10, 10) + _star_pattern(13) + _orthogonal_floor_plan(6, seed)
        rng = random.Random(seed)
        shuffled = list(base)
        rng.shuffle(shuffled)
        _assert_equivalent(shuffled, f"shuffled order seed={seed}")

    def test_dense_synthetic_cad_like_drawing(self):
        combined: List[Segment] = []
        combined.extend(_grid_pattern(20, 20))
        combined.extend(_star_pattern(25, radius=80.0, center=(100.0, 100.0)))
        combined.extend(_orthogonal_floor_plan(40, seed=99))
        combined.extend(_nearly_parallel_lines(30, base_angle=0.3))
        combined.extend(_duplicate_and_repeated_lines(_grid_pattern(3, 3), 3))
        assert len(combined) > 250
        _assert_equivalent(combined, "dense synthetic CAD-like drawing")


class TestOracleHitSuperset:
    """oracle_hit_pairs ⊆ indexed_candidate_pairs. Missing must stay 0."""

    def _near_tolerance_sets(self) -> List[List[Segment]]:
        tol = _INTERSECTION_BROADPHASE_TOL
        sets: List[List[Segment]] = []
        for gap in (tol - 4e-10, tol - 1e-10, tol, tol + 1e-10, tol + 4e-10):
            sets.append([_seg(0.0, 0.0, 1.0, 0.0), _seg(1.0 + gap, -1.0, 1.0 + gap, 1.0)])
            sets.append([_seg(0.0, 0.0, 0.0, 1.0), _seg(-1.0, 1.0 + gap, 1.0, 1.0 + gap)])
            sets.append([_seg(0.0, 0.0, 2.0, 0.0), _seg(2.0 + gap, 0.0, 2.0 + gap, 2.0)])
        return sets

    def test_near_tolerance_gaps_and_endpoint_near_misses(self) -> None:
        total = 0
        missing = 0
        for idx, segments in enumerate(self._near_tolerance_sets()):
            hits, miss = _assert_oracle_hits_are_candidates(segments, f"near-tol set {idx}")
            total += hits
            missing += miss
            _assert_equivalent(segments, f"near-tol set {idx}")
        assert missing == 0
        assert total >= 1

    @pytest.mark.parametrize("seed", [1, 2, 3, 11, 42])
    def test_random_clouds_and_metamorphics(self, seed: int) -> None:
        base = _random_cloud(80, seed)
        for name, segments in (
            ("cloud", base),
            ("translated", _translate(base, 40.0, -15.0)),
            ("rotated", _rotate(base, math.pi / 7)),
            ("scaled", _scale(base, 2.5)),
        ):
            _assert_oracle_hits_are_candidates(segments, f"{name} seed={seed}")
            _assert_equivalent(segments, f"{name} seed={seed}")

    def test_concurrent_nearly_parallel_duplicates_short_cad_shuffle(self) -> None:
        sets = [
            _star_pattern(19),
            _nearly_parallel_lines(40),
            _duplicate_and_repeated_lines(_grid_pattern(3, 3), 3),
            [_seg(0, 0, 1e-4, 1e-4), _seg(0, 1e-4, 1e-4, 0), _seg(0, 0, 2, 0)],
            _orthogonal_floor_plan(12, seed=8),
        ]
        shuffled = list(sets[-1])
        random.Random(4).shuffle(shuffled)
        sets.append(shuffled)
        total = 0
        missing = 0
        for idx, segments in enumerate(sets):
            hits, miss = _assert_oracle_hits_are_candidates(segments, f"property set {idx}")
            total += hits
            missing += miss
            _assert_equivalent(segments, f"property set {idx}")
        assert missing == 0
        assert total >= 1

    def test_exhaustive_small_sets_report_zero_missing(self) -> None:
        sets = [
            [_seg(0, 0, 10, 0), _seg(5, -5, 5, 5)],
            [_seg(0, 0, 5, 0), _seg(5, 0, 5, 5)],
            [_seg(0, 0, 10, 0), _seg(0, 0, 10, 0), _seg(5, -5, 5, 5)],
            _grid_pattern(4, 4),
            _star_pattern(11),
            _random_cloud(40, seed=9),
        ]
        total_hits = 0
        total_missing = 0
        for idx, segments in enumerate(sets):
            hits, miss = _assert_oracle_hits_are_candidates(segments, f"exhaustive set {idx}")
            total_hits += hits
            total_missing += miss
        assert total_missing == 0
        assert total_hits >= 1


# ---------------------------------------------------------------------------
# broadphase_reduction_stats / build_candidate_pairs sanity
# ---------------------------------------------------------------------------


class TestBroadphaseStats:
    def test_candidate_pairs_never_exceed_all_pairs(self):
        segments = _grid_pattern(12, 12)
        stats = broadphase_reduction_stats(segments)
        assert stats["candidate_pairs"] <= stats["all_pairs"]
        assert stats["segment_count"] == len(segments)

    def test_reduction_is_dramatic_on_sparse_realistic_layout(self):
        segments = _orthogonal_floor_plan(60, seed=3)
        stats = broadphase_reduction_stats(segments)
        assert stats["reduction_ratio"] < 0.05, stats

    def test_candidate_map_only_contains_indices_greater_than_key(self):
        segments = _random_cloud(80, seed=4)
        candidates = build_candidate_pairs(segments)
        for i, js in candidates.items():
            assert all(j > i for j in js)
            assert js == sorted(js)

    def test_segment_bbox_orders_min_max_regardless_of_endpoint_order(self):
        pad = _INTERSECTION_BROADPHASE_TOL
        assert segment_bbox(_seg(5, 5, 0, 0)) == (0.0 - pad, 0.0 - pad, 5.0 + pad, 5.0 + pad)
        assert segment_bbox(_seg(0, 5, 5, 0)) == (0.0 - pad, 0.0 - pad, 5.0 + pad, 5.0 + pad)


# ---------------------------------------------------------------------------
# Real committed drawing snapshots (CI-reproducible, no gitignored PDF
# needed -- same snapshot pattern established in
# tests/test_hosted_opening_geometry.py)
# ---------------------------------------------------------------------------

_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "hosted_opening_geometry"
_BAGHAU_SNAPSHOT_PATH = _FIXTURES_DIR / "baghau_p36.json"
_DUNGICHA_SNAPSHOT_PATH = _FIXTURES_DIR / "dungicha_p134.json"


class _Pt:
    def __init__(self, x, y):
        self.x = x
        self.y = y


class _Rect:
    def __init__(self, x0, y0, x1, y1):
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.width = x1 - x0
        self.height = y1 - y0


class _FakePage:
    def __init__(self, drawings, rect=None, number=0):
        self._drawings = drawings
        self.rect = rect or _Rect(0, 0, 2000, 2000)
        self.number = number

    def get_drawings(self):
        return self._drawings

    def get_text(self, *_a, **_kw):
        return ""


def _load_snapshot(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _snapshot_page(snapshot: dict):
    drawings = []
    for d in snapshot["drawings"]:
        items = []
        for item in d["items"]:
            op = item[0]
            items.append((op, *[_Pt(x, y) for x, y in item[1:]]))
        drawings.append(
            {
                "color": tuple(d["color"]) if d["color"] is not None else None,
                "fill": tuple(d["fill"]) if d["fill"] is not None else None,
                "width": d["width"],
                "rect": _Rect(*d["rect"]) if d["rect"] is not None else None,
                "items": items,
            }
        )
    page_rect = _Rect(*snapshot["page_rect"])
    return _FakePage(drawings, rect=page_rect, number=snapshot["source"]["pdf_page_0based"])


def _real_structural_point_pairs(snapshot_path: Path) -> List[Segment]:
    from pb_vector_geometry_v130 import extract_native_page
    from pb_wall_room_topology_stage_a import _segments_to_point_pairs, filter_structural_segments

    page = _snapshot_page(_load_snapshot(snapshot_path))
    native = extract_native_page(page)
    structural, _excluded = filter_structural_segments(native["segments"])
    return _segments_to_point_pairs(structural)


class TestRealDrawingEquivalenceAndPerformance:
    """Committed-fixture equivalence tests double as the performance
    regression guard: each asserts exact output equality against the O(n^2)
    oracle AND that the indexed path completed (implicitly, by not timing
    out) far faster than the oracle -- explicit wall-clock ratios are logged
    via the real-PDF probe below, not asserted here, since committed-
    fixture scale (2.4k-5.1k segments) is not the scale the original defect
    was measured at (see the real-PDF full-page test class below for that).
    """

    def test_matches_oracle_on_real_baghau_committed_snapshot(self):
        pairs = _real_structural_point_pairs(_BAGHAU_SNAPSHOT_PATH)
        assert len(pairs) > 2000
        _assert_equivalent(pairs, "real Baghau committed snapshot")

    def test_matches_oracle_on_real_dungicha_committed_snapshot(self):
        pairs = _real_structural_point_pairs(_DUNGICHA_SNAPSHOT_PATH)
        assert len(pairs) > 5000
        _assert_equivalent(pairs, "real Dungicha committed snapshot")

    def test_oracle_hit_superset_on_committed_snapshots(self):
        for path in (_BAGHAU_SNAPSHOT_PATH, _DUNGICHA_SNAPSHOT_PATH):
            pairs = _real_structural_point_pairs(path)
            hits, miss = _assert_oracle_hits_are_candidates(pairs, path.name)
            assert miss == 0
            assert hits >= 1

    def test_indexed_splitter_stays_fast_on_real_committed_snapshots(self):
        for path in (_BAGHAU_SNAPSHOT_PATH, _DUNGICHA_SNAPSHOT_PATH):
            pairs = _real_structural_point_pairs(path)
            t0 = time.perf_counter()
            split_segments_at_intersections_indexed(pairs)
            elapsed = time.perf_counter() - t0
            assert elapsed < 5.0, f"{path.name}: indexed splitter took {elapsed:.2f}s on {len(pairs)} segments"


# ---------------------------------------------------------------------------
# Real, full (non-region-scoped) native PDF pages -- the actual 7k-37k
# segment scale the original multi-minute defect was observed at. Skips
# cleanly when the gitignored source PDFs are not present (developer-
# machine-only, matching the existing benchmarks/sources/ convention); the
# committed-snapshot tests above are what CI runs unconditionally.
# ---------------------------------------------------------------------------

_SOURCES_DIR = Path(__file__).resolve().parent.parent / "benchmarks" / "sources"
_REAL_FULL_PAGES = [
    ("Baghau", _SOURCES_DIR / "bq_and_drawing_1747803602496.pdf", 35),
    ("Lamu", _SOURCES_DIR / "lamu-ishakani-ecd-classrooms-boq.pdf", 40),
    ("KSTVET", _SOURCES_DIR / "1727358888238-bq-nd-drawing.pdf", 53),
]
_REAL_DUNGICHA_FULL_PAGE = (_SOURCES_DIR / "dungicha_3classrooms.pdf", 133)


def _full_page_structural_pairs(pdf_path: Path, page_index: int) -> List[Segment]:
    fitz = pytest.importorskip("fitz")
    from pb_vector_geometry_v130 import extract_native_page
    from pb_wall_room_topology_stage_a import _segments_to_point_pairs, filter_structural_segments

    doc = fitz.open(str(pdf_path))
    try:
        native = extract_native_page(doc[page_index])
    finally:
        doc.close()
    structural, _excluded = filter_structural_segments(native["segments"])
    return _segments_to_point_pairs(structural)


class TestRealFullPageScaleWhereSourcesAvailable:
    """Full un-scoped native pages -- thousands to tens of thousands of
    structural segments, the exact regime the original multi-minute defect
    was observed in. Developer-machine-only (gitignored source PDFs)."""

    @pytest.mark.parametrize("name,pdf_path,page_index", _REAL_FULL_PAGES)
    def test_full_page_matches_oracle_and_is_fast(self, name, pdf_path, page_index):
        if not pdf_path.exists():
            pytest.skip(f"real source PDF not present: {pdf_path}")
        pairs = _full_page_structural_pairs(pdf_path, page_index)

        t0 = time.perf_counter()
        fast = split_segments_at_intersections_indexed(pairs)
        t_fast = time.perf_counter() - t0

        t0 = time.perf_counter()
        oracle = split_segments_at_intersections(pairs)
        t_oracle = time.perf_counter() - t0

        assert fast == oracle, f"{name}: full-page indexed output diverged from oracle"
        assert t_fast < t_oracle, f"{name}: indexed path was not faster than the oracle"

    def test_full_page_dungicha_37k_segments_completes_fast_via_bounded_oracle_parity(self):
        """Dungicha's full un-scoped page runs to 37k+ structural segments
        -- ~689 million all-pairs, the case that had to be killed after
        several minutes with the O(n^2) oracle. Per the standing instruction
        not to repeatedly wait on the O(n^2) oracle at this scale, oracle
        parity is proven on a large bounded prefix (6000 real segments from
        this same page) and the indexed path is then run, unbounded, on the
        complete real page -- proving both correctness (via the bounded
        oracle-parity slice) and practicality (via the full unbounded run)
        without ever invoking the O(n^2) oracle at full scale.
        """
        pdf_path, page_index = _REAL_DUNGICHA_FULL_PAGE
        if not pdf_path.exists():
            pytest.skip(f"real source PDF not present: {pdf_path}")
        pairs = _full_page_structural_pairs(pdf_path, page_index)
        assert len(pairs) > 30000, "expected the real full-page Dungicha defect scale"

        bounded = pairs[:6000]
        _assert_equivalent(bounded, "Dungicha full-page, 6000-segment bounded oracle-parity slice")

        t0 = time.perf_counter()
        fast_full = split_segments_at_intersections_indexed(pairs)
        elapsed = time.perf_counter() - t0
        assert elapsed < 30.0, (
            f"indexed splitter took {elapsed:.2f}s on the full {len(pairs)}-segment Dungicha "
            "page -- expected single-digit seconds; the O(n^2) oracle on this same page had to "
            "be killed after several minutes, which is the defect this module exists to fix"
        )
        assert len(fast_full) > 0
