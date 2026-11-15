"""Figure-to-painted-ink regression: no fixed PDF location or guessed area.

Source-neutral synthetic diagrams only. These assert uniqueness and failure
on forged/ambiguous word, tick, and shaft source evidence.
"""
from __future__ import annotations

from pb_source_cross_view_floor_correspondence_shadow import (
    _authenticate_p11_pwd_dimension_witness_box,
)


def _seg(x0, y0, x1, y1):
    return {"x1": float(x0), "y1": float(y0), "x2": float(x1), "y2": float(y1)}


def _diagram(offset_x=0.0, offset_y=0.0):
    # 110/2200 = 178.5/3570 = .05 pt/mm, but its page position
    # is arbitrary, not a copied original document crop.
    strokes = [
        _seg(80, 320, 80, 498.5),        # vertical 3570 figure shaft
        _seg(74, 320, 86, 320),          # independent upper witness
        _seg(74, 498.5, 86, 498.5),      # independent lower witness
        _seg(80, 313, 80, 320),          # upper ink tick
        _seg(80, 498.5, 80, 505.5),      # lower ink tick
        _seg(210, 610, 320, 610),        # horizontal 2200 figure shaft
        _seg(210, 604, 210, 616),        # left witness
        _seg(320, 604, 320, 616),        # right witness
        _seg(203, 610, 210, 610),        # left ink tick
        _seg(320, 610, 327, 610),        # right ink tick
    ]
    words = [
        (62.0, 400.0, 76.0, 420.0, "3570"),
        (253.0, 612.0, 277.0, 626.0, "2200"),
        (244.0, 407.0, 266.0, 425.0, "PWD"),
        (265.0, 605.0, 284.0, 620.0, "PWD"),  # other sheet note, not this room
    ]
    return (
        tuple({
            "x1": s["x1"] + offset_x, "x2": s["x2"] + offset_x,
            "y1": s["y1"] + offset_y, "y2": s["y2"] + offset_y,
        } for s in strokes),
        tuple((x0 + offset_x, y0 + offset_y, x1 + offset_x,
               y1 + offset_y, word) for x0, y0, x1, y1, word in words),
    )


def test_painted_orthogonal_figure_box_translates_without_fixed_coordinates():
    segments, words = _diagram()
    box = _authenticate_p11_pwd_dimension_witness_box(segments, words)
    assert box == (210.0, 320.0, 320.0, 498.5)
    dx, dy = (10_000.0, 30_000.0)
    shifted_segments, shifted_words = _diagram(dx, dy)
    shifted = _authenticate_p11_pwd_dimension_witness_box(
        shifted_segments, shifted_words,
    )
    assert shifted == (box[0] + dx, box[1] + dy,
                       box[2] + dx, box[3] + dy)


def test_two_room_labels_in_one_source_box_are_not_automatically_deduplicated():
    segments, words = _diagram()
    extra_pwd = (246.0, 425.0, 267.0, 444.0, "PWD")
    assert _authenticate_p11_pwd_dimension_witness_box(
        segments, (*words, extra_pwd),
    ) is None


def test_competing_figured_shaft_and_missing_source_word_both_abstain():
    segments, words = _diagram()
    extra = (
        _seg(90, 320, 90, 498.5),
        _seg(84, 320, 96, 320),
        _seg(84, 498.5, 96, 498.5),
        _seg(90, 313, 90, 320),
        _seg(90, 498.5, 90, 505.5),
    )
    assert _authenticate_p11_pwd_dimension_witness_box(
        (*segments, *extra), words,
    ) is None
    assert _authenticate_p11_pwd_dimension_witness_box(
        segments, tuple(w for w in words if w[4] != "2200"),
    ) is None


def test_private_original_dimension_witness_survives_source_translation():
    """SHA-pinned original witness relationships, not original page coordinates."""
    import hashlib
    import os
    from pathlib import Path

    import fitz
    import pytest

    import pb_maryborough_customer_authority as mary
    from pb_source_cross_view_floor_correspondence_shadow import (
        _extract_segments_from_drawings,
    )

    original = Path(os.environ.get(
        "PLANREADER_ORIGINAL_MARYBOROUGH",
        "documents/sources/Arch_Combined_Maryborough_Service_Station.pdf",
    ))
    if not original.is_file():
        pytest.skip("private original source unavailable")
    payload = original.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == mary.MARYBOROUGH_SOURCE_SHA256
    with fitz.open(stream=payload, filetype="pdf") as document:
        page = document[10]
        segments = _extract_segments_from_drawings(page.get_drawings())
        words = tuple(page.get_text("words"))
    box = _authenticate_p11_pwd_dimension_witness_box(segments, words)
    assert box is not None
    dx, dy = 12_000.0, 21_000.0
    moved_segments = tuple(
        {**s, "x1": s["x1"] + dx, "x2": s["x2"] + dx,
         "y1": s["y1"] + dy, "y2": s["y2"] + dy}
        for s in segments
    )
    moved_words = tuple(
        (w[0] + dx, w[1] + dy, w[2] + dx, w[3] + dy, *w[4:])
        for w in words
    )
    shifted_box = _authenticate_p11_pwd_dimension_witness_box(
        moved_segments, moved_words,
    )
    assert shifted_box == tuple(
        round(v + (dx if i % 2 == 0 else dy), 2)
        for i, v in enumerate(box)
    )
    owning_pwd = [
        w for w in words
        if str(w[4]).strip().upper() == "PWD"
        and box[0] < (w[0] + w[2]) / 2 < box[2]
        and box[1] < (w[1] + w[3]) / 2 < box[3]
    ]
    assert len(owning_pwd) == 1
    assert _authenticate_p11_pwd_dimension_witness_box(
        segments, (*words, owning_pwd[0]),
    ) is None
