"""U1: lossless plural primitive lineage through W2. Shadow only."""
from __future__ import annotations

import copy
import inspect
import random
from typing import Any, Dict, List

import fitz
import pytest

from pb_accuracy_v13_engines_v145 import split_segments_at_intersections
from pb_vector_geometry_v130 import extract_native_page
from pb_wall_room_topology_primitive_lineage import (
    LINEAGE_KEY,
    SNAP_COLLAPSE_REASON,
    fabricated_live_fields,
)
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    filter_structural_segments,
    is_structural_candidate_segment,
)
from pb_wall_topology_diagnostics import (
    collect_topology_from_segments,
    diagnose_wall_topology,
)


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


def _assert_live_sentinels(edge: Dict[str, Any]) -> None:
    live = fabricated_live_fields()
    for key, value in live.items():
        assert edge[key] == value


class TestOneSourceMultipleFragments:
    def test_crossing_splits_one_source_into_two_owned_fragments(self) -> None:
        segments = [_seg("h", -5, 0, 5, 0), _seg("v", 0, -5, 0, 5)]
        graph = build_wall_graph_for_viewport(segments)
        assert len(graph["edges"]) == 4
        horizontal = [edge for edge in graph["edges"] if abs(edge["y1"] - edge["y2"]) < 1e-6]
        vertical = [edge for edge in graph["edges"] if abs(edge["x1"] - edge["x2"]) < 1e-6]
        assert len(horizontal) == 2
        assert len(vertical) == 2
        assert all(_ids(edge) == ["h"] for edge in horizontal)
        assert all(_ids(edge) == ["v"] for edge in vertical)
        for edge in graph["edges"]:
            _assert_live_sentinels(edge)


class TestDuplicateAndOverlappingSources:
    def test_duplicate_identical_native_sources_keep_both_ids(self) -> None:
        segments = [_seg("a", 0, 0, 10, 0), _seg("b", 0, 0, 10, 0)]
        graph = build_wall_graph_for_viewport(segments)
        assert graph["edges"]
        for edge in graph["edges"]:
            assert _ids(edge) == ["a", "b"]
            assert len(_lineage(edge)["source_records"]) == 2

    def test_overlapping_coincident_sources_are_multi_parent(self) -> None:
        segments = [
            _seg("h1", -6, 0, 6, 0, width=1.0, layer="A"),
            _seg("h2", -6, 0, 6, 0, width=2.0, layer="B"),
            _seg("v", 0, -6, 0, 6),
        ]
        graph = build_wall_graph_for_viewport(segments)
        horizontal = [edge for edge in graph["edges"] if abs(edge["y1"] - edge["y2"]) < 1e-6]
        assert horizontal
        for edge in horizontal:
            assert _ids(edge) == ["h1", "h2"]
            assert _lineage(edge)["attribute_status"]["width"] == "conflict"
            assert _lineage(edge)["attribute_status"]["layer"] == "conflict"
            assert "width" in _lineage(edge)["attribute_conflicts"]
            assert "layer" in _lineage(edge)["attribute_conflicts"]


class TestCrossingAndOrder:
    def test_crossing_geometry_retains_per_stroke_lineage(self) -> None:
        graph = build_wall_graph_for_viewport([_seg("h", -4, 0, 4, 0), _seg("v", 0, -4, 0, 4)])
        by_axis = {"h": 0, "v": 0}
        for edge in graph["edges"]:
            ids = _ids(edge)
            assert len(ids) == 1
            by_axis[ids[0]] += 1
        assert by_axis == {"h": 2, "v": 2}

    def test_reversed_input_order_same_sorted_lineage(self) -> None:
        segments = [_seg("h", -4, 0, 4, 0), _seg("v", 0, -4, 0, 4)]
        forward = build_wall_graph_for_viewport(segments)
        reverse = build_wall_graph_for_viewport(list(reversed(segments)))

        def id_sets(graph: Dict[str, Any]) -> List[tuple]:
            rows = []
            for edge in graph["edges"]:
                ends = tuple(
                    sorted(
                        (
                            (round(edge["x1"], 3), round(edge["y1"], 3)),
                            (round(edge["x2"], 3), round(edge["y2"], 3)),
                        )
                    )
                )
                rows.append((ends, tuple(_ids(edge))))
            return sorted(rows)

        assert id_sets(forward) == id_sets(reverse)


class TestEquivalentRechunking:
    def test_one_stroke_versus_two_collinear_chunks_unions_given_ids(self) -> None:
        one = build_wall_graph_for_viewport([_seg("whole", 0, 0, 10, 0)])
        chunks = build_wall_graph_for_viewport(
            [_seg("left", 0, 0, 5, 0), _seg("right", 5, 0, 10, 0)]
        )
        assert len(one["edges"]) == 1
        assert len(chunks["edges"]) == 1
        assert {round(one["edges"][0]["length_pt"], 3)} == {round(chunks["edges"][0]["length_pt"], 3)}
        assert _ids(one["edges"][0]) == ["whole"]
        assert _ids(chunks["edges"][0]) == ["left", "right"]

    def test_rechunk_order_does_not_change_union(self) -> None:
        a = build_wall_graph_for_viewport([_seg("left", 0, 0, 5, 0), _seg("right", 5, 0, 10, 0)])
        b = build_wall_graph_for_viewport([_seg("right", 5, 0, 10, 0), _seg("left", 0, 0, 5, 0)])
        assert _ids(a["edges"][0]) == _ids(b["edges"][0]) == ["left", "right"]


class TestUnknownnessAndConflicts:
    def test_missing_source_metadata_stays_unknown(self) -> None:
        sparse = {
            "id": "bare",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 8.0,
            "y2": 0.0,
        }
        graph = build_wall_graph_for_viewport([sparse])
        edge = graph["edges"][0]
        _assert_live_sentinels(edge)
        lineage = _lineage(edge)
        assert lineage["source_primitive_ids"] == ["bare"]
        record = lineage["source_records"][0]
        assert record["width_present"] is False
        assert record["layer_present"] is False
        assert record["dashes_present"] is False
        assert record["stroke_present"] is False
        assert record["clip_present"] is False
        assert lineage["attribute_status"]["width"] == "unknown"
        assert lineage["attribute_status"]["layer"] == "unknown"
        assert lineage["attribute_conflicts"] == []

    def test_normalized_sentinels_are_not_treated_as_supplied(self) -> None:
        segment = _seg("s", 0, 0, 8, 0, width=0.0, layer="", dashes="", stroke=None, fill=None)
        graph = build_wall_graph_for_viewport([segment])
        record = _lineage(graph["edges"][0])["source_records"][0]
        assert record["width_present"] is False
        assert record["layer_present"] is False
        assert record["dashes_present"] is False
        assert record["stroke_present"] is False

    def test_conflicting_metadata_is_unresolved(self) -> None:
        segments = [
            _seg("a", 0, 0, 5, 0, width=1.0, stroke=(0, 0, 0), layer="A", dashes="[] 0"),
            _seg("b", 5, 0, 10, 0, width=2.5, stroke=(1, 0, 0), layer="B", dashes="[3 2] 0"),
        ]
        # dashes on b would be excluded by the structural filter; keep both
        # structural so merge can see the conflict.
        segments[1]["dashes"] = "[] 0"
        graph = build_wall_graph_for_viewport(segments)
        assert len(graph["edges"]) == 1
        lineage = _lineage(graph["edges"][0])
        assert lineage["source_primitive_ids"] == ["a", "b"]
        assert lineage["attribute_status"]["width"] == "conflict"
        assert lineage["attribute_status"]["stroke"] == "conflict"
        assert lineage["attribute_status"]["layer"] == "conflict"
        assert set(lineage["attribute_conflicts"]) >= {"width", "stroke", "layer"}
        _assert_live_sentinels(graph["edges"][0])


class TestSnapCollapseObservability:
    def test_short_fragment_collapse_keeps_lineage_and_reason(self) -> None:
        segments = [
            _seg("long", 0, 0, 20, 0),
            _seg("tiny", 50, 50, 51, 50),
        ]
        graph = build_wall_graph_for_viewport(segments)
        assert len(graph["edges"]) == 1
        assert _ids(graph["edges"][0]) == ["long"]
        collapsed = graph["snap_collapsed_fragments"]
        assert len(collapsed) == 1
        assert collapsed[0]["reason"] == SNAP_COLLAPSE_REASON
        assert collapsed[0][LINEAGE_KEY]["source_primitive_ids"] == ["tiny"]

    def test_shadow_diagnostics_surface_collapse(self) -> None:
        snapshot = collect_topology_from_segments(
            [_seg("long", 0, 0, 20, 0), _seg("tiny", 50, 50, 51, 50)],
            document_id="doc",
            page_id="page_1",
            page_number=1,
            viewport_id="vp_1",
        )
        report = diagnose_wall_topology(snapshot)
        assert report["counts"]["snap_collapsed_fragments"] == 1
        assert report["snap_collapsed_fragments"][0]["reason"] == SNAP_COLLAPSE_REASON


class TestCollinearMergeLineage:
    def test_two_edge_merge_unions_both_sources(self) -> None:
        graph = build_wall_graph_for_viewport([_seg("a", 0, 0, 5, 0), _seg("b", 5, 0, 10, 0)])
        assert len(graph["edges"]) == 1
        edge = graph["edges"][0]
        assert _ids(edge) == ["a", "b"]
        assert len(edge["collinear_merge_source_edge_ids"]) == 2
        assert edge["collinear_merge_leaf_edge_ids"]
        assert len(edge["collinear_merge_leaf_edge_ids"]) == 2

    def test_recursive_three_edge_merge_keeps_a_b_and_c(self) -> None:
        graph = build_wall_graph_for_viewport(
            [_seg("a", 0, 0, 3, 0), _seg("b", 3, 0, 7, 0), _seg("c", 7, 0, 10, 0)]
        )
        assert len(graph["edges"]) == 1
        edge = graph["edges"][0]
        assert _ids(edge) == ["a", "b", "c"]
        assert edge["collinear_merge_leaf_edge_ids"]
        assert len(edge["collinear_merge_leaf_edge_ids"]) == 3
        records_by_id = {record["id"]: record for record in _lineage(edge)["source_records"]}
        assert set(records_by_id) == {"a", "b", "c"}


class TestReplayImmutabilityViewportAndCurves:
    def test_deterministic_replay(self) -> None:
        segments = [_seg("h", -5, 0, 5, 0), _seg("v", 0, -5, 0, 5), _seg("a", 8, 0, 12, 0)]
        first = build_wall_graph_for_viewport(segments)
        second = build_wall_graph_for_viewport(copy.deepcopy(segments))
        assert [(_ids(edge), round(edge["length_pt"], 6)) for edge in first["edges"]] == [
            (_ids(edge), round(edge["length_pt"], 6)) for edge in second["edges"]
        ]
        assert first["snap_collapsed_fragments"] == second["snap_collapsed_fragments"]

    def test_does_not_mutate_inputs(self) -> None:
        segments = [_seg("h", -5, 0, 5, 0), _seg("v", 0, -5, 0, 5)]
        before = copy.deepcopy(segments)
        build_wall_graph_for_viewport(segments)
        assert segments == before

    def test_mixed_viewport_isolation_without_invented_ownership(self) -> None:
        viewport_a = [_seg("a1", 0, 0, 10, 0, viewport_id="vpA", document_id="doc", page_id="p1")]
        viewport_b = [_seg("b1", 0, 20, 10, 20, viewport_id="vpB", document_id="doc", page_id="p1")]
        graph_a = build_wall_graph_for_viewport(viewport_a)
        graph_b = build_wall_graph_for_viewport(viewport_b)
        assert _ids(graph_a["edges"][0]) == ["a1"]
        assert _ids(graph_b["edges"][0]) == ["b1"]
        record_a = _lineage(graph_a["edges"][0])["source_records"][0]
        record_b = _lineage(graph_b["edges"][0])["source_records"][0]
        assert record_a["viewport_id"] == "vpA"
        assert record_b["viewport_id"] == "vpB"
        assert "viewport_id" not in graph_a["edges"][0]
        assert "document_id" not in graph_a["edges"][0]
        assert "page_id" not in graph_a["edges"][0]

    def test_w2_does_not_clip_or_invent_a_viewport(self) -> None:
        crossing = _seg("cross", -5, 0, 15, 0)
        graph = build_wall_graph_for_viewport([crossing])
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["length_pt"] == pytest.approx(20.0)
        assert "viewport_id" not in graph["edges"][0]
        assert "viewport_bbox" not in graph

    def test_curves_remain_unsupported_in_native_extract(self) -> None:
        class _Point:
            def __init__(self, x: float, y: float) -> None:
                self.x = x
                self.y = y

        class _Page:
            def __init__(self) -> None:
                self.rect = type("R", (), {"width": 100.0, "height": 100.0})()

            def get_drawings(self) -> list:
                return [
                    {
                        "width": 1.0,
                        "color": (0, 0, 0),
                        "fill": None,
                        "layer": "WALL",
                        "dashes": "",
                        "items": [("c", _Point(0, 0), _Point(1, 2), _Point(3, 2), _Point(4, 0))],
                    }
                ]

            def get_text(self, kind: str) -> list:
                return []

        native = extract_native_page(_Page())
        assert native["segments"] == []
        assert native["segment_count"] == 0


class TestExistingSplitterAndFilterUnchanged:
    def test_intersection_engine_still_returns_bare_pairs(self) -> None:
        pairs = [(( -5.0, 0.0), (5.0, 0.0)), ((0.0, -5.0), (0.0, 5.0))]
        split = split_segments_at_intersections(pairs)
        assert all(isinstance(item, tuple) and len(item) == 2 for item in split)
        assert all(isinstance(point, tuple) and len(point) == 2 for item in split for point in item)
        assert len(split) == 4

    def test_structural_filter_is_not_widened(self) -> None:
        keep_short, _ = is_structural_candidate_segment(_seg("s", 0, 0, 0.3, 0))
        keep_dash, reasons = is_structural_candidate_segment(_seg("d", 0, 0, 10, 0, dashes="[3 2] 0"))
        assert keep_short is True
        assert keep_dash is False
        assert reasons == ["dashed_line_excluded"]
        kept, excluded = filter_structural_segments(
            [
                _seg("wall", 0, 0, 10, 0),
                _seg("hatch", 1, 1, 2, 2, layer="hatch"),
                _seg("dim", 1, 1, 2, 2, layer="dimensions"),
                _seg("text", 1, 1, 2, 2, layer="text-frame"),
            ]
        )
        assert [segment["id"] for segment in kept] == ["wall"]
        assert {segment["id"] for segment in excluded} == {"hatch", "dim", "text"}

    def test_shuffled_order_is_lineage_invariant(self) -> None:
        segments = [_seg("h", -5, 0, 5, 0), _seg("v", 0, -5, 0, 5), _seg("t", 5, 0, 5, 4)]
        baseline = build_wall_graph_for_viewport(segments)
        shuffled = list(segments)
        random.Random(7).shuffle(shuffled)
        other = build_wall_graph_for_viewport(shuffled)

        def bag(graph: Dict[str, Any]) -> List[tuple]:
            return sorted(
                (tuple(_ids(edge)), round(edge["length_pt"], 3)) for edge in graph["edges"]
            )

        assert bag(baseline) == bag(other)


class TestLiveAndCommercialStability:
    def test_live_extractor_does_not_import_w2_or_lineage(self) -> None:
        from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

        source = inspect.getsource(GenericPlanReaderExtractor)
        method = inspect.getsource(GenericPlanReaderExtractor.extract_from_pdf)
        assert "build_wall_graph_for_viewport" not in method
        assert "pb_wall_room_topology_stage_a" not in source
        assert "pb_wall_room_topology_primitive_lineage" not in source

    def test_live_extract_from_pdf_output_unchanged_on_synthetic_pdf(self, tmp_path) -> None:
        from pb_planreader_pdf_extractor import GenericPlanReaderExtractor

        pdf = tmp_path / "u1_live_stability.pdf"
        doc = fitz.open()
        page = doc.new_page(width=842, height=595)
        page.insert_text(
            (50, 50),
            "GROUND FLOOR PLAN\n"
            "SCALE 1:100\n"
            "DRAWING NO: AD-01\n"
            "12,000\n"
            "6,000\n"
            "FLOOR AREA - 72.00M2\n"
            "D.P.M. under floor bed\n",
        )
        page.draw_line((100, 100), (400, 100))
        page.draw_line((100, 100), (100, 400))
        page2 = doc.new_page(width=842, height=595)
        page2.insert_text((50, 50), "WINDOW SCHEDULE\nW1 1200 x 1200 2 No\n")
        doc.save(pdf)
        doc.close()

        first = [item.to_dict() for item in GenericPlanReaderExtractor().extract_from_pdf(pdf)]
        second = [item.to_dict() for item in GenericPlanReaderExtractor().extract_from_pdf(pdf)]
        assert first == second
        for item in first:
            assert "primitive_lineage" not in item
            assert "primitive_lineage" not in (item.get("metadata") or {})

    def test_commercial_adapter_untouched_and_gates_unchanged(self) -> None:
        import pb_quantity_takeoff_adapter as adapter
        from tests.test_quantity_takeoff_adapter import figured, quantity, source_trace

        source = inspect.getsource(adapter)
        assert "pb_wall_room_topology_primitive_lineage" not in source
        assert "build_wall_graph_for_viewport" not in source
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
        assert results["pricing"][0] is False
        assert results["jobhub"][0] is False
