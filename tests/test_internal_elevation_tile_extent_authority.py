from __future__ import annotations

import fitz
import pytest

from pb_internal_elevation_tile_extent_authority import (
    extract_internal_elevation_tile_surfaces,
)
from pb_migration_contracts import EvidenceResolutionStatus


SHA = "a" * 64
PT_PER_M_AT_1_50 = 1000.0 / (50.0 * 25.4 / 72.0)


def _page():
    doc = fitz.open()
    page = doc.new_page(width=600, height=800)
    return doc, page


def _title(page, x: float, y: float, text: str, *, scale: str | None = "Scale 1:50"):
    page.insert_text((x, y), text, fontsize=12)
    if scale:
        page.insert_text((x, y + 16), scale, fontsize=7)


def _wall(page, x: float, y: float, width_m: float, height_m: float):
    width = width_m * PT_PER_M_AT_1_50
    height = height_m * PT_PER_M_AT_1_50
    page.draw_rect(fitz.Rect(x, y, x + width, y + height), width=1.0)
    return fitz.Rect(x, y, x + width, y + height)


def test_repeated_source_titles_create_distinct_internal_elevation_viewports():
    doc, page = _page()
    _wall(page, 70, 100, 1.68, 2.7)
    _wall(page, 330, 100, 0.9, 2.7)
    _title(page, 75, 310, "Wet Area A")
    _title(page, 335, 310, "Wet Area B")

    result = extract_internal_elevation_tile_surfaces(
        page,
        document_id="doc",
        source_sha256=SHA,
        page_id="12",
        page_number=12,
    )

    assert len(result.viewports) == 2
    assert result.viewports[0].viewport_id != result.viewports[1].viewport_id
    assert all(v.view_kind == "internal_elevation" for v in result.viewports)
    doc.close()


def test_full_height_shower_return_uses_shw_width_and_authenticated_scale_height():
    doc, page = _page()
    _wall(page, 70, 100, 1.68, 2.7)
    target = _wall(page, 330, 100, 0.9, 2.7)
    _title(page, 75, 310, "Wet Area A")
    _title(page, 335, 310, "Wet Area B")
    page.insert_text((332, 80), "SHOWER TILES TO", fontsize=7)
    page.insert_text((332, 90), "RUN UP TO CEILING", fontsize=7)
    page.insert_text((340, target.y1 + 14), "900", fontsize=7)
    page.insert_text((340, target.y1 + 24), "SHW", fontsize=7)

    result = extract_internal_elevation_tile_surfaces(
        page,
        document_id="doc",
        source_sha256=SHA,
        page_id="12",
        page_number=12,
    )

    resolved = [r for r in result.resolutions if r.status is EvidenceResolutionStatus.CORROBORATED]
    assert len(resolved) == 1
    assert resolved[0].quantity_m2 == pytest.approx(2.43, rel=0.01)
    doc.close()


def test_figured_skirting_dimensions_publish_without_scale_authority():
    doc, page = _page()
    _wall(page, 70, 100, 1.68, 2.7)
    _wall(page, 330, 100, 3.08, 2.7)
    _title(page, 75, 310, "Utility A", scale=None)
    _title(page, 335, 310, "Utility B", scale=None)
    page.insert_text((340, 265), "TILE SKIRTING", fontsize=7)
    page.insert_text((340, 278), "3,080", fontsize=7)
    page.insert_text((390, 278), "190 TILES", fontsize=7)

    result = extract_internal_elevation_tile_surfaces(
        page,
        document_id="doc",
        source_sha256=SHA,
        page_id="13",
        page_number=13,
    )

    resolved = [r for r in result.resolutions if r.status is EvidenceResolutionStatus.CORROBORATED]
    assert len(resolved) == 1
    assert resolved[0].quantity_m2 == pytest.approx(0.5852, rel=1e-6)
    assert resolved[0].canonical_wall_surface is not None
    doc.close()


def test_full_height_tile_scope_without_scale_or_figured_height_abstains():
    doc, page = _page()
    _wall(page, 70, 100, 1.68, 2.7)
    target = _wall(page, 330, 100, 0.9, 2.7)
    _title(page, 75, 310, "Wet Area A", scale=None)
    _title(page, 335, 310, "Wet Area B", scale=None)
    page.insert_text((332, 80), "SHOWER TILES TO", fontsize=7)
    page.insert_text((332, 90), "RUN UP TO CEILING", fontsize=7)
    page.insert_text((340, target.y1 + 14), "900 SHW", fontsize=7)

    result = extract_internal_elevation_tile_surfaces(
        page,
        document_id="doc",
        source_sha256=SHA,
        page_id="12",
        page_number=12,
    )

    assert result.resolutions == ()
    assert "scale_or_figured_height_required" in result.reason_codes
    doc.close()


def test_rear_full_height_tile_face_subtracts_authenticated_niche_face():
    doc, page = _page()
    wall = _wall(page, 70, 100, 1.68, 2.7)
    _wall(page, 330, 100, 0.9, 2.7)
    _title(page, 75, 310, "Wet Area A")
    _title(page, 335, 310, "Wet Area B")
    page.insert_text((72, 80), "SHOWER TILES TO", fontsize=7)
    page.insert_text((72, 90), "RUN UP TO CEILING", fontsize=7)
    page.insert_text((85, wall.y1 + 14), "1,680", fontsize=7)
    page.insert_text((90, 180), "600", fontsize=7)
    page.insert_text((110, 195), "400 NICHE", fontsize=7)

    result = extract_internal_elevation_tile_surfaces(
        page,
        document_id="doc",
        source_sha256=SHA,
        page_id="12",
        page_number=12,
    )

    resolved = [r for r in result.resolutions if r.status is EvidenceResolutionStatus.CORROBORATED]
    assert len(resolved) == 1
    assert resolved[0].quantity_m2 == pytest.approx(4.296, rel=0.01)
    doc.close()


def test_plan_title_is_not_promoted_as_internal_elevation_viewport():
    doc, page = _page()
    _wall(page, 70, 100, 2.0, 2.7)
    page.insert_text((75, 310), "Wet Area Plan", fontsize=12)
    page.insert_text((75, 326), "Scale 1:50", fontsize=7)
    page.insert_text((85, 180), "TILES", fontsize=7)

    result = extract_internal_elevation_tile_surfaces(
        page,
        document_id="doc",
        source_sha256=SHA,
        page_id="12",
        page_number=12,
    )

    assert result.viewports == ()
    assert result.resolutions == ()
    doc.close()
