"""Typed white-panel wall evidence (report only). Synthetic PyMuPDF drawings."""
from __future__ import annotations

import copy

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_panel_wall_evidence_shadow import (
    REASON_CONTINUOUS,
    REASON_ISOLATED,
    REASON_OPEN_END,
    REASON_STACKED,
    REASON_TEXT,
    typed_panel_walls,
)

SHA = "a" * 64
# A closed room of four 8.6 pt panel strips, drawn on both long faces.
ROOM = [(41.4, 41.4, 172.6, 50), (41.4, 164, 172.6, 172.6), (41.4, 50, 50, 164), (164, 50, 172.6, 164)]


def faces(rect):
    x0, y0, x1, y1 = rect
    if (x1 - x0) >= (y1 - y0):
        return [((x0, y0), (x1, y0)), ((x0, y1), (x1, y1))]
    return [((x0, y0), (x0, y1)), ((x1, y0), (x1, y1))]


def drawings(rects=ROOM, lines=None, shift=(0.0, 0.0), reverse=False, words=(), dark=()):
    document = fitz.open()
    page = document.new_page(width=700, height=700)
    move = lambda p: (p[0] + shift[0], p[1] + shift[1])
    moved = [(*move(r[:2]), *move(r[2:])) for r in rects]
    for rect in (moved[::-1] if reverse else moved):
        page.draw_rect(fitz.Rect(rect), color=None, fill=(1, 1, 1), width=0)
    for rect in dark:
        page.draw_rect(fitz.Rect(*move(rect[:2]), *move(rect[2:])), color=None, fill=(0.2, 0.2, 0.2), width=0)
    for a, b in (lines if lines is not None else [seg for r in rects for seg in faces(r)]):
        page.draw_line(move(a), move(b), color=(0, 0, 0), width=0.7)
    for point, text in words:
        page.insert_text(move(point), text, fontsize=5)
    found, text_words = page.get_drawings(), page.get_text("words")
    document.close()
    return found, text_words


def run(**kwargs):
    found, words = drawings(**kwargs)
    return typed_panel_walls(found, words, source_sha256=SHA, page_index=0)


@pytest.mark.parametrize("kwargs", [{}, {"shift": (213.5, 91.25)}, {"reverse": True}], ids=["plain", "shifted", "reversed"])
def test_a_room_of_panel_walls_is_continuous_evidence_never_support(kwargs):
    records = run(**kwargs)
    assert len(records) == 4
    assert all(r["status"] is Status.CANDIDATE and r["reason"] == REASON_CONTINUOUS for r in records)
    assert all(r["counts_as_support"] is False and r["wall_authority"] is False for r in records)
    assert all(r["source_sha256"] == SHA and r["viewport_id"] is None for r in records)


def test_an_isolated_box_is_not_a_wall():
    [record] = run(rects=[(300, 300, 340, 310)])
    assert record["status"] is Status.ABSTAINED and record["reason"] == REASON_ISOLATED


def test_a_strip_with_an_open_end_abstains():
    records = {r["rect_pdf_pts"][1]: r for r in run(rects=ROOM[:1] + ROOM[2:3])}  # one L corner: far ends open
    assert {r["reason"] for r in records.values()} == {REASON_OPEN_END}


def test_a_labelled_box_abstains():
    records = run(words=[((100, 47), "SCHEDULE")])
    assert sorted(r["reason"] for r in records).count(REASON_TEXT) == 1


def test_a_box_painted_twice_is_one_isolated_strip():
    [record] = run(rects=[(300, 300, 340, 310)] * 2)
    assert record["reason"] == REASON_ISOLATED and len(record["fill_path_indices"]) == 2


def test_empty_table_rows_are_stacked_cells():
    records = run(rects=[(100, 300 + 8 * i, 160, 308 + 8 * i) for i in range(3)])
    assert len(records) == 3
    assert all(r["status"] is Status.ABSTAINED and r["reason"] == REASON_STACKED for r in records)


def test_a_row_of_empty_cells_never_reaches_wall_paint():
    records = run(rects=[(100 + 40 * i, 500, 140 + 40 * i, 508) for i in range(3)])
    assert [r["reason"] for r in records] == [REASON_ISOLATED] * 3


def test_a_wall_split_in_line_stays_continuous_and_a_gap_opens_it():
    right = ROOM[3]
    split = [*ROOM[:3], (right[0], right[1], right[2], 100), (right[0], 100, right[2], right[3])]
    records = run(rects=split)
    assert len(records) == 5 and all(r["reason"] == REASON_CONTINUOUS for r in records)
    gapped = [*ROOM[:3], (right[0], right[1], right[2], 90), (right[0], 120, right[2], right[3])]
    reasons = {r["rect_pdf_pts"][1]: r["reason"] for r in run(rects=gapped) if r["rect_pdf_pts"][0] == 164}
    assert reasons == {50.0: REASON_OPEN_END, 120.0: REASON_OPEN_END}


def test_a_nearly_repeated_box_does_not_stretch_the_end_tolerance():
    # The 340.5 / 299.5 box reaches the cross strips; the 300-340 box stops 1.2 pt short and is not "continued" by it.
    records = run(rects=[(300, 300, 340, 310), (299.5, 300, 340.5, 310), (341.2, 290, 349.8, 320),
                         (290.2, 290, 298.8, 320)])
    by_start = {r["rect_pdf_pts"][0]: r for r in records}
    assert by_start[299.5]["reason"] == REASON_CONTINUOUS and by_start[300.0]["reason"] == REASON_ISOLATED


@pytest.mark.parametrize("dark", [
    [(296, 290, 300, 320), (340, 290, 344, 320)],  # a dark wall bar across each end
    [(296, 290, 300, 320), (340, 300, 380, 310)],  # a bar across one end, a bar in line at the other
], ids=["crosswise", "in_line"])
def test_dark_wall_bars_close_the_ends(dark):
    [record] = run(rects=[(300, 300, 340, 310)], dark=dark)
    assert record["status"] is Status.CANDIDATE and record["ends_continuous"] == (True, True)


def test_the_source_paths_are_kept():
    found, words = drawings()
    for record in typed_panel_walls(found, words, source_sha256=SHA, page_index=0):
        assert all(found[i]["fill"] == (1.0, 1.0, 1.0) for i in record["fill_path_indices"])
        assert len(record["face_path_indices"]) == 2
        assert all(side and all(found[i]["items"][0][0] == "l" for i in side) for side in record["face_path_indices"])


@pytest.mark.parametrize("rects,lines", [
    (ROOM, [faces(r)[0] for r in ROOM]),  # one face only
    ([(300, 300, 320, 312)], None),  # shorter than three times its thickness
    ([(300, 300, 330, 312)], None),  # two and a half times: still short
    ([(300, 300, 380, 320)], None),  # 20 pt thick
], ids=["one_face", "short", "stubby", "thick"])
def test_look_alikes_give_no_record(rects, lines):
    assert run(rects=rects, lines=lines) == []


def test_inputs_and_digest():
    found, words = drawings()
    before = copy.deepcopy(found)
    first = typed_panel_walls(found, words, source_sha256=SHA, page_index=0)
    assert found == before and first == typed_panel_walls(found, words, source_sha256=SHA, page_index=0)
    flipped = typed_panel_walls(list(reversed(found)), words, source_sha256=SHA, page_index=0)
    assert [r["rect_pdf_pts"] for r in flipped] == [r["rect_pdf_pts"] for r in first]
    with pytest.raises(ValueError):
        typed_panel_walls(found, words, source_sha256="short", page_index=0)
    with pytest.raises(ValueError):
        typed_panel_walls(found, words, source_sha256=SHA, page_index=-1)
