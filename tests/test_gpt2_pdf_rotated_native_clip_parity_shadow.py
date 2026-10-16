"""Rotated clip parity cannot serve as glyph, paint, or material permission."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_pdf_rotated_native_clip_parity_shadow import (
    audit_original_rotated_native_clip_parity as audit,
    comparison_gate,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_parity_flag_does_not_grant_clip_or_text_authority():
    candidate = {"scissor": [1, 2, 3, 4], "word": "FT3"}
    assert comparison_gate(candidate, candidate) == (
        "exact_native_representation_parity_candidate_not_text_trust"
    )
    assert comparison_gate(candidate, {"scissor": [2, 2, 3, 4], "word": "FT3"}) == (
        "rotated_native_text_or_clip_representation_conflict"
    )


def test_negative_mismatched_source_and_malformed_pages_abstain():
    original = ORIGINAL.read_bytes()
    with pytest.raises(ValueError, match="original_source_sha_mismatch"):
        audit(original,expected_sha256="0"*64,page_numbers=(11,))
    for pages in ((),(0,),(11,11),(11,"12"),[11],(False,)):
        with pytest.raises(ValueError, match="exact_source_page_numbers_required"):
            audit(original,expected_sha256=SOURCE_SHA,page_numbers=pages)
    with pytest.raises(ValueError,match="original_source_page_out_of_range"):
        audit(original,expected_sha256=SOURCE_SHA,page_numbers=(40,))


def test_independent_synthetic_rotated_page_parity_remains_candidate_only():
    doc=fitz.open()
    page=doc.new_page(width=300,height=200)
    page.insert_text((30,45),"GRID 3000",fontsize=11)
    page.draw_line((20,70),(170,70))
    page.set_rotation(90)
    raw=doc.tobytes()
    sha=hashlib.sha256(raw).hexdigest()
    result=audit(raw,expected_sha256=sha,page_numbers=(1,))
    record=result["source_page_parity_rows"][0]
    assert record["original_source_rotation_degrees"]==90
    assert record["in_memory_original_rotation_restored"]
    assert record["source_native_snapshot_restored"]
    assert record["first_parity_gate"] == (
        "exact_native_representation_parity_candidate_not_text_trust"
    )
    assert not record["native_pdf_clip_stack_text_authority_granted"]
    assert not record["native_pdf_unicode_glyph_authority_granted"]
    assert not record["renderer_paint_clip_visibility_proven"]
    assert result["new_native_text_trust_grants"] == result["new_quantities"] == 0
    doc.close()


def test_original_six_rotated_maryborough_pages_with_real_clip_stacks():
    original=ORIGINAL.read_bytes()
    assert hashlib.sha256(original).hexdigest()==SOURCE_SHA
    result=audit(
        original,expected_sha256=SOURCE_SHA,page_numbers=(7,9,11,25,26,27)
    )
    assert result["original_source_bytes_unchanged"]
    assert result["original_source_bytes_after"]==SOURCE_SHA
    assert len(result["source_page_parity_rows"])==6
    for row in result["source_page_parity_rows"]:
        assert row["original_source_rotation_degrees"]==90
        assert row["in_memory_original_rotation_restored"]
        assert row["source_native_snapshot_restored"]
        assert row["source_original_rotation_snapshot"]["native_clip_record_count"]>0
        assert row["first_parity_gate"] == (
            "exact_native_representation_parity_candidate_not_text_trust"
        )
        assert row["source_original_rotation_snapshot"] == row["in_memory_zero_rotation_snapshot"]
        assert not row["renderer_paint_clip_visibility_proven"]
        assert not row["native_pdf_clip_stack_text_authority_granted"]
    assert result["new_native_text_trust_grants"]==0
    assert result["new_material_definitions"]==0
    assert result["new_source_room_owners"]==0
    assert result["new_quantities"]==0
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SOURCE_SHA
