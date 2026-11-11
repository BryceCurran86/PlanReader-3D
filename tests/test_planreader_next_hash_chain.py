"""Outside wall-end hashes own the unique figured length between them."""
from __future__ import annotations

import fitz

from planreader_next.engine import load_native_page
from planreader_next.hash_chain import bind_room_hash_axes, bind_wall_hash_length


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
