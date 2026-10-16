"""Synthetic proofs for exact annotation-cycle shadow classification.

Colour, width, and text nearness alone must not quarantine a segment.
"""
from __future__ import annotations

import math
from copy import deepcopy

import pytest

from pb_annotation_cycle_shadow import (
    _cycle_edges_cross,
    _without_proven_annotation_cycles,
    classify_exact_annotation_cycles,
    scope_segments_without_proven_annotation_cycles,
    segments_without_proven_annotation_cycles,
    shadow_annotation_cycle_post_identity_report,
    shadow_annotation_cycle_topology,
    wall_annotation_ancestry,
)

PAGE_SPAN = 2000.0
VIEW = (-500.0, -500.0, 500.0, 500.0)


def _line(sid, x1, y1, x2, y2, *, path, width=0.48, stroke=(0.0, 0.0, 0.0),
          dashes="[] 0", fill=None):
    return {
        "id": sid, "kind": "line", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "width": width, "stroke": stroke, "fill": fill, "dashes": dashes,
        "layer": "", "path_index": path, "item_index": 0,
    }


def _ring(n=16, radius=8.0, cx=0.0, cy=0.0, prefix="mark"):
    segments = []
    points = [
        (cx + radius * math.cos(2.0 * math.pi * i / n),
         cy + radius * math.sin(2.0 * math.pi * i / n))
        for i in range(n)
    ]
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1])):
        segments.append(_line(
            f"{prefix}{index}", start[0], start[1], end[0], end[1], path=1000 + index,
        ))
    return segments


def _word(text="MARK", x0=-1.0, y0=-1.0, x1=1.0, y1=1.0):
    return {"text": text, "x0": x0, "y0": y0, "x1": x1, "y1": y1}


def test_closed_singleton_cycle_containing_text_is_quarantined():
    result = classify_exact_annotation_cycles(
        _ring(), [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}
    assert result["cycles"][0]["status"] == "source_proven_annotation_cycle"
    assert result["cycles"][0]["contained_source_text"][0]["text"] == "MARK"
    assert result["diagnostic_only"]
    assert not result["quantity_or_metric_area_published"]
    assert not result["structural_wall_role_authenticated"]


def test_same_cycle_is_proven_for_a_different_stroke_and_width():
    segments = _ring()
    for segment in segments:
        segment["width"] = 0.24
        segment["stroke"] = (0.5, 0.5, 0.5)
    result = classify_exact_annotation_cycles(
        segments, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert len(result["quarantined_primitive_ids"]) == 16


def test_input_order_does_not_change_the_quarantine():
    forward = classify_exact_annotation_cycles(
        _ring(), [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    backward = classify_exact_annotation_cycles(
        list(reversed(_ring())), [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert forward["quarantined_primitive_ids"] == backward["quarantined_primitive_ids"]


def test_orthogonal_room_loop_with_interior_text_is_preserved():
    room = [
        _line("w0", 0, 0, 80, 0, path=1),
        _line("w1", 80, 0, 80, 40, path=2),
        _line("w2", 80, 40, 0, 40, path=3),
        _line("w3", 0, 40, 0, 0, path=4),
    ]
    result = classify_exact_annotation_cycles(
        room, [_word("ROOM", 30, 15, 40, 20)], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []


def test_short_wall_return_and_nearby_text_are_preserved():
    segments = [_line("return", 0, 0, 4, 0, path=1)]
    result = classify_exact_annotation_cycles(
        segments, [_word("N", 0.2, 0.4, 1.0, 1.2)], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []


def test_text_outside_a_closed_cycle_does_not_quarantine_it():
    result = classify_exact_annotation_cycles(
        _ring(), [_word(x0=30, y0=30, x1=34, y1=34)],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []


def test_open_chord_chain_is_not_a_cycle():
    segments = _ring()[:-1]
    result = classify_exact_annotation_cycles(
        segments, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []


def test_dashed_closed_mark_and_multi_item_path_are_preserved():
    dashed = _ring()
    for segment in dashed:
        segment["dashes"] = "[1 1] 0"
    shared = _ring(prefix="shared")
    for segment in shared:
        segment["path_index"] = 7
    dashed_result = classify_exact_annotation_cycles(
        dashed, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    shared_result = classify_exact_annotation_cycles(
        shared, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert dashed_result["quarantined_primitive_ids"] == []
    assert shared_result["quarantined_primitive_ids"] == []


def test_collinear_structural_continuation_blocks_quarantine():
    segments = _ring()
    chord = segments[0]
    dx = float(chord["x2"]) - float(chord["x1"])
    dy = float(chord["y2"]) - float(chord["y1"])
    length = math.hypot(dx, dy)
    segments.append(_line(
        "wall", chord["x2"], chord["y2"],
        chord["x2"] + dx / length * 40.0, chord["y2"] + dy / length * 40.0,
        path=50,
    ))
    result = classify_exact_annotation_cycles(
        segments, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []
    blocked = next(row for row in result["cycles"] if "mark0" in row["primitive_ids"])
    assert "competing_structural_continuation" in blocked["failed_gates"]


def test_cycle_outside_the_viewport_is_not_owned():
    result = classify_exact_annotation_cycles(
        _ring(), [_word()], page_span=PAGE_SPAN, viewport_bbox=(100, 100, 120, 120),
    )
    assert result["quarantined_primitive_ids"] == []


def test_shadow_withholds_the_cycle_and_keeps_the_crossing_geometry():
    segments = _ring(n=16, radius=4.0, cx=4.528, cy=4.528)
    segments.extend((
        _line("h", -40, 0, 40, 0, path=1, width=0.24, stroke=(0.5, 0.5, 0.5)),
        _line("v", 0, -40, 0, 40, path=2, width=0.24, stroke=(0.5, 0.5, 0.5)),
    ))
    report = shadow_annotation_cycle_topology(
        segments, [_word("MARK", 4.0, 4.0, 5.0, 5.0)],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-shadow",
    )
    assert report["classification"]["quarantined_primitive_ids"]
    assert report["unaffected_non_annotation_edge_geometry_unchanged"]
    baseline_nodes = {(node["x"], node["y"], node["samples"]) for node in report["baseline"]["w2_nodes"]}
    shadow_nodes = {(node["x"], node["y"], node["samples"]) for node in report["shadow_with_proven_cycles_withheld_from_snap_input"]["w2_nodes"]}
    assert any(samples > 4 for _x, _y, samples in baseline_nodes)
    assert (0.0, 0.0, 4) in {(round(x, 6), round(y, 6), samples) for x, y, samples in shadow_nodes}
    assert not any(
        sid.startswith("mark")
        for wall in report["shadow_with_proven_cycles_withheld_from_snap_input"]["w4_source_primitive_ids"]
        for sid in wall
    )
    assert report["diagnostic_only"]


def test_shadow_copy_does_not_mutate_the_caller_segments():
    segments = _ring()
    original = deepcopy(segments)
    classify_exact_annotation_cycles(
        segments, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert segments == original


def test_unstroked_rectangle_side_does_not_count_as_a_wall_continuation():
    segments = _ring()
    chord = segments[0]
    dx = float(chord["x2"]) - float(chord["x1"])
    dy = float(chord["y2"]) - float(chord["y1"])
    length = math.hypot(dx, dy)
    segments.append(_line(
        "rect-side", chord["x2"], chord["y2"],
        chord["x2"] + dx / length * 40.0, chord["y2"] + dy / length * 40.0,
        path=60, width=0.0, stroke=None,
    ))
    result = classify_exact_annotation_cycles(
        segments, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert len(result["quarantined_primitive_ids"]) == 16
    assert "rect-side" not in result["quarantined_primitive_ids"]


def test_missing_page_span_fails_closed():
    with pytest.raises(ValueError):
        classify_exact_annotation_cycles(_ring(), [_word()], page_span=0.0)


def test_proven_cycle_is_removed_from_wall_input_and_a_room_is_not():
    ring = _ring()
    room = [
        _line("w0", 0, 0, 80, 0, path=1),
        _line("w1", 80, 0, 80, 40, path=2),
        _line("w2", 80, 40, 0, 40, path=3),
        _line("w3", 0, 40, 0, 0, path=4),
    ]
    kept = segments_without_proven_annotation_cycles(
        ring + room, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert [segment["id"] for segment in kept] == ["w0", "w1", "w2", "w3"]
    unchanged = segments_without_proven_annotation_cycles(
        ring, [], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert [segment["id"] for segment in unchanged] == [segment["id"] for segment in ring]
    receipt = _receipt("MARK", (-1.0, -1.0, 1.0, 1.0))
    withheld = scope_segments_without_proven_annotation_cycles(
        ring, classification_segments=ring, text_receipts=(receipt,),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert withheld == ()


def test_leftover_chord_is_removed_when_the_cycle_is_proved_earlier():
    ring = _ring()
    receipt = _receipt("MARK", (-1.0, -1.0, 1.0, 1.0))
    leftover = scope_segments_without_proven_annotation_cycles(
        ring[:1], classification_segments=ring, text_receipts=(receipt,),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert leftover == ()


def test_the_live_wall_authority_does_not_call_the_annotation_shadow():
    import pb_physical_wall_candidate_authority as wall_mod

    source = open(wall_mod.__file__, encoding="utf-8").read()
    assert "pb_annotation_cycle_shadow" not in source
    assert "annotation_cycles" not in source


class TestNoQuantityOrLiveWiring:
    """Production must not import or call the annotation-cycle shadow."""

    def test_no_production_module_imports_annotation_cycle_shadow(self) -> None:
        import ast
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        skip = {"tests", "benchmarks", "scripts", "tools", "node_modules"}
        offenders = []
        for path in sorted(root.rglob("*.py")):
            rel = path.relative_to(root)
            if rel.parts[0] in skip or any(part.startswith(".") for part in rel.parts):
                continue
            if path.name.startswith("tmp_"):
                continue
            if path.name == "pb_annotation_cycle_shadow.py":
                continue
            tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            imported = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.extend(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.append(node.module)
                elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                    imported.append(node.value)
            if any(
                name == "pb_annotation_cycle_shadow"
                or name.startswith("pb_annotation_cycle_shadow.")
                for name in imported
            ):
                offenders.append(path.name)
        assert offenders == []

    def test_shadow_does_not_construct_quantity_evidence(self) -> None:
        import pb_annotation_cycle_shadow as mod

        source = open(mod.__file__, encoding="utf-8").read()
        assert "import QuantityEvidence" not in source
        assert "QuantityEvidence(" not in source
        assert not hasattr(mod, "QuantityEvidence")

    def test_not_imported_by_live_extractor(self) -> None:
        source = open("pb_planreader_pdf_extractor.py", encoding="utf-8").read()
        assert "pb_annotation_cycle_shadow" not in source


def test_chorded_component_is_not_removed_when_one_face_leaves_edges_out():
    ring = _ring()
    chord = _line(
        "chord", ring[0]["x1"], ring[0]["y1"], ring[4]["x1"], ring[4]["y1"], path=9,
    )
    result = classify_exact_annotation_cycles(
        ring + [chord], [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []
    assert any(
        "block_not_covered_by_one_source_word" in record["failed_gates"]
        for record in result["cycles"]
    )


def _rect_edge(sid, x1, y1, x2, y2, *, path, stroke=None, width=0.0, fill=(1.0, 1.0, 1.0)):
    return {
        "id": sid, "kind": "rect_edge", "x1": x1, "y1": y1, "x2": x2, "y2": y2,
        "width": width, "stroke": stroke, "fill": fill, "dashes": "",
        "layer": "", "path_index": path, "item_index": 0,
    }


def _frame(path, x0, y0, x1, y1, prefix, **kwargs):
    return [
        _rect_edge(f"{prefix}0", x0, y0, x1, y0, path=path, **kwargs),
        _rect_edge(f"{prefix}1", x1, y0, x1, y1, path=path, **kwargs),
        _rect_edge(f"{prefix}2", x1, y1, x0, y1, path=path, **kwargs),
        _rect_edge(f"{prefix}3", x0, y1, x0, y0, path=path, **kwargs),
    ]


def test_unstroked_frame_around_a_proven_cycle_is_withheld():
    ring = _ring()
    frame = _frame(50, -20.0, -20.0, 20.0, 20.0, "frame")
    far = _frame(51, 200.0, 200.0, 230.0, 230.0, "far")
    stroked = _frame(52, -20.0, -20.0, 20.0, 20.0, "stroke", stroke=(0.0, 0.0, 0.0), width=0.48)
    huge = _frame(53, -80.0, -80.0, 80.0, 80.0, "huge")
    result = classify_exact_annotation_cycles(
        ring + frame + far + stroked + huge, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    quarantined = set(result["quarantined_primitive_ids"])
    assert set(result["frame_primitive_ids"]) == {"frame0", "frame1", "frame2", "frame3"}
    assert {"frame0", "frame1", "frame2", "frame3"} <= quarantined
    assert not quarantined.intersection({"far0", "stroke0", "huge0"})


def _classify(segments, words=None, *, page_span=PAGE_SPAN, viewport=VIEW):
    return classify_exact_annotation_cycles(
        segments, [_word()] if words is None else words,
        page_span=page_span, viewport_bbox=viewport,
    )


def _shift(segments, dx, dy):
    moved = []
    for segment in segments:
        copy = dict(segment)
        copy["x1"] += dx
        copy["y1"] += dy
        copy["x2"] += dx
        copy["y2"] += dy
        moved.append(copy)
    return moved


def test_translation_preserves_the_quarantine():
    moved = _shift(_ring(), 40.0, -25.0)
    result = _classify(moved, [_word(x0=39.0, y0=-26.0, x1=41.0, y1=-24.0)])
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_rotation_preserves_the_quarantine():
    rotated = []
    for segment in _ring():
        copy = dict(segment)
        copy["x1"], copy["y1"] = -segment["y1"], segment["x1"]
        copy["x2"], copy["y2"] = -segment["y2"], segment["x2"]
        rotated.append(copy)
    result = _classify(rotated)
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_uniform_scale_preserves_the_quarantine():
    scaled = []
    for segment in _ring():
        copy = dict(segment)
        for key in ("x1", "y1", "x2", "y2"):
            copy[key] = segment[key] * 3.0
        scaled.append(copy)
    result = _classify(
        scaled, [_word(x0=-3.0, y0=-3.0, x1=3.0, y1=3.0)],
        page_span=PAGE_SPAN * 3.0,
        viewport=(-1500.0, -1500.0, 1500.0, 1500.0),
    )
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_splitting_one_edge_into_singleton_pieces_keeps_the_block():
    ring = _ring()
    edge = ring[0]
    mid_x = (edge["x1"] + edge["x2"]) / 2.0
    mid_y = (edge["y1"] + edge["y2"]) / 2.0
    pieces = [
        _line("mark0a", edge["x1"], edge["y1"], mid_x, mid_y, path=5000),
        _line("mark0b", mid_x, mid_y, edge["x2"], edge["y2"], path=5001),
    ]
    result = _classify(pieces + ring[1:])
    assert "mark0" not in result["quarantined_primitive_ids"]
    assert {"mark0a", "mark0b"} <= set(result["quarantined_primitive_ids"])


def test_unrelated_distant_line_is_not_quarantined():
    extra = _line("far", 400.0, 400.0, 460.0, 400.0, path=8)
    result = _classify(_ring() + [extra])
    assert "far" not in result["quarantined_primitive_ids"]
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_growing_the_viewport_does_not_change_an_owned_cycle():
    tight = _classify(_ring(), viewport=(-12.0, -12.0, 12.0, 12.0))
    wide = _classify(_ring(), viewport=(-400.0, -400.0, 400.0, 400.0))
    assert tight["quarantined_primitive_ids"] == wide["quarantined_primitive_ids"]


def test_replay_is_deterministic():
    first = _classify(_ring())
    second = _classify(_ring())
    assert first["quarantined_primitive_ids"] == second["quarantined_primitive_ids"]
    assert [row["status"] for row in first["cycles"]] == [row["status"] for row in second["cycles"]]


def test_hatch_lattice_longer_than_the_span_is_preserved():
    lines = []
    for index in range(6):
        lines.append(_line(f"h{index}", 0.0, index * 8.0, 40.0, index * 8.0, path=index))
        lines.append(_line(f"v{index}", index * 8.0, 0.0, index * 8.0, 40.0, path=20 + index))
    result = _classify(lines, [_word(x0=10.0, y0=10.0, x1=12.0, y1=12.0)])
    assert result["quarantined_primitive_ids"] == []


def test_disconnected_dimension_ticks_are_preserved():
    ticks = [
        _line(f"tick{index}", 10.0 * index, 0.0, 10.0 * index, 2.0, path=index)
        for index in range(8)
    ]
    result = _classify(ticks, [_word(x0=1.0, y0=-0.5, x1=2.0, y1=0.5)])
    assert result["quarantined_primitive_ids"] == []


def test_four_edge_title_frame_is_preserved():
    frame = [
        _line("f0", 0.0, 0.0, 80.0, 0.0, path=1),
        _line("f1", 80.0, 0.0, 80.0, 40.0, path=2),
        _line("f2", 80.0, 40.0, 0.0, 40.0, path=3),
        _line("f3", 0.0, 40.0, 0.0, 0.0, path=4),
    ]
    result = _classify(frame, [_word(x0=30.0, y0=15.0, x1=34.0, y1=19.0)])
    assert result["quarantined_primitive_ids"] == []


def test_small_furniture_loop_is_preserved():
    square = [
        _line("s0", -3.0, -3.0, 3.0, -3.0, path=1),
        _line("s1", 3.0, -3.0, 3.0, 3.0, path=2),
        _line("s2", 3.0, 3.0, -3.0, 3.0, path=3),
        _line("s3", -3.0, 3.0, -3.0, -3.0, path=4),
    ]
    result = _classify(square)
    assert result["quarantined_primitive_ids"] == []


def test_dashed_glazing_loop_is_preserved():
    ring = _ring()
    for segment in ring:
        segment["dashes"] = "[2 2] 0"
    result = _classify(ring)
    assert result["quarantined_primitive_ids"] == []


def test_two_words_inside_one_block_do_not_split_it():
    result = _classify(_ring(), [_word(text="A"), _word(text="B", x0=-0.4, y0=-0.4, x1=0.4, y1=0.4)])
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}
    texts = {
        item["text"]
        for row in result["cycles"]
        if row["status"] == "source_proven_annotation_cycle"
        for item in row["contained_source_text"]
    }
    assert texts == {"A", "B"}


def test_quarantine_ids_stay_sorted():
    result = _classify(list(reversed(_ring())))
    assert result["quarantined_primitive_ids"] == sorted(result["quarantined_primitive_ids"])


def test_classification_does_not_mutate_segment_coordinates():
    segments = _ring()
    before = [(segment["id"], segment["x1"], segment["y1"], segment["x2"], segment["y2"]) for segment in segments]
    _classify(segments)
    after = [(segment["id"], segment["x1"], segment["y1"], segment["x2"], segment["y2"]) for segment in segments]
    assert before == after


def _receipt(text, geometry, *, trusted=False, reasons=None):
    from types import SimpleNamespace
    from pb_pdf_text_integrity_authority import (
        TEXT_CLIP_STATE_UNRESOLVED,
        TEXT_GLYPH_MAPPING_UNVERIFIED,
    )
    if reasons is None:
        reasons = () if trusted else (TEXT_GLYPH_MAPPING_UNVERIFIED, TEXT_CLIP_STATE_UNRESOLVED)
    return SimpleNamespace(
        raw_text=text, geometry=geometry, trusted=trusted, reason_codes=tuple(reasons),
    )


def _withhold(segments, receipts):
    from types import SimpleNamespace
    return _without_proven_annotation_cycles(
        segments, classification_segments=segments, text_receipts=receipts,
        page_width=PAGE_SPAN, page_height=PAGE_SPAN,
        viewport=SimpleNamespace(bounding_box=VIEW),
    )


def test_a_trusted_receipt_proves_the_cycle():
    ring = _ring()
    assert _withhold(ring, (_receipt("MARK", (-1, -1, 1, 1), trusted=True),)) == ()


@pytest.mark.parametrize("reason", [
    "text_render_mode_untrusted",
    "text_opacity_untrusted",
    "text_optional_content_off",
    "text_optional_content_unresolved",
    "text_occluded_by_later_paint",
    "text_clipped_by_clip_region",
    "text_low_contrast_default_page",
    "text_trace_unavailable",
    "text_decode_mismatch",
])
def test_a_word_the_text_authority_cannot_show_proves_nothing(reason):
    import pb_pdf_text_integrity_authority as text_authority
    assert reason in {
        value for name, value in vars(text_authority).items()
        if name.startswith("TEXT_") and isinstance(value, str)
    }
    ring = _ring()
    receipt = _receipt(
        "MARK", (-1, -1, 1, 1),
        reasons=(text_authority.TEXT_GLYPH_MAPPING_UNVERIFIED, reason),
    )
    assert [segment["id"] for segment in _withhold(ring, (receipt,))] == [
        segment["id"] for segment in ring
    ]


def test_an_untrusted_receipt_without_reasons_proves_nothing():
    ring = _ring()
    receipt = _receipt("MARK", (-1, -1, 1, 1), trusted=False, reasons=())
    assert [segment["id"] for segment in _withhold(ring, (receipt,))] == [
        segment["id"] for segment in ring
    ]


def test_blank_receipt_text_leaves_the_wall_input_unchanged():
    ring = _ring()
    assert [segment["id"] for segment in _withhold(ring, (_receipt("   ", (-1, -1, 1, 1)),))] == [
        segment["id"] for segment in ring
    ]


def test_reversed_receipt_box_does_not_withhold_the_ring():
    ring = _ring()
    assert len(_withhold(ring, (_receipt("MARK", (1.0, 1.0, -1.0, -1.0)),))) == len(ring)


def test_short_receipt_geometry_does_not_withhold_the_ring():
    ring = _ring()
    assert len(_withhold(ring, (_receipt("MARK", (0.0, 0.0, 1.0)),))) == len(ring)


def test_non_finite_receipt_box_does_not_withhold_the_ring():
    ring = _ring()
    assert len(_withhold(ring, (_receipt("MARK", (0.0, 0.0, float("nan"), 1.0)),))) == len(ring)


def test_duplicate_primitive_ids_are_not_quarantined():
    ring = _ring()
    copy = dict(ring[0])
    result = classify_exact_annotation_cycles(
        ring + [copy], [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert "mark0" not in result["quarantined_primitive_ids"]


def test_missing_path_index_does_not_raise_or_quarantine():
    ring = _ring()
    for segment in ring:
        segment["path_index"] = None
    result = classify_exact_annotation_cycles(
        ring, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []


def test_non_finite_coordinate_does_not_raise_or_quarantine():
    ring = _ring()
    ring[0]["x1"] = float("nan")
    result = classify_exact_annotation_cycles(
        ring, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert "mark0" not in result["quarantined_primitive_ids"]


def test_word_order_does_not_change_the_quarantine():
    first = _classify(_ring(), [_word(text="A"), _word(text="B", x0=-0.4, y0=-0.4, x1=0.4, y1=0.4)])
    second = _classify(_ring(), [_word(text="B", x0=-0.4, y0=-0.4, x1=0.4, y1=0.4), _word(text="A")])
    assert first["quarantined_primitive_ids"] == second["quarantined_primitive_ids"]


def test_a_thicker_four_edge_loop_stays_when_the_thin_mark_is_withheld():
    thick = [
        _line("t0", -6.0, -6.0, 6.0, -6.0, path=11, width=2.0),
        _line("t1", 6.0, -6.0, 6.0, 6.0, path=12, width=2.0),
        _line("t2", 6.0, 6.0, -6.0, 6.0, path=13, width=2.0),
        _line("t3", -6.0, 6.0, -6.0, -6.0, path=14, width=2.0),
    ]
    result = _classify(_ring() + thick)
    quarantined = set(result["quarantined_primitive_ids"])
    assert {f"mark{i}" for i in range(16)} <= quarantined
    assert not quarantined.intersection({"t0", "t1", "t2", "t3"})


def test_kept_wall_segments_keep_their_source_attributes():
    room = _line("w0", 0.0, 0.0, 80.0, 0.0, path=7)
    room["layer"] = "WALL"
    room["clip"] = (0.0, 0.0, 100.0, 100.0)
    kept = _withhold(
        _ring() + [room],
        (_receipt("MARK", (-1.0, -1.0, 1.0, 1.0)),),
    )
    assert len(kept) == 1
    assert kept[0]["id"] == "w0"
    assert kept[0]["width"] == 0.48
    assert kept[0]["stroke"] == (0.0, 0.0, 0.0)
    assert kept[0]["dashes"] == "[] 0"
    assert kept[0]["layer"] == "WALL"
    assert kept[0]["path_index"] == 7
    assert kept[0]["clip"] == (0.0, 0.0, 100.0, 100.0)


def test_direct_reversed_word_box_does_not_quarantine():
    result = _classify(_ring(), [_word(x0=1.0, y0=1.0, x1=-1.0, y1=-1.0)])
    assert result["quarantined_primitive_ids"] == []


def test_whitespace_word_does_not_quarantine():
    result = _classify(_ring(), [_word(text="  ")])
    assert result["quarantined_primitive_ids"] == []


def test_zero_area_word_box_does_not_quarantine():
    result = _classify(_ring(), [_word(x0=-1.0, y0=0.0, x1=1.0, y1=0.0)])
    assert result["quarantined_primitive_ids"] == []


def test_non_finite_word_box_does_not_quarantine():
    result = _classify(_ring(), [_word(x1=float("inf"))])
    assert result["quarantined_primitive_ids"] == []


def test_string_path_index_does_not_raise_or_quarantine():
    ring = _ring()
    for segment in ring:
        segment["path_index"] = "1000"
    result = classify_exact_annotation_cycles(
        ring, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []


def test_endpoints_that_only_meet_after_rounding_do_not_close():
    ring = _ring()
    ring[0]["x1"] += 5e-7
    result = _classify(ring)
    assert result["quarantined_primitive_ids"] == []


def test_word_corner_on_a_ring_vertex_does_not_quarantine():
    result = _classify(_ring(), [_word(x0=7.5, y0=-0.2, x1=8.0, y1=0.2)])
    assert result["quarantined_primitive_ids"] == []


def test_reversed_viewport_does_not_own_the_ring():
    result = classify_exact_annotation_cycles(
        _ring(), [_word()], page_span=PAGE_SPAN, viewport_bbox=(500.0, 500.0, -500.0, -500.0),
    )
    assert result["quarantined_primitive_ids"] == []


def test_non_finite_page_span_fails_closed():
    with pytest.raises(ValueError):
        classify_exact_annotation_cycles(_ring(), [_word()], page_span=float("nan"))


def test_negative_page_span_fails_closed():
    with pytest.raises(ValueError):
        classify_exact_annotation_cycles(_ring(), [_word()], page_span=-PAGE_SPAN)


def test_missing_viewport_leaves_the_shadow_input_unchanged():
    from pb_annotation_cycle_shadow import segments_without_proven_annotation_cycles
    ring = _ring()
    kept = segments_without_proven_annotation_cycles(
        ring, [_word()], page_span=PAGE_SPAN, viewport_bbox=None,
    )
    assert [segment["id"] for segment in kept] == [segment["id"] for segment in ring]


def test_empty_segment_list_returns_no_quarantine():
    result = classify_exact_annotation_cycles(
        [], [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert result["quarantined_primitive_ids"] == []
    assert result["diagnostic_only"]
    assert not result["quantity_or_metric_area_published"]


def test_a_layer_name_does_not_quarantine_an_open_chain():
    chain = [
        _line("c0", 0.0, 0.0, 4.0, 1.0, path=1),
        _line("c1", 4.0, 1.0, 8.0, 0.0, path=2),
    ]
    for segment in chain:
        segment["layer"] = "DIM"
    result = _classify(chain)
    assert result["quarantined_primitive_ids"] == []


def test_a_layer_name_does_not_block_a_proven_ring():
    ring = _ring()
    for segment in ring:
        segment["layer"] = "ANNO"
    result = _classify(ring)
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_a_five_edge_path_is_not_a_frame():
    ring = _ring()
    frame = _frame(50, -20.0, -20.0, 20.0, 20.0, "frame")
    extra = _rect_edge("frame4", -20.0, -20.0, -20.0, -10.0, path=50)
    result = classify_exact_annotation_cycles(
        ring + frame + [extra], [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    quarantined = set(result["quarantined_primitive_ids"])
    assert {f"mark{i}" for i in range(16)} <= quarantined
    assert not quarantined.intersection({"frame0", "frame4"})


def test_quarantine_ids_are_a_subset_of_the_input_ids():
    segments = _ring() + [_line("wall", 0.0, 0.0, 80.0, 0.0, path=7)]
    result = _classify(segments)
    assert set(result["quarantined_primitive_ids"]) <= {segment["id"] for segment in segments}
    assert "wall" not in result["quarantined_primitive_ids"]


def test_absent_viewport_uses_the_page_box_for_an_in_page_mark():
    ring = _ring(cx=100.0, cy=100.0)
    kept = _without_proven_annotation_cycles(
        ring, classification_segments=ring,
        text_receipts=(_receipt("MARK", (99.0, 99.0, 101.0, 101.0)),),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN, viewport=None,
    )
    assert kept == ()


def test_absent_viewport_does_not_own_a_mark_outside_the_page():
    ring = _ring(cx=-100.0, cy=-100.0)
    kept = _without_proven_annotation_cycles(
        ring, classification_segments=ring,
        text_receipts=(_receipt("MARK", (-101.0, -101.0, -99.0, -99.0)),),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN, viewport=None,
    )
    assert [segment["id"] for segment in kept] == [segment["id"] for segment in ring]


def test_non_finite_frame_edge_does_not_raise():
    bad = _rect_edge("bad", float("nan"), 0.0, 10.0, 0.0, path=9)
    result = classify_exact_annotation_cycles(
        _ring() + [bad], [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert "bad" not in result["quarantined_primitive_ids"]
    assert len(result["quarantined_primitive_ids"]) == 16


def test_repeated_word_boxes_quarantine_the_ring_once():
    result = _classify(_ring(), [_word(), _word()])
    assert result["quarantined_primitive_ids"].count("mark0") == 1
    assert len(result["quarantined_primitive_ids"]) == 16


def _collinear_tail(length):
    segments = _ring()
    chord = segments[0]
    dx = float(chord["x2"]) - float(chord["x1"])
    dy = float(chord["y2"]) - float(chord["y1"])
    edge = math.hypot(dx, dy)
    segments.append(_line(
        "wall", chord["x2"], chord["y2"],
        chord["x2"] + dx / edge * length, chord["y2"] + dy / edge * length,
        path=50,
    ))
    return segments


def test_integer_and_float_path_indexes_are_the_same_path():
    ring = _ring()
    ring[0]["path_index"] = 1
    other = _line("other", 100.0, 100.0, 104.0, 100.0, path=1.0)
    result = _classify(ring + [other])
    assert result["quarantined_primitive_ids"] == []
    fractional = _ring(prefix="frac")
    fractional[0]["path_index"] = 1.9
    kept = _classify(fractional)
    assert kept["quarantined_primitive_ids"] == []


def test_missing_dash_pattern_still_counts_as_solid():
    ring = _ring()
    for segment in ring:
        segment["dashes"] = None
    result = _classify(ring)
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}
    flagged = _ring()
    for segment in flagged:
        segment["dashes"] = False
    assert _classify(flagged)["quarantined_primitive_ids"] == []


def test_list_and_tuple_strokes_form_one_family():
    ring = _ring()
    for segment in ring[:8]:
        segment["stroke"] = [0, 0, 0]
    result = _classify(ring)
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_integer_and_float_stroke_components_form_one_family():
    ring = _ring()
    for segment in ring[::2]:
        segment["stroke"] = (0, 0, 0)
    result = _classify(ring)
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_an_empty_fill_list_does_not_quarantine_or_raise():
    ring = _ring()
    for segment in ring:
        segment["fill"] = []
    result = _classify(ring)
    assert result["quarantined_primitive_ids"] == []


def test_a_non_numeric_width_is_not_quarantined():
    ring = _ring()
    for segment in ring:
        segment["width"] = "wide"
    result = _classify(ring)
    assert result["quarantined_primitive_ids"] == []


def test_a_zero_length_edge_does_not_enter_the_quarantine():
    dot = _line("dot", 0.0, 0.0, 0.0, 0.0, path=3)
    result = _classify(_ring() + [dot])
    assert "dot" not in result["quarantined_primitive_ids"]
    assert len(result["quarantined_primitive_ids"]) == 16


def test_a_clockwise_ring_is_quarantined():
    ring = _ring()
    for segment in ring:
        segment["x1"], segment["y1"], segment["x2"], segment["y2"] = (
            segment["x2"], segment["y2"], segment["x1"], segment["y1"],
        )
    result = _classify(ring)
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}


def test_only_the_ring_containing_the_word_is_quarantined():
    far = _ring(cx=40.0, cy=40.0, prefix="far")
    for segment in far:
        segment["path_index"] += 2000
    result = _classify(_ring() + far)
    quarantined = set(result["quarantined_primitive_ids"])
    assert quarantined == {f"mark{i}" for i in range(16)}


def test_a_short_collinear_tail_does_not_block_the_ring():
    result = _classify(_collinear_tail(4.0))
    assert {f"mark{i}" for i in range(16)} <= set(result["quarantined_primitive_ids"])
    assert "wall" not in result["quarantined_primitive_ids"]


def test_a_tail_at_the_span_limit_does_not_block_the_ring():
    result = _classify(_collinear_tail(PAGE_SPAN * 0.006))
    assert {f"mark{i}" for i in range(16)} <= set(result["quarantined_primitive_ids"])


def test_a_rectangle_edge_sharing_the_path_blocks_the_ring():
    ring = _ring()
    side = _rect_edge("side", 0.0, 0.0, 4.0, 0.0, path=float(ring[0]["path_index"]))
    result = _classify(ring + [side])
    assert result["quarantined_primitive_ids"] == []


def test_a_non_finite_viewport_bound_does_not_own_the_ring():
    result = classify_exact_annotation_cycles(
        _ring(), [_word()], page_span=PAGE_SPAN, viewport_bbox=(0.0, 0.0, float("nan"), 10.0),
    )
    assert result["quarantined_primitive_ids"] == []
    short = classify_exact_annotation_cycles(
        _ring(), [_word()], page_span=PAGE_SPAN, viewport_bbox=(0.0, 0.0, 10.0),
    )
    assert short["quarantined_primitive_ids"] == []


def test_an_infinite_page_span_fails_closed():
    with pytest.raises(ValueError):
        classify_exact_annotation_cycles(_ring(), [_word()], page_span=float("inf"))
    ring = _ring()
    kept = _withhold(ring, (_receipt("MARK", (-1.0, -1.0, 1.0, 1.0)),))
    # A caller with a real page span still withholds. An unreadable page size does not.
    assert kept == ()
    unchanged = _without_proven_annotation_cycles(
        ring, classification_segments=ring,
        text_receipts=(_receipt("MARK", (-1.0, -1.0, 1.0, 1.0)),),
        page_width=float("inf"), page_height=PAGE_SPAN, viewport=None,
    )
    assert [segment["id"] for segment in unchanged] == [segment["id"] for segment in ring]


def test_a_zero_width_hairline_ring_stays_in_the_wall_graph():
    ring = _ring()
    for segment in ring:
        segment["width"] = 0.0
    result = _classify(ring)
    assert result["quarantined_primitive_ids"] == []


def test_a_self_crossing_cycle_is_not_quarantined():
    count = 8
    radius = 5.0
    points = [
        (radius * math.cos(2.0 * math.pi * index / count),
         radius * math.sin(2.0 * math.pi * index / count))
        for index in range(count)
    ]
    segments = []
    for index, start in enumerate(points):
        end = points[(index + 3) % count]
        segments.append(_line(f"s{index}", start[0], start[1], end[0], end[1], path=100 + index))
    result = _classify(segments)
    assert result["quarantined_primitive_ids"] == []


def test_axis_aligned_edges_that_do_not_close_are_not_a_frame():
    ring = _ring()
    incomplete = [
        _rect_edge("p0", -30.0, -30.0, 30.0, -30.0, path=70),
        _rect_edge("p1", -30.0, 30.0, 30.0, 30.0, path=70),
        _rect_edge("p2", -30.0, -30.0, -30.0, 0.0, path=70),
        _rect_edge("p3", 30.0, -30.0, 30.0, 30.0, path=70),
    ]
    result = classify_exact_annotation_cycles(
        ring + incomplete, [_word()], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    quarantined = set(result["quarantined_primitive_ids"])
    assert {f"mark{i}" for i in range(16)} <= quarantined
    assert not quarantined.intersection({"p0", "p1", "p2", "p3"})


def test_non_mapping_inputs_do_not_raise():
    result = classify_exact_annotation_cycles(
        [None, "stroke", {"kind": "line"}, *_ring()],
        ["MARK", None, _word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    assert set(result["quarantined_primitive_ids"]) == {f"mark{i}" for i in range(16)}
    assert result["diagnostic_only"]
    assert not result["structural_wall_role_authenticated"]
    assert not result["quantity_or_metric_area_published"]


def _transform_segment(segment, transform):
    copy = dict(segment)
    copy["x1"], copy["y1"] = transform(segment["x1"], segment["y1"])
    copy["x2"], copy["y2"] = transform(segment["x2"], segment["y2"])
    return copy


def _word_through(transform, word=None):
    source = _word() if word is None else word
    corners = (
        (source["x0"], source["y0"]), (source["x1"], source["y0"]),
        (source["x1"], source["y1"]), (source["x0"], source["y1"]),
    )
    moved = [transform(x, y) for x, y in corners]
    xs = [point[0] for point in moved]
    ys = [point[1] for point in moved]
    return _word(text=source["text"], x0=min(xs), y0=min(ys), x1=max(xs), y1=max(ys))


def _frame_result(frame, transform=lambda x, y: (x, y)):
    ring = [_transform_segment(segment, transform) for segment in _ring()]
    moved = [_transform_segment(segment, transform) for segment in frame]
    result = classify_exact_annotation_cycles(
        ring + moved, [_word_through(transform)], page_span=PAGE_SPAN, viewport_bbox=VIEW,
    )
    return set(result["quarantined_primitive_ids"]), set(result["frame_primitive_ids"])


def test_duplicate_opposite_sides_are_not_a_rectangular_frame():
    false_frame = [
        _rect_edge("b0", -20.0, -20.0, 20.0, -20.0, path=80),
        _rect_edge("b1", -20.0, -20.0, 20.0, -20.0, path=80),
        _rect_edge("t0", -20.0, 20.0, 20.0, 20.0, path=80),
        _rect_edge("t1", 20.0, 20.0, -20.0, 20.0, path=80),
    ]
    quarantined, frames = _frame_result(false_frame)
    assert {f"mark{i}" for i in range(16)} <= quarantined
    assert not quarantined.intersection({"b0", "b1", "t0", "t1"})
    assert frames == set()


def test_disconnected_axis_aligned_edges_are_not_a_frame():
    pieces = [
        _rect_edge("d0", 0.0, 0.0, 10.0, 0.0, path=81),
        _rect_edge("d1", 40.0, 0.0, 50.0, 0.0, path=81),
        _rect_edge("d2", 0.0, 10.0, 0.0, 20.0, path=81),
        _rect_edge("d3", 40.0, 10.0, 40.0, 20.0, path=81),
    ]
    quarantined, frames = _frame_result(pieces)
    assert not quarantined.intersection({"d0", "d1", "d2", "d3"})
    assert frames == set()


def test_a_rectangle_missing_one_side_is_not_a_frame():
    partial = _frame(82, -20.0, -20.0, 20.0, 20.0, "part")[:3]
    quarantined, frames = _frame_result(partial)
    assert not quarantined.intersection({"part0", "part1", "part2"})
    assert frames == set()


def test_reversed_rectangle_sides_are_withheld():
    frame = _frame(83, -20.0, -20.0, 20.0, 20.0, "rev")
    for edge in frame:
        edge["x1"], edge["y1"], edge["x2"], edge["y2"] = edge["x2"], edge["y2"], edge["x1"], edge["y1"]
    quarantined, frames = _frame_result(frame)
    assert {"rev0", "rev1", "rev2", "rev3"} <= quarantined
    assert frames == {"rev0", "rev1", "rev2", "rev3"}


def test_a_rectangle_sharing_its_path_with_other_content_is_not_a_frame():
    shared_path = _frame(87, -20.0, -20.0, 20.0, 20.0, "mix") + [
        {**_line("mixline", 20.0, 20.0, 30.0, 20.0, path=87), "stroke": None, "width": 0.0, "fill": (1.0, 1.0, 1.0)},
    ]
    quarantined, frames = _frame_result(shared_path)
    assert {f"mark{i}" for i in range(16)} <= quarantined
    assert frames == set()
    assert not quarantined.intersection({"mix0", "mix1", "mix2", "mix3", "mixline"})


def test_rectangle_sides_from_two_path_items_are_not_a_frame():
    split = _frame(88, -20.0, -20.0, 20.0, 20.0, "item")
    split[2] = {**split[2], "item_index": 1}
    split[3] = {**split[3], "item_index": 1}
    quarantined, frames = _frame_result(split)
    assert frames == set()
    assert not quarantined.intersection({"item0", "item1", "item2", "item3"})


def test_rectangle_input_order_does_not_change_the_frame():
    frame = _frame(84, -20.0, -20.0, 20.0, 20.0, "ord")
    forward, forward_frames = _frame_result(frame)
    backward, backward_frames = _frame_result(list(reversed(frame)))
    assert forward == backward
    assert forward_frames == backward_frames == {"ord0", "ord1", "ord2", "ord3"}


def test_translated_rectangle_frame_is_withheld():
    frame = _frame(85, -20.0, -20.0, 20.0, 20.0, "mov")
    quarantined, frames = _frame_result(frame, lambda x, y: (x + 30.0, y - 15.0))
    assert {"mov0", "mov1", "mov2", "mov3"} <= quarantined
    assert frames == {"mov0", "mov1", "mov2", "mov3"}


def test_quarter_turn_rectangle_frames_are_withheld():
    frame = _frame(86, -20.0, -12.0, 20.0, 12.0, "rot")
    quarter, quarter_frames = _frame_result(frame, lambda x, y: (-y, x))
    three, three_frames = _frame_result(frame, lambda x, y: (y, -x))
    assert quarter_frames == three_frames == {"rot0", "rot1", "rot2", "rot3"}
    assert quarter_frames <= quarter
    assert three_frames <= three


_CONTACT = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (2.0, 0.0), (0.0, 4.0))


def _mapped_contact(transform):
    return [transform(x, y) for x, y in _CONTACT]


def test_interior_edge_contact_is_not_a_simple_boundary():
    assert _cycle_edges_cross(_CONTACT)
    assert _cycle_edges_cross(list(reversed(_CONTACT)))
    assert _cycle_edges_cross(_mapped_contact(lambda x, y: (x + 9.0, y - 3.0)))
    assert _cycle_edges_cross(_mapped_contact(lambda x, y: (-y, x)))
    assert _cycle_edges_cross(_mapped_contact(lambda x, y: (y, -x)))
    assert _cycle_edges_cross(_mapped_contact(lambda x, y: (x * 2.0, y * 2.0)))
    rotated_start = _CONTACT[2:] + _CONTACT[:2]
    assert _cycle_edges_cross(rotated_start)
    assert _cycle_edges_cross(_CONTACT) is _cycle_edges_cross(tuple(_CONTACT))


def test_a_near_contact_and_a_clean_square_stay_simple():
    near = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (2.0, 1e-4), (0.0, 4.0))
    square = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0))
    assert not _cycle_edges_cross(near)
    assert not _cycle_edges_cross(square)
    assert not _cycle_edges_cross(list(reversed(square)))


def test_a_corner_folded_back_along_its_neighbour_is_not_a_simple_boundary():
    folded = ((0.0, 0.0), (1.0, 0.0), (2.0, 0.0))
    for vertices in (folded, folded[1:] + folded[:1], folded[2:] + folded[:2]):
        assert _cycle_edges_cross(vertices)
        assert _cycle_edges_cross(list(reversed(vertices)))
    turned = tuple((-y * 3.0 + 5.0, x * 3.0 - 7.0) for x, y in folded)
    assert _cycle_edges_cross(turned)


def test_collinear_nonadjacent_overlap_is_not_a_simple_boundary():
    overlap = (
        (0.0, 0.0), (4.0, 0.0), (4.0, 1.0), (3.0, 0.0), (1.0, 0.0), (1.0, 2.0), (0.0, 2.0),
    )
    assert _cycle_edges_cross(overlap)


def test_interior_contact_does_not_quarantine_an_otherwise_closed_mark():
    count = 12
    radius = 6.0
    points = [
        (radius * math.cos(2.0 * math.pi * index / count),
         radius * math.sin(2.0 * math.pi * index / count))
        for index in range(count)
    ]
    start, end = points[0], points[1]
    touched = list(points)
    touched[6] = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)

    def polygon(vertices, prefix):
        segments = []
        for index, (left, right) in enumerate(zip(vertices, vertices[1:] + vertices[:1])):
            segments.append(_line(f"{prefix}{index}", left[0], left[1], right[0], right[1], path=400 + index))
        return segments

    contact = _classify(polygon(touched, "hit"))
    assert contact["quarantined_primitive_ids"] == []
    assert _cycle_edges_cross(touched)


def test_wall_annotation_ancestry_retains_unknown_mixed_and_empty_lineage():
    assert wall_annotation_ancestry((), ("mark0",)) == "no_source_lineage"
    assert wall_annotation_ancestry(("mark0", "mark1"), ("mark0", "mark1")) == "annotation_only"
    assert wall_annotation_ancestry(("mark0", "w0"), ("mark0",)) == "mixed_annotation_ancestry"
    assert wall_annotation_ancestry(("w0", "w1"), ("mark0",)) == "no_annotation_ancestry"


def test_post_identity_flags_the_mark_and_keeps_room_wall_ids():
    ring = _ring()
    room = [
        _line("w0", 40, 40, 120, 40, path=1),
        _line("w1", 120, 40, 120, 80, path=2),
        _line("w2", 120, 80, 40, 80, path=3),
        _line("w3", 40, 80, 40, 40, path=4),
    ]
    before = deepcopy(ring + room)
    report = shadow_annotation_cycle_post_identity_report(
        ring + room, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    room_only = shadow_annotation_cycle_post_identity_report(
        room, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    assert report["diagnostic_only"]
    assert report["quantity_or_metric_area_published"] is False
    assert report["pre_snap_withhold_changes_ordinal_w2_edge_ids"]
    surviving = set(report["surviving_wall_ids"])
    assert surviving
    assert surviving == set(room_only["surviving_wall_ids"])
    assert set(report["annotation_only_wall_ids"]).isdisjoint(surviving)
    replay = shadow_annotation_cycle_post_identity_report(
        ring + room, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    assert [row["face_a_segment_ids"] for row in report["minted_walls"]] == [
        row["face_a_segment_ids"] for row in replay["minted_walls"]
    ]
    assert before == ring + room


def test_post_identity_is_order_and_replay_invariant():
    ring = _ring()
    room = [
        _line("w0", 40, 40, 120, 40, path=1),
        _line("w1", 120, 40, 120, 80, path=2),
        _line("w2", 120, 80, 40, 80, path=3),
        _line("w3", 40, 80, 40, 40, path=4),
    ]
    first = shadow_annotation_cycle_post_identity_report(
        ring + room, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    reversed_input = list(reversed(ring + room))
    second = shadow_annotation_cycle_post_identity_report(
        reversed_input, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    replay = shadow_annotation_cycle_post_identity_report(
        ring + room, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    assert first["surviving_wall_ids"] == second["surviving_wall_ids"] == replay["surviving_wall_ids"]
    assert first["annotation_only_wall_ids"] == second["annotation_only_wall_ids"]
    assert first["surviving_wall_ids"] == replay["surviving_wall_ids"]


def test_post_identity_does_not_flag_a_room_when_the_mark_is_absent():
    room = [
        _line("w0", 40, 40, 120, 40, path=1),
        _line("w1", 120, 40, 120, 80, path=2),
        _line("w2", 120, 80, 40, 80, path=3),
        _line("w3", 40, 80, 40, 40, path=4),
    ]
    report = shadow_annotation_cycle_post_identity_report(
        room, [_word()],
        page_span=PAGE_SPAN, viewport_bbox=VIEW,
        document_id="synthetic", page_id="1", viewport_id="view-post",
    )
    assert report["annotation_only_wall_ids"] == []
    assert report["mixed_annotation_wall_ids"] == []
    assert report["surviving_wall_ids"]
    assert report["pre_snap_withhold_changes_ordinal_w2_edge_ids"] is False
