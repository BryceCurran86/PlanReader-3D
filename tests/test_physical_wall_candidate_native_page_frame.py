from __future__ import annotations

import fitz
import pytest

from pb_physical_wall_candidate_authority import (
    PHYSICAL_WALL_CANDIDATE_PAGE_FRAME_UNRESOLVED,
    _WallPageFrameUnresolved,
    _native_wall_scope_page_extent,
)


def _page(*, width: float = 600.0, height: float = 800.0, rotation: int = 0):
    doc = fitz.open()
    page = doc.new_page(width=width, height=height)
    if rotation:
        page.set_rotation(rotation)
    return doc, page


def test_rotation_zero_wall_scope_extent_is_unchanged() -> None:
    doc, page = _page(width=600.0, height=800.0)
    try:
        assert tuple(page.rect) == (0.0, 0.0, 600.0, 800.0)
        assert _native_wall_scope_page_extent(page) == (600.0, 800.0)
    finally:
        doc.close()


def test_rotation_90_wall_scope_uses_native_not_display_extent() -> None:
    doc, page = _page(width=600.0, height=800.0, rotation=90)
    try:
        assert tuple(page.rect) == (0.0, 0.0, 800.0, 600.0)
        native_width, native_height = _native_wall_scope_page_extent(page)
        assert (native_width, native_height) == (600.0, 800.0)

        # A native source primitive may legitimately occupy this band even
        # though it lies beyond the display-rotated page.rect height.
        native_source_y = 750.0
        assert native_source_y > float(page.rect.height)
        assert native_source_y < native_height
    finally:
        doc.close()


@pytest.mark.parametrize("rotation", [180, 270])
def test_unvalidated_real_source_rotations_fail_closed(rotation: int) -> None:
    doc, page = _page(width=600.0, height=800.0, rotation=rotation)
    try:
        with pytest.raises(
            _WallPageFrameUnresolved,
            match=PHYSICAL_WALL_CANDIDATE_PAGE_FRAME_UNRESOLVED,
        ):
            _native_wall_scope_page_extent(page)
    finally:
        doc.close()


def test_nonorthogonal_pdf_rotate_entry_fails_closed() -> None:
    doc, page = _page(width=600.0, height=800.0)
    try:
        doc.xref_set_key(page.xref, "Rotate", "135")
        with pytest.raises(
            _WallPageFrameUnresolved,
            match=PHYSICAL_WALL_CANDIDATE_PAGE_FRAME_UNRESOLVED,
        ):
            _native_wall_scope_page_extent(page)
    finally:
        doc.close()
