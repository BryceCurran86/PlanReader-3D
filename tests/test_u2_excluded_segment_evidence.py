"""U2 reconciliation: evidence atoms on excluded W2 segments. Shadow only.

Locks the two #282 defects: no global length statistic may erase a local
wall nomination, and no single-label winner may replace physical-wall
evidence with GRID/HATCH. Excluded geometry stays excluded.
"""
from __future__ import annotations

from typing import Any, Dict, List, Set

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_typed_negative_evidence import (
    GRAPH_ATOMS_KEY,
    KIND_DIMENSION,
    KIND_GRID,
    KIND_HATCH,
    KIND_PHYSICAL_WALL,
    assert_graph_geometry_unchanged,
    attach_typed_semantic_evidence,
    bundle_status,
    collect_typed_semantic_evidence,
)
from pb_wall_topology_diagnostics import collect_topology_from_segments, diagnose_wall_topology


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


def _attach(segments: List[Dict[str, Any]]) -> Dict[str, Any]:
    graph = build_wall_graph_for_viewport(segments)
    return attach_typed_semantic_evidence(graph, document_id="doc", page_id="page_1", viewport_id="vp1")


def _atoms(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(graph.get(GRAPH_ATOMS_KEY) or [])


def _kinds_for(graph: Dict[str, Any], target_id: str) -> List[str]:
    return sorted(
        atom["kind"]
        for atom in _atoms(graph)
        if (atom.get("metadata") or {}).get("target_edge_id") == target_id
    )


def _atom_signature(graph: Dict[str, Any], target_id: str) -> Set[tuple]:
    return {
        (
            atom["kind"],
            atom["metadata"].get("polarity"),
            tuple(atom["metadata"]["source_primitive_ids"]),
            tuple(atom.get("reason_codes") or []),
        )
        for atom in _atoms(graph)
        if (atom.get("metadata") or {}).get("target_edge_id") == target_id
    }


def _edge_for_source(graph: Dict[str, Any], source_id: str) -> Dict[str, Any]:
    from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY

    for edge in graph["edges"]:
        lineage = edge.get(LINEAGE_KEY) or {}
        ids = [str(item) for item in (lineage.get("source_primitive_ids") or [])]
        if source_id in ids:
            return edge
    raise AssertionError(f"no retained edge owned by {source_id}")


def _wall_fixture() -> List[Dict[str, Any]]:
    segments = [_seg("wall", 0, 0, 40, 0)]
    for idx, x in enumerate((8.0, 16.0, 24.0, 32.0)):
        segments.append(_seg(f"tick{idx}", x, 0, x, 4))
    return segments


class TestExtremeOutlierDoesNotEraseLocalWall:
    def test_unrelated_10000pt_line_leaves_wall_atoms_unchanged(self) -> None:
        baseline = _attach(_wall_fixture())
        wall = _edge_for_source(baseline, "wall")
        before = _atom_signature(baseline, wall["id"])
        assert KIND_PHYSICAL_WALL in _kinds_for(baseline, wall["id"])

        with_outlier = _wall_fixture()
        with_outlier.append(_seg("outlier", 5000, 8000, 15000, 8000))
        after_graph = _attach(with_outlier)
        original = _edge_for_source(after_graph, "wall")
        after = _atom_signature(after_graph, original["id"])
        assert after == before
        assert KIND_PHYSICAL_WALL in _kinds_for(after_graph, original["id"])


class TestRepeatedValidWallsKeepPhysicalWall:
    def test_parallel_wall_pairs_retain_wall_and_may_conflict_with_grid(self) -> None:
        segments: List[Dict[str, Any]] = []
        for idx, y in enumerate((0.0, 8.0, 16.0, 24.0)):
            segments.append(_seg(f"w{idx}a", 0, y, 40, y))
            segments.append(_seg(f"w{idx}b", 0, y + 1.5, 40, y + 1.5))
        graph = _attach(segments)
        wall_like = [
            edge
            for edge in graph["edges"]
            if abs(float(edge["x2"]) - float(edge["x1"])) >= 30
        ]
        assert len(wall_like) >= 4
        for edge in wall_like:
            kinds = set(_kinds_for(graph, edge["id"]))
            assert KIND_PHYSICAL_WALL in kinds
            if KIND_GRID in kinds:
                atoms = [
                    atom
                    for atom in collect_typed_semantic_evidence(graph, document_id="doc", page_id="page_1")
                    if atom.metadata["target_edge_id"] == edge["id"]
                ]
                assert bundle_status(atoms) == EvidenceResolutionStatus.CONFLICT
                assert {atom.kind for atom in atoms} >= {KIND_PHYSICAL_WALL, KIND_GRID}


class TestMultiReasonExcludedPrimitive:
    def test_excluded_primitive_keeps_two_atoms_and_no_winner(self) -> None:
        segments = [
            _seg("keep", 0, 0, 20, 0),
            _seg(
                "ambiguous",
                2,
                6,
                18,
                6,
                layer="HATCH-DIMENSION",
                dashes="[] 0",
            ),
        ]
        raw = build_wall_graph_for_viewport(segments)
        excluded_ids = {str(item.get("id")) for item in raw["excluded_segments"]}
        assert "ambiguous" in excluded_ids
        graph = attach_typed_semantic_evidence(raw, document_id="doc", page_id="page_1", viewport_id="vp1")
        kinds = set(_kinds_for(graph, "ambiguous"))
        assert KIND_HATCH in kinds
        assert KIND_DIMENSION in kinds
        atoms = [
            atom
            for atom in collect_typed_semantic_evidence(graph, document_id="doc", page_id="page_1")
            if atom.metadata["target_edge_id"] == "ambiguous"
        ]
        assert len(atoms) >= 2
        assert bundle_status(atoms) == EvidenceResolutionStatus.CONFLICT
        assert not any(atom.status == EvidenceResolutionStatus.CORROBORATED for atom in atoms)
        assert all(atom.metadata.get("retained") is False for atom in atoms)
        assert "hatch_layer_excluded" in atoms[0].metadata["exclusion_reason_codes"]
        assert "dimension_layer_excluded" in atoms[0].metadata["exclusion_reason_codes"]


class TestExclusionPreservation:
    def test_excluded_segment_does_not_reenter_edges(self) -> None:
        segments = [
            _seg("wall", 0, 0, 30, 0),
            _seg("dim", 0, 10, 20, 10, dashes="[3 2] 0"),
            _seg("hatch", 4, 2, 8, 6, layer="HATCH"),
        ]
        before = build_wall_graph_for_viewport(segments)
        after = attach_typed_semantic_evidence(before, document_id="doc", page_id="page_1")
        assert_graph_geometry_unchanged(before, after)
        excluded_ids = {str(item.get("id")) for item in after["excluded_segments"]}
        edge_ids = {str(edge.get("id")) for edge in after["edges"]}
        assert {"dim", "hatch"} <= excluded_ids
        assert edge_ids.isdisjoint({"dim", "hatch"})
        excluded_atoms = [atom for atom in _atoms(after) if atom["metadata"].get("retained") is False]
        assert excluded_atoms
        assert all(atom["metadata"]["target_edge_id"] in excluded_ids for atom in excluded_atoms)
        assert all(atom["metadata"]["source_primitive_ids"] for atom in excluded_atoms)
        assert all(atom["status"] != EvidenceResolutionStatus.CORROBORATED.value for atom in excluded_atoms)

    def test_diagnostics_expose_excluded_atoms_only(self) -> None:
        snapshot = collect_topology_from_segments(
            [
                _seg("wall", 0, 0, 30, 0),
                _seg("hatch", 4, 2, 8, 6, layer="HATCH"),
            ],
            document_id="doc",
            page_id="page_1",
            page_number=1,
            viewport_id="vp_1",
        )
        report = diagnose_wall_topology(snapshot)
        assert report["counts"]["excluded_semantic_evidence_atoms"] >= 1
        assert "hatch" in report["semantic_evidence"]["excluded_target_ids"]
        assert "hatch" not in {edge.get("id") for edge in snapshot.stage_a_graph.get("edges") or []}


class TestSchemaReuse:
    def test_excluded_atoms_are_evidence_atoms(self) -> None:
        graph = _attach(
            [_seg("wall", 0, 0, 20, 0), _seg("hatch", 1, 3, 4, 7, layer="HATCH")]
        )
        typed = collect_typed_semantic_evidence(graph, document_id="doc", page_id="page_1")
        excluded = [atom for atom in typed if atom.metadata.get("retained") is False]
        assert excluded
        assert all(isinstance(atom, EvidenceAtom) for atom in excluded)
        assert all(atom.evidence_id.startswith("ev_") for atom in excluded)
        replay = collect_typed_semantic_evidence(graph, document_id="doc", page_id="page_1")
        assert [atom.evidence_id for atom in typed] == [atom.evidence_id for atom in replay]
