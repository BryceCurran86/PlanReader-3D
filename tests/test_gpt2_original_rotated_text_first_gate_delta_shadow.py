"""Original PDF and misleading native word integrity reasons: no promotion."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_original_rotated_text_first_gate_delta_shadow import (
    audit_original_rotated_text_first_gates as audit,
)

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_wrong_source_sha_and_native_addresses_never_alias_a_word():
    raw=PDF.read_bytes()
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        audit(raw,expected_sha256="0"*64,page_number=11,native_word_addresses=((1,2,3),))
    for addresses in ((),((1,2,3),(1,2,3)),((-1,2,3),),((1,2,3.5),)):
        with pytest.raises(ValueError,match="exact_original_native_word_addresses_required"):
            audit(raw,expected_sha256=SHA,page_number=11,native_word_addresses=addresses)
    result=audit(raw,expected_sha256=SHA,page_number=11,
                 native_word_addresses=((99999,0,0),))
    assert result["native_word_first_gate_rows"][0]["first_unclosed_gate"] == (
        "native_word_missing_or_address_ambiguous"
    )
    assert not result["native_clip_or_unicode_authority_raised"]


def test_synthetic_rotated_text_even_if_existing_classifier_trusts_is_not_granted():
    document=fitz.open()
    page=document.new_page(width=400,height=300)
    page.insert_text((40,90),"OFFICE FT3",fontsize=11)
    page.set_rotation(90)
    raw=document.tobytes()
    h=hashlib.sha256(raw).hexdigest()
    with fitz.open(stream=raw,filetype="pdf") as source:
        w=source[0].get_text("words")
        addresses=tuple((a[5],a[6],a[7]) for a in w)
    result=audit(raw,expected_sha256=h,page_number=1,
                 native_word_addresses=addresses)
    assert len(result["native_word_first_gate_rows"])==2
    for row in result["native_word_first_gate_rows"]:
        assert row["source_word_exact_native_parity"]
        assert not row["source_text_trusted_by_audit"]
        assert row["existing_rotated_classification"]["diagnostic_publication_authority_granted"] is False
        assert row["existing_zero_rotation_classification"]["diagnostic_publication_authority_granted"] is False
    assert not result["native_clip_or_unicode_authority_raised"]
    assert result["new_native_trusted_text_words"]==0
    document.close()


def test_six_original_ft3_native_marks_and_schedule_keep_competing_text_gates():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as original:
        words=original[10].get_text("words")
        addresses=tuple((w[5],w[6],w[7]) for w in words if w[4]=="FT3")
        assert len(addresses)==6  # five physical-plan marks and one schedule
        assert len(set(addresses))==6
    result=audit(raw,expected_sha256=SHA,page_number=11,
                 native_word_addresses=addresses)
    assert result["original_pdf_page_rotation_degrees"]==90
    assert len(result["native_word_first_gate_rows"])==6
    for row in result["native_word_first_gate_rows"]:
        assert row["original_source_word_literal_not_authentic"]=="FT3"
        assert row["source_word_exact_native_parity"]
        assert not row["source_text_trusted_by_audit"]
        assert row["existing_rotated_classification"]["existing_text_integrity_reason_codes"]
        assert isinstance(row["reason_codes_absent_only_after_rotation_zero"],list)
        assert isinstance(row["reason_codes_appearing_only_after_rotation_zero"],list)
    assert result["same_original_pdf_bytes_in_both_interpretations"]
    assert result["new_native_trusted_text_words"]==0
    assert result["new_material_semantic_definitions"]==0
    assert result["new_physical_floor_finish_occurrences"]==0
    assert result["new_customer_quantities"]==0
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA
