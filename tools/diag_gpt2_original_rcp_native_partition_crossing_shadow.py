"""SHA-authenticated original RCP ink crossing a candidate viewport divider.

Diagnostic-only. A line crossing a derived viewport boundary is evidence
of incomplete source scope, not evidence that line is a structural wall,
GRID tile owner, ceiling finish occurrence, or a source-owned larger view.
"""
from __future__ import annotations

import hashlib
import math
import re

import fitz


def audit_original_source_rcp_ink_partition_crossings(
    pdf_bytes: bytes, *, expected_sha256: str,
    page_1_based: int, proposed_partition_coordinate_pdf_pts: float,
    source_material_codes: tuple[str,...] = ("GRID", "IPF1"),
    minimum_original_black_stroke_width_pdf_pts: float = 0.46,
    maximum_native_paths: int = 120000,
    maximum_crossings: int = 20000,
) -> dict:
    if (
        type(pdf_bytes) is not bytes or not pdf_bytes
        or type(expected_sha256) is not str
        or not re.fullmatch(r"[0-9a-f]{64}",expected_sha256)
        or hashlib.sha256(pdf_bytes).hexdigest() != expected_sha256
    ):
        raise ValueError("immutable_original_rcp_source_sha256_required")
    if type(page_1_based) is not int or page_1_based < 1:
        raise ValueError("original_rcp_page_required")
    if (type(proposed_partition_coordinate_pdf_pts) not in (int,float)
            or not math.isfinite(proposed_partition_coordinate_pdf_pts)):
        raise ValueError("finite_original_view_partition_required")
    if (type(minimum_original_black_stroke_width_pdf_pts) not in (float,int)
            or not math.isfinite(minimum_original_black_stroke_width_pdf_pts)
            or minimum_original_black_stroke_width_pdf_pts <= 0):
        raise ValueError("positive_original_stroke_filter_required")
    if (type(source_material_codes) not in (tuple,list) or not source_material_codes
            or len(source_material_codes) != len(set(source_material_codes))
            or any(type(x) is not str or not re.fullmatch("[A-Z][A-Z0-9]{1,11}", x)
                   for x in source_material_codes)):
        raise ValueError("original_source_material_codes_invalid")
    if (type(maximum_native_paths) is not int or maximum_native_paths <= 0
            or type(maximum_crossings) is not int or maximum_crossings <= 0):
        raise ValueError("bounded_original_rcp_source_required")
    with fitz.open(stream=pdf_bytes,filetype="pdf") as original:
        if page_1_based > len(original):
            raise ValueError("original_rcp_page_out_of_range")
        page = original[page_1_based-1]
        drawings = page.get_drawings()
        words = page.get_text("words", sort=False)
    if len(drawings) > maximum_native_paths or len(words) > 100000:
        raise ValueError("bounded_original_rcp_source_required")
    divider = float(proposed_partition_coordinate_pdf_pts)
    crossings = []
    for path_id, stroke in enumerate(drawings):
        if stroke.get("color") != (0.0,0.0,0.0):
            continue
        width = stroke.get("width")
        if (type(width) not in (float,int)
                or not math.isfinite(width)
                or width < minimum_original_black_stroke_width_pdf_pts):
            continue
        for item_id, item in enumerate(stroke.get("items",())):
            if len(item) < 3 or item[0] != "l":
                continue
            a,b = item[1],item[2]
            coords = (float(a.x),float(a.y),float(b.x),float(b.y))
            if not all(math.isfinite(v) for v in coords):
                raise ValueError("original_native_source_line_invalid")
            if a.x != b.x or not min(a.y,b.y) < divider < max(a.y,b.y):
                continue
            crossings.append({
                "original_native_path_item_id":f"d{path_id}i{item_id}",
                "original_axis":"vertical",
                "native_x_pdf_pts":float(a.x),
                "native_y_span_pdf_pts":tuple(sorted((float(a.y),float(b.y)))),
                "native_stroke_width_pdf_pts":float(width),
                "native_centerline_crosses_unverified_partition":True,
                "original_structural_wall_role_granted":False,
                "original_ceiling_material_occurrence_granted":False,
            })
            if len(crossings)>maximum_crossings:
                raise ValueError("original_native_partition_crossing_safety_cap")
    codes = set(source_material_codes)
    lexical = {"lower_pdf_coordinate_band":[],"higher_pdf_coordinate_band":[],
               "crossing_native_word_boundary":[]}
    for word in words:
        if str(word[4]).strip() not in codes:
            continue
        native = {
            "original_text_untrusted":str(word[4]),
            "native_source_word_address":(
                page_1_based,int(word[5]),int(word[6]),int(word[7])
            ),
            "original_word_bbox_pdf_pts":tuple(float(v) for v in word[:4]),
            "physical_rcp_occurrence_authenticated":False,
        }
        if word[3] <= divider:
            bucket="lower_pdf_coordinate_band"
        elif word[1] >= divider:
            bucket="higher_pdf_coordinate_band"
        else:
            bucket="crossing_native_word_boundary"
        lexical[bucket].append(native)
    return {
        "status":"original_rcp_partition_source_ink_crossing_census_only",
        "original_source_sha256":expected_sha256,
        "original_page_1_based":page_1_based,
        "proposed_partition_coordinate_unowned_pdf_pts":divider,
        "original_native_black_vertical_line_crossings":tuple(crossings),
        "original_material_code_words_by_proposed_coordinate_band":{
            key:tuple(sorted(value,key=lambda x:x["native_source_word_address"]))
            for key,value in lexical.items()
        },
        "proposed_partition_severs_original_ink":bool(crossings),
        "source_partition_owner_authenticated":False,
        "source_material_occurrence_owner_authenticated":False,
        "cross_view_ceiling_quantity_issued":False,
        "new_firm_quantities":0,
    }
