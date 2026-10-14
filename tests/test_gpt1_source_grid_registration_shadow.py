"""Source-native grid text may suggest a view transform but never mint area."""
from __future__ import annotations

import hashlib

import fitz
import pytest

from pb_source_grid_registration_shadow import source_grid_registration_shadow


def _document(*, letters_shift=25., number_shift=0.,
              competing=False, incomplete=False, corrupt_letter=False,
              physical_grid=False, corrupt_line=False):
    document=fitz.open()
    for p in range(2):
        page=document.new_page(width=800,height=800)
        for token, x in (("C",120.),("B",340.),("A",560.)):
            if incomplete and token=="B":
                continue
            dx=letters_shift if p else 0.
            if p and corrupt_letter and token=="B":
                dx+=4.
            page.insert_text((x+dx,650.),token,fontsize=12)
        for token, y in zip("234567",(140.,215.,290.,365.,440.,515.)):
            page.insert_text((45.,y+number_shift*p),token,fontsize=12)
        if competing:
            for token,x in (("C",120.),("B",340.),("A",560.)):
                page.insert_text((x+(letters_shift if p else 0.),730.),token,fontsize=12)
        if physical_grid:
            unique={
                word[4]:((float(word[0])+float(word[2]))/2.0,
                         (float(word[1])+float(word[3]))/2.0)
                for word in page.get_text("words")
                if word[4] in "ABC234567"
            }
            for marker in "ABC":
                x=unique[marker][0]+(7. if corrupt_line and p and marker=="B" else 0.)
                for k in range(18):
                    y=70.+k*35.
                    page.draw_line((x,y),(x,y+26.),
                                   color=(1,0,0),width=.24)
            for marker in "234567":
                y=unique[marker][1]
                for k in range(18):
                    x=70.+k*35.
                    page.draw_line((x,y),(x+26.,y),
                                   color=(1,0,0),width=.24)
    b=document.tobytes()
    document.close()
    return b


def _run(data):
    return source_grid_registration_shadow(
        data,expected_sha256=hashlib.sha256(data).hexdigest(),
        first_page_index=0,second_page_index=1,
    )


def test_unique_orthogonal_source_native_grid_candidate_never_authorizes_floor():
    out=_run(_document())
    assert out["source_native_text_grid_candidate"] is True
    assert out["letter_grid_control_count"]==3
    assert out["number_grid_control_count"]==6
    assert out["native_grid_translation_candidate_pdf_pts"] == [25.0,0.0]
    assert out["first_unclosed_gate"]=="source_grid_drawn_line_and_raster_receipts_unverified"
    assert all(out[x] is False for x in (
        "source_grid_line_witness_verified","source_word_raster_corroborated",
        "source_plan_viewport_owned","cross_view_physical_room_equivalence_verified",
        "source_finish_occurrence_owned","source_floor_area_quantity_created",
        "commercial_projection_allowed",
    ))


def test_figure_distortion_on_one_axis_abstains():
    out=_run(_document(corrupt_letter=True))
    assert out["source_native_text_grid_candidate"] is False
    assert out["native_grid_translation_candidate_pdf_pts"] is None


def test_missing_source_letter_control_abstains():
    out=_run(_document(incomplete=True))
    assert not out["source_native_text_grid_candidate"]


def test_two_competing_source_grids_are_ambiguous():
    out=_run(_document(competing=True))
    assert out["source_native_text_grid_candidate"] is False
    assert out["first_unclosed_gate"]=="competing_source_grid_control_registrations"


def test_second_axis_independent_native_shift_is_retained_as_candidate_only():
    out=_run(_document(number_shift=16.))
    assert out["native_grid_translation_candidate_pdf_pts"] == [25.0,16.0]
    assert not out["source_grid_line_witness_verified"]


def test_wrong_original_source_sha_refuses_crossview_registration():
    with pytest.raises(ValueError,match="SHA"):
        source_grid_registration_shadow(
            _document(),expected_sha256="f"*64,
            first_page_index=0,second_page_index=1,
        )


@pytest.mark.parametrize("index",[-1,2,True])
def test_invalid_page_and_boolean_index_not_promoted(index):
    with pytest.raises(ValueError):
        source_grid_registration_shadow(
            _document(),expected_sha256=hashlib.sha256(_document()).hexdigest(),
            first_page_index=index,second_page_index=1,
        )


def test_same_page_cannot_self_register():
    data=_document()
    with pytest.raises(ValueError):
        source_grid_registration_shadow(
            data,expected_sha256=hashlib.sha256(data).hexdigest(),
            first_page_index=1,second_page_index=1,
        )


def test_non_pdf_bytes_do_not_create_consensus():
    data=b"not a PDF"
    with pytest.raises(Exception):
        source_grid_registration_shadow(
            data,expected_sha256=hashlib.sha256(data).hexdigest(),
            first_page_index=0,second_page_index=1,
        )


def test_two_original_physical_grid_axes_have_native_path_witnesses():
    result=_run(_document(physical_grid=True))
    assert result["source_native_text_grid_candidate"] is True
    assert result["source_native_vector_grid_candidate"] is True
    assert result["native_vector_grid_translation_candidate_pdf_pts"]==[25.0,0.0]
    assert len(result["native_vector_grid_letter_lineage"])==3
    assert len(result["native_vector_grid_number_lineage"])==6
    assert all(
        item["first_original_segment_count"]>=12
        and item["second_original_segment_count"]>=12
        for item in result["native_vector_grid_letter_lineage"]
    )
    assert result["first_unclosed_gate"]=="source_grid_producer_and_room_physical_equivalence_unverified"
    assert result["source_grid_line_witness_verified"] is False
    assert result["source_finish_occurrence_owned"] is False
    assert result["commercial_projection_allowed"] is False


def test_native_text_still_matches_but_one_drawn_grid_axis_conflicts():
    result=_run(_document(physical_grid=True,corrupt_line=True))
    assert result["source_native_text_grid_candidate"] is True
    assert result["source_native_vector_grid_candidate"] is False
    assert result["source_grid_line_witness_verified"] is False
    assert result["native_grid_translation_candidate_pdf_pts"]==[25.0,0.0]
    assert result["commercial_projection_allowed"] is False
