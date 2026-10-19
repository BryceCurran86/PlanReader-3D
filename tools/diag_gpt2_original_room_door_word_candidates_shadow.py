"""Original source room-name and door-word census against an unsealed ink ring.

This does not prove source text glyph/clip integrity, physical wall identity,
printed door schedule authority, or any measured/finished floor area.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz


def audit_original_room_ring_word_candidates(
    pdf_bytes:bytes, *,expected_sha256:str,
    original_ring_source_candidate:dict,
    expected_original_room_text:str,
    expected_original_door_mark_text:str,
) -> dict:
    base={
        "status":"source_room_and_door_word_candidate_abstained",
        "first_unclosed_gate":"independent_original_room_or_door_text_unavailable",
        "original_room_label_semantic_owner_authenticated":False,
        "original_door_opening_or_threshold_authenticated":False,
        "original_room_physical_wall_owner_authenticated":False,
        "new_firm_quantities":0,
    }
    if (type(pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("immutable_original_room_source_sha256_required")
    if (type(original_ring_source_candidate) is not dict
            or original_ring_source_candidate.get("status") !=
               "original_black_ink_room_ring_with_virtual_door_gap_candidate"
            or original_ring_source_candidate.get("original_source_sha256")
               !=expected_sha256):
        return {**base,"first_unclosed_gate":"original_source_ink_ring_candidate_unproven"}
    for text in (expected_original_room_text,expected_original_door_mark_text):
        if (type(text) is not str or not text or text != text.strip()
                or not re.fullmatch(r"[A-Z0-9][A-Z0-9 -]{1,63}", text)):
            raise ValueError("original_source_word_text_invalid")
    page_no=original_ring_source_candidate.get("original_source_page_1_based")
    vertices=original_ring_source_candidate.get("original_source_candidate_ring_pdf_pts")
    gap=original_ring_source_candidate.get("original_source_top_ink_door_gap_pdf_pts")
    if (type(page_no) is not int or page_no<=0
            or type(vertices) not in (tuple,list) or len(vertices)!=4
            or type(gap) not in (tuple,list) or len(gap)!=2):
        return {**base,"first_unclosed_gate":"original_source_ring_geometry_invalid"}
    try:
        corners=tuple((float(p[0]),float(p[1])) for p in vertices)
        points=tuple((float(p[0]),float(p[1])) for p in gap)
    except (TypeError,ValueError,IndexError,OverflowError):
        return {**base,"first_unclosed_gate":"original_source_ring_geometry_invalid"}
    if (not all(math.isfinite(v) for point in (*corners,*points) for v in point)
            or len(set(corners))!=4):
        return {**base,"first_unclosed_gate":"original_source_ring_geometry_invalid"}
    xs=[x for x,y in corners]
    ys=[y for x,y in corners]
    x0,x1=min(xs),max(xs)
    y0,y1=min(ys),max(ys)
    if (x0>=x1 or y0>=y1
            or not all(p[1]==y0 for p in points)
            or not x0<=points[0][0]<points[1][0]<=x1):
        return {**base,"first_unclosed_gate":"original_source_ring_geometry_invalid"}
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if page_no>len(doc):
            return {**base,"first_unclosed_gate":"original_source_page_out_of_bounds"}
        words=doc[page_no-1].get_text("words",sort=False)
    if len(words)>100000:
        raise ValueError("bounded_original_text_source_words_required")
    selected={expected_original_room_text,expected_original_door_mark_text}
    all_words={key:[] for key in selected}
    for row in words:
        value=str(row[4]).strip().upper()
        if value not in selected:
            continue
        native_bbox=tuple(float(v) for v in row[:4])
        if any(not math.isfinite(v) for v in native_bbox):
            raise ValueError("original_source_word_bbox_nonfinite")
        all_words[value].append({
            "original_native_word_address":(
                page_no,int(row[5]),int(row[6]),int(row[7])
            ),
            "original_source_word_bbox_pdf_pts":native_bbox,
            "printed_word_text_untrusted":value,
            "source_word_glyph_and_clip_authenticated":False,
        })
    def is_inside(word):
        a,b,c,d=word["original_source_word_bbox_pdf_pts"]
        return a>=x0 and c<=x1 and b>=y0 and d<=y1
    def in_door_gap(word):
        a,b,c,d=word["original_source_word_bbox_pdf_pts"]
        cx=(a+c)/2
        return points[0][0]<=cx<=points[1][0] and b<=y0<=d
    rooms=tuple(all_words[expected_original_room_text])
    doors=tuple(all_words[expected_original_door_mark_text])
    inside=tuple(row for row in rooms if is_inside(row))
    outside=tuple(row for row in rooms if not is_inside(row))
    gap_mark=tuple(row for row in doors if in_door_gap(row))
    row={
        **base,
        "original_source_sha256":expected_sha256,
        "original_source_page_1_based":page_no,
        "all_original_same_room_word_candidates":rooms,
        "all_original_same_door_word_candidates":doors,
        "source_name_words_inside_candidate_ring":inside,
        "other_original_same_room_word_competitors":outside,
        "original_door_words_straddling_real_source_gap":gap_mark,
    }
    if len(inside)!=1 or len(gap_mark)!=1:
        return {**row,
            "first_unclosed_gate":"original_source_label_or_door_mark_not_unique"}
    return {
        **row,
        "status":"one_original_room_text_and_door_gap_word_source_candidate",
        "first_unclosed_gate":"source_text_ink_wall_role_and_door_threshold_unverified",
        "new_firm_quantities":0,
    }
