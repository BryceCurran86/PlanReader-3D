"""Printed figures are inventoried with unique dim-line geometry, never as quantities."""
from __future__ import annotations

from decimal import Decimal

import fitz

from planreader_next.dimension_index import (
    ROLE_UNMATCHED,
    STATUS_AMBIGUOUS,
    STATUS_UNMATCHED,
    STATUS_UNIQUE,
    clear_dimension_index_cache,
    inventory_page_dimensions,
)
from planreader_next.engine import load_native_page


def _page(tmp_path, drawer, name="dim-index.pdf"):
    document = fitz.open()
    page = document.new_page(width=400, height=300)
    drawer(page)
    path = tmp_path / name
    path.write_bytes(document.tobytes())
    document.close()
    return load_native_page(path, 0)


def _room_with_hashes(page):
    page.draw_rect(fitz.Rect(100, 80, 200, 160), color=(0, 0, 0), width=0.4)
    page.draw_line(fitz.Point(100, 160), fitz.Point(100, 165.5))
    page.draw_line(fitz.Point(200, 160), fitz.Point(200, 165.5))
    page.draw_line(fitz.Point(90, 165.5), fitz.Point(210, 165.5))
    page.insert_text((142, 176), "3600", fontsize=8)
    page.draw_line(fitz.Point(200, 80), fitz.Point(206, 80))
    page.draw_line(fitz.Point(200, 160), fitz.Point(206, 160))
    page.draw_line(fitz.Point(206, 70), fitz.Point(206, 170))
    page.insert_text((210, 116), "2400", fontsize=8)


def test_unique_dim_line_hashes_and_extensions_stay_unmatched_role(tmp_path):
    clear_dimension_index_cache()

    def drawer(page):
        _room_with_hashes(page)
        page.draw_line(fitz.Point(100, 150), fitz.Point(100, 165.5))
        page.draw_line(fitz.Point(200, 150), fitz.Point(200, 165.5))

    native = _page(tmp_path, drawer)
    index = inventory_page_dimensions(native)
    assert index.commercial_publishable is False
    assert index.official_score is None
    by_mm = {item.millimetres: item for item in index.figures}
    width = by_mm[Decimal("3600")]
    height = by_mm[Decimal("2400")]
    assert width.geometry_status == STATUS_UNIQUE
    assert height.geometry_status == STATUS_UNIQUE
    assert width.role == ROLE_UNMATCHED
    assert height.role == ROLE_UNMATCHED
    assert width.orientation == "horizontal"
    assert height.orientation == "vertical"
    assert width.dimension_line_refs
    assert height.dimension_line_refs
    assert len(width.hash_segment_refs) >= 2
    assert len(height.hash_segment_refs) >= 2
    assert width.extension_segment_refs
    assert width.endpoint_stations is not None


def test_unclassified_number_without_dim_line_stays_unmatched(tmp_path):
    clear_dimension_index_cache()
    native = _page(tmp_path, lambda page: page.insert_text((40, 40), "3600", fontsize=8))
    index = inventory_page_dimensions(native)
    assert len(index.figures) == 1
    assert index.figures[0].geometry_status == STATUS_UNMATCHED
    assert index.figures[0].role == ROLE_UNMATCHED
    assert index.figures[0].dimension_line_refs == ()


def test_two_dim_lines_for_one_figure_abstain(tmp_path):
    clear_dimension_index_cache()

    def drawer(page):
        page.insert_text((142, 188), "3600", fontsize=8)
        page.draw_line(fitz.Point(90, 165.5), fitz.Point(210, 165.5))
        page.draw_line(fitz.Point(90, 178.0), fitz.Point(210, 178.0))
        page.draw_line(fitz.Point(100, 160), fitz.Point(100, 165.5))
        page.draw_line(fitz.Point(200, 160), fitz.Point(200, 165.5))
        page.draw_line(fitz.Point(100, 172), fitz.Point(100, 178.0))
        page.draw_line(fitz.Point(200, 172), fitz.Point(200, 178.0))

    native = _page(tmp_path, drawer)
    item = inventory_page_dimensions(native).figures[0]
    assert item.geometry_status == STATUS_AMBIGUOUS
    assert item.role == ROLE_UNMATCHED


def test_two_figures_in_the_same_hash_interval_abstain(tmp_path):
    clear_dimension_index_cache()

    def drawer(page):
        page.draw_line(fitz.Point(90, 165.5), fitz.Point(210, 165.5))
        page.draw_line(fitz.Point(100, 160), fitz.Point(100, 165.5))
        page.draw_line(fitz.Point(200, 160), fitz.Point(200, 165.5))
        page.insert_text((120, 176), "3600", fontsize=8)
        page.insert_text((160, 176), "1800", fontsize=8)

    native = _page(tmp_path, drawer)
    statuses = {item.millimetres: item.geometry_status for item in inventory_page_dimensions(native).figures}
    assert statuses[Decimal("3600")] == STATUS_AMBIGUOUS
    assert statuses[Decimal("1800")] == STATUS_AMBIGUOUS


def test_cavity_slider_870_is_not_a_room_height(tmp_path):
    clear_dimension_index_cache()

    def drawer(page):
        page.insert_text((50, 40), "CS", fontsize=8)
        page.draw_line(fitz.Point(20, 30), fitz.Point(80, 30))
        page.draw_line(fitz.Point(30, 24), fitz.Point(30, 30))
        page.draw_line(fitz.Point(70, 24), fitz.Point(70, 30))
        page.insert_text((42, 42), "870", fontsize=8)

    native = _page(tmp_path, drawer)
    item = next(row for row in inventory_page_dimensions(native).figures if row.millimetres == Decimal("870"))
    assert item.role == ROLE_UNMATCHED
    assert item.geometry_status in {STATUS_UNIQUE, STATUS_UNMATCHED, STATUS_AMBIGUOUS}
    assert "height" not in item.role.lower()


def test_1200_1810_chain_owns_separate_hash_intervals(tmp_path):
    clear_dimension_index_cache()

    def drawer(page):
        for x in (100, 117, 168, 185):
            page.draw_line(fitz.Point(x, 160), fitz.Point(x, 165.5))
        page.draw_line(fitz.Point(90, 165.5), fitz.Point(195, 165.5))
        page.insert_text((105, 176), "1200", fontsize=8)
        page.insert_text((140, 176), "1810", fontsize=8)

    native = _page(tmp_path, drawer)
    by_mm = {item.millimetres: item for item in inventory_page_dimensions(native).figures}
    left, right = by_mm[Decimal("1200")], by_mm[Decimal("1810")]
    assert left.geometry_status == STATUS_UNIQUE
    assert right.geometry_status == STATUS_UNIQUE
    assert left.endpoint_stations != right.endpoint_stations
    assert left.role == ROLE_UNMATCHED


def test_inventory_is_cached_and_does_not_mutate_the_page(tmp_path):
    clear_dimension_index_cache()
    native = _page(tmp_path, _room_with_hashes)
    words = native.words
    first = inventory_page_dimensions(native)
    second = inventory_page_dimensions(native)
    assert first is second
    assert native.words is words


def test_translation_does_not_change_unique_millimetres(tmp_path):
    clear_dimension_index_cache()

    def shifted(page):
        page.draw_rect(fitz.Rect(130, 110, 230, 190), color=(0, 0, 0), width=0.4)
        page.draw_line(fitz.Point(130, 190), fitz.Point(130, 195.5))
        page.draw_line(fitz.Point(230, 190), fitz.Point(230, 195.5))
        page.draw_line(fitz.Point(120, 195.5), fitz.Point(240, 195.5))
        page.insert_text((172, 206), "3600", fontsize=8)

    origin = inventory_page_dimensions(_page(tmp_path, _room_with_hashes, "origin.pdf"))
    moved = inventory_page_dimensions(_page(tmp_path, shifted, "shifted.pdf"))
    origin_width = next(item for item in origin.figures if item.millimetres == Decimal("3600"))
    moved_width = next(item for item in moved.figures if item.millimetres == Decimal("3600"))
    assert origin_width.geometry_status == moved_width.geometry_status == STATUS_UNIQUE
    assert origin_width.millimetres == moved_width.millimetres


def test_extension_refs_must_touch_the_owned_dimension_line():
    """A distant segment at the same hash station is NOT source evidence."""
    from planreader_next.dimension_index import _segments_at_stations
    from planreader_next.engine import NativeSegment

    horizontal_line = NativeSegment("h-line", "line", 90, 100, 210, 100)
    near_h = NativeSegment("h-true-extension", "line", 100, 100, 100, 120)
    far_h = NativeSegment("h-unrelated-remote", "line", 100, 250, 100, 260)
    assert _segments_at_stations(
        [near_h, far_h], horizontal_line, (100.0, 200.0),
        max_length=44.0,
    ) == ("h-true-extension",)

    vertical_line = NativeSegment("v-line", "line", 100, 90, 100, 210)
    near_v = NativeSegment("v-true-extension", "line", 100, 100, 120, 100)
    far_v = NativeSegment("v-unrelated-remote", "line", 250, 100, 260, 100)
    assert _segments_at_stations(
        [near_v, far_v], vertical_line, (100.0, 200.0),
        max_length=44.0,
    ) == ("v-true-extension",)
