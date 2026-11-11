"""Outside wall-end hashes own the unique figured length between them."""
from __future__ import annotations

from decimal import Decimal

import fitz

from planreader_next.engine import NativeWord, _figured_mm, load_native_page
from planreader_next.hash_chain import (
    _unique_ratio_cover,
    bind_polygon_hash_axes,
    bind_room_hash_axes,
    bind_wall_hash_length,
)


def _page(tmp_path, drawer):
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    drawer(page)
    path = tmp_path / "hash-chain.pdf"
    path.write_bytes(document.tobytes())
    document.close()
    return load_native_page(path, 0)


def _room_with_hashes(page, *, extra_south_word=False, mid_hash=False):
    page.draw_rect(fitz.Rect(100, 80, 200, 160), color=(0, 0, 0), width=0.4)
    page.draw_line(fitz.Point(100, 160), fitz.Point(100, 165.5))
    page.draw_line(fitz.Point(200, 160), fitz.Point(200, 165.5))
    page.draw_line(fitz.Point(90, 165.5), fitz.Point(210, 165.5))
    if mid_hash:
        page.draw_line(fitz.Point(150, 160), fitz.Point(150, 165.5))
        page.insert_text((112, 176), "1800", fontsize=8)
        page.insert_text((162, 176), "1800", fontsize=8)
    else:
        page.insert_text((142, 176), "3600", fontsize=8)
        if extra_south_word:
            page.insert_text((168, 176), "1800", fontsize=8)
    page.draw_line(fitz.Point(200, 80), fitz.Point(206, 80))
    page.draw_line(fitz.Point(200, 160), fitz.Point(206, 160))
    page.draw_line(fitz.Point(206, 70), fitz.Point(206, 170))
    page.insert_text((210, 116), "2400", fontsize=8)


def test_wall_ends_take_the_unique_outside_hash_measurement(tmp_path):
    native = _page(tmp_path, _room_with_hashes)
    bound = bind_wall_hash_length(
        native, horizontal_wall=True, face_perp=160.0, lo=100.0, hi=200.0, outward=1.0,
    )
    assert bound is not None
    assert bound.length_mm == 3600
    width, height = bind_room_hash_axes(native, (100, 80, 200, 160))
    assert width is not None and height is not None
    assert width.length_mm == 3600
    assert height.length_mm == 2400


def test_two_figures_between_the_same_hashes_abstain(tmp_path):
    native = _page(tmp_path, lambda page: _room_with_hashes(page, extra_south_word=True))
    bound = bind_wall_hash_length(
        native, horizontal_wall=True, face_perp=160.0, lo=100.0, hi=200.0, outward=1.0,
    )
    assert bound is None


def test_hash_chain_walks_end_to_end_across_intermediate_hashes(tmp_path):
    native = _page(tmp_path, lambda page: _room_with_hashes(page, mid_hash=True))
    bound = bind_wall_hash_length(
        native, horizontal_wall=True, face_perp=160.0, lo=100.0, hi=200.0, outward=1.0,
    )
    assert bound is not None
    assert bound.length_mm == 3600
    assert len(bound.word_refs) == 2
    assert len(bound.hash_stations) == 3


def test_shared_middle_figures_split_onto_side_and_centre_hashes(tmp_path):
    def drawer(page):
        page.draw_rect(fitz.Rect(100, 80, 185, 160), color=(0, 0, 0), width=0.4)
        for x in (100, 117, 168, 185):
            page.draw_line(fitz.Point(x, 160), fitz.Point(x, 165.5))
        page.draw_line(fitz.Point(90, 165.5), fitz.Point(195, 165.5))
        page.insert_text((128, 176), "1200", fontsize=8)
        page.insert_text((148, 176), "1810", fontsize=8)
        page.draw_line(fitz.Point(185, 80), fitz.Point(191, 80))
        page.draw_line(fitz.Point(185, 160), fitz.Point(191, 160))
        page.draw_line(fitz.Point(191, 70), fitz.Point(191, 170))
        page.insert_text((195, 116), "2400", fontsize=8)

    native = _page(tmp_path, drawer)
    bound = bind_wall_hash_length(
        native, horizontal_wall=True, face_perp=160.0, lo=100.0, hi=185.0, outward=1.0,
    )
    assert bound is not None
    assert bound.length_mm == 3010
    assert len(bound.word_refs) == 2
    assert len(bound.hash_stations) == 4


def test_crowded_middle_figures_abstain_when_hash_spans_do_not_agree(tmp_path):
    def drawer(page):
        page.draw_rect(fitz.Rect(100, 80, 160, 160), color=(0, 0, 0), width=0.4)
        for x in (100, 110, 150, 160):
            page.draw_line(fitz.Point(x, 160), fitz.Point(x, 165.5))
        page.draw_line(fitz.Point(90, 165.5), fitz.Point(170, 165.5))
        page.insert_text((118, 176), "1200", fontsize=8)
        page.insert_text((132, 176), "1810", fontsize=8)

    native = _page(tmp_path, drawer)
    bound = bind_wall_hash_length(
        native, horizontal_wall=True, face_perp=160.0, lo=100.0, hi=160.0, outward=1.0,
    )
    assert bound is None


def test_equal_millimetre_words_on_separated_intervals_abstain():
    intervals = [
        (0.0, 10.0, Decimal("10")),
        (10.0, 30.0, Decimal("20")),
        (30.0, 40.0, Decimal("10")),
    ]
    figures = [
        NativeWord("left", "2000", (12, 10, 15, 14)),
        NativeWord("right", "2000", (22, 10, 25, 14)),
    ]
    assert _unique_ratio_cover(intervals, figures) is None
    assert _unique_ratio_cover(intervals, figures, horizontal_wall=True) is None


def test_unique_1200_1810_leftover_cover_still_binds_by_word_ref():
    intervals = [
        (0.0, 16.9, Decimal("16.9")),
        (16.9, 68.2, Decimal("51.3")),
        (68.2, 85.1, Decimal("16.9")),
    ]
    figures = [
        NativeWord("word:1200", "1,200", (40, 10, 48, 14)),
        NativeWord("word:1810", "1,810", (42, 10, 50, 14)),
    ]
    owned = _unique_ratio_cover(intervals, figures, horizontal_wall=True)
    assert owned is not None
    assert {word.ref for word in owned} == {"word:1200", "word:1810"}
    assert sum((_figured_mm(word) for word in owned), Decimal("0")) == Decimal("3010")


def test_wall_ends_line_up_with_hashes_on_an_outside_dimension_line(tmp_path):
    def drawer(page):
        page.draw_rect(fitz.Rect(100, 80, 200, 160), color=(0, 0, 0), width=0.4)
        page.draw_line(fitz.Point(90, 180), fitz.Point(210, 180))
        page.draw_line(fitz.Point(100, 177), fitz.Point(100, 183))
        page.draw_line(fitz.Point(200, 177), fitz.Point(200, 183))
        page.insert_text((142, 190), "3600", fontsize=8)
        page.draw_line(fitz.Point(220, 70), fitz.Point(220, 170))
        page.draw_line(fitz.Point(217, 80), fitz.Point(223, 80))
        page.draw_line(fitz.Point(217, 160), fitz.Point(223, 160))
        page.insert_text((224, 116), "2400", fontsize=8)

    native = _page(tmp_path, drawer)
    width, height = bind_room_hash_axes(native, (100, 80, 200, 160))
    assert width is not None and width.length_mm == 3600
    assert height is not None and height.length_mm == 2400


def test_far_aligned_hashes_do_not_bind_a_room_face(tmp_path):
    def drawer(page):
        page.draw_rect(fitz.Rect(100, 80, 200, 160), color=(0, 0, 0), width=0.4)
        page.draw_line(fitz.Point(90, 280), fitz.Point(210, 280))
        page.draw_line(fitz.Point(100, 277), fitz.Point(100, 283))
        page.draw_line(fitz.Point(200, 277), fitz.Point(200, 283))
        page.insert_text((142, 290), "3600", fontsize=8)

    native = _page(tmp_path, drawer)
    width, height = bind_room_hash_axes(native, (100, 80, 200, 160))
    assert width is None
    assert height is None


def test_polygon_faces_not_bbox_own_the_hash_chain(tmp_path):
    def drawer(page):
        # Finished face jogs north, so the east internal face is shorter than bbox.
        for a, b in [
            ((100, 160), (200, 160)), ((200, 160), (200, 100)),
            ((200, 100), (150, 100)), ((150, 100), (150, 80)),
            ((150, 80), (100, 80)), ((100, 80), (100, 160)),
        ]:
            page.draw_line(fitz.Point(*a), fitz.Point(*b), color=(0, 0, 0), width=0.4)
        page.draw_line(fitz.Point(100, 160), fitz.Point(100, 165.5))
        page.draw_line(fitz.Point(200, 160), fitz.Point(200, 165.5))
        page.draw_line(fitz.Point(90, 165.5), fitz.Point(210, 165.5))
        page.insert_text((142, 176), "3600", fontsize=8)
        page.draw_line(fitz.Point(200, 100), fitz.Point(206, 100))
        page.draw_line(fitz.Point(200, 160), fitz.Point(206, 160))
        page.draw_line(fitz.Point(206, 90), fitz.Point(206, 170))
        page.insert_text((210, 128), "2400", fontsize=8)

    native = _page(tmp_path, drawer)
    polygon = [(100, 160), (200, 160), (200, 100), (150, 100), (150, 80), (100, 80)]
    width, height = bind_polygon_hash_axes(native, polygon)
    assert width is not None and width.length_mm == 3600
    assert height is not None and height.length_mm == 2400
    bbox_width, bbox_height = bind_room_hash_axes(native, (100, 80, 200, 160))
    assert bbox_width is not None and bbox_width.length_mm == 3600
    assert bbox_height is None


def test_inner_face_is_not_swapped_for_the_outer_face_two_points_away(tmp_path):
    def drawer(page):
        _room_with_hashes(page)
        page.draw_line(fitz.Point(98, 160), fitz.Point(98, 165.5))
        page.draw_line(fitz.Point(202, 160), fitz.Point(202, 165.5))
        page.insert_text((40, 176), "9999", fontsize=8)

    native = _page(tmp_path, drawer)
    bound = bind_wall_hash_length(
        native, horizontal_wall=True, face_perp=160.0, lo=100.0, hi=200.0, outward=1.0,
    )
    assert bound is not None
    assert bound.length_mm == 3600
