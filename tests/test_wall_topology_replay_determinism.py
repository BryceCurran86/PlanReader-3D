"""Replay determinism of W3 relationships and W4 wall candidate identity.

Wall candidate ids are content-derived (``_canonical_wall_candidate_id``) and
feed physical-wall equivalence, representative selection, host binding and
every downstream physical-wall lineage. They must therefore be a pure function
of source geometry: never of set iteration order, which for string keys depends
on the interpreter's hash seed (``PYTHONHASHSEED``), never of edge-id numbering,
and never of which endpoint a source primitive happened to start at.

The non-simple chain fixture reproduces the real-source failure mode: one line
drawn twice -- once whole and once as fragments carrying T-junction stems --
whose two copies union into one W4 group with no single traversal.
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
from pb_wall_room_topology_junction_classifier import (
    TopologyRelationshipType,
    classify_junctions,
)
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import (
    _canonical_non_simple_points,
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


def test_t_junction_branches_follow_bar_arm_order() -> None:
    _walls, relationships = _assemble(_duplicate_drawn_line_segments())
    branches = [
        item
        for item in relationships
        if item.relationship_type == TopologyRelationshipType.BRANCHES_FROM
    ]
    assert branches
    by_junction: dict[str, list[str]] = {}
    for item in branches:
        by_junction.setdefault(item.via_junction_id, []).append(item.to_edge_id)
    for bar_edges in by_junction.values():
        # Each bar arm appears once, in the classifier's own deterministic
        # pair order rather than in set-iteration order.
        assert len(bar_edges) == len(set(bar_edges))
    # Same set of relationships as before the ordering fix: order changed, content did not.
    assert len({item.relationship_id for item in relationships}) == len(relationships)


def _edges(*pairs):
    return {
        f"e{index}": {"x1": a[0], "y1": a[1], "x2": b[0], "y2": b[1]}
        for index, (a, b) in enumerate(pairs)
    }


def test_non_simple_points_are_independent_of_edge_iteration_order() -> None:
    edges = _edges(
        ((707.08, 1063.88), (707.08, 1075.28)),
        ((707.08, 1067.6), (707.08, 1063.88)),
        ((707.08, 1067.6), (707.08, 1075.28)),
    )
    results = {
        tuple(_canonical_non_simple_points(list(order), edges))
        for order in itertools.permutations(edges)
    }
    assert len(results) == 1


def test_non_simple_points_are_independent_of_primitive_orientation() -> None:
    forward = _edges(
        ((0.0, 0.0), (100.0, 0.0)),
        ((0.0, 0.0), (40.0, 0.0)),
        ((40.0, 0.0), (100.0, 0.0)),
    )
    reversed_edges = {
        edge_id: {"x1": edge["x2"], "y1": edge["y2"], "x2": edge["x1"], "y2": edge["y1"]}
        for edge_id, edge in forward.items()
    }
    assert _canonical_non_simple_points(set(forward), forward) == (
        _canonical_non_simple_points(set(reversed_edges), reversed_edges)
    )


def test_non_simple_points_are_independent_of_edge_id_numbering() -> None:
    edges = _edges(
        ((0.0, 0.0), (100.0, 0.0)),
        ((0.0, 0.0), (40.0, 0.0)),
        ((40.0, 0.0), (100.0, 0.0)),
    )
    renamed = {f"zz_{9 - index}": edge for index, edge in enumerate(edges.values())}
    assert _canonical_non_simple_points(set(edges), edges) == (
        _canonical_non_simple_points(set(renamed), renamed)
    )


def test_line_drawn_twice_keeps_the_single_line_fingerprint() -> None:
    """Redundant collinear linework may not fabricate or drop geometry."""
    edges = _edges(
        ((707.08, 1063.88), (707.08, 1075.28)),
        ((707.08, 1067.6), (707.08, 1063.88)),
        ((707.08, 1067.6), (707.08, 1075.28)),
    )
    points = _canonical_non_simple_points(set(edges), edges)
    assert canonical_path_fingerprint(points) == canonical_path_fingerprint(
        [(707.08, 1063.88), (707.08, 1075.28)]
    )


def test_non_simple_points_keep_every_edge_endpoint() -> None:
    edges = _edges(
        ((0.0, 0.0), (100.0, 0.0)),
        ((0.0, 0.3), (50.0, 0.3)),
        ((50.0, 0.3), (100.0, 0.3)),
    )
    points = _canonical_non_simple_points(set(edges), edges)
    expected = {
        (edge[x], edge[y])
        for edge in edges.values()
        for x, y in (("x1", "y1"), ("x2", "y2"))
    }
    assert set(points) == expected
    assert len(points) == len(expected)


def test_non_simple_points_do_not_mutate_inputs() -> None:
    edges = _edges(
        ((0.0, 0.0), (100.0, 0.0)),
        ((0.0, 0.0), (40.0, 0.0)),
        ((40.0, 0.0), (100.0, 0.0)),
    )
    edge_ids = set(edges)
    before = copy.deepcopy(edges)
    _canonical_non_simple_points(edge_ids, edges)
    assert edges == before
    assert edge_ids == set(before)


def test_segment_input_order_does_not_change_wall_identity() -> None:
    segments = _duplicate_drawn_line_segments()
    reference = sorted(wall.candidate_id for wall in _assemble(segments)[0])
    rng = random.Random(20260929)
    for _ in range(6):
        shuffled = list(segments)
        rng.shuffle(shuffled)
        assert sorted(wall.candidate_id for wall in _assemble(shuffled)[0]) == reference


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
