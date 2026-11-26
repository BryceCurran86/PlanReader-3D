"""Production wall source-index parity: no new source authority or scoring."""
from collections import Counter, defaultdict
import random
from types import SimpleNamespace

import pytest

from pb_physical_wall_candidate_authority import (
    _ProvenFilledWallStrip,
    _producer_wall_strip_relation_overrides,
    _source_snap_collapsed_fragment_inventory,
    _line, _segment_geometry, PhysicalWallSnapCollapsedFragment,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY, SNAP_COLLAPSE_REASON


def old_strip(records, strips):
    out = {}
    for strip in strips:
        face = set(strip.face_raw_ids)
        owners = sorted({r.wall_candidate_id for r in records
                         if face & set(r.physical_identity.source_primitive_ids)})
        for i, left in enumerate(owners):
            for right in owners[i + 1:]:
                out[left, right] = PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
    return out


def old_collapsed(graph, identities):
    endpoints = defaultdict(list)
    owners = defaultdict(set)
    for candidate_id, identity in identities.items():
        if identity.usable:
            for edge_id in identity.edge_ids:
                owners[str(edge_id)].add(candidate_id)
    for edge in graph.get("edges", ()):
        line = _line(_segment_geometry(edge))
        parents = frozenset(str(p) for p in (edge.get(LINEAGE_KEY) or {}).get(
            "source_primitive_ids", ()))
        if line is None or not parents:
            continue
        for point, node in ((line[:2], edge.get("a")), (line[2:], edge.get("b"))):
            if node is not None:
                for parent in parents:
                    endpoints[point, parent].append((str(edge["id"]), node, parents))
    inventory = defaultdict(list)
    surviving = {str(e["id"]) for e in graph.get("edges", ())}
    collapsed = tuple(graph.get("snap_collapsed_fragments", ()))
    counts = Counter(str(f.get("id") or "") for f in collapsed)
    for f in collapsed:
        key = str(f.get("id") or "")
        line = _line(_segment_geometry(f))
        parents = frozenset(str(p) for p in (f.get(LINEAGE_KEY) or {}).get(
            "source_primitive_ids", ()))
        if (f.get("reason") != SNAP_COLLAPSE_REASON or not key or key in surviving
                or counts[key] != 1 or line is None or not parents):
            continue
        parent = min(parents)
        candidates = set()
        for left_id, left_node, left_parents in endpoints[line[:2], parent]:
            for right_id, right_node, right_parents in endpoints[line[2:], parent]:
                if (left_id == right_id or left_node != right_node
                        or not parents <= left_parents & right_parents):
                    continue
                candidates.update(owners[left_id] & owners[right_id])
        if len(candidates) != 1:
            continue
        candidate = next(iter(candidates))
        if not parents <= set(identities[candidate].source_primitive_ids):
            continue
        inventory[candidate].append(PhysicalWallSnapCollapsedFragment(
            edge_id=key, geometry=line, source_primitive_ids=tuple(sorted(parents))))
    return {cid: tuple(sorted(rows, key=lambda row: row.edge_id))
            for cid, rows in inventory.items()}


def strip(i):
    return _ProvenFilledWallStrip(i, (f"p{i}a", f"p{i}b"),
        (f"p{i}a", f"p{i}b"), ((0.,0.),(1.,0.),(1.,1.),(0.,1.)))


def edge(key, x1, x2, a, b, parents):
    return {"id":key, "x1":x1, "y1":1., "x2":x2, "y2":1.,
        "a":a, "b":b, LINEAGE_KEY: {"source_primitive_ids":list(parents)}}


def test_no_filled_wall_strips_skip_source_membership_index():
    class UnusedWall:
        @property
        def physical_identity(self):
            pytest.fail("empty strip input must not inspect wall membership")

    assert _producer_wall_strip_relation_overrides(records=(UnusedWall(),), strips=()) == {}


def test_no_collapsed_fragments_skip_edge_and_owner_indexes():
    class UnusedItems(dict):
        def items(self):
            pytest.fail("empty fragment input must not inspect wall membership")

    class UnusedEdges:
        def __iter__(self):
            pytest.fail("empty fragment input must not inspect surviving edges")

    graph = {"edges": UnusedEdges(), "snap_collapsed_fragments": ()}
    assert _source_snap_collapsed_fragment_inventory(graph, UnusedItems()) == {}


def test_authentic_strip_owner_lookup_preserves_legacy_random_source_owners():
    rng = random.Random(23091)
    strips = tuple(strip(i) for i in range(60))
    for _ in range(24):
        records = [
            SimpleNamespace(wall_candidate_id=f"wall{i}", physical_identity=SimpleNamespace(
                source_primitive_ids=tuple(rng.choice((
                    f"p{rng.randrange(60)}a", f"p{rng.randrange(60)}b", "unrelated"
                )) for _ in range(rng.randrange(5)))))
            for i in range(150)
        ]
        expected = old_strip(records, strips)
        assert _producer_wall_strip_relation_overrides(records=records, strips=strips) == expected
        rng.shuffle(records)
        assert _producer_wall_strip_relation_overrides(records=records, strips=strips) == expected


def test_collapsed_endpoints_preserve_quadratic_oracle_random_competitors():
    rng = random.Random(12389)
    for _ in range(90):
        edges = []
        for i in range(42):
            node = rng.randrange(5)
            parents = rng.choice((("p",), ("p","q"), ("q",), ("p","r")))
            if i % 2:
                edges.append(edge(f"e{i}", 2., 3.+i, node, 200+i, parents))
            else:
                edges.append(edge(f"e{i}", -3.-i, 0., 200+i, node, parents))
        f = edge("lost", 0., 2., 1, 1, ("p",))
        f["reason"] = SNAP_COLLAPSE_REASON
        graph = {"edges": edges, "snap_collapsed_fragments":[f]}
        ids = {f"wall{k}":SimpleNamespace(usable=k<4,
              edge_ids=tuple(e["id"] for e in edges if rng.randrange(4)==0),
              source_primitive_ids=("p","q") if k<3 else ("p",))
              for k in range(6)}
        expected = old_collapsed(graph, ids)
        assert _source_snap_collapsed_fragment_inventory(graph, ids) == expected
        rng.shuffle(edges)
        assert _source_snap_collapsed_fragment_inventory(graph, ids) == expected


def test_one_source_edge_can_never_fake_two_edge_closure():
    e = edge("same", 0., 2., 4, 4, ("p",))
    f = {**e, "id":"lost", "reason":SNAP_COLLAPSE_REASON}
    graph = {"edges":[e], "snap_collapsed_fragments":[f]}
    ids = {"wall": SimpleNamespace(usable=True,edge_ids=("same",),source_primitive_ids=("p",))}
    assert _source_snap_collapsed_fragment_inventory(graph, ids) == old_collapsed(graph, ids) == {}


def test_dense_same_node_witnesses_retained_without_pairwise_scan():
    edges = []
    for i in range(700):
        edges += [edge(f"L{i}", -i-1., 0., 2000+i, 1, ("p",)),
                  edge(f"R{i}", 2., i+3., 1, 3000+i, ("p",))]
    f = edge("lost", 0., 2., 1, 1, ("p",))
    f["reason"] = SNAP_COLLAPSE_REASON
    graph = {"edges":edges,"snap_collapsed_fragments":[f]}
    ids = {"wall":SimpleNamespace(usable=True,
            edge_ids=tuple(e["id"] for e in edges),source_primitive_ids=("p",))}
    expected = old_collapsed(graph, ids)
    assert _source_snap_collapsed_fragment_inventory(graph, ids) == expected
    assert expected["wall"][0].edge_id == "lost"
