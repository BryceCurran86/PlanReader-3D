"""Owner-original A502 native dimension-chain proofs; not customer quantities.

All source paths, printed numbers and arrow-tip pairs are re-read from the
SHA-pinned original Maryborough PDF. Public CI may omit this private source.
"""
import hashlib
from pathlib import Path

import pytest

from tools.diag_gpt2_original_native_dimension_chain_shadow import (
    audit_original_native_orthogonal_dimension_chains as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"

VERTICAL={
    "short_before":{
        "line_id":"d12610i0","word_address":(1,2,0),
        "first_ticks":("d12611i0","d12612i0"),
        "last_ticks":("d12616i0","d12617i0")},
    "main":{
        "line_id":"d12615i0","word_address":(1,1,0),
        "first_ticks":("d12616i0","d12617i0"),
        "last_ticks":("d12621i0","d12622i0")},
    "short_after":{
        "line_id":"d12620i0","word_address":(1,0,0),
        "first_ticks":("d12621i0","d12622i0"),
        "last_ticks":("d12625i0","d12626i0")},
}
HORIZONTAL={
    "short_before":{
        "line_id":"d12651i0","word_address":(3,2,0),
        "first_ticks":("d12652i0","d12653i0"),
        "last_ticks":("d12657i0","d12658i0")},
    "main":{
        "line_id":"d12656i0","word_address":(3,1,0),
        "first_ticks":("d12657i0","d12658i0"),
        "last_ticks":("d12662i0","d12663i0")},
    "short_after":{
        "line_id":"d12661i0","word_address":(3,0,0),
        "first_ticks":("d12662i0","d12663i0"),
        "last_ticks":("d12666i0","d12667i0")},
}


@pytest.mark.skipif(not PDF.exists(),reason="owner-private original source required")
def test_original_a502_two_orthogonal_92_main_92_source_figure_chains():
    original=PDF.read_bytes()
    assert hashlib.sha256(original).hexdigest()==SHA
    result=audit(original,expected_sha256=SHA,page_1_based=26,
                 vertical=VERTICAL,horizontal=HORIZONTAL)
    assert result["status"]=="source_orthogonal_native_figured_chains_candidate_only"
    vertical=result["native_printed_dimension_chains"]["vertical"]
    horizontal=result["native_printed_dimension_chains"]["horizontal"]
    assert vertical["original_dimension_chain_mm"]==[92,3570,92]
    assert horizontal["original_dimension_chain_mm"]==[92,2200,92]
    assert vertical["original_arrowhead_connected_chain_pdf_pts"]==[
        1764.32,1774.64,2179.52,2189.84]
    assert horizontal["original_arrowhead_connected_chain_pdf_pts"]==[
        206.88,217.44,466.8,477.36]
    # The actual short drawn path overhangs its arrowhead tips by 5.76pt.
    # Its entire 16.08pt stroke must NEVER be interpreted as 92 mm.
    assert vertical["original_source_records"]["short_before"][
        "source_original_line_overhangs_pdf_pts"]==[5.76,0.]
    assert horizontal["original_source_records"]["short_after"][
        "source_original_line_overhangs_pdf_pts"]==[0.,5.52]
    assert max(vertical["source_small_figure_ratio_relative_deviations"])<.02
    assert max(horizontal["source_small_figure_ratio_relative_deviations"])<.02
    assert result["source_finished_net_area_m2"] is None
    assert result["new_firm_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


@pytest.mark.skipif(not PDF.exists(),reason="original owner PDF required")
def test_original_minor_figure_cannot_reuse_wrong_tick_or_borrow_another_label():
    original=PDF.read_bytes()
    bad={**VERTICAL["short_before"],"last_ticks":("d12621i0","d12622i0")}
    with pytest.raises(ValueError,match="original_dimension_tip_outside_own_source_line"):
        audit(original,expected_sha256=SHA,page_1_based=26,
              vertical={**VERTICAL,"short_before":bad},horizontal=HORIZONTAL)
    bad={**HORIZONTAL["short_before"],"word_address":(3,1,0)}
    with pytest.raises(ValueError,match="original_figure_text_outside_arrowhead_interval"):
        audit(original,expected_sha256=SHA,page_1_based=26,
              vertical=VERTICAL,horizontal={**HORIZONTAL,"short_before":bad})
