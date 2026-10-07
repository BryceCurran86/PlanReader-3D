"""Exact W3-dedup source coverage sidecar for W4 physical walls."""
from __future__ import annotations

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import _exact_source_coverage_by_wall
from pb_physical_wall_identity import resolve_physical_wall_identity
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY


def _lineage(*source_ids: str) -> dict:
    return {
        "source_primitive_ids": list(source_ids),
        "source_records": [],
        "attribute_status": {},
        "attribute_conflicts": [],
    }


def _edge(
    edge_id: str,
    *,
    a: int,
    b: int,
    source_id: str,
    x1: float = 0.0,
    y1: float = 0.0,
    x2: float = 100.0,
    y2: float = 0.0,
) -> dict:
    return {
        "id": edge_id,
        "a": a,
        "b": b,
        "x1": x1,
        "y1": y1,
        "x2": x2,
        "y2": y2,
        LINEAGE_KEY: _lineage(source_id),
    }


def _wall(candidate_id: str, edge_id: str) -> WallCandidate:
    return WallCandidate(
        candidate_id=candidate_id,
        viewport_id="wall-source:page-1",
        representation="single_line",
        centerline_pts=((0.0, 0.0), (100.0, 0.0)),
        face_a_segment_ids=(edge_id,),
        face_b_segment_ids=None,
        is_curved=False,
        curve_control_pts=None,
        thickness_m=None,
        thickness_authority=MeasurementAuthorityType.PROVISIONAL,
        length_m=None,
        end_node_ids=("n0", "n1"),
        junction_types=(JunctionType.ENDPOINT, JunctionType.ENDPOINT),
        interior_exterior="unresolved",
        level_id=None,
        status=EvidenceResolutionStatus.CANDIDATE,
        confidence=0.5,
        reason_codes=(),
    )


def _nodes() -> list[dict]:
    return [
        {"id": 0, "x": 0.0, "y": 0.0},
        {"id": 1, "x": 100.0, "y": 0.0},
        {"id": 2, "x": 0.0, "y": 0.0},
        {"id": 3, "x": 100.0, "y": 0.0},
    ]


def test_exact_coincident_dedup_retains_discarded_source_coverage_without_identity_churn() -> None:
    graph = {
        "nodes": _nodes()[:2],
        "edges": [
            _edge("edge-a", a=0, b=1, source_id="raw-a"),
            _edge("edge-b", a=0, b=1, source_id="raw-b"),
        ],
        "adjacency": {0: [0, 1], 1: [0, 1]},
    }
    wall = _wall("wall-1", "edge-a")
    edges_by_id = {edge["id"]: edge for edge in graph["edges"]}

    identity_before = resolve_physical_wall_identity(
        wall=wall,
        edges_by_id=edges_by_id,
    )
    coverage = _exact_source_coverage_by_wall(walls=(wall,), graph=graph)
    identity_after = resolve_physical_wall_identity(
        wall=wall,
        edges_by_id=edges_by_id,
    )

    assert identity_before.usable
    assert identity_before == identity_after
    assert identity_before.source_primitive_ids == ("raw-a",)
    assert coverage == {"wall-1": ("raw-a", "raw-b")}


def test_equal_geometry_with_distinct_snapped_node_pairs_is_not_coverage_equivalent() -> None:
    graph = {
        "nodes": _nodes(),
        "edges": [
            _edge("edge-a", a=0, b=1, source_id="raw-a"),
            _edge("edge-b", a=2, b=3, source_id="raw-b"),
        ],
        "adjacency": {0: [0], 1: [0], 2: [1], 3: [1]},
    }
    wall = _wall("wall-1", "edge-a")

    coverage = _exact_source_coverage_by_wall(walls=(wall,), graph=graph)

    assert coverage == {"wall-1": ("raw-a",)}
    assert "raw-b" not in coverage["wall-1"]


def test_source_coverage_fails_closed_when_one_survivor_is_claimed_by_multiple_walls() -> None:
    graph = {
        "nodes": _nodes()[:2],
        "edges": [
            _edge("edge-a", a=0, b=1, source_id="raw-a"),
            _edge("edge-b", a=0, b=1, source_id="raw-b"),
        ],
        "adjacency": {0: [0, 1], 1: [0, 1]},
    }
    first = _wall("wall-1", "edge-a")
    second = _wall("wall-2", "edge-a")

    coverage = _exact_source_coverage_by_wall(
        walls=(first, second),
        graph=graph,
    )

    assert coverage == {}
