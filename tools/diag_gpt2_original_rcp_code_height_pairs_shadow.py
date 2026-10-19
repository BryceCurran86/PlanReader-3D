"""Exact original PDF RCP code/height pairs, never room ceiling quantities.

A numeric original callout line in the SAME native text block as a separate
material-code line is a source observation. This does not prove height unit,
plan-view ownership, structural room equivalence, area, or ceiling surface.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz

# These are source *ceiling materials* in the Maryborough A120 legend.
# CLD3 is signage-contractor CLADDING and is deliberately absent.
_ALLOWED_CEILING_MARK_CODES=frozenset(("GRID","WFPB","FPB","IP"))


def audit_original_rcp_native_material_height_pairs(
    original_pdf_bytes: bytes, *, expected_sha256: str, page_1_based: int,
    material_codes: tuple[str,...]=("GRID","WFPB","FPB","IP"),
    max_source_words: int=100000,
) -> dict:
    if (type(original_pdf_bytes) is not bytes
            or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
            or hashlib.sha256(original_pdf_bytes).hexdigest()!=expected_sha256):
        raise ValueError("original_rcp_source_sha256_required")
    if type(page_1_based) is not int or page_1_based<1:
        raise ValueError("original_rcp_page_required")
    if (type(material_codes) not in (tuple,list)
            or not material_codes
            or any(type(x) is not str or x not in _ALLOWED_CEILING_MARK_CODES
                   for x in material_codes)
            or len(set(material_codes))!=len(material_codes)):
        raise ValueError("original_rcp_material_code_not_ceiling_role")
    if type(max_source_words) is not int or max_source_words<=0:
        raise ValueError("bounded_original_rcp_source_words_required")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as source:
        if page_1_based>len(source):
            raise ValueError("original_rcp_page_out_of_range")
        words=source[page_1_based-1].get_text("words",sort=False)
    if len(words)>max_source_words:
        raise ValueError("original_rcp_word_source_safety_cap")
    blocks={}
    seen=set()
    for w in words:
        if len(w)<8:
            raise ValueError("invalid_original_rcp_native_word")
        addr=(page_1_based,int(w[5]),int(w[6]),int(w[7]))
        if addr in seen:
            raise ValueError("duplicated_original_rcp_native_word_address")
        seen.add(addr)
        blocks.setdefault(int(w[5]),{}).setdefault(int(w[6]),[]).append(w)
    wanted=set(material_codes)
    pairs=[]
    unpaired=[]
    for block_id, lines in blocks.items():
        found=[w for entries in lines.values() for w in entries
               if str(w[4]).strip() in wanted]
        if not found:
            continue
        if (set(lines)=={0,1}
                and len(lines[0])==1 and len(lines[1])==1
                and str(lines[1][0][4]).strip() in wanted
                and re.fullmatch(r"[1-9][0-9]{2,4}",str(lines[0][0][4]).strip())):
            height=lines[0][0]; material=lines[1][0]
            if not all(type(z) in (float,int) and math.isfinite(z)
                       for w in (height,material) for z in w[:4]):
                raise ValueError("original_rcp_pair_word_bbox_nonfinite")
            pairs.append({
                "original_native_block":block_id,
                "source_material_code_untrusted":str(material[4]).strip(),
                "source_numeric_height_callout_uninterpreted":str(height[4]).strip(),
                "source_numeric_height_native_word_id":(
                    page_1_based,int(height[5]),int(height[6]),int(height[7])),
                "source_material_code_native_word_id":(
                    page_1_based,int(material[5]),int(material[6]),int(material[7])),
                "source_height_word_bbox_pdf_pts":
                    tuple(float(x) for x in height[:4]),
                "source_code_word_bbox_pdf_pts":
                    tuple(float(x) for x in material[:4]),
                "source_height_unit_or_elevation_semantic_proven":False,
                "source_original_ceiling_zone_owned":False,
            })
        else:
            unpaired.extend((
                page_1_based,int(w[5]),int(w[6]),int(w[7]),str(w[4]).strip()
            ) for w in found)
    return {
        "status":"original_rcp_ceiling_code_height_native_source_pairs_only",
        "original_source_sha256":expected_sha256,
        "original_page_1_based":page_1_based,
        "all_exact_native_code_numeric_callout_pairs":tuple(
            sorted(pairs,key=lambda row:row["source_material_code_native_word_id"])
        ),
        "original_unpaired_or_schedule_code_words":tuple(sorted(unpaired)),
        "source_rcp_viewport_owner_authenticated":False,
        "source_ceiling_material_definition_authenticated":False,
        "source_physical_room_ceiling_zone_owned":False,
        "source_code_height_unit_authenticated":False,
        "new_firm_quantities":0,
    }
