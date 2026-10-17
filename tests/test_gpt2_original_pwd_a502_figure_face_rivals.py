"""Private original PWD A502 inner/outer face rivals; no benchmark or m² issuer."""
from pathlib import Path
import hashlib

import pytest

from tools.diag_gpt2_original_figured_detail_plan_shadow import (
    audit_original_figured_detail_plan_pair,
)
from tools.diag_gpt2_original_figured_face_rivals_shadow import (
    audit_original_figured_detail_face_rivals,
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
COMPETITORS=(
    {"family_id":"original-outer-linework-candidate",
     "left":"d514i0","right":"d498i0",
     "top":"d487i0","bottom":"d511i0"},
    {"family_id":"original-inner-linework-candidate",
     "left":"d1125i0","right":"d1132i0",
     "top":"d1137i0","bottom":"d1129i0"},
)


@pytest.mark.skipif(not PDF.exists(),reason="original owner source not on public GitHub")
def test_original_pwd_outer_figure_and_real_competing_inner_face_bounds():
    original=PDF.read_bytes()
    assert hashlib.sha256(original).hexdigest()==SHA
    figure=audit_original_figured_detail_plan_pair(
        original,expected_sha256=SHA,**FIGURES)
    out=audit_original_figured_detail_face_rivals(
        original,source_sha256=SHA,original_figure_receipt=figure,
        page_1_based=26,competing_original_wall_face_families=COMPETITORS)
    assert out["status"]=="original_figured_face_source_rivals_only"
    assert out["original_exact_figure_endpoint_family_count"]==1
    outside,inside=out["original_source_candidate_face_families"]
    assert outside["original_source_native_bbox_pdf_pts"]==[
        217.44,1774.64,466.8,2179.52]
    assert inside["original_source_native_bbox_pdf_pts"]==[
        219.6,1777.04,464.64,2177.36]
    assert outside["source_exact_printed_figure_endpoints_match"]
    assert not inside["source_exact_printed_figure_endpoints_match"]
    assert inside["source_original_figure_endpoint_residual_x_pdf_pts"]==[
        2.16,-2.16]
    assert inside["source_original_figure_endpoint_residual_y_pdf_pts"]==[
        2.4,-2.16]
    # Genuine outer strokes have unpainted/split corners: no closing snap.
    assert not outside["source_full_four_edge_ring_uninterrupted"]
    assert inside["source_full_four_edge_ring_uninterrupted"]
    assert out["original_source_figured_area_m2_candidate_not_signed"]==7.854
    assert not out["unique_finished_net_face_role_authenticated"]
    assert not out["source_A502_to_A110_physical_room_issuer_granted"]
    assert out["new_firm_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not PDF.exists(),reason="original owner source required")
def test_original_competing_face_inputs_cannot_erase_existing_inner_source_ink():
    original=PDF.read_bytes()
    figure=audit_original_figured_detail_plan_pair(
        original,expected_sha256=SHA,**FIGURES)
    with pytest.raises(ValueError,match="independent_competing_original_face_paths_required"):
        audit_original_figured_detail_face_rivals(
            original,source_sha256=SHA,original_figure_receipt=figure,
            page_1_based=26,
            competing_original_wall_face_families=(COMPETITORS[0],{
                **COMPETITORS[1],"top":"d487i0",
            }))
    with pytest.raises(ValueError,match="original_figured_faces_pdf_sha_mismatch"):
        audit_original_figured_detail_face_rivals(
            original+b"forged",source_sha256=SHA,
            original_figure_receipt=figure,page_1_based=26,
            competing_original_wall_face_families=COMPETITORS)
