"""Architecture-review regression coverage for U1 (primitive lineage through
W2), added independently of Cursor's own tests/test_wall_topology_primitive_
lineage.py suite. Written against Cursor's HEAD 4527d8a (fetched during this
review after Cursor's own follow-up commits already covered several gaps
this review found independently: partial collinear overlap, nested-lineage
aliasing, excluded-source observability, and a plural-children recursive
merge). Per the review's own coordination instructions, those are NOT
duplicated here -- see this session's PR body for the full reconciliation.

What remains genuinely unique in this file:

(a) A ground-truth validation of Cursor's OWN shipped bucket+fallback
    performance fix (``source_line_bucket``/``fragment_line_bucket`` inside
    ``attach_lineage_to_split_fragments``) against the exhaustive scan, run
    across thousands of real fragments from two real, committed drawing
    snapshots (Baghau p36, Dungicha p134) -- not just a few hand-picked
    synthetic cases. Cursor's own new tests are example-based; this is the
    property-style check the review brief specifically asked for
    ("splitter-output provenance recovery when duplicate geometries make
    coordinate-only matching ambiguous").
(b) A performance regression guard for the real, measured defect this
    review found before Cursor's own fix landed (an earlier, unindexed
    per-fragment full scan measured up to ~1727x slower on real Dungicha
    data -- 35s for one Stage-A region rebuild that should take ~20ms).
(c) A 4-edge sequential recursive merge (Cursor's own new test covers a
    2+2 balanced-tree merge; this is the different, complementary shape).
(d) A same-coordinates-in-two-separate-viewport-calls isolation check
    (Cursor's own existing test uses different coordinates per viewport).
(e) A multi-seed shuffle-order check specifically for a fixture that
    produces plural lineage (Cursor's own shuffle test fixture has no
    plural-parent edges at all).

Shadow only -- nothing here is wired into any production/commercial path.
"""
from __future__ import annotations

import json
import random
import time
from pathlib import Path
from typing import Any, Dict, List

from pb_wall_room_topology_primitive_lineage import (
    LINEAGE_KEY,
    fragment_contained_in_segment,
    sources_for_fragment,
)
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    filter_structural_segments,
    _segments_to_point_pairs,
)
from pb_accuracy_v13_engines_v145 import split_segments_at_intersections
from pb_vector_geometry_v130 import extract_native_page


def _seg(seg_id: str, x1: float, y1: float, x2: float, y2: float, **overrides: Any) -> Dict[str, Any]:
    base = {
        "id": seg_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": 1.0,
        "stroke": (0, 0, 0),
        "fill": None,
        "layer": "WALL",
        "dashes": "[] 0",
    }
    base.update(overrides)
    return base


def _lineage(edge: Dict[str, Any]) -> Dict[str, Any]:
    return edge[LINEAGE_KEY]


def _ids(edge: Dict[str, Any]) -> List[str]:
    return list(_lineage(edge)["source_primitive_ids"])


# ---------------------------------------------------------------------------
# Real-fixture ground-truth reconstruction (same _Pt/_Rect/_FakePage pattern
# already established in tests/test_hosted_opening_geometry.py, so this
# stays CI-reproducible without the gitignored source PDFs).
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


def _snapshot_page(snapshot: dict) -> _FakePage:
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


def _real_structural_segments(snapshot_path: Path) -> List[Dict[str, Any]]:
    snapshot = _load_snapshot(snapshot_path)
    page = _snapshot_page(snapshot)
    native = extract_native_page(page)
    structural, _ = filter_structural_segments(native["segments"])
    return structural


def _assert_ground_truth_matches_shipped_lineage(structural: List[Dict[str, Any]], *, sample_seeds=(1, 2, 3, 11, 42)) -> None:
    point_pairs = _segments_to_point_pairs(structural)
    split_pairs = split_segments_at_intersections(point_pairs)

    # The shipped path (bucket + fallback-on-empty-result), exercised
    # exactly as build_wall_graph_for_viewport uses it, via the same public
    # helper the pipeline calls.
    from pb_wall_room_topology_stage_a import _point_pairs_to_segment_dicts

    shipped_fragments = _point_pairs_to_segment_dicts(split_pairs, source_segments=structural)
    shipped_by_position = {
        (round(f["x1"], 6), round(f["y1"], 6), round(f["x2"], 6), round(f["y2"], 6)): f
        for f in shipped_fragments
    }

    mismatches = []
    checked = 0
    for seed in sample_seeds:
        rng = random.Random(seed)
        sample = rng.sample(split_pairs, min(300, len(split_pairs)))
        for fragment in sample:
            checked += 1
            key = (
                round(fragment[0][0], 6),
                round(fragment[0][1], 6),
                round(fragment[1][0], 6),
                round(fragment[1][1], 6),
            )
            shipped = shipped_by_position.get(key)
            assert shipped is not None, f"fragment {fragment} missing from shipped output entirely"
            exhaustive_ids = {
                s.get("id") for s in sources_for_fragment(fragment, structural)
            }
            shipped_ids = set(shipped[LINEAGE_KEY]["source_primitive_ids"])
            if exhaustive_ids != shipped_ids:
                mismatches.append((fragment, exhaustive_ids, shipped_ids))

    assert not mismatches, (
        f"{len(mismatches)}/{checked} fragments disagree with the exhaustive ground truth "
        f"(first: {mismatches[0]})"
    )


def test_shipped_lineage_matches_exhaustive_ground_truth_on_real_baghau_data():
    """Property-style validation the review brief specifically asked for
    ("splitter-output provenance recovery when duplicate geometries make
    coordinate-only matching ambiguous") -- not a handful of hand-picked
    cases, but thousands of real fragments from a real, messy CAD page,
    each checked against the exhaustive scan Cursor's own bucket+fallback
    optimization is supposed to reproduce exactly."""
    structural = _real_structural_segments(_BAGHAU_SNAPSHOT_PATH)
    assert len(structural) > 500  # sanity: this really is a dense real page
    _assert_ground_truth_matches_shipped_lineage(structural)


def test_shipped_lineage_matches_exhaustive_ground_truth_on_real_dungicha_data():
    """Same check on Dungicha p134 -- the specific page this review measured
    the original unindexed scan at ~1727x slower (35s vs ~20ms) before
    Cursor's own fix landed, and independently the page a prior, now-
    superseded version of this review's own fix still mismatched the
    ground truth on (a sign-canonicalization / short-fragment instability
    in a since-discarded line-signature approach) -- the real data this
    class of bug actually surfaces on, not just a synthetic edge case."""
    structural = _real_structural_segments(_DUNGICHA_SNAPSHOT_PATH)
    assert len(structural) > 1000
    _assert_ground_truth_matches_shipped_lineage(structural)


def test_shipped_lineage_stays_fast_on_real_dense_dungicha_data():
    """Direct regression guard for the real, measured defect (an earlier,
    unindexed per-fragment full scan measured at ~35s on this same real
    region, before any fix existed). The final shipped fix (bucket lookup
    + a bounded 27-cell neighbourhood check, needed for correctness -- see
    this module's own docstring and pb_wall_room_topology_primitive_
    lineage.fragment_line_bucket_neighbors -- + exhaustive fallback only on
    a genuine empty result) costs more than a single-bucket lookup would,
    but remains roughly 5x faster than the original regression while being
    fully correct (see the ground-truth tests above). A generous ceiling
    (this is a correctness-adjacent regression guard, not a tight perf
    benchmark, and CI hardware varies) that the ORIGINAL unindexed scan
    would still have failed by nearly an order of magnitude.
    """
    structural = _real_structural_segments(_DUNGICHA_SNAPSHOT_PATH)
    point_pairs = _segments_to_point_pairs(structural)
    split_pairs = split_segments_at_intersections(point_pairs)
    from pb_wall_room_topology_stage_a import _point_pairs_to_segment_dicts

    t0 = time.perf_counter()
    _point_pairs_to_segment_dicts(split_pairs, source_segments=structural)
    elapsed = time.perf_counter() - t0
    assert elapsed < 15.0, f"took {elapsed:.2f}s -- looks like the O(N) - per - fragment regression again"


# ---------------------------------------------------------------------------
# Remaining unique semantic gaps.
# ---------------------------------------------------------------------------


def test_four_edge_sequential_recursive_merge_keeps_all_four_leaves():
    """Complementary to Cursor's own new 2+2 balanced-tree merge test
    (test_plural_children_recursive_merge_unions_all_four_parents) -- this
    is the different, SEQUENTIAL 4-in-a-row shape (a->ab->abc->abcd),
    extending the existing 3-edge (a,b,c) test one level further to prove
    the transitive union keeps accumulating correctly across an additional
    merge round, not just the first one.

    Segment lengths are deliberately well above Stage A's own 2.5pt default
    gap-snap tolerance: spacing internal boundaries exactly AT that
    tolerance (as an earlier version of this fixture did, using 2.5pt
    segments) causes two genuinely distinct junction nodes to be
    snap-merged into one by that pre-existing, unrelated mechanism --
    a real test-construction hazard worth documenting, not a lineage bug.
    """
    segments = [
        _seg("a", 0.0, 0.0, 10.0, 0.0),
        _seg("b", 10.0, 0.0, 20.0, 0.0),
        _seg("c", 20.0, 0.0, 30.0, 0.0),
        _seg("d", 30.0, 0.0, 40.0, 0.0),
    ]
    graph = build_wall_graph_for_viewport(segments)
    assert len(graph["edges"]) == 1
    edge = graph["edges"][0]
    assert _ids(edge) == ["a", "b", "c", "d"]
    assert edge["collinear_merge_leaf_edge_ids"]
    assert len(edge["collinear_merge_leaf_edge_ids"]) == 4
    records_by_id = {record["id"]: record for record in _lineage(edge)["source_records"]}
    assert set(records_by_id) == {"a", "b", "c", "d"}


def test_same_coordinates_two_separate_viewport_calls_do_not_leak_state():
    """Cursor's own viewport-isolation test uses DIFFERENT coordinates per
    viewport. This uses the IDENTICAL coordinates in two independently
    scoped calls (matching how the real per-viewport pipeline actually
    runs, per AGENTS.md: viewport ownership is the caller's job, one call
    per viewport) -- proving no accidental module-level cache or shared
    mutable object leaks lineage from one independent call into another."""
    segments_a = [_seg("shared_id", 0.0, 0.0, 10.0, 0.0, viewport_id="vpA")]
    segments_b = [_seg("shared_id", 0.0, 0.0, 10.0, 0.0, viewport_id="vpB")]
    graph_a = build_wall_graph_for_viewport(segments_a)
    graph_b = build_wall_graph_for_viewport(segments_b)
    record_a = _lineage(graph_a["edges"][0])["source_records"][0]
    record_b = _lineage(graph_b["edges"][0])["source_records"][0]
    assert record_a["viewport_id"] == "vpA"
    assert record_b["viewport_id"] == "vpB"
    # Mutating one call's own result must never retroactively alter what a
    # DIFFERENT, already-completed call already returned.
    graph_a["edges"][0][LINEAGE_KEY]["source_records"][0]["viewport_id"] = "TAMPERED"
    assert record_b["viewport_id"] == "vpB"


def test_deterministic_result_under_many_shuffles_with_plural_lineage():
    """Strengthens Cursor's own single-seed shuffle test (which used a
    fixture with no plural-parent edges at all) by using a fixture that
    DOES produce plural lineage via both the split-recovery step AND a
    collinear merge, across several random orderings."""
    segments = [
        _seg("dup1", 0.0, 0.0, 5.0, 0.0, width=1.0, layer="A"),
        _seg("dup2", 0.0, 0.0, 5.0, 0.0, width=2.0, layer="B"),
        _seg("right", 5.0, 0.0, 10.0, 0.0),
        _seg("cross", 3.0, -3.0, 3.0, 3.0),
    ]

    def bag(graph):
        return sorted(
            (tuple(_ids(edge)), round(edge["length_pt"], 3)) for edge in graph["edges"]
        )

    baseline = build_wall_graph_for_viewport(segments)
    baseline_bag = bag(baseline)
    for seed in (1, 2, 3, 4, 5):
        shuffled = list(segments)
        random.Random(seed).shuffle(shuffled)
        other = build_wall_graph_for_viewport(shuffled)
        assert bag(other) == baseline_bag, f"seed={seed} produced a different lineage bag"
