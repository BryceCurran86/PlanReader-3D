"""Two original RCP printed IPF marks and room words across original ink.

This is a SHA-native SOURCE text/ink location candidate only. A broken
partition line is NOT a closed canonical ceiling polygon, and a printed
IPF1 mark does not itself grant authenticated material/finish/metric authority.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

from tools.diag_original_room_four_edge_source_ink_shadow import _line


def audit_original_rcp_two_rooms_opposed_mark_words(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    rcp_page_1_based: int,
    source_room_mark_receipts: tuple[
        tuple[str, tuple[int,int,int], tuple[int,int,int]],...
    ],
    original_source_partition_ink_path_ids: tuple[str,...],
    expected_finish_code: str,
    max_original_source_paths: int=120000,
) -> dict:
    if (type(original_pdf_bytes) is not bytes or not original_pdf_bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_rcp_source_sha256_conflict")
    if (type(rcp_page_1_based) is not int or rcp_page_1_based<=0
            or type(expected_finish_code) is not str
            or not re.fullmatch(r"[A-Z][A-Z0-9]{1,11}",expected_finish_code)):
        raise ValueError("original_rcp_source_scope_or_material_invalid")
    if (type(source_room_mark_receipts) not in (tuple,list)
            or len(source_room_mark_receipts)!=2
            or any(type(row) not in (tuple,list) or len(row)!=3
                   or type(row[0]) is not str or not row[0]
                   or type(row[1]) not in (tuple,list) or len(row[1])!=3
                   or type(row[2]) not in (tuple,list) or len(row[2])!=3
                   or any(type(v) is not int or v<0
                          for sub in row[1:3] for v in sub)
                   for row in source_room_mark_receipts)):
        raise ValueError("two_source_owned_room_mark_receipts_required")
    ids=[tuple(addr) for _,r,m in source_room_mark_receipts
         for addr in (r,m)]
    if (len(set(ids))!=4
            or len(set(name for name,*_ in source_room_mark_receipts))!=2
            or type(original_source_partition_ink_path_ids) not in (tuple,list)
            or not original_source_partition_ink_path_ids
            or len(original_source_partition_ink_path_ids)>32
            or len(set(original_source_partition_ink_path_ids))!=
               len(original_source_partition_ink_path_ids)
            or type(max_original_source_paths) is not int
            or max_original_source_paths<=0):
        raise ValueError("original_rcp_source_ancestry_aliased_or_overbound")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as doc:
        if rcp_page_1_based>len(doc):
            raise ValueError("original_rcp_source_page_missing")
        page=doc[rcp_page_1_based-1]
        native=page.get_text("words",sort=False)
        paths=page.get_drawings()
    if len(native)>100000 or len(paths)>max_original_source_paths:
        raise ValueError("original_rcp_native_source_inventory_cap")
    word_index={}
    for w in native:
        if len(w)<8:
            raise ValueError("original_rcp_source_word_malformed")
        key=tuple(int(v) for v in w[5:8])
        if key in word_index:
            raise ValueError("original_rcp_source_word_id_duplicated")
        word_index[key]=w
    walls=tuple(_line(paths,addr) for addr
                in original_source_partition_ink_path_ids)
    x_fixed=None
    ink=[]
    for source in walls:
        (x0,y0),(x1,y1)=source["ends"]
        if (x0!=x1 or y0>=y1 or source["source_color"]!=(0.,0.,0.)
                or source["stroke_opacity"]!=1.):
            raise ValueError("independent_original_black_partition_ink_unavailable")
        if x_fixed is None:
            x_fixed=x0
        elif x0!=x_fixed:
            raise ValueError("original_rcp_partition_source_line_conflict")
        ink.append((y0,y1))
    ink=sorted(ink)
    # Prevent an overlapping wall/door glyph being mistaken for two
    # separate original partition witnesses; do NOT bridge any real gap.
    if any(ink[i][1]>ink[i+1][0] for i in range(len(ink)-1)):
        raise ValueError("original_source_partition_ink_overlap_conflict")
    def word_receipt(addr):
        w=word_index.get(tuple(addr))
        if w is None:
            raise ValueError("original_room_or_finish_word_source_missing")
        box=tuple(float(v) for v in w[:4])
        if any(not math.isfinite(v) for v in box):
            raise ValueError("original_rcp_native_word_bbox_nonfinite")
        return w,box
    rows=[]
    for room,room_addr,mark_addr in source_room_mark_receipts:
        room_word,room_box=word_receipt(room_addr)
        mark_word,mark_box=word_receipt(mark_addr)
        if str(room_word[4]).strip()!=room or str(mark_word[4]).strip()!=expected_finish_code:
            raise ValueError("original_source_room_finish_word_text_conflict")
        # Both words must be FULLY on the same source ink side.
        left = room_box[2]<x_fixed and mark_box[2]<x_fixed
        right = room_box[0]>x_fixed and mark_box[0]>x_fixed
        if not left and not right:
            raise ValueError("original_rcp_room_and_mark_not_same_ink_side")
        rows.append({
            "source_room_name_untrusted":room,
            "original_room_word_address":(rcp_page_1_based,*tuple(room_addr)),
            "original_finish_word_address":(rcp_page_1_based,*tuple(mark_addr)),
            "source_original_ink_side":"left" if left else "right",
            "source_trusted_room_finish_zone_authenticated":False,
            "source_original_ceiling_area_issued":False,
        })
    if rows[0]["source_original_ink_side"]==rows[1]["source_original_ink_side"]:
        raise ValueError("original_room_mark_pairs_not_opposite_source_sides")
    competitors=tuple(
        (rcp_page_1_based,int(w[5]),int(w[6]),int(w[7]))
        for w in native if str(w[4]).strip()==expected_finish_code
    )
    if not set((row["original_finish_word_address"] for row in rows))<=set(competitors):
        raise ValueError("original_rcp_finish_word_universe_incomplete")
    return {
        "status":"two_original_printed_rcp_room_finish_candidates_opposite_ink",
        "original_source_sha256":expected_sha256,
        "original_source_page_1_based":rcp_page_1_based,
        "source_finish_code_untrusted":expected_finish_code,
        "source_original_partition_ink_ids":tuple(
            original_source_partition_ink_path_ids),
        "source_original_partition_ink_axis_x_pdf_pts":x_fixed,
        "source_original_partition_ink_intervals_pdf_pts":tuple(ink),
        "source_source_original_partition_closed_wall_verified":False,
        "source_original_room_finish_receipts":tuple(rows),
        "all_original_same_code_native_words_including_schedule":competitors,
        "source_rcp_viewport_ownership_authenticated":False,
        "source_rcp_physical_ceiling_zone_geometry_authenticated":False,
        "source_material_definition_and_occurrence_authenticated":False,
        "new_firm_quantities":0,
    }
