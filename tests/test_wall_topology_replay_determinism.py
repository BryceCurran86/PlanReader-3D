"""Replay determinism of W3 relationships and W4 wall candidate identity.

Wall candidate ids are content-derived (``_canonical_wall_candidate_id``) and
feed physical-wall equivalence, representative selection, host binding and
every downstream physical-wall lineage. They must therefore be a pure function
of source geometry: never of set iteration order, which for string keys depends
on the interpreter's hash seed (``PYTHONHASHSEED``), never of edge-id numbering,
and never of which endpoint a source primitive happened to start at.

The non-simple chain fixture reproduces the real-source failure mode: one line
drawn twice -- once whole and once as fragments carrying T-junction stems --
whose two copies union into one W4 group with no single traversal. The fix is
deliberately order-only: the fallback keeps exactly the points it used before,
so every result is one the previous implementation could already produce.
"""
from __future__ import annotations

import copy
import itertools
import json
import os
import random
import subprocess
import sys
from pathlib import Path

import pytest

from pb_migration_contracts import stable_contract_id
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import (
    _canonical_fallback_edge_order,
    _order_chain_path,
    assemble_wall_topology,
)
from pb_wall_room_topology_wall_identity_v2 import canonical_path_fingerprint


REPO_ROOT = Path(__file__).resolve().parents[1]
NON_SIMPLE = "non_simple_chain_topology_fallback_ordering"
HASH_SEEDS = (0, 1, 2, 3, 4, 5)


def _seg(seg_id, x1, y1, x2, y2):
    return {
        "id": seg_id,
        "kind": "line",
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        "width": 1.0,
        "stroke": (0, 0, 0),
        "fill": None,
        "layer": "",
        "dashes": "",
    }


def _duplicate_drawn_line_segments(dx: float = 0.0, dy: float = 0.0):
    """A line drawn whole plus the same line drawn as stemmed fragments."""
    segments = [_seg("whole", 0.0 + dx, 0.1 + dy, 300.0 + dx, 0.1 + dy)]
    xs = [0.25, 60.0, 120.0, 180.0, 240.0, 300.0]
    for index, (start, end) in enumerate(zip(xs, xs[1:])):
        segments.append(_seg(f"frag_{index}", start + dx, 0.0 + dy, end + dx, 0.0 + dy))
    for index, x in enumerate(xs[1:-1]):
        segments.append(_seg(f"stem_{index}", x + dx, 0.0 + dy, x + dx, -80.0 + dy))
    # One ordinary T-junction elsewhere so W3 emits branches_from relations.
    segments.append(_seg("bar", 0.0 + dx, 200.0 + dy, 300.0 + dx, 200.0 + dy))
    segments.append(_seg("stem_t", 150.0 + dx, 200.0 + dy, 150.0 + dx, 300.0 + dy))
    return segments


def _assemble(segments):
    graph = build_wall_graph_for_viewport(segments)
    junctions, relationships = classify_junctions(
        graph, document_id="doc", page_id="1", viewport_id="vp"
    )
    walls, _ = assemble_wall_topology(graph, junctions, relationships, viewport_id="vp")
    return walls, relationships


_SUBPROCESS_PROBE = r"""
import json
from tests.test_wall_topology_replay_determinism import (
    _assemble,
    _duplicate_drawn_line_segments,
    NON_SIMPLE,
)
walls, relationships = _assemble(_duplicate_drawn_line_segments())
print(json.dumps({
    "wall_ids": sorted(wall.candidate_id for wall in walls),
    "non_simple_ids": sorted(
        wall.candidate_id for wall in walls if NON_SIMPLE in wall.reason_codes
    ),
    "non_simple_points": [
        [list(point) for point in wall.centerline_pts]
        for wall in sorted(walls, key=lambda item: item.candidate_id)
        if NON_SIMPLE in wall.reason_codes
    ],
    "relationship_order": [item.relationship_id for item in relationships],
}))
"""


def _probe_under_hash_seed(seed: int) -> dict:
    env = dict(os.environ)
    env["PYTHONHASHSEED"] = str(seed)
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_PROBE],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
        check=True,
    )
    return json.loads(completed.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def probes_by_seed() -> dict[int, dict]:
    return {seed: _probe_under_hash_seed(seed) for seed in HASH_SEEDS}


def test_fixture_exercises_the_non_simple_chain_path() -> None:
    walls, _ = _assemble(_duplicate_drawn_line_segments())
    non_simple = [wall for wall in walls if NON_SIMPLE in wall.reason_codes]
    assert len(non_simple) == 1
    assert len(non_simple[0].face_a_segment_ids) >= 3


def test_wall_candidate_ids_are_independent_of_hash_seed(probes_by_seed) -> None:
    reference = probes_by_seed[HASH_SEEDS[0]]
    assert len(reference["non_simple_ids"]) == 1
    for seed, probe in probes_by_seed.items():
        assert probe["wall_ids"] == reference["wall_ids"], seed
        assert probe["non_simple_ids"] == reference["non_simple_ids"], seed
        assert probe["non_simple_points"] == reference["non_simple_points"], seed


def test_w3_relationship_order_is_independent_of_hash_seed(probes_by_seed) -> None:
    reference = probes_by_seed[HASH_SEEDS[0]]["relationship_order"]
    assert reference
    for seed, probe in probes_by_seed.items():
        assert probe["relationship_order"] == reference, seed


def _edges(*pairs):
    return {
        f"e{index}": {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]}
        for index, (a, b) in enumerate(pairs)
    }


def test_fallback_edge_order_is_independent_of_iteration_order() -> None:
    edges = _edges(
        ((707.08, 1063.88), (707.08, 1075.28)),
        ((707.08, 1067.6), (707.08, 1063.88)),
        ((707.08, 1067.6), (707.08, 1075.28)),
    )
    orders = {
        tuple(_canonical_fallback_edge_order(list(order), edges))
        for order in itertools.permutations(edges)
    }
    assert len(orders) == 1


def test_fallback_edge_order_does_not_depend_on_edge_id_numbering() -> None:
    edges = _edges(
        ((0.0, 0.0), (100.0, 0.0)),
        ((0.0, 0.3), (50.0, 0.3)),
        ((50.0, 0.3), (100.0, 0.3)),
    )
    renamed = {f"zz_{9 - index}": edge for index, edge in enumerate(edges.values())}
    by_geometry = lambda mapping, order: [  # noqa: E731
        (mapping[edge_id]["x1"], mapping[edge_id]["y1"], mapping[edge_id]["x2"], mapping[edge_id]["y2"])
        for edge_id in order
    ]
    assert by_geometry(edges, _canonical_fallback_edge_order(set(edges), edges)) == by_geometry(
        renamed, _canonical_fallback_edge_order(set(renamed), renamed)
    )


def test_fallback_keeps_exactly_the_previous_point_multiset() -> None:
    """Order-only fix: the same start points the old fallback used, nothing added or dropped."""
    edges = {
        "e0": {"a": 0, "b": 1, "x1": 0.0, "y1": 0.1, "x2": 300.0, "y2": 0.1},
        "e1": {"a": 0, "b": 2, "x1": 0.25, "y1": 0.0, "x2": 120.0, "y2": 0.0},
        "e2": {"a": 2, "b": 1, "x1": 120.0, "y1": 0.0, "x2": 300.0, "y2": 0.0},
    }
    nodes = {0: {"x": 0.0, "y": 0.05}, 1: {"x": 300.0, "y": 0.05}, 2: {"x": 120.0, "y": 0.0}}
    points, _start, _end, is_simple = _order_chain_path(set(edges), edges, nodes)
    assert is_simple is False
    assert sorted(points) == sorted((edge["x1"], edge["y1"]) for edge in edges.values())


def test_fallback_order_does_not_mutate_inputs() -> None:
    edges = _edges(
        ((0.0, 0.0), (100.0, 0.0)),
        ((0.0, 0.0), (40.0, 0.0)),
        ((40.0, 0.0), (100.0, 0.0)),
    )
    edge_ids = set(edges)
    before = copy.deepcopy(edges)
    _canonical_fallback_edge_order(edge_ids, edges)
    assert edges == before
    assert edge_ids == set(before)


def test_simple_wall_ids_are_independent_of_segment_input_order() -> None:
    segments = _duplicate_drawn_line_segments()

    def simple_ids(items):
        return sorted(
            wall.candidate_id
            for wall in _assemble(items)[0]
            if NON_SIMPLE not in wall.reason_codes
        )

    reference = simple_ids(segments)
    rng = random.Random(20260929)
    for _ in range(6):
        shuffled = list(segments)
        rng.shuffle(shuffled)
        assert simple_ids(shuffled) == reference


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Pre-existing, out of scope for this replay fix: the non-simple fallback "
        "keeps each edge's start point and W2 merged-edge orientation follows "
        "segment input order. Making the fallback orientation-free changes "
        "physical-wall equivalence outcomes and needs its own authority review."
    ),
)
def test_non_simple_wall_id_is_independent_of_segment_input_order() -> None:
    segments = _duplicate_drawn_line_segments()

    def non_simple_ids(items):
        return sorted(
            wall.candidate_id
            for wall in _assemble(items)[0]
            if NON_SIMPLE in wall.reason_codes
        )

    reference = non_simple_ids(segments)
    rng = random.Random(20260929)
    for _ in range(12):
        shuffled = list(segments)
        rng.shuffle(shuffled)
        assert non_simple_ids(shuffled) == reference


def test_translation_moves_the_non_simple_path_with_the_geometry() -> None:
    base_walls, _ = _assemble(_duplicate_drawn_line_segments())
    moved_walls, _ = _assemble(_duplicate_drawn_line_segments(dx=37.5, dy=-12.25))
    base = next(wall for wall in base_walls if NON_SIMPLE in wall.reason_codes)
    moved = next(wall for wall in moved_walls if NON_SIMPLE in wall.reason_codes)
    assert [
        (round(x + 37.5, 6), round(y - 12.25, 6)) for x, y in base.centerline_pts
    ] == [(round(x, 6), round(y, 6)) for x, y in moved.centerline_pts]


def test_simple_chain_identity_formula_is_unchanged() -> None:
    walls, _ = _assemble(_duplicate_drawn_line_segments())
    simple = [wall for wall in walls if NON_SIMPLE not in wall.reason_codes]
    assert simple
    for wall in simple:
        assert wall.candidate_id == stable_contract_id(
            "wall",
            {
                "viewport_id": "vp",
                "path_fingerprint": canonical_path_fingerprint(wall.centerline_pts),
            },
        )
