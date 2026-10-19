"""W5 source-owner ambiguity shadow: source-safe, production-default unchanged."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from random import Random

import pytest

import pb_wall_room_topology_room_faces as w5
from pb_migration_contracts import EvidenceResolutionStatus


BOX = [(0., 0.), (100., 0.), (100., 100.), (0., 100.)]


def _fixture(monkeypatch, *, conflicting_wall=False, conflicting_component=False):
    """Original producer-shaped graph without invoking a second snap engine."""
    nodes = [{"id": i, "x": point[0], "y": point[1]}
             for i, point in enumerate(BOX)]
    edges = []
    mapping = {}
    for idx, p in enumerate(BOX):
        q = BOX[(idx + 1) % len(BOX)]
        eid = "src_" + str(idx)
        edges.append(dict(id=eid, a=idx, b=(idx + 1) % len(BOX),
                          x1=p[0], y1=p[1], x2=q[0], y2=q[1]))
        mapping[eid] = "w4_" + str(idx)
    if conflicting_wall:
        # Two independent source address owners collapse onto the exact
        # same W5 geometric boundary key. No last/first W4 owner is valid.
        edges.append(dict(edges[0], id="rival_original_source"))
        mapping["rival_original_source"] = "different_w4_owner"
    if conflicting_component:
        # A geometrically coincident endpoint belonging to another W2
        # connected component cannot prove original source identity.
        nodes.extend(({"id": 4, "x": 0., "y": 0.},
                      {"id": 5, "x": 300., "y": 0.}))
        edges.append(dict(id="unrelated", a=4, b=5,
                          x1=0., y1=0., x2=300., y2=0.))
        mapping["unrelated"] = "unrelated_w4_owner"
    graph = {"nodes": nodes, "edges": edges}
    # Dedicated W5 boundary test uses independent producer-shaped W2
    # receipts and leaves both original contenders visible; W3 source
    # dedup belongs to a separate upstream negative contract.
    monkeypatch.setattr(w5, "deduplicate_coincident_edges",
                        lambda graph: (graph, ()))
    monkeypatch.setattr(w5, "extract_planar_faces",
                        lambda segments, **kwargs: [BOX])
    return graph, mapping


def _rooms(graph, mapping, *, shadow=False):
    return w5.reconstruct_room_candidates(
        graph, mapping, document_id="sha-pinned-document",
        viewport_id="source-viewport", source_page=7,
        source_boundary_owner_conflicts_shadow=shadow
    )


def test_complete_single_original_source_wall_owner_keeps_exact_default(monkeypatch):
    graph, mapping = _fixture(monkeypatch)
    original_graph, original_map = deepcopy(graph), deepcopy(mapping)
    default = _rooms(graph, mapping)
    shadow = _rooms(graph, mapping, shadow=True)
    assert len(default) == len(shadow) == 1
    assert asdict(shadow[0]) == asdict(default[0])
    assert shadow[0].status is EvidenceResolutionStatus.CANDIDATE
    assert len(shadow[0].bounding_wall_candidate_ids) == 4
    assert graph == original_graph and mapping == original_map


@pytest.mark.parametrize("seed", range(10))
def test_two_w4_owners_same_source_geometry_abstain_without_electing_one(monkeypatch, seed):
    graph, mapping = _fixture(monkeypatch, conflicting_wall=True)
    Random(seed).shuffle(graph["edges"])
    baseline = _rooms(graph, mapping)
    shadow = _rooms(graph, mapping, shadow=True)
    assert len(baseline) == len(shadow) == 1
    assert baseline[0].status is EvidenceResolutionStatus.CANDIDATE
    assert shadow[0].status is EvidenceResolutionStatus.ABSTAINED
    assert "source_boundary_competing_w4_owners" in shadow[0].reason_codes
    assert "different_w4_owner" not in shadow[0].bounding_wall_candidate_ids
    assert "w4_0" not in shadow[0].bounding_wall_candidate_ids
    assert len(shadow[0].bounding_wall_candidate_ids) == 3
    assert shadow[0].floor_area_m2 is None
    assert shadow[0].geometry_confidence == 0


def test_duplicate_source_component_at_room_vertex_abstains(monkeypatch):
    graph, mapping = _fixture(monkeypatch, conflicting_component=True)
    original = _rooms(graph, mapping)
    shadow = _rooms(graph, mapping, shadow=True)
    assert original[0].status is EvidenceResolutionStatus.CANDIDATE
    assert shadow[0].status is EvidenceResolutionStatus.ABSTAINED
    assert "source_boundary_competing_w2_components" in shadow[0].reason_codes
    assert shadow[0].building_component_id == ""
    assert shadow[0].floor_area_m2 is None


def test_both_w2_and_w4_original_source_conflicts_remain_visible(monkeypatch):
    graph, mapping = _fixture(
        monkeypatch, conflicting_wall=True, conflicting_component=True
    )
    shadow = _rooms(graph, mapping, shadow=True)
    assert shadow[0].status is EvidenceResolutionStatus.ABSTAINED
    assert set(shadow[0].reason_codes) == {
        "source_boundary_competing_w4_owners",
        "source_boundary_competing_w2_components",
    }


@pytest.mark.parametrize("bad", ("True", 1, None, [], {}))
def test_conflict_shadow_never_implicitly_activated(monkeypatch, bad):
    graph, mapping = _fixture(monkeypatch)
    with pytest.raises(ValueError, match="literal boolean"):
        w5.reconstruct_room_candidates(
            graph, mapping, document_id="doc", viewport_id="vp",
            source_boundary_owner_conflicts_shadow=bad
        )


def test_no_candidate_owner_is_physical_wall_quantity_authority(monkeypatch):
    graph, mapping = _fixture(monkeypatch)
    candidate = _rooms(graph, mapping, shadow=True)[0]
    assert candidate.status is EvidenceResolutionStatus.CANDIDATE
    assert candidate.floor_area_m2 is None
    assert candidate.label == ""
