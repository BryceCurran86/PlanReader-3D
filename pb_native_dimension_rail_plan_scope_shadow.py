"""Original PDF long-rail scope census, never a plan viewport or physical scale.

A one-sheet plan may have NO closed source vector frame even when large,
independently drawn horizontal/vertical figure rails bracket the actual
physical drawing. The source-native rails can constrain the next viewport
authority investigation, but not replace source-positive plan-role, structural
wall topology, complete footprint, or page-to-metre calibration.

This module reads the exact original SHA-verified PDF. Every returned segment
has an original path/item address. It never creates a SegmentedViewport,
canonical room/wall, measured area, QuantityEvidence, customer row or score.
"""
from __future__ import annotations

import hashlib
import math
from collections import Counter

import fitz


def _segments(page, orientation: str) -> list[dict]:
    width, height = float(page.rect.width), float(page.rect.height)
    if width <= 0 or height <= 0:
        return []
    found = []
    for path_id, drawing in enumerate(page.get_drawings()):
        color = drawing.get("color")
        native_width = drawing.get("width")
        if (
            type(color) not in (tuple, list) or len(color) != 3
            or any(type(v) not in (int, float) or
                   not math.isfinite(float(v)) or abs(float(v)) > 1e-5
                   for v in color)
            or type(native_width) not in (float, int)
            or not math.isfinite(float(native_width))
            or not 0.05 <= float(native_width) <= 1.0
        ):
            continue  # no graphite/paint/nonsolid legend assumed a dimensional rail
        for item_id, item in enumerate(drawing.get("items") or []):
            if not item or item[0] != "l" or len(item) < 3:
                continue
            a, b = item[1], item[2]
            coords = (a.x, a.y, b.x, b.y)
            if any(type(v) not in (int, float) or not math.isfinite(float(v)) for v in coords):
                continue
            dx, dy = abs(a.x - b.x), abs(a.y - b.y)
            if orientation == "horizontal":
                if dy > .05 or dx < width * .45:
                    continue
                constant = (a.y + b.y) / 2.
                span = sorted((a.x, b.x))
            elif orientation == "vertical":
                if dx > .05 or dy < height * .38:
                    continue
                constant = (a.x + b.x) / 2.
                span = sorted((a.y, b.y))
            else:
                raise ValueError("invalid source orientation")
            found.append({
                "orientation": orientation,
                "source_path_index": path_id,
                "source_item_index": item_id,
                "native_constant_pt": round(constant, 6),
                "native_span_pt": [round(span[0], 6), round(span[1], 6)],
                "native_length_pt": round(abs(span[1]-span[0]), 6),
                "source_stroke_width_pt": round(float(native_width), 6),
                "source_black_stroke": True,
            })
    return sorted(found, key=lambda x: (
        x["native_constant_pt"], -x["native_length_pt"],
        x["source_path_index"], x["source_item_index"],
    ))


def _source_title_words(page) -> list[dict]:
    groups = {}
    for item in page.get_text("words"):
        if len(item) < 8:
            continue
        x0,y0,x1,y1,token,block,line,word=item[:8]
        if not all(math.isfinite(float(v)) for v in (x0,y0,x1,y1)):
            continue
        groups.setdefault((int(block), int(line)), []).append(
            (int(word), str(token).strip(), (x0,y0,x1,y1))
        )
    title=[]
    for (block,line),words in groups.items():
        tokens=[token.upper() for _,token,_ in sorted(words)]
        if tokens == ["FLOOR","PLAN"]:
            boxes=[x[2] for x in words]
            title.append({
                "native_word_block":block, "native_word_line":line,
                "native_text":"FLOOR PLAN",
                "native_bbox_pdf_pts":[round(min(b[0] for b in boxes),6),
                    round(min(b[1] for b in boxes),6),
                    round(max(b[2] for b in boxes),6),
                    round(max(b[3] for b in boxes),6)],
                "title_word_source_only_not_plan_role":True,
            })
    return sorted(title,key=lambda x:(x["native_word_block"],x["native_word_line"]))


def original_dimension_rail_plan_candidate(
    pdf_bytes: bytes, *, source_sha256: str, page_index: int
) -> dict:
    if type(pdf_bytes) is not bytes:
        raise TypeError("original PDF must be immutable bytes")
    sha=hashlib.sha256(pdf_bytes).hexdigest()
    if sha != source_sha256:
        raise ValueError("original source SHA mismatch")
    if type(page_index) is not int or page_index < 0:
        raise ValueError("page_index invalid")
    with fitz.open(stream=pdf_bytes,filetype="pdf") as doc:
        if page_index >= len(doc):
            raise ValueError("page_index out of range")
        page=doc[page_index]
        page_size=[float(page.rect.width),float(page.rect.height)]
        rotation=int(page.rotation)
        h=_segments(page,"horizontal")
        v=_segments(page,"vertical")
        title=_source_title_words(page)
    result={
        "original_source_sha256":sha, "original_page_id":str(page_index+1),
        "native_page_size_pt":page_size,"native_rotation_degrees":rotation,
        "original_horizontal_rail_candidates":h,
        "original_vertical_rail_candidates":v,
        "original_exact_floor_plan_title_lines":title,
        "source_native_rail_region_candidate":None,
        "first_unclosed_gate":"independent_native_long_rails_unavailable",
        "source_plan_role_authenticated":False,
        "source_viewport_authenticated":False,
        "physical_wall_component_authenticated":False,
        "source_room_floor_owner_authenticated":False,
        "physical_scale_authenticated":False,
        "metric_area_published":False,
        "sealed_customer_quantity_ids":[],
        "benchmark_match_or_score_granted":False,
        "diagnostic_only":True,
    }
    if len(h)<2 or len(v)<2:
        return result
    upper,lower=h[0],h[-1]
    left,right=v[0],v[-1]
    # A duplicate or closely spaced competing extreme native stroke is not a
    # unique source boundary. Do not use longest/first arbitrary winner.
    eps=.75
    if (
        any(abs(item["native_constant_pt"]-upper["native_constant_pt"])<eps
            for item in h[1:])
        or any(abs(item["native_constant_pt"]-lower["native_constant_pt"])<eps
            for item in h[:-1])
        or any(abs(item["native_constant_pt"]-left["native_constant_pt"])<eps
            for item in v[1:])
        or any(abs(item["native_constant_pt"]-right["native_constant_pt"])<eps
            for item in v[:-1])
    ):
        result["first_unclosed_gate"]="competing_extreme_native_rail_source_claims"
        return result
    x0,x1=left["native_constant_pt"],right["native_constant_pt"]
    y0,y1=upper["native_constant_pt"],lower["native_constant_pt"]
    if (
        x1-x0 < page_size[0]*.60
        or y1-y0 < page_size[1]*.60
        or x0<=0 or y0<=0 or x1>=page_size[0] or y1>=page_size[1]
        or not all(rail["source_stroke_width_pt"]==
                upper["source_stroke_width_pt"] for rail in (lower,left,right))
    ):
        result["first_unclosed_gate"]="native_rail_extent_or_style_conflict"
        return result
    # Real drawings may have dimension rails that *bracket* the plan but do
    # not intersect at corners. This box is only the overall coordinate
    # envelope of those source-native segments, not a closed physical frame.
    result["source_native_rail_region_candidate"]={
        "bbox_pdf_pts":[x0,y0,x1,y1],
        "original_source_path_item_addresses":[
            [rail["source_path_index"],rail["source_item_index"]]
            for rail in (upper,lower,left,right)
        ],
        "source_native_closed_frame_proven":False,
        "source_complete_plan_footprint_proven":False,
        "source_plan_role_proven":False,
        "viewport_production_allowed":False,
    }
    result["first_unclosed_gate"]="source_rail_region_not_plan_viewport_or_room_authority"
    return result


__all__=["original_dimension_rail_plan_candidate"]
