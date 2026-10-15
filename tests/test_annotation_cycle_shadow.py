"""Synthetic proofs for exact annotation-cycle shadow classification.

Colour, width, and text nearness alone must not quarantine a segment.
"""
from __future__ import annotations

import math
from copy import deepcopy

import pytest

from pb_annotation_cycle_shadow import (
    classify_exact_annotation_cycles,
    shadow_annotation_cycle_topology,
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
    from types import SimpleNamespace
    from pb_annotation_cycle_shadow import segments_without_proven_annotation_cycles
    from pb_physical_wall_candidate_authority import _without_proven_annotation_cycles

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
    receipt = SimpleNamespace(raw_text="MARK", geometry=(-1.0, -1.0, 1.0, 1.0))
    withheld = _without_proven_annotation_cycles(
        ring, classification_segments=ring, text_receipts=(receipt,),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN,
        viewport=SimpleNamespace(bounding_box=VIEW),
    )
    assert withheld == ()


def test_leftover_chord_is_removed_when_the_cycle_is_proved_earlier():
    from types import SimpleNamespace
    from pb_physical_wall_candidate_authority import _without_proven_annotation_cycles

    ring = _ring()
    receipt = SimpleNamespace(raw_text="MARK", geometry=(-1.0, -1.0, 1.0, 1.0))
    leftover = _without_proven_annotation_cycles(
        ring[:1], classification_segments=ring, text_receipts=(receipt,),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN,
        viewport=SimpleNamespace(bounding_box=VIEW),
    )
    assert leftover == ()


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


def _receipt(text, geometry):
    from types import SimpleNamespace
    return SimpleNamespace(raw_text=text, geometry=geometry)


def _withhold(segments, receipts):
    from types import SimpleNamespace
    from pb_physical_wall_candidate_authority import _without_proven_annotation_cycles
    return _without_proven_annotation_cycles(
        segments, classification_segments=segments, text_receipts=receipts,
        page_width=PAGE_SPAN, page_height=PAGE_SPAN,
        viewport=SimpleNamespace(bounding_box=VIEW),
    )


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
    from pb_physical_wall_candidate_authority import _without_proven_annotation_cycles
    ring = _ring(cx=100.0, cy=100.0)
    kept = _without_proven_annotation_cycles(
        ring, classification_segments=ring,
        text_receipts=(_receipt("MARK", (99.0, 99.0, 101.0, 101.0)),),
        page_width=PAGE_SPAN, page_height=PAGE_SPAN, viewport=None,
    )
    assert kept == ()


def test_absent_viewport_does_not_own_a_mark_outside_the_page():
    from pb_physical_wall_candidate_authority import _without_proven_annotation_cycles
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
