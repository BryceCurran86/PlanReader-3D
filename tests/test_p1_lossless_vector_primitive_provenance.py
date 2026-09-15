"""Priority 1 residual: lossless vector-primitive provenance enrichment.

Gold-free. Proves additive path_index / clip / native page-coordinate retention
through extract_native_page → lineage source records, without inventing geometry
or changing live ExtractedPrediction tags.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_vector_geometry_v130 import extract_native_page
from pb_wall_room_topology_primitive_lineage import (
    LINEAGE_KEY,
    lineage_from_source_segments,
    source_record_from_segment,
)
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport


def _page_with_clip_line() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_line((60, 60), (140, 140), color=(0, 0, 0), width=2)
    xrefs = page.get_contents()
    data = doc.xref_stream(xrefs[0])
    doc.update_stream(xrefs[0], b"q\n50 50 100 100 re\nW\nn\n" + data + b"\nQ\n")
    # Keep doc alive via page.parent
    page._p1_doc = doc  # type: ignore[attr-defined]
    return page


def test_extract_native_page_emits_structured_path_indices_without_changing_ids() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.draw_line((10, 10), (90, 10), color=(0, 0, 0), width=1.5)
    page.draw_rect(fitz.Rect(20, 20, 80, 80), color=(0, 0, 1), width=1.0)
    native = extract_native_page(page)
    doc.close()

    assert native["segment_count"] == len(native["segments"])
    line = next(seg for seg in native["segments"] if seg["kind"] == "line")
    assert line["id"] == "d0i0"
    assert line["path_index"] == 0
    assert line["item_index"] == 0
    assert "edge_index" not in line
    assert line["width_present"] is True
    assert line["stroke_present"] is True

    rect_edges = [seg for seg in native["segments"] if seg["kind"] == "rect_edge"]
    assert len(rect_edges) == 4
    for edge in rect_edges:
        assert edge["id"].startswith("d1i0e")
        assert edge["path_index"] == 1
        assert edge["item_index"] == 0
        assert edge["edge_index"] in {0, 1, 2, 3}


def test_extract_native_page_associates_clip_scissor_without_inventing_when_absent() -> None:
    page = _page_with_clip_line()
    native = extract_native_page(page)
    assert len(native["segments"]) == 1
    seg = native["segments"][0]
    assert seg["clip_present"] is True
    assert seg["clip"] is not None
    assert len(seg["clip"]) == 4
    # Clip association must not invent geometry endpoints.
    assert (seg["x1"], seg["y1"], seg["x2"], seg["y2"]) == (60.0, 60.0, 140.0, 140.0)

    doc = fitz.open()
    plain = doc.new_page()
    plain.draw_line((10, 10), (50, 10), color=(0, 0, 0), width=1)
    plain_native = extract_native_page(plain)
    doc.close()
    plain_seg = plain_native["segments"][0]
    assert plain_seg["clip_present"] is False
    assert plain_seg["clip"] is None


def test_source_record_retains_path_indices_page_coords_and_clip_status() -> None:
    page = _page_with_clip_line()
    seg = extract_native_page(page)["segments"][0]
    record = source_record_from_segment(seg)
    assert record["path_index"] == seg["path_index"]
    assert record["item_index"] == seg["item_index"]
    assert record["page_coords_present"] is True
    assert (record["x1"], record["y1"], record["x2"], record["y2"]) == (
        seg["x1"],
        seg["y1"],
        seg["x2"],
        seg["y2"],
    )
    assert record["clip_present"] is True
    lineage = lineage_from_source_segments([seg])
    assert lineage["attribute_status"]["clip"] == "agreed"
    assert "clip" in lineage["attribute_status"]


def test_conflicting_clips_mark_attribute_conflict() -> None:
    a = {
        "id": "d0i0",
        "kind": "line",
        "x1": 0.0,
        "y1": 0.0,
        "x2": 10.0,
        "y2": 0.0,
        "clip": [0.0, 0.0, 50.0, 50.0],
        "clip_present": True,
        "path_index": 0,
        "item_index": 0,
    }
    b = {
        "id": "d1i0",
        "kind": "line",
        "x1": 0.0,
        "y1": 0.0,
        "x2": 10.0,
        "y2": 0.0,
        "clip": [10.0, 10.0, 60.0, 60.0],
        "clip_present": True,
        "path_index": 1,
        "item_index": 0,
    }
    lineage = lineage_from_source_segments([a, b])
    assert lineage["attribute_status"]["clip"] == "conflict"
    assert "clip" in lineage["attribute_conflicts"]


def test_w2_lineage_preserves_native_path_index_through_split_snap() -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    # Crossing lines force the splitter to emit fragments.
    page.draw_line((20, 100), (220, 100), color=(0, 0, 0), width=1)
    page.draw_line((120, 20), (120, 220), color=(0, 0, 0), width=1)
    native = extract_native_page(page)
    doc.close()

    graph = build_wall_graph_for_viewport(native["segments"])
    edges = list(graph.get("edges") or [])
    assert edges
    for edge in edges:
        lineage = edge.get(LINEAGE_KEY) or {}
        records = lineage.get("source_records") or []
        assert records
        for record in records:
            assert "path_index" in record
            assert record.get("page_coords_present") is True


def test_live_extractor_predictions_unchanged_by_additive_provenance(tmp_path: Path) -> None:
    pdf_path = tmp_path / "p1-live.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((40, 40), "SCALE 1:100 FLOOR PLAN")
    page.draw_rect(fitz.Rect(50, 80, 250, 280), color=(0, 0, 0), width=1)
    doc.save(pdf_path)
    doc.close()

    # Additive provenance must not introduce lineage or change prediction tags.
    extractor = GenericPlanReaderExtractor()
    preds = extractor.extract_from_pdf(str(pdf_path))
    tags = sorted(p.tag for p in preds)
    for pred in preds:
        payload = pred.to_dict()
        assert "primitive_lineage" not in payload
        assert "primitive_lineage" not in (payload.get("metadata") or {})
    # Re-run is deterministic for the live path.
    preds2 = extractor.extract_from_pdf(str(pdf_path))
    assert sorted(p.tag for p in preds2) == tags
    assert [p.to_dict() for p in preds2] == [p.to_dict() for p in preds]
