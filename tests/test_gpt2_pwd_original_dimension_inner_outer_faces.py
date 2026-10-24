"""Source PWD dimension terminals are not automatically inside wall faces."""
from __future__ import annotations

import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_original_dimension_face_terminal_rivals_shadow import (
    audit_original_dimension_to_competing_wall_faces as audit,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _synthetic():
    pdf=fitz.open()
    page=pdf.new_page(width=300,height=300)
    for y in (20,22,78,80):
        page.draw_line((50,y),(200,y),color=(0,0,0),width=.48)
    page.draw_line((10,20),(10,80),color=(0,0,0),width=.48)
    raw=pdf.tobytes()
    pdf.close()
    return raw


def _run(raw,**changes):
    args={
        "expected_sha256":hashlib.sha256(raw).hexdigest(),
        "page_1_based":1,
        "original_dimension_line_path_item_id":"d4i0",
        "original_candidate_face_line_path_item_ids":
            ("d0i0","d1i0","d2i0","d3i0"),
    }
    args.update(changes)
    return audit(raw,**args)


def test_native_dimension_terminal_faces_keep_inner_outer_candidates_without_electing():
    result=_run(_synthetic())
    assert result["original_dimension_axis"]=="vertical"
    assert result["original_dimension_terminal_coordinates_pdf_pts"]==(20.,80.)
    assert result["original_dimension_ink_length_pdf_pts"]==60
    rivals=result["all_bounded_competing_original_face_sources"]
    assert len(rivals)==4
    assert sorted(r["nearest_original_figured_terminal_distance_pdf_pts"]
                  for r in rivals)==[0.,0.,2.,2.]
    assert result["original_dimension_witness_is_internal_finished_clear_span"] is False
    assert result["new_firm_quantities"]==0


@pytest.mark.parametrize("kwargs",[
    {"expected_sha256":"0"*64},
    {"original_dimension_line_path_item_id":"d999i0"},
    {"original_dimension_line_path_item_id":"d0i0"},
    {"original_candidate_face_line_path_item_ids":("d0i0","d0i0")},
    {"original_candidate_face_line_path_item_ids":("d4i0",)},
    {"maximum_terminal_face_offset_pdf_pts":float("nan")},
    {"maximum_terminal_face_offset_pdf_pts":0},
    {"maximum_native_paths":1},
])
def test_non_original_or_invalid_figured_terminal_faces_fail_closed(kwargs):
    with pytest.raises(ValueError):
        _run(_synthetic(),**kwargs)


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF unavailable")
def test_original_pwd_a502_3570_outer_terminals_have_distinct_inner_faces():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    out=audit(
        raw,expected_sha256=SHA,page_1_based=26,
        original_dimension_line_path_item_id="d12615i0",
        original_candidate_face_line_path_item_ids=(
            "d487i0","d511i0","d1137i0","d1129i0"),
    )
    assert out["original_dimension_ink_length_pdf_pts"]==pytest.approx(404.88)
    rivals={r["original_face_native_path_item_id"]:r
            for r in out["all_bounded_competing_original_face_sources"]}
    assert len(rivals)==4
    assert rivals["d487i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==0
    assert rivals["d511i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==0
    assert rivals["d1137i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==pytest.approx(2.4)
    assert rivals["d1129i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==pytest.approx(2.16)
    assert out["source_painted_face_elected_for_finished_floor"] is False
    assert out["new_firm_quantities"]==0


@pytest.mark.skipif(not ORIGINAL.is_file(),reason="private original PDF unavailable")
def test_original_pwd_a502_2200_outer_terminals_have_distinct_inner_faces():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    out=audit(
        raw,expected_sha256=SHA,page_1_based=26,
        original_dimension_line_path_item_id="d12656i0",
        original_candidate_face_line_path_item_ids=(
            "d514i0","d498i0","d1125i0","d1132i0"),
    )
    assert out["original_dimension_ink_length_pdf_pts"]==pytest.approx(249.36)
    rivals={r["original_face_native_path_item_id"]:r
            for r in out["all_bounded_competing_original_face_sources"]}
    assert len(rivals)==4
    assert rivals["d514i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==0
    assert rivals["d498i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==0
    assert rivals["d1125i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==pytest.approx(2.16)
    assert rivals["d1132i0"]["nearest_original_figured_terminal_distance_pdf_pts"]==pytest.approx(2.16)
    assert out["source_painted_face_elected_for_finished_floor"] is False
