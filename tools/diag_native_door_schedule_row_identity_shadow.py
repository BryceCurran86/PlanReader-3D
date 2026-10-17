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

_DOOR_CODE=re.compile(r"^D(?:0[1-9]|[1-9][0-9]*)$",re.ASCII)
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
    """Enumerate every unique printed Dxx row, including non-swing doors.

    A source schedule can include automated sliding, glazed entry, coolroom
    contractor and partition-system doors. Do NOT silently exclude rows
    that lack SINGLE/SWING, or assume numeric width/height for D01.
    """
    blocks=defaultdict(list)
    for w in source_words:
        blocks[w["native_text_block"]].append(w)
    rows=[]
    for block,words in blocks.items():
        txt=[w["raw_literal_untrusted"] for w in words]
        codes=[x for x in txt if _DOOR_CODE.fullmatch(x)]
        if len(codes)!=1:
            continue
        # A standalone Dxx printed plan/detail label is not itself a
        # schedule row. The exact source-native block must contain actual
        # door semantics, not merely a familiar code.
        if "DOOR" not in txt and "SWING" not in txt:
            continue
        if "AUTOMATED" in txt and "SLIDING" in txt:
            kind="automated_double_sliding_candidate"
        elif "PARTITION" in txt and "SYSTEM" in txt:
            kind="partition_system_single_swing" if "SWING" in txt else "partition_system_candidate"
        elif "SOLID" in txt and "CORE" in txt:
            kind="solid_core_single_swing" if "SWING" in txt else "solid_core_candidate"
        elif "DISPLAY" in txt and "SHELVING" in txt and "DOOR" in txt:
            kind="coolroom_display_shelving_door_candidate"
        elif "SLIDING" in txt and "DOOR" in txt and "COOLROOM" in txt:
            kind="coolroom_sliding_door_candidate"
        elif "COOLROOM" in txt and "CONTRACTOR" in txt:
            kind="coolroom_contractor_candidate"
        elif "ALUMINIUM" in txt and "GLASS" in txt:
            kind="aluminium_framed_glass_candidate"
        else:
            kind="other_source_single_swing" if "SINGLE" in txt and "SWING" in txt else "other_source_door_candidate"
        start=txt.index("SWING")+1 if "SWING" in txt else txt.index(codes[0])+1
        nums=[(i,t) for i,t in enumerate(txt[start:],start) if _DIGITS.fullmatch(t)]
        # The first two source-row numbers may be width and height only
        # when BOTH are printed. No inferred count/standard dimensions.
        dimensions=nums[:2] if len(nums)>=2 else []
        original_width=dimensions[0][1] if dimensions else None
        original_height=dimensions[1][1] if dimensions else None
        rows.append({
            "source_native_text_block":block,
            "schedule_door_code_literal_untrusted":codes[0],
            "source_label_occurrences":[w for w in words
                if w["raw_literal_untrusted"]==codes[0]],
            "source_original_row_words":words,
            "source_row_has_single_swing_literals":"SINGLE" in txt and "SWING" in txt,
            "source_width_word_literal_untrusted":original_width,
            "source_height_word_literal_untrusted":original_height,
            "source_width_word_address":(
                words[dimensions[0][0]]["original_native_text_address"]
                if dimensions else None
            ),
            "source_height_word_address":(
                words[dimensions[1][0]]["original_native_text_address"]
                if dimensions else None
            ),
            "source_door_kind_candidate":kind,
            "source_height_derived_from_explicit_row_not_default":bool(dimensions),
            "source_dimensions_missing_or_untrusted":not bool(dimensions),
            "source_physical_room_perimeter_door_proven":False,
            "display_shelving_door_not_room_wall_assumed":(
                kind=="coolroom_display_shelving_door_candidate"
            ),
            "source_door_height_units_authenticated":False,
            "native_pdf_glyph_clip_paint_row_authenticated":False,
            "schedule_row_semantics_source_verified":False,
        })
    return sorted(rows,key=lambda row:(
        row["schedule_door_code_literal_untrusted"],row["source_native_text_block"]))

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
