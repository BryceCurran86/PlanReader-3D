"""U2: typed negative evidence over retained W2 edges. Shadow only."""
from __future__ import annotations

import copy
import inspect
import math
import random
from typing import Any, Dict, List

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport, is_structural_candidate_segment
from pb_wall_room_topology_typed_negative_evidence import (
    GRAPH_ATOMS_KEY,
    KIND_ANNOTATION_BORDER,
    KIND_DIMENSION,
    KIND_FURNITURE,
    KIND_GLAZING,
    KIND_GRID,
    KIND_HATCH,
    KIND_PHYSICAL_WALL,
    KIND_TABLE,
    KIND_UNKNOWN,
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


def _attach(segments: List[Dict[str, Any]], *, viewport_id: str = "vp1") -> Dict[str, Any]:
    graph = build_wall_graph_for_viewport(segments)
    return attach_typed_semantic_evidence(
        graph, document_id="doc", page_id="page_1", viewport_id=viewport_id
    )


def _atoms(graph: Dict[str, Any]) -> List[Dict[str, Any]]:
    return list(graph.get(GRAPH_ATOMS_KEY) or [])


def _kinds_for(graph: Dict[str, Any], edge_id: str) -> List[str]:
    return sorted(
        atom["kind"]
        for atom in _atoms(graph)
        if (atom.get("metadata") or {}).get("target_edge_id") == edge_id
    )


def _kinds(graph: Dict[str, Any]) -> List[str]:
    return sorted({atom["kind"] for atom in _atoms(graph)})


def _longest_edge(graph: Dict[str, Any]) -> Dict[str, Any]:
    return max(graph["edges"], key=lambda edge: float(edge.get("length_pt") or 0.0))


class TestTypedNegativeNominations:
    def test_wall_with_nearby_dimension_ticks(self) -> None:
        segments = [_seg("wall", 0, 0, 40, 0)]
        for idx, x in enumerate((8.0, 16.0, 24.0, 32.0)):
            segments.append(_seg(f"tick{idx}", x, 0, x, 4))
        graph = _attach(segments)
        wall = max(graph["edges"], key=lambda edge: abs(float(edge["x2"]) - float(edge["x1"])))
        kinds = _kinds_for(graph, wall["id"])
        assert KIND_PHYSICAL_WALL in kinds
        assert KIND_DIMENSION in kinds
        atoms = collect_typed_semantic_evidence(graph, document_id="doc", page_id="page_1")
        wall_atoms = [atom for atom in atoms if atom.metadata["target_edge_id"] == wall["id"]]
        assert bundle_status(wall_atoms) == EvidenceResolutionStatus.CONFLICT
        assert len(graph["edges"]) >= 5

    def test_wall_overlapped_by_hatch_is_retained(self) -> None:
        segments = [_seg("wall", 0, 0, 30, 0)]
        for idx in range(8):
            x = 2 + idx * 3
            segments.append(_seg(f"h{idx}", x, -2, x + 2, 2))
        before = build_wall_graph_for_viewport(segments)
        graph = _attach(segments)
        assert len(graph["edges"]) == len(before["edges"])
        assert KIND_HATCH in _kinds(graph)
        assert KIND_PHYSICAL_WALL in _kinds(graph)

    def test_glazing_mullion_array(self) -> None:
        segments = [_seg("host", 0, 0, 40, 0)]
        for idx, x in enumerate((8.0, 16.0, 24.0, 32.0)):
            segments.append(_seg(f"m{idx}", x, 0, x, 12))
        graph = _attach(segments)
        assert KIND_GLAZING in _kinds(graph)
        assert all(edge.get("id") for edge in graph["edges"])

    def test_furniture_rectangle(self) -> None:
        segments = [
            _seg("a", 0, 0, 16, 0),
            _seg("b", 16, 0, 16, 10),
            _seg("c", 16, 10, 0, 10),
            _seg("d", 0, 10, 0, 0),
        ]
        graph = _attach(segments)
        assert KIND_FURNITURE in _kinds(graph)
        assert len(graph["edges"]) == len(build_wall_graph_for_viewport(segments)["edges"])

    def test_room_like_rectangle_with_interior_partition_is_not_deleted(self) -> None:
        segments = [
            _seg("a", 0, 0, 80, 0),
            _seg("b", 80, 0, 80, 50),
            _seg("c", 80, 50, 0, 50),
            _seg("d", 0, 50, 0, 0),
            _seg("part", 0, 25, 80, 25),
        ]
        raw = build_wall_graph_for_viewport(segments)
        graph = _attach(segments)
        assert len(graph["edges"]) == len(raw["edges"])
        assert KIND_PHYSICAL_WALL in _kinds(graph)

    def test_schedule_table_frame(self) -> None:
        segments = [
            _seg("o1", 0, 0, 30, 0),
            _seg("o2", 30, 0, 30, 20),
            _seg("o3", 30, 20, 0, 20),
            _seg("o4", 0, 20, 0, 0),
        ]
        for idx, x in enumerate((6.0, 12.0, 18.0, 24.0)):
            segments.append(_seg(f"v{idx}", x, 0, x, 20))
        for idx, y in enumerate((5.0, 10.0, 15.0)):
            segments.append(_seg(f"h{idx}", 0, y, 30, y))
        graph = _attach(segments)
        assert KIND_TABLE in _kinds(graph)

    def test_repeated_grid(self) -> None:
        segments = [
            _seg("g0", 0, 0, 40, 0),
            _seg("g1", 0, 8, 40, 8),
            _seg("g2", 0, 16, 40, 16),
            _seg("g3", 0, 24, 40, 24),
        ]
        graph = _attach(segments)
        assert KIND_GRID in _kinds(graph)

    def test_annotation_border_enclosing_short_marks(self) -> None:
        segments = [
            _seg("o1", 0, 0, 40, 0),
            _seg("o2", 40, 0, 40, 24),
            _seg("o3", 40, 24, 0, 24),
            _seg("o4", 0, 24, 0, 0),
            _seg("t1", 6, 6, 10, 6),
            _seg("t2", 14, 6, 18, 6),
        ]
        graph = build_wall_graph_for_viewport(segments)
        graph = attach_typed_semantic_evidence(
            graph,
            document_id="doc",
            page_id="page_1",
            viewport_id="vp1",
            words=[{"text": "NOTE", "bbox": [8, 8, 20, 12]}],
        )
        assert KIND_ANNOTATION_BORDER in _kinds(graph)

    def test_conflicting_negative_kinds_stay_plural(self) -> None:
        segments = [_seg("wall", 0, 0, 36, 0)]
        for idx, x in enumerate((6.0, 12.0, 18.0, 24.0, 30.0)):
            segments.append(_seg(f"tick{idx}", x, 0, x, 3))
        for idx in range(7):
            x = 3 + idx * 4
            segments.append(_seg(f"h{idx}", x, -2, x + 1.5, 2))
        graph = _attach(segments)
        kinds = set(_kinds(graph))
        assert KIND_DIMENSION in kinds
        assert KIND_HATCH in kinds
        wall = _longest_edge(graph)
        wall_atoms = [
            atom
            for atom in collect_typed_semantic_evidence(graph, document_id="doc", page_id="page_1")
            if atom.metadata["target_edge_id"] == wall["id"]
        ]
        assert bundle_status(wall_atoms) == EvidenceResolutionStatus.CONFLICT
        assert not any(atom.status == EvidenceResolutionStatus.CORROBORATED for atom in wall_atoms)


class TestInvarianceIsolationAndGates:
    def test_input_order_invariance(self) -> None:
        segments = [_seg("wall", 0, 0, 40, 0)] + [
            _seg(f"tick{idx}", x, 0, x, 4) for idx, x in enumerate((8.0, 16.0, 24.0, 32.0))
        ]
        first = _kinds(_attach(segments))
        shuffled = list(segments)
        random.Random(3).shuffle(shuffled)
        assert _kinds(_attach(shuffled)) == first

    def test_translation_rotation_scale_metamorphic(self) -> None:
        segments = [_seg("wall", 0, 0, 40, 0)] + [
            _seg(f"tick{idx}", x, 0, x, 4) for idx, x in enumerate((10.0, 20.0, 30.0))
        ]

        def transform(items: List[Dict[str, Any]], *, dx=0.0, dy=0.0, scale=1.0, rot=0.0) -> List[Dict[str, Any]]:
            rad = math.radians(rot)
            out = []
            for item in items:
                copied = dict(item)
                for key_x, key_y in (("x1", "y1"), ("x2", "y2")):
                    x, y = float(item[key_x]) * scale, float(item[key_y]) * scale
                    xr = x * math.cos(rad) - y * math.sin(rad)
                    yr = x * math.sin(rad) + y * math.cos(rad)
                    copied[key_x] = xr + dx
                    copied[key_y] = yr + dy
                copied["id"] = item["id"]
                out.append(copied)
            return out

        baseline = set(_kinds(_attach(segments)))
        assert set(_kinds(_attach(transform(segments, dx=15, dy=-7)))) == baseline
        assert set(_kinds(_attach(transform(segments, rot=90)))) == baseline
        assert set(_kinds(_attach(transform(segments, scale=2.0)))) == baseline

    def test_rechunking_keeps_roles_not_provenance_identity(self) -> None:
        whole = _attach([_seg("whole", 0, 0, 40, 0), _seg("t0", 10, 0, 10, 4), _seg("t1", 20, 0, 20, 4), _seg("t2", 30, 0, 30, 4)])
        chunks = _attach(
            [
                _seg("left", 0, 0, 20, 0),
                _seg("right", 20, 0, 40, 0),
                _seg("t0", 10, 0, 10, 4),
                _seg("t1", 20, 0, 20, 4),
                _seg("t2", 30, 0, 30, 4),
            ]
        )
        assert KIND_DIMENSION in _kinds(whole)
        assert KIND_DIMENSION in _kinds(chunks)
        whole_ids = {
            tuple(atom["metadata"]["source_primitive_ids"])
            for atom in _atoms(whole)
            if atom["kind"] == KIND_PHYSICAL_WALL
        }
        chunk_ids = {
            tuple(atom["metadata"]["source_primitive_ids"])
            for atom in _atoms(chunks)
            if atom["kind"] == KIND_PHYSICAL_WALL
        }
        assert whole_ids != chunk_ids

    def test_viewport_isolation(self) -> None:
        segs_a = [_seg("a", 0, 0, 30, 0, viewport_id="vpA")]
        segs_b = [_seg("b", 0, 0, 30, 0, viewport_id="vpB")]
        graph_a = _attach(segs_a, viewport_id="vpA")
        graph_b = _attach(segs_b, viewport_id="vpB")
        assert all(atom.get("viewport_id") == "vpA" for atom in _atoms(graph_a))
        assert all(atom.get("viewport_id") == "vpB" for atom in _atoms(graph_b))
        _atoms(graph_a)[0]["metadata"]["source_primitive_ids"].append("leaked")
        assert "leaked" not in (_atoms(graph_b)[0]["metadata"]["source_primitive_ids"])

    def test_deterministic_replay_and_immutability(self) -> None:
        segments = [_seg("wall", 0, 0, 40, 0), _seg("t0", 10, 0, 10, 4), _seg("t1", 20, 0, 20, 4)]
        before = copy.deepcopy(segments)
        first = _attach(segments)
        second = _attach(copy.deepcopy(segments))
        assert [atom["evidence_id"] for atom in _atoms(first)] == [atom["evidence_id"] for atom in _atoms(second)]
        assert segments == before

    def test_no_early_deletion_and_w2_filter_unchanged(self) -> None:
        dashed = _seg("dim", 0, 10, 20, 10, dashes="[3 2] 0")
        keep, reasons = is_structural_candidate_segment(dashed)
        assert keep is False
        assert reasons == ["dashed_line_excluded"]
        segments = [_seg("wall", 0, 0, 40, 0), dashed]
        raw = build_wall_graph_for_viewport(segments)
        attached = _attach(segments)
        assert len(attached["edges"]) == len(raw["edges"])
        assert {seg["id"] for seg in attached["excluded_segments"]} == {"dim"}

    def test_unknown_when_no_feature(self) -> None:
        graph = _attach([_seg("bare", 0, 0, 9, 3)])
        assert _atoms(graph)
        assert KIND_UNKNOWN in _kinds(graph) or KIND_PHYSICAL_WALL in _kinds(graph)

    def test_diagnostics_surface_atoms(self) -> None:
        snapshot = collect_topology_from_segments(
            [_seg("wall", 0, 0, 40, 0), _seg("t0", 10, 0, 10, 4), _seg("t1", 20, 0, 20, 4), _seg("t2", 30, 0, 30, 4)],
            document_id="doc",
            page_id="page_1",
            page_number=1,
            viewport_id="vp_1",
        )
        report = diagnose_wall_topology(snapshot)
        assert report["counts"]["semantic_evidence_atoms"] >= 1
        assert report["semantic_evidence"]["atoms"]

    def test_u1_lineage_is_on_every_atom(self) -> None:
        graph = _attach([_seg("wall", 0, 0, 40, 0), _seg("t0", 10, 0, 10, 4), _seg("t1", 20, 0, 20, 4)])
        for atom in _atoms(graph):
            assert atom["metadata"]["source_primitive_ids"]
            assert atom["status"] != EvidenceResolutionStatus.CORROBORATED.value

    def test_live_extractor_and_commercial_isolation(self) -> None:
        from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
        import pb_quantity_takeoff_adapter as adapter
        from tests.test_quantity_takeoff_adapter import figured, quantity, source_trace

        source = inspect.getsource(GenericPlanReaderExtractor)
        method = inspect.getsource(GenericPlanReaderExtractor.extract_from_pdf)
        assert "typed_negative" not in source
        assert "collect_typed_semantic_evidence" not in method
        assert "typed_negative" not in inspect.getsource(adapter)
        pdf_path_unused = None
        del pdf_path_unused
        fingerprint = adapter.compute_commercial_projection_fingerprint(
            quantity(), trace=source_trace(), authority=figured()
        )
        assert fingerprint == adapter.compute_commercial_projection_fingerprint(
            quantity(), trace=source_trace(), authority=figured()
        )
        row = adapter.quantity_evidence_to_takeoff_output_row(
            quantity(), trace=source_trace(), authority=figured()
        )
        results = adapter.existing_commercial_gate_results(row)
        assert results["publishability"][0] is False


class TestFixtureCensusGuard:
    def test_baghau_sample_does_not_mark_every_edge_as_table(self) -> None:
        from tests.test_u1_lineage_architecture_review import (
            _BAGHAU_SNAPSHOT_PATH,
            _real_structural_segments,
        )

        structural = _real_structural_segments(_BAGHAU_SNAPSHOT_PATH)[:80]
        raw = build_wall_graph_for_viewport(structural)
        graph = _attach(structural)
        assert len(graph["edges"]) == len(raw["edges"])
        table_edges = {
            (atom.get("metadata") or {}).get("target_edge_id")
            for atom in _atoms(graph)
            if atom["kind"] == KIND_TABLE
        }
        assert table_edges != {edge["id"] for edge in graph["edges"]}


class TestLiveExtractUnchanged:
    def test_synthetic_pdf_predictions_have_no_semantic_atoms(self, tmp_path) -> None:
        from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

        pdf = tmp_path / "u2_live_stability.pdf"
        doc = fitz.open()
        page = doc.new_page(width=842, height=595)
        page.insert_text((50, 50), "GROUND FLOOR PLAN\nSCALE 1:100\nFLOOR AREA - 72.00M2\n")
        page.draw_line((100, 100), (400, 100))
        page.draw_line((100, 100), (100, 400))
        doc.save(pdf)
        doc.close()
        items = [item.to_dict() for item in GenericPlanReaderExtractor().extract_from_pdf(pdf)]
        for item in items:
            assert "semantic_evidence_atoms" not in item
            assert "typed_negative" not in str(item.get("metadata") or {})
