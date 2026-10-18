"""Stroked A120 GRID source-ring witnesses remain diagnostic and fail closed."""
import hashlib
from pathlib import Path
import fitz
import pytest

from tools.diag_gpt2_a120_grid_ring_shadow import (
    original_stroked_grid_rectangles_shadow as audit,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _document(*, offset=(0, 0), scale=1, rotation=0, competing="", omit_side=False, repeat_top=False):
    document = fitz.open()
    page = document.new_page(width=1500, height=1500)
    def at(pt):
        return (offset[0] + scale * pt[0], offset[1] + scale * pt[1])
    points = [(100, 100), (600, 100), (600, 650), (100, 650)]
    for i in range(3 if omit_side else 4):
        page.draw_line(at(points[i]), at(points[(i + 1) % 4]), color=(0, 0, 0), width=.48 * scale)
    if repeat_top:
        page.draw_line(at(points[0]), at(points[1]), color=(0, 0, 0), width=.48 * scale)
    # Genuine two-axis source grid lattice, independently of the outer ring.
    for y in (175, 250, 325, 400, 475, 550):
        page.draw_line(at((120, y)), at((580, y)), color=(0, 0, 0), width=.30 * scale)
    for x in (175, 250, 325, 400, 475, 550):
        page.draw_line(at((x, 120)), at((x, 630)), color=(0, 0, 0), width=.30 * scale)
    page.insert_text(at((250, 300)), "GRID")
    if competing:
        page.insert_text(at((270, 370)), competing)
    # A fill-only white graphic can never count as a wall ring witness.
    page.draw_rect(fitz.Rect(*at((700, 700)), *at((1350, 1350))),
                   color=None, fill=(1, 1, 1))
    if rotation:
        page.set_rotation(rotation)
    return document


@pytest.mark.parametrize("offset,scale,rotation", [
    ((0, 0), 1, 0), ((90, 30), 1, 0), ((0, 0), 1.3, 0),
    ((0, 0), 1, 90), ((0, 0), 1, 180), ((0, 0), 1, 270),
])
def test_native_four_stroked_sides_and_unique_material_mark(offset, scale, rotation):
    document = _document(offset=offset, scale=scale, rotation=rotation)
    try:
        result = audit(document[0], min_span_pt=200.)
        assert result["candidate_count"] == 1
        assert result["status"] == "candidate_source_stroked_ceiling_region"
        assert result["new_firm_quantities"] == 0
        assert result["candidates"][0]["firm_quantity_m2"] is None
        assert result["candidates"][0]["source_scale_authority"] is False
        assert len(set(result["candidates"][0]["source_path_ids"])) == 4
    finally:
        document.close()


@pytest.mark.parametrize("kwargs", [
    {"omit_side": True}, {"competing": "IPF1"}, {"competing": "IP"},
    {"competing": "FPB"}, {"competing": "WFPB"}, {"competing": "GRID"},
])
def test_missing_wall_source_or_competing_material_abstains(kwargs):
    document = _document(**kwargs)
    try:
        result = audit(document[0], min_span_pt=200.)
        assert result["candidate_count"] == 0
        assert result["new_firm_quantities"] == 0
    finally:
        document.close()


def test_duplicate_source_stroke_retains_all_parent_rivals():
    document = _document(repeat_top=True)
    try:
        result = audit(document[0], min_span_pt=200.)
        assert result["candidate_count"] == 2
        assert result["candidates"][0]["bbox_pdf_pts"] == result["candidates"][1]["bbox_pdf_pts"]
        assert result["candidates"][0]["source_path_ids"] != result["candidates"][1]["source_path_ids"]
        assert audit(document[0], min_span_pt=200.) == result
    finally:
        document.close()


def test_source_shadow_invalid_limits_fail_closed():
    document = _document()
    try:
        for invalid in (None, 0, -1, float("nan"), float("inf"), True):
            with pytest.raises(ValueError):
                audit(document[0], min_span_pt=invalid)
        with pytest.raises(ValueError):
            audit(document[0], code="GRID 3000")
    finally:
        document.close()


def test_original_a120_original_stroked_sales_grid_ring_with_rival_ink_parents():
    if not ORIGINAL.is_file():
        pytest.skip("PRIVATE original unavailable in public CI: no source-positive approval")
    raw = ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == SHA
    with fitz.open(stream=raw, filetype="pdf") as document:
        assert len(document) == 31
        page = document[8]
        assert page.rotation == 90
        result = audit(page, min_span_pt=200.)
        matching = [
            row for row in result["candidates"]
            if all(abs(a-b)<0.02 for a,b in zip(
                row["bbox_pdf_pts"], (703.44,646.40,1217.04,1550.48),
            ))
        ]
        assert len(matching) == 2
        assert {tuple(row["source_path_ids"]) for row in matching} == {
            (3897,3899,3898,3900), (3897,5135,3898,3900),
        }
        assert all(tuple(row["source_mark_address"]) == (114,1,0)
                   and row["firm_quantity_m2"] is None for row in matching)
        assert result["new_firm_quantities"] == 0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == SHA
