"""Original A502 PWD detail vs A110 physical room source coincidence receipt.

Private original source tests only: no guessed room polygons, calibration,
net square metres, benchmark-answer fixtures or public private-source upload.
"""
from pathlib import Path
import hashlib

import pytest

from tools.diag_gpt2_original_figured_detail_plan_shadow import (
    audit_original_figured_detail_plan_pair,
)
from tools.diag_gpt2_original_figured_face_rivals_shadow import (
    audit_original_figured_detail_face_rivals,
)
from tools.diag_gpt2_original_detail_floor_same_room_shadow import (
    audit_original_detail_vs_main_source_room_candidate,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
FIGURES={
    "page_1_based":26,
    "first_dimension":{
        "label_address":(1,1,0),"line_id":"d12615i0",
        "first_ticks":("d12616i0","d12617i0"),
        "last_ticks":("d12621i0","d12622i0"),
    },
    "second_dimension":{
        "label_address":(3,1,0),"line_id":"d12656i0",
        "first_ticks":("d12657i0","d12658i0"),
        "last_ticks":("d12662i0","d12663i0"),
    },
    "original_room_word_address":(15,0,0),
    "original_finish_word_address":(14,1,0),
    "plan_enclosure_bbox_pdf_pts":(200.,1740.,495.,2220.),
}
FAMILIES=(
    {"family_id":"actual-outer-source-face",
     "left":"d514i0","right":"d498i0",
     "top":"d487i0","bottom":"d511i0"},
    {"family_id":"actual-inner-source-face",
     "left":"d1125i0","right":"d1132i0",
     "top":"d1137i0","bottom":"d1129i0"},
)
INPUT={
    "original_floor_page":7,
    "original_detail_page":26,
    "floor_source_edge_ids":(
        "d66215i0","d53702i0","d53724i0",
        "d52626i0","d52631i0",
    ),
    "original_floor_room_word_address":(25,0,0),
    "original_detail_room_word_address":(15,0,0),
    "original_floor_door_word_address":(181,0,0),
    "original_detail_door_word_address":(14,0,0),
    "source_room_literal":"PWD",
    "original_door_code_literal":"D13",
    "original_detail_finish_code_literal":"FT2",
}


@pytest.mark.skipif(not PDF.exists(),reason="private owner original source required")
def test_source_pwd_plan_distinguished_from_four_inset_elevations_and_two_faces():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    figured=audit_original_figured_detail_plan_pair(
        raw,expected_sha256=SHA,**FIGURES)
    rivals=audit_original_figured_detail_face_rivals(
        raw,source_sha256=SHA,original_figure_receipt=figured,
        page_1_based=26,competing_original_wall_face_families=FAMILIES)
    receipt=audit_original_detail_vs_main_source_room_candidate(
        raw,source_sha256=SHA,original_detail_figure_face_receipt=rivals,
        **INPUT,
    )
    assert receipt["status"]=="original_detail_floor_source_coincidence_candidates_only"
    assert receipt["source_original_plan_caption_evidence"][
        "source_caption_literal_text"]=="PROP. PWD PLAN"
    assert receipt["source_original_plan_caption_evidence"][
        "source_competing_local_elevation_caption_count"]==4
    assert [row["original_raw_literal"] for row in
            receipt["source_original_room_and_door_word_candidates"]]==[
        "PWD","PWD","D13","D13"]
    assert receipt["original_page_rotations_degrees"]==(90,90)
    assert receipt["original_detail_finish_literal_source_candidate"]=="FT2"
    assert receipt["original_source_plan_words_inside_own_physical_ink_candidates"]
    assert receipt["original_source_door_word_intersects_printed_top_boundary"]
    assert len(receipt["source_all_figured_inner_outer_axis_correspondence_candidates"])==2
    geometries=receipt["source_all_figured_inner_outer_axis_correspondence_candidates"]
    assert all(row["source_original_axes_relative_disagreement"]<.01
               for row in geometries)
    assert receipt["original_source_figured_area_m2_candidate_not_signed"]==7.854
    assert not receipt["source_original_detail_to_main_floor_same_room_authenticated"]
    assert not receipt["source_W4_finished_floor_or_wall_role_authenticated"]
    assert receipt["new_firm_quantities"]==0


@pytest.mark.skipif(not PDF.exists(),reason="private original source required")
def test_wrong_native_room_label_or_moved_pdf_fails_before_w4_identity():
    raw=PDF.read_bytes()
    figured=audit_original_figured_detail_plan_pair(
        raw,expected_sha256=SHA,**FIGURES)
    rivals=audit_original_figured_detail_face_rivals(
        raw,source_sha256=SHA,original_figure_receipt=figured,
        page_1_based=26,competing_original_wall_face_families=FAMILIES)
    with pytest.raises(ValueError,match="original_room_or_door_source_literal_mismatch"):
        audit_original_detail_vs_main_source_room_candidate(
            raw,source_sha256=SHA,original_detail_figure_face_receipt=rivals,
            **{**INPUT,"original_detail_door_word_address":(15,0,0)},
        )
    # Exact D13 is ALSO printed elsewhere in the same original A502
    # sheet, but belongs to an elevation, not the PROP. PWD PLAN inset.
    with pytest.raises(ValueError,match="original_plan_word_or_door_boundary_not_source_owned"):
        audit_original_detail_vs_main_source_room_candidate(
            raw,source_sha256=SHA,original_detail_figure_face_receipt=rivals,
            **{**INPUT,"original_detail_door_word_address":(48,0,0)},
        )
    # A real "PWD" caption and D13 doorway cannot borrow the printed
    # floor finish from an unrelated FT code on an elevation or schedule.
    with pytest.raises(ValueError,match="original_detail_room_or_finish_mark_mismatch"):
        audit_original_detail_vs_main_source_room_candidate(
            raw,source_sha256=SHA,original_detail_figure_face_receipt=rivals,
            **{**INPUT,"original_detail_finish_code_literal":"IPF1"},
        )
    with pytest.raises(ValueError,match="original_same_room_source_sha_mismatch"):
        audit_original_detail_vs_main_source_room_candidate(
            raw+b"source changed",source_sha256=SHA,
            original_detail_figure_face_receipt=rivals,**INPUT,
        )
