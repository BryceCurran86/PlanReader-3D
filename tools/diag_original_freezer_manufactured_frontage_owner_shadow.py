"""Original manufactured coolroom frontage versus physical shell competitors.

The original Dxx schedule describes whether a cabinet door is display
shelving or an access door; this does not establish a physical wall or a
source host on the plan. Preserve distinct parallel original source ink
columns across two same-root plan views and do not close a room at casing.
"""
from __future__ import annotations
import hashlib
import fitz
from tools.diag_original_crosssheet_native_ink_registration_shadow import (
    audit_original_cross_sheet_source_translation,
)


def _original_schedule_door_words(page, codes):
    result={}
    for code in codes:
        rows={}
        for w in page.get_text("words"):
            rows.setdefault(int(w[5]),[]).append(w)
        matches=[
            w for block,w in rows.items()
            if w and str(w[0][4])==code
            and any(str(x[4])=="DOOR" for x in w)
        ]
        if len(matches)!=1:
            raise ValueError("original_door_schedule_row_ambiguous")
        row=matches[0]
        result[code]={
            "original_code":code,
            "original_word_ids":[[int(v) for v in word[5:8]] for word in row],
            "untrusted_original_literals":[str(word[4]) for word in row],
            "source_row_text_integrity_granted":False,
            "physical_plan_opening_owner_granted":False,
        }
    return result


def audit_original_manufactured_frontage_competitors(
    original_pdf:bytes, *, expected_sha256:str,
    floor_page:int, finish_page:int, schedule_page:int,
    original_floor_bbox:tuple[float,float,float,float],
    original_finish_bbox:tuple[float,float,float,float],
    inner_front_source_ids:tuple[str,str],
    outer_case_source_ids:tuple[str,str],
    access_door_code:str, manufacturer_door_codes:tuple[str,...],
    expected_translation_pdf_pts:tuple[float,float],
):
    if type(original_pdf) is not bytes or hashlib.sha256(original_pdf).hexdigest()!=expected_sha256:
        raise ValueError("immutable_source_sha_required")
    if (type(inner_front_source_ids) is not tuple
            or type(outer_case_source_ids) is not tuple
            or len(inner_front_source_ids)!=2 or len(outer_case_source_ids)!=2
            or len(set(inner_front_source_ids+outer_case_source_ids))!=4
            or type(manufacturer_door_codes) is not tuple
            or not manufacturer_door_codes
            or access_door_code in manufacturer_door_codes):
        raise ValueError("separate_manufactured_frontage_and_door_universes_required")
    with fitz.open(stream=original_pdf,filetype="pdf") as doc:
        if len({floor_page,finish_page,schedule_page})!=3 or not all(
                isinstance(i,int) and 1<=i<=len(doc) for i in
                (floor_page,finish_page,schedule_page)):
            raise ValueError("three_distinct_original_source_pages_required")
        r=audit_original_cross_sheet_source_translation(
            doc[floor_page-1],doc[finish_page-1],
            native_candidate_bbox_a=original_floor_bbox,
            native_candidate_bbox_b=original_finish_bbox,
            native_min_line_length_pt=30.,max_offset_pdf_pt=300.,
        )
        if not r.get("source_candidate_universe_complete"):
            return {"status":"source_stroke_universe_incomplete",
                    "physical_source_room_enclosed":False,
                    "new_firm_quantities":0}
        groups=[g for g in r["all_competing_translation_groups"]
                if g["original_source_translation_pdf_pts"]==list(expected_translation_pdf_pts)]
        if len(groups)!=1:
            raise ValueError("exact_source_translation_missing_or_ambiguous")
        candidates=groups[0]["all_original_candidate_pairs"]
        matched_ids={x["source_original_a_path_item_id"] for x in candidates}
        needed=set(inner_front_source_ids+outer_case_source_ids)
        if not needed<=matched_ids:
            raise ValueError("missing_original_frontage_source_pair")
        rows={r["source_path_item_id"]:r for r in r["source_original_a_rows"]}
        def col(ids):
            observations=[rows[i] for i in ids]
            if any(x["native_axis"]!="native_vertical" for x in observations):
                raise ValueError("parallel_frontage_lines_required")
            xs={x["original_endpoints_pdf_pts"][0][0] for x in observations}
            if len(xs)!=1:raise ValueError("inconsistent_source_frontage_column")
            return next(iter(xs))
        inner,outer=col(inner_front_source_ids),col(outer_case_source_ids)
        if inner>=outer:
            raise ValueError("inside_manufactured_frontage_and_outer_case_conflict")
        door_rows=_original_schedule_door_words(
            doc[schedule_page-1],(access_door_code,*manufacturer_door_codes))
        access=door_rows[access_door_code]["untrusted_original_literals"]
        if not {"SLIDING","DOOR"}<=set(access):
            raise ValueError("access_door_source_type_unresolved")
        for code in manufacturer_door_codes:
            words=set(door_rows[code]["untrusted_original_literals"])
            if not {"DISPLAY","SHELVING","DOOR","MANUFACTURER"}<=words:
                raise ValueError("display_cabinet_source_type_unresolved")
        return {
            "status":"original_coolroom_parallel_frontage_roles_compete",
            "inner_frontage_source_ids":inner_front_source_ids,
            "outer_case_source_ids":outer_case_source_ids,
            "inner_original_x_pdf_pts":inner,
            "outer_case_original_x_pdf_pts":outer,
            "original_ink_column_separation_pdf_pts":round(outer-inner,3),
            "original_access_and_manufactured_door_rows":door_rows,
            "original_double_cabinet_ink_not_structural_wall_proof":True,
            "physical_source_room_enclosed":False,
            "display_door_count_default_one_forbidden":True,
            "source_metric_wall_or_opening_width_proven":False,
            "new_firm_quantities":0,
        }
