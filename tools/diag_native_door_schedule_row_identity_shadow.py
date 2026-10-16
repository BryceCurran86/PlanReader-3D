"""Read-only native PDF schedule row -> labelled door occurrence first gate.

A printed door schedule row contains the identifier, type, width and height in
one source-owned text block, whereas the same door tag also occurs in plan and
elevations. No nearest label / dimension arithmetic, guessed count or default.
Native PyMuPDF text must additionally pass producer glyph/clip integrity;
this program does not make a material, door, count or customer quantity.
"""
from __future__ import annotations

from collections import defaultdict
import re

_DOOR_CODE=re.compile(r"^D[1-9][0-9]*$",re.ASCII)
_DIGITS=re.compile(r"^[1-9][0-9]*$",re.ASCII)


def _raw_words(page):
    rows=[]
    for w in page.get_text("words"):
        if len(w)<8:continue
        try:
            b,l,k=(int(w[5]),int(w[6]),int(w[7]))
        except (TypeError,ValueError,OverflowError):continue
        if min(b,l,k)<0:continue
        rows.append({
            "native_text_block":b,
            "original_native_text_address":[b,l,k],
            "raw_literal_untrusted":str(w[4]),
            "original_bbox_pdf_pts":[float(t) for t in w[:4]],
            "native_text_integrity_authenticated":False,
        })
    return rows


def _row_candidates(source_words):
    blocks=defaultdict(list)
    for w in source_words:
        blocks[w["native_text_block"]].append(w)
    rows=[]
    for block,words in blocks.items():
        txt=[w["raw_literal_untrusted"] for w in words]
        codes=[x for x in txt if _DOOR_CODE.fullmatch(x)]
        if not codes or "SINGLE" not in txt or "SWING" not in txt:
            continue
        # The original source table row, not nearest number, must own a single
        # printed door identifier and exactly one machine-readable WIDTH and
        # HEIGHT field. The two numeric fields sit after SINGLE, SWING in the
        # original producer word reading order.
        if len(codes)!=1:continue
        idx=txt.index("SWING")
        nums=[(i,t) for i,t in enumerate(txt[idx+1:],idx+1)
              if _DIGITS.fullmatch(t)]
        if len(nums)<2:continue
        rows.append({
            "source_native_text_block":block,
            "schedule_door_code_literal_untrusted":codes[0],
            "source_label_occurrences":[
                w for w in words if w["raw_literal_untrusted"]==codes[0]
            ],
            "source_original_row_words":words,
            "source_row_has_single_swing_literals":True,
            "source_width_word_literal_untrusted":nums[0][1],
            "source_height_word_literal_untrusted":nums[1][1],
            "source_width_word_address":next(
                w["original_native_text_address"] for w in words
                if w["raw_literal_untrusted"]==nums[0][1]
            ),
            "source_height_word_address":next(
                w["original_native_text_address"] for w in words
                if w["raw_literal_untrusted"]==nums[1][1]
            ),
            "native_pdf_glyph_clip_paint_row_authenticated":False,
            "schedule_row_semantics_source_verified":False,
        })
    return sorted(rows,key=lambda row:(row["schedule_door_code_literal_untrusted"],row["source_native_text_block"]))


def audit_original_door_schedule_row_candidates(
    schedule_page, *, other_plan_pages=(),
):
    if not isinstance(other_plan_pages,tuple):
        raise ValueError("explicit_original_plan_pages_tuple_required")
    original_rows=_row_candidates(_raw_words(schedule_page))
    schedules_by_code=defaultdict(list)
    for row in original_rows:
        schedules_by_code[row["schedule_door_code_literal_untrusted"]].append(row)
    original_tag_universe=defaultdict(list)
    for page_index,page in enumerate(other_plan_pages):
        for w in _raw_words(page):
            if _DOOR_CODE.fullmatch(w["raw_literal_untrusted"]):
                original_tag_universe[w["raw_literal_untrusted"]].append({
                    "caller_original_plan_page_index":page_index,
                    "original_source_word":w,
                    "source_tag_physical_opening_identity_authenticated":False,
                })
    receipt=[]
    for code in sorted(set(schedules_by_code)|set(original_tag_universe)):
        options=schedules_by_code.get(code,[])
        receipt.append({
            "original_door_label_literal_not_trusted":code,
            "source_schedule_candidates":options,
            "original_plan_label_competitors":original_tag_universe.get(code,[]),
            "unique_source_row_candidate_but_not_authority":len(options)==1,
            "first_unclosed_gate":(
                "missing_or_competing_schedule_source_rows"
                if len(options)!=1 else
                "text_glyph_clip_then_exact_physical_opening_identity"
            ),
            "default_count_1_not_permitted":True,
            "source_width_height_signed_to_opening":False,
            "source_material_or_quantity_authority_granted":False,
        })
    return {
        "status":"source_native_door_schedule_candidates_only",
        "all_original_schedule_row_candidates":original_rows,
        "original_plan_tag_and_schedule_comparisons":receipt,
        "original_pdf_untrusted_raw_text_not_promoted":True,
        "new_authoritative_opening_areas":0,
        "new_opening_counts":0,
        "new_customer_quantities":0,
    }
