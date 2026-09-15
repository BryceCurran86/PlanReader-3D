"""Priority 2: W4 stable wall identity — path-fingerprint assembly ids.

Gold-free. Proves geometry-only assembly identity properties without raising
wall measurement authority or changing live ExtractedPrediction output.
"""
from __future__ import annotations

from pathlib import Path

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_wall_room_topology_wall_assembly import (
    _canonical_wall_candidate_id,
    assemble_wall_candidates,
)
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_identity_v2 import (
    canonical_path_fingerprint,
    canonical_wall_candidate_id_v2,
)


def _seg(seg_id: str, x1: float, y1: float, x2: float, y2: float) -> dict:
    return {
        "id": seg_id,
        "kind": "line",
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "width": 1.0,
        "width_present": True,
        "stroke": (0, 0, 0),
        "stroke_present": True,
        "fill": None,
        "fill_present": False,
        "layer": "",
        "layer_present": False,
        "dashes": "",
        "dashes_present": False,
        "clip": None,
        "clip_present": False,
        "clip_known": True,
        "path_index": 0,
        "item_index": 0,
    }


def _assemble(segments):
    graph = build_wall_graph_for_viewport(segments)
    junctions, relationships = classify_junctions(
        graph, document_id="d", page_id="p", viewport_id="vp"
    )
    walls, edge_map = assemble_wall_candidates(
        graph, junctions, relationships, viewport_id="vp"
    )
    return walls, edge_map, graph


def test_p2_reversed_path_same_id() -> None:
    forward = _canonical_wall_candidate_id("vp", [(0.0, 0.0), (50.0, 10.0), (100.0, 0.0)])
    reversed_id = _canonical_wall_candidate_id(
        "vp", [(100.0, 0.0), (50.0, 10.0), (0.0, 0.0)]
    )
    assert forward == reversed_id


def test_p2_resegmented_collinear_path_same_id() -> None:
    one = _canonical_wall_candidate_id("vp", [(0.0, 0.0), (300.0, 0.0)])
    three = _canonical_wall_candidate_id(
        "vp", [(0.0, 0.0), (100.0, 0.0), (200.0, 0.0), (300.0, 0.0)]
    )
    assert one == three
    walls_one, _, _ = _assemble([_seg("a", 0, 0, 300, 0)])
    walls_three, _, _ = _assemble(
        [
            _seg("a", 0, 0, 100, 0),
            _seg("b", 100, 0, 200, 0),
            _seg("c", 200, 0, 300, 0),
        ]
    )
    assert walls_one[0].candidate_id == walls_three[0].candidate_id


def test_p2_same_endpoints_different_interior_path_different_id() -> None:
    straight = _canonical_wall_candidate_id("vp", [(0.0, 0.0), (100.0, 0.0)])
    detour = _canonical_wall_candidate_id(
        "vp", [(0.0, 0.0), (50.0, 40.0), (100.0, 0.0)]
    )
    assert straight != detour
    # Endpoint-only collision proof at the fingerprint layer.
    assert canonical_path_fingerprint([(0.0, 0.0), (100.0, 0.0)]) != canonical_path_fingerprint(
        [(0.0, 0.0), (50.0, 40.0), (100.0, 0.0)]
    )


def test_p2_duplicate_traced_representation_does_not_crash_dicts() -> None:
    walls, edge_map, _ = _assemble(
        [_seg("wall", 0, 0, 300, 0), _seg("wall_copy", 0, 0, 300, 0)]
    )
    assert len(walls) == 1
    # Downstream dict keyed by candidate_id must remain well-formed.
    by_id = {w.candidate_id: w for w in walls}
    assert len(by_id) == 1
    assert set(edge_map.values()) == {walls[0].candidate_id}


def test_p2_deterministic_replay_and_input_order() -> None:
    segments = [
        _seg("bar1", 0, 0, 150, 0),
        _seg("bar2", 150, 0, 300, 0),
        _seg("stem", 150, 0, 150, -80),
    ]
    first, _, _ = _assemble(segments)
    second, _, _ = _assemble(segments)
    shuffled, _, _ = _assemble(list(reversed(segments)))
    assert {w.candidate_id for w in first} == {w.candidate_id for w in second}
    assert {w.candidate_id for w in first} == {w.candidate_id for w in shuffled}


def test_p2_translation_changes_id_rotation_preserves_structure() -> None:
    # Canonical coordinate contract: absolute page coords participate, so a
    # pure translation yields a different id; structure/count stays invariant
    # under rotation (existing assembly metamorphic contract).
    base, _, _ = _assemble([_seg("a", 0, 0, 300, 0), _seg("b", 300, 0, 300, 200)])
    translated, _, _ = _assemble(
        [_seg("a", 50, 50, 350, 50), _seg("b", 350, 50, 350, 250)]
    )
    assert len(base) == len(translated) == 2
    assert {w.candidate_id for w in base} != {w.candidate_id for w in translated}

    rotated, _, _ = _assemble([_seg("a", 0, 0, 0, 300), _seg("b", 0, 300, -200, 300)])
    assert len(rotated) == 2


def test_p2_stable_identity_does_not_promote_wall_authority() -> None:
    walls, _, _ = _assemble([_seg("a", 0, 0, 300, 0)])
    wall = walls[0]
    assert wall.status == EvidenceResolutionStatus.CANDIDATE
    assert wall.length_m is None
    assert wall.thickness_m is None
    # Hybrid sidecar id may differ from geometry-only assembly id; neither
    # is firm measurement authority.
    sidecar = canonical_wall_candidate_id_v2(
        wall.viewport_id,
        list(wall.face_a_segment_ids),
        {
            eid: {
                "id": eid,
                "x1": wall.centerline_pts[0][0],
                "y1": wall.centerline_pts[0][1],
                "x2": wall.centerline_pts[-1][0],
                "y2": wall.centerline_pts[-1][1],
                "primitive_lineage": {"source_primitive_ids": ["a"]},
            }
            for eid in wall.face_a_segment_ids
        },
        wall.centerline_pts[0],
        wall.centerline_pts[-1],
    )
    assert isinstance(sidecar, str) and sidecar
    assert wall.status == EvidenceResolutionStatus.CANDIDATE
    assert wall.reason_codes  # assembly reasons only; no firm quantity promotion


def test_p2_live_extractor_predictions_unchanged(tmp_path: Path) -> None:
    pdf_path = tmp_path / "p2-live.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((40, 40), "SCALE 1:100 FLOOR PLAN")
    page.draw_rect(fitz.Rect(50, 80, 250, 280), color=(0, 0, 0), width=1)
    doc.save(pdf_path)
    doc.close()

    extractor = GenericPlanReaderExtractor()
    preds = extractor.extract_from_pdf(str(pdf_path))
    preds2 = extractor.extract_from_pdf(str(pdf_path))
    assert [p.to_dict() for p in preds2] == [p.to_dict() for p in preds]
    for pred in preds:
        payload = pred.to_dict()
        assert "wall_candidate_id" not in payload
        assert "primitive_lineage" not in payload
