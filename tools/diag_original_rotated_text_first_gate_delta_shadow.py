"""Compare the EXISTING text-integrity gate at /Rotate N versus zero.

This is an isolated original-SHA diagnostic, not a new text decoder.
Two independent in-memory copies of identical PDF bytes use their own
PdfTextIntegrityAuthority page caches; no source file is written and no word
is trusted or exported by this audit. Native block ordinals are exact
source addresses within each replay only, never semantic room identity.
"""
from __future__ import annotations

import hashlib
import fitz


MAX_EXPLICIT_ORIGINAL_WORD_ADDRESSES=64


def _words_by_native_address(page):
    indexed={}
    for word in page.get_text("words"):
        if len(word)<8:
            continue
        try:
            key=(int(word[5]),int(word[6]),int(word[7]))
        except (TypeError,ValueError,OverflowError):
            continue
        indexed.setdefault(key,[]).append(word)
    return indexed


def _native_word_record(word):
    return {
        "text":str(word[4]).strip(),
        "bbox":[float(v) for v in word[:4]],
        "block_no":int(word[5]),
        "line_no":int(word[6]),
        "word_no":int(word[7]),
    }


def _actual_integrity_receipt(page,word):
    from pb_pdf_text_integrity_authority import classify_native_word_integrity
    decision=classify_native_word_integrity(page,_native_word_record(word))
    return {
        "existing_text_integrity_decode_status":str(decision.decode_status),
        "existing_text_integrity_visibility_status":str(decision.visibility_status),
        "existing_text_integrity_reason_codes":list(decision.reason_codes),
        "existing_classifier_trusted_value_read_only":bool(decision.trusted),
        "diagnostic_publication_authority_granted":False,
    }


def audit_original_rotated_text_first_gates(
    source_bytes:bytes, *, expected_sha256:str,
    page_number:int, native_word_addresses:tuple[tuple[int,int,int],...],
):
    if type(source_bytes) is not bytes:
        raise TypeError("immutable_original_pdf_bytes_required")
    digest=hashlib.sha256(source_bytes).hexdigest()
    if type(expected_sha256) is not str or digest!=expected_sha256:
        raise ValueError("original_source_sha_mismatch")
    if type(page_number) is not int or page_number<1:
        raise ValueError("positive_original_pdf_page_required")
    if (type(native_word_addresses) is not tuple
            or not native_word_addresses
            or len(native_word_addresses)>MAX_EXPLICIT_ORIGINAL_WORD_ADDRESSES
            or len(set(native_word_addresses))!=len(native_word_addresses)
            or any(type(a) is not tuple or len(a)!=3
                   or any(type(i) is not int or i<0 for i in a)
                   for a in native_word_addresses)):
        raise ValueError("exact_original_native_word_addresses_required")

    # An independent second page handle ensures rotation-sensitive caches
    # never inadvertently borrow evidence from the first interpretation.
    with fitz.open(stream=source_bytes,filetype="pdf") as a:
        with fitz.open(stream=source_bytes,filetype="pdf") as b:
            if page_number>len(a) or page_number>len(b):
                raise ValueError("original_source_page_out_of_range")
            before=a[page_number-1]
            after=b[page_number-1]
            original_rotation=int(before.rotation)
            after.set_rotation(0)
            before_words=_words_by_native_address(before)
            zero_words=_words_by_native_address(after)
            rows=[]
            for addr in native_word_addresses:
                previous=before_words.get(addr,())
                transformed=zero_words.get(addr,())
                if len(previous)!=1 or len(transformed)!=1:
                    rows.append({
                        "native_source_word_address":list(addr),
                        "first_unclosed_gate":"native_word_missing_or_address_ambiguous",
                        "source_text_trusted_by_audit":False,
                    })
                    continue
                word1,word2=previous[0],transformed[0]
                same=(
                    str(word1[4])==str(word2[4])
                    and all(abs(float(x)-float(y))<1e-6
                            for x,y in zip(word1[:4],word2[:4]))
                )
                if not same:
                    rows.append({
                        "native_source_word_address":list(addr),
                        "first_unclosed_gate":"rotation_changed_native_word_ancestry",
                        "source_text_trusted_by_audit":False,
                    })
                    continue
                original=_actual_integrity_receipt(before,word1)
                normalized=_actual_integrity_receipt(after,word2)
                original_reasons=set(original["existing_text_integrity_reason_codes"])
                normalized_reasons=set(normalized["existing_text_integrity_reason_codes"])
                rows.append({
                    "native_source_word_address":list(addr),
                    "original_source_word_literal_not_authentic":str(word1[4]),
                    "original_native_word_bbox_pdf_pts":[float(x) for x in word1[:4]],
                    "source_word_exact_native_parity":True,
                    "existing_rotated_classification":original,
                    "existing_zero_rotation_classification":normalized,
                    "reason_codes_absent_only_after_rotation_zero":
                        sorted(original_reasons-normalized_reasons),
                    "reason_codes_appearing_only_after_rotation_zero":
                        sorted(normalized_reasons-original_reasons),
                    "first_unclosed_gate":"source_clip_or_glyph_paint_role_needs_independent_review",
                    "source_text_trusted_by_audit":False,
                })
    return {
        "original_source_sha256":digest,
        "original_pdf_page_one_based":page_number,
        "original_pdf_page_rotation_degrees":original_rotation,
        "native_word_first_gate_rows":rows,
        "same_original_pdf_bytes_in_both_interpretations":True,
        "original_source_bytes_immutable":True,
        "native_clip_or_unicode_authority_raised":False,
        "new_native_trusted_text_words":0,
        "new_material_semantic_definitions":0,
        "new_physical_floor_finish_occurrences":0,
        "new_customer_quantities":0,
    }
