"""Synthetic source-word gate tests for panel-lift doors (no job heuristic)."""
from __future__ import annotations

from pb_layered_wall_doorway_room_ring_shadow import (
    KIND_PANEL_LIFT, build_layered_wall_doorway_room_rings,
)
from tests.test_layered_wall_doorway_room_ring_shadow_v1 import room

SHA = "ab" * 32


def _wall_strips_without_swing():
    # Real gap in original wall, without a swing leaf. It must not be
    # silently spanned just because two ends are close.
    return [row for row in room() if row.get("fill") is not None]


def _word(text, y, ref):
    return {
        "text": text, "bbox_pdf_pts": (102.0, y, 108.0, y + 4.0),
        "source_ref": ref,
    }


def _panel_label():
    # Text is directly alongside the native right wall gap y=40..64.
    return [_word("Door", 41, "word:door"),
            _word("Lift", 46, "word:lift"),
            _word("Panel", 51, "word:panel"),
            _word("4,800", 58, "word:figure")]


def _evaluate(*, enabled=True, words=None):
    return build_layered_wall_doorway_room_rings(
        _wall_strips_without_swing(), source_sha256=SHA, page_index=0,
        panel_lift_label_closure=enabled,
        source_words=_panel_label() if words is None else words,
    )


def test_panel_lift_words_are_temporary_boundary_not_wall():
    result = _evaluate()
    panel = [c for c in result.closures if c.kind == KIND_PANEL_LIFT]
    assert len(panel) == 1
    assert panel[0].native_path_indices == ()
    assert len(panel[0].native_word_refs) == 4
    assert len(panel[0].wall_path_indices) >= 1
    assert len([r for r in result.rings if r.status.value == "candidate"]) == 1
    assert any(panel[0].closure_id in r.bounding_closure_ids for r in result.rings)


def test_panel_lift_requires_explicit_opt_in():
    result = _evaluate(enabled=False)
    assert not result.closures
    assert not result.rings or all(r.status.value == "abstained" for r in result.rings)


def test_panel_lift_requires_all_three_words_and_figured_size():
    for remove in ("Door", "Panel", "Lift", "4,800"):
        rows = [w for w in _panel_label() if w["text"] != remove]
        result = _evaluate(words=rows)
        assert not result.closures, remove


def test_panel_lift_requires_source_word_location_beside_an_actual_gap():
    rows = [{**word, "bbox_pdf_pts": (200.0, 201.0 + i*5, 206.0, 205.0 + i*5)}
            for i, word in enumerate(_panel_label())]
    assert not _evaluate(words=rows).closures


def test_word_repetition_does_not_authorize_ambiguous_panel_lift():
    words = _panel_label() + [_word("Panel", 53, "word:extra")]
    assert not _evaluate(words=words).closures
