"""Exact native PDF schedule row words: untrusted until glyph/clip authority.

This read-only source inventory preserves candidate definitions separately
from in-plan material occurrences and never authenticates a room or quantity.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz


def audit_original_native_floor_finish_schedule_rows(
    pdf_bytes:bytes, *, expected_sha256:str, page_1_based:int,
    requested_code_and_native_block:tuple[tuple[str,int],...],
) -> dict:
    if (type(pdf_bytes) is not bytes or not pdf_bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("immutable_original_schedule_source_sha256_required")
    if type(page_1_based) is not int or page_1_based<=0:
        raise ValueError("original_schedule_page_required")
    if (type(requested_code_and_native_block) not in (tuple,list)
            or not 1<=len(requested_code_and_native_block)<=32
            or any(type(row) not in (tuple,list) or len(row)!=2
                   or type(row[0]) is not str
                   or not re.fullmatch("[A-Z][A-Z0-9]{1,15}",row[0])
                   or type(row[1]) is not int or row[1]<0
                   for row in requested_code_and_native_block)):
        raise ValueError("source_native_material_block_selection_invalid")
    selections=tuple((str(code),int(block)) for code,block
                     in requested_code_and_native_block)
    if (len({row[0] for row in selections})!=len(selections)
            or len({row[1] for row in selections})!=len(selections)):
        raise ValueError("source_material_schedule_selector_alias_conflict")
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if page_1_based>len(doc):
            raise ValueError("original_schedule_page_out_of_range")
        words=doc[page_1_based-1].get_text("words",sort=False)
    if len(words)>100000:
        raise ValueError("bounded_source_native_schedule_words_required")
    by_block={}
    seen=set()
    for word in words:
        if (type(word) not in (tuple,list) or len(word)<8
                or any(type(v) is not int or v<0 for v in word[5:8])
                or any(type(v) not in (float,int) or not math.isfinite(v)
                       for v in word[:4])):
            raise ValueError("malformed_native_schedule_source_word")
        address=(page_1_based,word[5],word[6],word[7])
        if address in seen:
            raise ValueError("duplicate_native_schedule_word_address")
        seen.add(address)
        by_block.setdefault(word[5],[]).append(word)
    rows=[]
    for code,block_no in selections:
        candidates=sorted(by_block.get(block_no,()),
                          key=lambda w:(w[6],w[7]))
        if not candidates or str(candidates[0][4]).strip()!=code:
            raise ValueError("original_schedule_code_block_first_word_unproven")
        if sum(str(w[4]).strip()==code for w in candidates)!=1:
            raise ValueError("original_schedule_code_occurs_multiple_times")
        tokens=[]
        for word in candidates:
            tokens.append({
                "printed_text_untrusted":str(word[4]),
                "original_native_word_address":(
                    page_1_based,int(word[5]),int(word[6]),int(word[7])
                ),
                "original_word_bbox_pdf_pts":tuple(float(v) for v in word[:4]),
                "original_glyph_and_clip_integrity_verified":False,
            })
        lines={}
        for word in candidates:
            lines.setdefault(int(word[6]),[]).append(str(word[4]))
        rows.append({
            "material_code_untrusted":code,
            "native_original_material_block_number":block_no,
            "all_original_block_word_candidates":tuple(tokens),
            "native_original_printed_line_tokens":tuple(
                tuple(lines[line]) for line in sorted(lines)
            ),
            "authenticated_source_material_definition":False,
            "authenticated_physical_floor_occurrence":False,
        })
    return {
        "status":"original_native_material_schedule_words_only",
        "original_source_sha256":expected_sha256,
        "original_source_page_1_based":page_1_based,
        "all_original_schedule_row_candidates":tuple(rows),
        "requested_schedule_row_universe_complete_for_named_blocks":True,
        "source_glyph_raster_clip_and_material_issuer_proven":False,
        "physical_floor_finish_owner_authenticated":False,
        "new_firm_quantities":0,
    }
