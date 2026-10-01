"""A wrapped note's tail line is not a standalone drawing-view title.

Synthetic drawings only.  The rule uses positive source ownership: the fragment
is a non-first line of a run of contiguous, aligned, comparably typeset lines
inside one native PDF text block, and the existing page-title authority rejects
the merged run as a title.  No word list, page, project or coordinate input.
"""
from __future__ import annotations

import fitz
import pytest

import pb_viewport_segmentation as vs
from pb_drawing_evidence_binding import DrawingViewType
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    extract_view_title_anchors,
    segment_page_viewports,
)

FLOOR = DrawingViewType.FLOOR_PLAN.value
DERIVED = ViewportSegmentationStatus.DERIVED.value
UNSUPPORTED = ViewportSegmentationStatus.UNSUPPORTED.value

NOTE = ["PROVIDE REINFORCING TO", "WALLS IN ENSUITE -", "REFER TO REINFORCING", "DETAIL SHEET"]


def _reopen(doc: fitz.Document) -> fitz.Document:
    data = doc.tobytes()
    doc.close()
    return fitz.open(stream=data, filetype="pdf")


def _note(page: fitz.Page, lines, *, x: float, y: float, size: float = 8.0, scale: float = 1.0) -> None:
    page.insert_text((x * scale, y * scale), "\n".join(lines), fontsize=size * scale, lineheight=1.15)


def _sheet(
    *,
    note_lines=NOTE,
    note_at=(900.0, 150.0),
    caption=True,
    dx: float = 0.0,
    dy: float = 0.0,
    scale: float = 1.0,
    unrelated: bool = False,
    rotation: int = 0,
) -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=(1190 + dx) * scale, height=(842 + dy) * scale)
    if caption:
        page.insert_text(((70 + dx) * scale, (550 + dy) * scale), "FLOOR PLAN", fontsize=16 * scale, fontname="hebo")
    if note_lines:
        _note(page, note_lines, x=note_at[0] + dx, y=note_at[1] + dy, scale=scale)
    if unrelated:
        page.insert_text((300 * scale, 300 * scale), "3600", fontsize=8 * scale)
        page.draw_line((100 * scale, 700 * scale), (600 * scale, 700 * scale))
    if rotation:
        page.set_rotation(rotation)
    return _reopen(doc)


def _texts(doc: fitz.Document) -> list[str]:
    return sorted(a.text for a in extract_view_title_anchors(doc[0]))


def _block_lines(doc: fitz.Document) -> list[int]:
    return [len(b.get("lines", [])) for b in doc[0].get_text("dict")["blocks"] if b.get("type") == 0]


def test_fixture_note_is_one_native_block() -> None:
    doc = _sheet()
    assert max(_block_lines(doc)) == len(NOTE)
    doc.close()


def test_wrapped_note_tail_is_not_an_anchor_and_caption_survives() -> None:
    doc = _sheet()
    assert vs._wrapped_note_tail_lines(doc[0])
    assert _texts(doc) == ["FLOOR PLAN"]
    doc.close()


def test_sole_caption_is_unsupported_not_a_false_half() -> None:
    doc = _sheet()
    viewports = segment_page_viewports(doc[0], page_number=3)
    assert [(v.label, v.status, v.bounding_box) for v in viewports] == [("FLOOR PLAN", UNSUPPORTED, None)]
    doc.close()


def test_without_the_rule_the_tail_would_cut_the_page(monkeypatch) -> None:
    monkeypatch.setattr(vs, "_wrapped_note_tail_lines", lambda page: [])
    doc = _sheet()
    assert _texts(doc) == ["DETAIL SHEET", "FLOOR PLAN"]
    viewports = segment_page_viewports(doc[0], page_number=3)
    assert sorted(v.status for v in viewports) == [DERIVED, DERIVED]
    doc.close()


def test_stacked_two_line_title_in_one_block_is_kept() -> None:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((100, 300), "PROPOSED\nGROUND FLOOR PLAN", fontsize=14, lineheight=1.15)
    doc = _reopen(doc)
    assert max(_block_lines(doc)) == 2
    assert vs._wrapped_note_tail_lines(doc[0]) == []
    assert _texts(doc) == ["GROUND FLOOR PLAN"]
    doc.close()


def test_tail_of_a_different_type_size_is_kept() -> None:
    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)
    page.insert_text((900, 150), "\n".join(NOTE[:3]), fontsize=8, lineheight=1.15)
    page.insert_text((900, 175), "DETAIL SHEET", fontsize=14)
    doc = _reopen(doc)
    assert "DETAIL SHEET" in _texts(doc)
    doc.close()


def test_independently_dominant_bold_tail_is_kept() -> None:
    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)
    page.insert_text((900, 150), "\n".join(NOTE[:3]), fontsize=8, lineheight=1.15)
    page.insert_text((900, 177), "DETAIL SHEET", fontsize=8, fontname="hebo")
    doc = _reopen(doc)
    assert "DETAIL SHEET" in _texts(doc)
    doc.close()


def test_title_shaped_line_after_a_gap_is_kept() -> None:
    doc = fitz.open()
    page = doc.new_page(width=1190, height=842)
    page.insert_text((900, 150), "\n".join(NOTE[:3]), fontsize=8, lineheight=1.15)
    page.insert_text((900, 230), "DETAIL SHEET", fontsize=8)
    doc = _reopen(doc)
    assert "DETAIL SHEET" in _texts(doc)
    doc.close()


def test_single_line_title_shaped_block_is_never_a_tail() -> None:
    doc = _sheet(note_lines=None)
    assert vs._wrapped_note_tail_lines(doc[0]) == []
    assert _texts(doc) == ["FLOOR PLAN"]
    doc.close()


def test_short_two_line_run_that_still_reads_as_a_heading_is_kept() -> None:
    doc = _sheet(note_lines=["NORTH", "ELEVATION"], note_at=(700.0, 200.0))
    assert max(_block_lines(doc)) == 2
    assert vs._wrapped_note_tail_lines(doc[0]) == []  # merged text is heading-shaped
    doc.close()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"dx": 120.0, "dy": 45.0},
        {"scale": 1.6},
        {"scale": 0.8},
        {"unrelated": True},
        {"dx": 30.0, "dy": 10.0, "scale": 1.2, "unrelated": True},
        {"rotation": 180},
    ],
)
def test_outcome_is_invariant_to_translation_scale_unrelated_content_and_rotation(kwargs) -> None:
    doc = _sheet(**kwargs)
    assert _texts(doc) == ["FLOOR PLAN"]
    doc.close()


def test_replay_is_deterministic_and_input_is_not_mutated() -> None:
    doc = _sheet()
    page = doc[0]
    before = page.get_text("dict")
    first = [(v.view_id, v.status, v.label) for v in segment_page_viewports(page, page_number=3)]
    second = [(v.view_id, v.status, v.label) for v in segment_page_viewports(page, page_number=3)]
    assert first == second
    assert page.get_text("dict") == before
    doc.close()


def test_non_text_or_broken_page_falls_back_to_no_suppression() -> None:
    class Broken:
        def get_text(self, *args, **kwargs):
            raise RuntimeError("no text layer")

    assert vs._wrapped_note_tail_lines(Broken()) == []
