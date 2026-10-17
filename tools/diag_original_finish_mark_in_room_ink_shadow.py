"""Original FT2/FT3 native mark → exact source-ink enclosure candidate.

Consumes the same-root four-edge source evidence and never treats geometric
containment or a code literal as W4 physical floor, authentic material
occurrence issuer, document scale or quantity.
"""
from __future__ import annotations
import math
import fitz
from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_enclosure_correspondence,
)


def _native_mark_containment_census(words,*,code:str,bbox):
    # Original-page native words are not equivalent to trusted PDF glyphs.
    # A malformed source competitor must be retained as a typed negative,
    # never dropped from a seemingly unique FT2/FT3 mark universe.
    if (type(bbox) not in (tuple,list) or len(bbox)!=4):
        raise ValueError("original_mark_enclosure_bbox_unavailable")
    try:
        x0,y0,x1,y1=(float(v) for v in bbox)
    except (TypeError,ValueError,OverflowError):
        raise ValueError("original_mark_enclosure_bbox_unavailable") from None
    if (not all(math.isfinite(v) for v in (x0,y0,x1,y1))
            or x0>=x1 or y0>=y1):
        raise ValueError("original_mark_enclosure_bbox_unavailable")
    matches=[]
    malformed=0
    for w in words:
        if len(w)<8 or str(w[4])!=code:continue
        try:
            a,b,c,d=(float(x) for x in w[:4])
            address=[int(v) for v in w[5:8]]
            valid=(all(math.isfinite(v) for v in (a,b,c,d))
                   and a<c and b<d
                   and all(type(v) is int and v>=0 for v in w[5:8]))
        except (TypeError,ValueError,OverflowError):
            valid=False
            a=b=c=d=0.
            address=[]
        within=bool(valid and x0<a and y0<b and c<x1 and d<y1)
        if not valid:
            malformed+=1
        matches.append({
            "original_source_word_address":address,
            "original_source_text_untrusted":str(w[4]),
            "original_source_bbox_pdf_pts":[a,b,c,d] if valid else None,
            "strict_containment_candidate":within,
            "source_word_geometry_and_address_valid":bool(valid),
            "original_native_text_integrity_proven":False,
            "producer_issued_material_occurrence":False,
        })
    owners=[w for w in matches if w["strict_containment_candidate"]]
    return {
        "all_original_same_code_words_in_page":matches,
        "in_enclosure_candidates":owners,
        "malformed_same_code_source_words":malformed,
        "unique_native_code_word_in_enclosure":len(owners)==1 and malformed==0,
        "physical_source_floor_owner_authenticated":False,
        "new_firm_quantities":0,
    }


def audit_original_floor_finish_mark_enclosure_candidate(
    original_pdf:bytes, *, expected_sha256:str,
    floor_page:int,finish_page:int,source_side_pairs,
    translation_pdf_pts:tuple[float,float],finish_code_literal:str,
):
    if (type(finish_code_literal) is not str or not finish_code_literal
            or not finish_code_literal.isalnum() or
            not any(x.isalpha() for x in finish_code_literal)):
        raise ValueError("explicit_original_finish_literal_required")
    witness=audit_source_enclosure_correspondence(
        original_pdf,expected_sha256=expected_sha256,
        floor_page_1_based=floor_page,finish_page_1_based=finish_page,
        original_side_pairs=source_side_pairs,
        expected_translation_pdf_pts=translation_pdf_pts,
    )
    if witness.get("status")!="original_four_edge_ink_correspondence_with_unclosed_doorway":
        return {"status":"no_source_edge_candidate","new_firm_quantities":0}
    sides=witness["original_witnesses"]
    left=sides["left"]["finish_source"]["ends"][0][0]
    right=sides["right"]["finish_source"]["ends"][0][0]
    top=sides["top_partial"]["finish_source"]["ends"][0][1]
    bottom=sides["bottom"]["finish_source"]["ends"][0][1]
    with fitz.open(stream=original_pdf,filetype="pdf") as doc:
        source=_native_mark_containment_census(
            doc[finish_page-1].get_text("words"),code=finish_code_literal,
            bbox=(left,top,right,bottom),
        )
    return {
        "status":"source_ink_bounded_finish_mark_candidate_only",
        "original_source_edge_witnesses":witness["original_witnesses"],
        "original_native_enclosure_bbox_pdf_pts":[left,top,right,bottom],
        "source_mark_word_evidence":source,
        "original_top_door_gap_remains_open":True,
        "unique_original_w4_finished_face_owner_proven":False,
        "source_mark_material_definition_issued":False,
        "original_cross_sheet_floor_identity_issued":False,
        "source_measurement_and_metric_area_proven":False,
        "new_firm_quantities":0,
    }
