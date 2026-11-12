"""Source-faithful A120 dark-filled structural bars and face-edge candidates.

Visible dark rectangles are painted INK and may represent wall or partition
bars, unlike large WHITE background fill rectangles. A bar's two long edges
can be used as native source geometry witnesses without extending either
edge, inferring a physical finished face, or publishing a ceiling m2 value.

Output intentionally does not send these to the production quantity issuer.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .engine import NativePage, SourceConflict, load_native_page
from .rcp_mask_wall_witnesses import (
    _is_dark_wall_like_source_ink,
    report_rcp_mask_wall_witnesses,
)


def _long_edges(rect: Any) -> tuple[tuple[str,tuple[float,float,float,float]], ...]:
    x0,y0,x1,y1=rect.bbox
    if x1-x0 >= y1-y0:
        return (
            ("y_min",(x0,y0,x1,y0)),
            ("y_max",(x0,y1,x1,y1)),
        )
    return (
        ("x_min",(x0,y0,x0,y1)),
        ("x_max",(x1,y0,x1,y1)),
    )


def dark_filled_wall_bar_face_candidates(page: NativePage) -> dict[str, Any]:
    """Keep both genuine long edges of each DARK original source fill bar.

    No WHITE masks, thick filled fields, unknown fill colours, or short
    black decorations become wall faces. Also no constructed extension
    beyond exact native source rectangle bounds.
    """
    if not isinstance(page, NativePage):
        raise SourceConflict("dark_wall_bar_native_page_required")
    seen: set[str] = set()
    bars=[]
    edges=[]
    edge_ids: set[str] = set()
    for bar in page.rectangles:
        if not _is_dark_wall_like_source_ink(bar):
            continue
        if bar.ref in seen:
            raise SourceConflict("duplicate_dark_wall_source_rect_ref")
        seen.add(bar.ref)
        # Both painted types matter: original PDF dark-filled strips may
        # ALSO have stroke ink around them. Skipping those loses real bars
        # supporting original A120 ceiling boundaries.
        native_box=[float(x) for x in bar.bbox]
        face_ids=[]
        for side, xyxy in _long_edges(bar):
            eid=f"{bar.ref}|original_dark_fill|{side}"
            if eid in edge_ids:
                raise SourceConflict("dark_wall_face_candidate_identity_reused")
            edge_ids.add(eid)
            face_ids.append(eid)
            edges.append({
                "source_face_candidate_id":eid,
                "source_rectangle_ref":bar.ref,
                "source_sha256":page.source_sha256,
                "page_index":page.page_index,
                "face_side_of_source_fill_bar":side,
                "source_long_edge_pdf_pts":[float(v) for v in xyxy],
                "original_bar_bbox_pdf_pts":native_box,
                "ink_colour":list(bar.fill_color or ()),
                "source_ink_role":"DARK_FILLED_NARROW_RECTANGLE",
                "stroke_present":bar.stroke_present,
                "no_extension_beyond_original_source_bar":True,
                "physical_wall_identity_authenticated":False,
                "finished_wall_face_authenticated":False,
                "wall_height_mm":None,
                "commercial_publishable":False,
                "benchmark_credit":False,
            })
        bars.append({
            "source_rectangle_ref":bar.ref,
            "source_sha256":page.source_sha256,
            "page_index":page.page_index,
            "native_bbox_pdf_pts":native_box,
            "ink_colour":list(bar.fill_color or ()),
            "stroke_present":bar.stroke_present,
            "source_long_face_candidate_ids":face_ids,
            "physical_wall_identity_authenticated":False,
            "commercial_publishable":False,
        })
    return {
        "schema_version":"0.1.0-shadow",
        "source_sha256":page.source_sha256,
        "page_index":page.page_index,
        "dark_painted_bar_count":len(bars),
        "long_face_candidate_count":len(edges),
        "dark_painted_bar_candidates":bars,
        "dark_bar_long_face_candidates":edges,
        "strictly_source_ink_only":True,
        "source_wall_identity_authenticated":False,
        "finished_face_length_verified":False,
        "commercial_publishable":False,
        "benchmark_credit":False,
        "official_score":None,
    }


def rcp_mask_source_dark_wall_edge_correspondence(page: NativePage) -> dict[str, Any]:
    """Trace supported mask sides back to the EXACT original dark bar faces.

    The coordinates recorded for a dark bar remain ITS OWN real painted
    long edge, NOT a line extrapolated to the edge of the white layout
    box. Owner's erroneous line through Sales thus stays absent.
    """
    paint=dark_filled_wall_bar_face_candidates(page)
    layout=report_rcp_mask_wall_witnesses(page)
    faces_by_bar:dict[str,list[dict[str,Any]]]={}
    for face in paint["dark_bar_long_face_candidates"]:
        faces_by_bar.setdefault(face["source_rectangle_ref"],[]).append(face)
    rows=[]
    for mask in layout["layout_mask_candidates"]:
        side_reports=[]
        for side, detail in mask["edges"].items():
            requested_axis_start, requested_axis_end=detail["axis_range_pdf_pts"]
            expected_constant=detail["constant_pdf_pts"]
            active=[]
            for bar_ref in detail["visible_dark_wall_ref_candidates"]:
                for face in faces_by_bar.get(bar_ref,[]):
                    if face["face_side_of_source_fill_bar"][0]!=side[0]:
                        continue
                    a,b,c,d=face["source_long_edge_pdf_pts"]
                    actual_const=b if side.startswith("y") else a
                    if abs(actual_const-expected_constant)>8.5:
                        continue
                    lo=max(requested_axis_start, a if side.startswith("y") else b)
                    hi=min(requested_axis_end, c if side.startswith("y") else d)
                    if hi <= lo:
                        continue
                    active.append({
                        "source_face_candidate_id":face["source_face_candidate_id"],
                        "source_rectangle_ref":bar_ref,
                        "actual_original_dark_bar_long_edge_pdf_pts":face["source_long_edge_pdf_pts"],
                        "clipped_span_for_layout_comparison_pdf_pts":[lo,hi],
                        "source_original_edge_not_prolonged":True,
                        "physical_wall_face_authenticated":False,
                    })
            side_reports.append({
                "layout_mask_side":side,
                "source_mask_boundary_is_not_ink":True,
                "dark_bar_long_face_candidates":active,
                "unsupported_layout_intervals_pdf_pts":detail["unsupported_intervals_pdf_pts"],
                "source_bar_support_fraction":detail["covered_fraction_by_dark_wall_ink"],
                "physical_wall_face_authenticated":False,
            })
        rows.append({
            "source_rectangle_ref":mask["source_rectangle_ref"],
            "material_code_candidate":mask["material_code_candidate"],
            "height_mm_source_candidate":mask["height_mm_source_candidate"],
            "source_layout_mask_not_physical_ceiling_border":True,
            "side_source_dark_wall_face_evidence":side_reports,
            "physical_ceiling_zone_authenticated":False,
            "metric_ceiling_area_m2":None,
        })
    return {
        "source_sha256":page.source_sha256,
        "rcp_page_index":page.page_index,
        "dark_bar_count":paint["dark_painted_bar_count"],
        "source_dark_bar_long_face_candidates":paint["dark_bar_long_face_candidates"],
        "layout_mask_count":len(rows),
        "layout_mask_boundary_source_correspondence":rows,
        "ceiling_area_count":0,
        "commercial_publishable":False,
        "benchmark_credit":False,
        "official_score":None,
    }


def main() -> int:
    parser=argparse.ArgumentParser(
        description="Source-native A120 dark wall-bar faces and white layout mask correspondence."
    )
    parser.add_argument("--pdf",type=Path,required=True)
    parser.add_argument("--page",type=int,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    page=load_native_page(args.pdf,args.page)
    packet=rcp_mask_source_dark_wall_edge_correspondence(page)
    with args.output.open("x",encoding="utf-8") as f:
        json.dump(packet,f,indent=2,sort_keys=True)
    print(json.dumps({
        "source_dark_wall_bars":packet["dark_bar_count"],
        "painted_long_face_candidates":len(packet["source_dark_bar_long_face_candidates"]),
        "layout_masks":packet["layout_mask_count"],
        "ceiling_area_count":0,
        "commercial_publishable":False,
    },sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
