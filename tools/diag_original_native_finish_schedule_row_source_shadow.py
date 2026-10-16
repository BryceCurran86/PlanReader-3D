"""Original PDF same-native-text-block floor finish schedule source candidates.

A CAD material schedule can be encoded as one text block per material row,
with columns expressed as independent lines inside that block. This reader
preserves exact native word addresses and distinguishes floor tile semantics
from lookalike wall tile/paint codes. It enumerates *all* plan marks of each
code independently; no nearest label, schedule proximity, source text
auto-trust, physical ring/finish area or customer quantity publication.

The source native word/block is a renderer extraction address, not an
authenticated production SourceVisibilityProducer receipt.
"""
from __future__ import annotations

from collections import defaultdict
import re

MATERIAL_CODE_PATTERN=re.compile(r"^[A-Z][A-Z0-9]{1,7}$")
MEASUREMENT_PATTERN=re.compile(r"^[1-9][0-9]{1,4}[xX×][1-9][0-9]{1,4}$")


def _native_words(page):
    rows=[]
    for word in page.get_text("words") or ():
        if len(word)<8:
            continue
        try:
            block,line,index=tuple(int(v) for v in word[5:8])
            bbox=[float(v) for v in word[:4]]
        except (TypeError,ValueError,OverflowError):
            continue
        rows.append({
            "original_native_word_address":[block,line,index],
            "original_native_word_bbox_pdf_pts":bbox,
            "original_pdf_text_literal_untrusted":str(word[4]),
            "native_pdf_unicode_clip_paint_authenticated":False,
        })
    return rows


def audit_source_owned_material_schedule_rows(
    page, *, original_code_literals:tuple[str,...],
    original_plan_candidate_bbox:tuple[float,float,float,float],
    original_schedule_candidate_bbox:tuple[float,float,float,float],
):
    if (type(original_code_literals) is not tuple
            or not original_code_literals
            or len(set(original_code_literals))!=len(original_code_literals)
            or any(type(x) is not str or not MATERIAL_CODE_PATTERN.fullmatch(x)
                   for x in original_code_literals)):
        raise ValueError("distinct_native_finish_code_literals_required")
    for box in (original_plan_candidate_bbox,original_schedule_candidate_bbox):
        if (type(box) is not tuple or len(box)!=4
                or not all(type(v) in (int,float) for v in box)
                or box[0]>=box[2] or box[1]>=box[3]):
            raise ValueError("explicit_independent_native_viewport_scopes_required")
    if not (original_plan_candidate_bbox[2]<original_schedule_candidate_bbox[0]
            or original_schedule_candidate_bbox[2]<original_plan_candidate_bbox[0]
            or original_plan_candidate_bbox[3]<original_schedule_candidate_bbox[1]
            or original_schedule_candidate_bbox[3]<original_plan_candidate_bbox[1]):
        raise ValueError("overlapping_finish_plan_and_schedule_scopes")
    all_words=_native_words(page)
    blocks=defaultdict(list)
    for row in all_words:
        blocks[row["original_native_word_address"][0]].append(row)
    code_set=set(original_code_literals)
    scopes={
        "original_plan_candidate":original_plan_candidate_bbox,
        "original_schedule_candidate":original_schedule_candidate_bbox,
    }
    rows=[]
    plan_marks=[]
    for block_id,words in sorted(blocks.items()):
        literals=[w["original_pdf_text_literal_untrusted"] for w in words]
        own_codes=[code for code in code_set if code in literals]
        for code in own_codes:
            code_words=[w for w in words
                        if w["original_pdf_text_literal_untrusted"]==code]
            for w in code_words:
                x0,y0,x1,y1=w["original_native_word_bbox_pdf_pts"]
                centre=((x0+x1)/2,(y0+y1)/2)
                owners=[name for name,b in scopes.items()
                        if b[0]<=centre[0]<=b[2] and b[1]<=centre[1]<=b[3]]
                if len(owners)!=1:
                    plan_marks.append({
                        "original_code_literal_untrusted":code,
                        "original_code_source_word":w,
                        "first_unclosed_scope_gate":"source_viewport_scope_missing_or_conflicting",
                        "physical_plan_finish_owner_authenticated":False,
                    })
                    continue
                if owners[0]=="original_plan_candidate":
                    plan_marks.append({
                        "original_code_literal_untrusted":code,
                        "original_code_source_word":w,
                        "original_plan_view_scope_candidate_only":True,
                        "first_unclosed_scope_gate":"trusted_code_and_physical_source_floor_ring",
                        "physical_plan_finish_owner_authenticated":False,
                    })
                    continue
                native_line_groups=defaultdict(list)
                for member in words:
                    native_line_groups[member["original_native_word_address"][1]].append(
                        member["original_pdf_text_literal_untrusted"]
                    )
                others=[v for v in own_codes if v!=code]
                floor_token="FLOOR" in literals and "TILE" in literals
                wall_token="WALL" in literals and "TILE" in literals
                dimensions=[w for w in words if MEASUREMENT_PATTERN.fullmatch(
                    w["original_pdf_text_literal_untrusted"])]
                # Every material description word and code must be in ONE
                # native text block. A parallel wall tile row is a competing
                # floor-vs-wall material role, never an alias for floor tile.
                row_source_positive=(
                    len(code_words)==1 and not others and floor_token
                    and not wall_token and len(dimensions)==1
                )
                rows.append({
                    "original_native_text_block_id":block_id,
                    "original_material_code_literal_untrusted":code,
                    "original_source_code_word":w,
                    "original_manufacturer_line_untrusted":list(native_line_groups.get(1,())),
                    "original_description_line_untrusted":list(native_line_groups.get(2,())),
                    "original_native_row_lines_untrusted":[
                        {"original_native_line":key,"source_literals":list(tokens)}
                        for key,tokens in sorted(native_line_groups.items())
                    ],
                    "original_source_dimension_word_candidates":dimensions,
                    "source_native_same_block_floor_role_candidate":row_source_positive,
                    "source_native_wall_finish_row_not_floor":wall_token,
                    "first_unclosed_definition_gate":(
                        "source_text_glyph_clip_paint_and_schedule_role"
                        if row_source_positive else
                        "missing_or_conflicting_original_material_row"
                    ),
                    "source_schedule_definition_authentication_granted":False,
                    "source_original_text_trust_granted":False,
                })
    summary={}
    for code in sorted(code_set):
        a=[x for x in rows if x["original_material_code_literal_untrusted"]==code]
        marks=[x for x in plan_marks if x["original_code_literal_untrusted"]==code
               and x.get("original_plan_view_scope_candidate_only")]
        summary[code]={
            "original_schedule_row_candidates":len(a),
            "native_sameblock_floor_role_candidates":sum(
                x["source_native_same_block_floor_role_candidate"] for x in a),
            "original_inplan_mark_word_candidates":len(marks),
            "material_role_authenticated":False,
            "physical_occurrence_issued":0,
            "floor_finish_area_m2_authenticated":0,
        }
    return {
        "status":"original_source_same_block_schedule_and_plan_marks_candidate_only",
        "original_source_schedule_row_candidates":rows,
        "original_source_inplan_mark_candidates":plan_marks,
        "all_original_source_finish_code_summaries":summary,
        "native_word_universe_complete":True,
        "original_source_viewport_role_authentic":False,
        "original_source_physical_floor_correspondence":False,
        "new_source_material_definitions":0,
        "new_source_finish_occurrences":0,
        "new_floor_finish_area_m2":0,
        "new_customer_quantities":0,
    }
