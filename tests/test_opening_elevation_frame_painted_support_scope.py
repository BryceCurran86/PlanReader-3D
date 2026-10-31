"""The painted-support negative gate is scoped to the mark whose frame it could not prove.

A frame candidate whose support is not source-painted (for example a frame bounded only by invisible white-fill
edges) must never publish, and an unproved rival must never be dropped to elect another frame of the SAME mark. It
must not, however, erase the independent, fully stroke-supported frames of OTHER marks: a single unproved frame
elsewhere on the sheet is not evidence against them. Synthetic drawings only.
"""
from __future__ import annotations

import fitz

import pb_opening_elevation_frame_area_authority as authority_module
from pb_migration_contracts import EvidenceResolutionStatus as S
from pb_opening_elevation_frame_area_authority import (
    OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE, OpeningElevationFrameAreaProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_opening_elevation_frame_area_authority import _selector


def _draw_elevation(page, dx, mark, *, frame="stroke", dy=0.0):
    """One 150 x 120 pt frame with two figured dimensions (3000 x 2400), shifted by (dx, dy)."""
    rect = fitz.Rect(150.0 + dx, 120.0 + dy, 300.0 + dx, 240.0 + dy)
    if frame == "stroke":
        page.draw_rect(rect, width=1.0)
    else:                                              # the frame exists only as the edges of an invisible white fill
        page.draw_rect(rect, color=None, fill=(1, 1, 1))
    page.insert_text((215.0 + dx, 185.0 + dy), mark, fontsize=9.0)
    page.draw_line((150.0 + dx, 80.0 + dy), (300.0 + dx, 80.0 + dy), width=0.7)
    page.draw_line((150.0 + dx, 70.0 + dy), (150.0 + dx, 125.0 + dy), width=0.7)
    page.draw_line((300.0 + dx, 70.0 + dy), (300.0 + dx, 125.0 + dy), width=0.7)
    page.insert_text((212.0 + dx, 83.0 + dy), "3000", fontsize=8.0)
    page.draw_line((110.0 + dx, 120.0 + dy), (110.0 + dx, 240.0 + dy), width=0.7)
    page.draw_line((100.0 + dx, 120.0 + dy), (155.0 + dx, 120.0 + dy), width=0.7)
    page.draw_line((100.0 + dx, 240.0 + dy), (155.0 + dx, 240.0 + dy), width=0.7)
    page.insert_text((113.0 + dx, 196.0 + dy), "2400", fontsize=8.0, rotate=90)


def _pdf(frames_by_page, *, width=900.0):
    doc = fitz.open()
    try:
        for frames in frames_by_page:
            page = doc.new_page(width=width, height=400.0)
            page.insert_text((30.0, 30.0), "WINDOW ELEVATIONS", fontsize=10.0)
            for dx, mark, kind in frames:
                _draw_elevation(page, dx, mark, frame=kind)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _resolve_all(payload, marks):
    source = SourceVisibilityProducer(producer_method="elevation-scope-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(
        document_id="elevation-scope", source_bytes=payload, source_locator="memory://elevation-scope.pdf")
    authority = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source).authority()
    return {mark: authority.resolve(_selector(published, mark)) for mark in marks}


def _corroborated(result):
    return result.status is S.CORROBORATED and result.record is not None and abs(result.record.area_m2 - 7.2) < 1e-9


def test_a_fully_stroke_supported_frame_survives_an_unproved_frame_of_another_mark_on_the_same_page():
    got = _resolve_all(_pdf([[(0.0, "W1", "stroke"), (400.0, "W2", "white-fill")]]), ("W1", "W2"))
    assert _corroborated(got["W1"]), got["W1"].reason_codes
    assert got["W2"].status is S.ABSTAINED and got["W2"].record is None
    assert got["W2"].reason_codes == (OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE,)


def test_the_result_does_not_depend_on_which_mark_is_drawn_first_or_where():
    for frames in ([(400.0, "W1", "stroke"), (0.0, "W2", "white-fill")],
                   [(0.0, "W2", "white-fill"), (400.0, "W1", "stroke")]):
        got = _resolve_all(_pdf([frames]), ("W1", "W2"))
        assert _corroborated(got["W1"]) and got["W2"].status is S.ABSTAINED


def test_a_proved_frame_on_another_page_survives_an_unproved_frame_of_another_mark():
    got = _resolve_all(_pdf([[(0.0, "W1", "stroke")], [(0.0, "W2", "white-fill")]]), ("W1", "W2"))
    assert _corroborated(got["W1"]) and got["W2"].status is S.ABSTAINED


def test_two_proved_frames_of_different_marks_both_publish():
    got = _resolve_all(_pdf([[(0.0, "W1", "stroke"), (400.0, "W2", "stroke")]]), ("W1", "W2"))
    assert _corroborated(got["W1"]) and _corroborated(got["W2"])


def test_an_unproved_rival_of_the_same_mark_is_never_dropped_to_elect_the_proved_frame():
    for frames in ([[(0.0, "W1", "stroke"), (400.0, "W1", "white-fill")]], [[(0.0, "W1", "stroke")], [(0.0, "W1", "white-fill")]]):
        got = _resolve_all(_pdf(frames), ("W1",))
        assert got["W1"].status is S.ABSTAINED and got["W1"].record is None, got["W1"]


def test_an_unproved_frame_alone_still_abstains_and_a_proved_one_alone_still_publishes():
    assert _resolve_all(_pdf([[(0.0, "W1", "white-fill")]]), ("W1",))["W1"].status is S.ABSTAINED
    assert _corroborated(_resolve_all(_pdf([[(0.0, "W1", "stroke")]]), ("W1",))["W1"])


def test_a_failure_to_prove_painted_support_for_the_page_still_invalidates_the_whole_revision(monkeypatch):
    def broken(page, page_id):
        raise RuntimeError("paint proof unavailable")

    monkeypatch.setattr(authority_module, "_source_painted_geometry_ids", broken)
    got = _resolve_all(_pdf([[(0.0, "W1", "stroke"), (400.0, "W2", "stroke")]]), ("W1", "W2"))
    assert all(r.status is S.ABSTAINED and r.record is None for r in got.values())


def test_replay_is_identical_and_order_independent():
    payload = _pdf([[(0.0, "W1", "stroke"), (400.0, "W2", "white-fill")]])
    first = _resolve_all(payload, ("W1", "W2"))
    again = _resolve_all(payload, ("W2", "W1"))
    assert first == again
