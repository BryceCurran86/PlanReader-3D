"""The source-coordinate agreement does not bind a physical PWD wall face."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_source_dimension_face_competitors_shadow import (
    audit_native_dimension_face_competitors as audit,
)

PDF = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_original_pwd_figure_axis_agrees_but_actual_witness_does_not_intersect():
    data = PDF.read_bytes()
    assert hashlib.sha256(data).hexdigest() == SHA
    with fitz.open(stream=data, filetype="pdf") as doc:
        page = doc[25]
        region = (200,1700,500,2220)
        for source_id, outer_id, rival_id in (
            ("d12615i0","d487i0","d1137i0"),
            ("d12656i0","d514i0","d1125i0"),
        ):
            result = audit(
                page, source_dimension_line_id=source_id,
                candidate_region_bbox=region,
            )
            assert result["status"] == "read_only_projected_endpoint_competitors"
            assert not result["source_candidate_universe_complete"]
            assert not result["dimension_authority_granted"]
            assert not result["source_wall_face_authority_granted"]
            all_rows = [
                r for end in result["dimension_endpoints"]
                for r in end["all_region_axis_normal_original_source_lines"]
            ]
            outer = [r for r in all_rows if r["original_source_primitive_id"] == outer_id]
            assert outer and any(r["projected_dimension_coordinate_equal"] for r in outer)
            assert all(not r["source_figure_witness_intersection_proven"] for r in outer)
            assert all(r["transverse_gap_pdf_pts"] > 50 for r in outer)
            assert any(r["original_source_primitive_id"] == rival_id for r in all_rows)
    assert hashlib.sha256(PDF.read_bytes()).hexdigest() == SHA


def test_misleading_fixture_lines_share_the_same_axis_coordinate():
    d = fitz.open()
    p = d.new_page(width=300,height=300)
    p.draw_line((20,10),(20,120))   # source dimension candidate
    p.draw_line((50,10),(100,10))  # outer wall-like candidate
    p.draw_line((80,10),(90,10))   # same projected coordinate, fixture
    p.draw_line((50,12),(100,12))  # inner competing wall-like candidate
    result = audit(
        p,source_dimension_line_id="d0i0",
        candidate_region_bbox=(40,0,110,130),
    )
    rows = result["dimension_endpoints"][0]["all_region_axis_normal_original_source_lines"]
    assert len(rows) == 3
    assert len([r for r in rows if r["projected_dimension_coordinate_equal"]]) == 2
    assert all(not r["source_line_physical_wall_role_proven"] for r in rows)
    assert all(r["transverse_gap_pdf_pts"] >= 30 for r in rows)
    assert not result["quantity_granted"]
    d.close()


def test_invalid_primitive_or_region_refuses_authority():
    d=fitz.open()
    p=d.new_page()
    p.draw_line((10,10),(20,20))
    with pytest.raises(ValueError):
        audit(p,source_dimension_line_id="d1i0",candidate_region_bbox=(0,0,100,100))
    with pytest.raises(ValueError):
        audit(p,source_dimension_line_id="d0i0",candidate_region_bbox=(0,0,0,100))
    with pytest.raises(ValueError):
        audit(p,source_dimension_line_id="d0i0x",candidate_region_bbox=(0,0,100,100))
    result=audit(p,source_dimension_line_id="d0i0",candidate_region_bbox=(0,0,100,100))
    assert result["status"]=="not_a_native_axis_dimension_line"
    d.close()


def test_no_partial_universe_when_source_line_cap_exceeded():
    d=fitz.open()
    p=d.new_page()
    p.draw_line((20,10),(20,120))
    p.draw_line((50,10),(100,10))
    result=audit(
        p,source_dimension_line_id="d0i0",
        candidate_region_bbox=(0,0,200,200),max_original_lines=1,
    )
    assert result["status"]=="source_candidate_scope_exceeded_cap"
    assert not result["source_candidate_universe_complete"]
    assert not result["quantity_granted"]
    d.close()
