"""Cavity-slider CS closures are topology-only. Paired leaves are not walls."""
from __future__ import annotations

from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_CAVITY_SLIDER,
    build_layered_wall_doorway_room_rings,
)
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import line, strip

SHA = "ab" * 32


def _cavity_room():
    rows = []
    rows += strip(0, 0, 100, 2)
    rows += strip(0, 2, 2, 98)
    rows += strip(0, 98, 100, 100)
    rows += strip(98, 2, 100, 40)
    rows += strip(98, 64, 100, 98)
    rows.append(line((98.3, 40), (98.3, 58)))
    rows.append(line((99.6, 46), (99.6, 64)))
    return rows


def _cs_words():
    return [
        {"text": "870", "bbox_pdf_pts": (101.0, 48.0, 110.0, 52.0), "source_ref": "word:870"},
        {"text": "cs", "bbox_pdf_pts": (111.0, 48.0, 118.0, 52.0), "source_ref": "word:cs"},
    ]


def _evaluate(*, words=None, extra_lines=()):
    drawings = _cavity_room() + list(extra_lines)
    return build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=SHA,
        page_index=0,
        sliding_leaf_frame_closure=True,
        source_words=_cs_words() if words is None else words,
    )


def test_cs_paired_leaves_close_as_temporary_wall_only():
    result = _evaluate()
    cavity = [item for item in result.closures if item.kind == KIND_CAVITY_SLIDER]
    assert len(cavity) == 1
    assert cavity[0].native_word_refs == ("word:cs", "word:870")
    assert len(cavity[0].native_path_indices) == 2
    assert len([ring for ring in result.rings if ring.status.value == "candidate"]) == 1
    assert cavity[0].wall_path_indices


def test_paired_lines_without_cs_are_not_a_wall_or_a_room_closure():
    result = _evaluate(words=())
    assert not [item for item in result.closures if item.kind == KIND_CAVITY_SLIDER]
    assert result.unresolved_gap_count >= 1


def test_cs_without_paired_leaves_does_not_invent_a_closure():
    drawings = []
    drawings += strip(0, 0, 100, 2)
    drawings += strip(0, 2, 2, 98)
    drawings += strip(0, 98, 100, 100)
    drawings += strip(98, 2, 100, 40)
    drawings += strip(98, 64, 100, 98)
    result = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=SHA,
        page_index=0,
        sliding_leaf_frame_closure=True,
        source_words=_cs_words(),
    )
    assert not [item for item in result.closures if item.kind == KIND_CAVITY_SLIDER]


def test_duplicate_cs_marks_do_not_pick_a_gap():
    words = _cs_words() + [
        {"text": "cs", "bbox_pdf_pts": (111.0, 54.0, 118.0, 58.0), "source_ref": "word:cs2"},
    ]
    result = _evaluate(words=words)
    assert not [item for item in result.closures if item.kind == KIND_CAVITY_SLIDER]


def test_cs_inline_pocket_faces_close_the_walkthrough_only():
    drawings = []
    drawings += strip(0, 0, 100, 2)
    drawings += strip(0, 2, 2, 98)
    drawings += strip(0, 98, 100, 100)
    drawings += strip(98, 2, 100, 40)
    drawings += strip(98, 64, 100, 98)
    drawings.append(line((98.3, 64), (98.3, 88)))
    drawings.append(line((99.6, 64), (99.6, 88)))
    result = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=SHA,
        page_index=0,
        sliding_leaf_frame_closure=True,
        source_words=_cs_words(),
    )
    cavity = [item for item in result.closures if item.kind == KIND_CAVITY_SLIDER]
    assert len(cavity) == 1
    assert cavity[0].gap_interval == (40.0, 64.0) or (
        abs(cavity[0].gap_interval[0] - 40.0) < 0.2
        and abs(cavity[0].gap_interval[1] - 64.0) < 0.2
    )
    assert len(cavity[0].native_path_indices) == 2
    assert len([ring for ring in result.rings if ring.status.value == "candidate"]) == 1


def test_cs_face_interruption_without_strip_gap_still_closes():
    drawings = []
    drawings += strip(0, 0, 100, 2)
    drawings += strip(0, 2, 2, 98)
    drawings += strip(0, 98, 100, 100)
    drawings += strip(98, 2, 100, 98)
    drawings.append(line((49.2, 2), (49.2, 40)))
    drawings.append(line((50.8, 2), (50.8, 40)))
    drawings.append(line((49.2, 64), (49.2, 98)))
    drawings.append(line((50.8, 64), (50.8, 98)))
    words = [
        {"text": "720", "bbox_pdf_pts": (52.0, 48.0, 60.0, 52.0), "source_ref": "word:720"},
        {"text": "cs", "bbox_pdf_pts": (61.0, 48.0, 68.0, 52.0), "source_ref": "word:cs"},
    ]
    result = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=SHA,
        page_index=0,
        sliding_leaf_frame_closure=True,
        source_words=words,
    )
    cavity = [item for item in result.closures if item.kind == KIND_CAVITY_SLIDER]
    assert len(cavity) == 1
    assert cavity[0].native_word_refs[0] == "word:cs"
    assert abs(cavity[0].gap_interval[0] - 40.0) < 0.2
    assert abs(cavity[0].gap_interval[1] - 64.0) < 0.2
    assert cavity[0].horizontal is False
