"""3Laurel original: all fourteen internal door witnesses close topology only.

Frozen 120-item benchmark is not changed. No door quantity or finished area
may be issued by these candidate room polygons.
"""
import hashlib

import fitz

from pb_next_wall_ring_preview import (
    KIND_CAVITY_SLIDER, KIND_SWING,
    build_layered_wall_doorway_room_rings,
)
from pb_source_native_cavity_slider_jamb_shadow import match_source_native_cavity_sliders
from pb_source_internal_swing_room_barrier import detect_source_internal_swing_room_barriers
from tests.original_source_3laurel import ORIGINAL_SHA256, require_original_3laurel


def test_sha_original_internal_door_thresholds_are_14_distinct_source_owned():
    p = require_original_3laurel()
    b = p.read_bytes()
    assert hashlib.sha256(b).hexdigest() == ORIGINAL_SHA256
    with fitz.open(stream=b, filetype="pdf") as doc:
        rows, words = tuple(doc[2].get_drawings()), tuple(doc[2].get_text("words"))
    assert len(rows) == 11030
    hinges = detect_source_internal_swing_room_barriers(rows, words, page_index=2)
    sliders = match_source_native_cavity_sliders(rows, words, page_index=2)
    assert len(hinges) == 8
    assert len(sliders) == 6
    assert len({r.swing_arc_path_id for r in hinges}) == 8
    assert len({r.cs_word_index for r in sliders}) == 6
    assert all(r.first_host_path_id != r.second_host_path_id for r in hinges)
    assert all(r.host_path_ids[0] != r.host_path_ids[1] for r in sliders)

    page_index = 2
    source_words = tuple(
        {"text": str(row[4]), "bbox_pdf_pts": tuple(float(v) for v in row[:4]),
         "source_ref": f"source-word:p{page_index}:w{i}"}
        for i, row in enumerate(words)
    )
    candidate = build_layered_wall_doorway_room_rings(
        rows, source_sha256=ORIGINAL_SHA256, page_index=2,
        sliding_leaf_frame_closure=True,
        panel_lift_label_closure=True,
        source_words=source_words,
        stroke_pair_wall_faces=True,
        source_native_cs_jamb_closure=True,
        source_native_internal_swing_closure=True,
    )
    source_cs = [
        c for c in candidate.closures
        if c.kind == KIND_CAVITY_SLIDER
        and len(c.native_path_indices) >= 5
    ]
    source_swings = [
        c for c in candidate.closures
        if c.kind == KIND_SWING and len(c.native_path_indices) >= 5
    ]
    assert len(source_cs) == 6
    assert len(source_swings) == 8
    assert len({c.closure_id for c in source_cs + source_swings}) == 14
    assert len(candidate.rings) >= 10
    assert candidate.unresolved_gap_count >= 0
    assert all(r.takeoff_eligible is False for r in candidate.rings)
    assert all(r.commercial_projection_allowed is False for r in candidate.rings)
    assert all(r.metric_area_issued is False for r in candidate.rings)
    assert all(r.floor_finish_issued is False for r in candidate.rings)


def test_native_slider_topology_flag_cannot_be_enabled_without_explicit_existing_slider_mode():
    from pytest import raises
    with raises(ValueError, match="source_native_cs_jamb_closure"):
        build_layered_wall_doorway_room_rings(
            (), source_sha256="a"*64, page_index=2,
            source_native_cs_jamb_closure=True,
        )
