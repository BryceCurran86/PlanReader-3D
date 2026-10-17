"""Private original A502 PWD figured-plan evidence, never benchmark expected area.

The original PDF source exists privately on the owner's machine/ChatGPT
Library. Public Actions must skip positive original receipts when absent.
No frozen denominator/answer or customer quantity is input to the producer.
"""
import hashlib
from pathlib import Path

import pytest

from tools.diag_gpt2_original_figured_detail_plan_shadow import (
    audit_original_figured_detail_plan_pair as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

LENGTH={
    "label_address":(1,1,0),
    "line_id":"d12615i0",
    "first_ticks":("d12616i0","d12617i0"),
    "last_ticks":("d12621i0","d12622i0"),
}
WIDTH={
    "label_address":(3,1,0),
    "line_id":"d12656i0",
    "first_ticks":("d12657i0","d12658i0"),
    "last_ticks":("d12662i0","d12663i0"),
}
ARGS={
    "page_1_based":26,
    "first_dimension":LENGTH,
    "second_dimension":WIDTH,
    "original_room_word_address":(15,0,0),
    "original_finish_word_address":(14,1,0),
    "plan_enclosure_bbox_pdf_pts":(200.,1740.,495.,2220.),
}

@pytest.mark.skipif(not PDF.exists(),reason="private original drawing acceptance required")
def test_original_pwd_figures_have_independent_native_ends_and_orthogonal_ink():
    b=PDF.read_bytes()
    assert hashlib.sha256(b).hexdigest()==SHA
    r=audit(b,expected_sha256=SHA,**ARGS)
    assert r["status"]=="original_figured_orthogonal_detail_area_candidate_only"
    assert [v["original_native_figure_literal"]
            for v in r["original_figured_source_records"]]==["3570","2200"]
    assert r["scale_ratio_relative_disagreement"]<.001
    assert r["candidate_orthogonal_area_m2_not_signed"]==7.854
    assert [v["original_literal_untrusted"]
            for v in r["original_room_and_finish_mark_candidates"]]==["PWD","FT2"]
    assert not r["source_physical_room_crosssheet_identity_authenticated"]
    assert not r["source_finished_face_ownership_authenticated"]
    assert r["new_firm_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not PDF.exists(),reason="owner original PDF required")
def test_original_pwd_figured_figure_cannot_borrow_a_door_or_grid_source_arrow():
    b=PDF.read_bytes()
    bad={**LENGTH,"first_ticks":("d12616i0","d12657i0")}
    with pytest.raises(ValueError,match="source_figure_arrowhead_endpoint_not_bound"):
        audit(b,expected_sha256=SHA,**{**ARGS,"first_dimension":bad})
    bad={**WIDTH,"label_address":(1,1,0)}
    with pytest.raises(ValueError,match="duplicate_original_dimension_word"):
        audit(b,expected_sha256=SHA,**{**ARGS,"second_dimension":bad})


@pytest.mark.skipif(not PDF.exists(),reason="owner original PDF required")
def test_original_pwd_source_sha_cannot_be_replaced_by_morphed_pdf():
    b=PDF.read_bytes()
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit(b+b"forged",expected_sha256=SHA,**ARGS)
